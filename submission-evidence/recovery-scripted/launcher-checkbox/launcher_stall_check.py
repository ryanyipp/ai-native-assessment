"""Launcher stall option through the real UI.

capture UI_URL          : fill the launcher three ways and record the POST /api/runs body; the request is aborted,
                          so no run is created and nothing is spent.
e2e UI_URL API_URL OUT  : submit with the stall ticked through a UI wired to the scripted-model server, wait for the
                          run, and save its full record to OUT.
"""
import asyncio
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

from playwright.async_api import async_playwright

REPO = Path(__file__).resolve()
sys.path[:0] = [r"C:\Users\Ryan Yip\Desktop\ai-native-assessment\backend\tests",
                r"C:\Users\Ryan Yip\Desktop\ai-native-assessment\backend\tests\integration"]
from test_review import REQS  # noqa: E402

GOAL = "Explore the dashboard forms"


async def open_launcher(pg, ui):
    await pg.goto(ui + "/workspace")
    dlg_field = pg.get_by_label("Review goal")
    if not await dlg_field.count():
        await pg.get_by_role("button", name="New run").click()
    await dlg_field.wait_for()


async def fill(pg, target, stall, mode="queue_review"):
    await pg.get_by_label("Target website").fill(target)
    await pg.get_by_label("Review goal").fill(GOAL)
    await pg.get_by_label("Requirements (optional)").fill("\n".join(REQS))
    if stall:
        await pg.locator(f'input[type=radio][value="queue_review"]').check()
        await pg.get_by_label(re.compile("Inject a stall")).check()
    if mode != "queue_review":
        await pg.locator(f'input[type=radio][value="{mode}"]').check()


async def capture(ui):
    out = {}
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for name, stall, mode in (("stall off", False, "queue_review"), ("stall on", True, "queue_review"),
                                  ("stall ticked, then single agent", True, "single_agent")):
            pg = await b.new_page(viewport={"width": 1440, "height": 900})
            bodies = []

            async def handle(route, req, bodies=bodies):
                if req.method == "POST":
                    bodies.append(json.loads(req.post_data))
                    await route.abort()  # never reaches the backend: no run, no spend
                else:
                    await route.continue_()

            await pg.route("**/api/runs", handle)
            await open_launcher(pg, ui)
            await fill(pg, "http://localhost:5174/", stall, mode)
            if stall and mode == "queue_review":
                hint = await pg.get_by_label(re.compile("Inject a stall")).locator("xpath=..").inner_text()
                print("hint:", " ".join(hint.split()))
            await pg.get_by_role("button", name="Start live run").click()
            await pg.wait_for_timeout(800)
            body = bodies[0] if bodies else None
            out[name] = body
            print(f"{name}: mode={body and body['mode']} task_lease_s={body and body['limits'].get('task_lease_s')} "
                  f"fault_injection={body and body.get('fault_injection')}")
            await pg.close()
        await b.close()
    ok = (out["stall off"] and "task_lease_s" not in out["stall off"]["limits"] and "fault_injection" not in out["stall off"]
          and out["stall on"]["limits"].get("task_lease_s") == 45 and out["stall on"]["fault_injection"]["stall_s"] == 75
          and out["stall on"]["fault_injection"]["worker"] == "explorer-a"
          and out["stall ticked, then single agent"]["mode"] == "single_agent"
          and "task_lease_s" not in out["stall ticked, then single agent"]["limits"]
          and "fault_injection" not in out["stall ticked, then single agent"])
    print("PASS" if ok else "FAIL", "request bodies as intended")
    return 0 if ok else 1


async def e2e(ui, api, out_path):
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1440, "height": 900})
        await open_launcher(pg, ui)
        await fill(pg, "http://localhost:5174/", True)
        async with pg.expect_response(lambda r: r.url.endswith("/api/runs") and r.request.method == "POST") as resp:
            await pg.get_by_role("button", name="Start live run").click()
        r = await resp.value
        sent = json.loads(r.request.post_data)
        run_id = (await r.json())["id"]
        print("submitted", run_id, "status", r.status, "| sent lease", sent["limits"].get("task_lease_s"),
              "fault", sent.get("fault_injection"))
        await pg.screenshot(path=str(Path(out_path).with_suffix(".launched.png")))
        await b.close()
    while True:
        d = json.load(urllib.request.urlopen(f"{api}/api/runs/{run_id}"))
        if d["run"]["status"] not in ("queued", "running"):
            break
        time.sleep(3)
    Path(out_path).write_text(json.dumps(d, indent=1), "utf-8")
    print("finished", run_id, d["run"]["status"])
    return 0


if __name__ == "__main__":
    if sys.argv[1] == "capture":
        sys.exit(asyncio.run(capture(sys.argv[2])))
    sys.exit(asyncio.run(e2e(sys.argv[2], sys.argv[3], sys.argv[4])))
