"""The explorer's same-session persistence check, and how its stored result is read.

Each value the explorer claims to have checked gets one row with a status:
  matched / mismatch: compared against a field's value, or (for entered text with no field
                      left on the page) against the visible page text;
  not_evaluated:      the claim is about a checkbox or another on/off state. This check does
                      not compare such states, so visible text such as a "Completed" filter
                      link can never count as success.

Stored results are never rewritten. `summarise` reads both current rows and rows recorded
before statuses existed, applying the same rules, so old evidence is shown correctly.
"""

from __future__ import annotations

from typing import Any

from flowlens.models.contracts import Assertion, AssertionResult, AssertionType

# Claimed "values" that describe a state rather than entered text.
STATE_WORDS = {
    "completed", "complete", "incomplete", "done", "not done", "checked", "unchecked", "ticked", "unticked",
    "active", "inactive", "selected", "unselected", "on", "off", "true", "false", "yes", "no",
    "enabled", "disabled", "open", "closed", "pending", "toggled",
}
NOT_EVALUATED_REASON = "checkbox or on/off state: not compared by this check"


def _norm(t: str | None) -> str:
    return " ".join((t or "").split()).casefold()


def evaluate(checked_values: list, obs, reload_seen: bool) -> AssertionResult:
    rows: list[dict[str, Any]] = []
    for cv in checked_values:
        field, expected = cv.field, cv.expected
        same_name = [e for e in obs.elements if _norm(e.name) == _norm(field)]
        checkbox_row = any(e.checked is not None and _norm(field) and _norm(field) in _norm(e.context)
                           for e in obs.elements)
        value_el = next((e for e in same_name if e.value is not None and e.checked is None), None)
        if any(e.checked is not None for e in same_name) or checkbox_row or _norm(expected) in STATE_WORDS:
            rows.append({"field": field, "expected": expected, "actual_value": None, "matched": False,
                         "status": "not_evaluated", "basis": NOT_EVALUATED_REASON})
        elif value_el is not None:
            ok = value_el.value == expected
            rows.append({"field": field, "expected": expected, "actual_value": value_el.value, "matched": ok,
                         "status": "matched" if ok else "mismatch", "basis": "field value"})
        else:
            ok = expected in obs.text_excerpt
            rows.append({"field": field, "expected": expected, "actual_value": None, "matched": ok,
                         "status": "matched" if ok else "mismatch", "basis": "visible page text"})
    outcome = _outcome(rows, reload_seen)
    return AssertionResult(
        assertion=Assertion(type=AssertionType.text_or_value_retained,
                            params={"values": [cv.model_dump() for cv in checked_values],
                                    "requires_reload_in_trace": True}),
        passed=outcome == "passed",
        observed={"fields": rows, "reload_in_trace": reload_seen, "url": obs.url, "outcome": outcome},
    )


def _outcome(rows: list[dict], reload_seen: bool) -> str:
    if any(r["status"] == "mismatch" for r in rows):
        return "failed"
    if not rows or any(r["status"] == "not_evaluated" for r in rows):
        return "not_evaluated"
    return "passed" if reload_seen else "failed"


def _legacy_row(r: dict) -> dict:
    """A row stored before statuses existed: re-read by the same rules (the record is unchanged)."""
    if r.get("status"):
        return r
    if _norm(r.get("expected")) in STATE_WORDS:
        return {**r, "status": "not_evaluated", "basis": NOT_EVALUATED_REASON}
    if r.get("actual_value") is not None:
        return {**r, "status": "matched" if r.get("matched") else "mismatch", "basis": "field value"}
    return {**r, "status": "matched" if r.get("matched") else "mismatch", "basis": "visible page text"}


def summarise(result: AssertionResult | dict | None) -> dict | None:
    """{outcome, rows, reload_in_trace, headline, reinterpreted} for display; None if no check ran."""
    if result is None:
        return None
    data = result.model_dump() if isinstance(result, AssertionResult) else result
    observed = data.get("observed") or {}
    raw = observed.get("fields") or []
    rows = [_legacy_row(r) for r in raw]
    reload_seen = bool(observed.get("reload_in_trace"))
    outcome = observed.get("outcome") or _outcome(rows, reload_seen)
    n_ne = sum(r["status"] == "not_evaluated" for r in rows)
    headline = {
        "passed": "Values matched after a reload (same session; not independent)",
        "failed": ("A value did not match after the reload" if any(r["status"] == "mismatch" for r in rows)
                   else "No reload after saving was recorded, so retention was not shown"),
        "not_evaluated": (f"Not evaluated: {n_ne} of {len(rows)} claimed values are checkbox or on/off states, "
                          "which this check does not compare" if rows else "Not evaluated: the explorer named no values to check"),
    }[outcome]
    return {"outcome": outcome, "rows": rows, "reload_in_trace": reload_seen, "headline": headline,
            "reinterpreted": "outcome" not in observed}
