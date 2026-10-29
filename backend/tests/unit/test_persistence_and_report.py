"""Same-session persistence check statuses, and the report built from saved records."""

from pathlib import Path

from flowlens.agents.explorer import CheckedValue
from flowlens.models.contracts import (
    ActionResult,
    Evidence,
    Finding,
    Observation,
    ObservedElement,
    Run,
    RunDetail,
    RunLimits,
    RunStatus,
    SemanticStep,
    ControlRef,
    VerificationAttempt,
)
from flowlens.services.report import build_report, to_html, to_markdown
from flowlens.verification import persistence


def _obs(elements, text):
    return Observation(url="https://x.test/#/", title="t", headings=[], elements=elements, text_excerpt=text,
                       status_messages=[], alert_messages=[], invalid_fields=[])


TODO = [
    ObservedElement(id="e1", tag="input", role="textbox", name="What needs to be done?", input_type="text", value=""),
    ObservedElement(id="e2", tag="input", role="checkbox", name="Toggle Todo", input_type="checkbox", value="on",
                    checked=True, context="FlowLens milk", name_shared=True),
    ObservedElement(id="e3", tag="input", role="checkbox", name="Toggle Todo", input_type="checkbox", value="on",
                    checked=False, context="FlowLens dog", name_shared=True),
]
TODO_TEXT = "todos FlowLens milk FlowLens dog 1 item left All Active Completed"


def test_checkbox_claims_are_not_evaluated_even_when_the_word_is_on_the_page():
    res = persistence.evaluate([CheckedValue(field="FlowLens milk", expected="completed"),
                                CheckedValue(field="FlowLens dog", expected="Active")], _obs(TODO, TODO_TEXT), True)
    assert not res.passed and res.observed["outcome"] == "not_evaluated"
    assert [r["status"] for r in res.observed["fields"]] == ["not_evaluated", "not_evaluated"]
    # Naming a checkbox's row is not evaluated even with a non-state word.
    res = persistence.evaluate([CheckedValue(field="FlowLens milk", expected="FlowLens milk")], _obs(TODO, TODO_TEXT), True)
    assert res.observed["outcome"] == "not_evaluated"


def test_text_and_field_values_still_evaluate():
    els = [ObservedElement(id="e1", tag="input", role="textbox", name="Title", input_type="text", value="Summer")]
    ok = persistence.evaluate([CheckedValue(field="Title", expected="Summer"),
                               CheckedValue(field="Caption", expected="Beach day")], _obs(els, "Saved Beach day"), True)
    assert ok.passed and [r["basis"] for r in ok.observed["fields"]] == ["field value", "visible page text"]
    bad = persistence.evaluate([CheckedValue(field="Title", expected="Winter")], _obs(els, ""), True)
    assert not bad.passed and bad.observed["outcome"] == "failed"
    no_reload = persistence.evaluate([CheckedValue(field="Title", expected="Summer")], _obs(els, ""), False)
    assert no_reload.observed["outcome"] == "failed"


def test_legacy_record_is_reinterpreted_without_change():
    """The stored TodoMVC record (run_15f19bf8bb46): 'completed' matched only as page text."""
    stored = {"assertion": {"type": "text_or_value_retained", "params": {}}, "passed": False,
              "observed": {"fields": [{"field": "FlowLens milk", "expected": "completed", "actual_value": None, "matched": True},
                                      {"field": "FlowLens dog", "expected": "active", "actual_value": None, "matched": False}],
                           "reload_in_trace": True, "url": "https://demo.playwright.dev/todomvc/#/"}}
    before = repr(stored)
    s = persistence.summarise(stored)
    assert s["outcome"] == "not_evaluated" and s["reinterpreted"]
    assert all(r["status"] == "not_evaluated" for r in s["rows"]) and "Not evaluated" in s["headline"]
    assert repr(stored) == before  # evidence untouched


def _detail(tmp_path: Path, status=RunStatus.completed, mode="explore_test_verify", independence=None):
    lim = RunLimits(max_steps=5, max_model_calls=10, max_cost_usd=0.1, max_output_tokens=200)
    run = Run(target_url="http://localhost:5174/", goal="Check scheduling", model="m", limits=lim, mode=mode,
              requirements=["R5. A past publish date must be rejected."], status=status,
              stop_reason="step limit reached before the explorer finished" if status == RunStatus.partial else "done")
    (tmp_path / "runs").mkdir(parents=True)
    (tmp_path / "runs" / "a.png").write_bytes(b"png")
    ev = [Evidence(id="art_shot", run_id=run.id, kind="screenshot", path="runs/a.png", sha256="x", media_type="image/png"),
          Evidence(id="art_gone", run_id=run.id, kind="screenshot", path="runs/missing.png", sha256="x", media_type="image/png")]
    act = ActionResult(run_id=run.id, step=1, action={"type": "click", "element_id": "e3"}, target_description="button 'Schedule post'",
                       ok=True, url_before="u", url_after="u", started_at=run.created_at, duration_ms=5,
                       screenshot_artifact_id="art_shot", agent_id="input-tester", phase="input_test")
    who = "single-agent" if independence == "self" else "verifier"
    ver = VerificationAttempt(run_id=run.id, finding_id="fnd_1", verifier_id=who, replay_index=0, target_origin="o",
                              setup_ok=True, outcome="confirmed", reason="violated R5", evidence_refs=["art_gone"])
    f = Finding(id="fnd_1", run_id=run.id, kind="defect_candidate", reported_by="single-agent" if independence == "self" else "input-tester",
                description="Schedule a post: past date accepted", expected="A validation message", observed="Post was scheduled",
                requirement_ref="R5", evidence_refs=["art_shot"], verification_status="confirmed", verified_by=who,
                verification_ids=[ver.id], verification_independence=independence,
                reproduction_steps=[SemanticStep(type="fill", control=ControlRef(role="textbox", name="Publish date"), value="2026-06-14"),
                                    SemanticStep(type="click", control=ControlRef(role="button", name="Schedule post"))])
    return RunDetail(run=run, states=[], transitions=[], actions=[act], findings=[f], events=[], evidence=ev,
                     model_calls=[], verifications=[ver])


def test_report_leads_with_summary_and_separates_self_checks(tmp_path):
    rep = build_report(_detail(tmp_path), tmp_path, "http://localhost:8000")
    md = to_markdown(rep)
    assert md.index("## Summary") < md.index("## Problems to fix") < md.index("## What was not checked") < md.index("## Diagnostics")
    assert "**Status: Confirmed.** Re-checked by an independent verifier" in md
    assert "Type “2026-06-14” into “Publish date”" in md and "Click “Schedule post”" in md
    assert "(http://localhost:8000/api/artifacts/art_shot)" in md and "(file missing)" in md
    main = md.split("## Diagnostics")[0]
    for tech in ("fnd_1", "run_", "{", "defect_candidate"):  # ids and raw records only inside folded details
        assert tech not in main.replace(main[main.find("<details>"):main.find("</details>")], "")
    self_rep = build_report(_detail(tmp_path / "s", mode="single_agent", independence="self"), tmp_path / "s", "http://h")
    assert "Confirmed by self-check only" in to_markdown(self_rep) and "confirmed only by self-check" in self_rep["summary"][0]
    html = to_html(rep, "/api/runs/x/report.md")
    assert "@media print" in html and "<details><summary>Technical diagnostics</summary>" in html and 'href="/api/artifacts/art_shot"' in html


def test_partial_report_lists_incomplete_work_in_plain_words(tmp_path):
    rep = build_report(_detail(tmp_path, status=RunStatus.partial), tmp_path, "http://h")
    assert rep["incomplete"] and "it reached its limit on browser steps" in rep["gaps"][0]
    assert "Having no findings for an area does not mean that area works" in rep["gaps"][0]
