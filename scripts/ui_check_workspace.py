r"""Browser check of the preview/map workspace.

By default it checks a SAVED run (no spend). Only with --live does it start one bounded
queue_review run from the settings panel (24 calls, US$0.20 cap).

Needs backend (:8000), frontend (:5173) and the creator-studio broken build (:5174).
Usage:
  backend\.venv\Scripts\python scripts\ui_check_workspace.py OUT_DIR RUN_ID
  backend\.venv\Scripts\python scripts\ui_check_workspace.py OUT_DIR --live
"""

import asyncio
import os
import json
import re
import sys
import time
from pathlib import Path

import httpx
from playwright.async_api import Page, async_playwright, expect

UI = os.environ.get("FLOWLENS_UI", "http://localhost:5173")
API = os.environ.get("FLOWLENS_API", "http://localhost:8000")
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
    await page.goto(UI + "/workspace")
    panel = page.get_by_role("complementary", name="New review run")
    await expect(panel).to_be_visible()
    # The workspace loads after the page's load event, so wait for /api/health to fill the launcher.
    await expect(panel.get_by_text("google/gemini-3-flash-preview")).to_be_visible()
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
    strip = page.get_by_label("Agents")
    side = page.get_by_role("tabpanel")
    await page.wait_for_selector(".react-flow__node", timeout=60000)
    await page.wait_for_timeout(1500)
    detail = httpx.get(f"{API}/api/runs/{run_id}", timeout=20).json()
    print("run", detail["run"]["status"], detail["run"]["usage"]["reported_cost_usd"], flush=True)
    check("map is the main view", await main.get_attribute("aria-label") == "Website flow map")
    labels = [(await b.inner_text()).split("\n")[0] for b in await strip.get_by_role("button").all()]
    check("agent strip shows the shared-queue agents", labels == ["Explorer A", "Explorer B", "Input tester", "Verifier"], str(labels))

    # Compact header; metadata in Diagnostics; failures stay visible.
    check("header keeps a partial run's stop reason visible", await page.get_by_text("Stopped early").is_visible()
          if detail["run"]["status"] == "partial" else True)
    await page.get_by_text("Diagnostics").click()
    check("Diagnostics shows cost, model and run id", await page.get_by_text("Reported cost").is_visible()
          and await page.get_by_text(run_id).first.is_visible())
    await page.screenshot(path=OUT / "after-diagnostics.png")
    await page.get_by_text("Diagnostics").click()

    # Clicking a worker selects its browser view in the sidebar.
    await strip.get_by_role("button", name="Explorer B").click()
    await expect(page.get_by_role("tab", name="Browser")).to_have_attribute("aria-selected", "true")
    check("clicking a worker opens its browser view", await side.get_by_role("radio", name=re.compile("explorer-b")).get_attribute("aria-checked") == "true"
          and await strip.get_by_role("button", name="Explorer B").get_attribute("aria-pressed") == "true")
    captions = set()
    for name in ("Explorer A", "Explorer B", "Input tester", "Verifier"):
        await strip.get_by_role("button", name=name).click()
        captions.add(await side.get_by_text(re.compile("Last recorded action: step")).inner_text())
    check("each worker shows its own recorded action", len(captions) == 4, f"{len(captions)} distinct")
    check("worker screenshot labelled as recorded, not live", await side.get_by_text(re.compile("not live video")).first.is_visible())
    await page.screenshot(path=OUT / "after-browser-tab.png")

    hl = None
    for name in ("Explorer A", "Explorer B", "Input tester", "Verifier"):
        await strip.get_by_role("button", name=name).click()
        btn = side.get_by_role("button", name=re.compile("Show where step"))
        if await btn.count():
            await btn.click()
            try:
                await expect(side.get_by_test_id("click-highlight")).to_have_count(1, timeout=10000)
                hl = await side.get_by_text(re.compile("outlined from its recorded bounds")).is_visible()
            except AssertionError:
                hl = False
            await page.screenshot(path=OUT / "after-click-highlight.png")
            await side.get_by_role("button", name="Show page after the action").click()
            break
    check("highlight drawn only from recorded bounds" if hl is not None else "no last action supports a highlight (none drawn)", hl is not False)
    opened = 0
    for name in ("Explorer A", "Explorer B", "Input tester", "Verifier"):
        await strip.get_by_role("button", name=name).click()
        await side.get_by_role("button", name=re.compile("Open evidence for step")).click()
        await expect(page.get_by_role("tab", name="Evidence")).to_have_attribute("aria-selected", "true")
        opened += await side.get_by_text(re.compile(r"step \d+", re.I)).first.is_visible()
    check("every worker's screenshot opens its evidence", opened == 4, f"{opened}/4")

    # Map selection opens evidence in the same sidebar.
    await page.get_by_role("tab", name="Findings").click()
    await main.locator(".react-flow__node").first.click()
    await expect(page.get_by_role("tab", name="Evidence")).to_have_attribute("aria-selected", "true")
    check("map selection opens evidence in the sidebar", True)
    for tab in ("Activity", "Findings"):
        await page.get_by_role("tab", name=tab).click()
        check(f"{tab} tab renders in the sidebar", await side.is_visible())
    await page.screenshot(path=OUT / "after-run.png")
    await axe(page, "run view")

    follow = page.get_by_role("button", name="Follow new pages")
    box = await main.locator(".react-flow__pane").bounding_box()
    await page.mouse.move(box["x"] + 60, box["y"] + box["height"] - 60)
    await page.mouse.down()
    await page.mouse.move(box["x"] + 160, box["y"] + box["height"] - 120, steps=5)
    await page.mouse.up()
    check("panning turns off follow mode", await follow.get_attribute("aria-pressed") == "false")

    # Simultaneous activity and a new handoff: INTERCEPTED FIXTURE built from this run's own record
    # (status set to running, two real explore tasks marked claimed, then one handoff event appended).
    # This tests rendering of real event shapes; it is not presented as a live run.
    fx = json.loads(json.dumps(detail))
    fx["run"]["status"] = "running"
    explore = [t for t in fx["tasks"] if t["type"] == "explore" and t["owner"] in ("explorer-a", "explorer-b")]
    ta = next(t for t in explore if t["owner"] == "explorer-a")
    tb = next(t for t in explore if t["owner"] == "explorer-b")
    seq = max(e["seq"] for e in fx["events"])
    for t, s in ((ta, seq + 1), (tb, seq + 2)):
        t["status"] = "claimed"
        fx["events"].append({"seq": s, "type": "task_claimed", "message": "fixture claim", "agent_id": t["owner"],
                             "task_id": t["id"], "data": {}, "created_at": fx["run"]["created_at"]})
    second = json.loads(json.dumps(fx))
    second["events"].append({"seq": seq + 3, "type": "handoff_created", "message": "fixture handoff", "agent_id": "coordinator",
                             "task_id": None, "created_at": fx["run"]["created_at"],
                             "data": {"from_agent": "explorer-b", "to_agent": "input-tester", "kind": "form_to_tester"}})
    t_route = {"t0": None}

    async def serve(route):
        # Time-based switch: dev-mode StrictMode loads twice on mount, so the new handoff must arrive later.
        t_route["t0"] = t_route["t0"] or time.monotonic()
        body = fx if time.monotonic() - t_route["t0"] < 2.5 else second
        await route.fulfill(status=200, content_type="application/json", body=json.dumps(body))

    await page.route(f"**/api/runs/{run_id}", serve)
    await page.goto(UI + f"/?run={run_id}")
    await page.wait_for_selector(".react-flow__node")
    # The active count moved from the strip into Diagnostics (merged run toolbar).
    await page.get_by_text("Diagnostics").click()
    check("fixture: two workers shown active at once", await strip.locator(".fl-agent-active").count() == 2
          and await page.get_by_text("2 workers working on a claimed task").is_visible())
    await page.get_by_text("Diagnostics").click()
    await expect(strip.locator(".fl-handoff-new")).to_have_count(1, timeout=8000)
    check("fixture: a new handoff event animates once and marks the receiver",
          await strip.get_by_role("button", name="Input tester").locator(".fl-agent-received").count() == 1)
    await page.screenshot(path=OUT / "after-fixture-active-handoff.png")
    await page.unroute(f"**/api/runs/{run_id}")

    rm = await browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    rp = await rm.new_page()
    await rp.goto(UI + f"/?run={run_id}")
    await rp.wait_for_selector(".react-flow__node")
    anim = await rp.evaluate("""() => ['fl-agent-active', 'fl-handoff-new', 'fl-new-node'].map(c => {
        const n = document.createElement('div'); n.className = c; const k = document.createElement('div'); n.appendChild(k);
        document.body.appendChild(n); return getComputedStyle(c === 'fl-new-node' ? k : n).animationName })""")
    check("reduced motion disables strip and map animations", all(a == "none" for a in anim), str(anim))
    await rm.close()

    # Agents per workflow, and old/completed/partial/failed runs.
    for rid, want, what in [("run_e957eab8645e", ["Explorer A"], "old single-explorer run"),
                            ("run_db4f36872772", ["Explorer A", "Input tester", "Verifier"], "sequential run"),
                            ("run_9191ff906668", ["Single agent"], "single-agent run")]:
        await page.goto(UI + f"/?run={rid}")
        await page.wait_for_selector(".react-flow__node")
        got = [(await b.inner_text()).split("\n")[0] for b in await strip.get_by_role("button").all()]
        check(f"{what}: strip shows its actual agents", got == want, str(got))
    await page.goto(UI + "/?run=run_53d7009ff711")
    await page.wait_for_selector("[data-testid=main-view]")
    check("failed run: header shows where it stopped", await page.get_by_text("Stopped on an error").is_visible())
    await page.screenshot(path=OUT / "after-failed-run.png")

    for w, h in [(1280, 720), (1024, 768), (390, 844)]:
        await page.set_viewport_size({"width": w, "height": h})
        await page.goto(UI + f"/?run={run_id}")
        await page.wait_for_selector("[data-testid=main-view]")
        await page.wait_for_timeout(500)
        check(f"{w}x{h}: no horizontal overflow", not await page.evaluate("document.documentElement.scrollWidth > window.innerWidth"))
        await page.screenshot(path=OUT / f"after-{w}x{h}.png")
    await page.set_viewport_size({"width": 1440, "height": 900})
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
