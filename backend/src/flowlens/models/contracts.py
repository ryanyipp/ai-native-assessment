"""Shared validated contracts. Mirrored in frontend/src/lib/types.ts.

The lead session owns changes to this file (see AGENTS.md).
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, HttpUrl, model_validator


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def utcnow() -> datetime:
    return datetime.now(UTC)


# --- Provenance ------------------------------------------------------------


class Provenance(BaseModel):
    """Kept as separate flags because they can coexist (docs/plan.md, Run labels)."""

    live: bool = False  # a real browser and a real model call happened
    playback: bool = False  # replayed from saved evidence
    injected_failure: bool = False  # a deliberately injected fault
    synthetic_fixture: bool = True  # target is the controlled fixture app
    mocked_model: bool = False  # model replaced by a scripted stand-in (tests only)


# --- Run -------------------------------------------------------------------


class RunStatus(StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    partial = "partial"  # stopped on a budget limit: not a pass
    failed = "failed"
    interrupted = "interrupted"


class RunLimits(BaseModel):
    max_steps: int = Field(15, ge=1, le=60)
    max_model_calls: int = Field(40, ge=1, le=200)
    max_cost_usd: float = Field(0.50, gt=0, le=10)
    max_output_tokens: int = Field(800, ge=100, le=4000)
    max_duration_s: int = Field(600, ge=10, le=3600)
    max_states: int = Field(30, ge=1, le=200)


class RunCreate(BaseModel):
    target_url: HttpUrl
    goal: str = Field(min_length=5, max_length=2000)
    requirements: list[str] = Field(default_factory=list, max_length=20)
    limits: RunLimits | None = None


class Usage(BaseModel):
    model_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    reported_cost_usd: float = 0.0  # sum of provider-reported cost
    calls_without_cost: int = 0  # calls where the provider gave no cost figure


class Run(BaseModel):
    id: str = Field(default_factory=lambda: new_id("run"))
    target_url: str
    goal: str
    requirements: list[str] = Field(default_factory=list)
    model: str
    mode: Literal["single_explorer"] = "single_explorer"
    limits: RunLimits
    status: RunStatus = RunStatus.queued
    stop_reason: str | None = None
    provenance: Provenance = Field(default_factory=Provenance)
    usage: Usage = Field(default_factory=Usage)
    created_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None


# --- Task ------------------------------------------------------------------


class TaskStatus(StrEnum):
    ready = "ready"
    claimed = "claimed"
    done = "done"
    blocked = "blocked"
    failed = "failed"


class Task(BaseModel):
    id: str = Field(default_factory=lambda: new_id("task"))
    run_id: str
    type: Literal["explore", "input_test", "verify"] = "explore"
    key: str  # stable dedup key
    depends_on: list[str] = Field(default_factory=list)
    input_refs: list[str] = Field(default_factory=list)
    owner: str | None = None
    attempt_id: str | None = None
    lease_expires_at: datetime | None = None
    status: TaskStatus = TaskStatus.ready
    result_refs: list[str] = Field(default_factory=list)


# --- Browser commands and observations -------------------------------------


class ClickAction(BaseModel):
    type: Literal["click"] = "click"
    element_id: str = Field(pattern=r"^e\d{1,4}$")


class FillAction(BaseModel):
    type: Literal["fill"] = "fill"
    element_id: str = Field(pattern=r"^e\d{1,4}$")
    value: str = Field(max_length=2000)


class NavigateAction(BaseModel):
    type: Literal["navigate"] = "navigate"
    url: str = Field(max_length=2000)


class ReloadAction(BaseModel):
    type: Literal["reload"] = "reload"


class InspectAction(BaseModel):
    type: Literal["inspect"] = "inspect"


BrowserAction = Annotated[
    ClickAction | FillAction | NavigateAction | ReloadAction | InspectAction,
    Field(discriminator="type"),
]


class ObservedElement(BaseModel):
    id: str  # e1, e2 ... valid only for the observation that produced it
    tag: str
    role: str
    name: str  # accessible name (label / aria-label / text)
    input_type: str | None = None
    value: str | None = None
    href: str | None = None
    disabled: bool = False


class Observation(BaseModel):
    url: str
    title: str
    headings: list[str] = Field(default_factory=list)
    elements: list[ObservedElement] = Field(default_factory=list)
    text_excerpt: str = ""  # bounded visible text
    status_messages: list[str] = Field(default_factory=list)  # role=status/alert


class ActionResult(BaseModel):
    id: str = Field(default_factory=lambda: new_id("act"))
    run_id: str
    step: int
    action: dict[str, Any]
    target_description: str | None = None  # resolved element role/name
    ok: bool
    error: str | None = None
    url_before: str
    url_after: str
    started_at: datetime
    duration_ms: int
    screenshot_artifact_id: str | None = None
    observation_artifact_id: str | None = None


# --- Map records -----------------------------------------------------------


class ScreenState(BaseModel):
    id: str = Field(default_factory=lambda: new_id("state"))
    run_id: str
    signature: str
    signature_policy: str = "route+controls+headings+field-filled:v1"
    route: str  # normalised route pattern
    url: str  # first URL seen for this state
    title: str
    summary: str  # short human label
    screenshot_artifact_id: str | None = None
    first_seen_step: int
    # How another worker can reach this state: ordered actions from the start URL.
    setup_recipe: list[dict[str, Any]] = Field(default_factory=list)


class Transition(BaseModel):
    id: str = Field(default_factory=lambda: new_id("tr"))
    run_id: str
    step: int
    source_state_id: str
    target_state_id: str
    action: dict[str, Any]
    label: str
    action_result_id: str
    ok: bool
    duration_ms: int
    screenshot_artifact_id: str | None
    model_call_id: str | None = None


# --- Tests and findings ----------------------------------------------------


class AssertionType(StrEnum):
    element_visible = "element_visible"
    validation_message_present = "validation_message_present"
    navigation_reached = "navigation_reached"
    text_or_value_retained = "text_or_value_retained"
    state_condition = "state_condition"


class Assertion(BaseModel):
    type: AssertionType
    params: dict[str, Any] = Field(default_factory=dict)


class AssertionResult(BaseModel):
    assertion: Assertion
    passed: bool
    observed: dict[str, Any] = Field(default_factory=dict)
    evaluated_by: Literal["engine"] = "engine"


class TestCase(BaseModel):
    id: str = Field(default_factory=lambda: new_id("tc"))
    run_id: str
    setup: list[dict[str, Any]] = Field(default_factory=list)
    inputs: dict[str, Any] = Field(default_factory=dict)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    expectation_source: str
    assertion: Assertion


class VerificationStatus(StrEnum):
    unverified = "unverified"  # only the reporting agent has observed it
    confirmed = "confirmed"
    not_reproduced = "not_reproduced"
    inconclusive = "inconclusive"


class Finding(BaseModel):
    """A candidate observation. Checkpoint 1 never sets anything but `unverified`."""

    id: str = Field(default_factory=lambda: new_id("fnd"))
    run_id: str
    kind: Literal["persistence_check", "defect_candidate"]
    reported_by: str  # agent id
    description: str
    expected: str
    observed: str
    agent_claim: Literal["retained", "not_retained", "unknown"] | None = None
    # Engine check of the agent's own trace in the same browser context.
    # This is NOT independent verification.
    same_context_check: AssertionResult | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    verification_status: VerificationStatus = VerificationStatus.unverified
    replay_recipe: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def _no_self_confirmation(self) -> Finding:
        if self.verification_status != VerificationStatus.unverified and self.reported_by.startswith(
            "explorer"
        ):
            raise ValueError("an explorer cannot set a verification outcome on its own finding")
        return self


# --- Events and evidence ---------------------------------------------------


class Evidence(BaseModel):
    id: str = Field(default_factory=lambda: new_id("art"))
    run_id: str
    kind: Literal["screenshot", "observation", "model_call", "action_log"]
    path: str  # relative to the artifacts dir
    sha256: str
    media_type: str
    created_at: datetime = Field(default_factory=utcnow)


class Event(BaseModel):
    seq: int | None = None  # ordered ID assigned by storage
    run_id: str
    task_id: str | None = None
    attempt_id: str | None = None
    agent_id: str | None = None
    type: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    provenance: Provenance = Field(default_factory=Provenance)
    created_at: datetime = Field(default_factory=utcnow)


class ModelCall(BaseModel):
    id: str = Field(default_factory=lambda: new_id("mc"))
    run_id: str
    step: int
    model: str
    provider: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    reported_cost_usd: float | None = None
    latency_ms: int
    ok: bool
    error: str | None = None
    artifact_id: str | None = None


class RunDetail(BaseModel):
    run: Run
    states: list[ScreenState]
    transitions: list[Transition]
    actions: list[ActionResult]
    findings: list[Finding]
    events: list[Event]
    evidence: list[Evidence]
    model_calls: list[ModelCall]
