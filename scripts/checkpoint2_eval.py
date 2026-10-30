"""Checkpoint 2 evaluation: live explorer -> tester -> verifier chains on both fixture builds.

Evaluation tooling only. It knows which port serves which build; the agents do not.
Prerequisites: fixture broken build on :5174 and corrected build on :5175
(see fixtures/creator-studio/README.md), OPENROUTER_API_KEY in .env.

Usage: backend\\.venv\\Scripts\\python scripts\\checkpoint2_eval.py [broken|corrected|reverify|all]

Every attempt is appended to submission-evidence/checkpoint-2/attempts.jsonl;
nothing earlier is overwritten. Records go to the normal FlowLens database, so
runs appear in the UI.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from flowlens.config import get_settings  # noqa: E402
from flowlens.models.contracts import Provenance, Run, RunLimits, VerificationAttempt  # noqa: E402
from flowlens.orchestration.review import ReverifyRun, ReviewRun  # noqa: E402
from flowlens.services.llm import OpenRouterClient  # noqa: E402
from flowlens.storage.db import Store  # noqa: E402
from check_prereq import require_live

BUILDS = {"broken": "http://localhost:5174/", "corrected": "http://localhost:5175/"}
GOAL = ("Explore the creator dashboard and open each form a creator can use, without submitting them. "
        "Finish when you have seen them.")
OUT = ROOT / "submission-evidence" / "checkpoint-2"


def requirements() -> list[str]:
    text = (ROOT / "fixtures" / "creator-studio" / "requirements.md").read_text("utf-8")
    items = re.split(r"\n(?=- R\d)", text)
    return [" ".join(i.strip()[2:].split()) for i in items if i.strip().startswith("- R")]


def summarise(store: Store, run_id: str, label: str) -> dict:
    d = store.detail(run_id)
    return {
        "label": label, "run_id": run_id, "target": d.run.target_url, "target_build": d.run.target_build,
        "mode": d.run.mode, "status": d.run.status, "stop_reason": d.run.stop_reason,
        "live": d.run.provenance.live, "usage": d.run.usage.model_dump(),
        "calls_by_agent": {a: sum(1 for m in d.model_calls if m.agent_id == a) for a in
                           sorted({m.agent_id for m in d.model_calls})},
        "forms": [{"id": f.id, "route": f.route, "fields": [x.control.name for x in f.fields]} for f in d.forms],
        "handoffs": [{"id": h.id, "kind": h.kind, "from": h.from_agent, "to": h.to_agent} for h in d.handoffs],
        "test_cases": [{"id": t.id, "label": t.label, "inputs": t.inputs, "requirement": t.requirement_ref,
                        "status": t.status, "tester_verdict": t.tester_verdict,
                        "alerts": t.observed.get("alert_messages"), "url_after": t.observed.get("url_after")}
                       for t in d.test_cases],
        "findings": [{"id": f.id, "kind": f.kind, "reported_by": f.reported_by, "requirement": f.requirement_ref,
                      "inputs": f.inputs, "verification_status": f.verification_status,
                      "reason": f.verification_reason, "source_finding_id": f.source_finding_id}
                     for f in d.findings],
        "verifications": [{"id": v.id, "finding_id": v.finding_id, "replay": v.replay_index, "outcome": v.outcome,
                           "failure_class": v.failure_class,
                           "assertion": v.assertion.model_dump() if v.assertion else None,
                           "passed": v.result.passed if v.result else None,
                           "observed": v.result.observed if v.result else None,
                           "evidence_refs": v.evidence_refs} for v in d.verifications],
    }


def log(entry: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    entry["recorded_at"] = datetime.now(UTC).isoformat()
    with (OUT / "attempts.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, default=str) + "\n")
    print(json.dumps({k: entry[k] for k in ("label", "run_id", "status", "stop_reason", "usage")}, default=str))
    for f in entry["findings"]:
        print("  finding", f["id"], f["kind"], f["requirement"], f["verification_status"])


async def live_chain(build: str) -> str:
    s = get_settings()
    store = Store(s.database_path)
    run = Run(target_url=BUILDS[build], goal=GOAL, requirements=requirements(), model=s.openrouter_model,
              mode="explore_test_verify", limits=RunLimits(max_cost_usd=s.flowlens_run_budget_usd),
              target_build=f"creator-studio:{build}", provenance=Provenance(live=True, synthetic_fixture=True))
    store.put(run)
    await ReviewRun(run, store, s, OpenRouterClient(s)).execute()
    log(summarise(store, run.id, f"live chain on {build} build"))
    return run.id


async def reverify(source_run_id: str | None = None) -> str | None:
    s = get_settings()
    store = Store(s.database_path)
    if source_run_id is None:
        runs = [r for r in store.list_runs() if r.target_build == "creator-studio:broken" and r.mode == "explore_test_verify"]
        source_run_id = runs[0].id if runs else None
    if source_run_id is None:
        print("no broken-build run to re-check")
        return None
    src = next((f for f in store.detail(source_run_id).findings if f.verification_status == "confirmed"), None)
    if src is None:
        print(f"{source_run_id} has no confirmed finding to re-check")
        return None
    assertion = store.get(VerificationAttempt, src.verification_ids[0]).assertion
    run = Run(target_url=BUILDS["corrected"], goal=f"Re-check {src.id} from {source_run_id} on the corrected build",
              requirements=requirements(), model="none (browser-only re-check)", mode="reverify",
              limits=RunLimits(), target_build="creator-studio:corrected",
              provenance=Provenance(live=False, synthetic_fixture=True))
    store.put(run)
    await ReverifyRun(run, store, s, OpenRouterClient(s), src, assertion).execute()
    log(summarise(store, run.id, f"browser-only re-check of {src.id} on corrected build"))
    return run.id


async def main(which: str) -> None:
    broken = None
    if which in ("broken", "all"):
        broken = await live_chain("broken")
    if which in ("corrected", "all"):
        await live_chain("corrected")
    if which in ("reverify", "all"):
        await reverify(broken)


if __name__ == "__main__":
    require_live()
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "all"))
