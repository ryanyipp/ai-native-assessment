"""Extra checks on a saved recovery run: ordering, fresh setup for the replacement, nothing written late."""
import json
import sys

d = json.load(open(sys.argv[1], encoding="utf-8"))
ev = d["events"]
claim_a = next(e for e in ev if e["type"] == "task_claimed" and e["agent_id"] == "explorer-a")
tid, att_a = claim_a["task_id"], claim_a["data"]["attempt_id"]
seq = lambda t, f=lambda e: True: next(e["seq"] for e in ev if e["type"] == t and f(e))
expired = next(e for e in ev if e["type"] == "lease_expired")
task = next(t for t in d["tasks"] if t["id"] == tid)
att_b = task["attempt_id"]
acts = [a for a in d["actions"] if a.get("task_id") == tid]
a_acts = [a for a in acts if a["agent_id"] == "explorer-a"]
b_acts = [a for a in acts if a["agent_id"] == "explorer-b"]
ctx = lambda xs: sorted({a["context_id"] for a in xs})
late = [a for a in a_acts if a["started_at"] > expired["created_at"]]
b_states = [s for s in d["states"] if any(si.get("agent_id") == "explorer-b" for si in s.get("sightings", []))]
checks = {
    "1 A claimed, then the injected stall started": seq("task_claimed", lambda e: e["agent_id"] == "explorer-a") < seq("fault_injected", lambda e: e["agent_id"] == "explorer-a"),
    "2 lease expired for A's attempt": expired["data"].get("attempt_id") == att_a,
    "3 context fenced before the task was released": seq("lease_expired") < seq("context_fenced") < seq("task_reassigned"),
    "4a B claimed a new attempt of the same task": task["owner"] == "explorer-b" and att_b != att_a and att_a in task["expired_attempts"],
    "4b B used its own fresh context and workspace": bool(b_acts) and not set(ctx(b_acts)) & set(ctx(a_acts)),
    "4c B began by opening the start URL (the task's setup)": bool(b_acts) and b_acts[0]["action"]["type"] == "navigate",
    "5a A's late model call refused": any(e["type"] == "late_action_rejected" and e["data"].get("attempt_id") == att_a for e in ev),
    "5b A's late result rejected": any(e["type"] == "result_rejected" and e["data"].get("attempt_id") == att_a for e in ev),
    "5c A recorded no browser action after expiry": not late,
    "6a B's completion kept (task done, owned by B)": task["status"] == "done" and task["owner"] == "explorer-b",
    "6b recovery recorded": any(e["type"] == "task_recovered" for e in ev),
    "labels: injected failure and scripted model": d["run"]["provenance"]["injected_failure"] and d["run"]["provenance"]["mocked_model"] and not d["run"]["provenance"]["live"],
}
for k, v in checks.items():
    print("PASS" if v else "FAIL", k)
print("A contexts", ctx(a_acts), "actions", len(a_acts), "| B contexts", ctx(b_acts), "actions", len(b_acts))
print("B first action", b_acts[0]["action"] if b_acts else None, "| states sighted by B", len(b_states))
print("limits", {k: d["run"]["limits"][k] for k in ("task_lease_s", "max_model_calls", "max_duration_s")}, "fault", d["run"]["fault_injection"])
print("run", d["run"]["id"], d["run"]["status"], "| cost", d["run"]["usage"]["reported_cost_usd"], "| calls", d["run"]["usage"]["model_calls"])
sys.exit(0 if all(checks.values()) else 1)
