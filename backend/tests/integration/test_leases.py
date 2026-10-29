"""Lease expiry, reassignment, stale actions/results and budget reservation (checkpoint 4).

Queue tests use the real SQLite store. The stall run uses the real fixture and
Chromium with a scripted model (mocked_model) and a labelled injected fault.
"""

import asyncio
import threading

import pytest

from flowlens.models.contracts import FaultInjection, ModelCall, Task, TaskStatus
from flowlens.services.llm import BudgetExceeded, LLMResponse
from flowlens.storage.queue import StaleAttempt
from test_queue import _q, _t, make_queue_run, queue_script


def test_expiry_revokes_attempt_and_excludes_owner(tmp_path):
    _, q = _q(tmp_path)
    q.enqueue(_t("a", max_attempts=2))
    a1, _ = q.claim("explorer-a", {"explore"}, lease_s=0)
    ((t, owner, att, retried),) = q.expire_overdue()
    assert (owner, att, retried) == ("explorer-a", a1.attempt_id, True) and t.status == TaskStatus.ready
    assert t.fencing and q.claim("explorer-b", {"explore"}, 60)[0] is None  # held until fenced
    q.release(t.id)
    for late in (lambda: q.renew(a1, 60), lambda: q.complete(a1, ["late"]), lambda: q.fail(a1, "x")):
        with pytest.raises(StaleAttempt):
            late()
    assert q.claim("explorer-a", {"explore"}, 60)[0] is None  # the stalled worker may not reclaim it
    b, _ = q.claim("explorer-b", {"explore"}, 60)
    assert b.id == a1.id and b.attempt_id != a1.attempt_id and b.attempts == 2
    assert q.expire_overdue() == []  # a live lease is untouched
    assert q.complete(b, ["ok"]).status == TaskStatus.done
    assert q.snapshot()[0].expired_attempts == [a1.attempt_id]


def test_retry_exhaustion_on_expiry(tmp_path):
    _, q = _q(tmp_path)
    q.enqueue(_t("a", max_attempts=1))
    q.claim("explorer-a", {"explore"}, lease_s=0)
    ((t, _, _, retried),) = q.expire_overdue()
    assert not retried and t.status == TaskStatus.failed and "final attempt" in t.note
    assert q.claim("explorer-b", {"explore"}, 60)[0] is None


def test_expiry_and_completion_race_has_one_winner(tmp_path):
    _, q = _q(tmp_path)
    for i in range(25):
        q.enqueue(_t(f"r{i}"))
        t, _ = q.claim("w", {"explore"}, lease_s=0)
        out = {}

        def finish():
            try:
                q.complete(t, ["r"])
                out["complete"] = True
            except StaleAttempt:
                out["complete"] = False

        def expire():
            hit = q.expire_overdue()
            out["expired"] = bool(hit)
            for task, *_ in hit:
                q.release(task.id)

        ths = [threading.Thread(target=finish), threading.Thread(target=expire)]
        for th in ths:
            th.start()
        for th in ths:
            th.join()
        assert out["complete"] != out["expired"], out  # exactly one of them took effect
        final = next(x for x in q.snapshot() if x.id == t.id)
        assert final.status == (TaskStatus.done if out["complete"] else TaskStatus.ready)


class SlowClient:
    is_mock = True
    model = "slow-scripted"

    async def complete(self, messages, max_tokens, reasoning_tokens=None):
        await asyncio.sleep(0.05)
        return LLMResponse(content="{}", model=self.model, provider="none", prompt_tokens=1, completion_tokens=1,
                           total_tokens=2, reported_cost_usd=0.0, latency_ms=50)


async def test_concurrent_calls_cannot_overshoot_reserved_capacity(fixture_server, tmp_path):
    qr, store = make_queue_run(fixture_server, tmp_path, lambda m: "{}", max_model_calls=6,
                               reserved_testing_calls=1, reserved_verification_calls=2)
    qr.llm = SlowClient()
    task = Task(run_id=qr.run.id, key="x")
    lim = qr.run.limits

    async def explore_call():
        return await qr.call_model([{"role": "user", "content": "x"}], agent_id="explorer-a", phase="explore",
                                   task=task, reserve=lim.reserved_verification_calls,
                                   phase_cap=lim.max_model_calls - lim.reserved_testing_calls - lim.reserved_verification_calls)

    res = await asyncio.gather(*(explore_call() for _ in range(10)), return_exceptions=True)
    assert sum(not isinstance(r, Exception) for r in res) == 3  # 6 - 1 - 2, never more
    assert all(isinstance(r, BudgetExceeded) for r in res if isinstance(r, Exception))
    u = qr.run.usage
    assert u.model_calls == u.exploration_calls == 3 and qr.in_flight == 0
    # Testing keeps its reserved call and verification its two.
    await qr.call_model([{"role": "user", "content": "t"}], agent_id="input-tester", phase="input_test",
                        task=task, reserve=2)
    with pytest.raises(BudgetExceeded):
        await qr.call_model([{"role": "user", "content": "t"}], agent_id="input-tester", phase="input_test",
                            task=task, reserve=2)
    for _ in range(2):
        await qr.call_model([{"role": "user", "content": "v"}], agent_id="verifier", phase="verify", task=task)
    with pytest.raises(BudgetExceeded):
        await qr.call_model([{"role": "user", "content": "v"}], agent_id="verifier", phase="verify", task=task)
    assert (u.testing_calls, u.verification_calls, u.model_calls) == (1, 2, 6)
    assert len(store.list_for_run(ModelCall, qr.run.id)) == 6


async def test_injected_stall_is_recovered_by_explorer_b(fixture_server, tmp_path):
    script, _ = queue_script()
    qr, store = make_queue_run(fixture_server, tmp_path, script, name="stall", task_lease_s=6)
    qr.run.fault_injection = FaultInjection(worker="explorer-a", task_type="explore", stall_s=13)
    qr.run.provenance.injected_failure = True
    qr.faults_left = 1
    await qr.execute()
    d = store.detail(qr.run.id)
    ev = d.events
    stall = next(e for e in ev if e.type == "fault_injected" and e.data.get("stall_s"))
    stalled = next(t for t in d.tasks if t.id == stall.task_id)
    att_a = stall.data["attempt_id"]
    def in_order(*kinds):
        pos = ev.index(stall)
        trail = [f"{e.type}:{e.agent_id}" for e in ev if e.task_id == stalled.id]
        for kind in kinds:
            pos = next((i for i, e in enumerate(ev) if i > pos and e.type == kind and e.task_id == stalled.id), None)
            assert pos is not None, f"missing {kind} after earlier steps; trail {trail}"

    # Diagnosis and recovery, and separately the expired worker's late action and result.
    # Recovery may finish before or after the stalled worker wakes; both chains must hold.
    in_order("lease_expired", "context_fenced", "task_reassigned", "task_claimed", "task_recovered")
    in_order("lease_expired", "late_action_rejected", "result_rejected")
    assert stalled.status == TaskStatus.done and stalled.owner == "explorer-b"
    assert stalled.expired_attempts == [att_a] and "explorer-a" in stalled.excluded_workers
    assert next(e for e in ev if e.type == "context_fenced" and e.task_id == stalled.id).data["contexts_closed"] >= 1
    assert qr.engines[att_a] and all(eng.closed_by_coordinator for eng in qr.engines[att_a])  # cleaned up
    assert next(e for e in ev if e.type == "result_rejected" and e.task_id == stalled.id).data["attempt_id"] == att_a
    # Nothing was spent or recorded by the expired attempt after its stall began.
    after = ev[ev.index(stall):]
    assert not [e for e in after if e.type in ("model_call", "action_executed") and e.agent_id == "explorer-a"
                and e.task_id == stalled.id]
    assert not any("BUG" in e.message for e in ev)
    assert d.run.provenance.injected_failure
    assert next(f for f in d.findings if f.requirement_ref == "R5").verification_status == "confirmed"


def test_sole_worker_retries_instead_of_stranding(tmp_path):
    _, q = _q(tmp_path)
    q.enqueue(_t("v", type_="verify", max_attempts=2))
    v1, _ = q.claim("verifier", {"verify"}, lease_s=0)
    ((t, _, _, retried),) = q.expire_overdue(can_exclude=lambda task, owner: False)
    assert retried and t.excluded_workers == []
    q.release(t.id)
    v2, _ = q.claim("verifier", {"verify"}, 60)
    assert v2.id == v1.id and v2.attempt_id != v1.attempt_id
    with pytest.raises(StaleAttempt):
        q.complete(v1, ["late"])
