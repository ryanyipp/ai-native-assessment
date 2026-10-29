r"""Smoke check of a fresh FlowLens setup (native or Docker). No model calls.

Checks: the backend answers and has no API key configured (demo mode), the recorded demo runs are
loaded and labelled, a run's map, evidence and report open in the UI, live runs are disabled, and
each fixture origin can be previewed through the backend (a real screenshot, no model).

Usage: python scripts/check_setup.py UI_URL API_URL FIXTURE_URL [FIXTURE_URL ...] [--out DIR]
  e.g. python scripts/check_setup.py http://localhost:5173 http://localhost:8000 http://localhost:5174/ http://localhost:5176/
"""

import asyncio
import base64
import sys
from pathlib import Path

import httpx
from playwright.async_api import async_playwright, expect

args = [a for a in sys.argv[1:] if not a.startswith("--out")]
OUT = Path(next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--out=")), "setup-check"))
UI, API, FIXTURES = args[0].rstrip("/"), args[1].rstrip("/"), args[2:]
DEMO = ["run_a572a9bf88c5", "run_d50048493cc5", "run_a54099283d9d", "run_53d7009ff711",
        "run_fc9eba62a54c", "run_15f19bf8bb46", "run_40e786578fef"]
results: list[tuple[str, bool, str]] = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail else ""), flush=True)


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    h = httpx.get(f"{API}/api/health", timeout=20).json()
    check("backend health", h["ok"], f"model {h['model']}")
    check("no API key configured (demo mode)", h["api_key_configured"] is False)
    runs = {r["id"]: r for r in httpx.get(f"{API}/api/runs", timeout=20).json()}
    check("all recorded demo runs loaded", all(r in runs for r in DEMO), f"{sum(r in runs for r in DEMO)}/{len(DEMO)}")
    check("demo runs labelled as imported", all((runs.get(r) or {}).get("imported_from") for r in DEMO))
    check("statuses include completed, partial and failed",
          {"completed", "partial", "failed"} <= {runs[r]["status"] for r in DEMO if r in runs})
    for fx in FIXTURES:
        p = httpx.post(f"{API}/api/preview", json={"url": fx}, timeout=60)
        ok = p.status_code == 200 and p.json()["ok"] and base64.b64decode(p.json()["image_png_base64"])[:4] == b"\x89PNG"
        check(f"fixture {fx} previews through the backend", ok, p.json().get("title", p.text[:100]) if p.status_code == 200 else p.text[:120])
    r = httpx.post(f"{API}/api/runs", json={"target_url": FIXTURES[0] if FIXTURES else "http://localhost:5174/",
                                             "goal": "should be refused without a key"}, timeout=20)
    check("backend refuses live runs without a key", r.status_code == 400, r.text[:100])

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await (await browser.new_context(viewport={"width": 1440, "height": 900})).new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto(UI + "/")
        panel = page.get_by_role("complementary", name="New review run")
        await expect(panel).to_be_visible(timeout=30000)
        check("launcher disables live runs without a key", await panel.get_by_role("button", name="Start live run").is_disabled()
              and await panel.get_by_text("Live runs unavailable").is_visible())
        await page.goto(UI + "/?run=run_a572a9bf88c5")
        await page.wait_for_selector(".react-flow__node", timeout=60000)
        check("demo run map renders", await page.locator(".react-flow__node").count() > 0)
        check("run header shows Recorded demo result", await page.get_by_text("Recorded demo result").is_visible())
        await page.get_by_role("tab", name="Findings").click()
        check("findings render", await page.get_by_role("tabpanel").get_by_text("Confirmed").first.is_visible())
        await page.screenshot(path=OUT / "demo-run.png")
        d = httpx.get(f"{API}/api/runs/run_a572a9bf88c5", timeout=20).json()
        shot = next(e["id"] for e in d["evidence"] if e["kind"] == "screenshot")
        a = httpx.get(f"{UI}/api/artifacts/{shot}", timeout=20)
        check("saved screenshot served through the UI proxy", a.status_code == 200 and a.content[:4] == b"\x89PNG")
        await page.goto(UI + "/api/runs/run_a54099283d9d/report")
        check("report shows recorded-result and incomplete banners",
              await page.get_by_text("Recorded result.").is_visible() and await page.get_by_text("Incomplete review.").is_visible())
        await page.screenshot(path=OUT / "demo-report.png", full_page=True)
        md = httpx.get(f"{API}/api/runs/run_53d7009ff711/report.md", timeout=20)
        check("Markdown report downloads for the failed run", md.status_code == 200 and "Stopped by an error" in md.text)
        check("no uncaught page errors", not errors, "; ".join(errors))
        await browser.close()
    fails = [x for x in results if not x[1]]
    print(f"\n{len(results) - len(fails)}/{len(results)} passed")
    sys.exit(1 if fails else 0)


asyncio.run(main())
