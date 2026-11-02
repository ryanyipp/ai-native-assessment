"""An expired attempt cannot queue follow-up work, and a removal check needs its text present beforehand."""

import pytest

from flowlens.config import Settings
from flowlens.models.contracts import (
    Assertion,
    Observation,
    Provenance,
    Run,
    RunLimits,
    ScreenState,
    TaskStatus,
)
from flowlens.orchestration.queue_review import AttemptRevoked, QueueReviewRun
from flowlens.services.llm import ScriptedClient
from flowlens.storage.db import Store
from flowlens.verification.assertions import removal_precondition

LISTED = Observation(url="http://h/", title="t", headings=["My bookings"], text_excerpt="My bookings Concert · 2 ticket(s)")


def _absent(expected, **params):
    return Assertion(type="text_or_value_retained", params={"expected": expected, "expect_present": False, **params})


def test_removal_check_needs_its_text_on_the_check_page_before_the_action():
    # Text that is listed before the action: its disappearance can be checked.
    assert removal_precondition(_absent("Concert · 2 ticket(s)"), LISTED) is None
    # A record id the page never showed (for example from another session's record): nothing to remove.
    why = removal_precondition(_absent("843f9467"), LISTED)
    assert why and "'843f9467'" in why and "proves nothing" in why


def test_removal_precondition_leaves_other_assertions_alone():
    empty = Observation(url="http://h/", title="t", text_excerpt="")
    assert removal_precondition(Assertion(type="text_or_value_retained",
                                          params={"expected": "x", "expect_present": True}), empty) is None
    assert removal_precondition(_absent("x", field="Title"), empty) is None  # field checks are not removal checks
    assert removal_precondition(Assertion(type="validation_message_present", params={}), empty) is None


def _queue_run(tmp_path):
    settings = Settings(_env_file=None, artifacts_dir=tmp_path / "a", openrouter_api_key=None,
                        flowlens_allowed_origins="http://localhost:5174")
    store = Store(tmp_path / "q.db")
    run = Run(target_url="http://localhost:5174/", goal="Explore", model="scripted-test-model", mode="queue_review",
              limits=RunLimits(), provenance=Provenance(live=False, mocked_model=True))
    store.put(run)
    return QueueReviewRun(run, store, settings, ScriptedClient(lambda m: "{}")), store


def _state(run_id, sig):
    return ScreenState(run_id=run_id, signature=sig, url=f"http://localhost:5174/{sig}", route=f"/{sig}",
                       title=sig, summary=sig, first_seen_step=1)


def test_expired_attempt_cannot_queue_follow_up_tasks(tmp_path):
    qr, store = _queue_run(tmp_path)
    qr.enqueue("explore", "explore:start", by="coordinator", payload={})
    task, _ = qr.queue.claim("explorer-a", {"explore"}, 60)
    qr.revoked.add(task.attempt_id)  # what the watchdog does when the lease expires
    before = qr.queue.snapshot()
    with pytest.raises(AttemptRevoked):
        qr.defer_frontier([_state(qr.run.id, "later")], "explorer-a", task)
    assert qr.queue.snapshot() == before  # nothing queued, not even a skipped task
    (ev,) = [e for e in store.detail(qr.run.id).events if e.type == "late_action_rejected"]
    assert ev.data["attempt_id"] == task.attempt_id and ev.data["what"] == "follow-up tasks"


def test_current_attempt_still_queues_follow_up_tasks(tmp_path):
    qr, _ = _queue_run(tmp_path)
    qr.enqueue("explore", "explore:start", by="coordinator", payload={})
    task, _ = qr.queue.claim("explorer-a", {"explore"}, 60)
    qr.defer_frontier([_state(qr.run.id, "next")], "explorer-a", task)
    assert [t.status for t in qr.queue.snapshot() if t.key == "explore:next"] == [TaskStatus.ready]
