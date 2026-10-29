"""Single-agent baseline and the lease heartbeat during model calls (scripted model, mocked_model)."""

import asyncio
import json

from flowlens.config import Settings
from flowlens.models.contracts import Provenance, Run, RunLimits, RunStatus, Task, TaskStatus
from flowlens.orchestration.queue_review import CURRENT_TASK
from flowlens.orchestration.single_agent import SingleAgentRun
from flowlens.services.llm import LLMResponse, ScriptedClient
from flowlens.storage.db import Store
from test_queue import make_queue_run, queue_script
from test_review import REQS, make_script


async def test_single_agent_does_everything_in_one_context(fixture_server, tmp_path):
    script, calls = make_script()  # the sequential test script; it keys on the explorer role text
    seen = []

    def spy(messages):
        seen.append(messages)
        sys_ = messages[0]["content"].replace("You are the single agent, now exploring", "You are Explorer A")
        return script([{"role": "system", "content": sys_}, *messages[1:]])

    settings = Settings(_env_file=None, artifacts_dir=tmp_path / "a", flowlens_allowed_origins=fixture_server.url,
                        openrouter_api_key=None)
    store = Store(tmp_path / "s.db")
    run = Run(target_url=fixture_server.url + "/", goal="Explore the dashboard forms", requirements=REQS,
              model="scripted-test-model", mode="single_agent", limits=RunLimits(),
              provenance=Provenance(live=False, mocked_model=True))
    store.put(run)
    await SingleAgentRun(run, store, settings, ScriptedClient(spy)).execute()
    d = store.detail(run.id)
    assert d.run.status == RunStatus.completed, d.run.stop_reason
    assert {m.agent_id for m in d.model_calls} == {"single-agent"}
    assert {m.phase for m in d.model_calls} == {"explore", "input_test", "verify"}
    assert {a.agent_id for a in d.actions} == {"single-agent"}
    # One continuing context: the verification prompt carries the agent's own earlier test verdicts.
    verify_prompt = next(m for m in seen if "You are the Verifier" in m[0]["content"])[-1]["content"]
    assert "[input_test]" in verify_prompt and "unexpected" in verify_prompt
    r5 = next(f for f in d.findings if f.requirement_ref == "R5")
    assert r5.verification_status == "confirmed" and r5.verification_independence == "self"
    assert r5.reported_by == r5.verified_by == "single-agent"
    # Replays still ran in fresh contexts with their own workspaces; exploration had its own workspace too.
    vctx = {v.context_id for v in d.verifications if v.finding_id == r5.id}
    assert len(vctx) == 2 and all(c.startswith("single-agent:ver_") for c in vctx)
    assert all(a.context_id.startswith("single-agent:explore:ws_") for a in d.actions if a.phase == "explore")


class SlowCall:
    is_mock = True
    model = "slow"

    async def complete(self, messages, max_tokens, reasoning_tokens=None):
        await asyncio.sleep(5)
        return LLMResponse(content="{}", model="slow", provider="none", prompt_tokens=1, completion_tokens=1,
                           total_tokens=2, reported_cost_usd=0.0, latency_ms=5000)


async def test_healthy_model_call_longer_than_lease_does_not_expire(fixture_server, tmp_path):
    qr, store = make_queue_run(fixture_server, tmp_path, lambda m: "{}", task_lease_s=2)
    qr.llm = SlowCall()
    qr.queue.enqueue(Task(run_id=qr.run.id, key="k"))
    task, _ = qr.queue.claim("explorer-a", {"explore"}, 2)
    qr.workers_running = True
    dog = asyncio.create_task(qr.watchdog())
    token = CURRENT_TASK.set(task)
    try:
        await qr.call_model([{"role": "user", "content": "x"}], agent_id="explorer-a", phase="explore", task=task)
    finally:
        CURRENT_TASK.reset(token)
    # 5 s call, 2 s lease: the heartbeat kept it alive. Now the worker goes silent and must expire.
    cur = next(t for t in qr.queue.snapshot() if t.id == task.id)
    assert cur.status == TaskStatus.claimed and cur.attempt_id == task.attempt_id and not cur.expired_attempts
    await asyncio.sleep(3)
    qr.workers_running = False
    await dog
    cur = next(t for t in qr.queue.snapshot() if t.id == task.id)
    assert cur.expired_attempts == [task.attempt_id]
    assert "lease_expired" in [e.type for e in store.detail(qr.run.id).events]
