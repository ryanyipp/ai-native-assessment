"""Persistent, code-managed task queue on the SQLite store.

Every mutation runs in one `BEGIN IMMEDIATE` transaction, so a claim, an
enqueue or a completion is atomic even across threads or processes:

- enqueue: deduplicated by (run_id, task key) through a unique index.
- claim: picks the highest-priority ready task of the requested types whose
  dependencies are all done, and assigns owner, a new attempt id and a lease.
  Ready tasks whose dependency ended badly become `blocked`.
- complete / fail: accepted only from the current owner and attempt. A failure
  is retried (back to ready) until `max_attempts` claims have been used.

- renew: the current attempt extends its lease (called on every action).
- expire_overdue: claimed tasks past their lease lose their attempt. The task
  goes back to ready (the expired owner may not reclaim it) or, with no attempts
  left, to failed. Any later renew/complete/fail by that attempt is stale.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import timedelta
from typing import Iterator

from flowlens.models.contracts import Task, TaskStatus, new_id, utcnow
from flowlens.storage.db import Store

TERMINAL = {TaskStatus.done, TaskStatus.failed, TaskStatus.blocked, TaskStatus.unfinished, TaskStatus.deferred}
BAD_END = {TaskStatus.failed, TaskStatus.blocked, TaskStatus.unfinished}


class StaleAttempt(Exception):
    """A result from a worker that is no longer the task's current owner/attempt."""


class TaskQueue:
    def __init__(self, store: Store, run_id: str):
        self.store, self.run_id = store, run_id
        try:  # defence in depth; enqueue also checks inside its transaction
            with self._tx() as c:
                c.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_tasks_run_key ON tasks(run_id, json_extract(data, '$.key'))")
        except sqlite3.IntegrityError:
            pass  # an older database already holds duplicate keys in some run

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.store.path, timeout=10, isolation_level=None)
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def _all(self, c: sqlite3.Connection) -> list[Task]:
        rows = c.execute("SELECT data FROM tasks WHERE run_id=? ORDER BY pk", (self.run_id,)).fetchall()
        return [Task.model_validate_json(r[0]) for r in rows]

    @staticmethod
    def _save(c: sqlite3.Connection, t: Task) -> None:
        c.execute("UPDATE tasks SET data=? WHERE id=?", (t.model_dump_json(), t.id))

    def enqueue(self, task: Task) -> tuple[Task, bool]:
        """Insert unless a task with the same key exists. Returns (task, created)."""
        with self._tx() as c:
            row = c.execute("SELECT data FROM tasks WHERE run_id=? AND json_extract(data, '$.key')=?",
                            (self.run_id, task.key)).fetchone()
            if row:
                return Task.model_validate_json(row[0]), False
            c.execute("INSERT INTO tasks(id, run_id, data) VALUES (?, ?, ?)",
                      (task.id, self.run_id, task.model_dump_json()))
            return task, True

    def claim(self, worker: str, types: set[str], lease_s: int) -> tuple[Task | None, list[Task]]:
        """Atomically claim one task. Returns (claimed task, tasks newly blocked by failed dependencies)."""
        with self._tx() as c:
            tasks = self._all(c)
            by_id = {t.id: t for t in tasks}
            blocked = []
            for t in tasks:
                if t.status != TaskStatus.ready:
                    continue
                bad = [d for d in t.depends_on if d in by_id and by_id[d].status in BAD_END]
                if bad:
                    t.status, t.note, t.finished_at = TaskStatus.blocked, f"dependency {bad[0]} ended {by_id[bad[0]].status.value}", utcnow()
                    self._save(c, t)
                    blocked.append(t)
            ready = [t for t in tasks if t.status == TaskStatus.ready and t.type in types
                     and worker not in t.excluded_workers and not t.fencing
                     and all(by_id.get(d) is not None and by_id[d].status == TaskStatus.done for d in t.depends_on)]
            if not ready:
                return None, blocked
            t = max(ready, key=lambda x: (x.priority, -tasks.index(x)))
            now = utcnow()
            t.status, t.owner, t.attempt_id = TaskStatus.claimed, worker, new_id("att")
            t.attempts += 1
            t.claimed_at, t.lease_expires_at = now, now + timedelta(seconds=lease_s)
            self._save(c, t)
            return t, blocked

    def _current(self, c: sqlite3.Connection, task: Task) -> Task:
        row = c.execute("SELECT data FROM tasks WHERE id=?", (task.id,)).fetchone()
        cur = Task.model_validate_json(row[0])
        # Workers may already have set done/blocked on their own task object; the attempt must still be current.
        if cur.owner != task.owner or cur.attempt_id != task.attempt_id or cur.status not in (
                TaskStatus.claimed, TaskStatus.done, TaskStatus.blocked):
            raise StaleAttempt(f"{task.id}: attempt {task.attempt_id} by {task.owner} is not current "
                               f"(current {cur.attempt_id} by {cur.owner}, {cur.status.value})")
        return cur

    def complete(self, task: Task, result_refs: list[str], note: str | None = None,
                 status: TaskStatus | None = None) -> Task:
        """Default status: done, unless the worker already marked its task blocked."""
        with self._tx() as c:
            cur = self._current(c, task)
            final = status or (TaskStatus.blocked if cur.status == TaskStatus.blocked else TaskStatus.done)
            cur.status, cur.result_refs, cur.finished_at = final, result_refs, utcnow()
            cur.note = note or cur.note
            self._save(c, cur)
            return cur

    def fail(self, task: Task, error: str) -> tuple[Task, bool]:
        """Returns (task, retried). Retries go back to ready without an owner."""
        with self._tx() as c:
            cur = self._current(c, task)
            if cur.attempts < cur.max_attempts:
                cur.status, cur.owner, cur.lease_expires_at = TaskStatus.ready, None, None
                cur.note = f"attempt {cur.attempts} failed: {error[:300]}; retrying"
                retried = True
            else:
                cur.status, cur.finished_at = TaskStatus.failed, utcnow()
                cur.note = f"failed after {cur.attempts} attempt(s): {error[:300]}"
                retried = False
            self._save(c, cur)
            return cur, retried

    def renew(self, task: Task, lease_s: int) -> Task:
        with self._tx() as c:
            cur = self._current(c, task)
            cur.lease_expires_at = utcnow() + timedelta(seconds=lease_s)
            self._save(c, cur)
            return cur

    def expire_overdue(self, now=None, can_exclude=None) -> list[tuple[Task, str, str, bool]]:
        """Atomically expire claims past their lease. Returns (task, expired owner, expired attempt, retried).

        `can_exclude(task, owner)` says whether another worker can take the task; if not,
        the same worker may retry it with a fresh attempt instead of leaving it stranded.
        """
        now = now or utcnow()
        out = []
        with self._tx() as c:
            for t in self._all(c):
                if t.status != TaskStatus.claimed or t.lease_expires_at is None or t.lease_expires_at > now:
                    continue
                owner, attempt = t.owner or "", t.attempt_id or ""
                t.expired_attempts.append(attempt)
                if owner and owner not in t.excluded_workers and (can_exclude is None or can_exclude(t, owner)):
                    t.excluded_workers.append(owner)
                retried = t.attempts < t.max_attempts
                if retried:
                    t.status, t.owner, t.attempt_id, t.lease_expires_at = TaskStatus.ready, None, None, None
                    t.fencing = True  # held until the coordinator has closed the expired attempt's contexts
                    t.note = f"lease of {owner} attempt {attempt} expired; queued for another worker"
                else:
                    t.status, t.finished_at, t.attempt_id = TaskStatus.failed, now, None
                    t.note = f"lease of {owner} attempt {attempt} expired on the final attempt ({t.attempts}/{t.max_attempts})"
                self._save(c, t)
                out.append((t, owner, attempt, retried))
        return out

    def release(self, task_id: str) -> Task:
        """After fencing, make an expired task claimable again."""
        with self._tx() as c:
            row = c.execute("SELECT data FROM tasks WHERE id=?", (task_id,)).fetchone()
            t = Task.model_validate_json(row[0])
            t.fencing = False
            self._save(c, t)
            return t

    def snapshot(self) -> list[Task]:
        with self._tx() as c:
            return self._all(c)

    def claimable_types(self) -> set[str]:
        """Types that have a ready task whose dependencies are done or could still become done."""
        tasks = self.snapshot()
        by_id = {t.id: t for t in tasks}
        out = set()
        for t in tasks:
            if t.status == TaskStatus.ready and not any(
                    by_id.get(d) is not None and by_id[d].status in BAD_END for d in t.depends_on):
                out.add(t.type)
        return out

    def claimable_for(self, worker: str, types: set[str]) -> bool:
        """Could this worker claim something now or once running dependencies finish?"""
        tasks = self.snapshot()
        by_id = {t.id: t for t in tasks}
        return any(t.status == TaskStatus.ready and t.type in types and worker not in t.excluded_workers
                   and not any(by_id.get(d) is not None and by_id[d].status in BAD_END for d in t.depends_on)
                   for t in tasks)

    def mark_unfinished(self, reason: str) -> list[Task]:
        """At the end of a run: every task that never ran is explicitly unfinished."""
        with self._tx() as c:
            out = []
            for t in self._all(c):
                if t.status in (TaskStatus.ready, TaskStatus.claimed):
                    t.status, t.note, t.finished_at = TaskStatus.unfinished, reason, utcnow()
                    self._save(c, t)
                    out.append(t)
            return out
