"""Regression from run_8d31c2abbacf: a date-like caption was confirmed against a past-date requirement.

Scripted model, real Chromium and Creator Studio. The script stands in for the verifier's judgement, so these
tests cover the context it receives and how code handles its reply. They cannot show that a real model judges
applicability correctly.
"""

import json

from flowlens.config import Settings
from flowlens.models.contracts import Provenance, Run, RunLimits
from flowlens.orchestration.review import ReviewRun
from flowlens.services.llm import ScriptedClient
from flowlens.services.report import build_report, to_markdown
from flowlens.storage.db import Store
from test_review import _id

REQ = "Past dates must be rejected."
ASSERTION = {"type": "validation_message_present", "params": {}}


def decision(**kw):
    return json.dumps({"reasoning": "scripted", "requirement_ref": "REQ-1", "explicit": True, "requirement_quote": "Past dates",
                       "assertion": ASSERTION, "expected": "a validation message", **kw})


def script(link, inputs, submit, verifier_reply, seen):
    def reply(messages):
        system, user = messages[0]["content"], messages[-1]["content"]
        if "You operate a real browser" in system:
            page = user.split("Current page:")[1].split("\n\nNote:")[0]
            if f'"{link}"' in page and link not in user.split("Your previous actions:")[1].split("Current page:")[0]:
                return json.dumps({"reasoning": "open", "action": {"type": "click", "element_id": _id(page, "link", link)}})
            return json.dumps({"reasoning": "done", "action": {"type": "finish", "summary": "done"}})
        if "designed input cases" in system:
            return json.dumps({"reasoning": "s", "assessments": [
                {"case": 1, "verdict": "unexpected", "observed_summary": "accepted", "requirement_ref": "REQ-1"}]})
        if "You are the Verifier" in system:
            seen.append(user)
            return verifier_reply
        return json.dumps({"reasoning": "s", "cases": [{"label": "Past", "inputs": inputs, "submit": submit,
                                                        "requirement_ref": "REQ-1", "expected": "rejected"}]})
    return reply


async def review(server, tmp_path, *args):
    seen = []
    settings = Settings(_env_file=None, artifacts_dir=tmp_path / "a", flowlens_allowed_origins=server.url, openrouter_api_key=None)
    store = Store(tmp_path / "r.db")
    run = Run(target_url=server.url + "/", goal="Open the form", requirements=[REQ], model="scripted-test-model",
              mode="explore_test_verify", limits=RunLimits(max_forms_tested=1), provenance=Provenance(live=False, mocked_model=True))
    store.put(run)
    await ReviewRun(run, store, settings, ScriptedClient(script(*args, seen))).execute()
    return store.detail(run.id), seen


CAPTION = ("New draft", {"Title": "Old Draft", "Caption": "2020-01-01"}, "Save draft")
SCHEDULE = ("Schedule a post", {"Post title": "Old", "Publish date": "2026-06-14"}, "Schedule post")


async def test_a_date_like_caption_stays_inconclusive_when_the_verifier_says_it_does_not_apply(fixture_server, tmp_path):
    reply = decision(applicability="not_applicable", applicability_target="Caption",
                     applicability_reason="Caption is free text, not a date field.")
    d, seen = await review(fixture_server, tmp_path, *CAPTION, reply)
    (f,) = d.findings
    assert f.verification_status == "inconclusive"
    (v,) = d.verifications  # one attempt: repeating the behaviour cannot settle whether the requirement applies
    assert v.failure_class == "applicability" and v.result is None
    assert "Caption is free text" in v.reason
    md = to_markdown(build_report(d, tmp_path / "a", "http://h"))
    assert "does not apply" in md and "**Status: Confirmed" not in md
    assert '"Caption" (textbox) = "2020-01-01"' in seen[0]  # metadata and page context reach the verifier
    assert "Form under test: /drafts/new" in seen[0]


async def test_ambiguous_applicability_is_not_settled_by_replaying(fixture_server, tmp_path):
    reply = decision(applicability="ambiguous", applicability_reason="The requirement names no field.")
    d, _ = await review(fixture_server, tmp_path, *CAPTION, reply)
    assert d.findings[0].verification_status == "inconclusive"
    assert [v.failure_class for v in d.verifications] == ["applicability"]


async def test_a_verifier_that_skips_the_assessment_cannot_confirm(fixture_server, tmp_path):
    d, _ = await review(fixture_server, tmp_path, *CAPTION, decision())
    assert d.findings[0].verification_status == "inconclusive"
    assert "did not assess" in d.verifications[0].reason


async def test_applicability_must_name_a_control_the_test_used(fixture_server, tmp_path):
    reply = decision(applicability="applies", applicability_target="Publish date", applicability_reason="A date field.")
    d, _ = await review(fixture_server, tmp_path, *CAPTION, reply)
    assert d.findings[0].verification_status == "inconclusive"
    assert "Publish date" in d.verifications[0].reason


async def test_a_past_date_in_a_scheduling_date_field_remains_verifiable(fixture_server, tmp_path):
    reply = decision(applicability="applies", applicability_target="Publish date",
                     applicability_reason="Publish date is a date field for scheduling.")
    d, seen = await review(fixture_server, tmp_path, *SCHEDULE, reply)
    assert d.findings[0].verification_status == "confirmed"  # the broken fixture accepts the past date
    assert len(d.verifications) == 2 and d.verifications[0].applicability == "applies"
    assert '"Publish date" (textbox, type=date) = "2026-06-14"' in seen[0]
    md = to_markdown(build_report(d, tmp_path / "a", "http://h"))
    assert "Publish date is a date field for scheduling." in md
