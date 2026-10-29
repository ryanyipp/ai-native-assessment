"""Explorer agent: chooses one bounded browser action per step from observed controls.

It receives only the goal, supplied requirements, a compact observation of the
current page and a short history of its own actions. It has no filesystem,
repository or evaluation access, and it cannot confirm findings.
"""

from __future__ import annotations

import json
from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter

from flowlens.agents.common import parse_json_reply
from flowlens.models.contracts import (
    ClickAction,
    FillAction,
    NavigateAction,
    Observation,
    ReloadAction,
)

AGENT_ID = "explorer-a"


class CheckedValue(BaseModel):
    field: str = Field(max_length=120)  # control name as observed
    expected: str = Field(max_length=500)


class FinishAction(BaseModel):
    type: Literal["finish"] = "finish"
    persistence: Literal["retained", "not_retained", "unknown"] = "unknown"
    checked_values: list[CheckedValue] = Field(default_factory=list, max_length=10)
    summary: str = Field(max_length=600)


AgentAction = Annotated[
    ClickAction | FillAction | NavigateAction | ReloadAction | FinishAction,
    Field(discriminator="type"),
]


class ExplorerDecision(BaseModel):
    reasoning: str = Field(max_length=600)
    action: AgentAction


_decision = TypeAdapter(ExplorerDecision)

SYSTEM_PROMPT = """You are {name} inside FlowLens, a website reviewer. You operate a real browser on an \
authorised test website, one action at a time, to pursue a goal.

Each turn you get the goal, your previous actions with their outcomes, and an observation of the current \
page. Interactive elements are listed with short ids like e3. Ids are valid only for the current observation.

Reply with ONE JSON object and nothing else:
{"reasoning": "<one or two short sentences>", "action": <action>}

Allowed actions:
  {"type": "click", "element_id": "e3"}
  {"type": "fill", "element_id": "e4", "value": "text to enter"}
  {"type": "navigate", "url": "<absolute URL on the same site>"}
  {"type": "reload"}
  {"type": "finish", "persistence": "retained" | "not_retained" | "unknown",
   "checked_values": [{"field": "<control name>", "expected": "<value you entered>"}],
   "summary": "<what you observed>"}
  (persistence and checked_values are only for goals about saved data; otherwise use "unknown" and [].)

Rules:
- Choose controls from the observation only. Do not guess ids or URLs you have not seen.
- Prefer clicking visible links and buttons over typing URLs.
- Use distinctive test values so you can recognise them later.
- If an action fails, read the error and try a different approach.
- Forms you open are recorded and handed to an input tester; you do not need to test every input.
- Report only what you observed. Your finish result is an unverified observation; another component \
checks it independently.
- Finish with "unknown" if you cannot complete the goal."""


def render_observation(obs: Observation) -> str:
    lines = [f"URL: {obs.url}", f"Title: {obs.title}"]
    if obs.headings:
        lines.append("Headings: " + " | ".join(obs.headings))
    if obs.status_messages:
        lines.append("Status messages: " + " | ".join(obs.status_messages))
    if obs.alert_messages:
        lines.append("Alerts: " + " | ".join(obs.alert_messages))
    lines.append("Interactive elements:")
    for e in obs.elements:
        parts = [e.id, e.role, json.dumps(e.name)]
        if e.input_type and e.input_type not in ("text",):
            parts.append(f"type={e.input_type}")
        if e.value is not None:
            parts.append(f"value={json.dumps(e.value[:200])}")
        if e.href:
            parts.append(f"href={e.href}")
        if e.required:
            parts.append("required")
        if e.validation_message:
            parts.append(f"invalid={json.dumps(e.validation_message[:120])}")
        if e.disabled:
            parts.append("disabled")
        lines.append("  " + " ".join(parts))
    lines.append("Visible text (truncated): " + obs.text_excerpt[:800])
    return "\n".join(lines)


def build_messages(goal: str, requirements: list[str], history: list[str], obs: Observation,
                   step: int, max_steps: int, note: str | None = None,
                   name: str = "Explorer A") -> list[dict[str, str]]:
    req = "\n".join(f"- {r}" for r in requirements) or "(none supplied)"
    hist = "\n".join(history[-12:]) or "(no actions yet)"
    user = (
        f"Goal: {goal}\n\nSupplied requirements:\n{req}\n\n"
        f"Step {step} of at most {max_steps}.\n\nYour previous actions:\n{hist}\n\n"
        f"Current page:\n{render_observation(obs)}"
    )
    if note:
        user += f"\n\nNote: {note}"
    return [{"role": "system", "content": SYSTEM_PROMPT.replace("{name}", name)}, {"role": "user", "content": user}]


def parse_decision(content: str) -> ExplorerDecision:
    return parse_json_reply(content, _decision, "decision")
