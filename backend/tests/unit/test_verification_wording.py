"""Reports claim browser verification only when saved records show an assertion was evaluated."""

from types import SimpleNamespace as NS

from flowlens.services.report import to_html, to_markdown, build_report  # noqa: F401
from test_persistence_and_report import _detail


def _rep(tmp_path, attempt_changes):
    d = _detail(tmp_path)
    f = d.findings[0]
    f.verification_status = type(f.verification_status)("inconclusive")
    f.requirement_ref = None
    f.kind = "review_observation"
    for v in d.verifications:
        for k, val in attempt_changes.items():
            setattr(v, k, val)
    return build_report(d, tmp_path, "http://h")


def test_no_requirement_says_replay_was_not_attempted(tmp_path):
    rep = _rep(tmp_path, {"result": None, "assertion": None, "setup_ok": False, "setup_strategy": None, "setup_error": None,
                          "failure_class": "expectation", "action_result_ids": []})
    md = to_markdown(rep)
    assert "Inconclusive: no supplied requirement defines the expected behaviour. Browser replay was not attempted." in md
    assert "Re-checked" not in md and "Verified by" not in md
    assert "**Tester-proposed expectation:**" in md
    assert "Reviewed by" in md and "not applicable: no browser replay ran" in md
    assert "Tester-proposed expectation" in to_html(rep, "/x.md")


def test_setup_failure_does_not_imply_verification(tmp_path):
    md = to_markdown(_rep(tmp_path, {"result": None, "assertion": None, "setup_ok": False, "setup_strategy": None,
                                     "setup_error": "could not reach the form", "failure_class": "setup"}))
    assert "browser replay was attempted but setup failed (could not reach the form)" in md
    assert "No assertion was evaluated." in md and "Re-checked" not in md


def test_evaluated_assertions_show_each_replay(tmp_path):
    d = _detail(tmp_path)
    d.verifications[0].result = NS(passed=False)
    md = to_markdown(build_report(d, tmp_path, "http://h"))
    assert "fresh browser replay(s) (replay 1: assertion failed, confirmed" in md
    assert "shares the tester's steps and the same model" in md
