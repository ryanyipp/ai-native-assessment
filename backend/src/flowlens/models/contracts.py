"""Shared validated contracts. Mirrored in frontend/src/lib/types.ts.

The lead session owns changes to this file (see AGENTS.md).
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


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


Phase = Literal["explore", "input_test", "verify"]


# --- Run -------------------------------------------------------------------


class RunStatus(StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    partial = "partial"  # stopped on a budget limit: not a pass
    failed = "failed"
    interrupted = "interrupted"


RunMode = Literal["single_explorer", "explore_test_verify", "queue_review", "single_agent", "reverify"]


class RunLimits(BaseModel):
    max_steps: int = Field(15, ge=1, le=60)
    max_model_calls: int = Field(40, ge=1, le=200)
    max_cost_usd: float = Field(0.50, gt=0, le=10)
    max_output_tokens: int = Field(800, ge=100, le=4000)
    # Tester plans/assessments and verifier choices: hidden reasoning shares this cap.
    max_output_tokens_planning: int = Field(1400, ge=100, le=4000)
    max_duration_s: int = Field(600, ge=10, le=3600)
    max_states: int = Field(30, ge=1, le=200)
    # Calls held back from explorer and tester so verification can still run.
    reserved_verification_calls: int = Field(4, ge=0, le=50)
    max_forms_tested: int = Field(3, ge=0, le=10)
    max_cases_per_form: int = Field(3, ge=1, le=8)
    verification_replays: int = Field(2, ge=1, le=5)
    # Shared queue (queue_review): explorers leave these calls for tester and verifier.
    reserved_testing_calls: int = Field(8, ge=0, le=50)
    explore_steps_per_task: int = Field(4, ge=1, le=15)
    max_depth: int = Field(2, ge=0, le=6)  # frontier depth from the start state
    max_tasks: int = Field(40, ge=1, le=300)
    task_max_attempts: int = Field(2, ge=1, le=5)
    task_lease_s: int = Field(300, ge=2, le=3600)  # renewed on every action; expired claims are revoked
    planning_reasoning_tokens: int = Field(384, ge=0, le=4000)  # hidden-reasoning budget for tester/verifier


class FaultInjection(BaseModel):
    """Evaluation-only fault. Runs that use it are labelled provenance.injected_failure."""

    kind: Literal["stall_after_claim"] = "stall_after_claim"
    worker: Literal["explorer-a", "explorer-b", "input-tester", "verifier"] = "explorer-a"
    task_type: Literal["explore", "input_test", "verify"] = "explore"
    stall_s: int = Field(30, ge=1, le=600)  # should exceed the run's task_lease_s
    times: int = Field(1, ge=1, le=3)


class RunCreate(BaseModel):
    target_url: HttpUrl
    goal: str = Field(min_length=5, max_length=2000)
    requirements: list[str] = Field(default_factory=list, max_length=20)
    limits: RunLimits | None = None
    mode: Literal["single_explorer", "explore_test_verify", "queue_review", "single_agent"] = "single_explorer"
    fault_injection: FaultInjection | None = None  # queue_review only


class Usage(BaseModel):
    model_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    reported_cost_usd: float = 0.0  # sum of provider-reported cost
    calls_without_cost: int = 0  # calls where the provider gave no cost figure
    # Per-phase call counts (queue mode reserves capacity per phase).
    exploration_calls: int = 0
    testing_calls: int = 0
    verification_calls: int = 0
    truncated_calls: int = 0  # replies cut off at the output limit


class Run(BaseModel):
    id: str = Field(default_factory=lambda: new_id("run"))
    target_url: str
    goal: str
    requirements: list[str] = Field(default_factory=list)
    model: str
    mode: RunMode = "single_explorer"
    limits: RunLimits
    # Evaluation-only label of the target build (e.g. fixture mode). Recorded so
    # runs against different builds are never confused; never sent to agents.
    target_build: str | None = None
    fault_injection: FaultInjection | None = None
    status: RunStatus = RunStatus.queued
    stop_reason: str | None = None
    provenance: Provenance = Field(default_factory=Provenance)
    usage: Usage = Field(default_factory=Usage)
    created_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None


# --- Task ------------------------------------------------------------------


class TaskStatus(StrEnum):
    ready = "ready"
    deferred = "deferred"  # sequential mode: recorded for the queue, not executed
    unfinished = "unfinished"  # queue mode: never run because a limit or the run end was reached
    skipped = "skipped"  # queue mode: recorded but not explored (a variation or an already-tested outcome)
    claimed = "claimed"
    done = "done"
    blocked = "blocked"
    failed = "failed"


class Task(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    id: str = Field(default_factory=lambda: new_id("task"))
    run_id: str
    type: Literal["explore", "input_test", "verify"] = "explore"
    # Later checkpoints add leases and concurrent claims; these fields already exist.
    key: str  # stable dedup key
    depends_on: list[str] = Field(default_factory=list)
    input_refs: list[str] = Field(default_factory=list)
    owner: str | None = None  # worker id, e.g. explorer-a, input-tester, verifier
    attempt_id: str | None = None
    lease_expires_at: datetime | None = None
    status: TaskStatus = TaskStatus.ready
    result_refs: list[str] = Field(default_factory=list)
    note: str | None = None
    priority: int = 0  # higher is claimed first within a task type
    depth: int = 0
    attempts: int = 0  # claims so far
    max_attempts: int = 2
    payload: dict[str, Any] = Field(default_factory=dict)  # ids of the records this task works on
    queued_by: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    claimed_at: datetime | None = None
    finished_at: datetime | None = None
    excluded_workers: list[str] = Field(default_factory=list)  # owners whose lease expired on this task
    expired_attempts: list[str] = Field(default_factory=list)
    fencing: bool = False  # expired attempt not yet fenced: not claimable until released


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
    required: bool = False
    form_index: int | None = None  # index of the enclosing <form> in this observation
    # Browser constraint-validation message shown after user interaction, if any.
    validation_message: str | None = None


class Observation(BaseModel):
    url: str
    title: str
    headings: list[str] = Field(default_factory=list)
    elements: list[ObservedElement] = Field(default_factory=list)
    text_excerpt: str = ""  # bounded visible text
    status_messages: list[str] = Field(default_factory=list)  # role=status/alert
    alert_messages: list[str] = Field(default_factory=list)  # role=alert only
    invalid_fields: list[str] = Field(default_factory=list)  # names with aria-invalid/user-invalid


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
    # Worker provenance. Old single-explorer records default to explorer-a.
    agent_id: str = "explorer-a"
    phase: Phase = "explore"
    context_id: str | None = None  # browser context + test-data workspace label
    task_id: str | None = None


# --- Semantic controls and recipes -------------------------------------------


class ControlRef(BaseModel):
    """A control described by meaning, not by a per-observation element id.

    Resolved against a fresh observation each time. Zero or several matches is an
    explicit resolution error, never a guess.
    """

    role: str = Field(max_length=40)
    name: str = Field(max_length=160)
    input_type: str | None = Field(None, max_length=30)

    def describe(self) -> str:
        return f"{self.role} '{self.name}'"


class SemanticStep(BaseModel):
    type: Literal["navigate", "reload", "click", "fill"]
    path: str | None = None  # navigate: path + query relative to the target origin
    control: ControlRef | None = None
    value: str | None = None  # fill value (synthetic test data only, never secrets)

    def describe(self) -> str:
        if self.type == "navigate":
            return f"open {self.path}"
        if self.type == "reload":
            return "reload"
        if self.type == "fill":
            return f"fill {self.control.describe() if self.control else '?'} = {self.value!r}"
        return f"click {self.control.describe() if self.control else '?'}"


class SetupRecipe(BaseModel):
    """How a fresh worker reaches a recorded state."""

    target_state_id: str
    expected_signature: str
    direct_path: str | None = None  # tried first: open this path in the fresh context
    steps: list[SemanticStep] = Field(default_factory=list)  # fallback: replay from the start
    data_isolation: str = "fresh browser context and a newly provisioned fixture workspace per execution"


# --- Map records -----------------------------------------------------------


class StateSighting(BaseModel):
    agent_id: str
    phase: Phase
    context_id: str | None = None
    action_result_id: str | None = None


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
    # Raw actions keep their element ids, which are only valid in their own observation.
    setup_recipe: list[dict[str, Any]] = Field(default_factory=list)
    semantic_recipe: list[SemanticStep] = Field(default_factory=list)
    discovered_by: str = "explorer-a"
    phase: Phase = "explore"
    context_id: str | None = None
    # Every worker/context that observed this signature. States from different
    # test-data contexts share a node only with their sightings preserved.
    sightings: list[StateSighting] = Field(default_factory=list)
    structure: str | None = None  # page structure without field fill flags (see engine.page_structure)
    layout: str | None = None  # structure without status/alert messages


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
    agent_id: str = "explorer-a"
    phase: Phase = "explore"
    context_id: str | None = None
    test_case_id: str | None = None
    verification_id: str | None = None


# --- Requirements, forms and handoffs ---------------------------------------


class RequirementRef(BaseModel):
    id: str  # "R5" if the supplied text starts with an id, otherwise "REQ-n"
    text: str


class Expectation(BaseModel):
    text: str
    source: str  # requirement id, or "none supplied"


class FormField(BaseModel):
    control: ControlRef
    required: bool = False
    observed_value: str | None = None


class DiscoveredForm(BaseModel):
    """A form as observed by a worker. Extracted by code from a real observation."""

    id: str = Field(default_factory=lambda: new_id("form"))
    run_id: str
    key: str  # stable dedup key: route + field roles/names/types
    state_id: str
    url: str
    route: str
    headings: list[str] = Field(default_factory=list)
    fields: list[FormField]
    submit_controls: list[ControlRef] = Field(default_factory=list)
    page_text: str = ""  # bounded visible text of the page when discovered
    discovered_by: str
    action_result_id: str
    evidence_refs: list[str] = Field(default_factory=list)  # screenshot + observation artifacts


class Handoff(BaseModel):
    """A concrete artifact passed from one worker to another."""

    id: str = Field(default_factory=lambda: new_id("ho"))
    run_id: str
    kind: Literal["form_to_tester", "candidate_to_verifier"]
    from_agent: str
    to_agent: str
    task_id: str  # the task created for the receiving worker
    source_state_id: str
    form_id: str | None = None
    finding_id: str | None = None
    setup: SetupRecipe
    requirements: list[RequirementRef] = Field(default_factory=list)
    expected_behaviour: list[Expectation] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)


# --- Assertions --------------------------------------------------------------


class AssertionType(StrEnum):
    element_visible = "element_visible"
    validation_message_present = "validation_message_present"
    navigation_reached = "navigation_reached"
    text_or_value_retained = "text_or_value_retained"
    state_condition = "state_condition"


class Assertion(BaseModel):
    """A typed check from a fixed vocabulary. Code evaluates it; nothing is executed from a model."""

    type: AssertionType
    params: dict[str, Any] = Field(default_factory=dict)
    requirement_ref: str | None = None
    expected: str | None = None  # human-readable expected value
    chosen_by: str | None = None  # agent id that selected it


class AssertionResult(BaseModel):
    assertion: Assertion
    passed: bool
    observed: dict[str, Any] = Field(default_factory=dict)
    evaluated_by: Literal["engine"] = "engine"


# --- Tests and findings ----------------------------------------------------


class TestCase(BaseModel):
    __test__ = False  # not a pytest class

    id: str = Field(default_factory=lambda: new_id("tc"))
    run_id: str
    form_id: str
    handoff_id: str
    designed_by: str  # agent that chose the inputs
    label: str
    inputs: dict[str, str] = Field(default_factory=dict)  # field name -> value
    submit: ControlRef | None = None
    requirement_ref: str | None = None
    expected: str
    expectation_source: str  # requirement id or "unspecified"
    context_id: str | None = None
    status: Literal["planned", "executed", "setup_failed", "execution_failed"] = "planned"
    setup_strategy: str | None = None
    setup_error: str | None = None
    action_result_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    observed: dict[str, Any] = Field(default_factory=dict)  # code-extracted outcome facts
    resulting_state_id: str | None = None
    tester_verdict: Literal["as_expected", "unexpected", "unclear"] | None = None
    tester_note: str | None = None
    model_call_ids: list[str] = Field(default_factory=list)


class VerificationStatus(StrEnum):
    unverified = "unverified"  # only the reporting agent has observed it
    confirmed = "confirmed"
    not_reproduced = "not_reproduced"
    inconclusive = "inconclusive"


class VerificationAttempt(BaseModel):
    """One fresh-context replay by the verifier, evaluated by code."""

    id: str = Field(default_factory=lambda: new_id("ver"))
    run_id: str
    finding_id: str
    handoff_id: str | None = None
    verifier_id: str
    replay_index: int
    target_origin: str
    context_id: str | None = None
    fresh_context: bool = True
    setup_ok: bool = False
    setup_strategy: str | None = None
    setup_error: str | None = None
    # setup: could not recreate the start state; application: the app errored during
    # the repeated actions; expectation: no explicit requirement; verifier: no valid assertion.
    failure_class: Literal["setup", "application", "expectation", "verifier"] | None = None
    assertion: Assertion | None = None
    result: AssertionResult | None = None
    outcome: Literal["confirmed", "not_reproduced", "inconclusive"]
    reason: str
    action_result_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    model_call_id: str | None = None
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None


class Finding(BaseModel):
    """A candidate observation with its original suspicion and any verification."""

    id: str = Field(default_factory=lambda: new_id("fnd"))
    run_id: str
    kind: Literal["persistence_check", "defect_candidate", "review_observation"]
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
    # Checkpoint 2: input-test candidates.
    requirement_ref: str | None = None
    requirement_text: str | None = None
    inputs: dict[str, str] = Field(default_factory=dict)
    reproduction: SetupRecipe | None = None
    reproduction_steps: list[SemanticStep] = Field(default_factory=list)
    form_id: str | None = None
    test_case_id: str | None = None
    handoff_ids: list[str] = Field(default_factory=list)
    verification_ids: list[str] = Field(default_factory=list)
    verified_by: str | None = None
    verification_reason: str | None = None
    source_finding_id: str | None = None  # reverify runs: the finding being re-checked
    # "self": the single-agent baseline checked its own finding (code still evaluated the assertion).
    verification_independence: Literal["independent", "self"] | None = None

    @model_validator(mode="after")
    def _no_self_confirmation(self) -> Finding:
        if self.verification_status != VerificationStatus.unverified:
            if self.reported_by.startswith("explorer"):
                raise ValueError("an explorer cannot set a verification outcome on its own finding")
            if self.verification_independence == "self":
                if not (self.reported_by == self.verified_by == "single-agent"):
                    raise ValueError("only the single-agent baseline records self-checked outcomes")
            else:
                if not self.verified_by or not self.verified_by.startswith("verifier"):
                    raise ValueError("only a verifier can set a verification outcome")
                if self.verified_by == self.reported_by:
                    raise ValueError("a worker cannot verify its own finding")
            if not self.verification_ids:
                raise ValueError("a verification outcome must reference its verification attempts")
        return self


# --- Events and evidence ---------------------------------------------------


class Evidence(BaseModel):
    id: str = Field(default_factory=lambda: new_id("art"))
    run_id: str
    kind: Literal["screenshot", "observation", "model_call", "action_log", "handoff"]
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
    finish_reason: str | None = None  # "length" = truncated at the output limit
    reasoning_tokens: int | None = None
    agent_id: str = "explorer-a"
    phase: Phase = "explore"


class RunDetail(BaseModel):
    run: Run
    states: list[ScreenState]
    transitions: list[Transition]
    actions: list[ActionResult]
    findings: list[Finding]
    events: list[Event]
    evidence: list[Evidence]
    model_calls: list[ModelCall]
    tasks: list[Task] = Field(default_factory=list)
    forms: list[DiscoveredForm] = Field(default_factory=list)
    handoffs: list[Handoff] = Field(default_factory=list)
    test_cases: list[TestCase] = Field(default_factory=list)
    verifications: list[VerificationAttempt] = Field(default_factory=list)
