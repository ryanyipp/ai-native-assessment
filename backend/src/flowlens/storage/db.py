"""SQLite source of truth. Each record is stored as validated JSON keyed by id.

A new connection is opened per operation so worker threads can write safely;
writes are serialised by SQLite itself (WAL mode, busy timeout).
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, TypeVar

from pydantic import BaseModel

from flowlens.models.contracts import (
    ActionResult,
    DiscoveredForm,
    Event,
    Evidence,
    Finding,
    Handoff,
    ModelCall,
    Run,
    RunDetail,
    RunStatus,
    ScreenState,
    Task,
    TestCase,
    Transition,
    VerificationAttempt,
)

M = TypeVar("M", bound=BaseModel)

_TABLES: dict[str, type[BaseModel]] = {
    "runs": Run,
    "states": ScreenState,
    "transitions": Transition,
    "actions": ActionResult,
    "findings": Finding,
    "evidence": Evidence,
    "model_calls": ModelCall,
    "tasks": Task,
    "forms": DiscoveredForm,
    "handoffs": Handoff,
    "test_cases": TestCase,
    "verifications": VerificationAttempt,
}


class Store:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.execute("PRAGMA journal_mode=WAL")
            for table in _TABLES:
                c.execute(
                    f"CREATE TABLE IF NOT EXISTS {table} ("
                    "pk INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, "
                    "run_id TEXT, data TEXT NOT NULL)"
                )
                c.execute(f"CREATE INDEX IF NOT EXISTS ix_{table}_run ON {table}(run_id)")
            c.execute(
                "CREATE TABLE IF NOT EXISTS events ("
                "seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, data TEXT NOT NULL)"
            )

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=10)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _table_for(model: BaseModel) -> str:
        for table, cls in _TABLES.items():
            if type(model) is cls:
                return table
        raise TypeError(f"no table for {type(model).__name__}")

    def put(self, record: BaseModel) -> None:
        table = self._table_for(record)
        run_id = getattr(record, "run_id", None) or getattr(record, "id")
        with self._conn() as c:
            c.execute(
                f"INSERT INTO {table}(id, run_id, data) VALUES (?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET data=excluded.data",
                (record.id, run_id, record.model_dump_json()),
            )

    def get(self, cls: type[M], record_id: str) -> M | None:
        table = next(t for t, c in _TABLES.items() if c is cls)
        with self._conn() as c:
            row = c.execute(f"SELECT data FROM {table} WHERE id=?", (record_id,)).fetchone()
        return cls.model_validate_json(row[0]) if row else None

    def list_for_run(self, cls: type[M], run_id: str) -> list[M]:
        table = next(t for t, c in _TABLES.items() if c is cls)
        with self._conn() as c:
            rows = c.execute(f"SELECT data FROM {table} WHERE run_id=? ORDER BY pk", (run_id,)).fetchall()
        return [cls.model_validate_json(r[0]) for r in rows]

    def list_runs(self) -> list[Run]:
        with self._conn() as c:
            rows = c.execute("SELECT data FROM runs ORDER BY pk DESC").fetchall()
        return [Run.model_validate_json(r[0]) for r in rows]

    def append_event(self, event: Event) -> Event:
        with self._conn() as c:
            cur = c.execute("INSERT INTO events(run_id, data) VALUES (?, '{}')", (event.run_id,))
            event.seq = cur.lastrowid
            c.execute("UPDATE events SET data=? WHERE seq=?", (event.model_dump_json(), event.seq))
        return event

    def events_for_run(self, run_id: str, after_seq: int = 0) -> list[Event]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT data FROM events WHERE run_id=? AND seq>? ORDER BY seq", (run_id, after_seq)
            ).fetchall()
        return [Event.model_validate_json(r[0]) for r in rows]

    def total_reported_cost(self) -> float:
        """Recorded spend across every run, used for the overall credit pool."""
        return sum(r.usage.reported_cost_usd for r in self.list_runs())

    def mark_interrupted(self) -> int:
        """Runs left running by a crashed process stay inspectable, labelled interrupted."""
        n = 0
        for run in self.list_runs():
            if run.status in (RunStatus.queued, RunStatus.running):
                run.status = RunStatus.interrupted
                run.stop_reason = "backend process stopped before the run finished"
                self.put(run)
                n += 1
        return n

    def detail(self, run_id: str) -> RunDetail | None:
        run = self.get(Run, run_id)
        if run is None:
            return None
        return RunDetail(
            run=run,
            states=self.list_for_run(ScreenState, run_id),
            transitions=self.list_for_run(Transition, run_id),
            actions=self.list_for_run(ActionResult, run_id),
            findings=self.list_for_run(Finding, run_id),
            events=self.events_for_run(run_id),
            evidence=self.list_for_run(Evidence, run_id),
            model_calls=self.list_for_run(ModelCall, run_id),
            tasks=self.list_for_run(Task, run_id),
            forms=self.list_for_run(DiscoveredForm, run_id),
            handoffs=self.list_for_run(Handoff, run_id),
            test_cases=self.list_for_run(TestCase, run_id),
            verifications=self.list_for_run(VerificationAttempt, run_id),
        )
