"""Single-explorer run loop (Checkpoint 1).

Code owns execution, recording and limits. The model only proposes the next
action. States and transitions are derived from what the browser actually did.
"""

from __future__ import annotations

import asyncio
import threading
import time
import traceback
from typing import Any

from flowlens.agents import explorer
from flowlens.browser.engine import BrowserEngine, Execution, state_signature
from flowlens.config import Settings
from flowlens.models.contracts import (
    ActionResult,
    Assertion,
    AssertionResult,
    AssertionType,
    Event,
    Finding,
    ModelCall,
    NavigateAction,
    Run,
    RunStatus,
    ScreenState,
    Task,
    Transition,
    utcnow,
)
from flowlens.services.evidence import EvidenceStore
from flowlens.services.llm import BudgetExceeded, LLMClient, check_budget
from flowlens.storage.db import Store

MAX_CONSECUTIVE_INVALID = 3


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
    extra = f" — {obs.status_messages[0]}" if obs.status_messages else ""
    filled = sum(1 for e in obs.elements if e.value)
    fields = sum(1 for e in obs.elements if e.value is not None)
    form = f" ({filled}/{fields} fields filled)" if fields else ""
    return f"{head}{extra}{form}"


class ExplorerRun:
    def __init__(self, run: Run, store: Store, settings: Settings, llm: LLMClient):
        self.run = run
        self.store = store
        self.settings = settings
        self.llm = llm
        self.ev = EvidenceStore(settings.artifacts_path, store, run.id)
        self.task = Task(run_id=run.id, key=f"{run.id}:explore:start", owner=explorer.AGENT_ID,
                         attempt_id="att_1", status="claimed")
        self.states: dict[str, ScreenState] = {}
        self.recipe: list[dict[str, Any]] = []
        self.history: list[str] = []
        self.reload_seen_after_save = False

    # --- recording helpers ------------------------------------------------

    def event(self, type_: str, message: str, **data) -> None:
        self.store.append_event(Event(
            run_id=self.run.id, task_id=self.task.id, attempt_id=self.task.attempt_id,
            agent_id=explorer.AGENT_ID, type=type_, message=message, data=data,
            provenance=self.run.provenance,
        ))

    def _record_state(self, ex: Execution, step: int, shot_id: str) -> ScreenState:
        sig, route = state_signature(ex.observation)
        st = self.states.get(sig)
        if st is None:
            st = ScreenState(
                run_id=self.run.id, signature=sig, route=route, url=ex.observation.url,
                title=ex.observation.title, summary=_state_summary(ex.observation),
                screenshot_artifact_id=shot_id, first_seen_step=step, setup_recipe=list(self.recipe),
            )
            self.states[sig] = st
            self.store.put(st)
            self.event("state_discovered", f"New state: {st.summary}", state_id=st.id, route=route)
        return st

    def _record_execution(self, step: int, action: dict[str, Any], ex: Execution,
                          source: ScreenState | None, model_call_id: str | None) -> ScreenState:
        shot = self.ev.save_screenshot(step, ex.screenshot_png, action["type"])
        obs_art = self.ev.save_json("observation", f"{step:03d}", ex.observation.model_dump())
        result = ActionResult(
            run_id=self.run.id, step=step, action=action, target_description=ex.target_description,
            ok=ex.ok, error=ex.error, url_before=ex.url_before, url_after=ex.url_after,
            started_at=ex.started_at, duration_ms=ex.duration_ms,
            screenshot_artifact_id=shot.id, observation_artifact_id=obs_art.id,
        )
        self.store.put(result)
        if ex.ok:
            self.recipe.append(action)
        target = self._record_state(ex, step, shot.id)
        if source is not None:
            tr = Transition(
                run_id=self.run.id, step=step, source_state_id=source.id, target_state_id=target.id,
                action=action, label=_action_label(action, ex.target_description),
                action_result_id=result.id, ok=ex.ok, duration_ms=ex.duration_ms,
                screenshot_artifact_id=shot.id, model_call_id=model_call_id,
            )
            self.store.put(tr)
        self.event("action_executed", f"Step {step}: {_action_label(action, ex.target_description)}"
                   + ("" if ex.ok else f" failed: {ex.error}"),
                   action_result_id=result.id, ok=ex.ok, duration_ms=ex.duration_ms)
        outcome = "ok" if ex.ok else f"FAILED ({ex.error})"
        self.history.append(f"{step}. {_action_label(action, ex.target_description)} -> {outcome}; now at {ex.url_after}")
        return target

    def _save_run(self) -> None:
        self.store.put(self.run)

    # --- model step ---------------------------------------------------------

    async def _decide(self, step: int, obs, note: str | None):
        lim = self.run.limits
        check_budget(
            calls_used=self.run.usage.model_calls, max_calls=lim.max_model_calls,
            run_cost=self.run.usage.reported_cost_usd, run_limit=lim.max_cost_usd,
            pool_spent=self.store.total_reported_cost(), pool_limit=self.settings.flowlens_budget_usd,
        )
        messages = explorer.build_messages(self.run.goal, self.run.requirements, self.history, obs,
                                           step, lim.max_steps, note)
        call = ModelCall(run_id=self.run.id, step=step, model=self.llm.model, latency_ms=0, ok=False)
        resp = None
        try:
            resp = await self.llm.complete(messages, lim.max_output_tokens)
            call.ok = True
        except Exception as e:  # recorded, then surfaced as an invalid step
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
        art = self.ev.save_json("model_call", f"{step:03d}-{call.id}", {
            "messages": messages, "response": resp.content if resp else None,
            "usage": resp.raw.get("usage") if resp else None, "error": call.error,
        })
        call.artifact_id = art.id
        self.store.put(call)
        self._save_run()
        self.event("model_call", f"Model call {u.model_calls}: {call.total_tokens} tokens"
                   + (f", US${call.reported_cost_usd:.5f}" if call.reported_cost_usd is not None else ""),
                   model_call_id=call.id, ok=call.ok)
        if resp is None:
            raise ValueError(call.error or "model call failed")
        return explorer.parse_decision(resp.content), call.id

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
        run, lim = self.run, self.run.limits
        run.status = RunStatus.running
        self._save_run()
        self.event("run_started", f"Run started with model {self.llm.model}",
                   mocked_model=self.llm.is_mock)
        t_start = time.monotonic()
        invalid_streak = 0
        note = None
        saw_successful_click = False
        try:
            async with BrowserEngine(self.settings.allowed_origins, self.settings.flowlens_headless,
                                     self.settings.flowlens_test_session_path or None) as eng:
                start = NavigateAction(url=run.target_url)
                ex = await eng.execute(start)
                current = self._record_execution(0, start.model_dump(), ex, None, None)
                if not ex.ok:
                    raise RuntimeError(f"could not open target: {ex.error}")
                obs = ex.observation
                for step in range(1, lim.max_steps + 1):
                    if time.monotonic() - t_start > lim.max_duration_s:
                        return self._stop(RunStatus.partial, "time limit reached")
                    if len(self.states) >= lim.max_states:
                        return self._stop(RunStatus.partial, "state-count limit reached")
                    try:
                        decision, mc_id = await self._decide(step, obs, note)
                        invalid_streak, note = 0, None
                    except BudgetExceeded as e:
                        return self._stop(RunStatus.partial, str(e))
                    except ValueError as e:
                        invalid_streak += 1
                        note = f"Your previous reply was rejected: {e}. Reply with one valid JSON object."
                        self.event("decision_rejected", str(e))
                        if invalid_streak >= MAX_CONSECUTIVE_INVALID:
                            return self._stop(RunStatus.failed, "model produced repeated invalid decisions")
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
                    current = self._record_execution(step, act.model_dump(), ex, current, mc_id)
                    obs = ex.observation
                return self._stop(RunStatus.partial, "step limit reached before the explorer finished")
        except Exception as e:
            self.event("run_error", f"{type(e).__name__}: {e}", trace=traceback.format_exc()[-1500:])
            return self._stop(RunStatus.failed, f"{type(e).__name__}: {e}")

    def _finish(self, act: explorer.FinishAction, obs, mc_id: str) -> None:
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
        self._stop(RunStatus.completed, "explorer finished the goal")

    def _stop(self, status: RunStatus, reason: str) -> None:
        self.run.status = status
        self.run.stop_reason = reason
        self.run.finished_at = utcnow()
        self.task.status = "done" if status == RunStatus.completed else "failed"
        self._save_run()
        self.event("run_finished", f"Run {status.value}: {reason}", status=status.value)


def start_run_thread(run: Run, store: Store, settings: Settings, llm: LLMClient) -> threading.Thread:
    """Each run gets its own thread and event loop (Playwright needs a subprocess-capable loop on Windows)."""

    def target():
        asyncio.run(ExplorerRun(run, store, settings, llm).execute())

    t = threading.Thread(target=target, name=f"run-{run.id}", daemon=True)
    t.start()
    return t
