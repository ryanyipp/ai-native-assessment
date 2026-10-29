"""Input tester: designs bounded input cases for one discovered form, then assesses outcomes.

It receives only the form handoff (fields and controls as observed by an
explorer, page headings and text) and the supplied requirements. Code executes
each case in a fresh browser context with its own test-data workspace. The
tester's assessments are candidate findings, never confirmations.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field, TypeAdapter

from flowlens.agents.common import parse_json_reply, render_facts, render_requirements
from flowlens.models.contracts import DiscoveredForm, Handoff

AGENT_ID = "input-tester"


class PlannedCase(BaseModel):
    label: str = Field(max_length=120)
    inputs: dict[str, str] = Field(max_length=12)  # field name -> exact value
    submit: str | None = Field(None, max_length=160)  # submit control name
    requirement_ref: str | None = Field(None, max_length=20)
    expected: str = Field(max_length=200)
    # Optional same-site page whose content the requirement says should change because of the action.
    check_page: str | None = Field(None, max_length=200, pattern=r"^/[^\s]*$")


class TestPlan(BaseModel):
    __test__ = False

    reasoning: str = Field(max_length=300)
    cases: list[PlannedCase] = Field(max_length=8)


class CaseAssessment(BaseModel):
    case: int = Field(ge=1, le=8)
    verdict: str = Field(pattern=r"^(as_expected|unexpected|unclear)$")
    observed_summary: str = Field(max_length=240)
    requirement_ref: str | None = Field(None, max_length=20)


class TestAssessment(BaseModel):
    reasoning: str = Field(max_length=800)
    assessments: list[CaseAssessment] = Field(max_length=8)


_plan = TypeAdapter(TestPlan)
_assess = TypeAdapter(TestAssessment)

PLAN_SYSTEM = """You are the Input Tester inside FlowLens, a website reviewer. An explorer found a form on an \
authorised test website and handed it to you with the supplied requirements.

Design a small set of input cases that check what the requirements say about this form: include boundary \
and invalid values the requirements address, plus at least one valid control case. Code will enter each case \
in a fresh browser session, submit it, and record what the page does.

Reply with ONE JSON object and nothing else:
{"reasoning": "<one sentence>", "cases": [
  {"label": "<short name>", "inputs": {"<field name exactly as listed>": "<value>"},
   "submit": "<submit control name exactly as listed>",
   "requirement_ref": "<requirement id this case checks, or null>",
   "expected": "<what should happen, according to that requirement>",
   "check_page": "<optional: a page path from 'Links' where the effect should be visible, or null>"}]}

Rules:
- Use only the field and submit names listed. Unlisted fields keep their current value.
- A form with no fields performs an action (confirm, delete, cancel ...). Use "inputs": {} for it.
- If a requirement says the action changes another page (for example, an item disappears from a list),
  set check_page to that page's path. Code opens it in the same session before and after the action.
- Values are typed exactly. A field with type=date needs YYYY-MM-DD.
- Set requirement_ref only when a supplied requirement states the expected behaviour. If none does, use \
null and describe your own expectation; it will be treated as a review observation, not a defect.
- At most {max_cases} cases. Keep labels and expectations to one short line each.
- Reply with compact JSON on a single line (no indentation)."""

ASSESS_SYSTEM = """You are the Input Tester inside FlowLens. You designed input cases for a form; code \
executed them in fresh browser sessions. For each case you get your inputs and expectation, and the facts \
the browser recorded afterwards (URLs, headings, status and alert messages, invalid fields, visible text).

Judge each case only from those recorded facts:
- "as_expected": the facts match the expectation.
- "unexpected": the facts contradict the expectation.
- "unclear": the facts are insufficient, or the expectation itself is not stated by a requirement.

Reply with ONE JSON object and nothing else:
{"reasoning": "<one sentence>", "assessments": [
  {"case": <case number>, "verdict": "as_expected" | "unexpected" | "unclear",
   "observed_summary": "<what the facts show>", "requirement_ref": "<id or null>"}]}

If a case has a check page, its facts include that page before and after the action; compare them.
Your verdicts are unverified candidates. A separate verifier checks them independently.
Reply with compact JSON on a single line (no indentation)."""


def render_form(form: DiscoveredForm) -> str:
    lines = [f"Page: {form.url}", "Headings: " + (" | ".join(form.headings) or "(none)"), "Fields:"]
    for f in form.fields:
        c = f.control
        extra = [f"type={c.input_type}"] if c.input_type else []
        if f.required:
            extra.append("required")
        if f.observed_value:
            extra.append(f"current value={json.dumps(f.observed_value[:80])}")
        lines.append(f"  - {json.dumps(c.name)} ({c.role}{', ' + ', '.join(extra) if extra else ''})")
    if not form.fields:
        lines.append("  (none: this form performs an action)")
    lines.append("Submit controls: " + ", ".join(json.dumps(s.name) for s in form.submit_controls))
    if form.page_links:
        lines.append("Links on this page: " + ", ".join(form.page_links))
    lines.append("Visible page text (truncated): " + form.page_text[:600])
    return "\n".join(lines)


def plan_messages(handoff: Handoff, form: DiscoveredForm, max_cases: int, note: str | None = None):
    user = (f"Supplied requirements:\n{render_requirements(handoff.requirements)}\n\n"
            f"Form handed over by {handoff.from_agent}:\n{render_form(form)}")
    if note:
        user += f"\n\nNote: {note}"
    return [{"role": "system", "content": PLAN_SYSTEM.replace("{max_cases}", str(max_cases))},
            {"role": "user", "content": user}]


def assess_messages(handoff: Handoff, form: DiscoveredForm, executed: list[dict]):
    blocks = []
    for i, c in enumerate(executed, 1):
        blocks.append(
            f"Case {i}: {c['label']}\n  inputs: {json.dumps(c['inputs'], ensure_ascii=False)}\n"
            f"  requirement: {c['requirement_ref'] or 'none'}\n  expected: {c['expected']}\n"
            f"  execution: {c['status']}{(' - ' + c['error']) if c.get('error') else ''}\n"
            f"  recorded facts: {render_facts(c['facts']) if c.get('facts') else '(none)'}")
    user = (f"Supplied requirements:\n{render_requirements(handoff.requirements)}\n\n"
            f"Form: {form.url} ({' | '.join(form.headings)})\n\n" + "\n\n".join(blocks))
    return [{"role": "system", "content": ASSESS_SYSTEM}, {"role": "user", "content": user}]


def parse_plan(content: str) -> TestPlan:
    return parse_json_reply(content, _plan, "test plan")


def parse_assessment(content: str) -> TestAssessment:
    return parse_json_reply(content, _assess, "assessment")
