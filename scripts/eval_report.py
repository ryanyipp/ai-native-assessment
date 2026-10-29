r"""Score a saved evaluation batch against the frozen answer key and write the comparison.

Reads only saved records (the FlowLens database and evaluation/results/<batch>/runs.jsonl)
and evaluation/creator-studio/answer_key.json. Writes:
  evaluation/results/<batch>/runs/<run_id>.json   full run records
  evaluation/results/<batch>/scores.json          per-run scores
  docs/evaluation.md                              Markdown comparison

Usage: backend\.venv\Scripts\python scripts\eval_report.py BATCH_ID
"""

from __future__ import annotations

import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from flowlens.config import get_settings  # noqa: E402
from flowlens.storage.db import Store  # noqa: E402

KEY = json.loads((ROOT / "evaluation" / "creator-studio" / "answer_key.json").read_text("utf-8"))
SCEN = json.loads((ROOT / "evaluation" / "creator-studio" / "scenario.json").read_text("utf-8"))


def match_state(st, ref) -> bool:
    head = st.summary.split(" — ")[0]
    if st.route != ref["route"] or not head.startswith(ref["heading"]):
        return False
    return (" — " in st.summary) if ref.get("needs_alert") else True


def score(rec: dict, d) -> dict:
    build = rec["build"]
    refs = KEY["reference_states"]
    required = [r for r in refs if build not in r.get("optional_on", [])]
    matched = {r["id"] for r in refs if any(match_state(s, r) for s in d.states)}
    spurious = [s.summary for s in d.states if not any(match_state(s, r) for r in refs)]
    cand = [f for f in d.findings if f.kind != "persistence_check"]
    confirmed = [f for f in cand if f.verification_status == "confirmed"]
    defects = [k for k in KEY["known_defects"] if build in k["builds"]]

    def is_defect(f, k):
        v = (f.inputs or {}).get(k["field"], "")
        return f.requirement_ref == k["requirement"] and bool(v) and v < k["before"]

    found = [k["id"] for k in defects if any(is_defect(f, k) for f in confirmed)]
    false_conf = [f for f in confirmed if not any(is_defect(f, k) for k in defects)]
    verifs = {v.id: v for v in d.verifications}
    tasks_bad = [t for t in d.tasks if t.status in ("unfinished", "blocked", "failed")]
    forms_untested = [f.id for f in d.forms if not any(t.form_id == f.id for t in d.test_cases)]
    run = d.run
    elapsed = (run.finished_at - run.created_at).total_seconds() if run.finished_at else None
    return {
        **{k: rec[k] for k in ("condition", "build", "rep", "run_id")},
        "status": run.status.value, "stop_reason": run.stop_reason, "harness_error": rec.get("harness_error"),
        "coverage_required": f"{len(matched & {r['id'] for r in required})}/{len(required)}",
        "coverage_ratio": len(matched & {r["id"] for r in required}) / len(required),
        "matched_states": sorted(matched), "spurious_states": len(spurious), "states_total": len(d.states),
        "known_defects": [k["id"] for k in defects], "found": found,
        "missed": [k["id"] for k in defects if k["id"] not in found],
        "false_confirmations": [f"{f.requirement_ref}: {f.description}" for f in false_conf],
        "confirmed": len(confirmed), "not_reproduced": sum(f.verification_status == "not_reproduced" for f in cand),
        "inconclusive": sum(f.verification_status == "inconclusive" for f in cand),
        "unverified": sum(f.verification_status == "unverified" for f in cand),
        "candidates": len(cand), "test_cases": len(d.test_cases),
        "unfinished_tasks": len(tasks_bad), "forms_discovered": len(d.forms), "forms_untested": len(forms_untested),
        "elapsed_s": round(elapsed, 1) if elapsed is not None else None,
        "calls": run.usage.model_calls, "tokens": run.usage.total_tokens,
        "cost_usd": round(run.usage.reported_cost_usd, 6), "truncated_calls": run.usage.truncated_calls,
        "independence": sorted({f.verification_independence or "-" for f in confirmed}),
        "confirmed_assertions": [
            {"finding": f.id, "requirement": f.requirement_ref, "inputs": f.inputs,
             "assertion": (verifs[f.verification_ids[0]].assertion.model_dump() if f.verification_ids
                           and verifs.get(f.verification_ids[0]) and verifs[f.verification_ids[0]].assertion else None),
             "observed": [verifs[v].result.observed for v in f.verification_ids if verifs.get(v) and verifs[v].result],
             "verified_by": f.verified_by, "independence": f.verification_independence}
            for f in confirmed],
    }


def fmt(xs, nd=0):
    xs = [x for x in xs if x is not None]
    if not xs:
        return "–"
    m = statistics.mean(xs)
    return f"{m:.{nd}f} ({min(xs):.{nd}f}–{max(xs):.{nd}f})"


def main(batch: str) -> None:
    out = ROOT / "evaluation" / "results" / batch
    recs = [json.loads(x) for x in (out / "runs.jsonl").read_text("utf-8").splitlines() if x.strip()]
    store = Store(get_settings().database_path)
    (out / "runs").mkdir(exist_ok=True)
    scores = []
    for rec in recs:
        d = store.detail(rec["run_id"])
        (out / "runs" / f"{rec['run_id']}.json").write_text(d.model_dump_json(), "utf-8")
        scores.append(score(rec, d))
    (out / "scores.json").write_text(json.dumps(scores, indent=2, default=str), "utf-8")

    L = [f"# Evaluation: single-agent baseline vs shared-queue multi-agent ({batch})", "",
         "Generated by `scripts/eval_report.py` from saved run records and the frozen answer key "
         "(`evaluation/creator-studio/`). Live model, real Chromium, local fixture. No injected faults. "
         f"Same goal, requirements R1–R5, model `{get_settings().openrouter_model}`, limits "
         f"`{json.dumps(SCEN['limits'])}` and empty starting workspaces for both conditions.", "",
         "**Conditions.** `single_agent`: one agent context explores, tests, judges and self-checks its own findings; "
         "code replays in fresh contexts and evaluates the assertion. `queue_review`: explorer-a, explorer-b, "
         "input-tester and an independent verifier on the shared queue. The sequential specialist pipeline is not part "
         "of this comparison.", "",
         "Zero findings is never counted as a pass. Coverage counts matched reference states out of those required "
         "for the build (S6, the rejection alert, is not required on the broken build).", "",
         "## Per run", "",
         "| Condition | Build | Rep | Run | Status | Coverage | Spurious states | Defect found | False confirmations | "
         "Inconclusive | Unfinished tasks | Elapsed s | Calls | Tokens | US$ |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in scores:
        found = ", ".join(s["found"]) or ("missed " + ", ".join(s["missed"]) if s["missed"] else "n/a (none known)")
        L.append(f"| {s['condition']} | {s['build']} | {s['rep']} | `{s['run_id']}` | {s['status']} | "
                 f"{s['coverage_required']} | {s['spurious_states']} | {found} | {len(s['false_confirmations'])} | "
                 f"{s['inconclusive']} | {s['unfinished_tasks']} | {s['elapsed_s']} | {s['calls']} | {s['tokens']} | "
                 f"{s['cost_usd']:.4f} |")
    L += ["", "## Summary by condition and build", "",
          "Mean (min–max) over the runs that exist. With about three runs per cell these are descriptions, not "
          "statistically meaningful differences.", "",
          "| Condition | Build | Runs | D1 found | False confirmations | Coverage | Inconclusive | Unfinished tasks | "
          "Elapsed s | Calls | US$ |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in SCEN["conditions"]:
        for b in ("broken", "corrected"):
            g = [s for s in scores if s["condition"] == c and s["build"] == b]
            if not g:
                continue
            d1 = f"{sum('D1' in s['found'] for s in g)}/{len(g)}" if b == "broken" else "n/a"
            L.append(f"| {c} | {b} | {len(g)} | {d1} | {sum(len(s['false_confirmations']) for s in g)} | "
                     f"{fmt([s['coverage_ratio'] * 100 for s in g])}% | {fmt([s['inconclusive'] for s in g])} | "
                     f"{fmt([s['unfinished_tasks'] for s in g])} | {fmt([s['elapsed_s'] for s in g])} | "
                     f"{fmt([s['calls'] for s in g])} | {fmt([s['cost_usd'] for s in g], 4)} |")
    total = sum(s["cost_usd"] for s in scores)
    L += ["", f"Batch total: {len(scores)} runs, {sum(s['calls'] for s in scores)} calls, "
          f"{sum(s['tokens'] for s in scores):,} tokens, US${total:.4f} reported (cap US${SCEN['batch_cap_usd']}).", "",
          "## Confirmed findings and their assertions", "",
          "Every confirmed finding, with the assertion code evaluated and what it observed (see the manual review below).", ""]
    for s in scores:
        for a in s["confirmed_assertions"]:
            obs = a["observed"][0] if a["observed"] else {}
            short = {k: obs.get(k) for k in ("route", "alert_messages", "matching_messages", "status_messages") if k in obs}
            L.append(f"- `{s['run_id']}` ({s['condition']}, {s['build']}): {a['requirement']} inputs "
                     f"`{json.dumps(a['inputs'], ensure_ascii=False)}`; assertion "
                     f"`{a['assertion']['type'] if a['assertion'] else '-'} {json.dumps((a['assertion'] or {}).get('params'))}`; "
                     f"observed `{json.dumps(short, ensure_ascii=False)}`; checked by {a['verified_by']} "
                     f"({a['independence']}).")
    if not any(s["confirmed_assertions"] for s in scores):
        L.append("- none")
    L += ["", "## Runs that did not complete", ""]
    bad = [s for s in scores if s["status"] != "completed" or s["harness_error"]]
    for s in bad:
        L.append(f"- `{s['run_id']}` ({s['condition']}, {s['build']}, rep {s['rep']}): {s['status']} — {s['stop_reason']}"
                 + (f"; harness error: {s['harness_error']}" if s["harness_error"] else ""))
    if not bad:
        L.append("- none")
    (ROOT / "docs" / "evaluation.md").write_text("\n".join(L) + "\n", "utf-8")
    print(f"scored {len(scores)} runs; US${total:.4f}; wrote docs/evaluation.md")


if __name__ == "__main__":
    main(sys.argv[1])
