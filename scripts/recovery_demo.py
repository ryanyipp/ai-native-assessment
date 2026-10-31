r"""Injected-stall recovery demonstration: explorer-a stalls 75 s on a 45 s lease. Scripted model, no spend.

The website under review is only the target. The failure comes from the run's fault_injection setting.

Start the fixture (docker compose up -d) and scripts\scripted_server.py, then:
    backend\.venv\Scripts\python scripts\recovery_demo.py [--api URL] [--target URL] [--out FILE]
Exit code 0 only if every recovery check passes.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "backend" / "tests"), str(REPO / "backend" / "tests" / "integration")]
from test_review import REQS  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--api", default="http://127.0.0.1:8010")
p.add_argument("--target", default="http://localhost:5174/")
p.add_argument("--out")
a = p.parse_args()

BODY = {"target_url": a.target, "goal": "Explore the dashboard forms", "requirements": REQS, "mode": "queue_review",
        "limits": {"task_lease_s": 45, "max_model_calls": 40, "max_cost_usd": 0.5, "max_duration_s": 300},
        "fault_injection": {"worker": "explorer-a", "task_type": "explore", "stall_s": 75}}
r = httpx.post(a.api + "/api/runs", json=BODY, timeout=30)
r.raise_for_status()
run_id = r.json()["id"]
print("run", run_id, flush=True)
while True:
    d = httpx.get(f"{a.api}/api/runs/{run_id}", timeout=30).json()
    if d["run"]["status"] not in ("queued", "running"):
        break
    time.sleep(2)

events = d["events"]


def first(type_, test=lambda e: True):
    return next((e for e in events if e["type"] == type_ and test(e)), None)


claim = first("task_claimed", lambda e: e["agent_id"] == "explorer-a")
att = claim["data"]["attempt_id"]


def same(e):
    return e["task_id"] == claim["task_id"]


timeline = [claim, first("fault_injected", lambda e: e["agent_id"] == "explorer-a"), first("lease_expired"),
            first("context_fenced"), first("task_reassigned"),
            first("task_claimed", lambda e: same(e) and e["agent_id"] != "explorer-a"),
            first("task_completed", same), first("task_recovered"), first("late_action_rejected"),
            first("result_rejected"), first("run_finished")]
for e in timeline:
    if e:
        print(f'{e["seq"]:>5} {e["created_at"][11:23]} {e["agent_id"]:<12} {e["type"]:<21} {e["message"][:105]}')
task = next(t for t in d["tasks"] if t["id"] == claim["task_id"])
checks = {
    "scripted model label": d["run"]["provenance"]["mocked_model"] and not d["run"]["provenance"]["live"],
    "lease expired for the original attempt": att in task["expired_attempts"],
    "browser context closed": (first("context_fenced") or {"data": {}})["data"].get("contexts_closed", 0) >= 1,
    "replacement is explorer-b with a new attempt": task["owner"] == "explorer-b" and task["attempt_id"] != att,
    "replacement finished the task": task["status"] == "done",
    "late call refused": bool(first("late_action_rejected", lambda e: e["data"].get("attempt_id") == att)),
    "late result rejected": bool(first("result_rejected", lambda e: e["data"].get("attempt_id") == att)),
    "no model cost": d["run"]["usage"]["reported_cost_usd"] == 0,
}
for name, ok in checks.items():
    print("PASS" if ok else "FAIL", name)
print("final", d["run"]["status"], "|", d["run"]["stop_reason"][:160], "| findings",
      [(f["requirement_ref"], f["verification_status"]) for f in d["findings"]])
if a.out:
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(d, indent=1), "utf-8")
sys.exit(0 if all(checks.values()) else 1)
