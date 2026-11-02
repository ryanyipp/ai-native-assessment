# FlowLens

An AI website reviewer. It explores an authorised staging site, builds an evidence-linked map of observed states and transitions, tests form inputs against requirements you supply, and re-checks suspected defects in fresh browser replays. See `docs/plan.md` for the agreed plan and `AGENTS.md` for working rules.

**Status:** submission. Checkpoints 0–6 are built (vertical slice, verification, shared queue, recovery, review product, evaluation). What exists and what was only planned is listed under "Implementation status" in `AGENTS.md`. In short: the UI refreshes by polling every 1.5 s, reports are built from saved records with no model, re-checks are script-only, and review chat is out of scope. A completed run finished its work; it does not mean the website passed.

## How a review works

Four model-driven workers share one task queue. Code, not a model, runs the queue and writes the report.

| Part | Kind | Does |
|---|---|---|
| Coordinator | Code | Queues tasks, gives each claim a lease, expires stalled attempts, rejects late results, enforces call, cost and time limits |
| Explorer A and B | Model + browser | Choose links and buttons on claimed pages; code records states, transitions and forms, and refuses repeated or form-filling explorer actions |
| Input tester | Model + browser | Plans input cases for a discovered form; code fills text fields, dropdowns and tick boxes in a fresh browser and records what happened; the model then judges each case against the requirements |
| Verifier | Model + browser | Judges whether the requirement applies to the tested control, then picks one typed assertion; code replays the case twice in fresh browsers and evaluates the assertion |
| Report | Code | Builds the HTML and Markdown report from saved records |

A **confirmed** finding means the assertion failed in every fresh replay. It still rests on a model's reading of the requirement and its choice of assertion. Details and current behaviour are in [docs/architecture.md](docs/architecture.md).

## Known limitations

- **Requirements are needed.** Without them, a suspected problem stays an unverified observation.
- **Applicability is a model judgement.** Code checks its shape and that it names a tested control, not that it is right.
- **Unsupported controls:** radio buttons and file inputs. A case that needs one is marked `execution_failed` before the form is touched. Any case that does not complete gets no verdict and does not count as tested.
- **Bounded exploration:** call, cost, depth and task limits apply, and coverage is not exhaustive. On Leave Desk, explorers still repeat navigation.
- **Recovery is in one process.** Stalled workers are recovered within a run; if the backend restarts, running reviews are marked `interrupted`, not resumed.
- **Tester output:** truncated or invalid JSON can stop a form's test plan, which the run reports as untested.

## Try it

```sh
docker compose up --build          # FlowLens + three fixture apps (broken and corrected builds); open http://localhost:5173
```

The landing page has a demo video and **Explore recorded demos**, which opens eight saved runs without an API key, including the run in the video (`run_7bbdcc167bb6`). Live runs need `OPENROUTER_API_KEY` in `.env` (copy `.env.example`; never commit `.env`). Choose **Start a review**, keep the default target `http://localhost:5174/` or pick another fixture, enter a goal (at least 5 characters) and the requirements, and click **Start live run**.

Native setup (Python 3.12 + uv, Node 22+), configuration and the recorded demo runs are described in **[docs/setup.md](docs/setup.md)**.

## Checks

```powershell
cd backend; .\.venv\Scripts\python -m pytest -q     # no model calls; starts its own fixture servers
cd frontend; npm run lint; npm run build             # build type-checks first (tsc -b)
```

Browser checks against saved runs (`scripts/ui_check_*.py`) and the CI workflow are described in [docs/setup.md](docs/setup.md#checks).

## Evaluation

[docs/model-comparison.md](docs/model-comparison.md) compares models and the shared queue with a single-agent baseline. Every batch ran on code earlier than the submission; the document gives each batch's commit and fingerprint. The current-code rerun separates **scored** detections from **supported** ones, whose assertion also passes on the corrected build. Gemini 3 Flash found 6/6 supported in the shared queue and 3/6 as a single agent; across four models the totals were 9/24 and 8/24. An extension with four more model families stopped at 45 of 64 runs. Earlier evaluations are in [docs/evaluation.md](docs/evaluation.md) and [docs/evaluation-2.md](docs/evaluation-2.md).

## Budget

`FLOWLENS_BUDGET_USD` (default 10) is the overall credit pool, summed from provider-reported cost across this installation's runs. `FLOWLENS_RUN_BUDGET_USD` (default 0.50) caps each run. Output is bounded by `FLOWLENS_MAX_OUTPUT_TOKENS` (800). The launcher sends 60 model calls per run; `FLOWLENS_MAX_MODEL_CALLS_PER_RUN` (40) applies only to API requests that send no limits. Limits are checked **before** each call, so a call that starts under the limit can finish over it: this is a software guard, not a billing cap. Hitting a limit marks the run `partial`, never passing.

## Attribution

See [docs/attribution.md](docs/attribution.md).
