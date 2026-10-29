r"""Browser check of the run report (HTML view, print styling, Markdown download) on saved runs.

No model calls and no target website: reports are built only from saved records.
Needs backend (:8000) and frontend (:5173).
Usage: backend\.venv\Scripts\python scripts\ui_check_report.py OUT_DIR
"""

import asyncio
import re
import sys
from pathlib import Path

import httpx
from playwright.async_api import async_playwright, expect

UI, API = "http://localhost:5173", "http://localhost:8000"
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/report")
RUNS = {  # saved runs covering each status and verification type
    "run_a572a9bf88c5": ("completed", "sequential review with an independently confirmed finding"),
    "run_a54099283d9d": ("partial", "shared-queue review stopped at its exploration budget"),
    "run_53d7009ff711": ("failed", "review stopped by an internal error"),
    "run_fc9eba62a54c": ("completed", "single-agent baseline with a self-checked finding"),
    "run_15f19bf8bb46": ("completed", "TodoMVC explorer run with not-evaluated checkbox claims"),
    "run_40e786578fef": ("completed", "re-check of an earlier finding"),
}
results: list[tuple[str, bool, str]] = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail else ""), flush=True)


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 1280, "height": 900}, accept_downloads=True)
        page = await ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        # Opened from the run header.
        await page.goto(UI + "/?run=run_a572a9bf88c5")
        await page.wait_for_selector("[data-testid=main-view]")
        async with page.expect_popup() as pop:
            await page.get_by_role("link", name="Report").click()
        rp = await pop.value
        await rp.wait_for_load_state()
        check("header Report opens the HTML report", await rp.get_by_role("heading", name="Website review report").is_visible())
        async with page.expect_download() as dl:
            await page.get_by_role("link", name="Markdown").click()
        d = await dl.value
        md_path = OUT / d.suggested_filename
        await d.save_as(md_path)
        md = md_path.read_text("utf-8")
        check("header Markdown downloads the report file", d.suggested_filename == "flowlens-report-run_a572a9bf88c5.md"
              and md.startswith("# Website review report"))
        await rp.close()

        for rid, (status, what) in RUNS.items():
            await page.goto(f"{UI}/api/runs/{rid}/report")
            main = page.locator("main")
            h2 = [t.strip() for t in await page.locator("h2").all_inner_texts()]
            check(f"{what}: summary first, diagnostics last", h2[0] == "Summary" and h2[-1] == "Diagnostics", str(h2))
            # Technical content is folded: ids and raw JSON are not visible until opened.
            visible = await main.evaluate("""m => { const c = m.cloneNode(true); c.querySelectorAll('details').forEach(d => d.remove());
                                                    return c.innerText }""")
            check(f"{what}: no ids or raw JSON outside the technical dropdowns",
                  not re.search(r"\b(run|fnd|ver|art|task|state)_[0-9a-f]{6,}|\{\"", visible), "")
            det = page.locator("details").last
            await det.locator("summary").click()
            check(f"{what}: technical dropdown opens with diagnostics", await det.get_by_text(rid).is_visible())
            if status != "completed":
                check(f"{what}: incomplete review flagged with plain reason",
                      await page.get_by_text("Incomplete review.").is_visible()
                      and await page.get_by_text(re.compile("The review did not finish: ")).is_visible())
            if rid == "run_a572a9bf88c5":
                card = page.locator("article").first
                check("confirmed finding shows expected vs observed, steps and status",
                      await card.get_by_text("Confirmed", exact=True).is_visible()
                      and await card.get_by_text("Expected", exact=True).is_visible()
                      and await card.locator("ol li").count() >= 3)
                href = await card.locator("a[href^='/api/artifacts/']").first.get_attribute("href")
                r = httpx.get(API + href, timeout=10)
                check("evidence link opens the saved screenshot", r.status_code == 200 and r.headers["content-type"] == "image/png")
                check("report explains evidence link availability", await page.get_by_text(re.compile("work while the FlowLens server")).is_visible())
            if rid == "run_fc9eba62a54c":
                check("self-check is labelled, not independent", await page.get_by_text("Confirmed by self-check only").first.is_visible())
            if rid == "run_15f19bf8bb46":
                check("checkbox claims show Not evaluated", await page.locator("article td", has_text="Not evaluated").count() == 2
                      and await page.get_by_text("Explorer claim; not evaluated").is_visible())
            await page.screenshot(path=OUT / f"report-{status}-{rid}.png", full_page=True)

        # Print styling: toolbar hidden.
        await page.goto(f"{UI}/api/runs/run_a572a9bf88c5/report")
        await page.emulate_media(media="print")
        check("print styling hides the toolbar", not await page.locator(".toolbar").is_visible())
        await page.screenshot(path=OUT / "report-print-media.png", full_page=True)
        await page.emulate_media(media="screen")
        await page.set_viewport_size({"width": 390, "height": 844})
        check("390px: no horizontal overflow", not await page.evaluate("document.documentElement.scrollWidth > window.innerWidth"))

        # The app's findings panel uses the same not-evaluated reading.
        await page.set_viewport_size({"width": 1440, "height": 900})
        await page.goto(UI + "/?run=run_15f19bf8bb46")
        await page.wait_for_selector("[data-testid=main-view]")
        await page.get_by_role("tab", name="Findings").click()
        panel = page.get_by_role("tabpanel")
        await expect(panel.get_by_text("Same-session engine check")).to_be_visible()
        check("findings panel shows Not evaluated, not Mismatch or matched",
              await panel.get_by_text("Not evaluated").count() >= 3 and await panel.get_by_text("Mismatch").count() == 0)
        await page.screenshot(path=OUT / "findings-not-evaluated.png")
        check("no uncaught page errors", not errors, "; ".join(errors))
        await browser.close()
    fails = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(fails)}/{len(results)} passed")
    sys.exit(1 if fails else 0)


asyncio.run(main())
