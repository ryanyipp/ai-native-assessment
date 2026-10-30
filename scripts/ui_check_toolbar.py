r"""Browser check of the merged run toolbar on saved runs (no model calls).

Usage: backend\.venv\Scripts\python scripts\ui_check_toolbar.py OUT_DIR [UI_URL]
"""

import asyncio
import json
import re
import sys
from pathlib import Path

import httpx
from playwright.async_api import async_playwright, expect

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/run-toolbar")
UI = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:5173"
QUEUE, FAULT, FAILED = "run_a54099283d9d", "run_a4f1034bfe0f", "run_53d7009ff711"
results: list[tuple[str, bool, str]] = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail else ""), flush=True)


async def overlaps(page):
    """Pairs of visible toolbar items whose boxes overlap (they should never)."""
    return await page.evaluate("""() => {
      const bar = document.querySelector('[data-testid=run-toolbar]');
      const items = [...bar.querySelectorAll(':scope > *:not(.sr-only), [data-testid=toolbar-agents] li')]
        .filter(e => e.offsetParent !== null && !e.matches('[data-testid=toolbar-agents]'));
      const out = [];
      for (let i = 0; i < items.length; i++) for (let j = i + 1; j < items.length; j++) {
        if (items[i].contains(items[j]) || items[j].contains(items[i])) continue;
        const a = items[i].getBoundingClientRect(), b = items[j].getBoundingClientRect();
        if (a.width && b.width && a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1)
          out.push((items[i].innerText || items[i].tagName).slice(0, 20) + ' x ' + (items[j].innerText || items[j].tagName).slice(0, 20));
      }
      return out;
    }""")


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await (await browser.new_context(viewport={"width": 1440, "height": 900})).new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto(f"{UI}/?run={QUEUE}")
        await page.wait_for_selector(".react-flow__node", timeout=60000)
        bar = page.get_by_test_id("run-toolbar")
        rows = await page.evaluate("document.querySelectorAll('[aria-label=Agents]').length")
        check("one toolbar: summary and agents share a row", rows == 1 and await bar.get_by_role("group", name="Agents").is_visible())
        h = (await bar.bounding_box())["height"]
        check("toolbar is compact at 1440px (single line plus stop reason)", h <= 90, f"{h:.0f}px")
        goal = httpx.get(f"{UI}/api/runs/{QUEUE}", timeout=20).json()["run"]["goal"]
        visible_goal = await bar.evaluate("(b, g) => [...b.querySelectorAll('*')].some(e => e.offsetParent && !e.closest('details:not([open]), .sr-only') && e.childElementCount === 0 && e.textContent.includes(g.slice(0, 40)))", goal)
        check("long goal text is not shown inline", not visible_goal)
        await bar.get_by_text("Review", exact=True).click()
        menu = page.get_by_test_id("review-menu")
        check("Review dropdown shows full goal, target and workflow",
              await menu.get_by_text(goal).is_visible() and await menu.get_by_text("http://localhost:5174/").is_visible()
              and await menu.get_by_text("Shared queue").is_visible())
        await page.screenshot(path=OUT / "review-open.png")
        await bar.get_by_text("Review", exact=True).click()
        check("status, report and diagnostics controls visible",
              await bar.get_by_text("Partial").first.is_visible() and await bar.get_by_role("link", name="Report").is_visible()
              and await bar.get_by_role("link", name="Markdown").is_visible() and await bar.get_by_text("Diagnostics").is_visible())
        check("stop reason stays visible", await bar.get_by_text("Stopped early").is_visible())
        check("no polling text or active count in the toolbar", await bar.get_by_text(re.compile("Updating every|active now")).count() == 0)
        await bar.get_by_text("Diagnostics").click()
        check("Diagnostics holds the update status", await page.get_by_text("Not refreshing (the run is not active)").is_visible())
        await bar.get_by_text("Diagnostics").click()
        labels = [(await b.inner_text()).split("\n")[0] for b in await bar.get_by_role("group", name="Agents").get_by_role("button").all()]
        check("agent widgets inline with their labels", labels == ["Explorer A", "Explorer B", "Input tester", "Verifier"], str(labels))
        await bar.get_by_role("button", name="Explorer B").click()
        await expect(page.get_by_role("tab", name="Browser")).to_have_attribute("aria-selected", "true")
        check("clicking an agent still opens its browser view",
              await bar.get_by_role("button", name="Explorer B").get_attribute("aria-pressed") == "true")
        check("1440px: no overlapping toolbar items", not await overlaps(page), str(await overlaps(page)))
        await page.screenshot(path=OUT / "toolbar-1440.png")

        # Injected-fault badge stays visible.
        await page.goto(f"{UI}/?run={FAULT}")
        await page.wait_for_selector("[data-testid=run-toolbar]")
        run = httpx.get(f"{UI}/api/runs/{FAULT}", timeout=20).json()["run"]
        if run.get("fault_injection"):
            check("injected-fault badge visible", await page.get_by_test_id("run-toolbar").get_by_text("Injected fault").is_visible())

        # Active run (INTERCEPTED FIXTURE from the saved record): animation classes and active count in Diagnostics.
        d = httpx.get(f"{UI}/api/runs/{QUEUE}", timeout=20).json()
        fx = json.loads(json.dumps(d))
        fx["run"]["status"] = "running"
        t = next(x for x in fx["tasks"] if x["owner"] == "explorer-a" and x["type"] == "explore")
        t["status"] = "claimed"
        fx["events"].append({"seq": max(e["seq"] for e in fx["events"]) + 1, "type": "task_claimed", "message": "fixture claim",
                             "agent_id": "explorer-a", "task_id": t["id"], "data": {}, "created_at": fx["run"]["created_at"]})

        async def serve(route):
            await route.fulfill(status=200, content_type="application/json", body=json.dumps(fx))

        await page.route(f"**/api/runs/{QUEUE}", serve)
        await page.goto(f"{UI}/?run={QUEUE}")
        await page.wait_for_selector("[data-testid=run-toolbar]")
        bar = page.get_by_test_id("run-toolbar")
        check("fixture: active agent keeps its animation and colour inline",
              await bar.locator(".fl-agent-active").count() == 1 and await bar.locator(".bg-emerald-50").count() >= 1)
        await bar.get_by_text("Diagnostics").click()
        check("fixture: active count and refresh rate are in Diagnostics",
              await page.get_by_text("1 worker working on a claimed task").is_visible()
              and await page.get_by_text("Refreshing every 1.5 s while the run is active").is_visible())
        await page.unroute(f"**/api/runs/{QUEUE}")

        await page.goto(f"{UI}/?run={FAILED}")
        await page.wait_for_selector("[data-testid=run-toolbar]")
        check("failed run: stop line visible", await page.get_by_text("Stopped on an error").is_visible())

        for w, hgt in ((1280, 720), (1024, 768), (768, 1024), (390, 844)):
            await page.set_viewport_size({"width": w, "height": hgt})
            await page.goto(f"{UI}/?run={QUEUE}")
            await page.wait_for_selector("[data-testid=run-toolbar]")
            await page.wait_for_timeout(400)
            ov = await overlaps(page)
            agents_box = await page.get_by_test_id("toolbar-agents").bounding_box()
            label_ok = await page.evaluate("""() => [...document.querySelectorAll('[aria-label=Agents] li button span.block.text-\\\\[12px\\\\]')]
                .every(s => s.scrollWidth <= s.clientWidth + 1)""")
            check(f"{w}px: no overlap, labels readable, no page overflow",
                  not ov and label_ok and not await page.evaluate("document.documentElement.scrollWidth > window.innerWidth"),
                  f"overlaps {ov}; agents row {agents_box['width']:.0f}px")
            await page.screenshot(path=OUT / f"toolbar-{w}.png")
        check("no uncaught page errors", not errors, "; ".join(errors))
        await browser.close()
    fails = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(fails)}/{len(results)} passed")
    sys.exit(1 if fails else 0)


asyncio.run(main())
