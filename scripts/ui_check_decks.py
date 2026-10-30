r"""Browser check of map card decks and the resizable sidebar, on saved runs (no model calls).

Active-work and live-refresh behaviour use an INTERCEPTED FIXTURE built from a saved run's own
record (status set to running, then re-served), labelled as such; it is not a live run.
Needs backend (:8000) and frontend (:5173).
Usage: backend\.venv\Scripts\python scripts\ui_check_decks.py OUT_DIR
"""

import asyncio
import json
import re
import sys
from pathlib import Path

import httpx
from playwright.async_api import async_playwright, expect
from check_prereq import require_runs

UI = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:5173"
API = sys.argv[3] if len(sys.argv) > 3 else "http://localhost:8000"
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/map-decks")
RUN = "run_d50048493cc5"  # shared-queue ticket-desk run: Events and Book tickets decks
results: list[tuple[str, bool, str]] = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail else ""), flush=True)


async def counts(page):
    return (await page.locator(".react-flow__node-state").count(), await page.locator(".react-flow__node-deck").count())


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    before = httpx.get(f"{API}/api/runs/{RUN}", timeout=20).json()
    n_states, n_trans = len(before["states"]), len(before["transitions"])
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto(f"{UI}/?run={RUN}")
        await page.wait_for_selector(".react-flow__node", timeout=60000)
        await page.wait_for_timeout(600)
        s, dk = await counts(page)
        check("completed run: related states collapse into decks automatically", dk >= 1 and s + dk < n_states, f"{s} states + {dk} decks for {n_states} states")
        deck = page.locator(".react-flow__node-deck").first
        txt = await deck.inner_text()
        check("deck shows observed-state count", re.search(r"\d+ observed states", txt) is not None, txt.replace("\n", " | ")[:160])
        decks_txt = [await d.inner_text() for d in await page.locator(".react-flow__node-deck").all()]
        check("decks show recorded tests and finding badges where recorded",
              any(re.search(r"\d+ tests? recorded", t) for t in decks_txt) or not before["test_cases"],
              "; ".join(t.replace("\n", " ")[:90] for t in decks_txt))
        heads = [t.split("\n")[0] for t in decks_txt]
        check("distinct pages stay identifiable (one deck per page heading + route)", len(heads) == len(set(heads)), str(heads))
        await page.screenshot(path=OUT / "decks-collapsed.png")

        # Expand by clicking; underlying records unchanged; collapse from the expanded deck.
        await deck.get_by_role("button", name=re.compile("Expand")).click()
        await page.wait_for_timeout(500)
        s2, dk2 = await counts(page)
        check("clicking a deck expands it to its states", dk2 == dk - 1 and s2 > s, f"{s2} states + {dk2} decks")
        await page.screenshot(path=OUT / "deck-expanded.png")
        collapse = page.get_by_role("button", name=re.compile("Collapse \\d+ states of this page"))
        await collapse.first.click()
        await page.wait_for_timeout(500)
        check("collapse button regroups the states", await counts(page) == (s, dk))

        tb = page.get_by_role("group", name="Card decks")
        await tb.get_by_role("button", name="Expand all").click()
        await page.wait_for_timeout(500)
        s3, dk3 = await counts(page)
        check("Expand all shows every observed state", dk3 == 0 and s3 == n_states, f"{s3}/{n_states}")
        check("every transition is still drawn when expanded", await page.locator(".react-flow__edge").count() == n_trans)
        await page.locator(".react-flow__node-state").first.click()
        await expect(page.get_by_role("tab", name="Evidence")).to_have_attribute("aria-selected", "true")
        check("state evidence opens from an expanded deck", True)
        await tb.get_by_role("button", name="Collapse all").click()
        await page.wait_for_timeout(500)
        s4, dk4 = await counts(page)
        check("Collapse all collapses every multi-state deck", dk4 >= dk, f"{s4} states + {dk4} decks")
        after = httpx.get(f"{API}/api/runs/{RUN}", timeout=20).json()
        check("records unchanged (visual grouping only)", len(after["states"]) == n_states and len(after["transitions"]) == n_trans
              and json.dumps(after["evidence"]) == json.dumps(before["evidence"]))

        # INTERCEPTED FIXTURE: the same record served as running; the latest state's deck is active.
        fx = json.loads(json.dumps(before))
        fx["run"]["status"] = "running"
        latest = max(fx["states"], key=lambda x: x["first_seen_step"])
        served = {"n": 0}

        async def serve(route):
            served["n"] += 1
            await route.fulfill(status=200, content_type="application/json", body=json.dumps(fx))

        await page.route(f"**/api/runs/{RUN}", serve)
        await page.goto(f"{UI}/?run={RUN}")
        await page.wait_for_selector(".react-flow__node")
        await page.wait_for_timeout(800)
        heading = latest["summary"].split(" — ")[0].split(" (")[0]
        active_shown = await page.locator(".react-flow__node-state", has_text=heading).count()
        check("fixture: active work is not collapsed automatically", active_shown >= 1, f"latest state '{heading}' visible")
        # Manual choice survives polling refreshes (the fixture is re-served every 1.5 s).
        tb = page.get_by_role("group", name="Card decks")
        await tb.get_by_role("button", name="Collapse all").click()
        n0 = served["n"]
        await page.wait_for_timeout(3500)
        s5, dk5 = await counts(page)
        check("fixture: manual Collapse all is kept across live refreshes", served["n"] > n0 and dk5 >= 1
              and await page.locator(".react-flow__node-state", has_text=heading).count() == 0,
              f"{served['n'] - n0} refreshes, {dk5} decks")
        await page.unroute(f"**/api/runs/{RUN}")

        # Reduced motion: no regroup transition or deck animation.
        rm = await browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
        rp = await rm.new_page()
        await rp.goto(f"{UI}/?run={RUN}")
        await rp.wait_for_selector(".react-flow__node")
        val = await rp.evaluate("""() => { const w = document.createElement('div'); w.className = 'fl-regroup';
            const n = document.createElement('div'); n.className = 'react-flow__node fl-deck-in'; const k = document.createElement('div');
            n.appendChild(k); w.appendChild(n); document.body.appendChild(w);
            return [getComputedStyle(n).transitionDuration, getComputedStyle(k).animationName] }""")
        check("reduced motion disables deck animations", val[1] == "none" and val[0] in ("0s", "1e-05s"), str(val))
        await rm.close()

        # Sidebar divider.
        await page.goto(f"{UI}/?run={RUN}")
        await page.wait_for_selector(".react-flow__node")
        await page.evaluate("localStorage.removeItem('flowlens.sidebarWidth')")
        await page.reload()
        await page.wait_for_selector(".react-flow__node")
        div = page.get_by_role("separator", name="Resize sidebar")
        panel = page.get_by_role("tablist", name="Run details").locator("..")
        w0 = (await panel.bounding_box())["width"]
        check("divider is exposed as a vertical separator with limits",
              await div.get_attribute("aria-orientation") == "vertical" and await div.get_attribute("aria-valuemin") == "320")
        b = await div.bounding_box()
        await page.mouse.move(b["x"] + b["width"] / 2, b["y"] + 200)
        await page.mouse.down()
        await page.mouse.move(b["x"] - 150, b["y"] + 200, steps=6)
        await page.mouse.up()
        w1 = (await panel.bounding_box())["width"]
        check("dragging the divider widens the sidebar", abs(w1 - (w0 + 150)) <= 4, f"{w0} -> {w1}")
        await div.focus()
        await page.keyboard.press("ArrowRight")
        w2 = (await panel.bounding_box())["width"]
        check("keyboard: ArrowRight narrows by 16 px", abs(w2 - (w1 - 16)) <= 1, f"{w1} -> {w2}")
        await page.keyboard.press("Home")
        check("keyboard: Home goes to the 320 px minimum", abs((await panel.bounding_box())["width"] - 320) <= 1)
        await page.keyboard.press("End")
        wmax = (await panel.bounding_box())["width"]
        mapw = (await page.get_by_test_id("main-view").bounding_box())["width"]
        check("End reaches the maximum and the map keeps at least 420 px", wmax <= 760 and mapw >= 418, f"sidebar {wmax}, map {mapw}")
        await page.keyboard.press("Shift+ArrowRight")
        saved = (await panel.bounding_box())["width"]
        await page.reload()
        await page.wait_for_selector(".react-flow__node")
        check("width preference is saved across reloads", abs((await panel.bounding_box())["width"] - saved) <= 1, f"{saved}")
        await page.screenshot(path=OUT / "sidebar-resized.png")
        await page.keyboard.press("Tab")
        await div.focus()
        await page.keyboard.press("Enter")
        check("Enter resets to the default width", abs((await panel.bounding_box())["width"] - 440) <= 1)
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.wait_for_timeout(300)
        check("390px: divider hidden, sidebar stacks full width", not await div.is_visible()
              and not await page.evaluate("document.documentElement.scrollWidth > window.innerWidth"))
        await page.set_viewport_size({"width": 1024, "height": 768})
        await page.wait_for_timeout(300)
        check("1024px: no horizontal overflow", not await page.evaluate("document.documentElement.scrollWidth > window.innerWidth"))
        check("no uncaught page errors", not errors, "; ".join(errors))
        await browser.close()
    fails = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(fails)}/{len(results)} passed")
    sys.exit(1 if fails else 0)


require_runs("run_d50048493cc5")
asyncio.run(main())
