"""Regression tests for the correctness pass: action-only forms with multi-step postconditions,
capacity held for admitted tests, and truncation-aware bounded repair.

ticket-desk is now a KNOWN regression fixture (it was held out once; see docs/evaluation-2.md).
Scripted model stand-ins only (mocked_model); they know the fixture's labels.
"""

import json
import re
from pathlib import Path

import pytest

from flowlens.config import Settings
from flowlens.models.contracts import ModelCall, Provenance, Run, RunLimits, RunStatus, Task
from flowlens.orchestration.review import ReviewRun
from flowlens.orchestration.runner import extract_forms
from flowlens.services.llm import BudgetExceeded, LLMResponse, ScriptedClient
from flowlens.storage.db import Store
from test_queue import make_queue_run
from test_review import _id
from test_ticket_desk_fixture import TicketDesk
from flowlens.models.contracts import Observation, ObservedElement

REQ_FILE = Path(__file__).resolve().parents[3] / "fixtures" / "ticket-desk" / "requirements.md"
TREQS = [" ".join(i.strip()[2:].split()) for i in re.split(r"\n(?=- T\d)", REQ_FILE.read_text("utf-8"))
         if i.strip().startswith("- T")]


def test_action_only_form_is_extracted_with_its_own_key():
    obs = Observation(url="http://h/bookings/ab12cd34/cancel", title="t", headings=["Cancel this booking?"],
                      elements=[ObservedElement(id="e1", tag="button", role="button", name="Yes, cancel booking",
                                                form_index=0)])
    ((key, fields, submits),) = extract_forms(obs)
    assert fields == [] and [s.name for s in submits] == ["Yes, cancel booking"]
    other = obs.model_copy(update={"url": "http://h/items/ab12cd34/delete"})
    assert extract_forms(other)[0][0] != key  # action forms on different pages stay distinct


def ticket_script(verdict="facts"):
    calls = []

    def script(messages):
        system, user = messages[0]["content"], messages[-1]["content"]
        if "You are Explorer A" in system:
            calls.append("explorer")
            page = user.split("Current page:")[1]
            hist = user.split("Your previous actions:")[1].split("Current page:")[0]
            if "Headings: Cancel this booking?" in page:
                act = {"type": "finish", "summary": "reached the cancel dialog"}
            elif "Headings: Your booking" in page:
                act = {"type": "click", "element_id": _id(page, "link", "Cancel booking")}
            elif "Headings: Book tickets" in page:
                for name, value in (("Name", "Ann"), ("Email", "ann@example.com"), ("Tickets", "2")):
                    if f'"{name}"' in page and re.search(rf'textbox "{name}"[^\n]*value=""', page):
                        act = {"type": "fill", "element_id": _id(page, "textbox", name), "value": value}
                        break
                else:
                    act = {"type": "click", "element_id": _id(page, "button", "Book tickets")}
            elif "Book tickets for Harbour" not in hist:
                act = {"type": "click", "element_id": _id(page, "link", "Book tickets for Harbour Jazz Night")}
            else:
                act = {"type": "finish", "summary": "done"}
            return json.dumps({"reasoning": "scripted", "action": act})
        if "Design a small set" in system:
            calls.append("plan")
            if "(none: this form performs an action)" not in user:
                return json.dumps({"reasoning": "not this one", "cases": []})
            return json.dumps({"reasoning": "T5", "cases": [
                {"label": "cancel removes booking", "inputs": {}, "submit": "Yes, cancel booking",
                 "requirement_ref": "T5", "expected": "booking no longer listed", "check_page": "/"}]})
        if "Judge each case" in system:
            calls.append("assess")
            after = user.split('"after":')[-1]
            v = verdict if verdict != "facts" else ("unexpected" if "2 ticket(s)" in after else "as_expected")
            return json.dumps({"reasoning": "scripted", "assessments": [
                {"case": 1, "verdict": v, "observed_summary": "list after cancel", "requirement_ref": "T5"}]})
        if "You are the Verifier" in system:
            calls.append("verifier")
            assert "Check page / , opened" not in user and "Check page /, opened in the same fresh session BEFORE" in user
            return json.dumps({"reasoning": "T5", "requirement_ref": "T5", "explicit": True,
                               "requirement_quote": "A cancelled booking no longer appears under My bookings",
                               "assertion": {"type": "text_or_value_retained",
                                             "params": {"expected": "2 ticket(s)", "expect_present": False}},
                               "expected": "the cancelled booking is not listed"})
        raise AssertionError("unexpected prompt")

    return script, calls


def _review(srv, tmp_path, script, name):
    settings = Settings(_env_file=None, artifacts_dir=tmp_path / f"a-{name}", flowlens_allowed_origins=srv.url,
                        openrouter_api_key=None)
    store = Store(tmp_path / f"{name}.db")
    run = Run(target_url=srv.url + "/", goal="Explore", requirements=TREQS, model="scripted-test-model",
              mode="explore_test_verify", limits=RunLimits(), provenance=Provenance(live=False, mocked_model=True))
    store.put(run)
    return ReviewRun(run, store, settings, ScriptedClient(script)), store


@pytest.fixture
def ticket_builds(tmp_path):
    b = TicketDesk(tmp_path / "b.json", "broken").start()
    c = TicketDesk(tmp_path / "c.json", "corrected").start()
    yield b, c
    b.stop()
    c.stop()


async def test_multi_step_postcondition_distinguishes_builds(ticket_builds, tmp_path):
    broken, corrected = ticket_builds
    script, calls = ticket_script()
    rr, store = _review(broken, tmp_path, script, "b")
    await rr.execute()
    d = store.detail(rr.run.id)
    assert d.run.status == RunStatus.completed, d.run.stop_reason
    action_form = next(f for f in d.forms if f.action_only)
    assert [s.name for s in action_form.submit_controls] == ["Yes, cancel booking"] and "/" in action_form.page_links
    (tc,) = [t for t in d.test_cases if t.form_id == action_form.id]
    assert tc.check_path == "/" and tc.status == "executed"
    assert "2 ticket(s)" in tc.observed["check_page"]["before"]["text_excerpt"]
    (f,) = d.findings
    assert f.requirement_ref == "T5" and f.check_path == "/" and f.verification_status == "confirmed"
    checks = [a for a in d.actions if a.action.get("type") == "inspect"]
    assert {a.action["check"] for a in checks} == {"before", "after"} and all(a.screenshot_artifact_id for a in checks)

    # Corrected build: the tester's own facts show the booking gone, so nothing is reported...
    script, _ = ticket_script()
    rr, store = _review(corrected, tmp_path, script, "c")
    await rr.execute()
    d = store.detail(rr.run.id)
    assert not d.findings and next(t for t in d.test_cases if t.check_path).tester_verdict == "as_expected"
    # ...and a candidate forced through verification is not reproduced by the same assertion.
    script, _ = ticket_script(verdict="unexpected")
    rr, store = _review(corrected, tmp_path, script, "c2")
    await rr.execute()
    (f,) = store.detail(rr.run.id).findings
    assert f.verification_status == "not_reproduced"


class TruncatingClient:
    """First reply is cut off at the output limit (as seen in run_c249ce51edbe), the second is valid."""

    is_mock = True
    model = "truncating"

    def __init__(self, good: str, truncate_times: int = 1, reasoning_share: float = 1.0):
        self.good, self.left, self.seen, self.reasoning = good, truncate_times, [], []
        self.share = reasoning_share  # fraction of the cut-off output that was hidden reasoning

    async def complete(self, messages, max_tokens, reasoning_tokens=None):
        self.seen.append(max_tokens)
        self.reasoning.append(reasoning_tokens)
        if self.left > 0:
            self.left -= 1
            return LLMResponse(content='{"reasoning": "cut', model=self.model, provider="none", prompt_tokens=1,
                               completion_tokens=max_tokens, total_tokens=1 + max_tokens, reported_cost_usd=0.0,
                               latency_ms=1, finish_reason="length",
                               reasoning_tokens=int(max_tokens * self.share) - (10 if self.share == 1.0 else 0))
        return LLMResponse(content=self.good, model=self.model, provider="none", prompt_tokens=1, completion_tokens=5,
                           total_tokens=6, reported_cost_usd=0.0, latency_ms=1, finish_reason="stop")


async def test_truncated_reply_is_repaired_once_and_failures_are_kept(fixture_server, tmp_path):
    from flowlens.agents import input_tester
    good = json.dumps({"reasoning": "ok", "cases": []})
    qr, store = make_queue_run(fixture_server, tmp_path, lambda m: "{}", name="trunc")
    task = Task(run_id=qr.run.id, key="t")
    qr.llm = TruncatingClient(good, truncate_times=1)
    plan, _ = await qr.model([{"role": "system", "content": "s"}, {"role": "user", "content": "u"}],
                             agent_id="input-tester", phase="input_test", task=task, parse=input_tester.parse_plan)
    # Reasoning used the output budget: retry with minimal reasoning at the same cap (a bigger cap
    # did not help in run_156b7b84dc3b).
    assert plan.cases == [] and qr.llm.seen == [1400, 1400] and qr.llm.reasoning == [None, 0]
    ev = [e.type for e in store.detail(qr.run.id).events]
    assert "reply_truncated" in ev
    calls = store.list_for_run(ModelCall, qr.run.id)
    assert [c.finish_reason for c in calls] == ["length", "stop"]  # the failed attempt is preserved
    # Two truncations: bounded, the failure is raised and both attempts stay recorded.
    qr.llm = TruncatingClient(good, truncate_times=2)
    with pytest.raises(ValueError, match="truncated"):
        await qr.model([{"role": "system", "content": "s"}, {"role": "user", "content": "u"}],
                       agent_id="input-tester", phase="input_test", task=task, parse=input_tester.parse_plan)
    assert len(store.list_for_run(ModelCall, qr.run.id)) == 4
    # Visible text too long (little reasoning): the repair still doubles the output cap.
    qr.llm = TruncatingClient(good, truncate_times=1, reasoning_share=0.1)
    await qr.model([{"role": "system", "content": "s"}, {"role": "user", "content": "u"}],
                   agent_id="input-tester", phase="input_test", task=task, parse=input_tester.parse_plan)
    assert qr.llm.seen == [1400, 2800] and qr.llm.reasoning == [None, None]


async def test_admitted_test_keeps_its_capacity_against_verification(fixture_server, tmp_path):
    qr, store = make_queue_run(fixture_server, tmp_path, lambda m: "{}", name="hold", max_model_calls=6,
                               reserved_verification_calls=0, reserved_testing_calls=0)
    qr.llm = ScriptedClient(lambda m: "{}")
    t = Task(run_id=qr.run.id, key="test")
    u = qr.run.usage
    for _ in range(3):
        await qr.call_model([{"role": "user", "content": "x"}], agent_id="explorer-a", phase="explore", task=t)
    assert qr.admit("tt", 2, reserve=0)  # 3 used + 2 held <= 6
    assert not qr.admit("tt2", 2, reserve=0)  # would exceed the global limit
    await qr.call_model([{"role": "user", "content": "v"}], agent_id="verifier", phase="verify", task=t)
    with pytest.raises(BudgetExceeded):  # 4 used + 2 held = 6: the verifier cannot take the test's calls
        await qr.call_model([{"role": "user", "content": "v"}], agent_id="verifier", phase="verify", task=t)
    for _ in range(2):
        await qr.call_model([{"role": "user", "content": "t"}], agent_id="input-tester", phase="input_test",
                            task=t, hold_key="tt")
    qr.release("tt")
    assert u.model_calls == 6 and qr.holds == {}  # the global limit was never exceeded


def test_provider_json_schema_is_off_by_default():
    from flowlens.services.llm import OpenRouterClient
    s = Settings(_env_file=None, openrouter_api_key="test-placeholder-not-a-key")
    assert OpenRouterClient(s).supports_schema is False
    assert OpenRouterClient(Settings(_env_file=None, openrouter_api_key="x", flowlens_provider_json_schema=True)).supports_schema


async def test_explicit_requirement_without_assertion_is_a_verifier_failure(fixture_server, tmp_path):
    from test_review import make_review, make_script
    base, _ = make_script()

    def script(messages):
        if "You are the Verifier" in messages[0]["content"]:
            return json.dumps({"reasoning": "explicit", "requirement_ref": "R5", "explicit": True,
                               "requirement_quote": "A publish date in the past must be rejected"})
        return base(messages)

    rr, store, _ = make_review(fixture_server, tmp_path, script)
    await rr.execute()
    d = store.detail(rr.run.id)
    (f,) = d.findings
    assert f.verification_status == "inconclusive" and "supplied no assertion" in f.verification_reason
    assert {v.failure_class for v in d.verifications} == {"verifier"}
