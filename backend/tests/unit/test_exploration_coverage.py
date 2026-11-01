"""Coverage separates duplicate work from return trips, new controls and the other explorer's work."""

from flowlens.models.contracts import Observation, ObservedElement
from flowlens.orchestration.coverage import Coverage, control_key


def link(name, href):
    return ObservedElement(id=name, tag="a", role="link", name=name, href=href)


def page(*els):
    return Observation(url="http://h/", title="t", elements=list(els))


DASH, NEW = link("Dashboard", "/"), link("New draft", "/drafts/new")


def test_duplicate_investigation_is_no_progress():
    c = Coverage()
    obs = page(DASH, NEW)
    c.observe(obs)
    c.record(DASH, "Dashboard")
    c.record(NEW, "New draft")
    assert not c.progress(False, obs) and c.exhausted()


def test_return_navigation_to_unexplored_work_is_progress():
    c = Coverage()
    home, form = page(DASH, NEW), page(DASH)
    c.observe(home)
    c.record(DASH, "Dashboard")
    assert not c.progress(False, form)  # the form page itself has nothing left
    assert c.progress(False, home)  # the known Dashboard link leads back to unexplored New draft
    assert not c.exhausted()


def test_known_route_with_new_control_or_state_stays_explorable():
    c = Coverage()
    c.observe(page(DASH))
    c.record(DASH, "Dashboard")
    richer = page(DASH, link("My First Draft", "/drafts/abcdef12"))
    assert c.progress(False, richer)
    assert c.progress(True, page(DASH))  # a new state always counts


def test_second_explorer_is_pointed_at_distinct_work():
    c = Coverage()
    other, free = link("Schedule", "/schedule/new"), link("Help", "/help")
    obs = page(NEW, other, free)
    c.observe(obs)
    c.pursuing["explorer-a"] = control_key(other)
    text = c.summary("explorer-b", obs)
    assert "Unexplored on this page: New draft, Help." in text
    assert "explorer-a is following 'Schedule'" in text


def test_form_controls_are_not_coverage_work():
    c = Coverage()
    button = ObservedElement(id="b", tag="button", role="button", name="Save", form_index=0)
    c.observe(page(button))
    assert c.exhausted()
