"""Shared task queue and the two-explorer review (checkpoint 3).

Queue tests use the real SQLite store. Run tests use the real fixture and
Chromium with a scripted model (test-only; runs are labelled mocked_model).
"""

import json
import threading

import pytest

from flowlens.config import Settings
from flowlens.models.contracts import Provenance, Run, RunLimits, RunStatus, Task, TaskStatus
from flowlens.orchestration.queue_review import QueueReviewRun
from flowlens.services.llm import ScriptedClient
from flowlens.storage.db import Store
from flowlens.storage.queue import StaleAttempt, TaskQueue
from test_review import REQS, _id, make_script


def _q(tmp_path):
    store = Store(tmp_path / "q.db")
    return store, TaskQueue(store, "run_q")


def _t(key, type_="explore", **kw):
    return Task(run_id="run_q", key=key, type=type_, **kw)


def test_concurrent_claims_are_atomic(tmp_path):
    _, q = _q(tmp_path)
    for i in range(30):
        q.enqueue(_t(f"k{i}"))
    got: list[Task] = []
    lock = threading.Lock()

    def worker(name):
        while True:
            t, _ = q.claim(name, {"explore"}, 60)
            if t is None:
                return
            with lock:
                got.append(t)

    ths = [threading.Thread(target=worker, args=(f"w{i}",)) for i in range(8)]
    for th in ths:
        th.start()
    for th in ths:
        th.join()
    assert sorted(t.key for t in got) == sorted(f"k{i}" for i in range(30))  # each claimed exactly once
    assert len({t.attempt_id for t in got}) == 30
    assert all(t.lease_expires_at and t.owner for t in q.snapshot())


def test_dedup_dependencies_stale_and_retries(tmp_path):
    _, q = _q(tmp_path)
    a, created = q.enqueue(_t("a"))
    assert created and not q.enqueue(_t("a"))[1]  # dedup by key
    b, _ = q.enqueue(_t("b", type_="verify", depends_on=[a.id]))
    assert q.claim("v", {"verify"}, 60)[0] is None  # dependency not done
    ca, _ = q.claim("x", {"explore"}, 60)
    stale = ca.model_copy(update={"attempt_id": "att_old"})
    with pytest.raises(StaleAttempt):
        q.complete(stale, [])
    q.complete(ca, ["r1"])
    cb, _ = q.claim("v", {"verify"}, 60)
    assert cb.id == b.id
    # Bounded retries: two claims allowed, then failed; a dependent becomes blocked.
    c, _ = q.enqueue(_t("c", max_attempts=2))
    d, _ = q.enqueue(_t("d", type_="input_test", depends_on=[c.id]))
    c1, _ = q.claim("x", {"explore"}, 60)
    assert q.fail(c1, "boom")[1] is True
    c2, _ = q.claim("x", {"explore"}, 60)
    assert c2.id == c.id and c2.attempts == 2 and c2.attempt_id != c1.attempt_id
    cur, retried = q.fail(c2, "boom again")
    assert not retried and cur.status == TaskStatus.failed
    none, blocked = q.claim("t", {"input_test"}, 60)
    assert none is None and [x.id for x in blocked] == [d.id]


def queue_script():
    base, calls = make_script()

    def script(messages):
        system, user = messages[0]["content"], messages[-1]["content"]
        if "inside FlowLens, a website reviewer. You operate a real browser" in system:
            who = "explorer-b" if "You are Explorer B" in system else "explorer-a"
            calls.append(who)
            page = user.split("Current page:")[1].split("\n\nNote:")[0]
            known = user.split("already recorded:")[1] if "already recorded:" in user else ""
            if "Headings: Dashboard" in page and "(/schedule/new" not in known and "Your previous actions:\n(no actions yet)" in user:
                act = {"type": "click", "element_id": _id(page, "link", "Schedule a post")}
            elif "Headings: Scheduled post" in page and "Your previous actions:\n(no actions yet)" in user:
                act = {"type": "click", "element_id": _id(page, "link", "Back to dashboard")}
            else:
                act = {"type": "finish", "summary": "nothing new"}
            return json.dumps({"reasoning": "scripted", "action": act})
        return base(messages)

    return script, calls


def make_queue_run(server, tmp_path, script, name="q", **limits):
    settings = Settings(_env_file=None, artifacts_dir=tmp_path / f"artifacts-{name}",
                        flowlens_allowed_origins=server.url, openrouter_api_key=None)
    store = Store(tmp_path / f"{name}.db")
    run = Run(target_url=server.url + "/", goal="Explore the dashboard forms", requirements=REQS,
              model="scripted-test-model", mode="queue_review", limits=RunLimits(**limits),
              provenance=Provenance(live=False, mocked_model=True))
    store.put(run)
    return QueueReviewRun(run, store, settings, ScriptedClient(script)), store


async def test_two_explorers_share_queue_and_consume_tester_frontier(fixture_server, tmp_path):
    script, calls = queue_script()
    qr, store = make_queue_run(fixture_server, tmp_path, script)
    await qr.execute()
    d = store.detail(qr.run.id)
    assert d.run.status in (RunStatus.completed, RunStatus.partial), d.run.stop_reason
    tasks = d.tasks
    assert not [t for t in tasks if t.status in (TaskStatus.ready, TaskStatus.claimed)]  # terminated cleanly
    explore = [t for t in tasks if t.type == "explore"]
    assert len({t.key for t in tasks}) == len(tasks)  # deduplicated
    assert {t.owner for t in explore if t.owner} == {"explorer-a", "explorer-b"}  # both explorers claimed work
    # Each claim was a single attempt by one owner; claims are recorded as events.
    claims = [e for e in d.events if e.type == "task_claimed"]
    assert len(claims) == len({e.task_id for e in claims})
    # Newly discovered work from testing was consumed by an explorer.
    from_tester = [t for t in explore if t.queued_by == "input-tester"]
    assert from_tester and any(t.status == TaskStatus.done and t.owner in ("explorer-a", "explorer-b")
                               for t in from_tester)
    # Form discovered by an explorer -> tester task -> verify tasks that waited for it.
    tt = next(t for t in tasks if t.type == "input_test" and t.status == TaskStatus.done)
    form = next(f for f in d.forms if f.id == tt.payload["form_id"])
    assert form.discovered_by in ("explorer-a", "explorer-b") and tt.queued_by == form.discovered_by
    verifies = [t for t in tasks if t.type == "verify"]
    assert verifies and all(v.depends_on == [tt.id] and v.claimed_at >= tt.finished_at for v in verifies)
    r5 = next(f for f in d.findings if f.requirement_ref == "R5")
    assert r5.verification_status == "confirmed"
    # Isolation: each explore task used its own context and workspace.
    ctx_by_task = {}
    for a in d.actions:
        if a.phase == "explore":
            ctx_by_task.setdefault(a.task_id, set()).add(a.context_id)
    assert all(len(v) == 1 for v in ctx_by_task.values())
    assert len({next(iter(v)) for v in ctx_by_task.values()}) == len(ctx_by_task)
    # Shared states keep provenance from several workers.
    assert any(len({s.agent_id for s in st.sightings}) > 1 for st in d.states)
    assert d.run.usage.model_calls == len(d.model_calls) == len(calls)


async def test_explorer_budget_share_leaves_room_for_testing(fixture_server, tmp_path):
    # 6 calls; explorers may use 6 - (2 + 3) = 1, tester 2 + verifier 1 fit in the reserve.
    script, calls = queue_script()
    qr, store = make_queue_run(fixture_server, tmp_path, script, name="b", max_model_calls=6,
                               reserved_testing_calls=3, reserved_verification_calls=2)
    await qr.execute()
    d = store.detail(qr.run.id)
    agents = [m.agent_id for m in d.model_calls]
    assert sum(a.startswith("explorer") for a in agents) == 1
    assert "input-tester" in agents and "verifier" in agents
    assert d.run.status == RunStatus.partial
    unfinished = [t for t in d.tasks if t.status == TaskStatus.unfinished]
    assert unfinished and all(t.note for t in unfinished)
    assert "explorer share of the budget" in d.run.stop_reason
