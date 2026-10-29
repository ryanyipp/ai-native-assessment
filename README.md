# FlowLens

An AI website reviewer. It explores an authorised staging site and builds an evidence-linked map of observed states and transitions. See `docs/plan.md` for the full plan and `AGENTS.md` for working rules.

Status: **Checkpoint 1** (one live explorer, browser-to-map vertical slice).

## Prerequisites (Windows)

- Python 3.12 (`py -3.12`), Node 22+ / npm 10+, Git
- uv: `py -3.12 -m pip install --user uv` (then call it as `py -3.12 -m uv`)

## Setup (PowerShell, from the repository root)

```powershell
Copy-Item .env.example .env   # only if .env does not exist yet; then set OPENROUTER_API_KEY
cd backend; py -3.12 -m uv sync; .\.venv\Scripts\python -m playwright install chromium; cd ..
cd frontend; npm ci; cd ..
```

Empty or missing optional `.env` values fall back to defaults in `backend/src/flowlens/config.py`.

## Start (three terminals, from the repository root)

```powershell
# 1. Fixture (review target) on :5174
backend\.venv\Scripts\python -m uvicorn app:app --app-dir fixtures\creator-studio --host 127.0.0.1 --port 5174
# 2. Backend API on :8000
cd backend; .\.venv\Scripts\python -m uvicorn flowlens.main:app --host 127.0.0.1 --port 8000
# 3. Frontend on :5173
cd frontend; npm run dev
```

Open http://localhost:5173, keep the default target `http://localhost:5174/` and goal, and click **Start live run**.

## Checks

```powershell
cd backend; .\.venv\Scripts\python -m pytest -q
cd frontend; npm run build; npm run lint
# With backend and frontend running (no model calls):
backend\.venv\Scripts\python scripts\ui_check.py run_e957eab8645e docs\ui-iteration
```

## Budget

`FLOWLENS_BUDGET_USD` (default 10) is the overall credit pool, summed from provider-reported cost across all recorded runs. `FLOWLENS_RUN_BUDGET_USD` (default 0.50) caps each run. Output is bounded by `FLOWLENS_MAX_OUTPUT_TOKENS` (800) and calls by `FLOWLENS_MAX_MODEL_CALLS_PER_RUN` (40). Limits are checked **before** each call. A call that starts under the limit can finish over it (in-flight overshoot of at most one call per concurrent slot), so this is a software guard, not a billing cap. Hitting a limit marks the run `partial`, never passing.
