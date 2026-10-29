r"""Browser check of a saved queue_review run's Activity task board. Makes no model calls.

Usage (repo root): backend\.venv\Scripts\python scripts\ui_check_queue.py RUN_ID OUT_DIR
"""

import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

RUN, OUT = sys.argv[1], Path(sys.argv[2])
AXE = Path(__file__).resolve().parents[1] / "frontend" / "node_modules" / "axe-core" / "axe.min.js"


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ok = []
    async with async_playwright() as p:
        b = await p.chromium.launch()
        page = await (await b.new_context(viewport={"width": 1440, "height": 900})).new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto(f"http://localhost:5173/?run={RUN}")
        await page.wait_for_selector(".react-flow__node")
        await page.wait_for_timeout(700)
        ok.append(("header names shared queue", await page.get_by_text("Shared queue · 2 explorers").is_visible()))
        await page.screenshot(path=OUT / "queue-map.png")
        await page.get_by_role("tab", name="Activity").click()
        board = page.get_by_role("region", name="Tasks")
        ok.append(("task board visible", await board.is_visible()))
        for s in ("completed", "unfinished", "blocked"):
            ok.append((f"board shows {s} tasks", await board.get_by_text(s, exact=True).count() > 0))
        for w in ("explorer-a", "explorer-b", "input-tester", "verifier"):
            ok.append((f"board names {w}", await board.get_by_text(w, exact=True).count() > 0))
        ok.append(("board shows handed-off tasks", await board.get_by_text("handed off").count() > 0))
        trail = page.get_by_role("region", name="Handoffs between workers")
        ok.append(("trail has claims", await trail.get_by_text("Task claimed", exact=True).count() > 0))
        await board.screenshot(path=OUT / "queue-task-board.png")
        await page.screenshot(path=OUT / "queue-activity.png")
        await page.add_script_tag(path=str(AXE))
        res = await page.evaluate("async () => (await axe.run(document)).violations.filter(v => ['serious','critical'].includes(v.impact)).map(v => v.id)")
        ok.append((f"axe activity: no serious violations {res}", not res))
        ok.append(("no page errors", not errors))
        await b.close()
    for name, passed in ok:
        print(("PASS " if passed else "FAIL ") + name)
    print(f"{sum(p for _, p in ok)}/{len(ok)} checks passed")
    sys.exit(0 if all(p for _, p in ok) else 1)


asyncio.run(main())
