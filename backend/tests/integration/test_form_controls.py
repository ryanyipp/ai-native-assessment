"""Regressions from run_118da630dc8b. Scripted model, real Chromium and Leave Desk.

The scripted verdicts exercise mechanics only. They say nothing about how a real model judges a case.
"""

import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from flowlens.browser.engine import BrowserEngine
from flowlens.config import Settings
from flowlens.models.contracts import ClickAction, NavigateAction, Provenance, Run, RunLimits
from flowlens.orchestration.queue_review import QueueReviewRun
from flowlens.services.llm import ScriptedClient
from flowlens.services.report import build_report, to_markdown
from flowlens.storage.db import Store

REPO = Path(__file__).resolve().parents[3]
REQS = ["L1: Saved requests keep their leave type.", "L6: Profile changes, including the email-updates toggle, must be kept."]
DATES = {"Start date": "2026-07-10", "End date": "2026-07-12"}


@pytest.fixture
def leave_desk(tmp_path):
    with socket.socket() as s:  # each test gets its own port, so a server still shutting down cannot answer for this one
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {**os.environ, "LEAVE_DESK_DATA": str(tmp_path / "ld.json"), "LEAVE_DESK_MODE": "corrected"}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--app-dir", str(REPO / "fixtures" / "leave-desk"),
                             "--port", str(port), "--log-level", "warning"], env=env)
    url = f"http://localhost:{port}"
    for _ in range(100):
        assert proc.poll() is None, "Leave Desk exited during startup"
        try:
            httpx.get(url, timeout=1)
            break
        except httpx.HTTPError:
            time.sleep(0.1)
    else:
        pytest.fail("Leave Desk did not start")
    yield SimpleNamespace(url=url)
    proc.terminate()
    proc.wait(timeout=10)


def case(label, inputs, submit, ref=None):
    return {"label": label, "inputs": inputs, "submit": submit, "requirement_ref": ref, "expected": "scripted"}


LEAVE_PLAN = [case("Select", {"Leave type": "Sick", **DATES, "Reason (optional)": "flu"}, "Submit", "L1"),
              case("Bad option", {"Leave type": "Holiday", **DATES}, "Submit")]
PROFILE_PLAN = [case("Untick", {"Display name": "Alex M.", "Email me updates": "false"}, "Save", "L6"),
                case("Bad boolean", {"Email me updates": "maybe"}, "Save"),
                case("Missing control", {"Ghost field": "x"}, "Save")]


def script(messages):
    system, user = messages[0]["content"], messages[-1]["content"]
    if "You operate a real browser" in system:
        page = user.split("Current page:")[1].split("\n\nNote:")[0]
        for name in ("New request", "Profile"):
            m = re.search(rf'(e\d+) link "{name}"', page)
            if m and name not in user.split("Already investigated:")[1].split("Records:")[0]:
                return json.dumps({"reasoning": "scripted", "action": {"type": "click", "element_id": m.group(1)}})
        return json.dumps({"reasoning": "scripted", "action": {"type": "finish", "summary": "done"}})
    if "designed input cases" in system:
        n = len(re.findall(r"(?m)^Case \d+", user))
        return json.dumps({"reasoning": "scripted", "assessments": [
            {"case": i + 1, "verdict": "unexpected", "observed_summary": "scripted", "requirement_ref": None} for i in range(n)]})
    if "You are the Verifier" in system:
        ref, quote, target = (("L1", "Saved requests keep their leave type", "Leave type") if "L1" in user.split("\n")[0]
                              else ("L6", "email-updates toggle", "Email me updates"))
        return json.dumps({"reasoning": "scripted", "requirement_ref": ref, "explicit": True, "requirement_quote": quote,
                           "applicability": "applies", "applicability_target": target, "applicability_reason": "scripted",
                           "assertion": {"type": "validation_message_present", "params": {}}, "expected": "scripted"})
    return json.dumps({"reasoning": "scripted", "cases": LEAVE_PLAN if '"Leave type"' in user else PROFILE_PLAN})


async def review(server, tmp_path):
    settings = Settings(_env_file=None, artifacts_dir=tmp_path / "artifacts", flowlens_allowed_origins=server.url,
                        openrouter_api_key=None)
    store = Store(tmp_path / "r.db")
    run = Run(target_url=server.url + "/", goal="Open the forms", requirements=REQS, model="scripted-test-model",
              mode="queue_review", limits=RunLimits(max_model_calls=30), provenance=Provenance(live=False, mocked_model=True))
    store.put(run)
    qr = QueueReviewRun(run, store, settings, ScriptedClient(script))
    await qr.execute()
    return store.detail(run.id), tmp_path


async def test_controls_use_the_right_action_through_testing_and_replay(leave_desk, tmp_path):
    d, _ = await review(leave_desk, tmp_path)
    cases = {c.label: c for c in d.test_cases}
    assert cases["Select"].status == "executed", cases["Select"].setup_error
    assert cases["Untick"].status == "executed", cases["Untick"].setup_error
    assert "Sick" in cases["Select"].observed["text_excerpt"]  # the site really received the chosen option
    form_actions = [a.action for a in d.actions if a.agent_id == "input-tester"]
    assert {"type": "select", "value": "Sick"}.items() <= next(a for a in form_actions if a["type"] == "select").items()
    assert next(a for a in form_actions if a["type"] == "check")["checked"] is False
    replayed = [a.action for a in d.actions if a.agent_id == "verifier"]
    assert any(a["type"] == "select" and a["value"] == "Sick" for a in replayed)
    assert any(a["type"] == "check" and a["checked"] is False for a in replayed)
    assert {v.setup_ok for v in d.verifications} == {True}
    assert {v.failure_class for v in d.verifications} == {None}
    # Saved reproduction steps keep the action type and value.
    steps = [s for f in d.findings for s in f.reproduction_steps]
    assert any(s.type == "select" and s.value == "Sick" for s in steps)
    assert any(s.type == "check" and s.checked is False for s in steps)


async def test_unsupported_values_are_explicit_failures_not_website_verdicts(leave_desk, tmp_path):
    d, _ = await review(leave_desk, tmp_path)
    cases = {c.label: c for c in d.test_cases}
    bad = cases["Bad option"]
    assert bad.status == "execution_failed" and "'Holiday'" in bad.setup_error and "Annual" in bad.setup_error
    boolean = cases["Bad boolean"]
    assert boolean.status == "execution_failed" and "'maybe'" in boolean.setup_error
    assert cases["Missing control"].status == "execution_failed" and "Ghost field" in cases["Missing control"].setup_error
    assert cases["Missing control"].evidence_refs  # what happened before the failure stays inspectable
    for c in (bad, boolean, cases["Missing control"]):
        assert c.tester_verdict is None and c.tester_note is None
    assert {f.test_case_id for f in d.findings} == {cases["Select"].id, cases["Untick"].id}
    assert "2 test case(s) executed, 3 not completed" in d.run.stop_reason


async def test_reports_keep_tool_failures_apart_from_website_results(leave_desk, tmp_path):
    d, root = await review(leave_desk, tmp_path)
    md = to_markdown(build_report(d, root / "artifacts", "http://h"))
    assert "Test case “Bad option” did not complete" in md
    assert "This is a tool or execution failure, not evidence about the website." in md


async def test_a_real_site_error_is_an_observed_result_not_a_tool_failure(leave_desk):
    async with BrowserEngine([leave_desk.url]) as b:
        await b.execute(NavigateAction(url=leave_desk.url + "/"))
        await b.page.route("**/profile", lambda r: r.fulfill(status=500, content_type="text/html",
                                                             body="<h1>Internal Server Error</h1>"))
        el = next(e for e in b.last_observation.elements if e.name == "Profile")
        ex = await b.execute(ClickAction(element_id=el.id))
    assert ex.ok and "Internal Server Error" in ex.observation.headings  # recorded as what the site did
