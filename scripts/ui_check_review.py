"""Browser check of the checkpoint 2 review UI against saved real runs. Makes no model calls.

Needs the backend (:8000) and frontend dev server (:5173) running.
Usage (repo root):
  backend\\.venv\\Scripts\\python scripts\\ui_check_review.py BROKEN_RUN CORRECTED_RUN RECHECK_RUN OUT_DIR
"""

import asyncio
import os
import json
import sys
from pathlib import Path

from playwright.async_api import Page, async_playwright, expect

UI = os.environ.get("FLOWLENS_UI", "http://localhost:5173")
BROKEN, CORRECTED, RECHECK = sys.argv[1:4]
OUT = Path(sys.argv[4] if len(sys.argv) > 4 else "docs/checkpoint-2")
AXE = Path(__file__).resolve().parents[1] / "frontend" / "node_modules" / "axe-core" / "axe.min.js"
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail else ""))


async def axe(page: Page, label: str) -> None:
    await page.add_script_tag(path=str(AXE))
    res = await page.evaluate("async () => (await axe.run(document, {resultTypes: ['violations']})).violations"
                              ".map(v => ({id: v.id, impact: v.impact, n: v.nodes.length, t: v.nodes[0]?.target}))")
    serious = [v for v in res if v["impact"] in ("serious", "critical")]
    check(f"axe {label}: no serious/critical violations", not serious, json.dumps(serious))


async def open_run(page: Page, run: str) -> None:
    await page.goto(f"{UI}/?run={run}")
    await page.wait_for_selector(".react-flow__node")
    await page.wait_for_timeout(700)


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

        # --- broken-build review run --------------------------------------------
        await open_run(page, BROKEN)
        header = page.locator("header").first
        await page.get_by_text("Diagnostics").click()  # metadata moved into the Diagnostics dropdown
        check("header names the workflow", await page.get_by_text("Explorer → tester → verifier").first.is_visible())
        check("header shows evaluation build label", await page.get_by_text("build: creator-studio:broken").is_visible())
        await page.get_by_text("Diagnostics").click()
        check("map legend distinguishes test and verification", await page.get_by_text("Input test", exact=True).is_visible()
              and await page.get_by_text("Verification", exact=True).first.is_visible())
        check("map has tester and verifier transitions",
              await page.get_by_role("button", name="by input-tester").count() > 0
              and await page.get_by_role("button", name="by verifier").count() > 0)
        await page.screenshot(path=OUT / "broken-map.png")
        await axe(page, "review workspace")

        await page.get_by_role("tab", name="Findings").click()
        panel = page.get_by_role("tabpanel")
        r5 = panel.get_by_role("article").filter(has_text="R5:")
        check("R5 candidate shown as confirmed", await r5.count() >= 1
              and await r5.first.get_by_text("Confirmed", exact=True).first.is_visible())
        check("candidate shows requirement and assertion",
              await r5.first.get_by_text("A publish date in the past must be rejected", exact=False).count() > 0
              and await r5.first.get_by_text("validation_message_present").first.is_visible())
        check("tester and verifier evidence shown separately",
              await r5.first.get_by_text("Original suspicion: input tester evidence").is_visible()
              and await r5.first.get_by_text("Independent verification").is_visible()
              and await r5.first.get_by_text("Replay 2").is_visible())
        check("inconclusive outcomes are kept visible", await panel.get_by_text("Inconclusive", exact=True).count() >= 1)
        hrefs = await r5.first.locator("a[href^='/api/artifacts/']").evaluate_all("els => els.map(e => e.getAttribute('href'))")
        statuses = [(await page.request.get(UI + h)).status for h in hrefs]
        check("candidate evidence links resolve", bool(hrefs) and all(s == 200 for s in statuses), f"{len(hrefs)} links")
        await r5.first.scroll_into_view_if_needed()
        await r5.first.screenshot(path=OUT / "broken-r5-finding.png")
        await page.screenshot(path=OUT / "broken-findings.png")
        await axe(page, "review findings")

        await r5.first.get_by_role("button", name="Show this replay on the map").first.click()
        await expect(page.get_by_role("tab", name="Evidence")).to_have_attribute("aria-selected", "true")
        check("replay opens verification evidence", await page.get_by_text("Verification replay 1").is_visible())
        await page.screenshot(path=OUT / "broken-verification-evidence.png")

        await page.get_by_role("tab", name="Activity").click()
        panel = page.get_by_role("tabpanel")
        trail = panel.get_by_role("region", name="Handoffs between workers")
        kinds = ["Explorer discovered form", "Handoff", "Test executed", "Candidate reported",
                 "Verification executed", "Result accepted"]
        missing = [k for k in kinds if await trail.get_by_text(k, exact=True).count() == 0]
        check("activity shows each handoff stage", not missing, f"missing {missing}")
        check("activity attributes actions to each worker",
              all([await panel.get_by_text(a, exact=True).count() > 0 for a in ("explorer-a", "input-tester", "verifier")]))
        await page.screenshot(path=OUT / "broken-activity.png")
        await axe(page, "review activity")

        # State node seen by several workers keeps its sightings.
        await page.get_by_role("tab", name="Evidence").click()
        await expand_all(page)
        node = page.locator(".react-flow__node").filter(has_text="Schedule a post").first
        await node.click()
        check("shared state lists every worker/context", await page.get_by_text("Observed by").is_visible())
        await page.screenshot(path=OUT / "broken-state-sightings.png")

        await page.set_viewport_size({"width": 1280, "height": 720})
        await page.wait_for_timeout(400)
        over = await page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
        check("1280x720 review run: no horizontal overflow", not over)
        await page.set_viewport_size({"width": 1440, "height": 900})

        # --- corrected build ------------------------------------------------------
        await open_run(page, CORRECTED)
        await page.get_by_text("Diagnostics").click()
        check("corrected run labelled with its build", await page.get_by_text("build: creator-studio:corrected").is_visible())
        await page.get_by_text("Diagnostics").click()
        await page.get_by_role("tab", name="Findings").click()
        panel = page.get_by_role("tabpanel")
        check("corrected run has no confirmed finding",
              await panel.get_by_role("article").get_by_text("Confirmed", exact=True).count() == 0)
        await page.screenshot(path=OUT / "corrected-findings.png")
        await page.get_by_role("tab", name="Activity").click()
        await page.screenshot(path=OUT / "corrected-activity.png")

        # --- browser-only re-check of the broken finding on the corrected build -----
        await open_run(page, RECHECK)
        await page.get_by_text("Diagnostics").click()
        check("re-check run labelled as browser re-check", await page.get_by_text("Browser re-check").first.is_visible())
        await page.get_by_text("Diagnostics").click()
        await page.get_by_role("tab", name="Findings").click()
        panel = page.get_by_role("tabpanel")
        check("re-check shows not reproduced", await panel.get_by_text("Not reproduced", exact=True).first.is_visible()
              and await panel.get_by_text("Assertion held").count() >= 2)
        await page.screenshot(path=OUT / "recheck-findings.png")

        check("no uncaught page errors", not errors, "; ".join(errors))
        await b.close()
    n = sum(ok for _, ok, _ in results)
    print(f"{n}/{len(results)} checks passed")
    sys.exit(0 if n == len(results) else 1)


asyncio.run(main())
