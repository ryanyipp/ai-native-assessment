from __future__ import annotations

import asyncio
import base64
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse, HTMLResponse, Response

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


def normalise_origin(url: str) -> str:
    """scheme://host[:port] for an http(s) URL; raises ValueError for anything else."""
    try:
        u = urlsplit(url.strip())
        port = u.port
    except ValueError as e:
        raise ValueError(f"not a valid URL: {e}") from e
    if u.scheme not in ("http", "https") or not u.hostname:
        raise ValueError("only http and https URLs with a host can be approved")
    if u.username or u.password:
        raise ValueError("URLs with embedded credentials cannot be approved")
    host = u.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    default = {"http": 80, "https": 443}[u.scheme]
    return f"{u.scheme}://{host}" + (f":{port}" if port and port != default else "")


def fixture_origins(s) -> set[str]:
    return {o.lower() for o in s.allowed_origins}


def scope_for(origin: str, s, store) -> tuple[str, list[str]] | None:
    """(profile, origins the engine may load) for a target origin, or None if it is not approved.

    Configured fixture origins keep their workspace setup and shared scope. A launcher-approved
    website may load only its own origin; other origins, including redirect targets, are refused.
    """
    if origin in fixture_origins(s):
        return "fixture", s.allowed_origins
    if origin in {a["origin"] for a in store.approved_origins()}:
        return "website", [origin]
    return None


class OriginApproval(BaseModel):
    url: str = Field(max_length=2000)


@router.get("/origins")
def list_origins(request: Request):
    s, store = request.app.state.settings, request.app.state.store
    return {"configured": s.allowed_origins, "approved": store.approved_origins()}


@router.post("/origins", status_code=201)
def approve_origin(body: OriginApproval, request: Request):
    """Approve one origin for preview and runs. Stored in the database; .env is not changed."""
    s, store = request.app.state.settings, request.app.state.store
    try:
        origin = normalise_origin(body.url)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if origin in fixture_origins(s):
        return {"origin": origin, "profile": "fixture", "already_configured": True}
    store.approve_origin(origin, utcnow().isoformat())
    return {"origin": origin, "profile": "website", "already_configured": False}


@router.delete("/origins")
def revoke_origin(origin: str, request: Request):
    """Revoke a launcher approval. Runs already started keep the scope recorded at creation."""
    s, store = request.app.state.settings, request.app.state.store
    try:
        o = normalise_origin(origin)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if o in fixture_origins(s):
        raise HTTPException(400, "configured fixture origins are set in FLOWLENS_ALLOWED_ORIGINS")
    return {"origin": o, "revoked": store.revoke_origin(o)}


@router.get("/health")
def health(request: Request):
    s = request.app.state.settings
    store = request.app.state.store
    return {
        "ok": True,
        "model": s.openrouter_model,
        "api_key_configured": s.has_api_key,
        "allowed_origins": s.allowed_origins,
        "approved_origins": [a["origin"] for a in store.approved_origins()],
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
    try:
        scope = scope_for(normalise_origin(target), s, store)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if scope is None:
        raise HTTPException(400, f"target origin {origin_of(target)} is not approved; approve it in the launcher first")
    profile, scope_origins = scope
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
        target_profile=profile, scope_origins=scope_origins,
        provenance=Provenance(live=not llm.is_mock, mocked_model=llm.is_mock, synthetic_fixture=profile == "fixture",
                              injected_failure=body.fault_injection is not None),
    )
    store.put(run)
    start_run_thread(run, store, s, llm)
    return run


class PreviewRequest(BaseModel):
    url: str = Field(max_length=2000)


def _capture(url: str, settings, scope: list[str], profile: str) -> dict:
    """One static screenshot in a throwaway browser context (own thread and loop; Playwright on Windows)."""

    async def go():
        async with BrowserEngine(scope, settings.flowlens_headless) as eng:
            ex = await eng.execute(NavigateAction(url=url))
            return ex

    ex = asyncio.run(go())
    left_scope = bool(ex.error and "approved scope" in ex.error)
    return {"ok": ex.ok, "error": ex.error, "requested_url": url,
            "final_url": None if left_scope else ex.url_after,
            "title": None if left_scope else ex.observation.title,
            "headings": [] if left_scope else ex.observation.headings,
            "captured_at": utcnow().isoformat(), "viewport": {"width": 1280, "height": 800},
            "profile": profile,
            # Nothing from outside the approved scope is captured or returned.
            "image_png_base64": None if left_scope else base64.b64encode(ex.screenshot_png).decode()}


@router.post("/preview")
async def preview(body: PreviewRequest, request: Request):
    """A real, non-interactive screenshot of an allowed URL, before any run starts.

    Uses a fresh browser context with no test session and no workspace; nothing is stored.
    """
    s = request.app.state.settings
    try:
        scope = scope_for(normalise_origin(body.url), s, request.app.state.store)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if scope is None:
        raise HTTPException(400, f"origin {origin_of(body.url)} is not approved; approve it in the launcher first")
    profile, origins = scope
    try:
        return await asyncio.wait_for(asyncio.to_thread(_capture, body.url, s, origins, profile), timeout=40)
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


def _report(run_id: str, request: Request) -> dict:
    from flowlens.services.report import build_report

    d = request.app.state.store.detail(run_id)
    if d is None:
        raise HTTPException(404, "run not found")
    return build_report(d, request.app.state.settings.artifacts_path.resolve(), str(request.base_url))


@router.get("/runs/{run_id}/report.md")
def report_markdown(run_id: str, request: Request):
    """Markdown review report from the saved records only (no model call, no browser)."""
    from flowlens.services.report import to_markdown

    return Response(to_markdown(_report(run_id, request)), media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="flowlens-report-{run_id}.md"'})


@router.get("/runs/{run_id}/report", response_class=HTMLResponse)
def report_html(run_id: str, request: Request):
    """Printable HTML view of the same report."""
    from flowlens.services.report import to_html

    return HTMLResponse(to_html(_report(run_id, request), f"/api/runs/{run_id}/report.md"))
