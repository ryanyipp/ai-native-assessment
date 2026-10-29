"""Typed assertion vocabulary (v1), evaluated by code against a real observation.

A model may only *choose* an assertion type and fill its typed parameters. The
parameters are validated here, and evaluation is plain Python over the recorded
Observation. Nothing model-generated is executed.

Every assertion states what the page shows when the requirement is satisfied.
`passed=False` therefore means the requirement was violated in that replay.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from flowlens.browser.engine import _norm, normalise_route
from flowlens.models.contracts import Assertion, AssertionResult, AssertionType, Observation


class _P(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ElementVisibleParams(_P):
    name: str = Field(min_length=1, max_length=160)  # accessible name or heading text (substring)
    role: str | None = Field(None, max_length=40)  # e.g. button, link, textbox, heading
    expect_visible: bool = True


class ValidationMessageParams(_P):
    text_contains: str | None = Field(None, max_length=160)
    field: str | None = Field(None, max_length=160)  # restrict to one field's validation state


class NavigationReachedParams(_P):
    route: str = Field(min_length=1, max_length=200)  # normalised route, e.g. /items/:id
    expect_reached: bool = True


class TextOrValueRetainedParams(_P):
    expected: str = Field(min_length=1, max_length=500)
    field: str | None = Field(None, max_length=160)  # control name; omitted = visible page text


class StateConditionParams(_P):
    condition: Literal["remained_on_start_route", "left_start_route"]


PARAMS: dict[AssertionType, type[_P]] = {
    AssertionType.element_visible: ElementVisibleParams,
    AssertionType.validation_message_present: ValidationMessageParams,
    AssertionType.navigation_reached: NavigationReachedParams,
    AssertionType.text_or_value_retained: TextOrValueRetainedParams,
    AssertionType.state_condition: StateConditionParams,
}

VOCABULARY_DOC = """\
- element_visible {"name": str, "role": str|null, "expect_visible": bool}: a control or heading whose
  name contains `name` is (or, with expect_visible=false, is not) on the page.
- validation_message_present {"text_contains": str|null, "field": str|null}: the page shows a
  validation/alert message (optionally containing text). With `field`, only that field's own
  validation message or a page alert naming the field counts.
- navigation_reached {"route": str, "expect_reached": bool}: the final page's normalised route equals
  `route` (ids shown as :id), or with expect_reached=false does not.
- text_or_value_retained {"expected": str, "field": str|null}: a field holds `expected`, or the
  visible page text contains it.
- state_condition {"condition": "remained_on_start_route" | "left_start_route"}: whether the page
  route after the actions equals the route before them."""


class AssertionInvalid(ValueError):
    pass


def validate_assertion(a: Assertion) -> _P:
    try:
        return PARAMS[a.type].model_validate(a.params)
    except ValidationError as e:
        err = e.errors()[0]
        raise AssertionInvalid(f"{a.type.value} params invalid: {err['msg']} at {err['loc']}") from e


def evaluate(a: Assertion, after: Observation, start_url: str) -> AssertionResult:
    p = validate_assertion(a)
    observed: dict = {"url": after.url, "route": normalise_route(after.url)}
    if isinstance(p, ElementVisibleParams):
        names = [(e.role, e.name) for e in after.elements] + [("heading", h) for h in after.headings]
        hits = [f"{r} '{n}'" for r, n in names
                if _norm(p.name) in _norm(n) and (p.role is None or _norm(r) == _norm(p.role))]
        observed["matches"] = hits[:10]
        passed = bool(hits) == p.expect_visible
    elif isinstance(p, ValidationMessageParams):
        field_msgs = {e.name: e.validation_message for e in after.elements if e.validation_message}
        if p.field:
            # The field's own validation message, or a page alert that names the field.
            field_msgs = {k: v for k, v in field_msgs.items() if _norm(k) == _norm(p.field)}
            msgs = list(field_msgs.values()) + [m for m in after.alert_messages if _norm(p.field) in _norm(m)]
        else:
            msgs = list(after.alert_messages) + list(field_msgs.values())
        if p.text_contains:
            msgs = [m for m in msgs if _norm(p.text_contains) in _norm(m)]
        observed |= {"alert_messages": after.alert_messages, "field_validation": field_msgs,
                     "status_messages": after.status_messages, "matching_messages": msgs}
        passed = bool(msgs)
    elif isinstance(p, NavigationReachedParams):
        reached = observed["route"] == p.route.split("?")[0].rstrip("/") or observed["route"] == p.route
        passed = reached == p.expect_reached
    elif isinstance(p, TextOrValueRetainedParams):
        if p.field:
            el = next((e for e in after.elements if _norm(e.name) == _norm(p.field) and e.value is not None), None)
            observed["field_value"] = el.value if el else None
            passed = el is not None and el.value == p.expected
        else:
            passed = p.expected in after.text_excerpt
            observed["in_page_text"] = passed
    else:
        assert isinstance(p, StateConditionParams)
        same = normalise_route(start_url) == observed["route"]
        observed["start_route"] = normalise_route(start_url)
        passed = same if p.condition == "remained_on_start_route" else not same
    return AssertionResult(assertion=a, passed=passed, observed=observed)
