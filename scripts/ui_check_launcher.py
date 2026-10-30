r"""Browser check of the run launcher layout (no runs are started; no model calls).

Usage: backend\.venv\Scripts\python scripts\ui_check_launcher.py OUT_DIR [UI_URL]
"""

import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/launcher")
UI = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:5173"
results: list[tuple[str, bool, str]] = []
LONG = " ".join(["Explore the shopping journey, open product pages, add an item to the cart and inspect the cart."] * 12)


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail else ""), flush=True)


async def run(page, w, h):
    await page.set_viewport_size({"width": w, "height": h})
    await page.goto(UI + "/")
    panel = page.get_by_role("complementary", name="New review run")
    await panel.wait_for()
    await panel.get_by_label("Shared queue: two explorers, tester, verifier").check()
    tops = {}
    for name, loc in (("target", panel.get_by_label("Target website")), ("goal", panel.get_by_label("Review goal")),
                      ("requirements", panel.get_by_label("Requirements (optional)")),
                      ("workflow", panel.get_by_role("group", name="Workflow")), ("budget", panel.get_by_text("Budget and limits"))):
        tops[name] = (await loc.bounding_box())["y"]
    tops["fault"] = (await panel.get_by_text("Inject a stall (labelled fault)").bounding_box())["y"]
    order = sorted(tops, key=tops.get)
    check(f"{w}px: order Target, Goal, Requirements, Workflow, fault, Budget",
          order == ["target", "goal", "requirements", "workflow", "fault", "budget"], str(order))

    goal = panel.get_by_label("Review goal")
    h0 = (await goal.bounding_box())["height"]
    await goal.fill(LONG)
    await page.wait_for_timeout(100)
    h1 = (await goal.bounding_box())["height"]
    css = await goal.evaluate("e => [getComputedStyle(e).resize, getComputedStyle(e).maxHeight]")
    check(f"{w}px: goal grows with text and stops at its maximum", h1 > h0 and h1 <= 256 + 1, f"{h0:.0f} -> {h1:.0f}px")
    check(f"{w}px: goal can be resized vertically, capped", css == ["vertical", "256px"], str(css))
    req = panel.get_by_label("Requirements (optional)")
    r0 = (await req.bounding_box())["height"]
    await req.fill("\n".join(f"R{i}. Requirement number {i} must hold." for i in range(1, 30)))
    await page.wait_for_timeout(100)
    r1 = (await req.bounding_box())["height"]
    check(f"{w}px: requirements grow and stop at their maximum", r1 > r0 and r1 <= 320 + 1, f"{r0:.0f} -> {r1:.0f}px")
    # Manual vertical resize sticks (auto-grow never shrinks it back).
    await req.evaluate("e => { e.style.height = '300px' }")
    await req.press("End")
    await req.type(" more")
    check(f"{w}px: a manual height is kept while typing", abs((await req.bounding_box())["height"] - 300) <= 1)

    # Values and workflow selection preserved across workflow and fault changes.
    await panel.get_by_label("Inject a stall (labelled fault)").check()
    await panel.get_by_label("Single-agent baseline").check()
    await panel.get_by_label("Shared queue: two explorers, tester, verifier").check()
    ok = (await goal.input_value() == LONG and (await req.input_value()).startswith("R1.")
          and await panel.get_by_label("Shared queue: two explorers, tester, verifier").is_checked()
          and await panel.get_by_label("Inject a stall (labelled fault)").is_checked())
    check(f"{w}px: entered values and workflow selection are preserved", ok)

    # Buttons stay visible and never cover a field, even scrolled to the end.
    actions = page.get_by_test_id("launcher-actions")
    await panel.get_by_text("Budget and limits").click()
    last = panel.get_by_label("Max output tokens per call")
    await last.scroll_into_view_if_needed()
    a, f = await actions.bounding_box(), await last.bounding_box()
    vis = await panel.get_by_role("button", name="Preview page").is_visible() and await panel.get_by_role("button", name="Start live run").is_visible()
    in_view = a["y"] >= 0 and a["y"] + a["height"] <= h + 1
    check(f"{w}px: Preview/Start visible in the viewport and not covering fields",
          vis and in_view and f["y"] + f["height"] <= a["y"] + 1, f"actions y={a['y']:.0f}, last field bottom={f['y'] + f['height']:.0f}")
    await goal.scroll_into_view_if_needed()
    g = await goal.bounding_box()
    a = await actions.bounding_box()
    check(f"{w}px: buttons do not cover the goal field", g["y"] + g["height"] <= a["y"] + 1 or g["y"] >= a["y"] + a["height"])
    check(f"{w}px: no horizontal overflow", not await page.evaluate("document.documentElement.scrollWidth > window.innerWidth"))
    await page.screenshot(path=OUT / f"launcher-{w}.png", full_page=False)


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        page = await (await b.new_context()).new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        for w, h in ((1440, 900), (1024, 768), (390, 844)):
            await run(page, w, h)
        check("no uncaught page errors", not errors, "; ".join(errors))
        await b.close()
    fails = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(fails)}/{len(results)} passed")
    sys.exit(1 if fails else 0)


asyncio.run(main())
