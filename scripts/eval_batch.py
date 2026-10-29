r"""Evaluation batch: single-agent baseline vs shared-queue multi-agent, broken and corrected builds.

Evaluation tooling only (it knows which port is which build; agents do not).
Reads the frozen scenario in evaluation/creator-studio/scenario.json. Every run
is appended to evaluation/results/<batch>/runs.jsonl as soon as it ends,
including failures. The batch stops before a run that could exceed the cap.

Usage (repo root, with the scenario builds running):
  backend\.venv\Scripts\python scripts\eval_batch.py [BATCH_ID]
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from flowlens.config import get_settings  # noqa: E402
from flowlens.models.contracts import Provenance, Run, RunLimits  # noqa: E402
from flowlens.orchestration.launch import run_class  # noqa: E402
from flowlens.services.llm import OpenRouterClient  # noqa: E402
from flowlens.storage.db import Store  # noqa: E402

SCENARIO_PATH = (ROOT / sys.argv[2]) if len(sys.argv) > 2 else ROOT / "evaluation" / "creator-studio" / "scenario.json"
SCENARIO = json.loads(SCENARIO_PATH.read_text("utf-8"))
CONDITIONS = sys.argv[3].split(",") if len(sys.argv) > 3 and sys.argv[3] != "all" else list(SCENARIO["conditions"])
MAX_NEW_RUNS = int(sys.argv[4]) if len(sys.argv) > 4 else None  # staged batches: stop after this many new runs


def requirements() -> list[str]:
    text = (ROOT / SCENARIO["requirements_source"].split(" (")[0]).read_text("utf-8")
    items = re.split(r"\n(?=- [A-Z]+\d)", text)
    return [" ".join(i.strip()[2:].split()) for i in items if re.match(r"- [A-Z]+\d", i.strip())]


async def one(store, s, condition: str, build: str, rep: int, batch: str) -> dict:
    lim = SCENARIO["limits"]
    run = Run(target_url=SCENARIO["builds"][build], goal=SCENARIO["goal"], requirements=requirements(),
              model=s.openrouter_model, mode=condition, limits=RunLimits(**lim),
              target_build=f"creator-studio:{build}", provenance=Provenance(live=True, synthetic_fixture=True))
    store.put(run)
    t0 = time.monotonic()
    error = None
    try:
        await run_class(run)(run, store, s, OpenRouterClient(s)).execute()
    except Exception as e:  # recorded, never dropped
        error = f"{type(e).__name__}: {e}"
    final = store.get(Run, run.id)
    return {"batch": batch, "scenario": str(SCENARIO_PATH.relative_to(ROOT)), "condition": condition, "build": build, "rep": rep, "run_id": run.id,
            "status": final.status, "stop_reason": final.stop_reason, "harness_error": error,
            "wall_s": round(time.monotonic() - t0, 1), "reported_cost_usd": final.usage.reported_cost_usd,
            "recorded_at": datetime.now(UTC).isoformat()}


async def main(batch: str) -> None:
    s = get_settings()
    store = Store(s.database_path)
    out = ROOT / "evaluation" / "results" / batch
    out.mkdir(parents=True, exist_ok=True)
    log = out / "runs.jsonl"
    done = [json.loads(x) for x in log.read_text("utf-8").splitlines()] if log.exists() else []
    spent = sum(d["reported_cost_usd"] for d in done)
    cap, per_run = SCENARIO["batch_cap_usd"], SCENARIO["limits"]["max_cost_usd"]
    plan = [(c, b, r) for r in range(1, SCENARIO["repetitions"] + 1) for b in ("broken", "corrected")
            for c in CONDITIONS]
    new_runs = 0
    for condition, build, rep in plan:
        if MAX_NEW_RUNS is not None and new_runs >= MAX_NEW_RUNS:
            print(f"stopping: staged limit of {MAX_NEW_RUNS} new run(s) reached")
            break
        if any((d["condition"], d["build"], d["rep"]) == (condition, build, rep) for d in done):
            continue
        if spent + per_run > cap:
            print(f"stopping: US${spent:.4f} spent; another run could exceed the US${cap} cap")
            break
        rec = await one(store, s, condition, build, rep, batch)
        new_runs += 1
        spent += rec["reported_cost_usd"]
        with log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, default=str) + "\n")
        print(json.dumps({k: rec[k] for k in ("condition", "build", "rep", "run_id", "status", "wall_s",
                                               "reported_cost_usd")}, default=str), f"batch US${spent:.4f}", flush=True)


LOCK = ROOT / "evaluation" / ".batch.lock"


def other_batch_processes() -> list[str]:
    """Other running eval_batch processes, from the OS process table (Git Bash `ps` cannot see them)."""
    import os
    import subprocess
    if os.name != "nt":
        out = subprocess.run(["ps", "-eo", "pid,args"], capture_output=True, text=True).stdout.splitlines()
        rows = [line.strip().split(None, 1) for line in out[1:]]
    else:
        # Only Python interpreters running the script count; shells that merely launch it do not.
        cmd = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python' -and "
               "$_.CommandLine -match 'eval_batch\\.py' } | "
               "ForEach-Object { \"$($_.ProcessId) $($_.CommandLine)\" }")
        out = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True).stdout
        rows = [line.strip().split(None, 1) for line in out.splitlines() if line.strip()]
    me = {str(os.getpid()), str(os.getppid())}
    return [f"{r[0]} {r[1][:160]}" for r in rows if len(r) == 2 and r[0] not in me and "eval_batch.py" in r[1]
            and "python" in r[1].split("eval_batch.py")[0].lower()]


def acquire_lock(batch: str) -> None:
    """Refuse to start if another batch is running or a lock is held; one batch at a time, sequentially."""
    import os
    others = other_batch_processes()
    if others:
        sys.exit("refusing to start: another evaluation batch process is running:\n  " + "\n  ".join(others))
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        sys.exit(f"refusing to start: {LOCK} exists ({LOCK.read_text('utf-8').strip()}). Remove it only after "
                 "checking that no batch is running.")
    os.write(fd, f"pid={os.getpid()} batch={batch} started={datetime.now(UTC).isoformat()}".encode())
    os.close(fd)


if __name__ == "__main__":
    batch_id = sys.argv[1] if len(sys.argv) > 1 else datetime.now(UTC).strftime("batch-%Y%m%d-%H%M")
    acquire_lock(batch_id)
    try:
        asyncio.run(main(batch_id))
    finally:
        LOCK.unlink(missing_ok=True)
