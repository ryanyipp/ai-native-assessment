r"""Browser check of public-website support, against https://demo.playwright.dev/todomvc/.

Without --live: launcher approval, scope-limited preview and stale/cleared preview handling
(no model calls, no spend). With --live: also starts ONE single-explorer run from the
launcher (20 steps, 22 calls, US$0.10 cap) and checks its recorded actions.

Needs backend (:8000), frontend (:5173) and the creator-studio fixture (:5174).
Usage:
  backend\.venv\Scripts\python scripts\ui_check_public_site.py OUT_DIR [--live | RUN_ID]
"""

import asyncio
import json
import re
import sys
import time
from pathlib import Path

import httpx
from playwright.async_api import async_playwright, expect

UI, API = "http://localhost:5173", "http://localhost:8000"
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/public-site")
ARG = sys.argv[2] if len(sys.argv) > 2 else None
ROOT = Path(__file__).resolve().parents[1]
AXE = ROOT / "frontend" / "node_modules" / "axe-core" / "axe.min.js"
TARGET = "https://demo.playwright.dev/todomvc/"
ORIGIN = "https://demo.playwright.dev"
GOAL = ("Add two todos named 'FlowLens milk' and 'FlowLens dog', mark 'FlowLens milk' as completed, "
        "then view the Active, Completed and All filters, reload the page, and report whether both todos "
        "and the completed state are still shown after the reload.")
results: list[tuple[str, bool, str]] = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail else ""), flush=True)


async def axe(page, label):
    await page.add_script_tag(path=str(AXE))
    res = await page.evaluate("async () => (await axe.run(document)).violations.filter(v => ['serious','critical'].includes(v.impact))"
                              ".map(v => ({id: v.id, t: v.nodes[0]?.target}))")
    check(f"axe {label}: no serious/critical violations", not res, json.dumps(res))


async def launcher_checks(page):
    # Start from an unapproved state so the approval flow is exercised.
    httpx.delete(f"{API}/api/origins", params={"origin": ORIGIN}, timeout=10)
    await page.goto(UI + "/")
    panel = page.get_by_role("complementary", name="New review run")
    url = panel.get_by_label("Target website")
    prev = page.get_by_role("region", name="Browser preview")
    # A fixture preview first, so changing the target has something to clear.
    await panel.get_by_role("button", name="Preview page").click()
    await expect(prev.get_by_role("img", name=re.compile("Screenshot of"))).to_be_visible(timeout=40000)

    await url.fill(TARGET)
    check("changing origin clears the previous preview",
          await prev.get_by_text(re.compile("previous screenshot .* was cleared because the target origin changed")).is_visible()
          and await prev.get_by_role("img").count() == 0)
    group = panel.get_by_role("group", name="Approve target origin")
    check("unapproved origin asks for approval in the launcher", await group.is_visible()
          and await group.get_by_text(ORIGIN).first.is_visible())
    check("approval explains scope, redirects and shared server data",
          await group.get_by_text(re.compile("redirects to any other origin are blocked")).is_visible()
          and await group.get_by_text(re.compile("not isolated")).first.is_visible())
    check("preview and start are disabled until approved",
          await panel.get_by_role("button", name="Preview page").is_disabled()
          and await panel.get_by_role("button", name="Start live run").is_disabled())
    approve = group.get_by_role("button", name="Approve this origin")
    check("approve needs the authorisation acknowledgement", await approve.is_disabled())
    await page.screenshot(path=OUT / "launcher-approval.png")
    await group.get_by_role("checkbox").check()
    await approve.click()
    await expect(group).to_have_count(0, timeout=10000)
    h = httpx.get(f"{API}/api/health", timeout=10).json()
    check("approval is stored by the backend (no .env edit)", ORIGIN in h["approved_origins"]
          and ORIGIN not in h["allowed_origins"])
    check("launcher labels the website session profile",
          await panel.get_by_text(re.compile("fresh browser context per worker; the site's server data is shared")).is_visible())

    await panel.get_by_role("button", name="Preview page").click()
    img = prev.get_by_role("img", name=re.compile("Screenshot of"))
    await expect(img).to_be_visible(timeout=40000)
    nat = await img.evaluate("i => [i.naturalWidth, i.naturalHeight]")
    check("TodoMVC preview is a real screenshot", nat[0] == 1280 and nat[1] > 0, str(nat))
    check("preview caption says server data is not isolated",
          await prev.get_by_text(re.compile("server data is shared, not isolated")).is_visible())
    await page.screenshot(path=OUT / "preview-todomvc.png")

    await url.fill(TARGET + "#/active")
    fig = prev.get_by_test_id("preview-figure")
    check("same-origin URL change marks the preview out of date",
          await fig.get_attribute("data-stale") == "true" and await prev.get_by_text("Out of date:").is_visible())
    await page.screenshot(path=OUT / "preview-stale.png")
    await prev.get_by_role("button", name="Capture the current target").click()
    await expect(fig).not_to_have_attribute("data-stale", "true", timeout=40000)
    await expect(prev.get_by_role("img", name=re.compile("Screenshot of"))).to_be_visible(timeout=40000)
    check("capturing again clears the out-of-date mark", True)
    await axe(page, "launcher with approved website")

    # Backend enforcement (not just the UI): another origin is refused even with the UI bypassed.
    r = httpx.post(f"{API}/api/preview", json={"url": "https://playwright.dev/"}, timeout=40)
    check("backend refuses an unapproved origin", r.status_code == 400, r.text[:120])
    r = httpx.post(f"{API}/api/runs", json={"target_url": "https://playwright.dev/", "goal": "should be refused"}, timeout=20)
    check("backend refuses a run on an unapproved origin", r.status_code == 400, r.text[:120])
    # /todomvc (no slash) 301-redirects within the origin: allowed.
    p = httpx.post(f"{API}/api/preview", json={"url": ORIGIN + "/todomvc"}, timeout=60).json()
    check("same-origin redirect is followed", p["ok"] and p["final_url"].startswith(TARGET), str(p.get("final_url")))
    return panel


async def start_live(page, panel):
    await panel.get_by_label("Target website").fill(TARGET)
    await panel.get_by_label("Review goal").fill(GOAL)
    await panel.get_by_text("Budget and limits").click()
    for label, v in (("Max cost per run (US$)", "0.1"), ("Max browser steps", "20"), ("Max model calls", "22")):
        await panel.get_by_label(label).fill(v)
    await panel.get_by_role("button", name="Start live run").click()
    await page.wait_for_url(re.compile(r"run=run_"), timeout=20000)
    run_id = re.search(r"run=(run_[0-9a-f]+)", page.url).group(1)
    print("started", run_id, flush=True)
    t0 = time.time()
    shot = 0
    while time.time() - t0 < 600:
        d = httpx.get(f"{API}/api/runs/{run_id}", timeout=20).json()
        if d["run"]["status"] not in ("queued", "running"):
            break
        if shot < 2 and len(d["states"]) >= 2 + shot * 3:
            await page.screenshot(path=OUT / f"run-live-{shot + 1}.png")
            shot += 1
        await asyncio.sleep(3)
    return run_id


async def run_checks(page, run_id):
    d = httpx.get(f"{API}/api/runs/{run_id}", timeout=20).json()
    r = d["run"]
    print("run", r["status"], r["usage"], r["stop_reason"], flush=True)
    check("run recorded the website profile and scope", r.get("target_profile") == "website"
          and r.get("scope_origins") == [ORIGIN] and r["provenance"]["synthetic_fixture"] is False)
    acts = sorted(d["actions"], key=lambda a: a["step"])
    types = [a["action"]["type"] for a in acts]
    print("actions:", [(a["step"], a["action"]["type"], a["target_description"], a["ok"], a.get("error")) for a in acts], flush=True)
    press_ok = [a for a in acts if a["action"]["type"] == "press" and a["ok"]]
    check_ok = [a for a in acts if a["action"]["type"] == "check" and a["ok"]]
    check("explorer added todos with Enter", len(press_ok) >= 2, f"{len(press_ok)} successful press actions")
    check("explorer completed a todo with the checkbox action", len(check_ok) >= 1, f"{len(check_ok)} successful check actions")
    urls = {a["url_after"] for a in acts if a["ok"]}
    check("explorer switched filters", any(u.endswith("#/active") for u in urls) and any(u.endswith("#/completed") for u in urls),
          str(sorted(urls)))
    check("explorer reloaded", "reload" in types)
    check("every recorded page stayed on the approved origin",
          all(a["url_after"].startswith(ORIGIN) or a["url_after"] == "about:blank" for a in acts))
    check("run stayed under US$0.20", r["usage"]["reported_cost_usd"] < 0.20, str(r["usage"]["reported_cost_usd"]))
    await page.goto(UI + f"/?run={run_id}")
    await page.wait_for_selector(".react-flow__node", timeout=60000)
    check("run header labels the public website", await page.get_by_text("Public website").first.is_visible())
    await page.get_by_text("Diagnostics").click()
    check("Diagnostics shows the session isolation and allowed origin",
          await page.get_by_text(re.compile("server data is shared, not isolated")).is_visible()
          and await page.get_by_text(ORIGIN, exact=True).is_visible())
    await page.screenshot(path=OUT / "run-diagnostics.png")
    await page.get_by_text("Diagnostics").click()
    await page.get_by_role("tab", name="Activity").click()
    await page.screenshot(path=OUT / "run-activity.png")
    await page.get_by_role("tab", name="Findings").click()
    await page.screenshot(path=OUT / "run-findings.png")
    await axe(page, "website run view")
    return d


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await (await browser.new_context(viewport={"width": 1440, "height": 900})).new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        panel = await launcher_checks(page)
        run_id = await start_live(page, panel) if ARG == "--live" else ARG
        if run_id:
            d = await run_checks(page, run_id)
            (OUT / "run-record.json").write_text(json.dumps({
                "run": d["run"], "actions": [{k: a.get(k) for k in ("step", "action", "target_description", "ok", "error", "url_after")}
                                             for a in sorted(d["actions"], key=lambda a: a["step"])],
                "findings": d["findings"], "events": [e for e in d["events"] if e["type"] in
                                                      ("explorer_finished", "run_finished", "decision_rejected", "run_error")],
            }, indent=2), "utf-8")
        check("no uncaught page errors", not errors, "; ".join(errors))
        await browser.close()
    fails = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(fails)}/{len(results)} passed")
    sys.exit(1 if fails else 0)


asyncio.run(main())
