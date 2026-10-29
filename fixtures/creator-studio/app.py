"""Creator Studio: the controlled creator-dashboard fixture FlowLens reviews.

Server-rendered so a reload is a real fresh navigation. Data persists in a JSON
file (CREATOR_STUDIO_DATA), so it survives page reloads and fixture restarts.
Run:  uvicorn app:app --port 5174   (from this directory)

Evaluation-only settings (environment variables read by evaluation tooling,
never shown in pages and never given to runtime agents):

- CREATOR_STUDIO_MODE: "broken" (default) accepts a past publish date;
  "corrected" rejects it. Nothing else differs between the modes.
- CREATOR_STUDIO_TODAY: fixed studio clock (ISO date, default 2026-06-15) so
  date tests are repeatable.

Data isolation: records are kept per workspace. The workspace comes from the
`cs_ws` cookie (default "default"). Test harnesses create a fresh workspace with
POST /__fixture/workspaces and set the cookie on their browser context, so each
test case gets its own records. A fresh browser alone would not isolate data.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import UTC, date, datetime
from html import escape
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

DATA_PATH = Path(os.environ.get("CREATOR_STUDIO_DATA", Path(__file__).parent / "data" / "drafts.json"))
MODE = os.environ.get("CREATOR_STUDIO_MODE", "broken")
TODAY = date.fromisoformat(os.environ.get("CREATOR_STUDIO_TODAY", "2026-06-15"))
WORKSPACE_COOKIE = "cs_ws"
_lock = threading.Lock()

app = FastAPI(title="Creator Studio fixture", docs_url=None, redoc_url=None, openapi_url=None)


# --- storage -----------------------------------------------------------------


def _load_all() -> dict:
    if not DATA_PATH.exists():
        return {"workspaces": {}}
    raw = json.loads(DATA_PATH.read_text("utf-8"))
    if "workspaces" not in raw:  # checkpoint 0-1 format: a flat dict of drafts
        raw = {"workspaces": {"default": {"drafts": raw, "posts": {}}}}
    return raw


def _save_all(data: dict) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = DATA_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), "utf-8")
    tmp.replace(DATA_PATH)


def _ws_id(request: Request) -> str:
    return request.cookies.get(WORKSPACE_COOKIE) or "default"


def _ws(data: dict, ws: str) -> dict:
    w = data["workspaces"].setdefault(ws, {"drafts": {}, "posts": {}})
    w.setdefault("drafts", {})
    w.setdefault("posts", {})
    return w


def _read(request: Request) -> dict:
    return _ws(_load_all(), _ws_id(request))


# --- pages -------------------------------------------------------------------


def _page(title: str, body: str, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>{escape(title)} · Creator Studio</title>
<style>
 body{{font-family:system-ui,sans-serif;margin:0;background:#f6f6f8;color:#1b1b1f}}
 header{{background:#111;color:#fff;padding:12px 24px;display:flex;gap:24px;align-items:center}}
 header a{{color:#fff}} main{{max-width:720px;margin:24px auto;background:#fff;padding:24px;border-radius:8px}}
 label{{display:block;font-weight:600;margin-top:16px}} input,textarea{{width:100%;padding:8px;font:inherit;box-sizing:border-box}}
 button,.button{{margin-top:16px;padding:8px 16px;background:#fe2c55;color:#fff;border:0;border-radius:4px;font:inherit;cursor:pointer;text-decoration:none;display:inline-block}}
 .status{{background:#e6f7ec;border:1px solid #8fd1a5;padding:8px;border-radius:4px}} li{{margin:6px 0}}
 .error{{background:#fdecee;border:1px solid #f1a1ad;padding:8px;border-radius:4px}} .hint{{color:#555}}
</style></head><body>
<header><strong>Creator Studio</strong><nav aria-label="Main"><a href="/">Dashboard</a></nav></header>
<main>{body}</main></body></html>""",
        status_code=status_code,
    )


def _form(action: str, button: str, title: str = "", caption: str = "") -> str:
    return f"""<form method="post" action="{action}">
<label for="title">Title</label><input id="title" name="title" value="{escape(title)}" maxlength="120">
<label for="caption">Caption</label><textarea id="caption" name="caption" rows="4" maxlength="2200">{escape(caption)}</textarea>
<button type="submit">{button}</button></form>"""


def _schedule_form(title: str = "", publish_date: str = "", error: str = "") -> str:
    err = f'<p class="error" role="alert">{escape(error)}</p>' if error else ""
    return f"""<h1>Schedule a post</h1>{err}
<p class="hint">Studio date: {TODAY.isoformat()}</p>
<form method="post" action="/schedule">
<label for="post_title">Post title</label><input id="post_title" name="post_title" value="{escape(title)}" maxlength="120" required>
<label for="publish_date">Publish date</label><input id="publish_date" name="publish_date" type="date" value="{escape(publish_date)}" required>
<button type="submit">Schedule post</button></form>"""


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    w = _read(request)
    drafts = sorted(w["drafts"].values(), key=lambda d: d["updated_at"], reverse=True)
    items = "".join(
        f'<li><a href="/drafts/{d["id"]}">{escape(d["title"] or "(untitled)")}</a></li>' for d in drafts
    )
    listing = f"<ul aria-label=\"Drafts\">{items}</ul>" if items else "<p>No drafts yet.</p>"
    posts = sorted(w["posts"].values(), key=lambda p: p["publish_date"])
    pitems = "".join(
        f'<li><a href="/scheduled/{p["id"]}">{escape(p["title"])}</a> · {escape(p["publish_date"])}</li>'
        for p in posts
    )
    plisting = f"<ul aria-label=\"Scheduled posts\">{pitems}</ul>" if pitems else "<p>No scheduled posts.</p>"
    return _page(
        "Dashboard",
        '<h1>Dashboard</h1><a class="button" href="/drafts/new">New draft</a> '
        '<a class="button" href="/schedule/new">Schedule a post</a>'
        f"<h2>Your drafts</h2>{listing}<h2>Scheduled posts</h2>{plisting}",
    )


# --- drafts (checkpoint 1 journey, unchanged behaviour) ----------------------


@app.get("/drafts/new", response_class=HTMLResponse)
def new_draft():
    return _page("New draft", "<h1>New draft</h1>" + _form("/drafts", "Save draft"))


@app.post("/drafts")
def create_draft(request: Request, title: str = Form(""), caption: str = Form("")):
    now = datetime.now(UTC).isoformat()
    draft = {"id": uuid4().hex[:8], "title": title, "caption": caption, "created_at": now, "updated_at": now}
    with _lock:
        data = _load_all()
        _ws(data, _ws_id(request))["drafts"][draft["id"]] = draft
        _save_all(data)
    return RedirectResponse(f"/drafts/{draft['id']}?saved=1", status_code=303)


@app.get("/drafts/{draft_id}", response_class=HTMLResponse)
def edit_draft(request: Request, draft_id: str, saved: int = 0):
    d = _read(request)["drafts"].get(draft_id)
    if d is None:
        raise HTTPException(404, "Draft not found")
    status = '<p class="status" role="status">Draft saved.</p>' if saved else ""
    return _page(
        "Edit draft",
        f"<h1>Edit draft</h1>{status}" + _form(f"/drafts/{draft_id}", "Save changes", d["title"], d["caption"]),
    )


@app.post("/drafts/{draft_id}")
def update_draft(request: Request, draft_id: str, title: str = Form(""), caption: str = Form("")):
    with _lock:
        data = _load_all()
        drafts = _ws(data, _ws_id(request))["drafts"]
        if draft_id not in drafts:
            raise HTTPException(404, "Draft not found")
        drafts[draft_id].update(title=title, caption=caption, updated_at=datetime.now(UTC).isoformat())
        _save_all(data)
    return RedirectResponse(f"/drafts/{draft_id}?saved=1", status_code=303)


# --- scheduling ----------------------------------------------------------------


@app.get("/schedule/new", response_class=HTMLResponse)
def new_schedule():
    return _page("Schedule a post", _schedule_form())


@app.post("/schedule")
def create_schedule(request: Request, post_title: str = Form(""), publish_date: str = Form("")):
    title = post_title.strip()
    if not title:
        return _page("Schedule a post", _schedule_form(post_title, publish_date, "Post title is required."), 422)
    try:
        when = date.fromisoformat(publish_date)
    except ValueError:
        return _page("Schedule a post", _schedule_form(post_title, publish_date, "Enter a valid publish date."), 422)
    # The only difference between modes: corrected rejects a date before the studio date.
    if MODE == "corrected" and when < TODAY:
        return _page(
            "Schedule a post", _schedule_form(post_title, publish_date, "Publish date cannot be in the past."), 422
        )
    post = {"id": uuid4().hex[:8], "title": title, "publish_date": when.isoformat(),
            "created_at": datetime.now(UTC).isoformat()}
    with _lock:
        data = _load_all()
        _ws(data, _ws_id(request))["posts"][post["id"]] = post
        _save_all(data)
    return RedirectResponse(f"/scheduled/{post['id']}?scheduled=1", status_code=303)


@app.get("/scheduled/{post_id}", response_class=HTMLResponse)
def scheduled_post(request: Request, post_id: str, scheduled: int = 0):
    p = _read(request)["posts"].get(post_id)
    if p is None:
        raise HTTPException(404, "Scheduled post not found")
    status = '<p class="status" role="status">Post scheduled.</p>' if scheduled else ""
    return _page(
        "Scheduled post",
        f"<h1>Scheduled post</h1>{status}<dl><dt>Post title</dt><dd>{escape(p['title'])}</dd>"
        f"<dt>Publish date</dt><dd>{escape(p['publish_date'])}</dd></dl>"
        '<a href="/">Back to dashboard</a>',
    )


# --- test harness (POST-only: a browsing agent cannot reach these by navigating) --


@app.post("/__fixture/reset")
def reset():
    with _lock:
        _save_all({"workspaces": {}})
    return {"ok": True}


@app.post("/__fixture/workspaces")
def create_workspace():
    ws = f"ws_{uuid4().hex[:10]}"
    with _lock:
        data = _load_all()
        _ws(data, ws)
        _save_all(data)
    return {"workspace": ws, "cookie": WORKSPACE_COOKIE}
