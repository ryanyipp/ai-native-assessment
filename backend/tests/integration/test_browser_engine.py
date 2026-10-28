"""Browser engine against the real fixture in real Chromium (no mocks)."""

from flowlens.browser.engine import BrowserEngine, state_signature
from flowlens.models.contracts import ClickAction, FillAction, NavigateAction, ReloadAction


def by_name(obs, name, role=None):
    return next(e for e in obs.elements if e.name == name and (role is None or e.role == role))


async def test_inspect_lists_labelled_controls(fixture_server):
    async with BrowserEngine([fixture_server.url]) as b:
        ex = await b.execute(NavigateAction(url=fixture_server.url + "/"))
        assert ex.ok, ex.error
        names = {(e.role, e.name) for e in ex.observation.elements}
        assert ("link", "New draft") in names
        assert ex.observation.headings[0] == "Dashboard"
        assert ex.screenshot_png[:4] == b"\x89PNG"


async def test_create_save_reload_persists(fixture_server):
    async with BrowserEngine([fixture_server.url]) as b:
        await b.execute(NavigateAction(url=fixture_server.url + "/drafts/new"))
        obs = b.last_observation
        assert (await b.execute(FillAction(element_id=by_name(obs, "Title").id, value="Launch teaser"))).ok
        assert (await b.execute(FillAction(element_id=by_name(obs, "Caption").id, value="Coming soon #fyp"))).ok
        filled_sig, _ = state_signature(b.last_observation)
        saved = await b.execute(ClickAction(element_id=by_name(b.last_observation, "Save draft").id))
        assert saved.ok, saved.error
        assert "/drafts/" in saved.url_after and saved.url_after != saved.url_before
        assert "Draft saved." in saved.observation.status_messages
        sig_saved, route = state_signature(saved.observation)
        assert route == "/drafts/:id" and sig_saved != filled_sig

        reloaded = await b.execute(ReloadAction())
        assert reloaded.ok
        assert by_name(reloaded.observation, "Title").value == "Launch teaser"
        assert by_name(reloaded.observation, "Caption").value == "Coming soon #fyp"

    # Persistence is server-side: a brand-new browser context sees the draft too.
    async with BrowserEngine([fixture_server.url]) as b2:
        ex = await b2.execute(NavigateAction(url=fixture_server.url + "/"))
        assert any(e.name == "Launch teaser" for e in ex.observation.elements)


async def test_disallowed_origin_rejected_without_navigating(fixture_server):
    async with BrowserEngine([fixture_server.url]) as b:
        await b.execute(NavigateAction(url=fixture_server.url + "/"))
        ex = await b.execute(NavigateAction(url="https://example.com/"))
        assert not ex.ok and "not in the allowed" in ex.error
        assert ex.url_after.startswith(fixture_server.url)


async def test_unknown_or_unfillable_element_is_recorded_failure(fixture_server):
    async with BrowserEngine([fixture_server.url]) as b:
        await b.execute(NavigateAction(url=fixture_server.url + "/"))
        ex = await b.execute(ClickAction(element_id="e999"))
        assert not ex.ok and "not in the latest observation" in ex.error
        link = by_name(b.last_observation, "New draft")
        ex = await b.execute(FillAction(element_id=link.id, value="x"))
        assert not ex.ok and "not fillable" in ex.error


async def test_relative_navigate_resolves_against_current_origin(fixture_server):
    async with BrowserEngine([fixture_server.url]) as b:
        await b.execute(NavigateAction(url=fixture_server.url + "/"))
        ex = await b.execute(NavigateAction(url="/drafts/new"))
        assert ex.ok and ex.observation.headings == ["New draft"]
