r"""Cancellation through the real UI against scripted_server.py (start it with --delay 3). No spend.

Start scripted_server.py and a Vite dev server with FLOWLENS_API_URL pointing at it, then:
    backend\.venv\Scripts\python scripts\cancel_demo_check.py OUT_DIR [UI_URL] [API_URL] [SERVER_PID]
"""

import asyncio
import csv
import io
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

OUT = Path(sys.argv[1])
UI = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:5273"
API = sys.argv[3] if len(sys.argv) > 3 else "http://127.0.0.1:8010"
SERVER = int(sys.argv[4]) if len(sys.argv) > 4 else None
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print("PASS" if ok else "FAIL", name, detail, flush=True)


def browsers_under(pid):
    """Chromium processes descended from the server (Windows)."""
    if pid is None:
        return None
    rows = subprocess.run(["powershell", "-NoProfile", "-Command",
                           "Get-CimInstance Win32_Process | Select ProcessId,ParentProcessId,Name | "
                           "ConvertTo-Csv -NoTypeInformation"], capture_output=True, text=True).stdout
    procs = [(int(r["ProcessId"]), int(r["ParentProcessId"]), r["Name"]) for r in csv.DictReader(io.StringIO(rows))]
    seen, grew = {pid}, True
    while grew:
        grew = False
        for p, parent, _ in procs:
            if parent in seen and p not in seen:
                seen.add(p)
                grew = True
    return sum(1 for p, _, n in procs if p in seen and ("chrome" in n.lower() or "headless" in n.lower()))


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        page = await (await b.new_context(viewport={"width": 1440, "height": 900})).new_page()
        replies = []
        page.on("response", lambda r: replies.append(r.status) if r.url.endswith("/cancel") else None)
        await page.goto(UI + "/workspace")
        await page.get_by_label("Target website").fill("http://localhost:5174/")
        await page.get_by_label("Review goal").fill("Explore the dashboard forms")
        await page.get_by_text("Shared queue: two explorers").click()
        await page.get_by_role("button", name="Start live run").click()
        await page.wait_for_url(re.compile(r"run=run_"), timeout=20000)
        run_id = re.search(r"run=(run_[0-9a-f]+)", page.url).group(1)
        print("run", run_id, flush=True)
        for _ in range(120):
            d = httpx.get(f"{API}/api/runs/{run_id}").json()
            if d["run"]["usage"]["model_calls"] >= 3:
                break
            await asyncio.sleep(0.5)
        check("scripted label", d["run"]["provenance"]["mocked_model"] and not d["run"]["provenance"]["live"])
        during = browsers_under(SERVER)
        for _ in range(40):  # a single sample can fall between two browser launches
            if during is None or during > 0:
                break
            await asyncio.sleep(0.25)
            during = browsers_under(SERVER)
        check("browsers open while active", during is None or during > 0, str(during))
        await page.get_by_role("button", name="Cancel run").click()
        t0 = time.time()
        await page.get_by_role("button", name="Cancelling").wait_for(timeout=3000)
        check("button shows Cancelling", True)
        second = httpx.post(f"{API}/api/runs/{run_id}/cancel")
        check("repeat cancel while stopping", second.status_code in (202, 409), str(second.status_code))
        for _ in range(120):
            d = httpx.get(f"{API}/api/runs/{run_id}").json()
            if d["run"]["status"] not in ("queued", "running"):
                break
            await asyncio.sleep(0.25)
        print("stopped after", round(time.time() - t0, 1), "s", flush=True)
        await asyncio.sleep(1)  # the blocking calls above hold back Playwright's response events
        check("UI click returned 202", 202 in replies, str(replies))
        check("terminal status cancelled", d["run"]["status"] == "cancelled", d["run"]["stop_reason"][:90])
        await page.get_by_text("Stopped early").wait_for(timeout=6000)
        toolbar = page.locator('[data-testid="run-toolbar"]')
        check("UI shows Cancelled", await toolbar.get_by_text("Cancelled", exact=True).count() > 0)
        check("Cancel button gone", await page.get_by_role("button", name=re.compile(r"^(Cancel run|Cancelling)")).count() == 0)
        await page.screenshot(path=OUT / "cancelled-run.png")
        check("partial evidence remains", d["actions"] and d["evidence"], f'{len(d["actions"])} actions')
        check("no ready or claimed tasks", not [t for t in d["tasks"] if t["status"] in ("ready", "claimed")])
        asked = next(e for e in d["events"] if e["type"] == "cancel_requested")
        after = [e for e in d["events"] if e["seq"] > asked["seq"]]
        check("workers stopped their tasks", any(e["type"] == "task_cancelled" for e in after))
        check("no claims or accepted results after the request",
              not {"task_claimed", "result_accepted", "candidate_reported"} & {e["type"] for e in after})
        check("no browser action started after the request",
              not [a for a in d["actions"] if a["started_at"] > asked["created_at"]],
              f'{sum(e["type"] == "action_executed" for e in after)} in-progress action(s) finished and were recorded')
        check("no successful model call after the request", not [
            e for e in after if e["type"] == "model_call" and e["data"].get("ok")])
        print("calls_without_cost", d["run"]["usage"]["calls_without_cost"], flush=True)
        await asyncio.sleep(3)
        left = browsers_under(SERVER)
        check("browser processes closed", left in (None, 0), str(left))
        before = len(httpx.get(f"{API}/api/runs/{run_id}").json()["events"])
        await asyncio.sleep(5)
        check("no new events after the end", len(httpx.get(f"{API}/api/runs/{run_id}").json()["events"]) == before)
        r = httpx.post(f"{API}/api/runs/{run_id}/cancel")
        check("cancel after the end is 409", r.status_code == 409, r.text[:90])
        check("cancel of an unknown run is 404", httpx.post(f"{API}/api/runs/run_missing/cancel").status_code == 404)
        (OUT / f"{run_id}-detail.json").write_text(json.dumps(d, indent=1), "utf-8")
        await b.close()
    print(f"{sum(results)}/{len(results)} passed")
    sys.exit(0 if all(results) else 1)


asyncio.run(main())
