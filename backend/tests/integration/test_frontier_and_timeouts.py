"""Frontier filtering (variations, already-tested outcomes) and bounded model calls.

Scripted model (mocked_model) against the real fixture and Chromium.
"""

import asyncio
import time

from flowlens.browser.engine import page_structure
from flowlens.models.contracts import Observation, ObservedElement, Task, TaskStatus
from flowlens.orchestration.queue_review import CURRENT_TASK
import json

from test_queue import make_queue_run, queue_script
from test_review import _id


def filling_script():
    """Explorers also type into the scheduling form once: a filled-field variation of an explored state."""
    base, calls = queue_script()

    def script(messages):
        system, user = messages[0]["content"], messages[-1]["content"]
        if "You operate a real browser" in system:
            page = user.split("Current page:")[1].split("\n\nNote:")[0]
            if "Headings: Schedule a post" in page and 'Post title" value=""' in page and "fill" not in user.split("Current page:")[0]:
                return json.dumps({"reasoning": "scripted", "action": {
                    "type": "fill", "element_id": _id(page, "textbox", "Post title"), "value": "Draft title"}})
        return base(messages)

    return script, calls


def _obs(value="", headings=("Schedule a post",), alerts=(), status=()):
    return Observation(url="http://h/schedule/new", title="t", headings=list(headings),
                       elements=[ObservedElement(id="e1", tag="input", role="textbox", name="Post title", value=value)],
                       alert_messages=list(alerts), status_messages=list(status) + list(alerts))


def test_structure_ignores_fill_but_keeps_errors_dialogs_and_banners():
    assert page_structure(_obs(""))[0] == page_structure(_obs("x"))[0]  # fill variation
    assert page_structure(_obs("", alerts=["Date cannot be in the past."]))[0] != page_structure(_obs(""))[0]
    assert page_structure(_obs("", status=["Draft saved."]))[0] != page_structure(_obs(""))[0]
    assert page_structure(_obs("", headings=("Cancel this booking?",)))[0] != page_structure(_obs(""))[0]
    # The error outcome keeps the form's layout (used to spot already-tested outcomes).
    assert page_structure(_obs("", alerts=["bad"]))[1] == page_structure(_obs(""))[1]


async def test_queue_skips_variations_and_tested_outcomes_but_explores_new_pages(fixture_server, tmp_path):
    script, _ = filling_script()
    qr, store = make_queue_run(fixture_server, tmp_path, script, name="frontier")
    await qr.execute()
    d = store.detail(qr.run.id)
    skipped = [t for t in d.tasks if t.status == TaskStatus.skipped]
    assert skipped and all(t.note and t.note.startswith("not explored:") for t in skipped)
    states = {s.id: s for s in d.states}
    explored = [states[t.payload["state_id"]] for t in d.tasks
                if t.type == "explore" and t.status == TaskStatus.done and t.payload.get("state_id")]
    # No two explored states share a structure, and skipped states are still on the map with sightings.
    assert len({s.structure for s in explored}) == len(explored)
    assert all(states[t.payload["state_id"]].sightings for t in skipped)
    # The scheduled-post page reached only by testing is new structure and was still explored.
    assert any(t.queued_by == "input-tester" and t.status == TaskStatus.done for t in d.tasks if t.type == "explore")
    assert next(f for f in d.findings if f.requirement_ref == "R5").verification_status == "confirmed"


class HangClient:
    is_mock = True
    model = "hang"

    async def complete(self, messages, max_tokens, reasoning_tokens=None):
        await asyncio.sleep(3600)  # ignores its own timeout


async def test_hung_model_call_is_cut_off_and_its_lease_can_expire(fixture_server, tmp_path):
    qr, store = make_queue_run(fixture_server, tmp_path, lambda m: "{}", name="hang", task_lease_s=2)
    qr.settings.flowlens_model_timeout_s = 1.0  # deadline = 1 s + 2 s grace
    qr.llm = HangClient()
    qr.queue.enqueue(Task(run_id=qr.run.id, key="k"))
    task, _ = qr.queue.claim("explorer-a", {"explore"}, 2)
    qr.workers_running = True
    dog = asyncio.create_task(qr.watchdog())
    token = CURRENT_TASK.set(task)
    t0 = time.monotonic()
    try:
        try:
            await qr.call_model([{"role": "user", "content": "x"}], agent_id="explorer-a", phase="explore", task=task)
            raised = False
        except ValueError:
            raised = True
        assert raised and time.monotonic() - t0 < 6  # cut off at the bounded deadline, recorded as a failed call
        # Heartbeat alone cannot keep a hung call's lease alive past the deadline.
        hb = qr.start_heartbeat(task)
        await asyncio.sleep(6)
        hb.cancel()
    finally:
        CURRENT_TASK.reset(token)
        qr.workers_running = False
        await dog
    ev = [e.type for e in store.detail(qr.run.id).events]
    assert "heartbeat_stopped" in ev and "lease_expired" in ev
    (mc,) = store.detail(qr.run.id).model_calls
    assert not mc.ok and qr.in_flight == 0
