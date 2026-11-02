"""Verifier: selects one typed assertion from an explicit requirement.

It sees the requirement, the inputs and steps to repeat, the tested controls and
form context, and the form controls from its OWN fresh observation. It does not
see the tester's verdict or observed outcome. It judges whether the requirement
applies to what was tested and chooses the assertion; code checks the shape of
that judgement, replays the steps in fresh contexts and evaluates the assertion.
Code cannot prove the judgement is semantically right.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, TypeAdapter

from flowlens.agents import input_tester
from flowlens.agents.common import parse_json_reply
from flowlens.agents.explorer import render_observation
from flowlens.models.contracts import AssertionType, DiscoveredForm, Finding, Observation
from flowlens.verification.assertions import VOCABULARY_DOC

AGENT_ID = "verifier"


class ChosenAssertion(BaseModel):
    type: AssertionType
    params: dict[str, Any] = Field(default_factory=dict)


class VerifierDecision(BaseModel):
    reasoning: str = Field(max_length=800)
    requirement_ref: str = Field(max_length=20)
    # Does the requirement text itself state the behaviour being checked?
    explicit: bool
    requirement_quote: str = Field("", max_length=400)  # words from the requirement that state it
    # Does the requirement govern the tested form, control and action? Missing means not assessed.
    applicability: Literal["applies", "not_applicable", "ambiguous"] | None = None
    applicability_target: str = Field("", max_length=160)  # the tested control or action it governs
    applicability_reason: str = Field("", max_length=300)
    assertion: ChosenAssertion | None = None
    expected: str = Field("", max_length=300)


_decision = TypeAdapter(VerifierDecision)

SYSTEM = f"""You are the Verifier inside FlowLens, a website reviewer. A candidate defect was reported \
against an explicit requirement. Code will repeat the reported inputs in fresh browser sessions with fresh \
test data and then evaluate ONE assertion that you choose against the resulting page.

First decide whether the requirement applies to the tested form, control and action. Judge this from the \
control's name and type, the page, the form's purpose and the requirement's wording, never from what the entered \
value looks like. A value resembling a date, email or number in a free-text field does not make that field \
subject to a rule about dates, emails or numbers. Reply "applies" and name the tested control or action as \
"applicability_target"; reply "not_applicable" if it governs something else; reply "ambiguous" if the requirement \
does not let you tell. Repeating a behaviour cannot show that a requirement applies, so do not assume it does. \
Unless it applies, give no assertion: the candidate stays inconclusive.

Then decide whether the requirement text explicitly states what must happen for these inputs. A \
requirement that only describes what something has or contains does not make a value mandatory or forbidden. \
If it is not explicit, reply with "explicit": false and no assertion; the candidate stays a review observation.

Otherwise choose the assertion that the page must satisfy if the requirement is met after the actions. Code decides \
the outcome: if the assertion fails, the requirement violation is confirmed; if it passes, the candidate \
is not reproduced. Do not try to predict the outcome; encode the requirement faithfully.

Assertion vocabulary (type and params):
{VOCABULARY_DOC}

Reply with ONE JSON object and nothing else:
{{"reasoning": "<short>", "requirement_ref": "<the requirement id>", "explicit": true | false,
  "applicability": "applies" | "not_applicable" | "ambiguous",
  "applicability_target": "<tested control or action name>",
  "applicability_reason": "<one short sentence from the control, page and requirement>",
  "requirement_quote": "<exact words from the requirement that state the expected behaviour>",
  "assertion": {{"type": "<one type above>", "params": {{...}}}} | null,
  "expected": "<the expected value in plain words>"}}
Reply with compact JSON on a single line (no indentation)."""


def render_tested(finding: Finding, form: DiscoveredForm | None) -> str:
    """Each entered value with the control it went into, as observed."""
    fields = {f.control.name.casefold(): f.control for f in form.fields} if form else {}
    lines = []
    for name, value in finding.inputs.items():
        c = fields.get(" ".join(name.split()).casefold())
        kind = "unknown control" if c is None else c.role + (f", type={c.input_type}" if c.input_type else "")
        lines.append(f"  - {json.dumps(name)} ({kind}) = {json.dumps(value, ensure_ascii=False)}")
    return "\n".join(lines) or "  (none: this test only uses the action)"


def applicability_problem(decision: VerifierDecision, finding: Finding) -> str | None:
    """Why this reply cannot back a requirement check. Checks its shape, not whether it is right."""
    ref = finding.requirement_ref
    why = decision.applicability_reason[:240]
    if decision.applicability is None:
        return f"Verifier did not assess whether {ref} applies to what was tested"
    if decision.applicability == "not_applicable":
        return f"Verifier judged that {ref} does not apply to what was tested: {why}"
    if decision.applicability == "ambiguous":
        return f"Verifier could not tell whether {ref} applies to what was tested: {why}"
    used = {" ".join(n.split()).casefold() for n in finding.inputs}
    used |= {s.control.name.casefold() for s in finding.reproduction_steps if s.type == "click" and s.control}
    target = " ".join(decision.applicability_target.split()).casefold()
    if target not in used:
        return f"Verifier said {ref} applies to {decision.applicability_target!r}, which this test did not use"
    if not decision.applicability_reason.strip():
        return f"Verifier said {ref} applies but gave no reason"
    return None


def build_messages(finding: Finding, fresh_obs: Observation, note: str | None = None,
                   check_before: Observation | None = None, form: DiscoveredForm | None = None):
    steps = "\n".join(f"  {i}. {s.describe()}" for i, s in enumerate(finding.reproduction_steps, 1))
    user = (
        f"Requirement {finding.requirement_ref}: {finding.requirement_text}\n\n"
        f"Inputs to repeat: {json.dumps(finding.inputs, ensure_ascii=False)}\n"
        f"Controls the test used:\n{render_tested(finding, form)}\n"
        f"Steps code will repeat after reaching the start page:\n{steps}\n\n"
        + (f"Form under test: {form.route}\n{input_tester.render_form(form)}\n\n" if form else "") +
        f"Start page as you observed it in a fresh session (before the steps):\n{render_observation(fresh_obs)}"
    )
    if check_before is not None:
        user += (f"\n\nCheck page {finding.check_path}, opened in the same fresh session BEFORE the steps "
                 f"(the assertion is evaluated on this page AFTER the steps):\n{render_observation(check_before)}")
    if note:
        user += f"\n\nNote: {note}"
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def parse_decision(content: str) -> VerifierDecision:
    return parse_json_reply(content, _decision, "verifier decision")
