# FlowLens Product and Development Plan

Working specification • Version 1 • 29 October 2026

> Converted from `FlowLens_Product_and_Development_Plan.docx`. This is the agreed build plan. It describes proposed features, performance, costs and results. It does not claim any of them are implemented. Update this file when implementation evidence changes a decision.

FlowLens is an AI website reviewer for team leads, product managers, and QA reviewers. It explores an authorised staging website, builds a map of observed user journeys, tests interactions, and presents findings with reproducible evidence. A small review assistant answers questions from the saved run.

This document consolidates the agreed product, multi-agent workflow, implementation boundaries, evaluation approach, and development checkpoints.

## Product promise

Give FlowLens a staging URL and expected behaviours. Receive an interactive map showing what was discovered, what was tested, what failed, and what remains unknown.

## Primary user journey

Create a review run → observe exploration → inspect the website map → open a finding and its evidence → ask a follow-up question → export a concise review.

## Core deliverables

- Interactive map of observed screens, meaningful UI states, and transitions.
- Input tests and independently verified findings with screenshots and action records.
- Separate agent timeline showing assignments, handoffs, retries, and recovery.
- Summary of tested, blocked, and unexplored work, plus a Markdown report.
- Evidence-linked review chat once the complete testing workflow is stable.

## Scope and honest limits

Initial scope is Chromium, one user role, bounded exploration, and a supplied test session where authentication is needed. Begin with one controlled creator-dashboard fixture; add a small independent second application if time permits. The map describes observed UI behaviour, not backend architecture. No exhaustive coverage, automatic code repair, production load testing, or real TikTok integration is promised.

## Build and review roles

Ryan owns product choices, local execution, and final acceptance. Claude implements and tests in incremental commits. GPT prepares bounded implementation prompts and reviews shared code, artifacts, and results. Claude coding subagents are development assistants; they are separate from the agents running inside FlowLens.

---

# Multi-agent responsibilities

The product has four testing workers: two explorer instances, one input tester, and one verifier. An on-demand reporter and review assistant uses the completed records. All roles initially share one model, with separate instructions, context, and permissions. Limit simultaneous model calls to two during early development.

| Component | Input and responsibility | Output and boundary |
|---|---|---|
| Coordinator code | Run configuration, queue, budgets and task ownership | Assigns tasks and accepts validated results; no LLM supervisor required. |
| Explorer A and B | Claimed frontier item and route to its starting state | States, transitions, forms, candidate issues; cannot confirm its own defect. |
| Input tester | Discovered form and relevant requirements | Input cases, observed outcomes and candidate findings; new states return to exploration. |
| Verifier | Candidate finding, expected outcome and setup recipe | Confirmed, not reproduced or inconclusive result; supplies replay evidence. |
| Reporter and chat | Accepted run records and evidence references | Summary and cited answers; cannot invent observations or launch new tests in version one. |

## Why collaboration matters

Workers share discovered work rather than running independent scripts and concatenating reports. An explorer hands a form to the tester; a test exposes a new state; another explorer investigates that state; a verifier independently checks the suspected failure. Benefits must be measured against a single-agent baseline, not assumed.

## AI and deterministic responsibilities

LLMs decide where to investigate, choose useful input variations, interpret requirements, and propose assertions using a bounded schema. Code owns browser execution, task claims, budgets, state records, assertion evaluation, and evidence storage. LLM prose alone cannot create a confirmed finding.

## Browser and data isolation

Each worker gets a separate browser context. A verifier starts from a fresh context and recreates the documented setup. Browser isolation does not isolate server records: the reference app provides worker-specific accounts or namespaces and resettable fixtures. Operations involving shared global data must be serialised or explicitly controlled.

## Practical starting point

Implement one explorer first. Add the tester and verifier after the browser-to-map vertical slice works. Add the second explorer only when task ownership and state replay have meaningful tests. This avoids debugging concurrency and basic browser execution at the same time.

---

# Shared workflow and artifact handoffs

## Execution sequence

1. **Create the run.** Record target origin, supplied requirements, test session reference, model, limits, and run mode. Seed the starting exploration task.
2. **Claim work.** The coordinator atomically assigns a ready task to a worker with an attempt identifier and lease expiry.
3. **Restore context.** The worker opens its browser context and executes the setup and navigation recipe. If it cannot reach the target state, record a blocked task rather than fabricating results.
4. **Observe and act.** The model receives a compact page observation and proposes an allowed browser command. The engine validates and executes it, records the outcome, and captures evidence.
5. **Publish a handoff.** The worker returns structured observations and references to artifacts. The coordinator verifies current ownership before accepting the result and enqueuing follow-up work.
6. **Test and verify.** Discovered forms become input-test tasks. Candidate defects become independent verification tasks. Newly discovered states return to the exploration frontier.
7. **Update the review.** Accepted transitions update the website map; events update the agent timeline. A finding keeps both its original suspicion and subsequent verification outcome.
8. **Finish honestly.** Stop when the queue is exhausted, limits are reached, the user cancels, or a fatal error occurs. Preserve partial results and explain why the run stopped.

## Example collaboration

Explorer A discovers a scheduling form. Explorer B explores draft management. The tester submits an invalid date and observes an unexpected success screen. The verifier recreates the form with fresh data, repeats the input, and checks the explicit requirement that past dates must be rejected. A reproducible violation is confirmed and attached to that transition. If the requirement is absent, it remains an observation requiring review.

## State identification and replay

A state contains more than a URL: normalised route, meaningful page structure, dialog state, and validation state. Ignore transient timestamps and irrelevant identifiers where safe. Preserve distinctions that change behaviour. Store a setup recipe and ordered action sequence so another worker can reach the state. Do not store secrets as replay values; refer to local credentials or fixtures.

## Deduplication and bounded exploration

Use stable task keys based on run, task type, target state and test case. Fingerprints suggest duplicate states but can be wrong; retain supporting observations and version the identity policy. Enforce depth, action, model-call, time and state-count limits. Reaching a budget is a partial review, not a passing result.

---

# Contracts, verification and recovery

| Record | Minimum content |
|---|---|
| Run | Target, requirements, model, mode, configuration, limits, status and stop reason. |
| Task | Type, dependencies, input references, owner, attempt, lease, status and result references. |
| ScreenState | Route, UI signature, screenshot reference, setup and navigation recipe. |
| Transition | Source state, executed action, resulting state, timing and evidence references. |
| TestCase | Setup, inputs, actions, expectation source and executable assertion. |
| Finding | Candidate description, expected and observed outcomes, replay and verification status. |
| Event and evidence | Ordered event ID, run/task/attempt/agent IDs, provenance and artifact hashes. |

## Verification outcomes

- **Confirmed**: the failure reproduced and violated an explicit supplied requirement or declared constraint.
- **Not reproduced**: the replay ran but did not show the claimed failure. This does not prove the website has no intermittent bug.
- **Inconclusive**: setup, replay, evidence, or the expected behaviour was insufficient.

Keep every outcome visible.

Version one uses a small assertion vocabulary: element visible, validation message present, navigation reached, expected text or value retained, and an explicit state condition. Store the assertion and its observed inputs. The engine evaluates assertions; the verifier chooses them from requirements. Human review still matters because an assertion can encode the wrong expectation.

## Required recovery demonstration

Inject a labelled stall after Explorer A claims a task. Its lease expires, the coordinator reassigns the task to B, and B returns a valid result. When A returns late, reject its result using the attempt identifier. Record claim, timeout, reassignment, acceptance and rejection events. The injected failure and real recovery remain distinguishable.

A stale-result check prevents stale evidence from being accepted; it does not undo browser side effects. Close or fence the expired worker context and use isolated/resettable data before retrying. Late model responses cannot issue new actions after their attempt expires.

## Stopping and restart behaviour

Allow a bounded number of retries and reject repeated no-progress states. Do not stop solely because the same test fails twice: its evidence may have changed. Cancellation closes worker contexts. If the backend process crashes, persisted records remain inspectable and the run is marked interrupted; full crash-resume is outside the initial scope.

## Run labels

Live execution, recorded playback, injected failure events, and synthetic fixture data are separate provenance fields, since they can coexist. Playback uses saved evidence and makes no claim that a fresh browser or LLM execution occurred.

---

# Interface, stack and operating budget

## Interface organisation

The run launcher collects the target, goals and limits. The main workspace contains the website map, findings list and evidence drawer. Clicking a state opens its screenshot; clicking a transition opens its action, input, outcome and timing. A separate agent timeline shows collaboration. Chat cites saved event or artifact IDs and says when evidence is missing. The map shows observed, tested, blocked and failed paths without implying complete site coverage.

| Layer | Initial choice |
|---|---|
| Frontend | React, TypeScript, Vite and Tailwind CSS. |
| Website map | React Flow with custom state nodes and labelled transition edges. |
| Backend | Python 3.12, FastAPI and Pydantic contracts. |
| Browser | Playwright Python and Chromium; validated structured commands. |
| Coordinator | Custom asyncio task management in one backend process. |
| Persistence | SQLite as the record source of truth; local files for evidence. |
| Live updates | Server-Sent Events with ordered IDs; reconnect from stored events. |
| Model access | One server-side OpenRouter adapter and configurable model ID. |
| Verification and packaging | pytest, browser integration checks, lockfiles and Docker Compose. |

## Model choice and budget

Start by smoke-testing `google/gemini-3-flash-preview` across all roles. `anthropic/claude-haiku-4.5` is an alternative if browser-tool reliability is better. These are candidates, not a final model-quality conclusion. Keep the same model in the single-versus-multi evaluation and record the exact ID and provider information available.

Use an initial US$10 credit budget, two concurrent model calls and approximately 40 model calls per run as a tunable starting point. Reserve part of the run budget for verification. Record actual usage, enforce bounded output and retries, and stop new calls when the budget is exhausted. Concurrent requests can still incur in-flight cost; a software estimate is not an exact billing cap.

Feed compact page observations to the model. Save screenshots routinely for review but send them to the model only when useful. Separate browser interaction duration, model latency and queue waiting. Report timing sample counts and conditions; small local runs are not production performance benchmarks.

## Test boundaries

Run against explicitly authorised local or staging targets. Keep allowed origins and actions scoped; production payments or destructive actions require a deliberately enabled test fixture. Store keys and browser sessions outside Git, redact secrets from evidence, and keep model credentials server-side. A word blocklist alone is not a reliable action boundary.

---

# Repository and implementation ownership

Repository: https://github.com/ryanyipp/ai-native-assessment (local clone: `C:\Users\Ryan Yip\Desktop\ai-native-assessment`, starting commit `5512d83`).

Planned layout:

```
ai-native-assessment/
  README.md  AGENTS.md  CLAUDE.md  .env.example  .gitignore  compose.yaml
  docs/
    plan.md  architecture.md  contracts.md
    decisions.md  attribution.md  demo-script.md
    development-log.md
  backend/
    pyproject.toml  uv.lock
    src/flowlens/
      main.py  config.py
      api/              # runs, artifacts, chat
      models/           # shared validated contracts
      agents/           # roles, model loop, prompts
      orchestration/    # queue, leases, budgets, recovery
      browser/          # execution, states, replay, assertions
      services/         # LLM, evidence, reporting
      storage/          # SQLite repositories
    tests/unit/  tests/integration/
  frontend/
    package.json  package-lock.json
    src/features/
      run-launcher/  flow-map/  findings/  evidence/
      agent-timeline/  review-chat/
    src/lib/            # API client and shared types
  fixtures/creator-studio/  # target app and requirements
  evaluation/              # hidden map, defects, scoring
  artifacts/               # ignored runtime output
  submission-evidence/     # selected sanitised real runs
```

## Development workstreams

One lead Claude session establishes shared contracts and the vertical slice. Then delegate separate workstreams for browser/evidence, orchestration/agents, frontend, and fixtures/evaluation. Use clear file ownership and separate worktrees when helpful. The lead owns integration and schema changes. No runtime agent receives repository or answer-key access.

## Reuse policy

Use agentic-test-explorer as a reference for structured browser commands, recorded actions and reproduction artifacts. Do not assume its whole framework must be adopted. If code is reused, inspect the licence, preserve notices, and document precisely what was reused unchanged, modified, or newly implemented. Record how coding assistants contributed and where human review corrected their output.

---

# Evaluation and design decisions

## Reference application

Build a small creator dashboard with draft creation, editing, persistence and scheduling. Keep a documented reference map, known defects and a corrected build. The agents see only the browser and supplied requirements. Freeze evaluation scenarios before final runs and hold some cases out from prompt tuning.

### First demo journey

**Create draft → save → reload → verify persistence.**

1. Open the creator-studio fixture and start a new draft.
2. Enter draft content and save it.
3. Reload the page (fresh navigation, same session).
4. Verify that the saved draft and its values are still present. Use the `expected text or value retained` assertion.

This is the target for Checkpoint 1. A real model drives the browser through this journey, and the recorded states and transitions appear on a clickable evidence map.

| Metric | How to interpret it |
|---|---|
| Journey coverage | Matched observed states/transitions within the explicitly bounded reference set; count spurious states separately. |
| Defect detection | Known defects found, missed defects and false positives. Review whether the expectation and evidence are valid. |
| Fixed-build behaviour | Repeat scenarios on the corrected version; check that old failures disappear without new false alarms. |
| Recovery | Expired attempt rejected, replacement completes, no duplicate accepted result, and complete event trace. |
| Efficiency | Elapsed time, model calls, tokens and actual reported cost; include setup and verification consistently. |
| Answer grounding | Chat citations exist and support the answer; untested questions receive an explicit limitation. |

## Single-agent comparison

Baseline: one agent performs exploration, input testing and verification sequentially, with a fresh browser context for verification. Multi-agent condition: two explorers, tester and verifier collaborate through the queue. Keep model, tools, requirements, starting data and global limits comparable. Record both quality and cost; do not silently give each multi-agent worker the entire baseline budget.

Begin with about three repeated runs per condition on a small frozen scenario set. Show individual results and variation. One explorer versus two, while keeping separate tester/verifier agents, is an optional parallelism ablation, not the single-agent baseline. A second application is a limited generalisation check, not proof of arbitrary-site reliability.

## Two architecture decisions to defend

1. **Shared queue with explicit claims vs an LLM supervisor.** Explicit ownership makes retries and stale-result handling easier to inspect, but requires a constrained task model and navigation recipes.
2. **Independent replay with executable assertions vs an LLM-only verdict.** Replay provides stronger evidence, but costs time and still depends on correct expectations and setup.

## Documented design iteration

Compare an initial URL-only state map with a revised map that distinguishes dialogs and meaningful form states. Preserve screenshots and real run records. Measure collapsed states and duplicate nodes against the bounded reference map. Present the observed trade-off rather than assuming the revised method always wins.

---

# Delivery checkpoints and presentation

| Checkpoint | Acceptance gate |
|---|---|
| 0 Foundation | Repo and contracts exist; frontend, backend and fixture start; secrets are ignored. |
| 1 Vertical slice | A real model drives a browser journey; recorded transitions appear on a clickable evidence map. |
| 2 Verification | Input test finds one known defect; independent replay confirms it; corrected build passes the same check. |
| 3 Collaboration | Two explorers and specialist workers hand off actual work; ownership prevents duplicate acceptance. |
| 4 Recovery | A labelled stall expires and is reassigned; a late result is rejected; trace and side-effect handling are visible. |
| 5 Review product | Findings, timeline and evidence are usable; chat cites records; Markdown export uses the same data. |
| 6 Evaluation | Baseline comparison, fixed-build runs, clean setup, recording, attribution and presentation are complete. |

## Three-day implementation budget

- **Day one:** foundation, browser-to-map vertical slice, then one input test and verification.
- **Day two:** shared queue, second explorer, recovery and interface refinement; start evaluation runs.
- **Day three:** finish comparisons, add limited grounded chat, validate installation, record the demo and complete documentation.

If delayed, shrink chat and the second-app exercise before cutting recovery or validation.

## Human review loop

GPT supplies the next bounded prompt. Claude implements, verifies and commits. Ryan runs the application and reviews behaviour. Share the diff or commit plus artifacts and actual test output with GPT; GPT reviews and supplies a correction or next checkpoint. No one should infer that a successful build means browser behaviour was tested.

Each checkpoint report states changes, run commands, checks actually executed, live versus mocked behaviour, limitations, and commit hash. Preserve incremental commits and push completed work in time for the submission deadline; local-only commits are insufficient. Do not reproduce the confidential assessment document in the repository.

## Presentation narrative

Show the user goal and target website. Start a run; watch an explorer discover a form and hand it to the tester. Open a verified defect from the website map. Switch to the agent timeline to explain task ownership and a recorded or live recovery. Show the corrected-build result and single-agent comparison. Finish with architecture trade-offs, design iteration, attribution and limitations.

Prepare a short actual-run screen recording as backup. Clearly label playback. Presentation duration and recording-submission expectations remain subject to recruiter clarification.

Known dates:
- Participation and repository URL: 30 October 2026, 23:59 Singapore time.
- Final pushed work: 2 November 2026, 23:59.
- On-site session: 3 November 2026 (time and venue to be confirmed).

---

# References and remaining decisions

## Implementation references

- Agentic Test Explorer: reference for the workflow, action recording, reproduction artifacts and application-model export. Its documentation has been inspected, but the implementation has not been run yet. https://github.com/srbarrios/agentic-test-explorer
- Playwright browser contexts: https://playwright.dev/python/docs/api/class-browsercontext
- React Flow custom nodes: https://reactflow.dev/learn/customization/custom-nodes
- FastAPI concurrency: https://fastapi.tiangolo.com/async/
- OpenRouter Gemini candidate: https://openrouter.ai/google/gemini-3-flash-preview
- OpenRouter Haiku candidate: https://openrouter.ai/anthropic/claude-haiku-4.5

## Decisions to settle during implementation

- Model selection after a small navigation, form-input and structured-output smoke test.
- Exact fixture defects, held-out scenarios and bounded reference map before final evaluation.
- Lease duration, per-task limits and global budget after measuring the first complete run.
- Second application selection after the core product works.
- Whether any upstream code is reused, determined by inspection rather than assumed in advance.
- Recruiter confirmation of private-repository reviewer access, recording expectations and presentation duration.

## Definition of a successful first submission

A fresh setup launches FlowLens and its fixture. A real model-driven run creates a useful behaviour map. Discovered work moves between agents. A suspected defect is independently checked against an explicit expectation. An agent timeout is diagnosed and recovered from with recorded ownership checks. The report states coverage limits and the measured single-agent comparison. Every major claim can be traced to actual execution evidence.

## Immediate next action

Complete repository setup and the first browser-to-map vertical slice only. Review the result before expanding the worker team.
