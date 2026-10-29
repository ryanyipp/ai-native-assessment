"""Helpers shared by the runtime agents' prompt and reply handling."""

from __future__ import annotations

import json
import re
from typing import TypeVar

from pydantic import TypeAdapter, ValidationError

from flowlens.models.contracts import Observation, RequirementRef

T = TypeVar("T")


def parse_json_reply(content: str, adapter: TypeAdapter[T], what: str = "reply") -> T:
    """Extract one JSON object from a model reply and validate it against a bounded schema."""
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    elif not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            text = text[start : end + 1]
    try:
        return adapter.validate_json(text)
    except ValidationError as e:
        err = e.errors()[0]
        raise ValueError(f"invalid {what}: {err['msg']} at {err['loc']}") from e


_REQ_ID = re.compile(r"^\s*([A-Z]{1,4}-?\d{1,3})[.):]\s+(.*)$", re.S)


def requirement_refs(requirements: list[str]) -> list[RequirementRef]:
    """Give each supplied requirement a stable id: its own prefix ("R5.") or REQ-n."""
    out = []
    for i, text in enumerate(requirements, 1):
        m = _REQ_ID.match(text)
        out.append(RequirementRef(id=m.group(1), text=m.group(2).strip()) if m
                   else RequirementRef(id=f"REQ-{i}", text=text.strip()))
    return out


def render_requirements(reqs: list[RequirementRef]) -> str:
    return "\n".join(f"- {r.id}: {r.text}" for r in reqs) or "(none supplied)"


def outcome_facts(obs: Observation, url_before: str) -> dict:
    """Code-extracted facts about a page after an action. No interpretation."""
    return {
        "url_before": url_before,
        "url_after": obs.url,
        "title": obs.title,
        "headings": obs.headings,
        "status_messages": obs.status_messages,
        "alert_messages": obs.alert_messages,
        "invalid_fields": obs.invalid_fields,
        "text_excerpt": obs.text_excerpt[:500],
    }


def render_facts(facts: dict) -> str:
    return json.dumps(facts, ensure_ascii=False)
