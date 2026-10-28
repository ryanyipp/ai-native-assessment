"""Creator Studio: the controlled creator-dashboard fixture FlowLens reviews.

Server-rendered so a reload is a real fresh navigation. Drafts persist in a
JSON file (CREATOR_STUDIO_DATA), so they survive both page reloads and fixture
restarts. Run:  uvicorn app:app --port 5174   (from this directory)
"""

from __future__ import annotations

import json
import os
import threading
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

DATA_PATH = Path(os.environ.get("CREATOR_STUDIO_DATA", Path(__file__).parent / "data" / "drafts.json"))
_lock = threading.Lock()

app = FastAPI(title="Creator Studio fixture", docs_url=None, redoc_url=None, openapi_url=None)


def _load() -> dict[str, dict]:
    if not DATA_PATH.exists():
        return {}
    return json.loads(DATA_PATH.read_text("utf-8"))


def _save(drafts: dict[str, dict]) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = DATA_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(drafts, indent=2), "utf-8")
    tmp.replace(DATA_PATH)


def _page(title: str, body: str) -> HTMLResponse:
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
</style></head><body>
<header><strong>Creator Studio</strong><nav aria-label="Main"><a href="/">Dashboard</a></nav></header>
<main>{body}</main></body></html>"""
    )


def _form(action: str, button: str, title: str = "", caption: str = "") -> str:
    return f"""<form method="post" action="{action}">
<label for="title">Title</label><input id="title" name="title" value="{escape(title)}" maxlength="120">
<label for="caption">Caption</label><textarea id="caption" name="caption" rows="4" maxlength="2200">{escape(caption)}</textarea>
<button type="submit">{button}</button></form>"""


@app.get("/", response_class=HTMLResponse)
def dashboard():
    drafts = sorted(_load().values(), key=lambda d: d["updated_at"], reverse=True)
    items = "".join(
        f'<li><a href="/drafts/{d["id"]}">{escape(d["title"] or "(untitled)")}</a></li>' for d in drafts
    )
    listing = f"<ul aria-label=\"Drafts\">{items}</ul>" if items else "<p>No drafts yet.</p>"
    return _page(
        "Dashboard",
        f'<h1>Dashboard</h1><a class="button" href="/drafts/new">New draft</a><h2>Your drafts</h2>{listing}',
    )


@app.get("/drafts/new", response_class=HTMLResponse)
def new_draft():
    return _page("New draft", "<h1>New draft</h1>" + _form("/drafts", "Save draft"))


@app.post("/drafts")
def create_draft(title: str = Form(""), caption: str = Form("")):
    now = datetime.now(UTC).isoformat()
    draft = {"id": uuid4().hex[:8], "title": title, "caption": caption, "created_at": now, "updated_at": now}
    with _lock:
        drafts = _load()
        drafts[draft["id"]] = draft
        _save(drafts)
    return RedirectResponse(f"/drafts/{draft['id']}?saved=1", status_code=303)


@app.get("/drafts/{draft_id}", response_class=HTMLResponse)
def edit_draft(draft_id: str, saved: int = 0):
    d = _load().get(draft_id)
    if d is None:
        raise HTTPException(404, "Draft not found")
    status = '<p class="status" role="status">Draft saved.</p>' if saved else ""
    return _page(
        "Edit draft",
        f"<h1>Edit draft</h1>{status}" + _form(f"/drafts/{draft_id}", "Save changes", d["title"], d["caption"]),
    )


@app.post("/drafts/{draft_id}")
def update_draft(draft_id: str, title: str = Form(""), caption: str = Form("")):
    with _lock:
        drafts = _load()
        if draft_id not in drafts:
            raise HTTPException(404, "Draft not found")
        drafts[draft_id].update(title=title, caption=caption, updated_at=datetime.now(UTC).isoformat())
        _save(drafts)
    return RedirectResponse(f"/drafts/{draft_id}?saved=1", status_code=303)


@app.post("/__fixture/reset")
def reset():
    """Test-harness reset. POST-only so a browsing agent cannot trigger it by navigating."""
    with _lock:
        _save({})
    return {"ok": True}
