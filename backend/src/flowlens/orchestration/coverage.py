"""What explorers have followed so far, shared across a queue run.

A control is identified by role, name and normalised link target, never by URL alone: a listed record or a
new button on a known page stays unexplored, while "Dashboard" seen on every page counts once. Coverage only
informs the explorers and the no-progress stop. It never refuses a link, so return navigation stays possible.
"""

from __future__ import annotations

from flowlens.browser.engine import normalise_route

NO_PROGRESS_LIMIT = 2  # consecutive steps with no new state and nothing unexplored on the page reached


def control_key(el) -> tuple[str, str, str]:
    return el.role, el.name, normalise_route(el.href) if el.href else ""


def page_controls(obs) -> dict[tuple[str, str, str], str]:
    """Links and buttons outside forms. Forms belong to the input tester."""
    return {control_key(e): e.name for e in obs.elements if e.role in ("link", "button") and e.form_index is None}


class Coverage:
    def __init__(self) -> None:
        self.seen: dict[tuple[str, str, str], str] = {}
        self.followed: dict[tuple[str, str, str], str] = {}  # control -> summary of the state it reached
        self.pursuing: dict[str, tuple[str, str, str]] = {}  # explorer -> control it is following now

    def observe(self, obs) -> None:
        self.seen.update(page_controls(obs))

    def record(self, el, result_summary: str) -> None:
        if el is not None:
            self.followed[control_key(el)] = result_summary

    def open_controls(self, obs=None) -> dict[tuple[str, str, str], str]:
        pool = page_controls(obs) if obs is not None else self.seen
        return {k: v for k, v in pool.items() if k not in self.followed}

    def exhausted(self) -> bool:
        return not self.open_controls()

    def progress(self, new_state: bool, obs) -> bool:
        """Reaching a page with unexplored controls is progress, so a needed return trip is not a loop."""
        return new_state or bool(self.open_controls(obs))

    def summary(self, agent: str, obs) -> str:
        here = page_controls(obs)
        done = [f"'{name}' -> {self.followed[k]}" for k, name in here.items() if k in self.followed]
        others = {k for a, k in self.pursuing.items() if a != agent}
        todo = [name for k, name in here.items() if k not in self.followed and k not in others]
        elsewhere = [name for k, name in self.seen.items() if k not in self.followed and k not in here and k not in others]
        claimed = [f"{a} is following '{self.seen.get(k, k[1])}'" for a, k in self.pursuing.items() if a != agent]
        return ("Coverage so far.\n"
                f"Followed from this page: {'; '.join(done) or 'none'}.\n"
                f"Unexplored on this page: {', '.join(todo) or 'none'}.\n"
                f"Unexplored elsewhere: {', '.join(elsewhere) or 'none'}.\n"
                f"Claimed by the other explorer: {'; '.join(claimed) or 'nothing'}.\n"
                "Choose unexplored controls first. Known links are fine when they lead to unexplored work. "
                "If nothing is unexplored, finish.")
