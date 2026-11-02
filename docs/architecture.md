# Architecture

This is a reference for the current code. Module paths are relative to `backend/src/flowlens/`. How the design got here is in [development-log.md](development-log.md); the original plan is in [plan.md](plan.md).

## 1. Default workflow and module map

The launcher starts a **shared-queue review** (`queue_review`) by default. One backend process runs each review in its own thread and asyncio event loop. Four workers claim tasks from a queue that Python code manages; models choose browser actions, test inputs and assertions, and code executes, records, evaluates and accepts.

```text
launcher / POST /api/runs
        │
        ▼
QueueReviewRun (coordinator, no model)  ── SQLite: runs, tasks, states, findings, events …
        │ enqueues explore:start
        ▼
 explorer-a ─┐                    input_test task              verify task
 explorer-b ─┴─ explore tasks ──► (form handoff) ──► input-tester ──► (candidate handoff) ──► verifier
        ▲                                                │                                     │
        └──────────── new states become explore tasks ───┴─────────────────────────────────────┘
```

| Area | Module | Role |
|---|---|---|
| API | `api/runs.py`, `main.py` | Runs, cancel, preview, origin approval, artifacts, reports. Marks unfinished runs `interrupted` at startup. |
| Launch | `orchestration/launch.py` | Picks the run class by mode, starts the run thread, refuses to start from stale code. |
| Coordinator | `orchestration/queue_review.py` | `QueueReviewRun`: workers, leases, watchdog, frontier rules, explorer tasks. |
| Tester and verifier steps | `orchestration/review.py` | `ReviewRun`, which `QueueReviewRun` extends: handoffs, case execution, replays, acceptance. |
| Shared recording | `orchestration/runner.py` | `ExplorerRun`, the base class: recording actions and states, form discovery, budgets, cancellation. |
| Exploration memory | `orchestration/coverage.py` | `Coverage`: what was followed, what is open, short-lived claims. |
| Setup replay | `orchestration/replay.py` | `reach_state`: direct path, then semantic recipe, then a signature check. |
| Queue | `storage/queue.py` | `TaskQueue` on SQLite: atomic enqueue, claim, renew, expire, complete. |
| Store | `storage/db.py` | SQLite source of truth; each record is validated JSON. |
| Contracts | `models/contracts.py` | Pydantic models, mirrored in `frontend/src/lib/types.ts`. |
| Agents | `agents/explorer.py`, `agents/input_tester.py`, `agents/verifier.py` | Prompts and strict reply parsing. No browser or database access. |
| Browser | `browser/engine.py` | Playwright execution of typed actions, observations, signatures, origin scope. |
| Test data | `services/test_data.py` | Fixture workspaces or plain fresh contexts. |
| Assertions | `verification/assertions.py` | Typed assertion vocabulary, evaluated by code. |
| Model | `services/llm.py` | The only place a model is called (OpenRouter, server side). |
| Reports | `services/report.py` | HTML and Markdown from saved records, no model. |

## 2. Workers

| Worker | Agent id | Claims | Model decides | Code decides |
|---|---|---|---|---|
| Explorer A | `explorer-a` | `explore` | Next action on the claimed page, or finish | Execution, recording, form discovery, refusal of repeats and form use |
| Explorer B | `explorer-b` | `explore` | Same | Same |
| Input tester | `input-tester` | `input_test` | Case plan; then a verdict per completed case | Browser steps per control type, execution, outcome facts |
| Verifier | `verifier` | `verify` | Applicability, explicitness, requirement quote, one assertion | Replays, assertion evaluation, outcome |

Explorer A and B run the same code (`QueueReviewRun.explore_task` and `agents/explorer.py`). They differ only in their worker identity, which appears in prompts, records and claims, and in the tasks each one claims. The prompt tells each one which states the team has already recorded, and the exploration memory steers them to different open controls (section 6).

Agents see page observations, supplied requirements and handoff fields. They never see the fixture mode, its source, the defect list or evaluation answers. The verifier does not see the tester's verdict or observed outcome.

## 3. Coordinator and queue

`QueueReviewRun.execute` enqueues `explore:start` and runs four worker coroutines plus a watchdog. Each worker loops: claim a task of its type, run it, complete it.

`storage/queue.py` runs every operation in one `BEGIN IMMEDIATE` transaction:

| Operation | Behaviour |
|---|---|
| `enqueue` | Deduplicated by `(run_id, key)` with a unique index. |
| `claim` | Takes the highest-priority `ready` task of the worker's types whose dependencies are `done`; sets owner, a new `attempt_id` and a lease. Tasks whose dependency ended badly become `blocked`. |
| `renew` | Extends the current attempt's lease. |
| `complete`, `fail`, `update` | Accepted only from the current owner and attempt (`StaleAttempt` otherwise). `fail` retries until `task_max_attempts` claims are used. |
| `expire_overdue` | Revokes attempts past their lease (section 9). |
| `mark_unfinished` | At the end, every task that never ran becomes `unfinished`, with the reason. |

A worker exits when nothing it could claim is ready or could become ready, when the time limit is hit, or (explorers only) when the explorer call share is used. The run is `completed` only if no task is unfinished, blocked or failed and no limit was hit; otherwise it is `partial`. `cancelled`, `failed` (a coordinator error) and `interrupted` are separate statuses.

## 4. Handoffs and task flow

| Task | Queued by | Payload | Produces |
|---|---|---|---|
| `explore:start` | coordinator | none | States, transitions, forms |
| `explore:<signature>` | the worker that first recorded the state | `state_id` | More states and forms |
| `input_test:<form key>` | the explorer that saw the form | form and `form_to_tester` handoff | Test cases, candidate findings |
| `verify:<finding>` | input tester; depends on the test task | finding and `candidate_to_verifier` handoff | Verification attempts, accepted status |

A **handoff** is a stored record, also saved as a JSON artifact (event `handoff_created`). It contains the source state, the form or finding, a `SetupRecipe` (direct path, semantic steps and expected state signature), the supplied requirements with ids, one expectation per requirement, and evidence references.

**New states.** States reached by any worker become `explore` tasks, except:

- a variation of an explored page with the same structure (only field fill state differs);
- the outcome of an already-tested form with the same layout (its messages stay in the test-case record);
- a page on an explored route whose destinations are a subset of that page's (only listed data or a status banner differs);
- states deeper than `max_depth`, which are recorded as `unfinished`.

Skipped states stay on the map; only the extra task is not run.

## 5. Browser contexts, workspaces and setup replay

Every explore task, test case and verification replay opens a **new browser context**. On fixture targets, `services/test_data.py` first asks the fixture for a new **test-data workspace** (`POST` to `FLOWLENS_WORKSPACE_ENDPOINT`, default `/__fixture/workspaces`) and sets it as a cookie, so server-side records are separate too. Approved public websites get a fresh context only; their server data is shared. If provisioning fails, the result is inconclusive with failure class `setup`.

The context id (`<agent>:<record id>:<workspace>`) is stored on every action, state sighting, transition, test case and verification attempt.

**Setup replay.** A worker reaches its start state with `orchestration/replay.py`: open the direct path; if the reached state's signature differs, replay the semantic recipe from the start; succeed only on a signature match. A record created by filling a form exists only in the workspace that created it, so such states skip the direct path and replay the recipe. Recipes store `SemanticStep`s with a `ControlRef` (role, accessible name, input type), never element ids; each control is resolved fresh, with a short wait, and zero or several matches is an explicit failure.

States are merged by signature within a run, and each merge adds a sighting (agent, phase, context). Different runs are never merged.

## 6. Exploration memory and reservations

`orchestration/coverage.py` keeps one `Coverage` record per run, shared by both explorers:

- **Followed and open controls.** A link is identified by its destination, so one page reached by two labels counts once. Links to one id-based route form a record group; a couple of records are sampled while samples keep showing new controls, and the rest stay listed as unvisited.
- **Reservations.** Before each planning call, an explorer is assigned an open control that the other is not working on. The reservation lasts at most 120 s and is released when the task ends, so a stalled explorer cannot hold work.
- **Refusals.** Code refuses an action that repeats followed work or would fill or submit a recorded form (the input tester owns forms), and tells the model why. Refused actions are not executed.
- **No-progress stop.** Only a new control or page structure counts as progress. A task stops after 3 steps without progress, after 2 refused choices, or when nothing open is reachable.

Reservations are not leases. A **reservation** steers which control an explorer is asked about, lives in memory and is advisory. A **lease** (section 9) is the queue's ownership of a task and decides whose results are accepted.

## 7. Test execution, execution failures and applicability

**Plan.** The tester gets the form and requirements and returns up to `max_cases_per_form` cases (default 3). Each case gives exact inputs, a submit control, an optional requirement id, the control that requirement governs, an expected result and an optional check page. If the named control is not used by the case, the case is not requirement-backed.

**Execution** (`ReviewRun.execute_case`), per case in its own context and workspace:

- Code chooses the browser step from the observed control: `fill` for text-like inputs, `select` with an observed option for dropdowns, `check` with a boolean for checkboxes and switches.
- Radio buttons, file inputs, an unknown option, an unclear boolean or a missing submit control make the case `execution_failed` before the form is touched.
- With a check page, code observes it in a second tab before and after the submit.
- Code records outcome facts: URLs, headings, status and alert messages, invalid fields and text.

**Execution failures.** A case that did not complete keeps its actions and screenshots, gets no tester verdict, creates no finding and does not count as tested. A setup failure is `setup_failed`.

**Assessment.** A second tester call judges completed cases from the recorded facts. `unexpected` with a supplied requirement becomes a `defect_candidate`; any other non-`as_expected` verdict becomes a `review_observation`.

**Applicability.** On the first replay the verifier sees the requirement, inputs, the controls the test used, the form and its own fresh observation of the start page. It must say whether the requirement applies and name the control. `not_applicable`, `ambiguous`, a missing judgement, a named control the test did not use, or no reason gives `inconclusive` with failure class `applicability`, and no assertion is run. Code checks the shape of this judgement only, not whether it is right.

## 8. Assertions, replays and acceptance

**Vocabulary** (`verification/assertions.py`): `element_visible`, `validation_message_present`, `navigation_reached`, `text_or_value_retained`, `state_condition`. Each has a params model that forbids extra fields, and evaluation is plain Python over the recorded observation. An assertion states what the page shows when the requirement is met, so `passed=False` is a violation. Status messages do not count as validation; alerts and invalid fields do, and a field-scoped check also accepts a page alert naming the field.

**Replays** (`ReviewRun.replay`), `verification_replays` times (default 2), each in a fresh context and workspace:

1. Code reaches the start state.
2. On the first replay only, the verifier judges applicability and explicitness, quotes the requirement and chooses an assertion. Code checks that the quote is in the requirement, that it cites the candidate's requirement, and that the params validate. Later replays reuse that assertion.
3. Code repeats the recorded steps and evaluates the assertion, on the check page if the case has one.

Each attempt ends `confirmed` (assertion failed), `not_reproduced` (held) or `inconclusive` with a failure class: `setup`, `execution` (a browser action did not complete), `expectation`, `applicability` or `verifier`. Review observations get one `inconclusive` attempt with no replay.

**Acceptance** (`ReviewRun.accept`). Before the finding changes, the coordinator checks that every attempt came from a `verifier*` worker other than the reporter, has evidence, and that every non-inconclusive outcome has an engine-evaluated result. Then: all `confirmed` gives `confirmed`, all `not_reproduced` gives `not_reproduced`, anything else gives `inconclusive` with the reasons. All three stay visible.

## 9. Budgets, leases, cancellation, recovery and reporting

**Model budget.** Every call goes through `ExplorerRun.call_model` against one run budget: calls, run cost and the installation's credit pool. At most `FLOWLENS_MAX_CONCURRENT_MODEL_CALLS` (2) run at once. Capacity is taken in one synchronous step, and calls in flight count as used.

| Worker | Limit |
|---|---|
| Explorers | Their calls ≤ `max_model_calls − reserved_testing_calls − reserved_verification_calls`; total ≤ `max − reserved_verification_calls` |
| Input tester | Holds 2 calls (plan and assessment) when it starts a form, or the task is `unfinished`; total ≤ `max − reserved_verification_calls` |
| Verifier | Total ≤ `max_model_calls` |

Tester and verifier calls use `max_output_tokens_planning` (1400). An invalid reply is repaired once; a truncated one is retried with minimal reasoning or a larger cap. Cost is checked before each call from provider-reported totals, so one call can overshoot. Hitting a limit makes the run `partial`.

**Limits by mode.**

| Limit | Shared queue | Single agent, sequential, explorer only |
|---|---|---|
| `max_model_calls`, `max_cost_usd`, credit pool | Enforced | Enforced |
| `explore_steps_per_task` (4), `max_depth` (2), `max_tasks` (40), `task_max_attempts` (2), `task_lease_s` (300) | Enforced | Not used |
| `max_steps`, `max_states`, `max_forms_tested` | Not used | Enforced |
| `max_cases_per_form`, `verification_replays` | Enforced | Single agent and sequential |
| `max_duration_s` | Soft: checked before claims and between steps | Soft, during exploration |

The launcher sends cost (US$0.50), model calls (60), output tokens, steps and depth; every other limit takes the `RunLimits` default shown above. A request with no limits at all uses the `FLOWLENS_*` settings (40 calls).

**Leases.** Every browser-context launch, browser action and model call by a queue worker first calls `check_attempt`, which refuses a revoked attempt (`late_action_rejected`) or renews the lease. A heartbeat renews it during a model call, up to the call deadline. The watchdog runs every 0.25 s:

1. `expire_overdue` revokes the attempt atomically; an expiry and a completion racing on it have exactly one winner.
2. The coordinator closes every browser context the attempt opened (`context_fenced`).
3. The task returns to the queue (`task_reassigned`), excluding the expired worker if another worker of that type exists; on the last attempt it is `failed`.

A worker that resumes after expiry is refused on its next action, and its result is rejected (`result_rejected`). Tester and verifier writes go through the queue and `guard_publish`, with no `await` between the check and the write. Records the attempt wrote before expiry stay, labelled with its task and context.

**Fault injection.** `fault_injection` on `POST /api/runs` (queue mode only) stalls a chosen worker after a claim while it holds an open context. The launcher's checkbox stalls `explorer-a` for 75 s; the API also accepts other workers and task types. Such runs carry `provenance.injected_failure` and `[INJECTED FAULT]` events.

**Cancellation.** `POST /api/runs/{id}/cancel` and **Cancel run** block new claims, model calls and browser actions. A call in flight is abandoned within about 0.25 s, a running browser action finishes and is recorded, unrun tasks become `unfinished`, and the run ends `cancelled`. The provider may still bill a request it received. Cancellation reaches only runs executing in the current process.

**Recovery scope.** Leases, fencing and reassignment work inside one backend process. If the process stops, the next start marks any `queued` or `running` run `interrupted`, keeping its evidence; it is not resumed. A run is also refused if the backend source changed on disk after the process started.

**Live updates.** The frontend polls `GET /api/runs/{id}` every 1.5 s while a run is active. There is no SSE route.

**Reports.** `services/report.py` builds the report from saved records with no model call: `GET /api/runs/{id}/report` (HTML) and `/report.md`. A finished run is described as finished, never as passed, and incomplete work is listed.

## 10. Alternative modes and limitations

| Mode | Class | Started from | What it is |
|---|---|---|---|
| `queue_review` | `QueueReviewRun` | Launcher (default), API | Shared queue, described above |
| `single_agent` | `SingleAgentRun` | Launcher, API | Evaluation baseline: one agent identity and continuing context explores, tests and chooses assertions for its own findings. Same budgets, fresh contexts per case and replay, and code evaluation; findings are marked self-checked. |
| `explore_test_verify` | `ReviewRun` | API only | Sequential: one explorer, then the tester and verifier in turn. Testing and verification states are recorded as `deferred`, not explored. |
| `single_explorer` | `ExplorerRun` | API only (the API default when `mode` is omitted) | Exploration only. On finishing, the explorer's persistence claim and a same-session check are stored as a `persistence_check` finding, shown as an unverified explorer observation. |
| `reverify` | `ReverifyRun` | Scripts only (`scripts/checkpoint2_eval.py`, `scripts/supported_check.py`) | Replays an earlier finding's recipe and recorded assertion against another build with no model call. The API rejects it as a mode. |

When a queue explorer finishes, its summary is stored as an `explorer_observation` event. These notes appear in the Findings tab and report as unverified, create no finding and are never sent to the verifier.

**Limitations.** Applicability and assertion choice are model judgements. Radio and file controls are not supported. Exploration is bounded and can still repeat navigation (seen on Leave Desk). Recovery does not survive a backend restart. Fresh contexts do not isolate a public website's server data. The README lists these for users.

## Older records

Records from earlier code still load and display. Differences to expect:

- Failed replay actions in older records have failure class `application`; current code uses `execution`.
- Runs before explorer observations show none.
- Single-agent explore transitions in older runs read `explorer-a` / `explorer-a:default`.
- `planning_reasoning_tokens` is kept in limits only so old records validate.
- Imported demo runs keep their recorded cost but do not count toward the local credit pool.
