r"""Scripted before/after check of explorer repetition on Ticket Desk. No model calls, no spend.

Two scripted explorers imitate the saved runs: "booker" tries to book in every task (run_816054f4e335) and
"navigator" keeps walking the site (run_3f84fb9bdc8b). Point PYTHONPATH at another checkout's backend/src
to measure older code.

Usage (repo root): backend\.venv\Scripts\python scripts\repetition_check.py OUT_DIR [ticket-desk|leave-desk]
"""

import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if not os.environ.get("PYTHONPATH"):
    sys.path.insert(0, str(ROOT / "backend" / "src"))

from flowlens.config import Settings  # noqa: E402
from flowlens.models.contracts import Provenance, Run, RunLimits  # noqa: E402
from flowlens.orchestration.queue_review import QueueReviewRun  # noqa: E402
from flowlens.services.llm import ScriptedClient  # noqa: E402
from flowlens.storage.db import Store  # noqa: E402

PORT = 5399
SITE = sys.argv[2] if len(sys.argv) > 2 else "ticket-desk"
PLAN = {"reasoning": "scripted", "cases": [{"label": "Valid", "submit": "Book tickets", "expected": "booked", "inputs": {
    "Name": "John Doe", "Email": "john@example.com", "Tickets": "2"}}, {"label": "Zero", "submit": "Book tickets",
    "expected": "rejected", "inputs": {"Name": "John Doe", "Email": "john@example.com", "Tickets": "0"}}]}
ACTION_PLAN = {"reasoning": "scripted", "cases": [{"label": "Confirm", "submit": "Yes, cancel booking", "expected": "cancelled",
                                                   "inputs": {}}]}


def el(page, role, name):
    m = re.search(rf'(e\d+) {role} "{name}', page)
    return m.group(1) if m else None


def explorer(style, page, user):
    hist = user.split("Your previous actions:")[1].split("Current page:")[0]
    if style == "booker" and "refused" not in hist:
        for label, value in (("Name", "Ryan"), ("Email", "ryan@example.com"), ("Tickets", "2")):
            e = re.search(rf'(e\d+) textbox "{label}"(?: type=number)? value=""', page)
            if e:
                return {"type": "fill", "element_id": e.group(1), "value": value}
        if el(page, "button", "Book tickets"):
            return {"type": "click", "element_id": el(page, "button", "Book tickets")}
    for name in ("Cancel booking", "Book tickets for Harbour", "Book tickets for Open", "Events"):
        e = el(page, "link", name)
        if e and name not in hist:
            return {"type": "click", "element_id": e}
    return {"type": "finish", "summary": "scripted finish"}


def looper(page, user):
    """Imitates run_b92fc0e8e8c3: keeps walking links even when the map has nothing new."""
    hist = user.split("Your previous actions:")[1].split("Current page:")[0]
    links = re.findall(r'(e\d+) link "([^"]+)"', page)
    for e, name in links:
        if name not in hist:
            return {"type": "click", "element_id": e}
    return {"type": "click", "element_id": links[0][0]} if links else {"type": "finish", "summary": "scripted finish"}


def follower(page, user):
    """A cooperative model: takes the first control the coverage summary lists, and walks home if there are none here."""
    here = re.search(r"Unexplored on this page: (.*?)\.\n", user).group(1)
    links = re.findall(r'(e\d+) (?:link|button) "([^"]+)"', page)
    for e, name in links:
        if name in here:
            return {"type": "click", "element_id": e}
    hop = re.search(r"Next step towards unexplored work: (.*?)\.\n", user)
    for e, name in links if hop else []:
        if name in hop.group(1):
            return {"type": "click", "element_id": e}
    away = re.search(r"Unexplored elsewhere: (.*?)\.\n", user).group(1)
    return {"type": "click", "element_id": links[0][0]} if away != "none" and links else {"type": "finish", "summary": "scripted finish"}


def script(style):
    def reply(messages):
        system, user = messages[0]["content"], messages[-1]["content"]
        if "You operate a real browser" in system:
            page = user.split("Current page:")[1].split("\n\nNote:")[0]
            act = {"looper": looper, "follower": follower}.get(style, lambda p, u: explorer(style, p, u))(page, user)
            return json.dumps({"reasoning": "scripted", "action": act})
        if "designed input cases" in system:
            n = len(re.findall(r"(?m)^Case \d+", user)) or 2
            return json.dumps({"reasoning": "scripted", "assessments": [
                {"case": i + 1, "verdict": "as_expected", "observed_summary": "ok", "requirement_ref": None} for i in range(n)]})
        if SITE == "leave-desk":
            return json.dumps({"reasoning": "scripted", "cases": []})
        return json.dumps(ACTION_PLAN if "Yes, cancel booking" in user else PLAN)
    return reply


async def one(style, tmp):
    url = f"http://localhost:{PORT}"
    s = Settings(_env_file=None, artifacts_dir=Path(tmp) / style, flowlens_allowed_origins=url, openrouter_api_key=None)
    store = Store(Path(tmp) / f"{style}.db")
    run = Run(target_url=url + "/", goal="Scripted repetition check", requirements=[], model="scripted-test-model",
              mode="queue_review", limits=RunLimits(max_model_calls=40), provenance=Provenance(live=False, mocked_model=True))
    store.put(run)
    await QueueReviewRun(run, store, s, ScriptedClient(script(style))).execute()
    d = store.detail(run.id)
    model = {t.action_result_id for t in d.transitions if t.model_call_id}
    chosen = [t.label for t in d.transitions if t.model_call_id and t.agent_id.startswith("explorer") and t.ok]
    submits = [a for a in d.actions if a.action.get("type") == "click" and "button" in (a.target_description or "")
               and a.agent_id.startswith("explorer")]
    return {"style": style, "status": d.run.status.value, "actions": len(d.actions),
            "explorer_actions": sum(a.agent_id.startswith("explorer") for a in d.actions), "calls": d.run.usage.model_calls,
            "tasks": dict(Counter(t.status.value for t in d.tasks)), "explore_tasks_run": sum(
                t.type == "explore" and t.status.value in ("done", "unfinished") for t in d.tasks),
            "test_cases": len(d.test_cases), "forms": len(d.forms), "routes": sorted({s.route for s in d.states}),
            "explorer_submits_model": sum(a.id in model for a in submits), "explorer_submits_setup": sum(a.id not in model for a in submits),
            "failed_setups": sum(e.type == "task_retry" for e in d.events),
            "explorer_calls": sum(m.agent_id.startswith("explorer") for m in d.model_calls),
            "repeated_model_clicks": sum(n - 1 for n in Counter(chosen).values()),
            "refused_repeats": sum(e.type == "explorer_repeat_refused" for e in d.events),
            "structures": len({tuple(s.destinations) for s in d.states}),
            "unfinished": sorted({t.note for t in d.tasks if t.status.value == "unfinished"}), "clicks": chosen}


async def main():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        env = {**os.environ, "TICKET_DESK_DATA": str(Path(tmp) / "td.json"), "TICKET_DESK_MODE": "corrected",
               "LEAVE_DESK_DATA": str(Path(tmp) / "ld.json"), "LEAVE_DESK_MODE": "corrected"}
        proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--app-dir", str(ROOT / "fixtures" / SITE),
                                 "--port", str(PORT), "--log-level", "warning"], env=env)
        try:
            for _ in range(100):
                try:
                    httpx.get(f"http://localhost:{PORT}/", timeout=1)
                    break
                except httpx.HTTPError:
                    time.sleep(0.1)
            rows = [await one(style, tmp) for style in ("follower", "looper")]
        finally:
            proc.terminate()
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    (out / "repetition-check.json").write_text(json.dumps(rows, indent=1), "utf-8")
    for r in rows:
        print(json.dumps(r))


asyncio.run(main())
