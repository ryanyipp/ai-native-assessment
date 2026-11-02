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
import contextvars
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
from flowlens.orchestration.coverage import NO_PROGRESS_LIMIT, REFUSAL_LIMIT, Coverage
from flowlens.orchestration.replay import execute_step, reach_state
from flowlens.orchestration.review import COORDINATOR, ReviewRun, _Attempt
from flowlens.orchestration.runner import (
    CANCEL_POLL_S,
    CANCEL_REASON,
    RunCancelled,
    _action_label,
    extract_forms,
    relative_path,
    semantic_step,
)
from flowlens.services.llm import BudgetExceeded
from flowlens.storage.queue import StaleAttempt, TaskQueue

# The task a worker coroutine is executing; each worker runs in its own asyncio task/context.
CURRENT_TASK: contextvars.ContextVar[Task | None] = contextvars.ContextVar("current_task", default=None)

EXPLORERS = {"explorer-a": "Explorer A", "explorer-b": "Explorer B"}
PRIORITY = {"explore": 1, "input_test": 2, "verify": 3}


class SetupFailed(Exception):
    pass


class AttemptRevoked(Exception):
    """The worker's attempt is no longer current (lease expired); it may not act or report."""


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
        self.revoked: set[str] = set()
        self.engines: dict[str, list] = {}
        self.last_seen: dict[str, float] = {}
        self.faults_left = run.fault_injection.times if run.fault_injection else 0
        self.workers_running = False
        self.fault_target_claimed = asyncio.Event()
        self.coverage = Coverage()

    @property
    def explorer_reserve(self) -> int:
        lim = self.run.limits
        return lim.reserved_verification_calls + lim.reserved_testing_calls

    # --- queue helpers ---------------------------------------------------------

    def enqueue(self, type_: str, key: str, *, by: str, payload: dict, depth: int = 0,
                depends_on: list[str] | None = None, input_refs: list[str] | None = None,
                task_id: str | None = None, status: TaskStatus = TaskStatus.ready, note: str | None = None) -> Task | None:
        lim = self.run.limits
        if status == TaskStatus.ready and sum(t.status != TaskStatus.skipped for t in self.queue.snapshot()) >= lim.max_tasks:
            status, note = TaskStatus.unfinished, f"not run: task limit ({lim.max_tasks}) reached"
        t = Task(id=task_id or new_id("task"), run_id=self.run.id, type=type_, key=key, payload=payload,
                 queued_by=by, priority=PRIORITY[type_], depth=depth, depends_on=depends_on or [],
                 input_refs=input_refs or [], max_attempts=lim.task_max_attempts, status=status, note=note)
        t, created = self.queue.enqueue(t)
        if created:
            verb = "queued" if t.status == TaskStatus.ready else f"recorded as {t.status.value}"
            self.event({TaskStatus.ready: "task_queued", TaskStatus.skipped: "task_skipped"}.get(t.status, "task_unfinished"),
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

    def frontier_skip_reason(self, st: ScreenState, task: Task) -> str | None:
        """Why a new state should not become exploration work, or None if it should.

        Only page structure is compared; states are never merged, they keep their own
        records and sightings. Messages (errors, saved banners) and dialogs change the
        structure, so they are not treated as variations.
        """
        explored = {t.payload.get("state_id") for t in self.queue.snapshot()
                    if t.type == "explore" and t.status in (TaskStatus.ready, TaskStatus.claimed, TaskStatus.done)}
        if task.type == "explore" and not task.payload.get("state_id"):
            explored.add(None)
        for other in self.states.values():
            if other.id == st.id or other.structure is None or other.structure != st.structure:
                continue
            if other.id in explored or other.id == task.payload.get("state_id"):
                return f"variation of '{other.summary}': same page structure, only field fill state differs"
        if task.type in ("input_test", "verify"):
            form = next((f for f in self.forms.values() if f.id == task.payload.get("form_id")), None)
            if form is None and task.type == "verify":
                fnd = next((f for f in self.store.list_for_run(Finding, self.run.id)
                            if f.id == task.payload.get("finding_id")), None)
                form = next((f for f in self.forms.values() if fnd and f.id == fnd.form_id), None)
            form_state = self.state_by_id(form.state_id) if form else None
            if form_state and form_state.layout and form_state.layout == st.layout:
                return (f"outcome of the already-tested form '{form_state.summary}' "
                        "(same layout; its messages are kept in the test-case record)")
        return self.covered_by(st, explored, task)

    def covered_by(self, st: ScreenState, explored: set, task: Task) -> str | None:
        """Why this page adds no exploration: an explored page on its route leads everywhere it does.

        Catches pages that differ only by listed data or a status banner (run_3f84fb9bdc8b: the events
        page with bookings, and /?cancelled=1). The state stays on the map; only the extra task is
        skipped. A new control, form field, link target or alert keeps it explorable.
        """
        if not st.destinations:
            return None
        for other in self.states.values():
            if (other.id != st.id and other.route == st.route and set(st.destinations) <= set(other.destinations)
                    and (other.id in explored or other.id == task.payload.get("state_id"))):
                return f"same destinations as '{other.summary}': only listed data or a status message differs"
        return None

    def defer_frontier(self, states: list[ScreenState], agent_id: str, task: Task) -> None:
        """Queue mode: new states are actionable explore tasks unless they add nothing new to explore."""
        lim = self.run.limits
        for st in states:
            depth = task.depth + 1
            why = self.frontier_skip_reason(st, task)
            if why:
                self.enqueue("explore", f"explore:{st.signature}", by=agent_id, depth=depth,
                             payload={"state_id": st.id}, input_refs=[st.id], status=TaskStatus.skipped,
                             note=f"not explored: {why}")
                continue
            if depth > lim.max_depth:
                self.depth_cut += 1
                self.enqueue("explore", f"explore:{st.signature}", by=agent_id, depth=depth,
                             payload={"state_id": st.id}, input_refs=[st.id], status=TaskStatus.unfinished,
                             note=f"not run: beyond max_depth {lim.max_depth}")
                continue
            self.enqueue("explore", f"explore:{st.signature}", by=agent_id, depth=depth,
                         payload={"state_id": st.id}, input_refs=[st.id])

    def quiescent(self) -> bool:
        return self.busy == 0 and not any(self.queue.claimable_for(w, t) for w, t in self.live.items())

    # --- leases ------------------------------------------------------------------

    def other_worker_can_take(self, task: Task, owner: str) -> bool:
        return any(w != owner and task.type in types and w not in task.excluded_workers
                   for w, types in self.live.items())

    def engine(self, cookies):
        eng = super().engine(cookies)
        task = CURRENT_TASK.get()
        if task is not None:
            self.check_attempt(task, "browser context")  # refuse or renew before launching a context
            eng.before_action = lambda t=task: self.check_attempt(t, "browser action")
            self.engines.setdefault(task.attempt_id, []).append(eng)
        return eng

    def cancel(self) -> None:
        super().cancel()
        self.stopping = CANCEL_REASON  # workers claim nothing more

    def check_attempt(self, task: Task, what: str) -> None:
        """Refuse work from a cancelled run or an expired attempt; otherwise renew its lease."""
        self.raise_if_cancelled()
        if task.attempt_id in self.revoked:
            self.event("late_action_rejected", f"Refused {what} from {task.owner} attempt {task.attempt_id}: "
                       "its lease expired and the task was reassigned", agent_id=COORDINATOR, task=task,
                       worker=task.owner, attempt_id=task.attempt_id, what=what)
            raise AttemptRevoked(f"{task.attempt_id} revoked")
        try:
            self.queue.renew(task, self.run.limits.task_lease_s)
        except StaleAttempt as e:
            self.revoked.add(task.attempt_id or "")
            raise AttemptRevoked(str(e)) from e
        self.last_seen[task.attempt_id or ""] = time.monotonic()
        self.raise_if_cancelled()  # the renewal takes time; a request may have landed during it

    def guard_publish(self, task: Task) -> None:
        self.check_attempt(task, "result")

    def save_task(self, task: Task) -> None:
        try:
            self.queue.update(task)
        except StaleAttempt as e:
            self.revoked.add(task.attempt_id or "")
            raise AttemptRevoked(str(e)) from e

    def start_heartbeat(self, task: Task):
        """Renew the lease while a model call is in flight.

        A healthy call is bounded by the model timeout and must not expire its task;
        a stalled worker makes no call, so its lease still runs out.
        """
        current = CURRENT_TASK.get()
        if current is None:
            return None
        interval = max(0.5, self.run.limits.task_lease_s / 3)
        stop_at = time.monotonic() + self.call_deadline_s

        async def beat():
            while True:
                await asyncio.sleep(interval)
                if time.monotonic() > stop_at:
                    # A healthy call has returned by now; stop vouching for a hung one so its lease can expire.
                    self.event("heartbeat_stopped", f"Stopped renewing {current.key} for {current.owner}: model call "
                               f"exceeded {self.call_deadline_s:.0f}s", agent_id=COORDINATOR, task=current)
                    return
                try:
                    self.queue.renew(current, self.run.limits.task_lease_s)
                except StaleAttempt:
                    return
                self.last_seen[current.attempt_id or ""] = time.monotonic()

        return asyncio.create_task(beat())

    def guard_call(self, task: Task) -> None:
        current = CURRENT_TASK.get()
        if current is not None:
            self.check_attempt(current, "model call")

    async def maybe_stall(self, task: Task, agent: str) -> None:
        """Labelled fault injection: the worker stops renewing its lease while holding an open context."""
        fi = self.run.fault_injection
        if not fi or self.faults_left <= 0 or fi.worker != agent or fi.task_type != task.type:
            return
        self.faults_left -= 1
        self.event("fault_injected", f"[INJECTED FAULT] {agent} stalls for {fi.stall_s}s holding {task.key} "
                   f"attempt {task.attempt_id} (lease {self.run.limits.task_lease_s}s)", agent_id=agent, task=task,
                   injected=True, stall_s=fi.stall_s, attempt_id=task.attempt_id)
        resume_at = time.monotonic() + fi.stall_s
        while time.monotonic() < resume_at and not self.cancel_requested.is_set():
            await asyncio.sleep(CANCEL_POLL_S)
        self.event("fault_injected", f"[INJECTED FAULT] {agent} resumes after its stall and tries to continue",
                   agent_id=agent, task=task, injected=True, attempt_id=task.attempt_id)

    async def watchdog(self) -> None:
        lease = self.run.limits.task_lease_s
        while self.workers_running:
            for t, owner, attempt, retried in self.queue.expire_overdue(can_exclude=self.other_worker_can_take):
                self.revoked.add(attempt)
                idle = time.monotonic() - self.last_seen.get(attempt, time.monotonic() - lease)
                self.event("lease_expired", f"Lease expired: {owner} attempt {attempt} on {t.key} made no action or "
                           f"model call for {idle:.0f}s (lease {lease}s). Attempt revoked.", agent_id=COORDINATOR,
                           task=t, worker=owner, attempt_id=attempt, idle_s=round(idle, 1),
                           injected=bool(self.run.fault_injection))
                closed = 0
                for eng in self.engines.get(attempt, []):
                    await eng.fence()
                    closed += 1
                self.event("context_fenced", f"Closed {closed} browser context(s) of {owner} attempt {attempt}; "
                           "further actions from it fail", agent_id=COORDINATOR, task=t, attempt_id=attempt,
                           contexts_closed=closed)
                if retried:
                    t = self.queue.release(t.id)
                    who = ("another worker" if owner in t.excluded_workers
                           else f"a fresh attempt by {owner} (no other {t.type} worker)")
                    self.event("task_reassigned", f"{t.key} returned to the queue for {who} "
                               f"(excluded: {', '.join(t.excluded_workers) or 'none'}; attempt {t.attempts}/{t.max_attempts} used)",
                               agent_id=COORDINATOR, task=t, excluded=t.excluded_workers)
                else:
                    self.event("task_failed", f"{t.key}: {t.note}", agent_id=COORDINATOR, task=t)
            await asyncio.sleep(0.25)

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
                fi = self.run.fault_injection
                if (fi and self.faults_left and agent != fi.worker and fi.task_type in types
                        and not self.fault_target_claimed.is_set()):
                    # Labelled injection setup: the faulty worker claims first so the stall hits real work.
                    try:
                        await asyncio.wait_for(self.fault_target_claimed.wait(), timeout=15)
                    except TimeoutError:
                        self.fault_target_claimed.set()
                    continue
                task, blocked = self.queue.claim(agent, types, lim.task_lease_s)
                for b in blocked:
                    self.event("task_blocked", f"{b.type} task blocked: {b.note}", agent_id=COORDINATOR, task=b)
                if task is None:
                    if self.quiescent():
                        break
                    await asyncio.sleep(0.25)
                    continue
                self.busy += 1
                self.last_seen[task.attempt_id or ""] = time.monotonic()
                self.event("task_claimed", f"{agent} claimed {task.type} task {task.key} (attempt {task.attempts})",
                           agent_id=agent, task=task, lease_expires_at=task.lease_expires_at.isoformat(),
                           attempt_id=task.attempt_id)
                if self.run.fault_injection and agent == self.run.fault_injection.worker:
                    self.fault_target_claimed.set()
                token = CURRENT_TASK.set(task)
                try:
                    refs, note, status = await self.run_task(task, agent)
                    done = self.queue.complete(task, refs, note, status)
                    self.event("task_completed" if done.status == TaskStatus.done else f"task_{done.status.value}",
                               f"{agent} finished {task.type} task {task.key}: {done.status.value}"
                               + (f" ({done.note})" if done.note else ""), agent_id=agent, task=done, result_refs=refs)
                    if done.expired_attempts and done.status == TaskStatus.done:
                        self.event("task_recovered", f"{task.key} recovered: expired attempt(s) "
                                   f"{', '.join(done.expired_attempts)}; completed by {agent} attempt {task.attempt_id}",
                                   agent_id=COORDINATOR, task=done, completed_by=agent)
                except RunCancelled:  # still claimed: the end of the run marks it unfinished with the reason
                    self.event("task_cancelled", f"{agent} stopped {task.type} task {task.key}: {CANCEL_REASON}",
                               agent_id=agent, task=task)
                except (AttemptRevoked, StaleAttempt) as e:
                    self.reject_late_result(task, agent, e)
                except Exception as e:  # browser/setup errors: bounded retry
                    cur, retried = self.queue.fail(task, f"{type(e).__name__}: {e}")
                    self.event("task_retry" if retried else "task_failed", f"{task.type} task {task.key}: {cur.note}",
                               agent_id=agent, task=cur)
                finally:
                    CURRENT_TASK.reset(token)
                    self.busy -= 1
        finally:
            self.live.pop(agent, None)

    def reject_late_result(self, task: Task, agent: str, why: Exception) -> None:
        """The expired worker still submits what it has; the queue must refuse it."""
        try:
            self.queue.complete(task, [], f"late result from {agent}")
            self.event("run_error", f"BUG: late result from {agent} {task.attempt_id} was accepted", agent_id=COORDINATOR,
                       task=task)
        except StaleAttempt as e:
            self.event("result_rejected", f"Late result from {agent} attempt {task.attempt_id} rejected: {e}",
                       agent_id=COORDINATOR, task=task, worker=agent, attempt_id=task.attempt_id, cause=str(why)[:200],
                       injected=bool(self.run.fault_injection))

    async def run_task(self, task: Task, agent: str) -> tuple[list[str], str | None, TaskStatus | None]:
        if task.type == "explore":
            return await self.explore_task(task, agent)
        if task.type == "input_test":
            form = next(f for f in self.forms.values() if f.id == task.payload["form_id"])
            handoff = self.store.get(Handoff, task.payload["handoff_id"])
            self._current_depth = task.depth
            lim = self.run.limits
            # Admission: a test needs a plan and an assessment call. Hold both now, so verification
            # or exploration running meanwhile cannot strand a test halfway (seen in batch-cs-queue-rerun).
            if not self.admit(task.id, 2, lim.reserved_verification_calls):
                return [], "not admitted: not enough call capacity left for a full test (plan + assessment)", \
                    TaskStatus.unfinished
            self.event("capacity_held", f"Held 2 calls for {task.key} (admitted test)", agent_id=COORDINATOR,
                       task=task, holds=dict(self.holds))
            try:
                findings = await self.test_form(form, task=task, handoff=handoff)
            finally:
                self.release(task.id)
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
                "FlowLens replayed any steps needed to reach this page in your own test workspace, so data shown here "
                "may come from that setup, not from you. The input tester owns every recorded form: do not fill or "
                "submit one, and do not repeat a journey to satisfy the goal again. "
                "Prefer actions that reach pages or page conditions not in that list. Finish when nothing new is "
                "reachable within a few actions.")

    def stop_no_progress(self, agent: str, task: Task, why: str) -> str:
        note = f"stopped: no exploration progress ({why})"
        self.event("explore_no_progress", f"{agent} {note}", agent_id=agent, task=task)
        return note

    def tester_owned(self, obs, act) -> str | None:
        """The recorded form this explorer action would fill or submit, if any."""
        el = next((e for e in obs.elements if e.id == getattr(act, "element_id", None)), None)
        if el is None:
            return None
        for key, fields, submits in extract_forms(obs):
            controls = {(c.role, c.name) for c in [*(f.control for f in fields), *submits]}
            if key in self.forms and (el.role, el.name) in controls:
                return key
        return None

    async def explore_task(self, task: Task, agent: str) -> tuple[list[str], str | None, TaskStatus | None]:
        try:
            return await self._explore_task(task, agent)
        finally:  # a failed or revoked attempt leaves its work open for the retry
            self.coverage.release(agent)

    async def _explore_task(self, task: Task, agent: str) -> tuple[list[str], str | None, TaskStatus | None]:
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
            self.coverage.observe(obs)
            stalled = refused = 0
            self._current_depth = task.depth
            await self.maybe_stall(task, agent)
            for step in range(1, lim.explore_steps_per_task + 1):
                if self.stopping:
                    status, note = TaskStatus.unfinished, f"stopped early: {self.stopping}"
                    break
                if self.coverage.nothing_left(agent, obs):  # no call: nothing is left for this explorer to choose
                    note = self.stop_no_progress(agent, task, "no unexplored control is reachable from here")
                    break
                self.coverage.assign(agent, obs)
                messages = explorer.build_messages(self.run.goal, self.run.requirements, history, obs, step,
                                                   lim.explore_steps_per_task,
                                                   self.team_note(agent, current) + "\n" + self.coverage.summary(agent, obs),
                                                   name=EXPLORERS[agent])
                try:
                    content, mc_id = await self.call_model(
                        messages, agent_id=agent, phase="explore", task=task,
                        reserve=lim.reserved_verification_calls,
                        phase_cap=lim.max_model_calls - lim.reserved_testing_calls - lim.reserved_verification_calls)
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
                    # An unverified note, kept apart from findings: no requirement, no verification task.
                    self.event("explorer_observation", act.summary, agent_id=agent, task=task, state_id=current.id,
                               route=current.route, persistence=act.persistence, model_call_id=mc_id)
                    break
                owned = self.tester_owned(obs, act)
                if owned:
                    self.event("explorer_action_refused", f"{agent} may not use form {owned}: the input tester owns it",
                               agent_id=agent, task=task, model_call_id=mc_id, action=act.model_dump())
                    history.append(f"{step}. refused, not run: the input tester owns this form. Go elsewhere or finish.")
                    continue
                el = next((e for e in obs.elements if e.id == getattr(act, "element_id", None)), None)
                why = self.coverage.repeat_reason(agent, el, obs) if el is not None else None
                if why:
                    self.event("explorer_repeat_refused", f"{agent}: {why}", agent_id=agent, task=task,
                               model_call_id=mc_id, action=act.model_dump())
                    history.append(f"{step}. refused, not run: {why}")
                    refused += 1
                    if refused >= REFUSAL_LIMIT:
                        note = self.stop_no_progress(agent, task, f"{refused} repeated choices refused")
                        break
                    continue
                fresh = el is not None and self.coverage.is_new(el)
                ex = await eng.execute(act)
                current, sem = self._explorer_step(act.model_dump(), ex, current, sem, agent, ctx.context_id,
                                                   task, mc_id, att, produced)
                history.append(f"{step}. {_action_label(act.model_dump(), ex.target_description)} -> "
                               f"{'ok' if ex.ok else 'FAILED (' + str(ex.error) + ')'}; now at {ex.url_after}")
                obs = ex.observation
                discovered = self.coverage.observe(obs)
                if ex.ok:
                    self.coverage.record(el, obs, current.summary)
                else:
                    self.coverage.failed(el)
                stalled = 0 if discovered or (fresh and ex.ok) else stalled + 1
                if stalled >= NO_PROGRESS_LIMIT:
                    note = self.stop_no_progress(agent, task, f"{stalled} steps reached nothing new")
                    break
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
        if run.fault_injection:
            self.event("fault_injected", f"[INJECTED FAULT] configured: {run.fault_injection.model_dump()}",
                       agent_id=COORDINATOR, injected=True)
        self.workers_running = True
        dog = asyncio.create_task(self.watchdog())
        try:
            await asyncio.gather(
                *(self.worker(a, {"explore"}) for a in EXPLORERS),
                self.worker(input_tester.AGENT_ID, {"input_test"}),
                self.worker(verifier.AGENT_ID, {"verify"}),
            )
        except Exception as e:  # coordinator bug: recorded, never hidden
            error = f"{type(e).__name__}: {e}"
            self.event("run_error", f"Coordinator stopped: {error}", agent_id=COORDINATOR)
        finally:
            self.workers_running = False
            await dog
            for att, engs in self.engines.items():  # cleanup: nothing from a revoked attempt stays open
                if att in self.revoked:
                    for eng in engs:
                        if not eng.closed_by_coordinator:
                            await eng.fence()
        reason = self.stopping or self.explore_exhausted or (f"stopped: {error}" if error else "queue drained")
        left = self.queue.mark_unfinished(f"not run: {reason}")
        for t in left:
            self.event("task_unfinished", f"{t.type} task {t.key} not run: {reason}", agent_id=COORDINATOR, task=t)
        tasks = self.queue.snapshot()
        counts = {s.value: sum(1 for t in tasks if t.status == s) for s in TaskStatus if any(t.status == s for t in tasks)}
        owners = {a: sum(1 for t in tasks if t.owner == a) for a in [*EXPLORERS, input_tester.AGENT_ID, verifier.AGENT_ID]}
        s = self.summary
        text = (f"{reason}; tasks {counts}; claimed by {owners}; {s['cases']} test case(s) executed{f", {s['not_completed']} not completed" if s['not_completed'] else ""}, {s['candidates']} candidate(s), "
                f"verification {dict((o, s['outcomes'].count(o)) for o in sorted(set(s['outcomes'])))}")
        if self.cancel_requested.is_set():
            status = RunStatus.cancelled
            text = f"Results are incomplete. {text}"
        elif error:
            status = RunStatus.failed
            text = f"failed in the coordinator: {error}. Results are incomplete; zero findings does not mean the website passed. {text}"
        elif counts.get("unfinished") or counts.get("blocked") or counts.get("failed") or self.budget_note or self.stopping:
            status = RunStatus.partial
        else:
            status = RunStatus.completed
        self._stop(status, text)
