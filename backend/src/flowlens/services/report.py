"""Review report built only from a run's saved records, rendered as Markdown or HTML.

Written for a non-technical reader: summary and actionable findings first, unchecked areas
and incomplete work next, technical diagnostics last (and folded away). Nothing here calls a
model or the target website; every statement comes from stored records. Verification is
labelled by who checked it: an independent verifier in fresh browser sessions, the same agent
checking itself (single-agent baseline), or only the agent that reported it.
"""

from __future__ import annotations

import html
import re
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from flowlens.agents.common import requirement_refs
from flowlens.models.contracts import Finding, RunDetail
from flowlens.verification import persistence

WORKFLOW = {
    "single_explorer": "One explorer agent (no separate testing or verification)",
    "explore_test_verify": "Explorer, then input tester, then independent verifier",
    "queue_review": "Shared queue: two explorers, an input tester and an independent verifier",
    "single_agent": "Single agent that explores, tests and checks its own findings (comparison baseline)",
    "reverify": "Re-check of an earlier finding against another build",
}
STATUS = {
    "completed": ("Finished", "The review ran to its end. Finished does not mean the website passed."),
    "partial": ("Incomplete", "The review stopped at a time, step or budget limit before everything was checked."),
    "failed": ("Stopped by an error", "The review stopped because of an error, so later checks did not run."),
    "interrupted": ("Interrupted", "The review was interrupted (for example, the server restarted) before it finished."),
    "running": ("Still running", "This report is a snapshot of a review that has not finished."),
    "queued": ("Not started", "The review has not started yet."),
}
INCONCLUSIVE_WHY = {
    "setup": "the re-check could not recreate the starting page",
    "expectation": "no supplied requirement says what should happen here",
    "application": "the website errored while the steps were repeated",
    "verifier": "the checker could not form a valid check",
}
TASK_WHY = {
    "unfinished": "not started because a limit was reached or the review ended",
    "skipped": "deliberately skipped as a near-duplicate of something already covered",
    "deferred": "recorded for later; this workflow does not explore them",
    "blocked": "blocked because something it depended on failed",
    "failed": "attempted but failed",
    "ready": "still waiting in the queue when the review ended",
    "claimed": "in progress when the review ended",
}
TASK_KIND = {"explore": "page(s) to explore", "input_test": "form(s) to test", "verify": "finding(s) to re-check"}


def _clip(t: str | None, n: int = 240) -> str:
    t = " ".join((t or "").split())
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def plain_step(step: dict[str, Any]) -> str:
    """One reproduction step in plain words."""
    t = step.get("type")
    c = step.get("control") or {}
    name = c.get("name") or "the control"
    where = f" in the “{c['context']}” row" if c.get("context") else ""
    if t == "navigate":
        return f"Open the page {step.get('path') or '/'}"
    if t == "reload":
        return "Reload the page"
    if t == "fill":
        v = step.get("value")
        return f"Leave “{name}” empty" if v == "" else f"Type “{v}” into “{name}”"
    if t == "press":
        return f"Press {step.get('key') or 'Enter'} in “{name}”"
    if t == "check":
        return f"{'Tick' if step.get('checked', True) is not False else 'Untick'} “{name}”{where}"
    if t == "click":
        return f"Click “{name}”{where}"
    return str(t)


_TARGET = re.compile(r"^(?P<role>[\w-]+) '(?P<name>.*?)'(?: in '(?P<ctx>.*)')?$")


def plain_action(action: dict[str, Any], target: str | None) -> str:
    """A recorded action in plain words, using the target's recorded role and name."""
    m = _TARGET.match(target or "")
    control = {"role": m["role"], "name": m["name"], "context": m["ctx"]} if m else {"name": None}
    t = action.get("type")
    if t == "navigate":
        u = urlsplit(action.get("url") or target or "")
        return plain_step({"type": "navigate", "path": (u.path or "/") + (f"#{u.fragment}" if u.fragment else "")})
    return plain_step({**action, "control": control})


_IDS = ((re.compile(r"\bfnd_[0-9a-f]{6,}\b"), "an earlier finding"), (re.compile(r"\brun_[0-9a-f]{6,}\b"), "an earlier review"))


def no_ids(t: str) -> str:
    """Stored goals and titles of re-check runs name record ids; the main report says what they are."""
    for rx, words in _IDS:
        t = rx.sub(words, t)
    return t


def plain_stop(status: str, reason: str | None) -> str:
    """Why a run stopped, in plain words (the raw reason is kept in Diagnostics)."""
    t = (reason or "").lower()
    if status == "failed":
        return "an internal error in FlowLens stopped it (details under Diagnostics)"
    if status == "interrupted":
        return "it was interrupted, for example by a server restart"
    for key, text in (("share", "the part of the budget set aside for exploring was used up"),
                      ("step limit", "it reached its limit on browser steps"), ("time limit", "it reached its time limit"),
                      ("cost", "it reached its cost limit"), ("model call", "it reached its limit on model calls"),
                      ("budget", "it reached its budget"), ("state-count", "it reached its limit on pages")):
        if key in t:
            return text
    return "it stopped before finishing (details under Diagnostics)"


class ReportBuilder:
    def __init__(self, d: RunDetail, artifacts_root: Path, base_url: str):
        self.d = d
        self.root = artifacts_root
        self.base = base_url.rstrip("/")
        self.evidence = {e.id: e for e in d.evidence}
        self.actions = {a.id: a for a in d.actions}
        self.shot_action = {a.screenshot_artifact_id: a for a in d.actions if a.screenshot_artifact_id}
        self.verifs = {v.id: v for v in d.verifications}
        self.reqs = {r.id: r for r in requirement_refs(d.run.requirements)}

    # --- evidence -------------------------------------------------------------

    def _link(self, art_id: str, label: str) -> dict:
        ev = self.evidence.get(art_id)
        present = bool(ev) and (self.root / ev.path).is_file()
        return {"label": label, "href": f"/api/artifacts/{art_id}", "abs": f"{self.base}/api/artifacts/{art_id}",
                "present": present, "id": art_id, "kind": ev.kind if ev else "missing"}

    def _shot_label(self, art_id: str) -> str:
        a = self.shot_action.get(art_id)
        if a is None:
            return "Screenshot"
        who = {"explorer-a": "Explorer A", "explorer-b": "Explorer B", "input-tester": "input tester",
               "verifier": "verifier", "single-agent": "single agent"}.get(a.agent_id or "", a.agent_id or "agent")
        failed = "" if a.ok else " (this action failed)"
        return f"After “{_clip(plain_action(a.action, a.target_description), 90)}”{failed}, {who}"

    def evidence_for(self, refs: list[str]) -> tuple[list[dict], list[dict]]:
        """(screenshots for the main report, other records for the technical section)."""
        shots, other = [], []
        for ref in refs:
            if ref in self.actions:  # explorer findings reference actions; link their screenshots
                a = self.actions[ref]
                if a.screenshot_artifact_id:
                    shots.append(self._link(a.screenshot_artifact_id, self._shot_label(a.screenshot_artifact_id)))
                if a.observation_artifact_id:
                    other.append(self._link(a.observation_artifact_id, f"Page record, step {a.step}"))
                continue
            ev = self.evidence.get(ref)
            if ev is None:
                other.append(self._link(ref, "Record"))
            elif ev.kind == "screenshot":
                shots.append(self._link(ref, self._shot_label(ref)))
            else:
                other.append(self._link(ref, {"observation": "Page record", "model_call": "Model call record",
                                              "action_log": "Action log", "handoff": "Handoff record"}[ev.kind]))
        return shots, other

    # --- findings -------------------------------------------------------------

    def verification(self, f: Finding) -> dict:
        attempts = [self.verifs[i] for i in f.verification_ids if i in self.verifs]
        n = len(attempts)
        st = f.verification_status.value
        indep = f.verification_independence != "self"
        who = "an independent verifier" if indep else "the same agent that reported it (self-check, not independent)"
        if f.kind == "persistence_check":
            s = persistence.summarise(f.same_context_check)
            label = {"passed": "Explorer claim; same-session check matched",
                     "failed": "Explorer claim; same-session check did not match",
                     "not_evaluated": "Explorer claim; not evaluated"}.get(s["outcome"] if s else "", "Explorer claim; not checked")
            return {"status": "unverified", "label": label, "tone": "amber",
                    "independence": "none",
                    "text": ("Only the explorer observed this. FlowLens compared its claimed values in the same browser session, "
                             "which is not an independent re-check. " + (s["headline"] + "." if s else "No values were checked.")),
                    "check": s}
        if st == "confirmed":
            return {"status": st, "label": "Confirmed" if indep else "Confirmed by self-check only", "tone": "red" if indep else "amber",
                    "independence": "independent" if indep else "self",
                    "text": f"Re-checked by {who}: repeated {n} time(s) in fresh browser sessions and the problem appeared each time. "
                            + ("" if indep else "Treat as likely but not independently confirmed.")}
        if st == "not_reproduced":
            return {"status": st, "label": "Not reproduced", "tone": "green", "independence": "independent" if indep else "self",
                    "text": f"Re-checked by {who} in {n} fresh browser session(s); the problem did not appear."}
        if st == "inconclusive":
            why = next((INCONCLUSIVE_WHY[a.failure_class] for a in attempts if a.failure_class in INCONCLUSIVE_WHY), None)
            return {"status": st, "label": "Inconclusive", "tone": "slate", "independence": "independent" if indep else "self",
                    "text": f"Re-checked by {who}, but no verdict was possible" + (f": {why}." if why else ".")
                            + (" A person should decide whether this matters." if (why or "").startswith("no supplied") else "")}
        stopped = self.d.run.status in ("partial", "failed", "interrupted")
        return {"status": "unverified", "label": "Unverified", "tone": "amber", "independence": "none",
                "text": "Only the agent that reported it has seen this; it was not re-checked"
                        + (" because the review stopped first." if stopped else ".")}

    def finding(self, f: Finding) -> dict:
        req = self.reqs.get(f.requirement_ref or "")
        steps = []
        if f.reproduction and f.reproduction.direct_path:
            steps.append(f"Open the page {f.reproduction.direct_path} in a new browser session")
        elif f.kind != "persistence_check":
            steps.append(f"Open {self.d.run.target_url} in a new browser session")
        if f.reproduction_steps:
            steps += [plain_step(s.model_dump()) for s in f.reproduction_steps]
        elif f.kind == "persistence_check":
            # Explorer findings store raw actions (element ids); describe the recorded actions instead.
            acts = sorted((a for a in self.d.actions if a.agent_id in (None, f.reported_by) and a.phase in (None, "explore")),
                          key=lambda a: a.step)
            steps += [plain_action(a.action, a.target_description) for a in acts if a.ok and a.action.get("type") != "inspect"]
        if f.check_path:
            steps.append(f"Open {f.check_path} to see the result")
        shots, other = self.evidence_for(f.evidence_refs)
        for vid in f.verification_ids:
            v = self.verifs.get(vid)
            if v:
                s2, o2 = self.evidence_for(v.evidence_refs)
                shots += [{**x, "label": f"Re-check {v.replay_index + 1}: {x['label']}"} for x in s2]
                other += o2
        kind = {"defect_candidate": "Possible problem", "review_observation": "Observation (no requirement covers this)",
                "persistence_check": "Explorer observation"}[f.kind]
        attempts = [self.verifs[i] for i in f.verification_ids if i in self.verifs]
        return {
            # Explorer persistence findings carry a generic stored description; the report states what was claimed.
            "title": ("Does entered content stay after a reload? (explorer's claim: "
                      + {"retained": "yes", "not_retained": "no", "unknown": "could not tell"}[f.agent_claim or "unknown"] + ")")
                     if f.kind == "persistence_check" else _clip(no_ids(f.description), 140),
            "kind": kind, "requirement": (f"{req.id}: {req.text}" if req else None),
            "expected": f.expected, "observed": f.observed, "inputs": f.inputs,
            "verification": self.verification(f), "steps": steps, "screenshots": shots,
            "technical": {
                "Finding id": f.id, "Reported by": f.reported_by, "Kind": f.kind,
                "Verification status (stored)": f.verification_status.value,
                "Verified by": f.verified_by or "—", "Independence": f.verification_independence or ("—" if not f.verified_by else "independent"),
                "Stored reason": _clip(f.verification_reason, 600) or "—",
                "Re-check attempts": "; ".join(
                    f"#{a.replay_index + 1} {a.outcome} (setup {a.setup_strategy or 'failed'}"
                    f"{', ' + a.failure_class if a.failure_class else ''}, context {a.context_id or '—'}): {_clip(a.reason, 200)}"
                    for a in attempts) or "none",
                "Other records": other,
            },
        }

    # --- whole report ---------------------------------------------------------

    def build(self) -> dict:
        d, r = self.d, self.d.run
        order = {"confirmed": 0, "unverified": 1, "inconclusive": 2, "not_reproduced": 3}
        fs = sorted(d.findings, key=lambda f: (f.kind == "persistence_check", f.kind == "review_observation",
                                               order[f.verification_status.value]))
        findings = [self.finding(f) for f in fs]
        groups = {
            "act": [x for x in findings if x["verification"]["status"] == "confirmed"],
            "decide": [x for x in findings if x["verification"]["status"] in ("unverified", "inconclusive")],
            "cleared": [x for x in findings if x["verification"]["status"] == "not_reproduced"],
        }
        status_label, status_text = STATUS.get(r.status.value, (r.status.value, ""))
        incomplete = r.status.value in ("partial", "failed", "interrupted", "running", "queued")

        # Requirements: what was exercised.
        tc_by_req = Counter(tc.expectation_source for tc in d.test_cases if tc.status == "executed")
        f_by_req = Counter(f.requirement_ref for f in d.findings if f.requirement_ref)
        reqs = []
        for q in self.reqs.values():
            n_tc, n_f = tc_by_req.get(q.id, 0), f_by_req.get(q.id, 0)
            reqs.append({"id": q.id, "text": q.text,
                         "coverage": (f"{n_tc} test case(s) run" + (f", {n_f} finding(s)" if n_f else ""))
                         if n_tc else (f"{n_f} finding(s), no test cases" if n_f else "Not checked in this run")})

        # Unchecked areas and incomplete work.
        tested_forms = {tc.form_id for tc in d.test_cases if tc.status == "executed"}
        untested = [f for f in d.forms if f.id not in tested_forms]
        gaps: list[str] = []
        if incomplete:
            gaps.append(f"The review did not finish: {plain_stop(r.status.value, r.stop_reason)}. "
                        "Having no findings for an area does not mean that area works.")
        if r.mode == "single_explorer":
            gaps.append("No input testing or independent verification ran in this workflow; anything reported is an unverified observation.")
        for f in untested:
            heading = f.headings[0] if f.headings else f.route
            gaps.append(f"Form found but not tested: “{_clip(heading, 80)}” at {f.route}.")
        tc_failed = [tc for tc in d.test_cases if tc.status in ("setup_failed", "execution_failed")]
        if tc_failed:
            gaps.append(f"{len(tc_failed)} planned test case(s) could not be run (the starting page could not be recreated or the run failed).")
        open_tasks = Counter((t.type, t.status.value) for t in d.tasks if t.status.value not in ("done",))
        for (ty, st), n in sorted(open_tasks.items()):
            gaps.append(f"{n} {TASK_KIND.get(ty, ty)} {TASK_WHY.get(st, st)}.")
        not_checked = [q for q in reqs if q["coverage"] == "Not checked in this run"]
        if not_checked:
            gaps.append("Requirements not checked in this run: " + ", ".join(q["id"] for q in not_checked) + ".")
        if r.target_profile == "website":
            gaps.append("Public website: each agent used a fresh browser, but the site's own server data is shared "
                        "and was not isolated between agents, runs or other users.")

        # Summary.
        c = Counter(x["verification"]["status"] for x in findings)
        n_self = sum(1 for x in findings if x["verification"]["independence"] == "self")
        lines = []
        if groups["act"]:
            n_act_self = sum(1 for x in groups["act"] if x["verification"]["independence"] == "self")
            lines.append(f"{len(groups['act'])} confirmed problem(s) to fix"
                         + (f" ({n_act_self} confirmed only by self-check)" if n_act_self else "")
                         + ": " + "; ".join(x["title"] for x in groups["act"]) + ".")
        else:
            lines.append("No confirmed problems." + (" The review was incomplete, so this is not a clean result." if incomplete else ""))
        if groups["decide"]:
            lines.append(f"{len(groups['decide'])} item(s) need a decision or a further check "
                         f"({c.get('unverified', 0)} unverified, {c.get('inconclusive', 0)} inconclusive).")
        if groups["cleared"]:
            lines.append(f"{len(groups['cleared'])} suspected problem(s) were re-checked and did not reproduce.")
        if n_self:
            lines.append(f"{n_self} outcome(s) are self-checks by the same agent, not independent verification.")
        lines.append(f"Review status: {status_label}. {status_text}")

        any_missing = any(not s["present"] for x in findings for s in x["screenshots"])
        u = r.usage
        return {
            "title": "Website review report", "goal": no_ids(r.goal), "target": r.target_url,
            "date": r.created_at.strftime("%d %b %Y, %H:%M UTC"), "workflow": WORKFLOW.get(r.mode, r.mode),
            "recorded": r.imported_from,
            "status_label": status_label, "status_text": status_text, "incomplete": incomplete,
            "summary": lines, "groups": groups, "requirements": reqs, "gaps": gaps,
            "evidence_note": (
                "Evidence links open screenshots saved by FlowLens. They work while the FlowLens server that ran this "
                f"review is running (links point to {self.base}) and its artifacts folder is kept. The artifacts folder "
                "is not shared or version-controlled, so links will not open for someone without access to that server."
                + (" Some files are missing from the artifacts folder and are marked as missing." if any_missing else "")),
            "diagnostics": {
                "Imported from": r.imported_from or "— (run by this installation)",
                "Run id": r.id, "Goal as stored": r.goal, "Workflow (internal name)": r.mode, "Model": r.model,
                "Status (internal)": r.status.value, "Stop reason (raw)": r.stop_reason or "—",
                "Started": r.created_at.isoformat(), "Finished": r.finished_at.isoformat() if r.finished_at else "—",
                "Model calls": f"{u.model_calls} of {r.limits.max_model_calls} allowed "
                               f"(explore {u.exploration_calls}, testing {u.testing_calls}, verification {u.verification_calls})",
                "Tokens": f"{u.total_tokens:,} ({u.prompt_tokens:,} prompt, {u.completion_tokens:,} completion)",
                "Reported cost": f"US${u.reported_cost_usd:.4f} of a US${r.limits.max_cost_usd:.2f} limit"
                                 + (f"; {u.calls_without_cost} call(s) reported no cost" if u.calls_without_cost else ""),
                "Truncated replies": str(u.truncated_calls),
                "Limits": f"{r.limits.max_steps} steps, {r.limits.max_model_calls} calls, {r.limits.max_output_tokens} output tokens per call",
                "Target profile": "Approved public website" if r.target_profile == "website" else "Configured fixture with test workspaces",
                "Allowed origins": ", ".join(r.scope_origins) or "configured origins (recorded before per-run scope existed)",
                "Build label (evaluation only)": r.target_build or "—",
                "Provenance": ", ".join(k for k, v in r.provenance.model_dump().items() if v) or "—",
                "Injected fault": (f"{r.fault_injection.worker} stalls {r.fault_injection.stall_s}s" if r.fault_injection else "none"),
                "Records": f"{len(d.states)} pages, {len(d.transitions)} moves, {len(d.actions)} actions, {len(d.forms)} forms, "
                           f"{len(d.test_cases)} test cases, {len(d.verifications)} re-check attempts, {len(d.evidence)} evidence files",
            },
        }


def build_report(d: RunDetail, artifacts_root: Path, base_url: str) -> dict:
    return ReportBuilder(d, artifacts_root, base_url).build()


# --- Markdown ----------------------------------------------------------------


def _md(t: Any) -> str:
    return str(t).replace("|", "\\|").replace("\n", " ")


def to_markdown(rep: dict) -> str:
    out = [f"# {rep['title']}", "",
           f"**Goal:** {_md(rep['goal'])}  ", f"**Website:** {rep['target']}  ",
           f"**Reviewed:** {rep['date']}  ", f"**How it was reviewed:** {rep['workflow']}  ",
           f"**Status:** {rep['status_label']}. {rep['status_text']}", ""]
    if rep.get("recorded"):
        out += [f"> **Recorded result.** Loaded from {rep['recorded']}; it was not run by this installation.", ""]
    out += ["## Summary", ""]
    out += [f"- {_md(x)}" for x in rep["summary"]] + [""]

    def finding(x: dict, n: int) -> list[str]:
        v = x["verification"]
        lines = [f"### {n}. {_md(x['title'])}", "", f"**Status: {v['label']}.** {v['text']}  ", f"*{x['kind']}*", ""]
        if x["requirement"]:
            lines += [f"**Requirement:** {_md(x['requirement'])}", ""]
        lines += [f"**Expected:** {_md(x['expected'])}", "", f"**Observed:** {_md(x['observed'])}", ""]
        if v.get("check") and v["check"]["rows"]:
            lines += ["| Value the explorer checked | Expected | Result |", "|---|---|---|"]
            for row in v["check"]["rows"]:
                res = {"matched": "Matched", "mismatch": "Did not match", "not_evaluated": "Not evaluated"}[row["status"]]
                lines.append(f"| {_md(row['field'])} | {_md(row['expected'])} | {res} ({_md(row['basis'])}) |")
            lines.append("")
        if x["steps"]:
            lines += ["**How to reproduce:**", ""] + [f"{i}. {_md(s)}" for i, s in enumerate(x["steps"], 1)] + [""]
        if x["screenshots"]:
            lines += ["**Evidence:**", ""]
            lines += [f"- [{_md(s['label'])}]({s['abs']})" + ("" if s["present"] else " (file missing)") for s in x["screenshots"]]
            lines.append("")
        lines += ["<details><summary>Technical details</summary>", ""]
        for k, val in x["technical"].items():
            if k == "Other records":
                val = ", ".join(f"[{o['label']}]({o['abs']})" for o in val) or "none"
            lines.append(f"- **{k}:** {_md(val)}")
        lines += ["", "</details>", ""]
        return lines

    n = 0
    for key, title, empty in (("act", "Problems to fix (confirmed)", "No confirmed problems."),
                              ("decide", "Needs a decision or a further check", "Nothing in this group."),
                              ("cleared", "Re-checked and not reproduced", None)):
        items = rep["groups"][key]
        if not items and empty is None:
            continue
        out += [f"## {title}", ""]
        if not items:
            out += [empty, ""]
        for x in items:
            n += 1
            out += finding(x, n)
    out += ["## What was not checked", ""]
    out += [f"- {_md(g)}" for g in rep["gaps"]] or ["- Nothing recorded as unchecked."]
    out += [""]
    if rep["requirements"]:
        out += ["## Requirements", "", "| Requirement | Coverage in this run |", "|---|---|"]
        out += [f"| {_md(q['id'])}: {_md(q['text'])} | {_md(q['coverage'])} |" for q in rep["requirements"]]
        out += [""]
    out += ["## How findings were checked", "",
            "- **Confirmed / Not reproduced / Inconclusive** (independent): a separate verifier agent repeated the steps in "
            "fresh browser sessions, and code, not the agent, decided the result.",
            "- **Self-check**: the same agent that reported the finding checked it (single-agent baseline). Code still "
            "evaluated the result, but it is not independent.",
            "- **Unverified / Explorer claim**: only the reporting agent saw it. A same-session check compares the explorer's "
            "own values in its own browser; checkbox and on/off states are shown as *not evaluated*.", "",
            "## About evidence links", "", rep["evidence_note"], "",
            "## Diagnostics", "", "<details><summary>Technical diagnostics</summary>", ""]
    out += [f"- **{k}:** {_md(v)}" for k, v in rep["diagnostics"].items()]
    out += ["", "</details>", ""]
    return "\n".join(out)


# --- HTML --------------------------------------------------------------------

_CSS = """
:root{--ink:#0f172a;--muted:#475569;--line:#e2e8f0;--soft:#f8fafc}
*{box-sizing:border-box}body{margin:0;font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--ink);background:#f1f5f9}
main{max-width:860px;margin:0 auto;background:#fff;padding:40px 48px 56px;min-height:100vh}
h1{font-size:26px;margin:0 0 4px}h2{font-size:19px;margin:36px 0 10px;padding-top:8px;border-top:1px solid var(--line)}
h3{font-size:16px;margin:0 0 6px}a{color:#1d4ed8}
.meta{display:grid;grid-template-columns:150px 1fr;gap:4px 14px;margin:16px 0;color:var(--muted)}.meta dt{font-weight:600;color:var(--ink)}
.meta dd{margin:0;overflow-wrap:anywhere}
.toolbar{display:flex;gap:8px;margin:0 0 20px}.toolbar a,.toolbar button{font:inherit;font-size:13px;padding:6px 12px;border:1px solid #cbd5e1;border-radius:6px;background:#fff;color:var(--ink);text-decoration:none;cursor:pointer}
.summary{background:var(--soft);border:1px solid var(--line);border-radius:10px;padding:14px 18px}.summary ul{margin:0;padding-left:20px}
.banner{border-left:4px solid #d97706;background:#fffbeb;padding:10px 14px;border-radius:6px;margin:12px 0}
.card{border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:14px 0;break-inside:avoid}
.pill{display:inline-block;font-size:12px;font-weight:600;padding:2px 9px;border-radius:999px;margin-right:6px}
.red{background:#fee2e2;color:#991b1b}.amber{background:#fef3c7;color:#92400e}.green{background:#dcfce7;color:#166534}.slate{background:#e2e8f0;color:#334155}
.kind{font-size:12px;color:var(--muted)}.ev{display:grid;grid-template-columns:1fr 1fr;gap:6px 18px;font-size:14px}
.cmp{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:10px 0}.cmp div{background:var(--soft);border-radius:8px;padding:8px 12px}
.cmp b{display:block;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
table{border-collapse:collapse;width:100%;font-size:14px;margin:8px 0}th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{font-size:12px;color:var(--muted);font-weight:600}
details{margin-top:10px;border:1px dashed #cbd5e1;border-radius:8px;padding:6px 12px;background:#fcfcfd}summary{cursor:pointer;font-size:13px;font-weight:600;color:var(--muted)}
details dl{display:grid;grid-template-columns:200px 1fr;gap:4px 12px;font-size:13px}details dt{color:var(--muted)}details dd{margin:0;overflow-wrap:anywhere;font-family:ui-monospace,Consolas,monospace;font-size:12px}
.missing{color:#b91c1c;font-size:12px}.note{color:var(--muted);font-size:13px}
@media (max-width:640px){main{padding:24px 18px}.meta,.cmp,.ev,details dl{grid-template-columns:1fr}}
@media print{body{background:#fff}main{padding:0;max-width:none}.toolbar{display:none}a{color:inherit;text-decoration:none}
 .card,.summary{border-color:#94a3b8}h2{break-after:avoid}details{border:none;padding:0}details:not([open]) > :not(summary){display:none}
 details:not([open]) summary::after{content:" (open before printing to include)";font-weight:400}}
"""


def _e(t: Any) -> str:
    return html.escape(str(t if t is not None else ""))


def to_html(rep: dict, md_href: str) -> str:
    def finding(x: dict, n: int) -> str:
        v = x["verification"]
        parts = [f'<article class="card"><h3>{n}. {_e(x["title"])}</h3>',
                 f'<p><span class="pill {v["tone"]}">{_e(v["label"])}</span><span class="kind">{_e(x["kind"])}</span></p>',
                 f'<p>{_e(v["text"])}</p>']
        if x["requirement"]:
            parts.append(f'<p><b>Requirement:</b> {_e(x["requirement"])}</p>')
        parts.append(f'<div class="cmp"><div><b>Expected</b>{_e(x["expected"])}</div><div><b>Observed</b>{_e(x["observed"])}</div></div>')
        if v.get("check") and v["check"]["rows"]:
            rows = "".join(
                f'<tr><td>{_e(r["field"])}</td><td>{_e(r["expected"])}</td><td>'
                f'{ {"matched": "Matched", "mismatch": "Did not match", "not_evaluated": "Not evaluated"}[r["status"]] }'
                f' <span class="note">({_e(r["basis"])})</span></td></tr>' for r in v["check"]["rows"])
            parts.append(f'<table><thead><tr><th>Value the explorer checked</th><th>Expected</th><th>Result</th></tr></thead>'
                         f'<tbody>{rows}</tbody></table>')
        if x["steps"]:
            parts.append("<p><b>How to reproduce</b></p><ol>" + "".join(f"<li>{_e(s)}</li>" for s in x["steps"]) + "</ol>")
        if x["screenshots"]:
            parts.append("<p><b>Evidence</b></p><ul>" + "".join(
                f'<li><a href="{_e(s["href"])}" target="_blank" rel="noopener">{_e(s["label"])}</a>'
                + ("" if s["present"] else ' <span class="missing">(file missing)</span>') + "</li>" for s in x["screenshots"]) + "</ul>")
        tech = []
        for k, val in x["technical"].items():
            if k == "Other records":
                val_html = ", ".join(f'<a href="{_e(o["href"])}" target="_blank" rel="noopener">{_e(o["label"])}</a>' for o in val) or "none"
            else:
                val_html = _e(val)
            tech.append(f"<dt>{_e(k)}</dt><dd>{val_html}</dd>")
        parts.append(f'<details><summary>Technical details</summary><dl>{"".join(tech)}</dl></details></article>')
        return "".join(parts)

    body = [f'<main><nav class="toolbar"><a href="{_e(md_href)}" download>Download Markdown</a>'
            '<button type="button" onclick="window.print()">Print</button></nav>',
            f'<h1>{_e(rep["title"])}</h1>',
            '<dl class="meta">' + "".join(f"<dt>{k}</dt><dd>{_e(v)}</dd>" for k, v in (
                ("Goal", rep["goal"]), ("Website", rep["target"]), ("Reviewed", rep["date"]),
                ("How it was reviewed", rep["workflow"]), ("Status", f'{rep["status_label"]}. {rep["status_text"]}'))) + "</dl>"]
    if rep.get("recorded"):
        body.append(f'<div class="banner"><b>Recorded result.</b> Loaded from {_e(rep["recorded"])}; it was not run by this installation.</div>')
    if rep["incomplete"]:
        body.append('<div class="banner"><b>Incomplete review.</b> Some areas were not checked; see “What was not checked”.</div>')
    body.append('<h2>Summary</h2><div class="summary"><ul>' + "".join(f"<li>{_e(s)}</li>" for s in rep["summary"]) + "</ul></div>")
    n = 0
    for key, title, empty in (("act", "Problems to fix (confirmed)", "No confirmed problems."),
                              ("decide", "Needs a decision or a further check", "Nothing in this group."),
                              ("cleared", "Re-checked and not reproduced", None)):
        items = rep["groups"][key]
        if not items and empty is None:
            continue
        body.append(f"<h2>{title}</h2>")
        if not items:
            body.append(f'<p class="note">{empty}</p>')
        for x in items:
            n += 1
            body.append(finding(x, n))
    body.append("<h2>What was not checked</h2><ul>" + ("".join(f"<li>{_e(g)}</li>" for g in rep["gaps"])
                                                       or "<li>Nothing recorded as unchecked.</li>") + "</ul>")
    if rep["requirements"]:
        body.append("<h2>Requirements</h2><table><thead><tr><th>Requirement</th><th>Coverage in this run</th></tr></thead><tbody>"
                    + "".join(f'<tr><td><b>{_e(q["id"])}</b> {_e(q["text"])}</td><td>{_e(q["coverage"])}</td></tr>'
                              for q in rep["requirements"]) + "</tbody></table>")
    body.append("<h2>How findings were checked</h2><ul>"
                "<li><b>Confirmed, Not reproduced, Inconclusive</b>: a separate verifier agent repeated the steps in fresh browser "
                "sessions, and code, not the agent, decided the result (independent).</li>"
                "<li><b>Self-check</b>: the agent that reported the finding checked it itself (single-agent baseline). Code still "
                "evaluated the result, but it is not independent.</li>"
                "<li><b>Unverified / Explorer claim</b>: only the reporting agent saw it. A same-session check compares the "
                "explorer's own values in its own browser; checkbox and on/off states are shown as <i>not evaluated</i>.</li></ul>")
    body.append(f'<h2>About evidence links</h2><p class="note">{_e(rep["evidence_note"])}</p>')
    body.append('<h2>Diagnostics</h2><details><summary>Technical diagnostics</summary><dl>'
                + "".join(f"<dt>{_e(k)}</dt><dd>{_e(v)}</dd>" for k, v in rep["diagnostics"].items()) + "</dl></details></main>")
    host = urlsplit(rep["target"]).netloc
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>Review report: {_e(host)}</title><style>{_CSS}</style></head><body>{''.join(body)}</body></html>")
