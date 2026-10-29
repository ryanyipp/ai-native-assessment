"""Sequential explorer -> input tester -> verifier review (checkpoint 2).

The coordinator here is plain code. It turns the explorer's discovered forms
into tester handoffs, executes the tester's chosen cases in fresh contexts with
fresh test data, turns unexpected outcomes into candidate findings, hands each
candidate to the verifier, and accepts a verification result only after
checking who produced it and that it is backed by engine-evaluated evidence.

Concurrent claims, leases and the second explorer come in checkpoint 3; tasks
are recorded with the fields those need, and new states found by testing are
recorded as deferred exploration tasks rather than explored now.
"""

from __future__ import annotations

from typing import Any

from flowlens.agents import input_tester, verifier
from flowlens.agents.common import outcome_facts, requirement_refs
from flowlens.browser.engine import BrowserEngine, ControlResolutionError, Execution
from flowlens.models.contracts import (
    ActionResult,
    Assertion,
    ControlRef,
    DiscoveredForm,
    Expectation,
    Finding,
    Handoff,
    Run,
    RunStatus,
    ScreenState,
    SemanticStep,
    SetupRecipe,
    Task,
    TestCase,
    Transition,
    VerificationAttempt,
    VerificationStatus,
    new_id,
    utcnow,
)
from flowlens.orchestration.replay import execute_step, reach_state
from flowlens.orchestration.runner import ExplorerRun, relative_path
from flowlens.services.llm import BudgetExceeded
from flowlens.services.test_data import SetupError, WorkspaceProvider
from flowlens.verification.assertions import AssertionInvalid, evaluate, validate_assertion

COORDINATOR = "coordinator"


def _short_inputs(inputs: dict[str, str]) -> str:
    return ", ".join(f"{k}={v[:24]!r}" for k, v in inputs.items())[:90]


class _Attempt:
    """Collects the records produced inside one fresh browser context."""

    def __init__(self, review: ReviewRun, agent_id: str, phase: str, context_id: str, task: Task):
        self.r, self.agent_id, self.phase, self.context_id, self.task = review, agent_id, phase, context_id, task
        self.results: list[ActionResult] = []
        self.states: list[ScreenState] = []
        self.new_states: list[ScreenState] = []
        self.evidence: list[str] = []
        self.duration_ms = 0

    async def record(self, action: dict, ex: Execution, label: str) -> None:
        # Intermediate setup and fill steps are kept as actions with evidence, not as map states.
        res, _, _, obs_art = self.r.record_execution(action, ex, agent_id=self.agent_id, phase=self.phase,
                                                     context_id=self.context_id, task=self.task, label=label,
                                                     make_state=False)
        self.results.append(res)
        self.evidence += [x for x in (res.screenshot_artifact_id, obs_art) if x]
        self.duration_ms += res.duration_ms

    def mark_state(self, ex: Execution, recipe: list[SemanticStep] | None = None) -> ScreenState:
        """Record the state after the latest action: the reached start state or the outcome.

        `recipe` is how a fresh worker reaches this state from the start; it is stored
        only if the state is new, so it can become an actionable exploration task.
        """
        last = self.results[-1]
        st, new = self.r.record_state(ex, last.step, last.screenshot_artifact_id, agent_id=self.agent_id,
                                      phase=self.phase, context_id=self.context_id, action_result_id=last.id,
                                      task=self.task, recipe=recipe)
        self.states.append(st)
        if new:
            self.new_states.append(st)
        return st


class ReviewRun(ExplorerRun):
    tester_id = input_tester.AGENT_ID
    verifier_id = verifier.AGENT_ID
    # False only for the single-agent baseline, whose checks are self-checks by the reporting agent.
    independent_verification = True
    def __init__(self, run: Run, store, settings, llm):
        super().__init__(run, store, settings, llm)
        self.reqs = requirement_refs(run.requirements)
        self.req_ids = {r.id: r for r in self.reqs}
        self.provider = WorkspaceProvider(settings.flowlens_workspace_endpoint, settings.flowlens_workspace_cookie)
        self.budget_note: str | None = None
        self.summary: dict[str, Any] = {"forms_tested": 0, "cases": 0, "candidates": 0, "outcomes": []}

    def incomplete_note(self) -> str:
        s = self.summary
        return (f" (before stopping: {len(self.forms)} form(s) discovered, {s['forms_tested']} handed to the tester, "
                f"{s['cases']} case(s) run, {s['candidates']} candidate(s), {len(s['outcomes'])} verified). "
                "Zero findings here does not mean the website passed")

    @property
    def explorer_reserve(self) -> int:
        # Explorer leaves room for the tester (2 calls per form) and verification.
        lim = self.run.limits
        return lim.reserved_verification_calls + 2 * min(lim.max_forms_tested, 1)

    def engine(self, cookies: list[dict]) -> BrowserEngine:
        return BrowserEngine(self.settings.allowed_origins, self.settings.flowlens_headless,
                             self.settings.flowlens_test_session_path or None, cookies=cookies)

    def state_by_id(self, state_id: str) -> ScreenState | None:
        return next((s for s in self.states.values() if s.id == state_id), None)

    def setup_for(self, state: ScreenState) -> SetupRecipe:
        return SetupRecipe(target_state_id=state.id, expected_signature=state.signature,
                           direct_path=relative_path(state.url), steps=list(state.semantic_recipe))

    def new_task(self, type_: str, key: str, owner: str, input_refs: list[str]) -> Task:
        t = Task(run_id=self.run.id, type=type_, key=key, owner=owner, attempt_id="att_1", status="claimed",
                 input_refs=input_refs)
        self.store.put(t)
        return t

    def publish_handoff(self, h: Handoff) -> str:
        art = self.ev.save_json("handoff", h.id, h.model_dump(mode="json"))
        h.evidence_refs = [*h.evidence_refs, art.id]
        self.store.put(h)
        what = f"form {h.form_id}" if h.kind == "form_to_tester" else f"candidate {h.finding_id}"
        self.event("handoff_created", f"Handoff {h.id}: {what} from {h.from_agent} to {h.to_agent}",
                   agent_id=COORDINATOR, handoff_id=h.id, kind=h.kind, from_agent=h.from_agent,
                   to_agent=h.to_agent, form_id=h.form_id, finding_id=h.finding_id, task_id=h.task_id,
                   artifact_id=art.id)
        return art.id

    def defer_frontier(self, states: list[ScreenState], agent_id: str, task: Task) -> None:
        for st in states:
            t = Task(run_id=self.run.id, type="explore", key=f"{self.run.id}:explore:{st.signature}",
                     input_refs=[st.id], status="deferred", owner=None,
                     note="New state found by testing; the shared exploration queue arrives in checkpoint 3.")
            self.store.put(t)
            self.event("frontier_deferred", f"New state from {agent_id} queued for exploration (deferred): {st.summary}",
                       agent_id=COORDINATOR, task=task, state_id=st.id, deferred_task_id=t.id)

    async def model(self, messages, *, agent_id: str, phase: str, task: Task, parse, reserve: int = 0):
        """One model call plus one corrective retry on an invalid reply."""
        note_msgs = messages
        last_err = None
        for _ in range(2):
            content, mc_id = await self.call_model(note_msgs, agent_id=agent_id, phase=phase, task=task,
                                                   reserve=reserve,
                                                   max_tokens=self.run.limits.max_output_tokens_planning,
                                                   reasoning_tokens=self.run.limits.planning_reasoning_tokens)
            try:
                return parse(content), mc_id
            except ValueError as e:
                last_err = e
                self.event("decision_rejected", str(e), agent_id=agent_id, task=task, model_call_id=mc_id)
                note_msgs = [*messages[:-1], {"role": "user", "content": messages[-1]["content"]
                             + f"\n\nNote: your previous reply was rejected: {e}. Reply with one valid JSON object."}]
        raise ValueError(f"{agent_id} produced invalid replies: {last_err}")

    # --- coordinator ---------------------------------------------------------

    async def after_explore(self, status: RunStatus, reason: str) -> tuple[RunStatus, str]:
        if status == RunStatus.failed:
            return status, reason
        lim = self.run.limits
        forms = list(self.forms.values())
        if not forms:
            self.event("no_forms", "The explorer did not open any form, so nothing was handed to the tester.",
                       agent_id=COORDINATOR)
        candidates: list[Finding] = []
        for form in forms[: lim.max_forms_tested]:
            self.stage = f"testing form {form.id} ({form.route}) as input-tester"
            candidates += await self.test_form(form)
        for f in candidates:
            self.stage = f"verifying finding {f.id} as verifier"
            await self.verify_finding(f, from_agent=self.tester_id)
        self.stage = "finishing"
        s = self.summary
        outcome_counts = {o: s["outcomes"].count(o) for o in sorted(set(s["outcomes"]))}
        text = (f"{reason}; {s['forms_tested']} form(s) tested with {s['cases']} case(s); "
                f"{s['candidates']} candidate(s)"
                + (f", verification: {outcome_counts}" if outcome_counts else ""))
        if self.budget_note or status == RunStatus.partial:
            return RunStatus.partial, text + (f"; stopped early: {self.budget_note}" if self.budget_note else "")
        return RunStatus.completed, text

    # --- input tester ----------------------------------------------------------

    def form_handoff(self, form: DiscoveredForm, task_id: str) -> Handoff:
        state = self.state_by_id(form.state_id)
        assert state is not None
        return Handoff(
            run_id=self.run.id, kind="form_to_tester", from_agent=form.discovered_by, to_agent=self.tester_id,
            task_id=task_id, source_state_id=state.id, form_id=form.id, setup=self.setup_for(state),
            requirements=self.reqs,
            expected_behaviour=[Expectation(text=r.text, source=r.id) for r in self.reqs]
            or [Expectation(text="No requirement supplied.", source="none supplied")],
            evidence_refs=list(form.evidence_refs),
        )

    async def test_form(self, form: DiscoveredForm, task: Task | None = None,
                        handoff: Handoff | None = None) -> list[Finding]:
        """Sequential mode creates the task and handoff here; queue mode passes in the claimed ones."""
        lim = self.run.limits
        state = self.state_by_id(form.state_id)
        assert state is not None
        if task is None:
            task = self.new_task("input_test", f"{self.run.id}:input_test:{form.key}", self.tester_id, [form.id])
        if handoff is None:
            handoff = self.form_handoff(form, task.id)
            self.publish_handoff(handoff)
            task.input_refs.append(handoff.id)
            self.store.put(task)
        self.summary["forms_tested"] += 1
        try:
            plan, plan_mc = await self.model(
                input_tester.plan_messages(handoff, form, lim.max_cases_per_form),
                agent_id=self.tester_id, phase="input_test", task=task, parse=input_tester.parse_plan,
                reserve=lim.reserved_verification_calls)
        except BudgetExceeded as e:
            return self._block(task, f"tester not run: {e}")
        except ValueError as e:
            return self._block(task, str(e), budget=False)
        self.event("test_plan", f"Input tester planned {len(plan.cases)} case(s): {plan.reasoning[:300]}",
                   agent_id=self.tester_id, task=task, model_call_id=plan_mc,
                   cases=[c.model_dump() for c in plan.cases])
        cases: list[TestCase] = []
        for pc in plan.cases[: lim.max_cases_per_form]:
            submit = self._submit_control(form, pc.submit)
            ref = pc.requirement_ref if pc.requirement_ref in self.req_ids else None
            tc = TestCase(run_id=self.run.id, form_id=form.id, handoff_id=handoff.id,
                          designed_by=self.tester_id, label=pc.label, inputs=pc.inputs, submit=submit,
                          requirement_ref=ref, expected=pc.expected, expectation_source=ref or "unspecified",
                          model_call_ids=[plan_mc])
            await self.execute_case(tc, form, handoff, task, state)
            cases.append(tc)
        self.summary["cases"] += len(cases)
        if not cases:
            task.status = "done"
            self.store.put(task)
            return []
        executed = [{"label": c.label, "inputs": c.inputs, "requirement_ref": c.requirement_ref,
                     "expected": c.expected, "status": c.status, "error": c.setup_error, "facts": c.observed}
                    for c in cases]
        try:
            assessment, assess_mc = await self.model(
                input_tester.assess_messages(handoff, form, executed), agent_id=self.tester_id,
                phase="input_test", task=task, parse=input_tester.parse_assessment,
                reserve=lim.reserved_verification_calls)
        except BudgetExceeded as e:
            return self._block(task, f"tester could not assess outcomes: {e}")
        except ValueError as e:
            return self._block(task, str(e), budget=False)
        findings = []
        for a in assessment.assessments:
            if not 1 <= a.case <= len(cases):
                continue
            tc = cases[a.case - 1]
            tc.tester_verdict, tc.tester_note = a.verdict, a.observed_summary  # type: ignore[assignment]
            tc.model_call_ids.append(assess_mc)
            self.store.put(tc)
            if a.verdict == "as_expected" or tc.status != "executed":
                continue
            findings.append(self._candidate(tc, form, handoff, state, a.verdict, a.observed_summary, assess_mc, task))
        task.status = "done"
        task.result_refs = [c.id for c in cases] + [f.id for f in findings]
        self.store.put(task)
        return findings

    def _block(self, task: Task, why: str, budget: bool = True) -> list[Finding]:
        task.status = "blocked"
        task.note = why
        self.store.put(task)
        self.budget_note = why if budget else (self.budget_note or f"{task.owner} task blocked: {why}")
        self.event("task_blocked", why, agent_id=task.owner, task=task)
        return []

    @staticmethod
    def _submit_control(form: DiscoveredForm, name: str | None) -> ControlRef | None:
        if name:
            hit = [c for c in form.submit_controls if c.name.casefold() == name.strip().casefold()]
            if hit:
                return hit[0]
            return ControlRef(role="button", name=name)  # resolution will fail explicitly if it is not there
        return form.submit_controls[0] if len(form.submit_controls) == 1 else None

    async def execute_case(self, tc: TestCase, form: DiscoveredForm, handoff: Handoff, task: Task,
                           state: ScreenState) -> None:
        """Run one case in a fresh context with its own workspace. Everything is recorded."""
        try:
            ctx = self.provider.provision(self.origin, f"{self.tester_id}:{tc.id}")
        except SetupError as e:
            tc.status, tc.setup_error = "setup_failed", str(e)
            self.store.put(tc)
            self.event("test_executed", f"Test case {tc.id} '{tc.label}': setup failed ({e})",
                       agent_id=self.tester_id, task=task, test_case_id=tc.id, status=tc.status)
            return
        tc.context_id = ctx.context_id
        att = _Attempt(self, self.tester_id, "input_test", ctx.context_id, task)
        async with self.engine(ctx.cookies) as eng:
            reached = await reach_state(eng, self.origin, handoff.setup, att.record)
            tc.setup_strategy = reached.strategy
            if not reached.ok:
                tc.status, tc.setup_error = "setup_failed", reached.error
            else:
                start_state, start_url = att.mark_state(reached.execution), reached.execution.observation.url
                steps = self._case_steps(tc, form)
                err, app_err, ex = await self._run_steps(eng, steps, att)
                if err or app_err or ex is None:
                    tc.status, tc.setup_error = "execution_failed", err or app_err or "no actions executed"
                else:
                    tc.status = "executed"
                if ex is not None:
                    tc.observed = outcome_facts(ex.observation, start_url)
                    end_state = att.mark_state(ex, recipe=[*handoff.setup.steps, *steps])
                    tc.resulting_state_id = end_state.id
                    last = att.results[-1]
                    self.store.put(Transition(
                        run_id=self.run.id, step=last.step, source_state_id=start_state.id,
                        target_state_id=end_state.id,
                        action={"type": "test_case", "test_case_id": tc.id, "inputs": tc.inputs,
                                "submit": tc.submit.name if tc.submit else None},
                        label=f"test: {_short_inputs(tc.inputs)}", action_result_id=last.id,
                        ok=tc.status == "executed", duration_ms=att.duration_ms,
                        screenshot_artifact_id=last.screenshot_artifact_id, model_call_id=tc.model_call_ids[0],
                        agent_id=self.tester_id, phase="input_test", context_id=ctx.context_id,
                        test_case_id=tc.id))
        tc.action_result_ids = [r.id for r in att.results]
        tc.evidence_refs = att.evidence
        self.store.put(tc)
        self.event("test_executed", f"Test case '{tc.label}' ({_short_inputs(tc.inputs)}): {tc.status}"
                   + (f" ({tc.setup_error})" if tc.setup_error else ""),
                   agent_id=self.tester_id, task=task, test_case_id=tc.id, status=tc.status,
                   context_id=ctx.context_id, resulting_state_id=tc.resulting_state_id,
                   evidence_refs=tc.evidence_refs[-2:])
        self.defer_frontier(att.new_states, self.tester_id, task)

    @staticmethod
    def _case_steps(tc: TestCase, form: DiscoveredForm) -> list[SemanticStep]:
        by_name = {f.control.name.casefold(): f.control for f in form.fields}
        steps = []
        for name, value in tc.inputs.items():
            ctrl = by_name.get(" ".join(name.split()).casefold()) or ControlRef(role="textbox", name=name)
            steps.append(SemanticStep(type="fill", control=ctrl, value=value))
        if tc.submit:
            steps.append(SemanticStep(type="click", control=tc.submit))
        return steps

    async def _run_steps(self, eng: BrowserEngine, steps: list[SemanticStep], att: _Attempt
                         ) -> tuple[str | None, str | None, Execution | None]:
        """(resolution error, application error, last execution). Each control is resolved fresh."""
        ex = None
        for step in steps:
            try:
                action, ex = await execute_step(eng, self.origin, step)
            except ControlResolutionError as e:
                return str(e), None, ex
            await att.record(action, ex, step.describe())
            if not ex.ok:
                return None, f"{step.describe()} failed: {ex.error}", ex
        return None, None, ex

    def _candidate(self, tc: TestCase, form: DiscoveredForm, handoff: Handoff, state: ScreenState,
                   verdict: str, observed: str, mc_id: str, task: Task) -> Finding:
        explicit = verdict == "unexpected" and tc.requirement_ref in self.req_ids
        req = self.req_ids.get(tc.requirement_ref or "")
        f = Finding(
            run_id=self.run.id, kind="defect_candidate" if explicit else "review_observation",
            reported_by=self.tester_id,
            description=f"{form.headings[0] if form.headings else form.route}: {tc.label}",
            expected=tc.expected, observed=observed, evidence_refs=list(tc.evidence_refs),
            requirement_ref=tc.requirement_ref, requirement_text=req.text if req else None,
            inputs=dict(tc.inputs), reproduction=handoff.setup, reproduction_steps=self._case_steps(tc, form),
            form_id=form.id, test_case_id=tc.id, handoff_ids=[handoff.id],
        )
        self.store.put(f)
        self.summary["candidates"] += 1
        label = "candidate defect" if explicit else "review observation (expectation not backed by a requirement)"
        self.event("candidate_reported", f"Input tester reports {label}: {f.description}",
                   agent_id=self.tester_id, task=task, finding_id=f.id, test_case_id=tc.id,
                   kind=f.kind, verdict=verdict, requirement_ref=f.requirement_ref, model_call_id=mc_id)
        return f

    # --- verifier ---------------------------------------------------------------

    def candidate_handoff(self, f: Finding, from_agent: str, task_id: str) -> Handoff:
        req = self.req_ids.get(f.requirement_ref or "")
        return Handoff(
            run_id=self.run.id, kind="candidate_to_verifier", from_agent=from_agent, to_agent=self.verifier_id,
            task_id=task_id, source_state_id=f.reproduction.target_state_id if f.reproduction else "",
            form_id=f.form_id, finding_id=f.id, setup=f.reproduction or SetupRecipe(target_state_id="", expected_signature=""),
            requirements=[req] if req else [],
            expected_behaviour=[Expectation(text=req.text, source=req.id)] if req
            else [Expectation(text=f.expected, source="none supplied")],
            evidence_refs=list(f.evidence_refs),
        )

    async def verify_finding(self, f: Finding, *, from_agent: str, fixed_assertion: Assertion | None = None,
                             task: Task | None = None, handoff: Handoff | None = None) -> None:
        lim = self.run.limits
        req = self.req_ids.get(f.requirement_ref or "")
        if task is None:
            task = self.new_task("verify", f"{self.run.id}:verify:{f.id}", self.verifier_id, [f.id])
        if handoff is None:
            handoff = self.candidate_handoff(f, from_agent, task.id)
            self.publish_handoff(handoff)
        handoff_art = handoff.evidence_refs[-1]
        if handoff.id not in f.handoff_ids:
            f.handoff_ids.append(handoff.id)
        attempts: list[VerificationAttempt] = []
        if req is None or f.kind != "defect_candidate":
            why = ("No supplied requirement states the expected behaviour" if req is None else
                   f"The tester could not judge the outcome against {req.id} (verdict unclear)")
            att = VerificationAttempt(
                run_id=self.run.id, finding_id=f.id, handoff_id=handoff.id, verifier_id=self.verifier_id,
                replay_index=0, target_origin=self.origin, failure_class="expectation", outcome="inconclusive",
                reason=f"{why}, so there is no explicit assertion to evaluate. Kept as a review observation.",
                evidence_refs=[handoff_art], finished_at=utcnow())
            self._record_attempt(att, task)
            attempts.append(att)
        else:
            assertion = fixed_assertion
            for i in range(lim.verification_replays):
                att = await self.replay(f, handoff, task, i, assertion)
                attempts.append(att)
                if att.failure_class in ("expectation", "verifier") and assertion is None:
                    break  # no valid assertion: further replays would have nothing to evaluate
                if assertion is None and att.assertion is not None and att.failure_class != "verifier":
                    assertion = att.assertion  # reuse the validated assertion for later replays
        self.accept(f, attempts, task)

    def _record_attempt(self, att: VerificationAttempt, task: Task) -> None:
        # Every attempt, including one that failed before a browser opened, gets an attempt log.
        log = self.ev.save_json("action_log", f"verification-{att.id}", att.model_dump(mode="json"))
        att.evidence_refs = [*att.evidence_refs, log.id]
        self.store.put(att)
        detail = (f"assertion {att.assertion.type.value} {'passed' if att.result.passed else 'failed'}"
                  if att.result and att.assertion else (att.failure_class or ""))
        self.event("verification_executed", f"Verification replay {att.replay_index + 1} of {att.finding_id}: "
                   f"{att.outcome} ({detail})", agent_id=self.verifier_id, task=task, verification_id=att.id,
                   finding_id=att.finding_id, outcome=att.outcome, failure_class=att.failure_class,
                   context_id=att.context_id, evidence_refs=att.evidence_refs[-2:])

    async def replay(self, f: Finding, handoff: Handoff, task: Task, idx: int,
                     assertion: Assertion | None) -> VerificationAttempt:
        att = VerificationAttempt(run_id=self.run.id, finding_id=f.id, handoff_id=handoff.id,
                                  verifier_id=self.verifier_id, replay_index=idx, target_origin=self.origin,
                                  outcome="inconclusive", reason="")

        def done(outcome: str, reason: str, failure: str | None = None) -> VerificationAttempt:
            att.outcome, att.reason, att.failure_class = outcome, reason, failure  # type: ignore[assignment]
            att.finished_at = utcnow()
            self._record_attempt(att, task)
            return att

        try:
            ctx = self.provider.provision(self.origin, f"{self.verifier_id}:{att.id}")
        except SetupError as e:
            att.setup_error = str(e)
            return done("inconclusive", f"Could not set up controlled test data: {e}", "setup")
        att.context_id = ctx.context_id
        rec = _Attempt(self, self.verifier_id, "verify", ctx.context_id, task)
        try:
            async with self.engine(ctx.cookies) as eng:
                reached = await reach_state(eng, self.origin, handoff.setup, rec.record)
                att.setup_strategy = reached.strategy
                att.evidence_refs = rec.evidence
                att.action_result_ids = [r.id for r in rec.results]
                if not reached.ok:
                    att.setup_error = reached.error
                    return done("inconclusive", f"Could not recreate the starting state: {reached.error}", "setup")
                att.setup_ok = True
                start_state, start_obs = rec.mark_state(reached.execution), reached.execution.observation
                if assertion is None:
                    try:
                        decision, mc_id = await self.model(
                            verifier.build_messages(f, start_obs), agent_id=self.verifier_id, phase="verify",
                            task=task, parse=verifier.parse_decision)
                    except BudgetExceeded as e:
                        self.budget_note = str(e)
                        return done("inconclusive", f"Verifier could not choose an assertion: {e}", "verifier")
                    except ValueError as e:
                        return done("inconclusive", str(e), "verifier")
                    att.model_call_id = mc_id
                    quote = " ".join(decision.requirement_quote.split()).casefold()
                    quote_ok = bool(quote) and quote in " ".join((f.requirement_text or "").split()).casefold()
                    if not decision.explicit or decision.assertion is None:
                        return done("inconclusive", f"Verifier judged that {f.requirement_ref} does not explicitly "
                                    f"state this behaviour: {decision.reasoning[:240]}", "expectation")
                    if not quote_ok:
                        return done("inconclusive", "The verifier's quoted requirement text was not found in "
                                    f"{f.requirement_ref}: {decision.requirement_quote[:120]!r}", "verifier")
                    if decision.requirement_ref != f.requirement_ref:
                        return done("inconclusive", f"Verifier cited {decision.requirement_ref}, not the candidate's "
                                    f"requirement {f.requirement_ref}", "verifier")
                    candidate = Assertion(type=decision.assertion.type, params=decision.assertion.params,
                                          requirement_ref=f.requirement_ref, expected=decision.expected,
                                          chosen_by=self.verifier_id)
                    try:
                        validate_assertion(candidate)
                    except AssertionInvalid as e:
                        att.assertion = candidate
                        return done("inconclusive", f"Assertion rejected by the engine: {e}", "verifier")
                    assertion = candidate
                    self.event("assertion_selected", f"Verifier selected {assertion.type.value} for "
                               f"{f.requirement_ref}: {decision.reasoning[:240]}", agent_id=self.verifier_id,
                               task=task, finding_id=f.id, model_call_id=mc_id, assertion=assertion.model_dump())
                att.assertion = assertion
                err, app_err, ex = await self._run_steps(eng, f.reproduction_steps, rec)
                att.evidence_refs = rec.evidence
                att.action_result_ids = [r.id for r in rec.results]
                if err:
                    att.setup_error = err
                    return done("inconclusive", f"Could not resolve a control in the fresh session: {err}", "setup")
                if app_err or ex is None:
                    return done("inconclusive", f"The application failed during the repeated actions: {app_err}",
                                "application")
                try:
                    result = evaluate(assertion, ex.observation, start_obs.url)
                except AssertionInvalid as e:
                    return done("inconclusive", f"Assertion rejected by the engine: {e}", "verifier")
                att.result = result
                last = rec.results[-1]
                self.store.put(Transition(
                    run_id=self.run.id, step=last.step, source_state_id=start_state.id,
                    target_state_id=rec.mark_state(ex, recipe=[*handoff.setup.steps, *f.reproduction_steps]).id,
                    action={"type": "verify_case", "finding_id": f.id, "inputs": f.inputs,
                            "assertion": assertion.type.value},
                    label=f"verify: {_short_inputs(f.inputs)}", action_result_id=last.id, ok=True,
                    duration_ms=rec.duration_ms, screenshot_artifact_id=last.screenshot_artifact_id,
                    model_call_id=att.model_call_id, agent_id=self.verifier_id, phase="verify",
                    context_id=ctx.context_id, verification_id=att.id))
                if result.passed:
                    return done("not_reproduced", f"Assertion {assertion.type.value} held: the page met "
                                f"{f.requirement_ref} in this fresh replay.")
                return done("confirmed", f"Assertion {assertion.type.value} failed: the page violated "
                            f"{f.requirement_ref} in this fresh replay.")
        finally:
            self.defer_frontier(rec.new_states, self.verifier_id, task)

    def accept(self, f: Finding, attempts: list[VerificationAttempt], task: Task) -> None:
        """Coordinator acceptance: provenance and evidence checks before the finding changes."""
        problems = []
        for a in attempts:
            if self.independent_verification and (not a.verifier_id.startswith("verifier")
                                                  or a.verifier_id == f.reported_by):
                problems.append(f"{a.id} was not produced by an independent verifier")
            if not a.evidence_refs:
                problems.append(f"{a.id} has no evidence")
            if a.outcome != "inconclusive" and (a.result is None or a.result.evaluated_by != "engine"):
                problems.append(f"{a.id} has no engine-evaluated assertion")
        if problems or not attempts:
            self.event("result_rejected", "Verification result rejected: " + "; ".join(problems or ["no attempts"]),
                       agent_id=COORDINATOR, task=task, finding_id=f.id)
            task.status = "failed"
            self.store.put(task)
            return
        outcomes = {a.outcome for a in attempts}
        if outcomes == {"confirmed"}:
            status, reason = VerificationStatus.confirmed, f"All {len(attempts)} fresh replays violated {f.requirement_ref}."
        elif outcomes == {"not_reproduced"}:
            status, reason = VerificationStatus.not_reproduced, (
                f"All {len(attempts)} fresh replays met {f.requirement_ref}; this does not prove there is no "
                "intermittent bug.")
        else:
            status = VerificationStatus.inconclusive
            reason = "; ".join(dict.fromkeys(a.reason for a in attempts if a.outcome == "inconclusive")) or (
                f"Replays disagreed ({', '.join(a.outcome for a in attempts)}).")
        f.verification_status = status
        f.verified_by = self.verifier_id
        f.verification_independence = "independent" if self.independent_verification else "self"
        f.verification_ids = [a.id for a in attempts]
        f.verification_reason = reason
        f = Finding.model_validate(f.model_dump())  # re-run the no-self-confirmation validator
        self.store.put(f)
        task.status = "done"
        task.result_refs = f.verification_ids
        self.store.put(task)
        self.summary["outcomes"].append(status.value)
        self.event("result_accepted", f"Accepted {status.value} for {f.id}: {reason}", agent_id=COORDINATOR,
                   task=task, finding_id=f.id, outcome=status.value, verification_ids=f.verification_ids)


class ReverifyRun(ReviewRun):
    """Browser-only re-check of an earlier finding against another build, reusing its assertion.

    No model call is made: the assertion chosen by the original verifier is
    replayed as-is, so the same executable check is compared across builds.
    """

    def __init__(self, run: Run, store, settings, llm, source: Finding, assertion: Assertion):
        super().__init__(run, store, settings, llm)
        self.source, self.fixed = source, assertion

    async def execute(self) -> None:
        run = self.run
        run.status = RunStatus.running
        self._save_run()
        self.event("run_started", f"Re-check of {self.source.id} from run {self.source.run_id} on {self.origin} "
                   "(browser only, reused assertion, no model call)", agent_id=COORDINATOR)
        self.task.status = "done"
        self.store.put(self.task)
        try:
            copy = self.source.model_copy(update={
                "id": new_id("fnd"), "run_id": run.id,
                "source_finding_id": self.source.id, "verification_status": VerificationStatus.unverified,
                "verified_by": None, "verification_ids": [], "verification_reason": None, "handoff_ids": [],
                "description": f"Re-check of {self.source.id}: {self.source.description}",
            })
            copy = Finding.model_validate(copy.model_dump())
            self.store.put(copy)
            await self.verify_finding(copy, from_agent=COORDINATOR, fixed_assertion=self.fixed)
            final = self.store.get(Finding, copy.id)
            status, reason = RunStatus.completed, f"re-check finished: {final.verification_status.value}"
        except Exception as e:  # recorded, never hidden
            self.event("run_error", f"{type(e).__name__}: {e}", agent_id=COORDINATOR)
            status, reason = RunStatus.failed, f"{type(e).__name__}: {e}"
        self._stop(status, reason)
