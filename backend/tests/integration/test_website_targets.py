"""Generic website targets: launcher-approved origins, scope enforcement (including redirects),
Enter and checkbox actions, and same-named controls told apart by their list item."""

import base64
import socket
import threading
import time

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.testclient import TestClient

from flowlens.api.runs import normalise_origin
from flowlens.browser.engine import BrowserEngine, ControlResolutionError, resolve_control, state_signature
from flowlens.models.contracts import (
    CheckAction,
    ClickAction,
    ControlRef,
    FillAction,
    NavigateAction,
    PressAction,
    ReloadAction,
    SemanticStep,
)
from flowlens.orchestration.replay import execute_step
from flowlens.orchestration.runner import relative_path, semantic_step

TODO_PAGE = """<!doctype html><html><head><title>Todos</title></head><body>
<h1>todos</h1>
<input class="new" placeholder="What needs to be done?" aria-label="What needs to be done?">
<ul id="list"></ul>
<a href="#/">All</a> <a href="#/active">Active</a> <a href="#/completed">Completed</a>
<a id="out" href="/redirect-out">Leave</a>
<script>
const items = JSON.parse(localStorage.getItem('t') || '[]');
const save = () => localStorage.setItem('t', JSON.stringify(items));
function render() {
  const f = location.hash.replace('#/', '');
  const ul = document.getElementById('list'); ul.innerHTML = '';
  items.filter(i => f === 'active' ? !i.done : f === 'completed' ? i.done : true).forEach(i => {
    const li = document.createElement('li');
    const cb = document.createElement('input'); cb.type = 'checkbox'; cb.setAttribute('aria-label', 'Toggle Todo');
    cb.checked = i.done; cb.onchange = () => { i.done = cb.checked; save(); render(); };
    const label = document.createElement('label'); label.textContent = i.title;
    li.append(cb, label); ul.append(li);
  });
}
document.querySelector('.new').addEventListener('keydown', e => {
  if (e.key === 'Enter' && e.target.value.trim()) { items.push({title: e.target.value.trim(), done: false});
    e.target.value = ''; save(); render(); }
});
window.addEventListener('hashchange', render); render();
</script></body></html>"""


def _port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Site:
    def __init__(self, app):
        self.port = _port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="warning"))
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def __enter__(self):
        self.thread.start()
        for _ in range(100):
            try:
                httpx.get(self.url + "/", timeout=0.5)
                return self
            except httpx.HTTPError:
                time.sleep(0.05)
        raise RuntimeError("site did not start")

    def __exit__(self, *a):
        self.server.should_exit = True
        self.thread.join(timeout=5)


@pytest.fixture
def sites():
    other = FastAPI()
    other.get("/", response_class=HTMLResponse)(lambda: "<title>Elsewhere</title><h1>Another origin</h1>")
    with Site(other) as o:
        app = FastAPI()
        app.get("/", response_class=HTMLResponse)(lambda: TODO_PAGE)
        app.get("/redirect-in")(lambda: RedirectResponse("/#/active", 302))
        app.get("/redirect-out")(lambda: RedirectResponse(o.url + "/", 302))
        app.get("/chain-out")(lambda: RedirectResponse("/redirect-out", 302))
        with Site(app) as s:
            yield s, o


async def test_redirects_out_of_scope_are_blocked_and_nothing_is_captured(sites):
    site, other = sites
    async with BrowserEngine([site.url]) as eng:
        ok = await eng.execute(NavigateAction(url=site.url + "/redirect-in"))
        assert ok.ok and ok.url_after == site.url + "/#/active"
        for path in ("/redirect-out", "/chain-out"):  # one hop and two hops
            ex = await eng.execute(NavigateAction(url=site.url + path))
            assert not ex.ok and "left the approved scope" in ex.error and other.url in ex.error
            assert ex.url_after.startswith(site.url) or ex.url_after == "about:blank"
            assert "Another origin" not in ex.observation.text_excerpt
        # A link that redirects off-site is blocked too.
        await eng.execute(NavigateAction(url=site.url + "/"))
        leave = resolve_control(eng.last_observation, ControlRef(role="link", name="Leave"))
        ex = await eng.execute(ClickAction(element_id=leave.id))
        assert not ex.ok and "left the approved scope" in ex.error
        assert "Another origin" not in ex.observation.text_excerpt
        # Direct navigation to another origin is refused before loading.
        ex = await eng.execute(NavigateAction(url=other.url + "/"))
        assert not ex.ok and "rejected" in ex.error


async def test_enter_checkbox_filters_and_reload(sites):
    site, _ = sites
    async with BrowserEngine([site.url]) as eng:
        await eng.execute(NavigateAction(url=site.url + "/"))
        for title in ("Buy milk", "Walk dog"):
            box = resolve_control(eng.last_observation, ControlRef(role="textbox", name="What needs to be done?"))
            assert (await eng.execute(FillAction(element_id=box.id, value=title))).ok
            ex = await eng.execute(PressAction(element_id=box.id, key="Enter"))
            assert ex.ok, ex.error
        toggles = [e for e in ex.observation.elements if e.name == "Toggle Todo"]
        assert [t.context for t in toggles] == ["Buy milk", "Walk dog"] and all(t.checked is False for t in toggles)
        assert all(t.name_shared for t in toggles)
        before = state_signature(ex.observation)[0]
        ex = await eng.execute(CheckAction(element_id=toggles[0].id, checked=True))
        assert ex.ok and "in 'Buy milk'" in ex.target_description
        assert next(e for e in ex.observation.elements if e.context == "Buy milk").checked is True
        assert state_signature(ex.observation)[0] != before  # completing a todo is a new state
        # Recorded by meaning, including which row: replay resolves the same checkbox.
        step = semantic_step(CheckAction(element_id=toggles[0].id, checked=False).model_dump(), ex)
        assert step.control.context == "Buy milk" and step.checked is False
        assert step.describe() == "uncheck checkbox 'Toggle Todo' in 'Buy milk'"
        # Fill is refused on a checkbox, and check on a textbox.
        assert "use check" in (await eng.execute(FillAction(element_id=toggles[1].id, value="x"))).error
        box = resolve_control(ex.observation, ControlRef(role="textbox", name="What needs to be done?"))
        assert "not a checkbox" in (await eng.execute(CheckAction(element_id=box.id))).error
        # Hash filters, and the fragment is kept in recorded paths.
        active = resolve_control(eng.last_observation, ControlRef(role="link", name="Active"))
        ex = await eng.execute(ClickAction(element_id=active.id))
        assert ex.ok and relative_path(ex.url_after) == "/#/active"
        assert [e.name for e in ex.observation.elements].count("Toggle Todo") == 1
        # Alone under a filter, the row's checkbox still resolves by its recorded row text.
        only = resolve_control(ex.observation, ControlRef(role="checkbox", name="Toggle Todo", context="Walk dog"))
        assert only.context == "Walk dog" and not only.name_shared
        with pytest.raises(ControlResolutionError):  # the completed row is not shown: no guess
            resolve_control(ex.observation, ControlRef(role="checkbox", name="Toggle Todo", context="Buy milk"))
        ex = await eng.execute(ReloadAction())
        assert ex.ok and "Walk dog" in ex.observation.text_excerpt and "Buy milk" not in ex.observation.text_excerpt
        # A recorded press step replays through the same engine path.
        await eng.execute(NavigateAction(url=site.url + "/"))
        box = resolve_control(eng.last_observation, ControlRef(role="textbox", name="What needs to be done?"))
        await eng.execute(FillAction(element_id=box.id, value="Third"))
        _, ex = await execute_step(eng, site.url, SemanticStep(
            type="press", control=ControlRef(role="textbox", name="What needs to be done?"), key="Enter"))
        assert ex.ok and "Third" in ex.observation.text_excerpt


def test_normalise_origin():
    assert normalise_origin("https://Demo.Playwright.dev/todomvc/#/") == "https://demo.playwright.dev"
    assert normalise_origin("https://demo.playwright.dev:443/x") == "https://demo.playwright.dev"
    assert normalise_origin("http://127.0.0.1:5176/") == "http://127.0.0.1:5176"
    for bad in ("ftp://example.com/", "javascript:alert(1)", "https://user:pw@example.com/", "not a url"):
        with pytest.raises(ValueError):
            normalise_origin(bad)


def test_launcher_approval_scopes_preview_and_runs(sites, tmp_path, monkeypatch):
    site, other = sites
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path / "a"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'w.db').as_posix()}")
    monkeypatch.setenv("FLOWLENS_ALLOWED_ORIGINS", "http://127.0.0.1:5174")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    from flowlens.config import get_settings
    get_settings.cache_clear()
    from flowlens.main import app
    with TestClient(app) as c:
        assert c.post("/api/preview", json={"url": site.url + "/"}).status_code == 400  # not approved yet
        r = c.post("/api/origins", json={"url": site.url + "/some/path?q=1"})
        assert r.status_code == 201 and r.json() == {"origin": site.url, "profile": "website", "already_configured": False}
        assert site.url in c.get("/api/health").json()["approved_origins"]
        p = c.post("/api/preview", json={"url": site.url + "/"}).json()
        assert p["ok"] and p["profile"] == "website" and base64.b64decode(p["image_png_base64"])[:4] == b"\x89PNG"
        # Approving one origin does not approve the origin it redirects to: no image is returned.
        p = c.post("/api/preview", json={"url": site.url + "/redirect-out"}).json()
        assert not p["ok"] and "approved scope" in p["error"] and p["image_png_base64"] is None and p["title"] is None
        assert c.post("/api/preview", json={"url": other.url + "/"}).status_code == 400
        # Fixture origins stay configured in .env and keep the fixture profile.
        r = c.post("/api/origins", json={"url": "http://127.0.0.1:5174/"})
        assert r.json()["profile"] == "fixture" and r.json()["already_configured"]
        assert c.post("/api/origins", json={"url": "ftp://x.test/"}).status_code == 400
        assert c.delete("/api/origins", params={"origin": site.url}).json()["revoked"] is True
        assert c.post("/api/preview", json={"url": site.url + "/"}).status_code == 400
    get_settings.cache_clear()


def test_run_records_website_profile_and_scope(sites, tmp_path):
    """Run creation records the profile and scope; the website provider gives plain fresh contexts."""
    from flowlens.api.runs import scope_for
    from flowlens.config import Settings
    from flowlens.models.contracts import Run, RunLimits
    from flowlens.services.test_data import FreshContextProvider, WorkspaceProvider, session_provider
    from flowlens.storage.db import Store

    site, _ = sites
    s = Settings(_env_file=None, artifacts_dir=tmp_path / "a", flowlens_allowed_origins="http://127.0.0.1:5174")
    store = Store(tmp_path / "s.db")
    assert scope_for(site.url, s, store) is None
    store.approve_origin(site.url, "2026-10-30T00:00:00")
    assert scope_for(site.url, s, store) == ("website", [site.url])
    assert scope_for("http://127.0.0.1:5174", s, store) == ("fixture", ["http://127.0.0.1:5174"])
    lim = RunLimits(max_steps=1, max_model_calls=1, max_cost_usd=0.01, max_output_tokens=100)
    web = Run(target_url=site.url + "/", goal="add todos", model="m", limits=lim, target_profile="website",
              scope_origins=[site.url])
    prov = session_provider(web, s)
    assert isinstance(prov, FreshContextProvider)
    ctx = prov.provision(site.url, "explorer-a:t1")
    assert ctx.cookies == [] and ctx.context_id == "explorer-a:t1:fresh-context"
    assert "not isolated" in prov.isolation
    old = Run(target_url="http://127.0.0.1:5174/", goal="old run", model="m", limits=lim)
    assert old.target_profile == "fixture" and isinstance(session_provider(old, s), WorkspaceProvider)
