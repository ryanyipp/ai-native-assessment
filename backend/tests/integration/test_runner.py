"""Run loop with a scripted model stand-in against the real fixture and real Chromium.

The model is mocked here, and these runs are labelled mocked_model and not live.
They test recording, linking and limits, not model quality.
"""

import json
import re

from fastapi.testclient import TestClient

from flowlens.config import Settings
from flowlens.models.contracts import Provenance, Run, RunLimits, RunStatus
from flowlens.orchestration.runner import ExplorerRun
from flowlens.services.llm import ScriptedClient
from flowlens.storage.db import Store


def _id(msg: str, role: str, name: str) -> str:
    m = re.search(rf"(e\d+) {role} \"{re.escape(name)}\"", msg)
    return m.group(1) if m else ""


def scripted_explorer(messages):
    """A deterministic script (test-only) that knows the fixture's labels."""
    msg = messages[-1]["content"]
    history = msg.split("Your previous actions:")[1].split("Current page:")[0]
    page = msg.split("Current page:")[1]
    if "reload -> ok" in history:
        act = {"type": "finish", "persistence": "retained", "summary": "values shown after reload",
               "checked_values": [{"field": "Title", "expected": "T-42"}, {"field": "Caption", "expected": "C-42"}]}
    elif "Draft saved." in page:
        act = {"type": "reload"}
    elif "Headings: New draft" in page:
        if 'Title" value=""' in page:
            act = {"type": "fill", "element_id": _id(page, "textbox", "Title"), "value": "T-42"}
        elif 'Caption" value=""' in page:
            act = {"type": "fill", "element_id": _id(page, "textbox", "Caption"), "value": "C-42"}
        else:
            act = {"type": "click", "element_id": _id(page, "button", "Save draft")}
    else:
        act = {"type": "click", "element_id": _id(page, "link", "New draft")}
    return json.dumps({"reasoning": "scripted", "action": act})


def make_run(fixture_server, tmp_path, **limits):
    settings = Settings(_env_file=None, artifacts_dir=tmp_path / "artifacts",
                        flowlens_allowed_origins=fixture_server.url, openrouter_api_key=None)
    store = Store(tmp_path / "t.db")
    run = Run(target_url=fixture_server.url + "/", goal="Create, save, reload, check persistence",
              model="scripted-test-model", limits=RunLimits(**limits),
              provenance=Provenance(live=False, mocked_model=True))
    store.put(run)
    return ExplorerRun(run, store, settings, ScriptedClient(scripted_explorer)), store, settings


async def test_scripted_run_records_linked_states_and_transitions(fixture_server, tmp_path):
    er, store, settings = make_run(fixture_server, tmp_path)
    await er.execute()
    d = store.detail(er.run.id)
    assert d.run.status == RunStatus.completed, d.run.stop_reason
    assert d.run.provenance.mocked_model and not d.run.provenance.live

    actions = {a.id: a for a in d.actions}
    evidence = {e.id: e for e in d.evidence}
    states = {s.id for s in d.states}
    assert [t.action["type"] for t in d.transitions] == ["click", "fill", "fill", "click", "reload"]
    for t in d.transitions:
        assert t.action_result_id in actions
        assert actions[t.action_result_id].action == t.action
        assert t.source_state_id in states and t.target_state_id in states
        shot = evidence[t.screenshot_artifact_id]
        assert (settings.artifacts_path / shot.path).read_bytes()[:4] == b"\x89PNG"
        assert t.model_call_id
    # Reload of a retained draft maps back to the same state.
    reload_tr = d.transitions[-1]
    assert reload_tr.source_state_id == reload_tr.target_state_id

    (f,) = d.findings
    assert f.verification_status == "unverified" and f.agent_claim == "retained"
    assert f.same_context_check.passed
    assert [e.seq for e in d.events] == sorted(e.seq for e in d.events)


async def test_call_limit_stops_run_as_partial(fixture_server, tmp_path):
    er, store, _ = make_run(fixture_server, tmp_path, max_model_calls=2)
    await er.execute()
    run = store.get(Run, er.run.id)
    assert run.status == RunStatus.partial and "model-call limit" in run.stop_reason
    assert run.usage.model_calls == 2


async def test_wrong_claim_fails_same_context_check(fixture_server, tmp_path):
    def liar(messages):
        out = json.loads(scripted_explorer(messages))
        if out["action"]["type"] == "finish":
            out["action"]["checked_values"] = [{"field": "Title", "expected": "never-entered"}]
        return json.dumps(out)

    er, store, _ = make_run(fixture_server, tmp_path)
    er.llm = ScriptedClient(liar)
    await er.execute()
    (f,) = store.detail(er.run.id).findings
    assert f.agent_claim == "retained" and not f.same_context_check.passed


def test_api_rejects_disallowed_origin_and_serves_artifacts(tmp_path, monkeypatch):
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path / "a"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'api.db').as_posix()}")
    from flowlens.config import get_settings
    get_settings.cache_clear()
    from flowlens.main import app
    with TestClient(app) as c:
        r = c.post("/api/runs", json={"target_url": "https://example.com/", "goal": "do something"})
        assert r.status_code == 400
        assert c.get("/api/artifacts/art_missing").status_code == 404
        assert "api_key_configured" in c.get("/api/health").json()
        assert "sk-or" not in c.get("/api/health").text
    get_settings.cache_clear()
