r"""Is a confirmed finding a supported detection? Browser only: no model calls, no spend.

Rule, fixed before the rerun: replay the finding's recorded steps and assertion on both builds. It is
supported only if every replay fails on the broken build and every replay passes on the corrected build.
An assertion that fails on both cannot tell the builds apart. A replay that cannot be set up is not supported.

Usage (repo root, fixtures running):
  backend\.venv\Scripts\python scripts\supported_check.py OUT.json run_id [run_id ...]
  backend\.venv\Scripts\python scripts\supported_check.py OUT.json --batch BATCH
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from flowlens.config import get_settings  # noqa: E402
from flowlens.models.contracts import Assertion, Finding, Provenance, Run, RunLimits, VerificationAttempt  # noqa: E402
from flowlens.orchestration.review import ReverifyRun  # noqa: E402
from flowlens.services.llm import ScriptedClient  # noqa: E402
from flowlens.storage.db import Store  # noqa: E402

PAIRS = {"http://localhost:5174/": ("http://localhost:5174/", "http://localhost:5175/"),
         "http://localhost:5176/": ("http://localhost:5176/", "http://localhost:5177/")}


def refuse(messages):
    raise RuntimeError("supported_check makes no model calls")


async def replay(store, s, src_run: Run, f: Finding, assertion: Assertion, url: str, build: str) -> dict:
    run = Run(target_url=url, goal=f"Supported-detection replay of {f.id}", requirements=src_run.requirements,
              model="none (browser-only re-check)", mode="reverify", limits=RunLimits(), target_build=build,
              scope_origins=s.allowed_origins, provenance=Provenance(live=False, synthetic_fixture=True))
    store.put(run)
    await ReverifyRun(run, store, s, ScriptedClient(refuse), f, assertion).execute()
    copy = store.list_for_run(Finding, run.id)[0]
    return {"run_id": run.id, "status": copy.verification_status.value,
            "attempts": [a.outcome for a in store.list_for_run(VerificationAttempt, run.id)]}


async def check(store, s, run_id: str) -> list[dict]:
    src_run = store.get(Run, run_id)
    if src_run.target_url not in PAIRS:
        return []
    broken, corrected = PAIRS[src_run.target_url]
    out = []
    for f in store.list_for_run(Finding, run_id):
        if f.kind == "persistence_check" or f.verification_status.value != "confirmed":
            continue
        a = next(v.assertion for v in reversed(store.list_for_run(VerificationAttempt, run_id))
                 if v.finding_id == f.id and v.assertion)
        b = await replay(store, s, src_run, f, a, broken, "broken")
        c = await replay(store, s, src_run, f, a, corrected, "corrected")
        row = {"source_run": run_id, "finding": f.id, "requirement": f.requirement_ref, "assertion": a.type.value,
               "params": a.params, "broken": b, "corrected": c,
               "supported": b["status"] == "confirmed" and c["status"] == "not_reproduced"}
        print(json.dumps(row), flush=True)
        out.append(row)
    return out


async def main(argv: list[str]) -> None:
    s = get_settings()
    store = Store(s.database_path)
    if argv[1] == "--batch":
        path = ROOT / "evaluation" / "results" / argv[2] / "scored.jsonl"
        runs = [r["run_id"] for r in map(json.loads, path.read_text("utf-8").splitlines()) if "broken" in r["target"]]
    else:
        runs = argv[1:]
    rows = [row for r in runs for row in await check(store, s, r)]
    Path(argv[0]).parent.mkdir(parents=True, exist_ok=True)
    Path(argv[0]).write_text(json.dumps(rows, indent=1), "utf-8")
    print(f"{sum(r['supported'] for r in rows)}/{len(rows)} supported")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
