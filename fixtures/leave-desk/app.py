"""Leave Desk: a third, held-out reference app for FlowLens evaluation.

Built and frozen before any agent ran against it. Prompts were not tuned on it.

Evaluation-only settings (environment variables; never shown in pages, never given to agents):
- LEAVE_DESK_MODE: "broken" (default) or "corrected". See evaluation/leave-desk/answer_key.json.
- LEAVE_DESK_DATA: data file (default data/leave.json, ignored by Git).

Data isolation works as in creator-studio: the `ld_ws` cookie selects a workspace,
and POST /__fixture/workspaces creates one. Every workspace starts from the same seed.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import date
from html import escape
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

DATA_PATH = Path(os.environ.get("LEAVE_DESK_DATA", Path(__file__).parent / "data" / "leave.json"))
MODE = os.environ.get("LEAVE_DESK_MODE", "broken")
TODAY = "2026-07-01"
STARTING_BALANCE = 12
MAX_REASON = 200
WORKSPACE_COOKIE = "ld_ws"
LEAVE_TYPES = ("Annual", "Sick")
STATUSES = ("Pending", "Approved", "Cancelled")
_lock = threading.Lock()

app = FastAPI(title="Leave Desk fixture", docs_url=None, redoc_url=None, openapi_url=None)


def _seed() -> dict:
    # Seeded requests predate the balance: it starts at 12 and only requests made here use it.
    seeded = [("1001", "Annual", "2026-06-08", "2026-06-09", "Family visit", "Approved"),
              ("1002", "Annual", "2026-07-20", "2026-07-22", "Moving house", "Pending"),
              ("1003", "Sick", "2026-06-22", "2026-06-22", "Dentist", "Cancelled")]
    return {
        "requests": {i: {"id": i, "type": t, "start": s, "end": e, "reason": r, "status": st, "seeded": True}
                     for i, t, s, e, r, st in seeded},
        "profile": {"name": "Alex Morgan", "email": "alex.morgan@example.test", "updates": False},
    }


def _load() -> dict:
    return json.loads(DATA_PATH.read_text("utf-8")) if DATA_PATH.exists() else {"workspaces": {}}


def _save(data: dict) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = DATA_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), "utf-8")
    tmp.replace(DATA_PATH)


def _ws(data: dict, request: Request) -> dict:
    return data["workspaces"].setdefault(request.cookies.get(WORKSPACE_COOKIE) or "default", _seed())


def _days(r: dict) -> int:
    return (date.fromisoformat(r["end"]) - date.fromisoformat(r["start"])).days + 1


def _remaining(ws: dict) -> int:
    return STARTING_BALANCE - sum(_days(r) for r in ws["requests"].values()
                                  if r["status"] != "Cancelled" and not r.get("seeded"))


def _pending(ws: dict) -> int:
    # Broken build: a cancelled request keeps counting as pending.
    return sum(r["status"] == "Pending" or (MODE == "broken" and r.get("cancelled_here", False))
               for r in ws["requests"].values())


def _newest(ws: dict) -> list[dict]:
    return sorted(ws["requests"].values(), key=lambda r: int(r["id"]), reverse=True)


def _page(title: str, body: str, footer: str = "", status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{escape(title)} · Leave Desk</title>
<style>body{{font-family:system-ui,sans-serif;margin:0;background:#f3f6f4}} header{{background:#17423a;color:#fff;padding:12px 24px}}
header a{{color:#fff}} main{{max-width:680px;margin:24px auto;background:#fff;padding:24px;border-radius:8px}} footer{{max-width:680px;margin:0 auto 24px;text-align:center}}
label{{display:block;font-weight:600;margin-top:14px}} input,select,textarea{{width:100%;padding:8px;box-sizing:border-box;font:inherit}}
input[type=checkbox]{{width:auto}} button,.button{{margin-top:14px;padding:8px 14px;background:#1f7a66;color:#fff;border:0;border-radius:4px;font:inherit;text-decoration:none;display:inline-block;cursor:pointer}}
.error{{background:#fdecee;border:1px solid #f1a1ad;padding:8px}} .status{{background:#e6f4ea;border:1px solid #8fcf9f;padding:8px}}
[role=dialog]{{border:1px solid #999;padding:16px;border-radius:8px;margin-top:16px}}</style>
</head><body><header><strong>Leave Desk</strong> · <a href="/">Dashboard</a> · <span>Today: {TODAY}</span></header><main>{body}</main>{footer}</body></html>""",
                        status_code=status_code)


def _row(r: dict) -> str:
    return (f'<li><a href="/requests/{r["id"]}">{escape(r["type"])} leave, {r["start"]} to {r["end"]}</a>'
            f' · {r["status"]}</li>')


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    ws = _ws(_load(), request)
    recent = "".join(_row(r) for r in _newest(ws)[:3])
    return _page("Dashboard", f"""<h1>Dashboard</h1><p>Remaining balance: {_remaining(ws)} days</p>
<p>Pending requests: {_pending(ws)}</p><a class="button" href="/requests/new">New request</a>
<a class="button" href="/requests">My requests</a> <a class="button" href="/profile">Profile</a>
<h2>Recent requests</h2><ul aria-label="Recent requests">{recent}</ul>""",
                 '<footer><a href="/calendar">Team calendar</a></footer>')


def _form(action: str, heading: str, button: str, leave_type="Annual", start="", end="", reason="", error="") -> str:
    err = f'<p class="error" role="alert">{escape(error)}</p>' if error else ""
    options = "".join(f'<option value="{t}"{" selected" if t == leave_type else ""}>{t}</option>' for t in LEAVE_TYPES)
    return f"""<h1>{heading}</h1>{err}<form method="post" action="{action}">
<label for="leave_type">Leave type</label><select id="leave_type" name="leave_type">{options}</select>
<label for="start_date">Start date</label><input id="start_date" name="start_date" type="date" value="{escape(start)}">
<label for="end_date">End date</label><input id="end_date" name="end_date" type="date" value="{escape(end)}">
<label for="reason">Reason (optional)</label><textarea id="reason" name="reason" rows="4">{escape(reason)}</textarea>
<button type="submit">{button}</button></form>"""


def _invalid(ws: dict, leave_type: str, start: str, end: str, reason: str, editing: dict | None = None) -> str:
    """The validation message for a submitted request, or an empty string."""
    if leave_type not in LEAVE_TYPES:
        return "Choose a leave type."
    try:
        days = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    except ValueError:
        return "Enter a start date and an end date."
    if days < 1:
        return "End date cannot be before the start date."
    if len(reason) > MAX_REASON:
        return f"Reason must be {MAX_REASON} characters or fewer."
    available = _remaining(ws) + (_days(editing) if editing and not editing.get("seeded") else 0)
    # Broken build: the balance is never checked.
    if MODE == "corrected" and days > available:
        return f"This request is for {days} days, but only {available} days remain."
    return ""


@app.get("/requests/new", response_class=HTMLResponse)
def new_request():
    return _page("New request", _form("/requests", "New request", "Submit"))


@app.post("/requests")
def create_request(request: Request, leave_type: str = Form("Annual"), start_date: str = Form(""),
                   end_date: str = Form(""), reason: str = Form("")):
    with _lock:
        data = _load()
        ws = _ws(data, request)
        error = _invalid(ws, leave_type, start_date, end_date, reason)
        if error:
            return _page("New request", _form("/requests", "New request", "Submit", leave_type, start_date, end_date,
                                              reason, error), status_code=422)
        rid = str(max(int(i) for i in ws["requests"]) + 1)
        ws["requests"][rid] = {"id": rid, "type": leave_type, "start": start_date, "end": end_date, "reason": reason,
                               "status": "Pending"}
        _save(data)
    return RedirectResponse(f"/requests/{rid}", status_code=303)


@app.get("/requests", response_class=HTMLResponse)
def my_requests(request: Request, status: str = "All"):
    ws = _ws(_load(), request)
    active = status if status in STATUSES else "All"
    tabs = " ".join(
        f'<a href="{"/requests" if s == "All" else f"/requests?status={s}"}"{" aria-current=page" if s == active else ""}>{s}</a>'
        for s in ("All", *STATUSES))
    rows = "".join(_row(r) for r in _newest(ws) if active in ("All", r["status"]))
    listing = f'<ul aria-label="Requests">{rows}</ul>' if rows else "<p>No requests.</p>"
    return _page("My requests", f'<h1>My requests</h1><nav aria-label="Status filter">{tabs}</nav>{listing}')


def _detail(r: dict, dialog: str = "") -> HTMLResponse:
    actions = ""
    if r["status"] == "Pending":
        actions = (f'<a class="button" href="/requests/{r["id"]}/edit">Edit</a> '
                   f'<a class="button" href="/requests/{r["id"]}?cancel=1">Cancel request</a>')
    return _page("Request", f"""<h1>Leave request</h1><dl><dt>Leave type</dt><dd>{escape(r["type"])}</dd>
<dt>Start date</dt><dd>{r["start"]}</dd><dt>End date</dt><dd>{r["end"]}</dd><dt>Days</dt><dd>{_days(r)}</dd>
<dt>Reason</dt><dd>{escape(r["reason"]) or "None given"}</dd><dt>Status</dt><dd>{r["status"]}</dd></dl>
{actions} <a href="/requests">Back to my requests</a>{dialog}""")


def _get(ws: dict, request_id: str) -> dict:
    r = ws["requests"].get(request_id)
    if r is None:
        raise HTTPException(404)
    return r


@app.get("/requests/{request_id}", response_class=HTMLResponse)
def detail(request: Request, request_id: str, cancel: int = 0):
    r = _get(_ws(_load(), request), request_id)
    dialog = ""
    if cancel and r["status"] == "Pending":
        dialog = (f'<div role="dialog" aria-modal="true" aria-label="Cancel this request?"><h2>Cancel this request?</h2>'
                  f'<form method="post" action="/requests/{request_id}/cancel"><button type="submit">Confirm</button></form>'
                  f'<a href="/requests/{request_id}">Keep request</a></div>')
    return _detail(r, dialog)


@app.post("/requests/{request_id}/cancel")
def cancel_request(request: Request, request_id: str):
    with _lock:
        data = _load()
        r = _get(_ws(data, request), request_id)
        if r["status"] == "Pending":
            r.update(status="Cancelled", cancelled_here=True)
            _save(data)
    return RedirectResponse(f"/requests/{request_id}", status_code=303)


@app.get("/requests/{request_id}/edit", response_class=HTMLResponse)
def edit_form(request: Request, request_id: str):
    r = _get(_ws(_load(), request), request_id)
    if r["status"] != "Pending":
        return RedirectResponse(f"/requests/{request_id}", status_code=303)
    return _page("Edit request", _form(f"/requests/{request_id}/edit", "Edit request", "Save changes", r["type"],
                                       r["start"], r["end"], r["reason"]))


@app.post("/requests/{request_id}/edit")
def save_edit(request: Request, request_id: str, leave_type: str = Form("Annual"), start_date: str = Form(""),
              end_date: str = Form(""), reason: str = Form("")):
    with _lock:
        data = _load()
        ws = _ws(data, request)
        r = _get(ws, request_id)
        if r["status"] != "Pending":
            return RedirectResponse(f"/requests/{request_id}", status_code=303)
        error = _invalid(ws, leave_type, start_date, end_date, reason, editing=r)
        if error:
            return _page("Edit request", _form(f"/requests/{request_id}/edit", "Edit request", "Save changes",
                                               leave_type, start_date, end_date, reason, error), status_code=422)
        # Broken build: the reason is dropped on save.
        r.update(type=leave_type, start=start_date, end=end_date, reason=reason if MODE == "corrected" else "")
        _save(data)
    return RedirectResponse(f"/requests/{request_id}", status_code=303)


@app.get("/profile", response_class=HTMLResponse)
def profile(request: Request):
    with _lock:
        data = _load()
        ws = _ws(data, request)
        p = ws["profile"]
        saved = ws.pop("just_saved", False)
        checked = " checked" if p["updates"] else ""
        if saved:
            if MODE == "broken":  # broken build: the toggle survives only the view straight after Save
                p["updates"] = False
            _save(data)
    status = '<p class="status" role="status">Saved.</p>' if saved else ""
    return _page("Profile", f"""<h1>Profile</h1>{status}<form method="post" action="/profile">
<label for="display_name">Display name</label><input id="display_name" name="display_name" value="{escape(p["name"])}">
<label for="email">Email</label><input id="email" name="email" value="{escape(p["email"])}">
<label><input id="email_updates" name="email_updates" type="checkbox"{checked}> Email me updates</label>
<button type="submit">Save</button></form>""")


@app.post("/profile")
def save_profile(request: Request, display_name: str = Form(""), email: str = Form(""), email_updates: str = Form("")):
    with _lock:
        data = _load()
        ws = _ws(data, request)
        ws["profile"] = {"name": display_name, "email": email, "updates": bool(email_updates)}
        ws["just_saved"] = True
        _save(data)
    return RedirectResponse("/profile", status_code=303)


@app.get("/calendar", response_class=HTMLResponse)
def calendar(request: Request):
    ws = _ws(_load(), request)
    # Broken build: cancelled requests are not filtered out.
    shown = sorted((r for r in ws["requests"].values() if MODE == "broken" or r["status"] != "Cancelled"),
                   key=lambda r: r["start"])
    rows = "".join(f'<li>{r["start"]} to {r["end"]}: {escape(ws["profile"]["name"])}, {escape(r["type"])} ({r["status"]})</li>'
                   for r in shown)
    listing = f'<ul aria-label="Team leave">{rows}</ul>' if rows else "<p>No leave booked.</p>"
    return _page("Team calendar", f"<h1>Team calendar</h1>{listing}")


@app.post("/__fixture/workspaces")
def create_workspace():
    ws = f"ws_{uuid4().hex[:10]}"
    with _lock:
        data = _load()
        data["workspaces"][ws] = _seed()
        _save(data)
    return {"workspace": ws, "cookie": WORKSPACE_COOKIE}


@app.post("/__fixture/reset")
def reset():
    with _lock:
        _save({"workspaces": {}})
    return {"ok": True}
