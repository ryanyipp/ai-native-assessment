"""Regression for run_53d7009ff711: the API review path with default settings.

That run crashed with AttributeError('RunLimits' has no 'max_output_tokens_planning')
because a backend started before a contract change lazily imported newer review
code. The model here is a scripted stand-in: runs are labelled mocked_model.
"""

import time

import pytest
from fastapi.testclient import TestClient

from flowlens.models.contracts import RunLimits, RunStatus
from flowlens.services.llm import ScriptedClient
from test_review import REQS, make_review, make_script


@pytest.fixture
def api(tmp_path, monkeypatch, fixture_server):
    monkeypatch.setenv("ARTIFACTS_DIR", str(tmp_path / "a"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'api.db').as_posix()}")
    monkeypatch.setenv("FLOWLENS_ALLOWED_ORIGINS", fixture_server.url)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-placeholder-not-a-key")
    from flowlens.config import get_settings
    get_settings.cache_clear()
    script, calls = make_script()
    monkeypatch.setattr("flowlens.api.runs.OpenRouterClient", lambda s: ScriptedClient(script))
    from flowlens.main import app
    with TestClient(app) as c:
        yield c, fixture_server, calls
    get_settings.cache_clear()


def _wait(c, run_id, timeout=180):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        d = c.get(f"/api/runs/{run_id}").json()
        if d["run"]["status"] not in ("queued", "running"):
            return d
        time.sleep(0.5)
    raise AssertionError("run did not finish")


def test_api_review_run_with_default_settings_reaches_tester_and_verifier(api):
    c, srv, calls = api
    r = c.post("/api/runs", json={"target_url": srv.url + "/", "goal": "Find the scheduling form",
                                  "requirements": REQS, "mode": "explore_test_verify"})  # no limits: defaults
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["limits"]["max_output_tokens_planning"] == RunLimits().max_output_tokens_planning
    assert run["provenance"]["mocked_model"] and not run["provenance"]["live"]
    d = _wait(c, run["id"])
    assert d["run"]["status"] == "completed", d["run"]["stop_reason"]
    kinds = {h["kind"] for h in d["handoffs"]}
    assert kinds == {"form_to_tester", "candidate_to_verifier"}
    assert d["test_cases"] and all(t["status"] == "executed" for t in d["test_cases"])
    assert d["verifications"] and {m["agent_id"] for m in d["model_calls"]} == {"explorer-a", "input-tester", "verifier"}
    assert "run_error" not in [e["type"] for e in d["events"]]


def test_api_refuses_to_start_from_stale_code(api, monkeypatch):
    c, srv, _ = api
    monkeypatch.setattr("flowlens.orchestration.launch.LOADED_FINGERPRINT", "0000000000000000")
    r = c.post("/api/runs", json={"target_url": srv.url + "/", "goal": "Find the scheduling form",
                                  "mode": "explore_test_verify"})
    assert r.status_code == 503 and "Restart the backend" in r.json()["detail"]
    assert "code_version" in c.get("/api/health").json()


async def test_crash_mid_review_states_where_it_stopped(fixture_server, tmp_path):
    script, _ = make_script()
    rr, store, _ = make_review(fixture_server, tmp_path, script)

    async def boom(form):
        raise AttributeError("simulated crash in the tester stage")

    rr.test_form = boom
    await rr.execute()
    d = store.detail(rr.run.id)
    assert d.run.status == RunStatus.failed
    reason = d.run.stop_reason
    assert "failed while testing form" in reason and "does not mean the website passed" in reason
    assert not d.findings
    err = next(e for e in d.events if e.type == "run_error")
    assert err.data["stage"].startswith("testing form") and err.agent_id == "coordinator"
