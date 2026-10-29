"""Shared-queue review (checkpoint 3): two explorers, an input tester and a verifier.

The coordinator is code. Work items live in the persistent queue
(storage/queue.py); four async workers claim them atomically:

- explore (explorer-a, explorer-b): reach a frontier state in a fresh context and
  workspace, take a few model-chosen actions, record states/transitions. Each new
  state becomes an explore task (deduplicated by signature, bounded by depth);
  each new form becomes an input_test task with its handoff.
- input_test (input-tester): the checkpoint 2 tester on a claimed form handoff.
  Candidates become verify tasks that depend on the test task. States reached by
  testing become explore tasks too, so the explorers act on them.
- verify (verifier): the checkpoint 2 verifier on a claimed candidate handoff.

Explorers stop claiming once their share of the call budget is used, leaving
`reserved_testing_calls + reserved_verification_calls` for the other workers.
Anything not run at the end is marked `unfinished` with the reason.
"""

from __future__ import annotations

import asyncio
import time

from flowlens.agents import explorer, input_tester, verifier
from flowlens.browser.engine import Execution
from flowlens.models.contracts import (
    DiscoveredForm,
    Finding,
    Handoff,
    Run,
    RunStatus,
    ScreenState,
    SemanticStep,
    Task,
    TaskStatus,
    TestCase,
    Transition,
    new_id,
)
from flowlens.orchestration.replay import execute_step, reach_state
from flowlens.orchestration.review import COORDINATOR, ReviewRun, _Attempt
from flowlens.orchestration.runner import _action_label, relative_path, semantic_step
from flowlens.services.llm import BudgetExceeded
from flowlens.storage.queue import StaleAttempt, TaskQueue

EXPLORERS = {"explorer-a": "Explorer A", "explorer-b": "Explorer B"}
PRIORITY = {"explore": 1, "input_test": 2, "verify": 3}


class SetupFailed(Exception):
    pass


class QueueReviewRun(ReviewRun):
    persist_root_task = False  # the coordinator's events are not a work item

    def __init__(self, run: Run, store, settings, llm):
        super().__init__(run, store, settings, llm)
        self.queue = TaskQueue(store, run.id)
        self.live: dict[str, set[str]] = {}
        self.busy = 0
        self.stopping: str | None = None
        self.explore_exhausted: str | None = None
        self.depth_cut = 0

    @property
    def explorer_reserve(self) -> int:
        lim = self.run.limits
        return lim.reserved_verification_calls + lim.reserved_testing_calls

    # --- queue helpers ---------------------------------------------------------

    def enqueue(self, type_: str, key: str, *, by: str, payload: dict, depth: int = 0,
                depends_on: list[str] | None = None, input_refs: list[str] | None = None,
                task_id: str | None = None, status: TaskStatus = TaskStatus.ready, note: str | None = None) -> Task | None:
        lim = self.run.limits
        if status == TaskStatus.ready and len(self.queue.snapshot()) >= lim.max_tasks:
            status, note = TaskStatus.unfinished, f"not run: task limit ({lim.max_tasks}) reached"
        t = Task(id=task_id or new_id("task"), run_id=self.run.id, type=type_, key=key, payload=payload,
                 queued_by=by, priority=PRIORITY[type_], depth=depth, depends_on=depends_on or [],
                 input_refs=input_refs or [], max_attempts=lim.task_max_attempts, status=status, note=note)
        t, created = self.queue.enqueue(t)
        if created:
            verb = "queued" if t.status == TaskStatus.ready else f"recorded as {t.status.value}"
            self.event("task_queued" if t.status == TaskStatus.ready else "task_unfinished",
                       f"{type_} task {verb} by {by}: {key}" + (f" ({note})" if note else ""), agent_id=by, task=t,
                       task_type=type_, key=key, depends_on=t.depends_on, payload=payload, depth=depth)
            return t
        return None

    def on_form_discovered(self, form: DiscoveredForm) -> None:
        tid = new_id("task")
        handoff = self.form_handoff(form, tid)
        self.publish_handoff(handoff)
        depth = getattr(self, "_current_depth", 0)
        self.enqueue("input_test", f"input_test:{form.key}", by=form.discovered_by, task_id=tid, depth=depth,
                     payload={"form_id": form.id, "handoff_id": handoff.id}, input_refs=[form.id, handoff.id])

    def defer_frontier(self, states: list[ScreenState], agent_id: str, task: Task) -> None:
        """Queue mode: new states are actionable explore tasks, not deferred."""
        lim = self.run.limits
        for st in states:
            depth = task.depth + 1
            if depth > lim.max_depth:
                self.depth_cut += 1
                self.enqueue("explore", f"explore:{st.signature}", by=agent_id, depth=depth,
                             payload={"state_id": st.id}, input_refs=[st.id], status=TaskStatus.unfinished,
                             note=f"not run: beyond max_depth {lim.max_depth}")
                continue
            self.enqueue("explore", f"explore:{st.signature}", by=agent_id, depth=depth,
                         payload={"state_id": st.id}, input_refs=[st.id])

    def quiescent(self) -> bool:
        wanted = set().union(*self.live.values()) if self.live else set()
        return self.busy == 0 and not (self.queue.claimable_types() & wanted)

    # --- workers -----------------------------------------------------------------

    async def worker(self, agent: str, types: set[str]) -> None:
        lim = self.run.limits
        self.live[agent] = types
        try:
            while not self.stopping:
                if time.monotonic() - self.t_start > lim.max_duration_s:
                    self.stopping = "time limit reached"
                    break
                if agent in EXPLORERS and self.explore_exhausted:
                    break
                task, blocked = self.queue.claim(agent, types, lim.task_lease_s)
                for b in blocked:
                    self.event("task_blocked", f"{b.type} task blocked: {b.note}", agent_id=COORDINATOR, task=b)
                if task is None:
                    if self.quiescent():
                        break
                    await asyncio.sleep(0.25)
                    continue
                self.busy += 1
                self.event("task_claimed", f"{agent} claimed {task.type} task {task.key} (attempt {task.attempts})",
                           agent_id=agent, task=task, lease_expires_at=task.lease_expires_at.isoformat())
                try:
                    refs, note, status = await self.run_task(task, agent)
                    done = self.queue.complete(task, refs, note, status)
                    self.event("task_completed" if done.status == TaskStatus.done else f"task_{done.status.value}",
                               f"{agent} finished {task.type} task {task.key}: {done.status.value}"
                               + (f" ({done.note})" if done.note else ""), agent_id=agent, task=done, result_refs=refs)
                except StaleAttempt as e:
                    self.event("result_rejected", f"Stale result rejected: {e}", agent_id=COORDINATOR, task=task)
                except Exception as e:  # browser/setup errors: bounded retry
                    cur, retried = self.queue.fail(task, f"{type(e).__name__}: {e}")
                    self.event("task_retry" if retried else "task_failed", f"{task.type} task {task.key}: {cur.note}",
                               agent_id=agent, task=cur)
                finally:
                    self.busy -= 1
        finally:
            self.live.pop(agent, None)

    async def run_task(self, task: Task, agent: str) -> tuple[list[str], str | None, TaskStatus | None]:
        if task.type == "explore":
            return await self.explore_task(task, agent)
        if task.type == "input_test":
            form = next(f for f in self.forms.values() if f.id == task.payload["form_id"])
            handoff = self.store.get(Handoff, task.payload["handoff_id"])
            self._current_depth = task.depth
            findings = await self.test_form(form, task=task, handoff=handoff)
            for f in findings:
                self.queue_verification(f, task)
            cases = [c.id for c in self.store.list_for_run(TestCase, self.run.id) if c.handoff_id == handoff.id]
            return cases + [f.id for f in findings], None, None
        if task.type == "verify":
            f = self.store.get(Finding, task.payload["finding_id"])
            handoff = self.store.get(Handoff, task.payload["handoff_id"])
            await self.verify_finding(f, from_agent=handoff.from_agent, task=task, handoff=handoff)
            f = self.store.get(Finding, f.id)
            return f.verification_ids, f"result {f.verification_status.value}", None
        raise ValueError(f"unknown task type {task.type}")

    def queue_verification(self, f: Finding, test_task: Task) -> None:
        tid = new_id("task")
        handoff = self.candidate_handoff(f, input_tester.AGENT_ID, tid)
        self.publish_handoff(handoff)
        f.handoff_ids.append(handoff.id)
        self.store.put(f)
        self.enqueue("verify", f"verify:{f.id}", by=input_tester.AGENT_ID, task_id=tid, depth=test_task.depth,
                     depends_on=[test_task.id], payload={"finding_id": f.id, "handoff_id": handoff.id},
                     input_refs=[f.id, handoff.id])

    # --- explorer task -------------------------------------------------------------

    def team_note(self, agent: str, current: ScreenState) -> str:
        known = [s for s in self.states.values() if s.id != current.id][:15]
        lines = "\n".join(f"- {s.summary} ({s.route}, found by {s.discovered_by})" for s in known) or "- (none yet)"
        return (f"You are {agent}, one of two explorers sharing a map. You started this task at: {current.summary}. "
                f"States the team has already recorded:\n{lines}\n"
                "Prefer actions that reach pages or page conditions not in that list. Finish when nothing new is "
                "reachable within a few actions.")

    async def explore_task(self, task: Task, agent: str) -> tuple[list[str], str | None, TaskStatus | None]:
        lim = self.run.limits
        ctx = self.provider.provision(self.origin, f"{agent}:{task.id}")  # SetupError -> retry
        att = _Attempt(self, agent, "explore", ctx.context_id, task)
        produced: list[str] = []
        status: TaskStatus | None = None
        note = None
        async with self.engine(ctx.cookies) as eng:
            state_id = task.payload.get("state_id")
            if state_id is None:
                start = SemanticStep(type="navigate", path=relative_path(self.run.target_url))
                action, ex = await execute_step(eng, self.origin, start)
                await att.record(action, ex, "open start URL")
                if not ex.ok:
                    raise SetupFailed(f"could not open target: {ex.error}")
                sem = [start]
                current = att.mark_state(ex, recipe=sem)
            else:
                st = self.state_by_id(state_id)
                setup = self.setup_for(st)
                reached = await reach_state(eng, self.origin, setup, att.record)
                if not reached.ok:
                    raise SetupFailed(f"could not reach {st.summary}: {reached.error}")
                ex = reached.execution
                current = att.mark_state(ex)
                sem = list(st.semantic_recipe) if reached.strategy == "recipe" or st.semantic_recipe else [
                    SemanticStep(type="navigate", path=setup.direct_path)]
            obs, history = ex.observation, []
            self._current_depth = task.depth
            for step in range(1, lim.explore_steps_per_task + 1):
                if self.stopping:
                    status, note = TaskStatus.unfinished, f"stopped early: {self.stopping}"
                    break
                messages = explorer.build_messages(self.run.goal, self.run.requirements, history, obs, step,
                                                   lim.explore_steps_per_task, self.team_note(agent, current),
                                                   name=EXPLORERS[agent])
                try:
                    content, mc_id = await self.call_model(messages, agent_id=agent, phase="explore", task=task,
                                                           reserve=self.explorer_reserve)
                except BudgetExceeded as e:
                    self.explore_exhausted = f"explorer share of the budget used ({e})"
                    status, note = TaskStatus.unfinished, f"stopped early: {self.explore_exhausted}"
                    break
                except ValueError as e:
                    history.append(f"(model call failed: {e})")
                    continue
                try:
                    decision = explorer.parse_decision(content)
                except ValueError as e:
                    self.event("decision_rejected", str(e), agent_id=agent, task=task, model_call_id=mc_id)
                    history.append(f"(reply rejected: {e})")
                    continue
                self.event("decision", decision.reasoning, agent_id=agent, task=task, step=step,
                           action=decision.action.model_dump(), model_call_id=mc_id)
                act = decision.action
                if isinstance(act, explorer.FinishAction):
                    note = f"explorer finished: {act.summary[:160]}"
                    break
                ex = await eng.execute(act)
                current, sem = self._explorer_step(act.model_dump(), ex, current, sem, agent, ctx.context_id,
                                                   task, mc_id, att, produced)
                history.append(f"{step}. {_action_label(act.model_dump(), ex.target_description)} -> "
                               f"{'ok' if ex.ok else 'FAILED (' + str(ex.error) + ')'}; now at {ex.url_after}")
                obs = ex.observation
        self.defer_frontier(att.new_states, agent, task)
        return produced, note, status

    def _explorer_step(self, action: dict, ex: Execution, current: ScreenState, sem: list[SemanticStep], agent: str,
                       context_id: str, task: Task, mc_id: str, att: _Attempt, produced: list[str]):
        res, _, _, obs_art = self.record_execution(action, ex, agent_id=agent, phase="explore", context_id=context_id,
                                                   task=task, make_state=False)
        step_sem = semantic_step(action, ex)
        new_sem = [*sem, step_sem] if ex.ok and step_sem else sem
        st, new = self.record_state(ex, res.step, res.screenshot_artifact_id, agent_id=agent, phase="explore",
                                    context_id=context_id, action_result_id=res.id, task=task, recipe=new_sem)
        if new:
            att.new_states.append(st)
            produced.append(st.id)
        tr = Transition(run_id=self.run.id, step=res.step, source_state_id=current.id, target_state_id=st.id,
                        action=action, label=_action_label(action, ex.target_description), action_result_id=res.id,
                        ok=ex.ok, duration_ms=ex.duration_ms, screenshot_artifact_id=res.screenshot_artifact_id,
                        model_call_id=mc_id, agent_id=agent, phase="explore", context_id=context_id)
        self.store.put(tr)
        produced.append(tr.id)
        if ex.ok:
            self._discover_forms(ex, st, res, obs_art, agent_id=agent, task=task)
        return st, new_sem

    # --- run ---------------------------------------------------------------------------

    async def execute(self) -> None:
        run, lim = self.run, self.run.limits
        run.status = RunStatus.running
        self._save_run()
        self.event("run_started", f"Shared-queue review started with model {self.llm.model}: explorer-a, "
                   "explorer-b, input-tester, verifier", agent_id=COORDINATOR, mocked_model=self.llm.is_mock)
        self.t_start = time.monotonic()
        error = None
        self.enqueue("explore", "explore:start", by=COORDINATOR, payload={})
        try:
            await asyncio.gather(
                *(self.worker(a, {"explore"}) for a in EXPLORERS),
                self.worker(input_tester.AGENT_ID, {"input_test"}),
                self.worker(verifier.AGENT_ID, {"verify"}),
            )
        except Exception as e:  # coordinator bug: recorded, never hidden
            error = f"{type(e).__name__}: {e}"
            self.event("run_error", f"Coordinator stopped: {error}", agent_id=COORDINATOR)
        reason = self.stopping or self.explore_exhausted or (f"stopped: {error}" if error else "queue drained")
        left = self.queue.mark_unfinished(f"not run: {reason}")
        for t in left:
            self.event("task_unfinished", f"{t.type} task {t.key} not run: {reason}", agent_id=COORDINATOR, task=t)
        tasks = self.queue.snapshot()
        counts = {s.value: sum(1 for t in tasks if t.status == s) for s in TaskStatus if any(t.status == s for t in tasks)}
        owners = {a: sum(1 for t in tasks if t.owner == a) for a in [*EXPLORERS, input_tester.AGENT_ID, verifier.AGENT_ID]}
        s = self.summary
        text = (f"{reason}; tasks {counts}; claimed by {owners}; {s['cases']} test case(s), {s['candidates']} candidate(s), "
                f"verification {dict((o, s['outcomes'].count(o)) for o in sorted(set(s['outcomes'])))}")
        if error:
            status = RunStatus.failed
            text = f"failed in the coordinator: {error}. Results are incomplete; zero findings does not mean the website passed. {text}"
        elif counts.get("unfinished") or counts.get("blocked") or counts.get("failed") or self.budget_note or self.stopping:
            status = RunStatus.partial
        else:
            status = RunStatus.completed
        self._stop(status, text)
