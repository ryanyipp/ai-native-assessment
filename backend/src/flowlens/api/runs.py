from __future__ import annotations

import asyncio
import base64

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse

from flowlens.browser.engine import BrowserEngine, origin_of
from flowlens.models.contracts import (
    Evidence,
    NavigateAction,
    Provenance,
    Run,
    RunCreate,
    RunDetail,
    RunLimits,
    utcnow,
)
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
    if body.fault_injection and body.mode != "queue_review":
        raise HTTPException(400, "fault_injection is only supported in queue_review mode")
    llm = OpenRouterClient(s)
    run = Run(
        target_url=target, goal=body.goal, requirements=body.requirements, model=llm.model,
        limits=limits, mode=body.mode,
        fault_injection=body.fault_injection,
        provenance=Provenance(live=not llm.is_mock, mocked_model=llm.is_mock, synthetic_fixture=True,
                              injected_failure=body.fault_injection is not None),
    )
    store.put(run)
    start_run_thread(run, store, s, llm)
    return run


class PreviewRequest(BaseModel):
    url: str = Field(max_length=2000)


def _capture(url: str, settings) -> dict:
    """One static screenshot in a throwaway browser context (own thread and loop; Playwright on Windows)."""

    async def go():
        async with BrowserEngine(settings.allowed_origins, settings.flowlens_headless) as eng:
            ex = await eng.execute(NavigateAction(url=url))
            return ex

    ex = asyncio.run(go())
    return {"ok": ex.ok, "error": ex.error, "requested_url": url, "final_url": ex.url_after,
            "title": ex.observation.title, "headings": ex.observation.headings,
            "captured_at": utcnow().isoformat(), "viewport": {"width": 1280, "height": 800},
            "image_png_base64": base64.b64encode(ex.screenshot_png).decode()}


@router.post("/preview")
async def preview(body: PreviewRequest, request: Request):
    """A real, non-interactive screenshot of an allowed URL, before any run starts.

    Uses a fresh browser context with no test session and no workspace; nothing is stored.
    """
    s = request.app.state.settings
    if origin_of(body.url) not in {o.lower() for o in s.allowed_origins}:
        raise HTTPException(400, f"origin {origin_of(body.url)} is not in FLOWLENS_ALLOWED_ORIGINS")
    try:
        return await asyncio.wait_for(asyncio.to_thread(_capture, body.url, s), timeout=40)
    except TimeoutError as e:
        raise HTTPException(504, "the page did not load within 40 s") from e


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
