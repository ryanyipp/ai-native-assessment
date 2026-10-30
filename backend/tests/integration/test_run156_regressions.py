"""Regressions from run_156b7b84dc3b (automationexercise.com, shared queue, partial).

Causes found in its saved records and reproduced with the browser engine (no model calls):
1. A Google ad interstitial (<iframe id="aswift_3" title="Advertisement"> inside
   <ins class="adsbygoogle" data-vignette-loaded>) covered the page; clicks timed out at 5 s.
2. Rotating ad links changed state fingerprints on every visit, so setup recipes "reached a
   different state" and 5 explore tasks failed.
3. "View Cart" appears only after add-to-cart returns; replay looked for it too early.
4. Tester planning calls sent a reasoning token budget the provider ignored (1342 and 2684 hidden
   reasoning tokens against 384), so replies were cut off; doubling the cap did not help.
"""

import socket
import threading
import time
from types import SimpleNamespace

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from flowlens.browser.engine import BrowserEngine, interceptor_of, is_ad_host, resolve_control, state_signature
from flowlens.models.contracts import ClickAction, ControlRef, ModelCall, NavigateAction, SemanticStep, Task
from flowlens.orchestration.replay import execute_step
from flowlens.orchestration.review import ReviewRun, reasoning_starved
from flowlens.orchestration.runner import relative_path
from flowlens.services.llm import reasoning_request
from flowlens.services.report import plain_stop

# Trimmed from the real Playwright call log reproduced for run_156b7b84dc3b.
REAL_TRACE = '''Locator.click: Timeout 5000ms exceeded.
Call log:
  - waiting for locator("[data-flowlens-id=\\"e35\\"]")
    - locator resolved to <a data-flowlens-id="e35" href="/product_details/2">…</a>
  - attempting click action
      - <iframe width="" height="" tabindex="0" id="aswift_3" name="aswift_3" title="Advertisement" aria-label="Advertisement" src="https://googleads.g.double…></iframe> from <ins tabindex="0" aria-hidden="false" data-ad-status="filled" data-vignette-loaded="true" class="adsbygoogle adsbygoogle-noablate">…</ins> subtree intercepts pointer events
    - retrying click action'''

PAGE = """<!doctype html><title>Shop</title><h1>Shop</h1>
<a href="/next">Next page</a>
<ins class="adsbygoogle"><a href="https://ads.example/x">Compare Broadband</a></ins>
<img src="https://pagead2.googlesyndication.com/pagead/x.gif" alt="">
<div id="cover" style="position:fixed;inset:0;background:rgba(0,0,0,.4);display:none"></div>
<button id="add">Add to cart</button>
<script>
const cover = document.getElementById('cover');
const mode = new URLSearchParams(location.search).get('cover');
if (mode) cover.style.display = 'block';
document.addEventListener('keydown', e => { if (e.key === 'Escape' && mode === 'escape') cover.style.display = 'none'; });
document.getElementById('add').onclick = () => setTimeout(() => {
  const a = document.createElement('a'); a.href = '/next'; a.textContent = 'View Cart'; document.body.append(a); }, 700);
</script>"""


def _port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def shop():
    app = FastAPI()
    app.get("/", response_class=HTMLResponse)(lambda: PAGE)
    app.get("/next", response_class=HTMLResponse)(lambda: "<title>Next</title><h1>Next</h1>")
    port = _port()
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=srv.run, daemon=True)
    th.start()
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            httpx.get(url + "/", timeout=0.5)
            break
        except httpx.HTTPError:
            time.sleep(0.05)
    yield url
    srv.should_exit = True
    th.join(timeout=5)


def test_interceptor_is_named_from_the_real_trace():
    assert interceptor_of(REAL_TRACE) == ('<iframe id="aswift_3" title="Advertisement" aria-label="Advertisement"> '
                                          'inside <ins class="adsbygoogle adsbygoogle-noablate">')
    assert interceptor_of("Locator.click: Timeout 5000ms exceeded.\nCall log:\n  - element is not visible") is None


async def test_ads_are_blocked_and_ignored_so_fingerprints_are_stable(shop):
    sigs = set()
    for _ in range(2):
        async with BrowserEngine([shop]) as eng:
            ex = await eng.execute(NavigateAction(url=shop + "/"))
            assert eng.blocked_ad_requests >= 1  # the ad-network image never left the browser
            assert "Compare Broadband" not in [e.name for e in ex.observation.elements]
            sigs.add(state_signature(ex.observation)[0])
    assert len(sigs) == 1
    assert is_ad_host("https://googleads.g.doubleclick.net/pagead/x") and not is_ad_host(shop)
    assert relative_path("https://automationexercise.com/products#google_vignette") == "/products"
    assert relative_path("https://x.test/todomvc/#/active") == "/todomvc/#/active"


async def test_covered_click_recovers_once_with_escape(shop):
    async with BrowserEngine([shop]) as eng:
        await eng.execute(NavigateAction(url=shop + "/?cover=escape"))
        link = resolve_control(eng.last_observation, ControlRef(role="link", name="Next page"))
        ex = await eng.execute(ClickAction(element_id=link.id))
    assert ex.ok and ex.url_after == shop + "/next"
    assert ex.recovery and 'id="cover"' in ex.recovery and "retry succeeded" in ex.recovery


async def test_cover_that_stays_fails_bounded_with_full_trace(shop):
    async with BrowserEngine([shop]) as eng:
        await eng.execute(NavigateAction(url=shop + "/?cover=stay"))
        link = resolve_control(eng.last_observation, ControlRef(role="link", name="Next page"))
        t0 = time.monotonic()
        ex = await eng.execute(ClickAction(element_id=link.id))
        took = time.monotonic() - t0
    assert not ex.ok and ex.error.startswith("blocked: <div id=\"cover\"> covers the element")
    assert "intercepts pointer events" in ex.error_detail and "retry after Escape" in ex.error_detail
    assert "still covered" in ex.recovery
    assert took < 5 + 2 + 3  # one normal attempt, one short retry; never an open-ended wait
    assert ex.url_after.startswith(shop + "/?cover")  # not forced through the cover


async def test_replay_waits_briefly_for_a_control_that_appears_after_a_request(shop):
    async with BrowserEngine([shop]) as eng:
        await eng.execute(NavigateAction(url=shop + "/"))
        add = resolve_control(eng.last_observation, ControlRef(role="button", name="Add to cart"))
        await eng.execute(ClickAction(element_id=add.id))
        _, ex = await execute_step(eng, shop, SemanticStep(type="click", control=ControlRef(role="link", name="View Cart")))
    assert ex.ok and ex.url_after == shop + "/next"


def test_reasoning_settings_and_starved_retry():
    assert reasoning_request(None) == {"effort": "low", "exclude": True}
    assert reasoning_request(0) == {"effort": "minimal", "exclude": True}
    starved = ModelCall(run_id="r", step=1, model="m", latency_ms=1, ok=True, completion_tokens=1385,
                        reasoning_tokens=1342, finish_reason="length")
    assert reasoning_starved(starved)
    assert not reasoning_starved(starved.model_copy(update={"reasoning_tokens": 100}))


async def test_planning_retry_uses_minimal_reasoning_not_a_bigger_cap():
    calls = []
    store = {}

    async def call_model(msgs, *, max_tokens, reasoning_tokens, **kw):
        calls.append((max_tokens, reasoning_tokens))
        mc = ModelCall(run_id="r", step=1, model="m", latency_ms=1, ok=True, completion_tokens=1385,
                       reasoning_tokens=1342, finish_reason="length")
        store[mc.id] = mc
        return ('{"reasoning": "cut', mc.id) if len(calls) == 1 else ('{"ok": true}', mc.id)

    lim = SimpleNamespace(max_output_tokens_planning=1400)
    fake = SimpleNamespace(run=SimpleNamespace(limits=lim), holds={}, call_model=call_model,
                           store=SimpleNamespace(get=lambda cls, i: store.get(i)), event=lambda *a, **k: None)

    def parse(c):
        if not c.endswith("}"):
            raise ValueError("Invalid JSON: EOF while parsing a string")
        return c

    task = Task(run_id="r", key="k")
    out, _ = await ReviewRun.model(fake, [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}],
                                   agent_id="input-tester", phase="input_test", task=task, parse=parse)
    assert out == '{"ok": true}'
    assert calls == [(1400, None), (1400, 0)]  # effort low, then minimal at the same cap


def test_report_names_the_real_cause_of_a_drained_queue():
    tasks = [SimpleNamespace(type="explore", status=SimpleNamespace(value="failed"),
                             note="failed after 2 attempt(s): SetupFailed: could not reach X: direct path reached a different state")] * 5 + \
            [SimpleNamespace(type="input_test", status=SimpleNamespace(value="blocked"),
                             note="input-tester produced invalid replies: truncated at the output limit; invalid test plan")] * 2
    text = plain_stop("partial", "queue drained; tasks {'done': 2, 'blocked': 2, 'failed': 5}", tasks)
    assert text.startswith("no work was left that could run")
    assert "5 page(s) to explore failed because their starting page could not be recreated" in text
    assert "2 form(s) to test were blocked because the agent's replies were cut off" in text
    assert "limit" not in text
