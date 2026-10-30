r"""Comparative benchmark: single_agent vs queue_review across models and targets.

Evaluation tooling only. One process, one review run at a time. Reads the frozen scenario in
evaluation/model-comparison/scenario.json. Spend is tracked across smoke and scored runs in
evaluation/results/<batch>/ledger.jsonl, taking the larger of recorded cost and the OpenRouter
key's usage change, and a run starts only if its full reservation still fits under the ceiling.
A finished cell is never rerun, so a restart cannot select better results.

Usage (repo root, fixtures running):
  backend\.venv\Scripts\python scripts\model_benchmark.py BATCH smoke --live
  backend\.venv\Scripts\python scripts\model_benchmark.py BATCH scored --live
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

import httpx  # noqa: E402

from check_prereq import require_live  # noqa: E402
from flowlens.browser.engine import origin_of  # noqa: E402
from flowlens.config import get_settings  # noqa: E402
from flowlens.models.contracts import Provenance, Run, RunLimits  # noqa: E402
from flowlens.orchestration.launch import LOADED_FINGERPRINT, run_class  # noqa: E402
from flowlens.services.llm import OpenRouterClient  # noqa: E402
from flowlens.storage.db import Store  # noqa: E402

require_live()
SCENARIO_PATH = ROOT / "evaluation" / "model-comparison" / os.environ.get("BENCHMARK_SCENARIO", "scenario.json")
SC = json.loads(SCENARIO_PATH.read_text("utf-8"))


def requirements(t: dict) -> list[str]:
    if "requirements" in t:
        return t["requirements"]
    text = (ROOT / t["requirements_file"]).read_text("utf-8")
    items = re.split(r"\n(?=- [A-Z]+\d)", text)
    return [" ".join(i.strip()[2:].split()) for i in items if re.match(r"- [A-Z]+\d", i.strip())]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def key_usage(s) -> float:
    key = s.openrouter_api_key.get_secret_value().strip()
    r = httpx.get(f"{s.openrouter_base_url.rstrip('/')}/key", headers={"Authorization": f"Bearer {key}"}, timeout=20)
    r.raise_for_status()
    return float(r.json()["data"]["usage"])


class Ledger:
    def __init__(self, out: Path, s):
        self.path, self.s = out / "ledger.jsonl", s
        self.rows = [json.loads(x) for x in self.path.read_text("utf-8").splitlines()] if self.path.exists() else []
        if self.rows:
            self.base = self.rows[0]["key_usage_base"]
        else:
            self.base = key_usage(s)
            self.note("start", 0.0)

    @property
    def recorded(self) -> float:
        return sum(r["recorded_usd"] for r in self.rows)

    def spent(self) -> float:
        return max(self.recorded, key_usage(self.s) - self.base)

    def note(self, label: str, cost: float) -> None:
        row = {"at": datetime.now(UTC).isoformat(), "label": label, "recorded_usd": cost, "key_usage_base": self.base,
               "key_usage": key_usage(self.s)}
        self.rows.append(row)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")


def unusable(store: Store, run_id: str, error: str | None) -> bool:
    d = store.detail(run_id)
    bad_calls = sum(not m.ok for m in d.model_calls)
    rejected = sum(e.type in ("decision_rejected", "reply_truncated") for e in d.events)
    good = len(d.model_calls) - bad_calls
    return bool(error) or good == 0 or (bad_calls + rejected) * 2 >= len(d.model_calls)


async def one(store, s, model: str, target: str, mode: str, rep, limits: dict, batch: str) -> dict:
    t = SC["targets"][target]
    settings = s.model_copy(update={"openrouter_model": model})
    llm = OpenRouterClient(settings)
    website = t["profile"] == "website"
    run = Run(target_url=t["url"], goal=t["goal"], requirements=requirements(t), model=model, mode=mode,
              limits=RunLimits(**limits), target_build=target, target_profile=t["profile"],
              scope_origins=[origin_of(t["url"])] if website else s.allowed_origins,
              provenance=Provenance(live=True, synthetic_fixture=not website))
    store.put(run)
    t0 = time.monotonic()
    error = None
    try:
        await run_class(run)(run, store, settings, llm).execute()
    except Exception as e:  # recorded, never dropped
        error = f"{type(e).__name__}: {e}"
    final = store.get(Run, run.id)
    return {"batch": batch, "model": model, "target": target, "mode": mode, "rep": rep, "run_id": run.id,
            "status": final.status, "stop_reason": final.stop_reason, "harness_error": error,
            "wall_s": round(time.monotonic() - t0, 1), "reported_cost_usd": final.usage.reported_cost_usd,
            "calls_without_cost": final.usage.calls_without_cost, "unusable": unusable(store, run.id, error),
            "git": git("rev-parse", "HEAD"), "code_fingerprint": LOADED_FINGERPRINT,
            "recorded_at": datetime.now(UTC).isoformat()}


def plan() -> list[tuple]:
    """Whole first repetition first, so a budget stop leaves matched pairs. The first mode alternates."""
    cells = []
    for rep in range(1, SC["repetitions"] + 1):
        for ti, target in enumerate(SC["targets"]):
            for mi, model in enumerate(SC["models"]):
                modes = SC["modes"] if (rep + ti + mi) % 2 == 0 else SC["modes"][::-1]
                cells += [(model, target, mode, rep) for mode in modes]
    return cells


async def main(batch: str, stage: str) -> int:
    s = get_settings()
    store = Store(s.database_path)
    out = ROOT / "evaluation" / "results" / batch
    out.mkdir(parents=True, exist_ok=True)
    ledger = Ledger(out, s)
    log = out / f"{stage}.jsonl"
    done = [json.loads(x) for x in log.read_text("utf-8").splitlines()] if log.exists() else []
    if stage == "smoke":
        cells = [(m, "creator-broken", "queue_review", "smoke") for m in SC.get("smoke_models", SC["models"][1:])]
        limits = SC["smoke_limits"]
    else:
        if git("status", "--porcelain", "--", "backend/src", "scripts/model_benchmark.py", "evaluation/model-comparison"):
            print("refusing to start: the frozen code or scenario has uncommitted changes")
            return 1
        cells, limits = plan(), SC["limits"]
    bad_streak = {m: 0 for m in SC["models"]}
    for r in done:
        bad_streak[r["model"]] = bad_streak[r["model"]] + 1 if r["unusable"] else 0
    for model, target, mode, rep in cells:
        if any((d["model"], d["target"], d["mode"], d["rep"]) == (model, target, mode, rep) for d in done):
            continue
        if bad_streak[model] >= 2:
            print(f"model stopped by the unusable rule, cell not run: {model} {target} {mode} {rep}", flush=True)
            continue
        spent = ledger.spent()
        if spent + SC["run_reservation_usd"] > SC["ceiling_usd"]:
            print(f"stopping: US${spent:.4f} spent; a further reservation could exceed the ceiling", flush=True)
            break
        rec = await one(store, s, model, target, mode, rep, limits, batch)
        with log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, default=str) + "\n")
        bad_streak[model] = bad_streak[model] + 1 if rec["unusable"] else 0
        await asyncio.sleep(4)  # let the key's usage figure catch up
        ledger.note(f"{stage}:{rec['run_id']}", rec["reported_cost_usd"])
        spent = ledger.spent()
        print(json.dumps({k: rec[k] for k in ("model", "target", "mode", "rep", "run_id", "status", "wall_s",
                                               "reported_cost_usd", "unusable")}, default=str),
              f"total US${spent:.4f} recorded US${ledger.recorded:.4f}", flush=True)
        gap = abs(spent - ledger.recorded)
        if rec["calls_without_cost"] or gap > SC["ledger_tolerance_usd"]:
            print(f"stopping: cost cannot be accounted for (no-cost calls {rec['calls_without_cost']}, gap US${gap:.4f})", flush=True)
            return 2
    print("batch finished", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1], sys.argv[2])))
