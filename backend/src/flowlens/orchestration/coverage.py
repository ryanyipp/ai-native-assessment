"""Shared exploration memory: what the explorers followed, what it led to, and what is still open.

A link is identified by where it goes, so "Dashboard" counts once and "Back to my requests" matches
"My requests". Links to one id-based route form a record group: a few records are sampled, and sampling
continues while samples keep showing different controls. Other records stay listed as unvisited.

Pending work is not progress. Only new controls or a new page structure count as a discovery, and known
links stay allowed once a page has no open work and they lead to some, so return navigation still works. Claims are taken before
the model plans and expire, so a stalled worker cannot hold work for ever.
"""

from __future__ import annotations

import time
from urllib.parse import urlsplit

from flowlens.browser.engine import normalise_route, page_destinations

NO_PROGRESS_LIMIT = 3  # consecutive known-control steps with no discovery; a two-hop return trip stays possible
REFUSAL_LIMIT = 2  # refused repeats per task, so a stubborn model cannot spend the budget arguing
RECORD_SAMPLES = 2  # records opened per route before a matching sample closes the group
MAX_FAILURES = 2  # failed attempts before a control stops being offered; it never counts as followed
CLAIM_TTL_S = 120.0


def target(url: str) -> str:
    query = urlsplit(url).query
    return normalise_route(url) + (f"?{query}" if query else "")


def control_key(el) -> tuple[str, str, str]:
    return (el.role, "", target(el.href)) if el.href else (el.role, el.name, "")


def is_record(key: tuple[str, str, str]) -> bool:
    return ":id" in key[2]


def page_controls(obs) -> dict[tuple[str, str, str], object]:
    """Links and buttons outside forms. Forms belong to the input tester."""
    return {control_key(e): e for e in obs.elements if e.role in ("link", "button") and e.form_index is None}


class Coverage:
    def __init__(self, clock=time.monotonic) -> None:
        self.clock = clock
        self.seen: dict[tuple, str] = {}
        self.followed: dict[tuple, str] = {}  # control -> summary of the state it reached
        self.leads_to: dict[tuple, str] = {}  # control -> page it reached
        self.pages: dict[str, set] = {}  # page -> controls on it
        self.structures: set = set()
        self.members: dict[tuple, dict] = {}  # record group -> every record link seen, with its name
        self.visited: dict[tuple, set] = {}  # record group -> records opened
        self.samples: dict[tuple, set] = {}  # record group -> page structures seen
        self.sample_was_new: dict[tuple, bool] = {}
        self.failures: dict[tuple, int] = {}
        self.claims: dict[str, tuple[tuple, float]] = {}  # explorer -> (control, expiry)

    def observe(self, obs) -> bool:
        """Remember a page. True only for a real discovery: an unseen control or page structure."""
        controls = page_controls(obs)
        new = [k for k in controls if k not in self.seen]
        for k, el in controls.items():
            self.seen.setdefault(k, el.name)
        for el in obs.elements:  # every row, though page_controls keeps one per group
            if el.role == "link" and el.href and el.form_index is None and is_record(control_key(el)):
                self.members.setdefault(control_key(el), {})[el.href] = el.name
        self.pages.setdefault(target(obs.url), set()).update(controls)
        structure = (normalise_route(obs.url), tuple(page_destinations(obs)))
        fresh = structure not in self.structures
        self.structures.add(structure)
        return bool(new) or fresh

    def is_new(self, el) -> bool:
        key = control_key(el)
        if is_record(key):
            return self.is_open(key) and el.href not in self.visited.get(key, ())
        return self.is_open(key)

    def is_open(self, key: tuple) -> bool:
        if self.failures.get(key, 0) >= MAX_FAILURES:
            return False
        if not is_record(key):
            return key not in self.followed
        visited = self.visited.get(key, set())
        if not set(self.members.get(key, ())) - visited:
            return False
        return len(visited) < RECORD_SAMPLES or self.sample_was_new.get(key, False)

    def record(self, el, obs, summary: str) -> None:
        """A successful model-chosen action. Setup replay and failed actions never reach this."""
        if el is None:
            return
        key = control_key(el)
        self.followed[key], self.leads_to[key] = summary, target(obs.url)
        if is_record(key):
            structure = tuple(page_destinations(obs))
            samples = self.samples.setdefault(key, set())
            self.sample_was_new[key] = structure not in samples
            samples.add(structure)
            self.visited.setdefault(key, set()).add(el.href)
            self.members.setdefault(key, {})[el.href] = el.name

    def failed(self, el) -> None:
        if el is not None:
            key = control_key(el)
            self.failures[key] = self.failures.get(key, 0) + 1

    # --- claims ------------------------------------------------------------------------

    def claimed_by_others(self, agent: str) -> dict[tuple, str]:
        now = self.clock()
        return {k: a for a, (k, until) in self.claims.items() if a != agent and until > now}

    def assign(self, agent: str, obs) -> tuple | None:
        """Claim open work for this planning call, so explorers planning at once pick different things."""
        others = self.claimed_by_others(agent)
        pick = next((k for k in page_controls(obs) if self.is_open(k) and k not in others), None)
        if pick is None:
            self.claims.pop(agent, None)
        else:
            self.claims[agent] = (pick, self.clock() + CLAIM_TTL_S)
        return pick

    def release(self, agent: str) -> None:
        self.claims.pop(agent, None)

    # --- decisions ---------------------------------------------------------------------

    def reaches_open(self, key: tuple, seen: set | None = None) -> bool:
        seen = set() if seen is None else seen
        page = self.leads_to.get(key)
        if page is None or page in seen:
            return False
        seen.add(page)
        return any(self.is_open(k) or self.reaches_open(k, seen) for k in self.pages.get(page, ()))

    def next_hop(self, agent: str, obs) -> tuple | None:
        """The known control that heads to open work, shortest route first. It never stays on this page."""
        others = self.claimed_by_others(agent)
        here = target(obs.url)
        frontier = [(k, k) for k in page_controls(obs) if k in self.leads_to and self.leads_to[k] != here]
        seen = {here}
        while frontier:
            step = []
            for first, key in frontier:
                page = self.leads_to[key]
                if page in seen:
                    continue
                seen.add(page)
                controls = self.pages.get(page, ())
                if any(self.is_open(k) and k not in others for k in controls):
                    return first
                step += [(first, k) for k in controls if k in self.leads_to]
            frontier = step
        return None

    def nothing_left(self, agent: str, obs) -> bool:
        others = self.claimed_by_others(agent)
        return not any(self.is_open(k) and k not in others for k in page_controls(obs)) and not self.next_hop(agent, obs)

    def repeat_reason(self, agent: str, el, obs) -> str | None:
        """Why not to use this control now. Known links may lead to open work once this page has none."""
        key = control_key(el)
        owner = self.claimed_by_others(agent).get(key)
        if owner:
            return f"{owner} is already investigating '{self.seen.get(key, el.name)}'."
        if self.is_new(el):
            return None
        here = [k for k in page_controls(obs) if self.is_open(k) and k not in self.claimed_by_others(agent)]
        if not here and self.leads_to.get(key) != target(obs.url) and self.reaches_open(key):
            return None
        tried = f"'{el.name}' was already followed and reached: {self.followed.get(key, 'nothing recorded')}."
        left = self.names([k for k in page_controls(obs) if self.is_open(k)])
        return f"{tried} Still unexplored here: {left}. Nothing further is reachable through that control."

    # --- what the model reads ----------------------------------------------------------

    def label(self, key: tuple) -> str:
        if not is_record(key):
            return self.seen.get(key, key[1])
        visited = self.visited.get(key, ())  # name a record still to open, never one already sampled
        name = next((n for h, n in self.members.get(key, {}).items() if h not in visited), key[2])
        return f"{name} ({key[2]} records)"

    def names(self, keys) -> str:
        return ", ".join(self.label(k) for k in keys) or "none"

    def summary(self, agent: str, obs) -> str:
        here = page_controls(obs)
        others = self.claimed_by_others(agent)
        mine = self.claims.get(agent, (None,))[0]
        done = [f"'{self.label(k)}' -> {self.followed[k]}" for k in self.followed][:20]
        todo = [k for k in here if self.is_open(k) and k not in others]
        elsewhere = [k for k in self.seen if self.is_open(k) and k not in here and k not in others]
        routes = [f"{k[2]}: {len(self.visited.get(k, ()))} sampled of {len(m)} seen, "
                  f"{'keep sampling' if self.is_open(k) else 'enough sampled, others unvisited'}"
                  for k, m in self.members.items()]
        claimed = [f"{a} is investigating '{self.label(k)}'" for k, a in others.items()]
        hop = None if todo else self.next_hop(agent, obs)
        return ("Exploration memory, shared across tasks and explorers.\n"
                f"Already investigated: {'; '.join(done) or 'nothing yet'}.\n"
                f"Records: {'; '.join(routes) or 'none'}.\n"
                f"Unexplored on this page: {self.names(todo)}.\n"
                f"Unexplored elsewhere: {self.names(elsewhere)}.\n"
                f"Other worker: {'; '.join(claimed) or 'nothing claimed'}.\n"
                + (f"Your assignment: {self.label(mine)}.\n" if mine else "")
                + (f"Next step towards unexplored work: {self.label(hop)}.\n" if hop else "")
                + "Choose unexplored controls first. Known links are fine when they lead to unexplored work. "
                "If nothing is unexplored, finish.")
