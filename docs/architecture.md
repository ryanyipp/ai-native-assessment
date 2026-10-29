# Architecture notes (checkpoint 2)

These notes describe what is implemented. `docs/plan.md` remains the agreed plan.

## Workers and boundaries

| Worker | Code | Receives | Produces | Cannot |
|---|---|---|---|---|
| Coordinator (code) | `orchestration/review.py` `ReviewRun` | Run config, records | Tasks, handoffs, acceptance events | Run a model |
| Explorer A | `agents/explorer.py` | Goal, supplied requirements, compact observation, own history | Browser actions, states, transitions, finish summary | Confirm anything (contract validator) |
| Input tester | `agents/input_tester.py` | One `form_to_tester` handoff + requirements | Planned cases, then verdicts on code-recorded facts | Set a verification status |
| Verifier | `agents/verifier.py` | Requirement, inputs, steps, its own fresh observation of the start page | Explicit/not-explicit judgement, requirement quote, one typed assertion | See the tester's verdict or observed outcome; decide the outcome |

No runtime agent receives the fixture mode, its source, the defect list or evaluation answers. Prompts contain only page observations, supplied requirements and handoff fields.

## Sequential flow (checkpoint 2)

1. **Explore.** Explorer A acts as in checkpoint 1. After every successful action, code groups the observed controls by enclosing `<form>` and records a `DiscoveredForm` (event `form_discovered`). The dedup key is the set of field role, name and type; the route is excluded, so create and edit pages with the same fields count once.
2. **Hand off to the tester.** For each form (up to `max_forms_tested`), the coordinator creates an `input_test` task and a `Handoff` of kind `form_to_tester`. It contains:
   - the source state and evidence refs;
   - the form;
   - a `SetupRecipe`: a direct path plus a semantic step recipe, and the expected state signature;
   - every supplied requirement with an id;
   - one `Expectation` per requirement, with its source.

   The handoff JSON is stored as an artifact (event `handoff_created`).
3. **Test.** The tester plans up to `max_cases_per_form` cases. Each case runs in a **new browser context with a newly provisioned fixture workspace**:
   - Code reaches the start state, either by the direct path or by the recipe, and requires a signature match.
   - Each field and the submit control are resolved by role and name against the fresh observation.
   - Code records outcome facts: URLs, headings, status and alert messages, invalid fields, and text.

   Event `test_executed`. A second tester call judges each case from those facts.
4. **Candidates.** An `unexpected` verdict that cites a supplied requirement becomes a `defect_candidate`. Anything else that isn't `as_expected` becomes a `review_observation` (event `candidate_reported`). Each records:
   - the requirement;
   - the inputs;
   - the reproduction recipe and steps;
   - the tester's evidence.
5. **Hand off to the verifier.** Kind `candidate_to_verifier`, with the requirement and expected behaviour.
   - **Review observations** are recorded as `inconclusive`, failure class `expectation`, with no replay.
   - **Candidates** get a fresh context and workspace for each replay (`verification_replays`, default 2):
     - Code reaches the start state.
     - On the first replay, the verifier sees its own fresh observation and either declines (not explicit) or quotes the requirement and selects an assertion. Code checks that the quote appears in the requirement text and validates the typed params.
     - Code repeats the steps and evaluates the assertion (event `verification_executed`).
6. **Accept.** The coordinator accepts only attempts:
   - made by a `verifier*` worker other than the reporter;
   - that have evidence;
   - where every non-inconclusive outcome has an engine-evaluated result.

   Only then is the finding updated (event `result_accepted`; otherwise `result_rejected`).

   | Replay outcomes | Finding status |
   |---|---|
   | All confirmed | `confirmed` |
   | All not reproduced | `not_reproduced` |
   | Anything else | `inconclusive`, with the reasons |

   New states reached by testing or verification are recorded as `deferred` explore tasks (event `frontier_deferred`) for the checkpoint 3 queue.

`ReverifyRun` replays an earlier finding's recipe **with its recorded assertion** against another build. It makes no model call, so one executable check can be compared across the broken and corrected builds.

## Assertions

`verification/assertions.py` holds the v1 vocabulary:
- `element_visible`
- `validation_message_present`
- `navigation_reached`
- `text_or_value_retained`
- `state_condition`

Each type has a pydantic params model with `extra="forbid"`, and evaluation is plain Python over the recorded `Observation`. An assertion states what the page shows **when the requirement is met**: `passed=False` means a violation in that replay. Status messages (`role=status`) do not count as validation; alerts (`role=alert`) and user-invalid fields do. A field-scoped validation check also accepts a page alert that names the field.

## Identity and replay

- `ObservedElement.id` (e1, e2 …) is valid only in its own observation. Recipes store `SemanticStep`s with a `ControlRef` (role, accessible name, input type). `resolve_control` raises on zero or several matches; a replay that cannot resolve is a setup failure, never a guess.
- Navigation steps store a path relative to the target origin, so a recipe can be replayed against another build.
- States are merged by signature within a run, and each merge appends a `StateSighting` (agent, phase, context). Different runs are never merged, so builds and modes stay separate. Fresh tester and verifier sessions add only their start and outcome states; intermediate steps remain actions with evidence.

## Data isolation

A fresh browser does not isolate server records. `services/test_data.py` calls the target's harness endpoint (`FLOWLENS_WORKSPACE_ENDPOINT`, POST) before each tester or verifier execution and sets the returned workspace cookie on the new context. The context id (`<agent>:<record id>:<workspace>`) is stored on every action, state sighting, transition, test case and verification attempt. If provisioning fails, the result is `inconclusive` with failure class `setup`.

## Budget

All workers call the model through `ExplorerRun.call_model`, which is checked against **one** run budget (calls, run cost and the overall pool) and recorded with `agent_id` and `phase`.

- **Reserved calls:** the explorer leaves `reserved_verification_calls` plus 2 tester calls unused; the tester leaves the verification reserve.
- **Output caps:** tester and verifier calls use `max_output_tokens_planning` (default 2000), because hidden reasoning shares the output cap.
- **Exhausted budget:** if verification runs out of budget, the result is inconclusive and the run is `partial`.

## Ready for later checkpoints

`Task` already has `owner`, `attempt_id`, `lease_expires_at` and `depends_on`, and every record carries agent and context ids. Handoffs are standalone records. Adding the shared queue, leases, the second explorer and stale-result rejection replaces the sequential loop in `ReviewRun.after_explore` without changing the record shapes.

# Checkpoint 3: shared queue (`queue_review` mode)

The sequential `explore_test_verify` mode above is unchanged and stays selectable for regression checks.

## Queue (`storage/queue.py`)

Tasks live in the SQLite `tasks` table. Every operation runs in one `BEGIN IMMEDIATE` transaction:

| Operation | Behaviour |
|---|---|
| `enqueue` | Deduplicated by `(run_id, key)`, checked inside the transaction and backed by a unique expression index. Returns the existing task if the key is taken. |
| `claim(worker, types)` | Picks the highest-priority `ready` task of those types whose `depends_on` tasks are all `done`. Sets owner, a new `attempt_id`, `attempts += 1`, `claimed_at` and `lease_expires_at`. Ready tasks whose dependency ended failed, blocked or unfinished become `blocked`. |
| `complete` / `fail` | Accepted only if owner and attempt are still current (`StaleAttempt` otherwise). `fail` puts the task back to `ready` until `max_attempts` claims are used, then marks it `failed`. |
| `mark_unfinished` | At the end of a run, every task that never ran becomes `unfinished`, with the reason. |

Leases are recorded but not yet enforced. Expiry, reassignment and stale-result rejection under an injected stall are checkpoint 4.

## Workers (`orchestration/queue_review.py`)

Four coroutines share one event loop: `explorer-a`, `explorer-b` (type `explore`), `input-tester` (`input_test`) and `verifier` (`verify`).

| Task | Queued by | Work | Produces |
|---|---|---|---|
| `explore:start` | coordinator | Open the target in a fresh context and workspace | States, transitions, forms |
| `explore:<signature>` | whichever worker first recorded the state | Reach the state by direct path or semantic recipe (signature must match), then up to `explore_steps_per_task` model-chosen actions. The prompt lists states the team already has. | New states (depth + 1, up to `max_depth`; deeper ones are recorded `unfinished`), forms |
| `input_test:<form key>` | the explorer that saw the form | The checkpoint 2 tester on the stored `form_to_tester` handoff | Test cases; outcome states queued as explore tasks; candidates |
| `verify:<finding>` | input-tester; `depends_on` the test task | The checkpoint 2 verifier on the stored `candidate_to_verifier` handoff | Verification attempts and the accepted result |

- **Shared discoveries:** every worker records into one signature-keyed state map. A merge appends a sighting (agent, phase, context), so provenance is kept.
- **Isolation:** each task, test case and replay gets its own browser context and a newly provisioned fixture workspace. A state found by one explorer is reproduced by another through the stored recipe, not through shared server data.
- **Budget:**
  - One run budget is shared by every worker.
  - Explorers stop when total calls reach `max_model_calls − reserved_testing_calls − reserved_verification_calls`; the tester leaves the verification reserve.
  - The check happens before each call, so concurrent workers can overshoot by one call (seen live: 20/19).
- **Termination:** a worker exits when no task it can claim is ready, no task is in progress, and nothing in progress could produce more. It also exits when the time limit is hit or the explorer budget share is used. The run is `partial` if anything is unfinished, blocked or failed, or if a budget limit was hit.

# Checkpoint 4: leases, fencing and recovery

- **Renewal.** Every browser-context launch, browser action and model call by a queue worker first calls `check_attempt`. A revoked attempt is refused (`late_action_rejected`); otherwise the lease is renewed for `task_lease_s`.
- **Expiry.** A watchdog coroutine calls `TaskQueue.expire_overdue` every 0.25 s. This is atomic: an expiry and a completion racing on the same attempt have exactly one winner.
  - **Who may retry:** the expired owner is excluded from the task when another live worker of that type exists. Otherwise the same worker retries with a fresh attempt, so single-worker types are not stranded.
  - **Fencing hold:** the task is held (`fencing`) until the coordinator has closed every browser context opened by the expired attempt (`context_fenced`). Only then is it released (`task_reassigned`).
  - **Last attempt:** expiry on the final attempt marks the task `failed`.
- **Late results.** When the expired worker resumes, its next action or model call is refused. The worker still submits its result, and the queue rejects it because the attempt is no longer current (`result_rejected`). When a reassigned task completes, `task_recovered` records the expired attempts and the recovering worker. Records the expired attempt wrote *before* expiry stay, labelled with its task and context id.
- **Fault injection.** `fault_injection` on `POST /api/runs` (queue_review only) stalls a chosen worker after a claim, while it holds an open browser context. Such runs carry `provenance.injected_failure = true`, and the events are prefixed `[INJECTED FAULT]`. Setup step: the other explorers wait up to 15 s for the faulty worker's first claim, so the stall lands on real work. Everything after the stall (diagnosis, fencing, reassignment, rejection, recovery) is the normal coordinator path.

## Budget reservation

`reserve_call` checks and takes capacity in one synchronous step: no `await` between check and increment, and in-flight calls count as used. Usage keeps per-phase counters (`exploration_calls`, `testing_calls`, `verification_calls`).

| Worker | Limits |
|---|---|
| Explorers | Their own count ≤ `max_model_calls − reserved_testing_calls − reserved_verification_calls`, and the total ≤ `max − reserved_verification_calls` |
| Tester | Total ≤ `max − reserved_verification_calls` |
| Verifier | Total ≤ `max` |

Cost is still checked before each call from provider-reported totals; one call's cost can overshoot the cost limit.

## Planning outputs

Tester and verifier calls send `reasoning: {max_tokens: planning_reasoning_tokens (384), exclude: true}` with `max_output_tokens_planning` 1400. Plans have at most 3 cases and shorter fields. The provider's `finish_reason` and reasoning-token count are stored per call, and `Usage.truncated_calls` counts cut-off replies.
