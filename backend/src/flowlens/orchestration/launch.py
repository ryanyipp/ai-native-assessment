"""Starting runs, and refusing to start them from stale code.

All run classes are imported here at process start. Before this module existed,
`ReviewRun` was imported lazily on the first review run; a backend left running
across a code change then combined new `review.py` with old in-memory contracts
and crashed mid-run (run_53d7009ff711). Now one process uses one code version,
and a change on disk after start is detected before a run begins.
"""

from __future__ import annotations

import asyncio
import hashlib
import threading
from pathlib import Path

from flowlens.config import Settings
from flowlens.models.contracts import Run
from flowlens.orchestration.queue_review import QueueReviewRun
from flowlens.orchestration.review import ReviewRun
from flowlens.orchestration.runner import ExplorerRun
from flowlens.orchestration.single_agent import SingleAgentRun
from flowlens.services.llm import LLMClient
from flowlens.storage.db import Store

PACKAGE_DIR = Path(__file__).resolve().parents[1]


def source_fingerprint(root: Path = PACKAGE_DIR) -> str:
    """Hash of every backend source file (paths and contents)."""
    h = hashlib.sha256()
    for p in sorted(root.rglob("*.py")):
        h.update(p.relative_to(root).as_posix().encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


LOADED_FINGERPRINT = source_fingerprint()


class StaleCodeError(RuntimeError):
    pass


def check_code_current() -> None:
    on_disk = source_fingerprint()
    if on_disk != LOADED_FINGERPRINT:
        raise StaleCodeError(
            "The backend source changed after this server started "
            f"(loaded {LOADED_FINGERPRINT}, on disk {on_disk}). Restart the backend before starting a run."
        )


def run_class(run: Run) -> type[ExplorerRun]:
    return {"explore_test_verify": ReviewRun, "queue_review": QueueReviewRun, "single_agent": SingleAgentRun}.get(run.mode, ExplorerRun)


def start_run_thread(run: Run, store: Store, settings: Settings, llm: LLMClient) -> threading.Thread:
    """Each run gets its own thread and event loop (Playwright needs a subprocess-capable loop on Windows)."""
    cls = run_class(run)

    def target():
        asyncio.run(cls(run, store, settings, llm).execute())

    t = threading.Thread(target=target, name=f"run-{run.id}", daemon=True)
    t.start()
    return t
