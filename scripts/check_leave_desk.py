"""Deterministic Playwright check of both Leave Desk builds. No FlowLens agents, no model calls.

Run from the repository root with the two builds started (see fixtures/leave-desk/README.md):

    backend\\.venv\\Scripts\\python scripts\\check_leave_desk.py

Every check reports whether the requirement held, then compares that with what each build should do.
Exit code 0 means all defects are present on broken, absent on corrected, and the controls pass on both.
"""

from __future__ import annotations

import re
import sys

import httpx
from playwright.sync_api import Browser, Page, sync_playwright

BROKEN_URL = "http://127.0.0.1:5178"
CORRECTED_URL = "http://127.0.0.1:5179"
DEFECTS = ("L2", "L4", "L5", "L6", "L8")


def _session(browser: Browser, url: str):
    ws = httpx.post(url + "/__fixture/workspaces", timeout=10).json()
    context = browser.new_context(base_url=url)
    context.add_cookies([{"name": ws["cookie"], "value": ws["workspace"], "url": url}])
    context.set_default_timeout(5000)
    return context, context.new_page()


def _submit(page: Page, start: str, end: str, reason: str = "") -> None:
    page.goto("/requests/new")
    page.get_by_label("Start date").fill(start)
    page.get_by_label("End date").fill(end)
    page.get_by_label("Reason (optional)").fill(reason)
    page.get_by_role("button", name="Submit").click()


def _rejected(page: Page) -> bool:
    return page.get_by_role("alert").count() == 1


def _count(page: Page) -> int:
    page.goto("/requests")
    return page.get_by_role("list", name="Requests").get_by_role("listitem").count()


def _dashboard(page: Page) -> tuple[int, int]:
    page.goto("/")
    text = page.locator("main").inner_text()
    return (int(re.search(r"Remaining balance: (-?\d+) days", text).group(1)),
            int(re.search(r"Pending requests: (\d+)", text).group(1)))


def check_seed(page: Page) -> bool:
    return _count(page) == 3 and _dashboard(page) == (12, 1) and all(
        page.goto(f"/requests?status={s}") and page.get_by_role("list", name="Requests").get_by_role("listitem").count() == 1
        for s in ("Pending", "Approved", "Cancelled"))


def check_l1(page: Page) -> bool:
    _submit(page, "2026-08-10", "2026-08-09")
    return _rejected(page) and _count(page) == 3


def check_l2(page: Page) -> bool:
    _submit(page, "2026-08-01", "2026-08-13")  # 13 days on a 12-day balance
    return _rejected(page) and _count(page) == 3 and _dashboard(page)[0] == 12


def check_l3(page: Page) -> bool:
    _submit(page, "2026-08-10", "2026-08-10", "x" * 201)
    rejected = _rejected(page) and _count(page) == 3
    _submit(page, "2026-08-10", "2026-08-10", "x" * 200)
    return rejected and not _rejected(page) and _count(page) == 4


def check_l4(page: Page) -> bool:
    before = _dashboard(page)[1]
    page.goto("/requests?status=Pending")
    page.get_by_role("list", name="Requests").get_by_role("link").first.click()
    page.get_by_role("link", name="Cancel request").click()
    unchanged = page.get_by_role("dialog").is_visible() and "Pending" in page.locator("dl").inner_text()
    page.get_by_role("button", name="Confirm").click()
    return unchanged and "Cancelled" in page.locator("dl").inner_text() and _dashboard(page)[1] == before - 1


def check_l5(page: Page) -> bool:
    page.goto("/requests/1002/edit")
    page.get_by_label("End date").fill("2026-07-23")
    page.get_by_role("button", name="Save changes").click()
    text = page.locator("dl").inner_text()
    return "Moving house" in text and "2026-07-23" in text and "2026-07-20" in text and "Annual" in text


def check_l6(page: Page) -> bool:
    page.goto("/profile")
    page.get_by_label("Display name").fill("Sam Lee")
    page.get_by_label("Email", exact=True).fill("sam@example.test")
    page.get_by_label("Email me updates").check()
    page.get_by_role("button", name="Save").click()
    saved = page.get_by_role("status").inner_text() == "Saved."
    page.reload()
    return (saved and page.get_by_label("Display name").input_value() == "Sam Lee"
            and page.get_by_label("Email", exact=True).input_value() == "sam@example.test"
            and page.get_by_label("Email me updates").is_checked())


def check_l7(page: Page) -> bool:
    page.goto("/requests")
    for status in ("Pending", "Approved", "Cancelled"):
        page.get_by_role("navigation", name="Status filter").get_by_role("link", name=status).click()
        rows = page.get_by_role("list", name="Requests").get_by_role("listitem").all_inner_texts()
        if not rows or not all(row.endswith(status) for row in rows):
            return False
    return True


def check_l8(page: Page) -> bool:
    page.goto("/calendar")
    text = page.get_by_role("list", name="Team leave").inner_text()
    return "(Cancelled)" not in text and "(Pending)" in text and "(Approved)" in text


CHECKS = {"seed": check_seed, "L1": check_l1, "L2": check_l2, "L3": check_l3, "L4": check_l4,
          "L5": check_l5, "L6": check_l6, "L7": check_l7, "L8": check_l8}


def run(broken_url: str = BROKEN_URL, corrected_url: str = CORRECTED_URL) -> list[str]:
    """Print the results and return the checks that did not match the expected behaviour."""
    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        print(f"{'check':6} {'broken':8} {'corrected':10} verdict")
        for name, check in CHECKS.items():
            held = {}
            for url in (broken_url, corrected_url):
                context, page = _session(browser, url)  # a fresh workspace per check
                held[url] = check(page)
                context.close()
            ok = held[broken_url] == (name not in DEFECTS) and held[corrected_url]
            print(f"{name:6} {'holds' if held[broken_url] else 'VIOLATED':8} "
                  f"{'holds' if held[corrected_url] else 'VIOLATED':10} {'as expected' if ok else 'UNEXPECTED'}")
            if not ok:
                failures.append(name)
        browser.close()
    return failures


if __name__ == "__main__":
    sys.exit(1 if run() else 0)
