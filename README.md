# FlowLens

An AI website reviewer. It explores an authorised staging site and builds an evidence-linked map of observed states and transitions. See `docs/plan.md` for the full plan and `AGENTS.md` for working rules.

Status: **Checkpoint 4** (shared task queue with enforced leases, fencing and stalled-worker recovery; labelled fault injection; the sequential checkpoint 2 workflow remains selectable). See `docs/architecture.md`.

## Setup

Full instructions, configuration and the recorded demo runs are in **[docs/setup.md](docs/setup.md)**. In short:

```sh
docker compose up --build          # FlowLens + both fixture apps; open http://localhost:5173
```

or natively (Python 3.12 + uv, Node 22+):

```powershell
cd backend; py -3.12 -m uv sync --frozen; .\.venv\Scripts\python -m playwright install chromium; .\.venv\Scripts\python -m flowlens.demo load; cd ..
cd frontend; npm ci; cd ..
# then start the fixtures, backend and frontend as in docs/setup.md
```

No API key is needed to inspect the recorded demo runs (labelled **Recorded demo result**). Live runs need `OPENROUTER_API_KEY` in `.env` (copy `.env.example`; never commit `.env`). Open http://localhost:5173, keep the default target `http://localhost:5174/` and goal, and click **Start live run**.

## Checks

```powershell
cd backend; .\.venv\Scripts\python -m pytest -q
cd frontend; npm run build; npm run lint
# With backend and frontend running (no model calls):
backend\.venv\Scripts\python scripts\ui_check.py run_e957eab8645e docs\ui-iteration
backend\.venv\Scripts\python scripts\ui_check_review.py run_db4f36872772 run_44704dfc5083 run_40e786578fef docs\checkpoint-2
backend\.venv\Scripts\python scripts\ui_check_queue.py run_72e3868cc54e docs\checkpoint-3
# Checkpoint 2 live evaluation (spends credit; both fixture builds must be running):
backend\.venv\Scripts\python scripts\checkpoint2_eval.py all
```

## Budget

`FLOWLENS_BUDGET_USD` (default 10) is the overall credit pool, summed from provider-reported cost across all recorded runs. `FLOWLENS_RUN_BUDGET_USD` (default 0.50) caps each run. Output is bounded by `FLOWLENS_MAX_OUTPUT_TOKENS` (800) and calls by `FLOWLENS_MAX_MODEL_CALLS_PER_RUN` (40). Limits are checked **before** each call. A call that starts under the limit can finish over it (in-flight overshoot of at most one call per concurrent slot), so this is a software guard, not a billing cap. Hitting a limit marks the run `partial`, never passing.
