"""Regressions from run_816054f4e335 and run_3f84fb9bdc8b. Scripted model, real Chromium and Ticket Desk."""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from flowlens.browser.engine import page_destinations
from flowlens.models.contracts import ControlRef, Observation, ObservedElement, ScreenState, SemanticStep

from test_queue import make_queue_run
from test_review import _id

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture
def ticket_desk(tmp_path):
    port = 5398
    env = {**os.environ, "TICKET_DESK_DATA": str(tmp_path / "td.json"), "TICKET_DESK_MODE": "corrected"}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--app-dir", str(REPO / "fixtures" / "ticket-desk"),
                             "--port", str(port), "--log-level", "warning"], env=env)
    url = f"http://localhost:{port}"
    for _ in range(100):
        try:
            httpx.get(url, timeout=1)
            break
        except httpx.HTTPError:
            time.sleep(0.1)
    yield SimpleNamespace(url=url)
    proc.terminate()


def _obs(url, links, buttons=(), alerts=()):
    els = [ObservedElement(id=f"l{i}", tag="a", role="link", name=n, href=h) for i, (n, h) in enumerate(links)]
    els += [ObservedElement(id=f"b{i}", tag="button", role="button", name=n) for i, n in enumerate(buttons)]
    return Observation(url=url, title="t", headings=[], elements=els, alert_messages=list(alerts))


def test_destinations_ignore_listed_data_but_keep_new_controls_and_errors():
    base = page_destinations(_obs("http://h/", [("Trip · 2 tickets", "/bookings/aaaaaaaa")]))
    assert base == page_destinations(_obs("http://h/", [("Gig · 9 tickets", "/bookings/bbbbbbbb")]))
    assert not set(page_destinations(_obs("http://h/", [("Refund", "/refunds")]))) <= set(base)
    assert not set(page_destinations(_obs("http://h/", [], buttons=["Delete"]))) <= set(base)
    assert not set(page_destinations(_obs("http://h/", [], alerts=["Bad date"]))) <= set(base)


def booking_goal_script():
    """A model that insists on booking in every explorer task, as the goal in run_816054f4e335 asked."""
    def script(messages):
        system, user = messages[0]["content"], messages[-1]["content"]
        if "You operate a real browser" in system:
            page = user.split("Current page:")[1].split("\n\nNote:")[0]
            if "Headings: Book tickets" in page and "refused" not in user:
                return json.dumps({"reasoning": "scripted: book", "action": {
                    "type": "fill", "element_id": _id(page, "textbox", "Name"), "value": "Ryan"}})
            if "Book tickets for Harbour" in page and "refused" not in user:
                m = re.search(r"(e\d+) link \"Book tickets for Harbour", page)
                return json.dumps({"reasoning": "scripted: open", "action": {"type": "click", "element_id": m.group(1)}})
            return json.dumps({"reasoning": "scripted", "action": {"type": "finish", "summary": "done"}})
        if "designed input cases" in system:
            return json.dumps({"reasoning": "scripted", "assessments": [
                {"case": 1, "verdict": "as_expected", "observed_summary": "booked", "requirement_ref": None}]})
        return json.dumps({"reasoning": "scripted", "cases": [{"label": "Valid", "submit": "Book tickets", "expected": "booked",
                                                               "inputs": {"Name": "Ann", "Email": "a@example.test", "Tickets": "2"}}]})
    return script


async def test_explorers_cannot_fill_a_form_the_tester_owns(ticket_desk, tmp_path):
    qr, store = make_queue_run(ticket_desk, tmp_path, booking_goal_script(), name="own")
    qr.run.requirements = []
    await qr.execute()
    d = store.detail(qr.run.id)
    chosen = {t.action_result_id for t in d.transitions if t.model_call_id}  # setup replay may still fill forms
    assert not [a for a in d.actions if a.id in chosen and a.agent_id.startswith("explorer") and a.action.get("type") == "fill"]
    assert any(e.type == "explorer_action_refused" for e in d.events)
    assert d.test_cases  # the tester still books


def test_created_records_replay_their_recipe_but_seeded_ids_stay_direct(tmp_path):
    qr, _ = make_queue_run(SimpleNamespace(url="http://localhost:1"), tmp_path, lambda m: "{}", name="setup")
    nav = SemanticStep(type="navigate", path="/")
    fill = SemanticStep(type="fill", value="x", control=ControlRef(role="textbox", name="Name"))
    created = ScreenState(run_id=qr.run.id, signature="s", route="/bookings/:id", url="http://h/bookings/abcdef12?booked=1",
                          title="t", summary="s", first_seen_step=1, discovered_by="input-tester", phase="input_test",
                          semantic_recipe=[nav, fill])
    seeded = created.model_copy(update={"route": "/events/:id/book", "url": "http://h/events/1/book", "semantic_recipe": [nav]})
    assert qr.setup_for(created).direct_path is None
    assert qr.setup_for(seeded).direct_path == "/events/1/book"
