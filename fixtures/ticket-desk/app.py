"""Ticket Desk: a second, held-out reference app for FlowLens evaluation.

Built after the checkpoint-5 evaluation and frozen before any agent ran against it.
Prompts were not tuned on it.

Evaluation-only settings (environment variables; never shown in pages, never given to agents):
- TICKET_DESK_MODE: "broken" (default) or "corrected". See evaluation/ticket-desk/answer_key.json.
- TICKET_DESK_DATA: data file (default data/bookings.json, ignored by Git).

Data isolation works as in creator-studio: the `td_ws` cookie selects a workspace,
and POST /__fixture/workspaces creates one.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

DATA_PATH = Path(os.environ.get("TICKET_DESK_DATA", Path(__file__).parent / "data" / "bookings.json"))
MODE = os.environ.get("TICKET_DESK_MODE", "broken")
WORKSPACE_COOKIE = "td_ws"
EVENTS = {"1": "Harbour Jazz Night", "2": "Open-Air Cinema"}
_lock = threading.Lock()

app = FastAPI(title="Ticket Desk fixture", docs_url=None, redoc_url=None, openapi_url=None)


def _load() -> dict:
    return json.loads(DATA_PATH.read_text("utf-8")) if DATA_PATH.exists() else {"workspaces": {}}


def _save(data: dict) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = DATA_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), "utf-8")
    tmp.replace(DATA_PATH)


def _ws(data: dict, request: Request) -> dict:
    return data["workspaces"].setdefault(request.cookies.get(WORKSPACE_COOKIE) or "default", {"bookings": {}})


def _page(title: str, body: str, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{escape(title)} · Ticket Desk</title>
<style>body{{font-family:system-ui,sans-serif;margin:0;background:#f4f6f9}} header{{background:#123;color:#fff;padding:12px 24px}}
header a{{color:#fff}} main{{max-width:680px;margin:24px auto;background:#fff;padding:24px;border-radius:8px}}
label{{display:block;font-weight:600;margin-top:14px}} input{{width:100%;padding:8px;box-sizing:border-box;font:inherit}}
button,.button{{margin-top:14px;padding:8px 14px;background:#1d5fd1;color:#fff;border:0;border-radius:4px;font:inherit;text-decoration:none;display:inline-block}}
.error{{background:#fdecee;border:1px solid #f1a1ad;padding:8px}} .status{{background:#e6f4ea;border:1px solid #8fcf9f;padding:8px}}</style>
</head><body><header><strong>Ticket Desk</strong> · <a href="/">Events</a></header><main>{body}</main></body></html>""",
                        status_code=status_code)


@app.get("/", response_class=HTMLResponse)
def events(request: Request, cancelled: int = 0):
    ws = _ws(_load(), request)
    status = '<p class="status" role="status">Booking cancelled.</p>' if cancelled else ""
    items = "".join(f'<li>{escape(n)} <a href="/events/{i}/book">Book tickets for {escape(n)}</a></li>'
                    for i, n in EVENTS.items())
    mine = [b for b in ws["bookings"].values() if MODE == "broken" or not b.get("cancelled")]
    rows = "".join(f'<li><a href="/bookings/{b["id"]}">{escape(EVENTS[b["event"]])} · {b["tickets"]} ticket(s)</a></li>'
                   for b in mine)
    return _page("Events", f"<h1>Events</h1>{status}<ul aria-label=\"Events\">{items}</ul><h2>My bookings</h2>"
                 + (f'<ul aria-label="My bookings">{rows}</ul>' if rows else "<p>No bookings yet.</p>"))


def _form(event_id: str, name="", email="", tickets="", error="") -> str:
    err = f'<p class="error" role="alert">{escape(error)}</p>' if error else ""
    return f"""<h1>Book tickets</h1><p>{escape(EVENTS[event_id])}</p>{err}
<form method="post" action="/events/{event_id}/book">
<label for="name">Name</label><input id="name" name="name" value="{escape(name)}">
<label for="email">Email</label><input id="email" name="email" value="{escape(email)}">
<label for="tickets">Tickets</label><input id="tickets" name="tickets" type="number" value="{escape(tickets)}">
<button type="submit">Book tickets</button></form>"""


@app.get("/events/{event_id}/book", response_class=HTMLResponse)
def book_form(event_id: str):
    if event_id not in EVENTS:
        raise HTTPException(404)
    return _page("Book tickets", _form(event_id))


@app.post("/events/{event_id}/book")
def book(request: Request, event_id: str, name: str = Form(""), email: str = Form(""), tickets: str = Form("")):
    if event_id not in EVENTS:
        raise HTTPException(404)
    try:
        n = int(tickets)
    except ValueError:
        return _page("Book tickets", _form(event_id, name, email, tickets, "Enter a number of tickets."), 422)
    # Broken build: the upper bound is missing (only n < 1 is rejected).
    too_many = n > 6 and MODE == "corrected"
    if n < 1 or too_many:
        return _page("Book tickets", _form(event_id, name, email, tickets, "Choose between 1 and 6 tickets."), 422)
    if "@" not in email:
        return _page("Book tickets", _form(event_id, name, email, tickets, "Enter an email address containing @."), 422)
    b = {"id": uuid4().hex[:8], "event": event_id, "name": name, "email": email, "tickets": n,
         "created_at": datetime.now(UTC).isoformat()}
    with _lock:
        data = _load()
        _ws(data, request)["bookings"][b["id"]] = b
        _save(data)
    return RedirectResponse(f"/bookings/{b['id']}?booked=1", status_code=303)


@app.get("/bookings/{booking_id}", response_class=HTMLResponse)
def booking(request: Request, booking_id: str, booked: int = 0):
    b = _ws(_load(), request)["bookings"].get(booking_id)
    if b is None:
        raise HTTPException(404)
    status = '<p class="status" role="status">Booking confirmed.</p>' if booked else ""
    return _page("Booking", f"<h1>Your booking</h1>{status}<dl><dt>Event</dt><dd>{escape(EVENTS[b['event']])}</dd>"
                 f"<dt>Name</dt><dd>{escape(b['name'])}</dd><dt>Tickets</dt><dd>{b['tickets']}</dd></dl>"
                 f'<a class="button" href="/bookings/{booking_id}/cancel">Cancel booking</a> <a href="/">Back to events</a>')


@app.get("/bookings/{booking_id}/cancel", response_class=HTMLResponse)
def cancel_confirm(request: Request, booking_id: str):
    if booking_id not in _ws(_load(), request)["bookings"]:
        raise HTTPException(404)
    return _page("Cancel booking", f'<h1>Cancel this booking?</h1><form method="post" action="/bookings/{booking_id}/cancel">'
                 '<button type="submit">Yes, cancel booking</button></form><a href="/">Keep booking</a>')


@app.post("/bookings/{booking_id}/cancel")
def cancel(request: Request, booking_id: str):
    with _lock:
        data = _load()
        b = _ws(data, request)["bookings"].get(booking_id)
        if b is None:
            raise HTTPException(404)
        b["cancelled"] = True  # broken build still lists cancelled bookings
        _save(data)
    return RedirectResponse("/?cancelled=1", status_code=303)


@app.post("/__fixture/workspaces")
def create_workspace():
    ws = f"ws_{uuid4().hex[:10]}"
    with _lock:
        data = _load()
        data["workspaces"][ws] = {"bookings": {}}
        _save(data)
    return {"workspace": ws, "cookie": WORKSPACE_COOKIE}


@app.post("/__fixture/reset")
def reset():
    with _lock:
        _save({"workspaces": {}})
    return {"ok": True}
