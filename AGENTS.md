# AGENTS.md: FlowLens implementation instructions

`docs/plan.md` is the full agreed plan. If this file and the plan disagree, the plan wins. Raise the conflict instead of guessing.

## Product

FlowLens is an AI website reviewer. It explores an authorised staging site and builds an interactive map of observed states and transitions. It tests inputs, independently verifies candidate defects, and presents evidence-linked findings, an agent timeline and a Markdown report. A grounded review chat comes last.

## Stack (initial choices)

- **Frontend:** React, TypeScript, Vite, Tailwind CSS, React Flow (custom state nodes, labelled transition edges)
- **Backend:** Python 3.12, FastAPI, Pydantic contracts, custom asyncio coordinator in one process
- **Browser:** Playwright Python + Chromium, executing validated structured commands
- **Persistence:** SQLite as the source of truth, with evidence stored as local files under `artifacts/` (ignored by Git)
- **Live updates:** SSE with ordered event IDs that clients can reconnect from
- **Model:** one server-side OpenRouter adapter. The model ID comes from `OPENROUTER_MODEL`. Never call the model from the frontend.
- **Verification and packaging:** pytest, browser integration tests, lockfiles (`uv.lock`, `package-lock.json`), Docker Compose

## Scope

In scope: Chromium, one user role, bounded exploration, a supplied test session, and the `fixtures/creator-studio` creator-dashboard fixture. A second small app is optional.

Out of scope: exhaustive coverage, automatic code repair, load testing, real TikTok integration and full crash-resume.

## Runtime agents (inside FlowLens)

| Role | Does | Must not |
|---|---|---|
| Coordinator (code, not an LLM) | Queue, atomic claims with attempt ID and lease, budgets, accepts validated results | Accept a result from a non-current attempt |
| Explorer A / B | Explore a claimed frontier state; emit states, transitions, forms, candidate issues | Confirm its own defects |
| Input tester | Generate input cases for a discovered form; emit outcomes and candidate findings | Skip returning new states to exploration |
| Verifier | Replay from a fresh context; evaluate an executable assertion | Produce a verdict from LLM prose alone |
| Reporter / chat | Summarise and answer using cited record and artifact IDs | Invent observations or launch tests (v1) |

- LLMs propose actions, inputs and assertions, constrained by a bounded schema. Code executes, records, evaluates and stores.
- Each worker gets its own browser context. Operations on shared server data are serialised or namespaced.
- Verification outcomes are `confirmed`, `not_reproduced` or `inconclusive`, and all of them stay visible.
- Assertion vocabulary (v1): element visible, validation message present, navigation reached, expected text/value retained, explicit state condition.
- Provenance fields stay separate: live, playback, injected failure and synthetic fixture data.
- Enforce depth, action, model-call, time, state-count and cost limits. Hitting a budget means the review is partial, not passing.
- Starting budget: max 2 concurrent model calls and about 40 calls per run, with part of it reserved for verification.

## Core contracts

Define these first as Pydantic models in `backend/src/flowlens/models/` and mirror them in `frontend/src/lib/`:
Run, Task, ScreenState, Transition, TestCase, Finding, Event/Evidence.
See the minimum fields in `docs/plan.md` § Contracts. The lead session owns schema changes.

## Development roles

- **Ryan:** product decisions, runs the app locally, final acceptance.
- **Claude (lead session):** contracts, vertical slice, integration, schema changes, commits.
- **Claude subagents:** separate workstreams (browser/evidence, orchestration/agents, frontend, fixtures/evaluation), each with clear file ownership. Use worktrees when helpful.
- **GPT:** writes bounded prompts and reviews diffs and artifacts.
- No runtime agent may access the repository or `evaluation/` answer keys.

## Build order (checkpoints)

0. **Foundation:** contracts exist; backend, frontend and fixture start; secrets ignored.
1. **Vertical slice:** a real model drives *create draft → save → reload → verify persistence* with one explorer, and the transitions appear on a clickable evidence map.
2. **Verification:** an input test finds one known defect, independent replay confirms it, and the corrected build passes.
3. **Collaboration:** two explorers plus specialist workers hand off real work, and ownership prevents duplicate acceptance.
4. **Recovery:** a labelled stall expires and the task is reassigned. The late result is rejected, and every event is recorded.
5. **Review product:** findings, timeline, evidence, cited chat and Markdown export.
6. **Evaluation:** single-agent baseline (about 3 runs per condition), fixed-build runs, clean setup, attribution.

Stop at the end of each checkpoint for review. Add the second explorer only after ownership and replay have tests.

## Working rules

- **Commits:** make small, clear, incremental commits, one logical change each. Never commit secrets, `.env`, browser sessions or `artifacts/`.
- **Pushing:** never push or change repository visibility unless Ryan explicitly asks.
- **Verification:** run the relevant checks before claiming something works. A successful build does not mean browser behaviour was tested.
- **Checkpoint report:** list the changes, run commands, checks actually executed, what was live and what was mocked, limitations, and the commit hash.
- **Secrets:** keep keys in `.env` only (copy the template from `.env.example`) and redact secrets from evidence. Replay recipes reference credentials and never contain them.
- **Targets:** only authorised local or staging origins. Destructive actions require an explicitly enabled fixture.
- **Evidence:** `submission-evidence/` holds selected, sanitised real runs and is tracked by Git. Label playback as playback.
- **Attribution:** record reuse (unchanged, modified or new) and assistant contributions in `docs/attribution.md`. Check the licence before reusing agentic-test-explorer code.
- **Confidentiality:** never copy the confidential assessment PDF or its problem statements into the repo.
