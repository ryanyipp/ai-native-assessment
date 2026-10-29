from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from flowlens.browser.engine import origin_of
from flowlens.models.contracts import Evidence, Provenance, Run, RunCreate, RunDetail, RunLimits
from flowlens.orchestration.launch import LOADED_FINGERPRINT, StaleCodeError, check_code_current, start_run_thread
from flowlens.services.llm import OpenRouterClient

router = APIRouter(prefix="/api")


@router.get("/health")
def health(request: Request):
    s = request.app.state.settings
    store = request.app.state.store
    return {
        "ok": True,
        "model": s.openrouter_model,
        "api_key_configured": s.has_api_key,
        "allowed_origins": s.allowed_origins,
        "budget_usd": s.flowlens_budget_usd,
        "spent_reported_usd": round(store.total_reported_cost(), 6),
        "default_run_budget_usd": s.flowlens_run_budget_usd,
        "code_version": LOADED_FINGERPRINT,
    }


@router.post("/runs", response_model=Run, status_code=201)
def create_run(body: RunCreate, request: Request):
    s = request.app.state.settings
    store = request.app.state.store
    target = str(body.target_url)
    if origin_of(target) not in {o.lower() for o in s.allowed_origins}:
        raise HTTPException(400, f"target origin {origin_of(target)} is not in FLOWLENS_ALLOWED_ORIGINS")
    try:
        check_code_current()
    except StaleCodeError as e:
        raise HTTPException(503, str(e)) from e
    if not s.has_api_key:
        raise HTTPException(400, "OPENROUTER_API_KEY is not configured; live runs are unavailable")
    limits = body.limits or RunLimits(
        max_steps=s.flowlens_max_steps,
        max_model_calls=s.flowlens_max_model_calls_per_run,
        max_cost_usd=s.flowlens_run_budget_usd,
        max_output_tokens=s.flowlens_max_output_tokens,
    )
    llm = OpenRouterClient(s)
    run = Run(
        target_url=target, goal=body.goal, requirements=body.requirements, model=llm.model,
        limits=limits, mode=body.mode,
        provenance=Provenance(live=not llm.is_mock, mocked_model=llm.is_mock, synthetic_fixture=True),
    )
    store.put(run)
    start_run_thread(run, store, s, llm)
    return run


@router.get("/runs", response_model=list[Run])
def list_runs(request: Request):
    return request.app.state.store.list_runs()


@router.get("/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: str, request: Request):
    d = request.app.state.store.detail(run_id)
    if d is None:
        raise HTTPException(404, "run not found")
    return d


@router.get("/artifacts/{artifact_id}")
def get_artifact(artifact_id: str, request: Request):
    store = request.app.state.store
    root = request.app.state.settings.artifacts_path.resolve()
    ev = store.get(Evidence, artifact_id)
    if ev is None:
        raise HTTPException(404, "artifact not found")
    path = (root / ev.path).resolve()
    if root not in path.parents or not path.is_file():
        raise HTTPException(404, "artifact file missing")
    return FileResponse(path, media_type=ev.media_type)
