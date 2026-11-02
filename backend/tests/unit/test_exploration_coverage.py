"""Shared exploration memory: repeats, return trips, record sampling, failures and claims."""

from flowlens.models.contracts import Observation, ObservedElement
from flowlens.orchestration.coverage import Coverage, control_key


def link(name, href):
    return ObservedElement(id=name, tag="a", role="link", name=name, href=href)


def page(url, *els):
    return Observation(url=f"http://h{url}", title="t", elements=list(els))


DASH, LIST, CAL = link("Dashboard", "/"), link("My requests", "/requests"), link("Calendar", "/calendar")
NAV = (DASH, LIST, CAL)


def follow(c, el, *els):
    obs = page(el.href, *els)
    c.observe(obs)
    c.record(el, obs, f"page {el.name}")
    return obs


def rows():
    return [link(n, f"/requests/{i}") for i, n in enumerate("ABCD", 1)]


def test_two_explorers_planning_at_once_get_different_work():
    c = Coverage()
    obs = page("/", *NAV)
    c.observe(obs)
    assert c.assign("explorer-a", obs) != c.assign("explorer-b", obs)
    text = c.summary("explorer-b", obs)
    assert "explorer-a is investigating" in text and "Your assignment:" in text


def test_a_second_explorer_is_refused_the_claimed_control():
    c = Coverage()
    obs = page("/", DASH)
    c.observe(obs)
    c.assign("explorer-a", obs)
    assert "explorer-a is already investigating" in c.repeat_reason("explorer-b", DASH, obs)


def test_a_finished_investigation_gets_specific_feedback():
    c = Coverage()
    home = page("/", DASH, CAL)
    c.observe(home)
    follow(c, CAL, DASH, CAL)
    follow(c, DASH, DASH, CAL)
    assert "'Calendar' was already followed and reached: page Calendar" in c.repeat_reason("explorer-a", CAL, home)


def test_pending_records_on_a_familiar_page_are_not_a_discovery():
    c = Coverage()
    home = page("/", DASH, *rows())
    assert c.observe(home)
    assert not c.observe(home)  # still unvisited, yet nothing was learned


def test_return_navigation_to_an_unexplored_branch_is_allowed():
    c = Coverage()
    home = page("/", DASH, LIST)
    c.observe(home)
    follow(c, LIST, DASH, link("Edit", "/edit"))  # the list holds open work
    follow(c, DASH, DASH, LIST)
    assert c.repeat_reason("explorer-a", LIST, home) is None
    assert not c.nothing_left("explorer-a", home)


def test_matching_records_are_sampled_and_the_rest_stay_listed_unvisited():
    c = Coverage()
    r = rows()
    lst = page("/requests", DASH, *r)
    c.observe(lst)
    follow(c, r[0], DASH)
    follow(c, r[1], DASH)
    assert not c.is_open(control_key(r[2]))
    assert c.repeat_reason("explorer-a", r[2], lst)
    assert "2 sampled of 4 seen, enough sampled, others unvisited" in c.summary("explorer-a", lst)


def test_an_open_record_group_names_a_record_still_unvisited():
    c = Coverage()
    r = rows()
    lst = page("/requests", DASH, *r)
    c.observe(lst)
    follow(c, r[0], DASH)
    assert "Unexplored on this page: Dashboard, B (" in c.summary("explorer-a", lst)


def test_records_with_different_controls_keep_the_group_open():
    c = Coverage()
    r = rows()
    c.observe(page("/requests", DASH, *r))
    follow(c, r[0], DASH)
    follow(c, r[1], DASH, ObservedElement(id="x", tag="button", role="button", name="Cancel"))
    assert c.is_open(control_key(r[2]))  # the second sample looked different


def test_failed_navigation_is_not_coverage_and_is_bounded():
    c = Coverage()
    c.observe(page("/", CAL))
    c.failed(CAL)
    assert control_key(CAL) not in c.followed and c.is_open(control_key(CAL))
    c.failed(CAL)
    assert not c.is_open(control_key(CAL)) and control_key(CAL) not in c.followed


def test_a_failed_worker_leaves_work_open_and_a_stalled_claim_expires():
    now = [0.0]
    c = Coverage(clock=lambda: now[0])
    obs = page("/", CAL)
    c.observe(obs)
    c.assign("explorer-a", obs)
    assert c.nothing_left("explorer-b", obs)
    c.release("explorer-a")  # worker failed: its retry can claim the work
    assert c.assign("explorer-b", obs) == control_key(CAL)
    now[0] = 500  # explorer-b stalled and never released
    assert c.assign("explorer-a", obs) == control_key(CAL)


def test_different_labels_for_one_target_are_one_control():
    assert control_key(link("My requests", "/requests")) == control_key(link("Back to my requests", "/requests"))
    assert control_key(link("Approved", "/requests?status=Approved")) != control_key(LIST)


def test_form_controls_are_not_coverage_work():
    c = Coverage()
    obs = page("/", ObservedElement(id="b", tag="button", role="button", name="Save", form_index=0))
    c.observe(obs)
    assert c.nothing_left("explorer-a", obs)
