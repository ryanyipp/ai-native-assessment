# Development log

## 2026-10-29: Checkpoints 0 and 1

**Environment found:** Windows 11, Python 3.12.10 (also 3.10 default `python`, 3.11), Node 22.22.0, npm 10.9.4, Git 2.49, Docker 29.1.3.

**Prerequisite gaps:**
- `uv` was not installed. Installed with `py -3.12 -m pip install --user uv`. It is not on PATH, so commands use `py -3.12 -m uv`.
- The default `python` is 3.10. Always use `py -3.12` or `backend\.venv\Scripts\python`.
- Vite binds `localhost` (IPv6 on this machine). Use `http://localhost:5173`, not `127.0.0.1`.
- `compose.yaml` and Docker packaging are not done yet.

**.env:** the existing values were kept. `OPENROUTER_MODEL` and `DATABASE_URL` were empty, so defaults apply (`google/gemini-3-flash-preview`, `artifacts/flowlens.db`). The unused `PORT` key is ignored.

**Design notes:**
- State signature policy v1: normalised route + headings + control role/name + field filled/empty + status messages. Values are excluded, so a reload with retained values maps to the same state (a self-loop).
- Each run executes in its own thread with its own asyncio loop. Playwright needs a subprocess-capable loop on Windows.
- The explorer is stateless per step. It gets the goal, its last 12 actions and a compact observation, which keeps prompt size bounded (about 600–1000 tokens per call in the live run).

**First live run:** `run_e957eab8645e`: 6 calls, 4,386 tokens, reported US$0.004238, completed. Evidence is in `submission-evidence/checkpoint-1/`.

## 2026-10-29: Workspace UI

**Frontend dependencies added:**
- `lucide-react`: icons.
- `@dagrejs/dagre`: layered graph layout.
- `@radix-ui/react-dialog`, `@radix-ui/react-tabs`, `@radix-ui/react-tooltip`: accessible primitives.
- `@fontsource-variable/inter`, `@fontsource-variable/jetbrains-mono`: self-hosted fonts.
- `axe-core` (dev): accessibility checks.

shadcn/ui was not adopted. Only three primitives were needed, so I wrote small Tailwind components over Radix instead (`frontend/src/components/ui.tsx`) rather than adding the shadcn CLI and generated files.

**Backend changes:** none. The UI uses only the existing `/api/health`, `/api/runs`, `/api/runs/{id}` and `/api/artifacts/{id}` endpoints.

**Browser check:** `backend\.venv\Scripts\python scripts\ui_check.py run_e957eab8645e docs\ui-iteration` runs 29 checks, including axe, against a saved real run. It needs the backend and frontend running and makes no model calls. The design iteration is recorded in `docs/ui-iteration/README.md`.

## 2026-10-29: Checkpoint 2 (input tester and independent verifier)

**Built:** fixture scheduling form with broken/corrected modes, fixed clock and per-workspace data; handoff, test-case and verification contracts; semantic control resolution; typed assertions; `ReviewRun` (explorer → input tester → verifier, sequential); `ReverifyRun`; UI extensions. Design: `docs/architecture.md`. Evidence: `submission-evidence/checkpoint-2/`.

**Problems found by live runs, and what changed:**
- *Truncated tester JSON* (`run_eb3e50ed6997`): hidden reasoning consumed 764 of 800 output tokens. Added `max_output_tokens_planning` (2000) for tester/verifier calls. This still truncated once in `run_44704dfc5083` (1,918 reasoning tokens). That run is recorded as partial; it is not hidden or retried away.
- *Blocked tester left the run `completed`*: a blocked task now marks the run `partial`.
- *False confirmations of R2* (`run_5f08da7d0fc8`): "A draft has a title and a caption" was read as "both required". The verifier now states whether the requirement is explicit and quotes it; code checks the quote against the requirement text. Not explicit → inconclusive. This is a prompt and schema change, not fixture-specific.
- *Field-scoped validation assertion* did not see page-level alerts naming the field, so the corrected build would also have "failed". The evaluator now accepts an alert that names the field.
- *Disconnected map nodes*: every fill in a fresh session created a state. Fresh sessions now add only start and outcome states.
- *Contrast*: white text on `accent-500` (selected step pill) and the Start badge on dimmed nodes were below 4.5:1 (axe). Fixed.

**Checks:** backend pytest 37 passed (scripted-model tests are labelled `mocked_model`); `npm run build`, `npm run lint` clean; `scripts/ui_check.py` 29/29 on the checkpoint 1 run (compatibility); `scripts/ui_check_review.py` 22/22 on the checkpoint 2 runs.

## 2026-10-29: Fix for run_53d7009ff711 (stale backend)

**Symptom:** a review run started from the UI failed when the tester started: `AttributeError: 'RunLimits' object has no attribute 'max_output_tokens_planning'`. The explorer had finished, one form had been handed off, and 15 calls (US$0.0166) had been spent. The run record is unchanged.

**Root cause:** the API backend had been started before `RunLimits` gained the field, and was not restarted. `start_run_thread` imported `ReviewRun` lazily, so the first review run loaded the newer `review.py` from disk on top of the old in-memory contracts. The traceback's line numbers did not match the loaded code. The evaluation script runs in a fresh process, which is why the earlier live runs did not hit it.

**Fix (`63037f0`):**
- Run classes are now imported at startup (`orchestration/launch.py`).
- The API returns 503 ("restart the backend") if backend source changed after the process started, and `/api/health` reports `code_version`.
- Failures record the stage and progress, and state that zero findings is not a pass; the Findings tab leads with this.
- API runs take their provenance label from the client.
- Regression tests cover the API review path with default settings, the stale-code refusal, and a crash mid-review.

**Verification:** backend restarted while idle. A fresh live run through the API, `run_a572a9bf88c5`, completed: 11 calls (explorer 4, tester 4, verifier 3), 14,820 tokens, US$0.023625 reported. R5 was confirmed in 2/2 fresh replays; two R2 candidates and one observation without a requirement were inconclusive.

## 2026-10-29: Checkpoint 3 (shared queue and second explorer)

**Built:** persistent queue (`storage/queue.py`) and the `queue_review` mode (`orchestration/queue_review.py`) with explorer-a, explorer-b, input-tester and verifier. Tester-discovered states are now actionable explore tasks. The Activity tab has a task board. Design: `docs/architecture.md`.

**Bug found while designing:** the model-slot semaphore was a blocking `threading` semaphore. With several workers on one event loop, a third concurrent call would have frozen the loop while the slot holders awaited I/O. Slots are now acquired with `asyncio.to_thread`.

**Checks:** backend pytest 44 passed. New tests cover:
- atomic claims from 8 threads over 30 tasks;
- deduplication, dependency gating, stale completion and bounded retries;
- a scripted two-explorer run: both explorers claim, tester frontier is consumed, verify tasks wait for the test task, one context per explore task, shared sightings;
- the explorer budget share leaving room for the tester and verifier.

Frontend build and lint are clean. UI checks: `ui_check.py` 29/29, `ui_check_review.py` 22/22, `ui_check_queue.py` 13/13.

**Live run:** `run_72e3868cc54e` through the API (limits: 30 calls, US$0.30, 3 steps per explore task, depth 2, 6 testing + 5 verification calls reserved). It ended **partial**: 21 calls (explorer-a 10, explorer-b 6, input-tester 4, verifier 1), 25,431 tokens, US$0.0361 reported.
- **Tasks:** 8 done, 1 blocked (the draft-form tester plan was truncated again), 2 unfinished (the explorer budget share was used).
- **Handoffs:** two forms explorer-a → input-tester; two candidates input-tester → verifier. R5 confirmed; one observation without a requirement inconclusive.
- **Tester frontier consumed:** "Scheduled post — Post scheduled." was queued by the tester and explored by explorer-b.
