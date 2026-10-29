"""Explorer run loop and the shared recording used by every worker.

Code owns execution, recording and limits. The model only proposes the next
action. States and transitions are derived from what the browser actually did.
`ReviewRun` (orchestration/review.py) extends this with the input tester and
verifier; a plain `ExplorerRun` is the checkpoint 1 single-explorer mode.
"""

from __future__ import annotations

import asyncio
import hashlib
import threading
import time
import traceback
from typing import Any
from urllib.parse import urlsplit

from flowlens.agents import explorer
from flowlens.browser.engine import BrowserEngine, Execution, control_of, origin_of, state_signature
from flowlens.config import Settings
from flowlens.models.contracts import (
    ActionResult,
    Assertion,
    AssertionResult,
    AssertionType,
    ControlRef,
    DiscoveredForm,
    Event,
    Finding,
    FormField,
    ModelCall,
    NavigateAction,
    Run,
    RunStatus,
    ScreenState,
    SemanticStep,
    StateSighting,
    Task,
    Transition,
    utcnow,
)
from flowlens.services.evidence import EvidenceStore
from flowlens.services.llm import BudgetExceeded, LLMClient, check_budget
from flowlens.storage.db import Store

MAX_CONSECUTIVE_INVALID = 3
FIELD_TAGS = ("input", "textarea", "select")
NON_FIELD_TYPES = ("submit", "button", "reset", "hidden", "image")


def _action_label(action: dict[str, Any], target: str | None) -> str:
    t = action.get("type")
    if t == "fill":
        v = str(action.get("value", ""))
        return f"fill {target or action.get('element_id')} = \"{v[:40]}\""
    if t == "click":
        return f"click {target or action.get('element_id')}"
    if t == "navigate":
        return f"navigate {action.get('url')}"
    return str(t)


def _state_summary(obs) -> str:
    head = obs.headings[0] if obs.headings else obs.title
    msgs = obs.alert_messages or obs.status_messages
    extra = f" — {msgs[0]}" if msgs else ""
    filled = sum(1 for e in obs.elements if e.value)
    fields = sum(1 for e in obs.elements if e.value is not None)
    form = f" ({filled}/{fields} fields filled)" if fields else ""
    return f"{head}{extra}{form}"


def relative_path(url: str) -> str:
    s = urlsplit(url)
    return (s.path or "/") + (f"?{s.query}" if s.query else "")


def semantic_step(action: dict[str, Any], ex: Execution) -> SemanticStep | None:
    """Describe an executed action by meaning, so a fresh session can re-resolve it."""
    t = action.get("type")
    if t == "navigate":
        return SemanticStep(type="navigate", path=relative_path(ex.url_after if ex.ok else action["url"]))
    if t == "reload":
        return SemanticStep(type="reload")
    if t in ("click", "fill") and ex.target_element is not None:
        return SemanticStep(type=t, control=control_of(ex.target_element),
                            value=action.get("value") if t == "fill" else None)
    return None


def extract_forms(obs) -> list[tuple[str, list[FormField], list[ControlRef]]]:
    """Group observed controls by enclosing <form>: (key, fields, submit controls)."""
    groups: dict[int, list] = {}
    for e in obs.elements:
        if e.form_index is not None:
            groups.setdefault(e.form_index, []).append(e)
    out = []
    for els in groups.values():
        fields = [FormField(control=control_of(e), required=e.required, observed_value=e.value)
                  for e in els if e.tag in FIELD_TAGS and (e.input_type or "") not in NON_FIELD_TYPES]
        submits = [control_of(e) for e in els if e.role == "button"]
        if not fields or not submits:
            continue
        # Route is deliberately excluded: the same form on create and edit pages is tested once.
        raw = ";".join(sorted(f"{f.control.role}:{f.control.name}:{f.control.input_type}" for f in fields))
        out.append((hashlib.sha256(raw.encode()).hexdigest()[:16], fields, submits))
    return out


class ExplorerRun:
    def __init__(self, run: Run, store: Store, settings: Settings, llm: LLMClient):
        self.run = run
        self.store = store
        self.settings = settings
        self.llm = llm
        self.ev = EvidenceStore(settings.artifacts_path, store, run.id)
        self.origin = origin_of(run.target_url)
        self.task = Task(run_id=run.id, key=f"{run.id}:explore:start", owner=explorer.AGENT_ID,
                         attempt_id="att_1", status="claimed")
        self.store.put(self.task)
        self.states: dict[str, ScreenState] = {}
        self.forms: dict[str, DiscoveredForm] = {}
        self.recipe: list[dict[str, Any]] = []
        self.semantic: list[SemanticStep] = []
        self.history: list[str] = []
        self.reload_seen_after_save = False
        self.step_seq = -1  # one ordered step counter across every worker in the run

    def next_step(self) -> int:
        self.step_seq += 1
        return self.step_seq

    # --- recording helpers ------------------------------------------------

    def event(self, type_: str, message: str, *, agent_id: str | None = None, task: Task | None = None,
              **data) -> None:
        task = task or self.task
        self.store.append_event(Event(
            run_id=self.run.id, task_id=task.id, attempt_id=task.attempt_id,
            agent_id=agent_id or explorer.AGENT_ID, type=type_, message=message, data=data,
            provenance=self.run.provenance,
        ))

    def record_state(self, ex: Execution, step: int, shot_id: str, *, agent_id: str, phase: str,
                     context_id: str | None, action_result_id: str, task: Task | None = None) -> tuple[ScreenState, bool]:
        sig, route = state_signature(ex.observation)
        st = self.states.get(sig)
        sighting = StateSighting(agent_id=agent_id, phase=phase, context_id=context_id,
                                 action_result_id=action_result_id)
        if st is None:
            st = ScreenState(
                run_id=self.run.id, signature=sig, route=route, url=ex.observation.url,
                title=ex.observation.title, summary=_state_summary(ex.observation),
                screenshot_artifact_id=shot_id, first_seen_step=step,
                setup_recipe=list(self.recipe) if phase == "explore" else [],
                semantic_recipe=list(self.semantic) if phase == "explore" else [],
                discovered_by=agent_id, phase=phase, context_id=context_id, sightings=[sighting],
            )
            self.states[sig] = st
            self.store.put(st)
            self.event("state_discovered", f"New state: {st.summary}", agent_id=agent_id, task=task,
                       state_id=st.id, route=route, phase=phase, context_id=context_id)
            return st, True
        if not any(s.agent_id == agent_id and s.context_id == context_id for s in st.sightings):
            st.sightings.append(sighting)
            self.store.put(st)
        return st, False

    def record_execution(self, action: dict[str, Any], ex: Execution, *, agent_id: str, phase: str,
                         context_id: str | None, task: Task, label: str | None = None
                         ) -> tuple[ActionResult, ScreenState, bool, str]:
        """Store one executed browser action with screenshot and observation evidence."""
        step = self.next_step()
        shot = self.ev.save_screenshot(step, ex.screenshot_png, action["type"])
        obs_art = self.ev.save_json("observation", f"{step:03d}", ex.observation.model_dump())
        result = ActionResult(
            run_id=self.run.id, step=step, action=action, target_description=ex.target_description,
            ok=ex.ok, error=ex.error, url_before=ex.url_before, url_after=ex.url_after,
            started_at=ex.started_at, duration_ms=ex.duration_ms,
            screenshot_artifact_id=shot.id, observation_artifact_id=obs_art.id,
            agent_id=agent_id, phase=phase, context_id=context_id, task_id=task.id,
        )
        self.store.put(result)
        state, new = self.record_state(ex, step, shot.id, agent_id=agent_id, phase=phase,
                                       context_id=context_id, action_result_id=result.id, task=task)
        text = label or _action_label(action, ex.target_description)
        self.event("action_executed", f"Step {step}: {text}" + ("" if ex.ok else f" failed: {ex.error}"),
                   agent_id=agent_id, task=task, action_result_id=result.id, ok=ex.ok,
                   duration_ms=ex.duration_ms, phase=phase, context_id=context_id)
        return result, state, new, obs_art.id

    def _record_explorer_step(self, action: dict[str, Any], ex: Execution, source: ScreenState | None,
                              model_call_id: str | None) -> ScreenState:
        if ex.ok:
            self.recipe.append(action)
            sem = semantic_step(action, ex)
            if sem:
                self.semantic.append(sem)
        result, target, _, obs_art = self.record_execution(
            action, ex, agent_id=explorer.AGENT_ID, phase="explore", context_id="explorer-a:default",
            task=self.task)
        if source is not None:
            self.store.put(Transition(
                run_id=self.run.id, step=result.step, source_state_id=source.id, target_state_id=target.id,
                action=action, label=_action_label(action, ex.target_description),
                action_result_id=result.id, ok=ex.ok, duration_ms=ex.duration_ms,
                screenshot_artifact_id=result.screenshot_artifact_id, model_call_id=model_call_id,
                context_id="explorer-a:default",
            ))
        outcome = "ok" if ex.ok else f"FAILED ({ex.error})"
        self.history.append(f"{result.step}. {_action_label(action, ex.target_description)} -> {outcome}; "
                            f"now at {ex.url_after}")
        if ex.ok:
            self._discover_forms(ex, target, result, obs_art)
        return target

    def _discover_forms(self, ex: Execution, state: ScreenState, result: ActionResult, obs_art: str) -> None:
        for key, fields, submits in extract_forms(ex.observation):
            if key in self.forms:
                continue
            form = DiscoveredForm(
                run_id=self.run.id, key=key, state_id=state.id, url=ex.observation.url, route=state.route,
                headings=ex.observation.headings, fields=fields, submit_controls=submits,
                page_text=ex.observation.text_excerpt[:800], discovered_by=explorer.AGENT_ID,
                action_result_id=result.id,
                evidence_refs=[r for r in (result.screenshot_artifact_id, obs_art) if r],
            )
            self.forms[key] = form
            self.store.put(form)
            names = ", ".join(f.control.name for f in fields)
            self.event("form_discovered", f"Form on {state.route}: {names}", form_id=form.id,
                       state_id=state.id, action_result_id=result.id, evidence_refs=form.evidence_refs)

    def _save_run(self) -> None:
        self.store.put(self.run)

    # --- model calls (one budget for every worker in the run) ----------------

    async def call_model(self, messages: list[dict[str, str]], *, agent_id: str, phase: str, task: Task,
                         reserve: int = 0, max_tokens: int | None = None) -> tuple[str, str]:
        """Budget-checked call recorded against the run. Returns (content, model_call_id).

        `reserve` holds back calls for later workers (verification) from this caller.
        """
        lim = self.run.limits
        check_budget(
            calls_used=self.run.usage.model_calls, max_calls=max(lim.max_model_calls - reserve, 0),
            run_cost=self.run.usage.reported_cost_usd, run_limit=lim.max_cost_usd,
            pool_spent=self.store.total_reported_cost(), pool_limit=self.settings.flowlens_budget_usd,
        )
        call = ModelCall(run_id=self.run.id, step=max(self.step_seq, 0), model=self.llm.model, latency_ms=0,
                         ok=False, agent_id=agent_id, phase=phase)
        resp = None
        try:
            resp = await self.llm.complete(messages, max_tokens or lim.max_output_tokens)
            call.ok = True
        except Exception as e:  # recorded, then surfaced as an invalid reply
            call.error = str(e)[:300]
        u = self.run.usage
        u.model_calls += 1
        if resp:
            call.model, call.provider, call.latency_ms = resp.model, resp.provider, resp.latency_ms
            call.prompt_tokens, call.completion_tokens = resp.prompt_tokens, resp.completion_tokens
            call.total_tokens, call.reported_cost_usd = resp.total_tokens, resp.reported_cost_usd
            u.prompt_tokens += resp.prompt_tokens
            u.completion_tokens += resp.completion_tokens
            u.total_tokens += resp.total_tokens
            if resp.reported_cost_usd is None:
                u.calls_without_cost += 1
            else:
                u.reported_cost_usd += resp.reported_cost_usd
        art = self.ev.save_json("model_call", f"{u.model_calls:03d}-{agent_id}-{call.id}", {
            "agent_id": agent_id, "messages": messages, "response": resp.content if resp else None,
            "usage": resp.raw.get("usage") if resp else None, "error": call.error,
        })
        call.artifact_id = art.id
        self.store.put(call)
        self._save_run()
        self.event("model_call", f"Model call {u.model_calls} ({agent_id}): {call.total_tokens} tokens"
                   + (f", US${call.reported_cost_usd:.5f}" if call.reported_cost_usd is not None else ""),
                   agent_id=agent_id, task=task, model_call_id=call.id, ok=call.ok, phase=phase)
        if resp is None:
            raise ValueError(call.error or "model call failed")
        return resp.content, call.id

    @property
    def explorer_reserve(self) -> int:
        return 0

    async def _decide(self, step: int, obs, note: str | None):
        lim = self.run.limits
        messages = explorer.build_messages(self.run.goal, self.run.requirements, self.history, obs,
                                           step, lim.max_steps, note)
        content, mc_id = await self.call_model(messages, agent_id=explorer.AGENT_ID, phase="explore",
                                               task=self.task, reserve=self.explorer_reserve)
        return explorer.parse_decision(content), mc_id

    # --- same-context check ----------------------------------------------

    def _same_context_check(self, decision: explorer.FinishAction, obs) -> AssertionResult:
        """Engine evaluates the explorer's claimed values against the last real observation.

        Same browser context and same trace: NOT an independent verification.
        """
        rows = []
        for cv in decision.checked_values:
            el = next((e for e in obs.elements if e.name.lower() == cv.field.lower() and e.value is not None), None)
            actual = el.value if el else None
            in_text = cv.expected in obs.text_excerpt
            rows.append({"field": cv.field, "expected": cv.expected, "actual_value": actual,
                         "matched": actual == cv.expected or (el is None and in_text)})
        passed = bool(rows) and all(r["matched"] for r in rows) and self.reload_seen_after_save
        return AssertionResult(
            assertion=Assertion(type=AssertionType.text_or_value_retained,
                                params={"values": [cv.model_dump() for cv in decision.checked_values],
                                        "requires_reload_in_trace": True}),
            passed=passed,
            observed={"fields": rows, "reload_in_trace": self.reload_seen_after_save, "url": obs.url},
        )

    # --- main loop ----------------------------------------------------------

    async def execute(self) -> None:
        run = self.run
        run.status = RunStatus.running
        self._save_run()
        self.event("run_started", f"Run started with model {self.llm.model} ({run.mode})",
                   mocked_model=self.llm.is_mock)
        t_start = time.monotonic()
        try:
            status, reason = await self._explore(t_start)
            self.task.status = "done" if status == RunStatus.completed else "failed"
            self.store.put(self.task)
            status, reason = await self.after_explore(status, reason)
        except Exception as e:
            self.event("run_error", f"{type(e).__name__}: {e}", trace=traceback.format_exc()[-1500:])
            status, reason = RunStatus.failed, f"{type(e).__name__}: {e}"
        self._stop(status, reason)

    async def after_explore(self, status: RunStatus, reason: str) -> tuple[RunStatus, str]:
        return status, reason

    async def _explore(self, t_start: float) -> tuple[RunStatus, str]:
        run, lim = self.run, self.run.limits
        invalid_streak = 0
        note = None
        saw_successful_click = False
        async with BrowserEngine(self.settings.allowed_origins, self.settings.flowlens_headless,
                                 self.settings.flowlens_test_session_path or None) as eng:
            start = NavigateAction(url=run.target_url)
            ex = await eng.execute(start)
            current = self._record_explorer_step(start.model_dump(), ex, None, None)
            if not ex.ok:
                raise RuntimeError(f"could not open target: {ex.error}")
            obs = ex.observation
            for step in range(1, lim.max_steps + 1):
                if time.monotonic() - t_start > lim.max_duration_s:
                    return RunStatus.partial, "time limit reached"
                if len(self.states) >= lim.max_states:
                    return RunStatus.partial, "state-count limit reached"
                try:
                    decision, mc_id = await self._decide(step, obs, note)
                    invalid_streak, note = 0, None
                except BudgetExceeded as e:
                    return RunStatus.partial, str(e)
                except ValueError as e:
                    invalid_streak += 1
                    note = f"Your previous reply was rejected: {e}. Reply with one valid JSON object."
                    self.event("decision_rejected", str(e))
                    if invalid_streak >= MAX_CONSECUTIVE_INVALID:
                        return RunStatus.failed, "model produced repeated invalid decisions"
                    continue
                act = decision.action
                self.event("decision", decision.reasoning, step=step, action=act.model_dump(), model_call_id=mc_id)
                if isinstance(act, explorer.FinishAction):
                    return self._finish(act, obs, mc_id)
                ex = await eng.execute(act)
                if ex.ok and act.type == "click" and ex.url_before != ex.url_after:
                    saw_successful_click = True
                if ex.ok and act.type == "reload" and saw_successful_click:
                    self.reload_seen_after_save = True
                current = self._record_explorer_step(act.model_dump(), ex, current, mc_id)
                obs = ex.observation
            return RunStatus.partial, "step limit reached before the explorer finished"

    def _finish(self, act: explorer.FinishAction, obs, mc_id: str) -> tuple[RunStatus, str]:
        if self.run.mode == "single_explorer" or act.checked_values or act.persistence != "unknown":
            check = self._same_context_check(act, obs)
            finding = Finding(
                run_id=self.run.id, kind="persistence_check", reported_by=explorer.AGENT_ID,
                description="Saved draft content persists after page reload (explorer observation)",
                expected="Values entered and saved are shown again after a reload",
                observed=act.summary, agent_claim=act.persistence, same_context_check=check,
                evidence_refs=[a.id for a in self.store.list_for_run(ActionResult, self.run.id)],
                replay_recipe=list(self.recipe),
            )
            self.store.put(finding)
            self.event("explorer_finished", f"Explorer reports persistence: {act.persistence} (unverified)",
                       finding_id=finding.id, same_context_check_passed=check.passed, model_call_id=mc_id)
        else:
            self.event("explorer_finished", f"Explorer finished: {act.summary[:200]}", model_call_id=mc_id)
        return RunStatus.completed, "explorer finished the goal"

    def _stop(self, status: RunStatus, reason: str) -> None:
        self.run.status = status
        self.run.stop_reason = reason
        self.run.finished_at = utcnow()
        self._save_run()
        self.event("run_finished", f"Run {status.value}: {reason}", agent_id="coordinator", status=status.value)


def start_run_thread(run: Run, store: Store, settings: Settings, llm: LLMClient) -> threading.Thread:
    """Each run gets its own thread and event loop (Playwright needs a subprocess-capable loop on Windows)."""
    from flowlens.orchestration.review import ReviewRun

    cls = ReviewRun if run.mode == "explore_test_verify" else ExplorerRun

    def target():
        asyncio.run(cls(run, store, settings, llm).execute())

    t = threading.Thread(target=target, name=f"run-{run.id}", daemon=True)
    t.start()
    return t
