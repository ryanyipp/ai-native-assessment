"""Verifier: selects one typed assertion from an explicit requirement.

It sees the requirement, the inputs and steps to repeat, and the form controls
from its OWN fresh observation. It does not see the tester's verdict or
observed outcome. It only chooses the assertion; code replays the steps in
fresh contexts and evaluates the assertion.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field, TypeAdapter

from flowlens.agents.common import parse_json_reply
from flowlens.agents.explorer import render_observation
from flowlens.models.contracts import AssertionType, Finding, Observation
from flowlens.verification.assertions import VOCABULARY_DOC

AGENT_ID = "verifier"


class ChosenAssertion(BaseModel):
    type: AssertionType
    params: dict[str, Any] = Field(default_factory=dict)


class VerifierDecision(BaseModel):
    reasoning: str = Field(max_length=800)
    requirement_ref: str = Field(max_length=20)
    assertion: ChosenAssertion
    expected: str = Field(max_length=300)


_decision = TypeAdapter(VerifierDecision)

SYSTEM = f"""You are the Verifier inside FlowLens, a website reviewer. A candidate defect was reported \
against an explicit requirement. Code will repeat the reported inputs in fresh browser sessions with fresh \
test data and then evaluate ONE assertion that you choose against the resulting page.

Choose the assertion that the page must satisfy if the requirement is met after the actions. Code decides \
the outcome: if the assertion fails, the requirement violation is confirmed; if it passes, the candidate \
is not reproduced. Do not try to predict the outcome; encode the requirement faithfully.

Assertion vocabulary (type and params):
{VOCABULARY_DOC}

Reply with ONE JSON object and nothing else:
{{"reasoning": "<short>", "requirement_ref": "<the requirement id>",
  "assertion": {{"type": "<one type above>", "params": {{...}}}},
  "expected": "<the expected value in plain words>"}}"""


def build_messages(finding: Finding, fresh_obs: Observation, note: str | None = None):
    steps = "\n".join(f"  {i}. {s.describe()}" for i, s in enumerate(finding.reproduction_steps, 1))
    user = (
        f"Requirement {finding.requirement_ref}: {finding.requirement_text}\n\n"
        f"Inputs to repeat: {json.dumps(finding.inputs, ensure_ascii=False)}\n"
        f"Steps code will repeat after reaching the start page:\n{steps}\n\n"
        f"Start page as you observed it in a fresh session (before the steps):\n{render_observation(fresh_obs)}"
    )
    if note:
        user += f"\n\nNote: {note}"
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def parse_decision(content: str) -> VerifierDecision:
    return parse_json_reply(content, _decision, "verifier decision")
