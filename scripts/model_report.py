r"""Score the model comparison from saved records and frozen keys; writes scores.json and tables.md.

Usage: backend\.venv\Scripts\python scripts\model_report.py BATCH
"""

from __future__ import annotations

import json
import os
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from eval_report_v2 import defect_hit  # noqa: E402
from flowlens.config import get_settings  # noqa: E402
from flowlens.storage.db import Store  # noqa: E402

SC = json.loads((ROOT / "evaluation" / "model-comparison" / os.environ.get("BENCHMARK_SCENARIO", "scenario.json")).read_text("utf-8"))
SHORT = {"google/gemini-3-flash-preview": "Gemini", "deepseek/deepseek-v4-flash": "DeepSeek", "openai/gpt-5-nano": "GPT-5 Nano",
         "anthropic/claude-haiku-5.5": "Haiku 5.5"}
MODE = {"single_agent": "single", "queue_review": "queue"}


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else None


def score(rec, d):
    t = SC["targets"][rec["target"]]
    urls = [a.url_after or "" for a in d.actions if a.ok]
    goal = [u for u in t["goal_urls"] if not any(re.search(u, x) for x in urls)]
    cand = [f for f in d.findings if f.kind != "persistence_check"]
    conf = [f for f in cand if f.verification_status == "confirmed"]
    if t["key"]:
        key = json.loads((ROOT / t["key"]).read_text("utf-8"))
        known = [k for k in key["known_defects"] if t["build"] in k["builds"]]
        found = [k["id"] for k in known if any(defect_hit(f, k) for f in conf)]
        false = [f"{f.requirement_ref} {f.inputs}" for f in conf if not any(defect_hit(f, k) for k in known)]
        defects, nknown = found, len(known)
    else:
        defects, nknown, false = None, None, None
    ml = [m.latency_ms for m in d.model_calls if m.ok]
    bl = [a.duration_ms for a in d.actions]
    events = [e.type for e in d.events]
    return {
        **{k: rec[k] for k in ("model", "target", "mode", "rep", "run_id", "wall_s", "unusable", "git", "code_fingerprint")},
        "status": d.run.status.value, "stop_reason": d.run.stop_reason, "goal_met": not goal, "goal_missing": goal,
        "reqs_tested": sorted({c.requirement_ref for c in d.test_cases if c.requirement_ref and c.status == "executed"}),
        "reqs_verified": sorted({f.requirement_ref for f in cand if f.verification_status in ("confirmed", "not_reproduced")}),
        "forms": len(d.forms), "cases": len(d.test_cases), "defects_found": defects, "defects_known": nknown,
        "false_confirmations": false, "confirmed": [f"{f.requirement_ref}: {f.description} {f.inputs}" for f in conf],
        "independence": sorted({f.verification_independence for f in conf if f.verification_independence}),
        "unfinished": sum(t2.status.value in ("unfinished", "blocked", "failed") for t2 in d.tasks),
        "model_p50_ms": pct(ml, .5), "model_p95_ms": pct(ml, .95), "browser_p50_ms": pct(bl, .5), "browser_p95_ms": pct(bl, .95),
        "calls": d.run.usage.model_calls, "failed_calls": sum(not m.ok for m in d.model_calls),
        "in_tokens": d.run.usage.prompt_tokens, "out_tokens": d.run.usage.completion_tokens,
        "cost": d.run.usage.reported_cost_usd, "truncated": d.run.usage.truncated_calls,
        "retries": sum(x in ("decision_rejected", "reply_truncated", "task_retry") for x in events),
        "actual_models": sorted({m.model for m in d.model_calls}), "providers": sorted({str(m.provider) for m in d.model_calls}),
    }


def med(g, k):
    xs = [s[k] for s in g if s[k] is not None]
    return statistics.median(xs) if xs else None


def main(batch):
    out = ROOT / "evaluation" / "results" / batch
    store = Store(get_settings().database_path)
    recs = [json.loads(x) for x in (out / "scored.jsonl").read_text("utf-8").splitlines() if x.strip()]
    S = [score(r, store.detail(r["run_id"])) for r in recs]
    (out / "scores.json").write_text(json.dumps(S, indent=1, default=str), "utf-8")
    L = ["### Summary by model, mode and target", "",
         "Medians across repetitions. Defects are found/known across runs; `n/a` means no answer key.", "",
         "| Model | Mode | Target | Runs | Completed | Goal met | Reqs tested (union) | Reqs verified (union) | Defects | False conf. | Unfinished | Elapsed s | Calls | US$ total | Trunc. | Retries |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    groups = defaultdict(list)
    for s in S:
        groups[(s["model"], s["mode"], s["target"])].append(s)
    for (m, mo, t), g in groups.items():
        keyed = g[0]["defects_known"] is not None
        dk = sum(s["defects_known"] for s in g) if keyed else 0
        L.append(f"| {SHORT[m]} | {MODE[mo]} | {t} | {len(g)} | {sum(s['status'] == 'completed' for s in g)} | "
                 f"{sum(s['goal_met'] for s in g)}/{len(g)} | {','.join(sorted({r for s in g for r in s['reqs_tested']})) or '–'} | "
                 f"{','.join(sorted({r for s in g for r in s['reqs_verified']})) or '–'} | "
                 + (f"{sum(len(s['defects_found']) for s in g)}/{dk} | {sum(len(s['false_confirmations']) for s in g)}" if keyed else "n/a | unknown")
                 + f" | {sum(s['unfinished'] for s in g)} | {med(g, 'wall_s'):.0f} | {med(g, 'calls'):.0f} | {sum(s['cost'] for s in g):.4f} | "
                 f"{sum(s['truncated'] for s in g)} | {sum(s['retries'] for s in g)} |")
    L += ["", "### Model and mode rollup", "",
          "| Model | Mode | Runs | Failed | Unusable | Goal met | Keyed defects | False conf. (keyed) | Elapsed s (median) | Model latency ms p50/p95 (median of runs) | Browser ms p50/p95 | Input tokens | Output tokens | US$ | Trunc. | Retries | Failed calls |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    roll = defaultdict(list)
    for s in S:
        roll[(s["model"], s["mode"])].append(s)
    for (m, mo), g in roll.items():
        k = [s for s in g if s["defects_known"] is not None]
        L.append(f"| {SHORT[m]} | {MODE[mo]} | {len(g)} | {sum(s['status'] == 'failed' for s in g)} | {sum(s['unusable'] for s in g)} | "
                 f"{sum(s['goal_met'] for s in g)}/{len(g)} | {sum(len(s['defects_found']) for s in k)}/{sum(s['defects_known'] for s in k)} | "
                 f"{sum(len(s['false_confirmations']) for s in k)} | {med(g, 'wall_s'):.0f} | {med(g, 'model_p50_ms'):.0f}/{med(g, 'model_p95_ms'):.0f} | "
                 f"{med(g, 'browser_p50_ms'):.0f}/{med(g, 'browser_p95_ms'):.0f} | {sum(s['in_tokens'] for s in g):,} | {sum(s['out_tokens'] for s in g):,} | "
                 f"{sum(s['cost'] for s in g):.4f} | {sum(s['truncated'] for s in g)} | {sum(s['retries'] for s in g)} | {sum(s['failed_calls'] for s in g)} |")
    L += ["", "### Individual runs", "",
          "| Model | Mode | Target | Rep | Run | Status | Goal | Tested | Verified | Defects | False | Unfin. | s | Calls | In | Out | US$ | Model p50/p95 ms | Browser p50/p95 ms | Trunc. | Retries |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in S:
        d = "n/a" if s["defects_known"] is None else f"{len(s['defects_found'])}/{s['defects_known']}"
        fc = "unknown" if s["false_confirmations"] is None else len(s["false_confirmations"])
        L.append(f"| {SHORT[s['model']]} | {MODE[s['mode']]} | {s['target']} | {s['rep']} | `{s['run_id']}` | {s['status']} | {'yes' if s['goal_met'] else 'no'} | "
                 f"{','.join(s['reqs_tested']) or '–'} | {','.join(s['reqs_verified']) or '–'} | {d} | {fc} | {s['unfinished']} | {s['wall_s']:.0f} | {s['calls']} | "
                 f"{s['in_tokens']} | {s['out_tokens']} | {s['cost']:.4f} | {s['model_p50_ms']}/{s['model_p95_ms']} | {s['browser_p50_ms']}/{s['browser_p95_ms']} | {s['truncated']} | {s['retries']} |")
    (out / "tables.md").write_text("\n".join(L) + "\n", "utf-8")


if __name__ == "__main__":
    main(sys.argv[1])
