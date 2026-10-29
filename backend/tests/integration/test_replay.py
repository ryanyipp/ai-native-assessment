"""Semantic replay in fresh contexts, against the real fixture and Chromium (no model)."""

import httpx
import pytest

from flowlens.browser.engine import BrowserEngine, ControlResolutionError, resolve_control, state_signature
from flowlens.models.contracts import (
    Assertion,
    ControlRef,
    NavigateAction,
    Observation,
    ObservedElement,
    SemanticStep,
    SetupRecipe,
)
from flowlens.orchestration.replay import execute_step, reach_state
from flowlens.services.test_data import WorkspaceProvider
from flowlens.verification.assertions import evaluate


async def _noop(*_):
    return None


async def test_recipe_resolves_controls_from_fresh_observation(fixture_server):
    url = fixture_server.url
    provider = WorkspaceProvider("/__fixture/workspaces", "cs_ws")

    def draft(ctx, title):
        httpx.post(url + "/drafts", data={"title": title, "caption": ""}, cookies={"cs_ws": ctx.cookies[0]["value"]})

    target = ControlRef(role="link", name="Target draft")
    # Original session: the target draft is the only one.
    a = provider.provision(url, "orig")
    draft(a, "Target draft")
    async with BrowserEngine([url], cookies=a.cookies) as eng:
        await eng.execute(NavigateAction(url=url + "/"))
        orig_id = resolve_control(eng.last_observation, target).id
        _, ex = await execute_step(eng, url, SemanticStep(type="click", control=target))
        expected = state_signature(ex.observation)[0]
    # Fresh workspace: newer drafts are listed first, so the stored element id is stale.
    b = provider.provision(url, "fresh")
    for t in ("Target draft", "Newer 1", "Newer 2"):
        draft(b, t)
    recipe = SetupRecipe(target_state_id="s", expected_signature=expected, direct_path=None,
                         steps=[SemanticStep(type="navigate", path="/"), SemanticStep(type="click", control=target)])
    seen = []

    async def record(action, ex, label):
        seen.append((action, ex))

    async with BrowserEngine([url], cookies=b.cookies) as eng:
        reached = await reach_state(eng, url, recipe, record)
    assert reached.ok and reached.strategy == "recipe"
    clicked = seen[1][0]["element_id"]
    assert clicked != orig_id  # resolved afresh; reusing the old id would have opened another draft
    assert seen[1][1].target_element.name == "Target draft"


async def test_unreachable_state_is_an_explicit_setup_failure(fixture_server):
    url = fixture_server.url
    recipe = SetupRecipe(target_state_id="s", expected_signature="0" * 16, direct_path="/schedule/new", steps=[
        SemanticStep(type="navigate", path="/"),
        SemanticStep(type="click", control=ControlRef(role="link", name="No such link")),
    ])
    async with BrowserEngine([url]) as eng:
        reached = await reach_state(eng, url, recipe, _noop)
    assert not reached.ok and "No such link" in reached.error and "direct path reached a different state" in reached.error


def _obs(elements, **kw):
    return Observation(url=kw.pop("url", "http://h/schedule"), title="t",
                       elements=[ObservedElement(id=f"e{i}", tag="button", **e) for i, e in enumerate(elements, 1)], **kw)


def test_ambiguous_or_missing_control_is_an_error():
    obs = _obs([{"role": "button", "name": "Save"}, {"role": "button", "name": "Save"}])
    with pytest.raises(ControlResolutionError, match="ambiguous"):
        resolve_control(obs, ControlRef(role="button", name="Save"))
    with pytest.raises(ControlResolutionError, match="no button 'Publish'"):
        resolve_control(obs, ControlRef(role="button", name="Publish"))
    assert resolve_control(_obs([{"role": "button", "name": " save "}]), ControlRef(role="button", name="Save")).id == "e1"


def test_assertions_evaluate_observations():
    rejected = _obs([], url="http://h/schedule", alert_messages=["Publish date cannot be in the past."],
                    status_messages=["Publish date cannot be in the past."], headings=["Schedule a post"])
    accepted = _obs([], url="http://h/scheduled/ab12cd34?scheduled=1", status_messages=["Post scheduled."],
                    headings=["Scheduled post"], text_excerpt="Post scheduled. Publish date 2026-06-01")
    start = "http://h/schedule/new"
    vm = Assertion(type="validation_message_present", params={})
    assert evaluate(vm, rejected, start).passed and not evaluate(vm, accepted, start).passed  # status != validation
    assert evaluate(Assertion(type="validation_message_present", params={"text_contains": "past"}), rejected, start).passed
    nav = Assertion(type="navigation_reached", params={"route": "/scheduled/:id", "expect_reached": False})
    assert evaluate(nav, rejected, start).passed and not evaluate(nav, accepted, start).passed
    ev = Assertion(type="element_visible", params={"name": "Scheduled post", "role": "heading", "expect_visible": False})
    assert evaluate(ev, rejected, start).passed and not evaluate(ev, accepted, start).passed
    tr = Assertion(type="text_or_value_retained", params={"expected": "2026-06-01"})
    assert evaluate(tr, accepted, start).passed
    sc = Assertion(type="state_condition", params={"condition": "left_start_route"})
    assert evaluate(sc, accepted, start).passed
