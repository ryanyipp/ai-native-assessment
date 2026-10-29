"""Explorer -> input tester -> verifier chain against the real fixture and real Chromium.

The model is a scripted stand-in here (test-only, it knows the fixture's labels).
These runs are labelled mocked_model and never live. They test handoffs,
fresh-session replay, assertion evaluation and acceptance rules, not model quality.
"""

import json
import re
from pathlib import Path

import pytest

from flowlens.config import Settings
from flowlens.models.contracts import (
    Assertion,
    Finding,
    Provenance,
    Run,
    RunLimits,
    RunStatus,
    VerificationAttempt,
)
from flowlens.orchestration.review import ReverifyRun, ReviewRun
from flowlens.services.llm import ScriptedClient
from flowlens.services.test_data import SetupError, WorkspaceProvider
from flowlens.storage.db import Store

REQS = [line.strip()[2:].replace("\n", " ") for line in re.split(
    r"\n(?=- R\d)", (Path(__file__).resolve().parents[3] / "fixtures" / "creator-studio" / "requirements.md")
    .read_text("utf-8")) if line.strip().startswith("- R")]
REQS = [" ".join(r.split()) for r in REQS]


def _id(msg, role, name):
    m = re.search(rf"(e\d+) {role} \"{re.escape(name)}\"", msg)
    return m.group(1) if m else ""


def make_script(tester_verdict=None, tester_ref="R5", verifier_assertion=None):
    """tester_verdict: None = judge from recorded facts; or a fixed verdict for the past-date case."""
    calls = []

    def script(messages):
        system, user = messages[0]["content"], messages[-1]["content"]
        if "You are Explorer A" in system:
            calls.append("explorer-a")
            page = user.split("Current page:")[1]
            if "Headings: Schedule a post" in page:
                act = {"type": "finish", "summary": "found the scheduling form"}
            else:
                act = {"type": "click", "element_id": _id(page, "link", "Schedule a post")}
            return json.dumps({"reasoning": "scripted", "action": act})
        if "Design a small set" in system:
            calls.append("input-tester:plan")
            if "Publish date" not in user:  # a form without dates: no cases
                return json.dumps({"reasoning": "nothing relevant", "cases": []})
            return json.dumps({"reasoning": "scripted", "cases": [
                {"label": "past date", "inputs": {"Post title": "Past", "Publish date": "2026-06-01"},
                 "submit": "Schedule post", "requirement_ref": tester_ref, "expected": "rejected"},
                {"label": "future date", "inputs": {"Post title": "Future", "Publish date": "2026-07-01"},
                 "submit": "Schedule post", "requirement_ref": "R4", "expected": "scheduled"},
            ]})
        if "Judge each case" in system:
            calls.append("input-tester:assess")
            blocks = user.split("\n\nCase ")[1:]
            out = []
            for i, b in enumerate(blocks, 1):
                if i == 1:
                    v = tester_verdict or ("unexpected" if '"alert_messages": []' in b else "as_expected")
                else:
                    v = "as_expected"
                out.append({"case": i, "verdict": v, "observed_summary": "scripted", "requirement_ref": tester_ref})
            return json.dumps({"reasoning": "scripted", "assessments": out})
        if "You are the Verifier" in system:
            calls.append("verifier")
            a = verifier_assertion or {"type": "validation_message_present", "params": {}}
            return json.dumps({"reasoning": "scripted", "requirement_ref": "R5", "explicit": True,
                               "requirement_quote": "A publish date in the past must be rejected",
                               "assertion": a, "expected": "a validation message"})
        raise AssertionError("unexpected prompt")

    return script, calls


def make_review(server, tmp_path, script, name="r", **limits):
    settings = Settings(_env_file=None, artifacts_dir=tmp_path / f"artifacts-{name}",
                        flowlens_allowed_origins=server.url, openrouter_api_key=None)
    store = Store(tmp_path / f"{name}.db")
    run = Run(target_url=server.url + "/", goal="Find the scheduling form", requirements=REQS,
              model="scripted-test-model", mode="explore_test_verify", limits=RunLimits(**limits),
              provenance=Provenance(live=False, mocked_model=True))
    store.put(run)
    return ReviewRun(run, store, settings, ScriptedClient(script)), store, settings


def _types(d):
    return [e.type for e in d.events]


async def test_broken_build_chain_confirms_past_date_defect(fixture_server, tmp_path):
    script, calls = make_script()
    rr, store, settings = make_review(fixture_server, tmp_path, script)
    await rr.execute()
    d = store.detail(rr.run.id)
    assert d.run.status == RunStatus.completed, d.run.stop_reason
    assert d.run.provenance.mocked_model and not d.run.provenance.live

    # The tester consumed the explorer's actual form record.
    form = next(f for f in d.forms if any(x.control.name == "Publish date" for x in f.fields))
    assert form.discovered_by == "explorer-a"
    assert next(a for a in d.actions if a.id == form.action_result_id).agent_id == "explorer-a"
    ho = next(h for h in d.handoffs if h.kind == "form_to_tester" and h.form_id == form.id)
    assert ho.from_agent == "explorer-a" and ho.to_agent == "input-tester"
    assert {r.id for r in ho.requirements} >= {"R4", "R5"}
    assert ho.setup.expected_signature == next(s for s in d.states if s.id == form.state_id).signature
    plan_call = next(m for m in d.model_calls if m.agent_id == "input-tester")
    plan_prompt = json.loads((settings.artifacts_path / next(
        e for e in d.evidence if e.id == plan_call.artifact_id).path).read_text("utf-8"))["messages"][-1]["content"]
    assert form.url in plan_prompt and '"Publish date" (textbox, type=date, required)' in plan_prompt

    # Each tester case ran in its own fresh workspace context.
    sched = [t for t in d.test_cases if t.form_id == form.id]
    assert len(sched) == 2 and len({t.context_id for t in sched}) == 2
    assert all(t.status == "executed" and t.handoff_id == ho.id for t in sched)

    (f,) = [x for x in d.findings if x.kind == "defect_candidate"]
    assert f.reported_by == "input-tester" and f.requirement_ref == "R5"
    assert f.inputs["Publish date"] == "2026-06-01"
    assert f.verification_status == "confirmed" and f.verified_by == "verifier"
    vs = [v for v in d.verifications if v.finding_id == f.id]
    assert len(vs) == 2 and all(v.outcome == "confirmed" and v.result and not v.result.passed for v in vs)
    assert all(v.assertion.type == "validation_message_present" and v.assertion.requirement_ref == "R5" for v in vs)
    # Verifier evidence is new and separate from the tester's.
    ver_ev = {e for v in vs for e in v.evidence_refs}
    assert ver_ev and not ver_ev & set(f.evidence_refs)
    assert len({v.context_id for v in vs} | {t.context_id for t in sched}) == 4
    _assert_evidence_files(d, settings, vs)

    order = _types(d)
    seq = ["form_discovered", "handoff_created", "test_executed", "candidate_reported", "handoff_created",
           "verification_executed", "result_accepted"]
    pos = -1
    for t in seq:
        pos = order.index(t, pos + 1)
    # Map provenance: tester and verifier transitions are labelled, explorer ones unchanged.
    phases = {t.phase for t in d.transitions}
    assert phases == {"explore", "input_test", "verify"}
    assert all(t.agent_id == {"explore": "explorer-a", "input_test": "input-tester", "verify": "verifier"}[t.phase]
               for t in d.transitions)
    # One shared budget for every worker.
    assert d.run.usage.model_calls == len(d.model_calls) == len(calls)
    assert {m.agent_id for m in d.model_calls} == {"explorer-a", "input-tester", "verifier"}
    assert any(t.type == "explore" and t.status == "deferred" for t in d.tasks)  # new states from testing


def _assert_evidence_files(d, settings, attempts):
    ev = {e.id: e for e in d.evidence}
    for v in attempts:
        assert v.evidence_refs, v.id
        for ref in v.evidence_refs:
            assert (settings.artifacts_path / ev[ref].path).is_file()
        assert any(ev[r].kind == "screenshot" for r in v.evidence_refs) or v.failure_class == "expectation"


async def test_corrected_build_satisfies_assertion_and_reports_nothing(corrected_server, tmp_path):
    script, _ = make_script()
    rr, store, _ = make_review(corrected_server, tmp_path, script)
    await rr.execute()
    d = store.detail(rr.run.id)
    assert d.run.status == RunStatus.completed, d.run.stop_reason
    past = next(t for t in d.test_cases if t.label == "past date")
    assert past.observed["alert_messages"] == ["Publish date cannot be in the past."]
    assert past.tester_verdict == "as_expected"
    assert not d.findings and not d.verifications


async def test_reverify_on_corrected_build_with_same_assertion(fixture_server, corrected_server, tmp_path):
    script, _ = make_script()
    rr, store, settings = make_review(fixture_server, tmp_path, script)
    await rr.execute()
    src = next(f for f in store.detail(rr.run.id).findings if f.verification_status == "confirmed")
    assertion = store.get(VerificationAttempt, src.verification_ids[0]).assertion
    settings2 = Settings(_env_file=None, artifacts_dir=settings.artifacts_dir,
                         flowlens_allowed_origins=f"{fixture_server.url},{corrected_server.url}",
                         openrouter_api_key=None)
    run = Run(target_url=corrected_server.url + "/", goal="re-check", requirements=REQS, model="none",
              mode="reverify", limits=RunLimits(), provenance=Provenance(live=False))
    store.put(run)
    await ReverifyRun(run, store, settings2, ScriptedClient(lambda m: ""), src, assertion).execute()
    d = store.detail(run.id)
    (f,) = d.findings
    assert f.source_finding_id == src.id and f.verification_status == "not_reproduced"
    assert all(v.result.passed and v.assertion == assertion for v in d.verifications)
    assert d.run.usage.model_calls == 0


async def test_non_reproducing_candidate_is_not_reproduced(corrected_server, tmp_path):
    script, _ = make_script(tester_verdict="unexpected")  # tester wrongly claims a defect
    rr, store, _ = make_review(corrected_server, tmp_path, script)
    await rr.execute()
    d = store.detail(rr.run.id)
    (f,) = d.findings
    assert f.kind == "defect_candidate" and f.verification_status == "not_reproduced"
    assert all(v.outcome == "not_reproduced" for v in d.verifications)


async def test_unclear_expectation_is_inconclusive_without_replay(fixture_server, tmp_path):
    script, calls = make_script(tester_ref=None)
    rr, store, _ = make_review(fixture_server, tmp_path, script)
    await rr.execute()
    d = store.detail(rr.run.id)
    (f,) = d.findings
    assert f.kind == "review_observation" and f.verification_status == "inconclusive"
    (v,) = d.verifications
    assert v.failure_class == "expectation" and v.evidence_refs and "verifier" not in calls


async def test_failed_verifier_setup_is_inconclusive(fixture_server, tmp_path):
    script, _ = make_script()
    rr, store, _ = make_review(fixture_server, tmp_path, script)

    class FailForVerifier(WorkspaceProvider):
        def provision(self, origin, label):
            if label.startswith("verifier"):
                raise SetupError("workspace service unavailable (test)")
            return super().provision(origin, label)

    rr.provider = FailForVerifier(rr.provider.endpoint_path, rr.provider.cookie_name)
    await rr.execute()
    d = store.detail(rr.run.id)
    (f,) = d.findings
    assert f.verification_status == "inconclusive"
    assert all(v.failure_class == "setup" and not v.setup_ok for v in d.verifications)


async def test_invalid_assertion_is_inconclusive(fixture_server, tmp_path):
    script, _ = make_script(verifier_assertion={"type": "validation_message_present", "params": {"js": "1"}})
    rr, store, _ = make_review(fixture_server, tmp_path, script)
    await rr.execute()
    (f,) = store.detail(rr.run.id).findings
    assert f.verification_status == "inconclusive" and "Assertion rejected" in f.verification_reason


async def test_verification_reserve_and_shared_budget(fixture_server, tmp_path):
    # 5 calls, 1 reserved: explorer may use 5 - (1 + 2) = 2, tester 2, verifier 1.
    script, calls = make_script()
    rr, store, _ = make_review(fixture_server, tmp_path, script, max_model_calls=5, reserved_verification_calls=1)
    await rr.execute()
    d = store.detail(rr.run.id)
    assert d.run.usage.model_calls == 5 == len(calls)
    assert calls.count("verifier") == 1
    assert next(f for f in d.findings).verification_status == "confirmed"

    # 4 calls: the verifier has no budget left, so the result is inconclusive and the run partial.
    script, calls = make_script()
    rr, store, _ = make_review(fixture_server, tmp_path, script, name="r2", max_model_calls=4,
                               reserved_verification_calls=0)
    await rr.execute()
    d = store.detail(rr.run.id)
    assert d.run.status == RunStatus.partial and d.run.usage.model_calls == 4
    assert next(f for f in d.findings).verification_status == "inconclusive"


async def test_coordinator_rejects_self_verification(fixture_server, tmp_path):
    script, _ = make_script()
    rr, store, _ = make_review(fixture_server, tmp_path, script)
    f = Finding(run_id=rr.run.id, kind="defect_candidate", reported_by="input-tester", description="d",
                expected="e", observed="o", requirement_ref="R5")
    store.put(f)
    forged = VerificationAttempt(run_id=rr.run.id, finding_id=f.id, verifier_id="input-tester", replay_index=0,
                                 target_origin=fixture_server.url, outcome="confirmed", reason="trust me",
                                 evidence_refs=["art_x"])
    rr.accept(f, [forged], rr.new_task("verify", "k", "verifier", [f.id]))
    assert store.get(Finding, f.id).verification_status == "unverified"
    assert "result_rejected" in _types(store.detail(rr.run.id))


def test_findings_cannot_be_self_confirmed():
    base = dict(run_id="r", kind="defect_candidate", description="d", expected="e", observed="o",
                verification_ids=["ver_1"])
    with pytest.raises(ValueError):
        Finding(reported_by="explorer-a", verification_status="confirmed", verified_by="verifier", **base)
    with pytest.raises(ValueError):
        Finding(reported_by="input-tester", verification_status="confirmed", verified_by="input-tester", **base)
    with pytest.raises(ValueError):
        Finding(reported_by="input-tester", verification_status="confirmed", verified_by="verifier",
                **{**base, "verification_ids": []})
    assert Finding(reported_by="input-tester", verification_status="confirmed", verified_by="verifier", **base)


def test_assertion_params_are_typed():
    from flowlens.verification.assertions import AssertionInvalid, validate_assertion
    with pytest.raises(AssertionInvalid):
        validate_assertion(Assertion(type="navigation_reached", params={"route": "/x", "script": "alert(1)"}))
    with pytest.raises(ValueError):
        Assertion(type="run_javascript", params={})


async def test_truncated_tester_reply_blocks_task_and_marks_run_partial(fixture_server, tmp_path):
    base, _ = make_script()

    def script(messages):
        if "Design a small set" in messages[0]["content"]:
            return '{"reasoning": "cut off'
        return base(messages)

    rr, store, _ = make_review(fixture_server, tmp_path, script)
    await rr.execute()
    d = store.detail(rr.run.id)
    assert d.run.status == RunStatus.partial and "blocked" in d.run.stop_reason
    assert any(t.type == "input_test" and t.status == "blocked" for t in d.tasks)
    assert not d.findings


async def test_verifier_can_judge_requirement_not_explicit(fixture_server, tmp_path):
    base, calls = make_script()

    def script(messages):
        if "You are the Verifier" in messages[0]["content"]:
            calls.append("verifier")
            return json.dumps({"reasoning": "R5 does not say this", "requirement_ref": "R5", "explicit": False,
                               "requirement_quote": "", "assertion": None, "expected": ""})
        return base(messages)

    rr, store, _ = make_review(fixture_server, tmp_path, script)
    await rr.execute()
    d = store.detail(rr.run.id)
    (f,) = d.findings
    assert f.verification_status == "inconclusive" and calls.count("verifier") == 1
    assert [v.failure_class for v in d.verifications] == ["expectation"]


async def test_field_scoped_assertion_accepts_alert_naming_field(corrected_server, tmp_path):
    script, _ = make_script(tester_verdict="unexpected",
                            verifier_assertion={"type": "validation_message_present", "params": {"field": "Publish date"}})
    rr, store, _ = make_review(corrected_server, tmp_path, script)
    await rr.execute()
    (f,) = store.detail(rr.run.id).findings
    assert f.verification_status == "not_reproduced"
