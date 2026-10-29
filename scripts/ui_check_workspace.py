r"""Browser check of the preview/map workspace.

By default it checks a SAVED run (no spend). Only with --live does it start one bounded
queue_review run from the settings panel (24 calls, US$0.20 cap).

Needs backend (:8000), frontend (:5173) and the creator-studio broken build (:5174).
Usage:
  backend\.venv\Scripts\python scripts\ui_check_workspace.py OUT_DIR RUN_ID
  backend\.venv\Scripts\python scripts\ui_check_workspace.py OUT_DIR --live
"""

import asyncio
import json
import re
import sys
import time
from pathlib import Path

import httpx
from playwright.async_api import Page, async_playwright, expect

UI, API = "http://localhost:5173", "http://localhost:8000"
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/ui-iteration-2")
TARGET = sys.argv[2] if len(sys.argv) > 2 else None
ROOT = Path(__file__).resolve().parents[1]
AXE = ROOT / "frontend" / "node_modules" / "axe-core" / "axe.min.js"
REQS = "\n".join(" ".join(i.strip()[2:].split()) for i in re.split(r"\n(?=- R\d)", (ROOT / "fixtures" / "creator-studio" /
                 "requirements.md").read_text("utf-8")) if i.strip().startswith("- R"))
GOAL = "Explore the creator dashboard and open each form a creator can use, without submitting them. Finish when you have seen them."
results: list[tuple[str, bool, str]] = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail else ""), flush=True)


async def axe(page: Page, label: str):
    await page.add_script_tag(path=str(AXE))
    res = await page.evaluate("async () => (await axe.run(document)).violations.filter(v => ['serious','critical'].includes(v.impact))"
                              ".map(v => ({id: v.id, t: v.nodes[0]?.target}))")
    check(f"axe {label}: no serious/critical violations", not res, json.dumps(res))


async def setup_checks(page):
    await page.goto(UI + "/")
    panel = page.get_by_role("complementary", name="New review run")
    await expect(panel).to_be_visible()
    check("pre-run: settings panel shows model and limits",
          await panel.get_by_text("google/gemini-3-flash-preview").is_visible() and await panel.get_by_text("Budget and limits").is_visible())
    prev = page.get_by_role("region", name="Browser preview")
    check("pre-run: preview labelled non-interactive", await prev.get_by_text("Static screenshot · not interactive").is_visible())
    await page.screenshot(path=OUT / "after-setup-idle.png")
    await panel.get_by_role("button", name="Preview page").click()
    check("preview shows a loading state", await prev.get_by_text("Capturing").is_visible())
    img = prev.get_by_role("img", name=re.compile("Screenshot of"))
    await expect(img).to_be_visible(timeout=40000)
    nat = await img.evaluate("i => [i.naturalWidth, i.naturalHeight]")
    check("preview shows a real screenshot", nat[0] == 1280 and nat[1] > 0, str(nat))
    check("preview states when it was captured", await prev.get_by_text(re.compile("captured once at")).is_visible())
    await page.screenshot(path=OUT / "after-setup-preview.png")
    await axe(page, "setup view")
    await page.route("**/api/preview", lambda r: r.fulfill(status=504, body='{"detail":"the page did not load within 40 s"}',
                                                         content_type="application/json"))
    await prev.get_by_role("button", name="Capture again").click()
    try:
        await expect(prev.get_by_text("Could not capture the page")).to_be_visible(timeout=10000)
        check("preview error state", True)
    except AssertionError as e:
        check("preview error state", False, str(e).splitlines()[0])
    await page.unroute("**/api/preview")
    await page.screenshot(path=OUT / "after-setup-preview-error.png")
    return panel


async def start_live(page, panel):
    await panel.get_by_label("Review goal").fill(GOAL)
    await panel.get_by_text("Shared queue: two explorers, tester, verifier").click()
    await panel.get_by_label("Requirements (optional)").fill(REQS)
    await panel.get_by_text("Budget and limits").click()
    await panel.get_by_label("Max model calls").fill("24")
    await panel.get_by_label("Max cost per run (US$)").fill("0.2")
    await panel.get_by_role("button", name="Start live run").click()
    await page.wait_for_url(re.compile(r"run=run_"), timeout=15000)
    run_id = re.search(r"run=(run_[0-9a-f]+)", page.url).group(1)
    print("live run", run_id, flush=True)
    await page.wait_for_selector(".react-flow__node", timeout=60000)
    shots, t0, seen_new = 0, time.monotonic(), False
    while time.monotonic() - t0 < 420:
        status = httpx.get(f"{API}/api/runs/{run_id}", timeout=20).json()["run"]["status"]
        if await page.locator(".fl-new-node, .fl-new-edge").count() > 0:
            seen_new = True
        if shots < 3 and time.monotonic() - t0 > 12 * (shots + 1):
            await page.screenshot(path=OUT / f"after-live-{shots + 1}.png")
            shots += 1
        if status not in ("queued", "running"):
            break
        await page.wait_for_timeout(2000)
    return run_id, seen_new


async def run_checks(page, browser, run_id, errors):
    main = page.get_by_test_id("main-view")
    dock = page.get_by_test_id("dock")
    await page.wait_for_selector(".react-flow__node", timeout=60000)
    await page.wait_for_timeout(1500)
    check("run view: map is the main view", await main.get_attribute("aria-label") == "Website flow map")
    check("run view: worker view is docked", await dock.get_attribute("aria-label") == "Docked worker browser view")
    detail = httpx.get(f"{API}/api/runs/{run_id}", timeout=20).json()
    print("run", detail["run"]["status"], detail["run"]["stop_reason"], detail["run"]["usage"]["reported_cost_usd"], flush=True)

    radios = dock.get_by_role("radio")
    names = [(await r.inner_text()).split("\n")[0] for r in await radios.all()]
    check("worker selector lists the run's workers", {"explorer-a", "explorer-b"} <= set(names), str(names))
    captions = set()
    for r in await radios.all():
        await r.click()
        await expect(r).to_have_attribute("aria-checked", "true")
        captions.add(await dock.get_by_text(re.compile("Last recorded action: step")).inner_text())
    check("switching workers changes the recorded action shown", len(captions) >= 2, f"{len(captions)} distinct")
    check("worker screenshot labelled as recorded, not live",
          await dock.get_by_text(re.compile("not live video")).first.is_visible())
    await page.screenshot(path=OUT / "after-worker-dock.png")

    hl = None
    for r in await radios.all():
        await r.click()
        btn = dock.get_by_role("button", name=re.compile("Show where step"))
        if await btn.count():
            await btn.click()
            try:  # drawn once the before-screenshot has loaded and its natural size is known
                await expect(dock.get_by_test_id("click-highlight")).to_have_count(1, timeout=10000)
                hl = await dock.get_by_text(re.compile("outlined from its recorded bounds")).is_visible()
            except AssertionError:
                hl = False
            await page.screenshot(path=OUT / "after-click-highlight.png")
            await dock.get_by_role("button", name="Show page after the action").click()
            break
    acts = [a for a in detail["actions"] if a["action"]["type"] in ("click", "fill")]
    with_box = sum(1 for a in acts if a.get("target_box"))
    check("click/fill actions in the run recorded bounds", acts and with_box == len(acts), f"{with_box}/{len(acts)}")
    check("highlight drawn from recorded bounds" if hl is not None else "no last action supports a highlight (none drawn)",
          hl is not False)

    await dock.get_by_role("button", name=re.compile("Open evidence for step")).click()
    await expect(page.get_by_role("tab", name="Evidence")).to_have_attribute("aria-selected", "true")
    check("worker screenshot opens its evidence",
          await page.get_by_role("tabpanel").get_by_text(re.compile(r"step \d+", re.I)).first.is_visible())

    await dock.get_by_role("button", name=re.compile("Swap views")).click()
    check("swap: worker view becomes the main view", await main.get_attribute("aria-label") == "Worker browser view (main)")
    check("swap: map is docked", await dock.get_attribute("aria-label") == "Docked map"
          and await dock.locator(".react-flow__node").count() > 0)
    await page.screenshot(path=OUT / "after-swapped.png")
    await axe(page, "swapped run view")
    await dock.get_by_role("button", name=re.compile("Swap views")).click()
    check("swap back restores the map", await main.get_attribute("aria-label") == "Website flow map")

    follow = page.get_by_role("button", name="Follow new pages")
    box = await main.locator(".react-flow__pane").bounding_box()
    await page.mouse.move(box["x"] + 60, box["y"] + box["height"] - 60)
    await page.mouse.down()
    await page.mouse.move(box["x"] + 160, box["y"] + box["height"] - 120, steps=5)
    await page.mouse.up()
    check("panning turns off follow mode", await follow.get_attribute("aria-pressed") == "false")

    for tab in ("Activity", "Findings"):
        await page.get_by_role("tab", name=tab).click()
        check(f"{tab} tab still renders", await page.get_by_role("tabpanel").is_visible())
    await page.screenshot(path=OUT / "after-run-findings.png")
    await axe(page, "run view")

    await page.goto(UI + "/?run=run_e957eab8645e")
    await page.wait_for_selector(".react-flow__node")
    check("old single-explorer run loads with a worker view", await dock.get_by_role("radio", name=re.compile("explorer-a")).is_visible())
    await page.goto(UI + "/?run=run_53d7009ff711")
    await page.wait_for_selector("[data-testid=main-view]")
    await page.get_by_role("tab", name="Findings").click()
    check("failed run states where it stopped", await page.get_by_text("Review stopped on an error").is_visible())
    await page.screenshot(path=OUT / "after-failed-run.png")

    rm = await browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    rp = await rm.new_page()
    await rp.goto(UI + f"/?run={run_id}")
    await rp.wait_for_selector(".react-flow__node")
    anim = await rp.evaluate("""() => { const n = document.createElement('div'); n.className = 'fl-new-node';
        const c = document.createElement('div'); n.appendChild(c); document.body.appendChild(n);
        return getComputedStyle(c).animationName }""")
    check("reduced motion disables map animations", anim == "none", anim)
    await rm.close()

    for w, h in [(1280, 720), (1024, 768), (390, 844)]:
        await page.set_viewport_size({"width": w, "height": h})
        await page.goto(UI + f"/?run={run_id}")
        await page.wait_for_selector("[data-testid=main-view]")
        await page.wait_for_timeout(500)
        check(f"{w}x{h}: no horizontal overflow", not await page.evaluate("document.documentElement.scrollWidth > window.innerWidth"))
        await page.screenshot(path=OUT / f"after-{w}x{h}.png")
    check("no uncaught page errors", not errors, "; ".join(errors))
    return detail


async def main():
    if not TARGET:
        sys.exit("give a saved RUN_ID, or --live to start one bounded live run")
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        page = await (await b.new_context(viewport={"width": 1440, "height": 900})).new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        panel = await setup_checks(page)
        if TARGET == "--live":
            run_id, seen_new = await start_live(page, panel)
            check("live: newly accepted map records were marked for animation", seen_new)
        else:
            run_id = TARGET
            await page.goto(UI + f"/?run={run_id}")
        detail = await run_checks(page, b, run_id, errors)
        (OUT / "checked-run.json").write_text(json.dumps({"run_id": run_id, "status": detail["run"]["status"],
                                                          "stop_reason": detail["run"]["stop_reason"],
                                                          "usage": detail["run"]["usage"]}, indent=2), "utf-8")
        await b.close()
    n = sum(ok for _, ok, _ in results)
    print(f"{n}/{len(results)} checks passed")
    sys.exit(0 if n == len(results) else 1)


asyncio.run(main())
