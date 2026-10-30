"""Browser check of the FlowLens UI against the running app and a saved real run.

Needs the backend (:8000) and frontend dev server (:5173) running. Makes no model calls.
Usage (repo root):
  backend\\.venv\\Scripts\\python scripts\\ui_check.py run_e957eab8645e docs\\ui-iteration
"""

import asyncio
import os
import json
import sys
from pathlib import Path

from playwright.async_api import Page, async_playwright, expect

UI = os.environ.get("FLOWLENS_UI", "http://localhost:5173")
RUN = sys.argv[1] if len(sys.argv) > 1 else "run_e957eab8645e"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "docs/ui-iteration")
AXE = Path(__file__).resolve().parents[1] / "frontend" / "node_modules" / "axe-core" / "axe.min.js"
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail else ""))


async def axe(page: Page, label: str) -> None:
    await page.add_script_tag(path=str(AXE))
    res = await page.evaluate("async () => (await axe.run(document, {resultTypes: ['violations']})).violations"
                              ".map(v => ({id: v.id, impact: v.impact, n: v.nodes.length, t: v.nodes[0]?.target}))")
    serious = [v for v in res if v["impact"] in ("serious", "critical")]
    check(f"axe {label}: no serious/critical violations", not serious, json.dumps(res))


async def expand_all(page):
    """Card decks collapse related states; per-state checks expand them first (display only)."""
    b = page.get_by_role("button", name="Expand all")
    if await b.count() and await b.is_enabled():
        await b.click()
        await page.wait_for_timeout(500)


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1440, "height": 900})
        page = await ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        await page.goto(f"{UI}/?run={RUN}")
        await page.wait_for_selector(".react-flow__node")
        await page.wait_for_timeout(600)
        await expand_all(page)
        check("map renders states", await page.locator(".react-flow__node").count() == 5)
        check("map renders transition labels", await page.get_by_role("button", name="Transition step").count() == 5)
        await axe(page, "workspace")

        # Keyboard stepping from the page body.
        await page.locator("body").focus()
        await page.keyboard.press("ArrowRight")
        await expect(page.get_by_text("Step 1 of 5")).to_be_visible()
        for _ in range(3):
            await page.keyboard.press("ArrowRight")
        await expect(page.get_by_text("Step 4 of 5")).to_be_visible()
        await page.keyboard.press("ArrowLeft")
        await expect(page.get_by_text("Step 3 of 5")).to_be_visible()
        check("arrow keys step through transitions", True)
        check("browser and model timing shown separately",
              await page.get_by_text("Browser action", exact=True).is_visible()
              and await page.locator("span", has_text="Model decision").first.is_visible())
        await page.keyboard.press("Escape")
        await expect(page.get_by_text("Select a state or an action")).to_be_visible()
        check("Escape clears selection", True)

        # Node selection, then navigate to a transition from the state view.
        await page.locator(".react-flow__node").filter(has_text="Edit draft").click()
        await expect(page.get_by_role("heading", name="Edit draft — Draft saved. (2/2 fields filled)")).to_be_visible()
        await page.get_by_role("tabpanel").get_by_role("button", name="5 reload").first.click()
        await expect(page.get_by_text("Step 5 of 5")).to_be_visible()
        check("state view links to its transitions", True)

        # Screenshot dialog: open, focus trapped, Escape closes and returns focus.
        trigger = page.get_by_role("button", name="Enlarge screenshot")
        await trigger.click()
        dialog = page.get_by_role("dialog")
        await expect(dialog).to_be_visible()
        img_ok = await dialog.locator("img").evaluate("i => i.complete && i.naturalWidth > 0")
        await page.screenshot(path=OUT / "after-screenshot-dialog.png")
        await page.keyboard.press("Escape")
        await expect(dialog).to_be_hidden()
        check("screenshot dialog opens full image and closes with Escape", img_ok)
        try:
            await trigger.evaluate_handle("e => new Promise((ok, no) => { const t0 = performance.now(); (function poll() {"
                                          " if (e === document.activeElement) ok(true); else if (performance.now() - t0 > 1000) no('timeout');"
                                          " else requestAnimationFrame(poll); })() })")
            focus_back = True
        except Exception:
            focus_back = False
        check("focus returns to the screenshot trigger", focus_back)

        # Every artifact link in the technical details resolves.
        await page.get_by_text("Technical details").click()
        hrefs = await page.locator("a[data-artifact-id]").evaluate_all("els => els.map(e => e.href)")
        statuses = [(await page.request.get(h)).status for h in hrefs]
        check("artifact links resolve", len(hrefs) == 3 and all(s == 200 for s in statuses), f"{len(hrefs)} links {statuses}")
        await page.screenshot(path=OUT / "after-1440x900-transition-details.png")

        # Activity tab.
        await page.get_by_role("tab", name="Activity").click()
        items = page.get_by_role("tabpanel").get_by_role("listitem")
        check("activity lists all recorded actions", await items.count() == 6)
        check("activity names the explorer", await page.get_by_role("tabpanel").get_by_text("explorer-a").count() >= 6)
        await page.screenshot(path=OUT / "after-1440x900-activity.png")
        await page.get_by_role("tabpanel").get_by_role("button", name="Step 2 fill textbox").click()
        await expect(page.get_by_text("Step 2 of 5")).to_be_visible()
        check("activity item opens its evidence", await page.get_by_role("tab", name="Evidence").get_attribute("aria-selected") == "true")

        # Findings tab.
        await page.get_by_role("tab", name="Findings").click()
        panel = page.get_by_role("tabpanel")
        check("finding labelled unverified", await panel.get_by_text("Unverified", exact=True).is_visible())
        check("completed vs correct explained", await panel.get_by_text("Completed is not the same as correct").is_visible())
        check("no confirmed or pass-rate claims", await panel.get_by_text("confirmed", exact=True).count() == 0
              and await page.get_by_text("%").count() == 0)
        await page.screenshot(path=OUT / "after-1440x900-findings.png")
        await axe(page, "findings tab")

        # Launcher validation (client-side; nothing is submitted).
        await page.get_by_role("button", name="New run").first.click()
        dlg = page.get_by_role("complementary", name="New review run")  # persistent settings panel (was a dialog)
        # An unapproved origin asks for approval in the launcher and cannot start (nothing is approved here).
        await dlg.get_by_label("Target website").fill("https://example.com/")
        url_err = (await dlg.get_by_role("group", name="Approve target origin").is_visible()
                   and await dlg.get_by_role("button", name="Start live run").is_disabled())
        await dlg.get_by_label("Target website").fill("http://localhost:5174/")
        await dlg.get_by_label("Review goal").fill("abc")
        await dlg.get_by_role("button", name="Start live run").click()
        goal_err = await dlg.get_by_text("at least 5 characters").is_visible()
        check("launcher shows URL and goal validation", url_err and goal_err)
        check("launcher shows model without secrets", await dlg.get_by_text("google/gemini-3-flash-preview").is_visible()
              and "sk-or" not in await dlg.inner_text())
        await dlg.get_by_label("Target website").fill("http://localhost:5174/")
        await dlg.get_by_label("Review goal").fill("Create a draft and check it")
        await dlg.get_by_text("Budget and limits").click()
        await dlg.get_by_label("Max browser steps").fill("100")
        await dlg.get_by_role("button", name="Start live run").click()
        check("launcher validates limits", await dlg.get_by_text("Between 1 and 60.").is_visible())
        await page.screenshot(path=OUT / "after-launcher-validation.png")
        await axe(page, "run settings panel")
        await dlg.get_by_role("button", name="Close run settings").click()

        # Missing screenshots degrade to placeholders.
        await page.route("**/api/artifacts/*", lambda r: r.fulfill(status=404, body="{}"))
        await page.reload()
        await page.wait_for_selector(".react-flow__node")
        await page.wait_for_timeout(500)
        await expand_all(page)
        check("broken screenshots show placeholders", await page.get_by_text("Screenshot unavailable").count() >= 5)
        await page.screenshot(path=OUT / "after-missing-screenshots.png")
        await page.unroute("**/api/artifacts/*")

        # Long goal and URL do not break the header.
        async def long_run(route):
            resp = await route.fetch()
            d = await resp.json()
            d["run"]["goal"] = "Create a draft with a very long goal description " * 6
            d["run"]["target_url"] = "http://localhost:5174/" + "deep/" * 30 + "?q=" + "x" * 80
            await route.fulfill(response=resp, json=d)
        await page.route(f"**/api/runs/{RUN}", long_run)
        await page.reload()
        await page.wait_for_selector(".react-flow__node")
        overflow = await page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
        check("long goal and URL do not cause horizontal overflow", not overflow)
        await page.screenshot(path=OUT / "after-long-content.png")
        await page.unroute(f"**/api/runs/{RUN}")

        # Unknown run: error with retry.
        await page.goto(f"{UI}/?run=run_doesnotexist")
        await expect(page.get_by_text("Could not load run_doesnotexist")).to_be_visible()
        check("unknown run shows actionable error", await page.get_by_role("button", name="Retry").is_visible())

        # Backend down: simulated by failing every API request.
        await page.route("**/api/**", lambda r: r.abort())
        await page.goto(f"{UI}/workspace")
        await expect(page.get_by_role("status").filter(has_text="Backend unreachable")).to_be_visible()
        check("backend outage is shown", await page.get_by_text("Cannot reach the backend").is_visible())
        await page.screenshot(path=OUT / "after-backend-unreachable.png")
        await page.unroute("**/api/**")

        # Other viewports.
        for w, h in [(1280, 720), (1024, 768), (390, 844)]:
            vp = await ctx.new_page()
            await vp.set_viewport_size({"width": w, "height": h})
            await vp.goto(f"{UI}/?run={RUN}")
            await vp.wait_for_selector(".react-flow__node")
            await vp.wait_for_timeout(600)
            if w >= 1024:
                await vp.get_by_role("button", name="Transition step 4").click()
                await vp.wait_for_timeout(300)
            over = await vp.evaluate("document.documentElement.scrollWidth > window.innerWidth")
            check(f"{w}x{h}: no horizontal overflow", not over)
            await vp.screenshot(path=OUT / f"after-{w}x{h}.png")
            await vp.close()

        check("no uncaught page errors", not errors, "; ".join(errors))
        await b.close()

    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    sys.exit(1 if failed else 0)


asyncio.run(main())
