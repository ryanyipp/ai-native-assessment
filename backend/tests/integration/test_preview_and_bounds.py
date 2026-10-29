"""Preview endpoint (real screenshot, allowed origins only) and recorded click bounds."""

import base64

from fastapi.testclient import TestClient

from flowlens.browser.engine import BrowserEngine, resolve_control
from flowlens.models.contracts import ClickAction, ControlRef, NavigateAction


def test_preview_returns_real_png_and_refuses_other_origins(fixture_server, tmp_path, monkeypatch):
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path / "a"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'p.db').as_posix()}")
    monkeypatch.setenv("FLOWLENS_ALLOWED_ORIGINS", fixture_server.url)
    from flowlens.config import get_settings
    get_settings.cache_clear()
    from flowlens.main import app
    with TestClient(app) as c:
        r = c.post("/api/preview", json={"url": fixture_server.url + "/"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert base64.b64decode(body["image_png_base64"])[:4] == b"\x89PNG" and body["title"].startswith("Dashboard")
        assert c.post("/api/preview", json={"url": "https://example.com/"}).status_code == 400
    get_settings.cache_clear()


async def test_click_records_target_bounds_in_page_coordinates(fixture_server):
    async with BrowserEngine([fixture_server.url]) as eng:
        await eng.execute(NavigateAction(url=fixture_server.url + "/"))
        el = resolve_control(eng.last_observation, ControlRef(role="link", name="Schedule a post"))
        ex = await eng.execute(ClickAction(element_id=el.id))
    b = ex.target_box
    assert b and b["width"] > 0 and b["height"] > 0 and 0 <= b["x"] < 1280 and b["y"] >= 0
