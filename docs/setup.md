# Setting up FlowLens

There are two ways to run FlowLens with its two fixture apps:

- **Docker Compose**: one command, nothing installed locally except Docker.
- **Native**: Python, Node and Playwright installed on your machine.

Both can show the **recorded demo runs** without an API key.

## What runs where

| Service | Port | What it is |
|---|---|---|
| Frontend | 5173 | The FlowLens UI. It proxies `/api` to the backend. |
| Backend API | 8000 | FastAPI, SQLite and Playwright Chromium. The browser engine and all model calls run here. |
| creator-studio, broken | 5174 | Fixture app with a seeded past-date defect. |
| creator-studio, corrected | 5175 | The same app with the defect fixed. |
| ticket-desk, broken | 5176 | A second fixture app with seeded defects. |
| ticket-desk, corrected | 5177 | Its corrected build. |

The fixtures are review targets. Their source and `evaluation/` are never given to the runtime agents. Each fixture creates its own data file on first use.

## Configuration

All settings are optional, and empty values fall back to the defaults in `backend/src/flowlens/config.py`. To set any of them, copy `.env.example` to `.env`; this never overwrites an existing `.env`. `.env` is git-ignored and excluded from Docker builds.

| Setting | Needed for | Notes |
|---|---|---|
| `OPENROUTER_API_KEY` | Live runs only | Without it the UI works, saved and demo runs can be inspected and previews work, but **Start live run** is disabled. Server-side only; never sent to the browser. |
| `OPENROUTER_MODEL` | | Default `google/gemini-3-flash-preview`. |
| `FLOWLENS_BUDGET_USD`, `FLOWLENS_RUN_BUDGET_USD` | | The overall credit pool (10) and the per-run cap (0.50). |
| `FLOWLENS_ALLOWED_ORIGINS` | | Fixture origins that get test-data workspaces. The default covers ports 5174–5177 on `localhost` and `127.0.0.1`. Change it only if you move the fixtures. Other websites are approved in the launcher. |
| `DATABASE_URL`, `ARTIFACTS_DIR` | | Default `artifacts/flowlens.db` and `artifacts/`, both git-ignored. |
| `FRONTEND_PORT` | | The frontend port and the CORS origin (5173). |
| `FLOWLENS_API_URL` | | The backend URL the frontend proxies to (`http://127.0.0.1:8000`). Read by the frontend dev server; set it when the backend uses another port. |

## Option A: Docker Compose

Prerequisite: Docker Engine or Docker Desktop with Compose v2.24 or later.

```sh
docker compose up --build
# open http://localhost:5173
```

- **First build:** about 1–2 GB to download. It installs the locked Python packages, Chromium with its system libraries (`playwright install --with-deps chromium`) and the frontend build.
- **Demo runs:** loaded into a Docker volume at start. Set `FLOWLENS_LOAD_DEMO=0` to skip them.
- **Live runs:** put `OPENROUTER_API_KEY` in `.env` before `docker compose up`. Compose reads `.env` if it exists; the file is never copied into an image.
- **Ports:** if any are taken on the host, change the host side, for example `FRONTEND_HOST_PORT=15173 BACKEND_HOST_PORT=18000 docker compose up`. Targets inside FlowLens keep using `http://localhost:5174` and so on, because every service shares the backend's network namespace.
- **Reset data:** `docker compose down -v` removes the volume, including the database, artifacts and fixture data.

## Option B: Native

Prerequisites:

- **Python 3.12**, plus **uv**: `py -3.12 -m pip install --user uv` on Windows, or `pipx install uv`.
- **Node 22 or later** with npm 10, and Git.
- Disk space for Chromium (about 300 MB, downloaded by Playwright). On Linux, `playwright install --with-deps chromium` also installs system libraries; it needs `sudo`.

### Install (from the repository root)

PowerShell:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }   # optional; add OPENROUTER_API_KEY for live runs
cd backend; py -3.12 -m uv sync --frozen; .\.venv\Scripts\python -m playwright install chromium; cd ..
cd frontend; npm ci; cd ..
```

bash (macOS and Linux):

```sh
[ -f .env ] || cp .env.example .env                           # optional
(cd backend && uv sync --frozen && .venv/bin/python -m playwright install --with-deps chromium)
(cd frontend && npm ci)
```

### Start (separate terminals, from the repository root)

PowerShell; on bash, use `backend/.venv/bin/python` and `export VAR=value`.

```powershell
# Fixtures (start the ones you need)
backend\.venv\Scripts\python -m uvicorn app:app --app-dir fixtures\creator-studio --host 127.0.0.1 --port 5174
$env:CREATOR_STUDIO_MODE='corrected'; $env:CREATOR_STUDIO_DATA='fixtures\creator-studio\data\corrected.json'; backend\.venv\Scripts\python -m uvicorn app:app --app-dir fixtures\creator-studio --host 127.0.0.1 --port 5175
backend\.venv\Scripts\python -m uvicorn app:app --app-dir fixtures\ticket-desk --host 127.0.0.1 --port 5176
$env:TICKET_DESK_MODE='corrected'; $env:TICKET_DESK_DATA='fixtures\ticket-desk\data\corrected.json'; backend\.venv\Scripts\python -m uvicorn app:app --app-dir fixtures\ticket-desk --host 127.0.0.1 --port 5177

# Backend API
cd backend; .\.venv\Scripts\python -m uvicorn flowlens.main:app --host 127.0.0.1 --port 8000

# Frontend
cd frontend; npm run dev
```

Open http://localhost:5173.

## Recorded demo runs (no API key)

`demo/` holds seven saved runs: their records plus the screenshots and page records they reference.

| Run | What it shows |
|---|---|
| `run_a572a9bf88c5` | A sequential review of creator-studio (broken): the past-date defect confirmed by an independent verifier. |
| `run_d50048493cc5` | A shared-queue review of ticket-desk (corrected) that drained its queue. |
| `run_a54099283d9d` | A shared-queue review that stopped early (partial) at its exploration budget. |
| `run_53d7009ff711` | A run that stopped on an internal error (failed). |
| `run_fc9eba62a54c` | The single-agent baseline: a finding confirmed only by self-check. |
| `run_15f19bf8bb46` | A public website (TodoMVC) explorer run; its checkbox claims are not evaluated. |
| `run_40e786578fef` | A re-check of an earlier finding on the corrected build: not reproduced. |

To load them natively (Docker does this automatically), with the backend stopped or running:

```powershell
cd backend; .\.venv\Scripts\python -m flowlens.demo load
```

- **No API key and no model or website calls:** it copies records into the configured database and artifacts folder.
- **Repeat-safe:** runs that already exist are skipped; `--replace` re-imports them.
- **Labelled:** every loaded run is marked as imported. The run header shows **Recorded demo result**, Diagnostics and the report say where it came from, and nothing is re-run.
- **Viewing them:** choose **Explore recorded demos** on the landing page (`/`), or open a run from the run history and use Map, Browser, Evidence, Activity, Findings and **Report**. The map, screenshots and reports come from the saved records.
- **Making new runs:** that still needs the fixtures and an API key.

Maintainers re-export with `python -m flowlens.demo export RUN_ID ... --note RUN_ID=TEXT`. It reads the current database and writes into `demo/`. Check the bundle for secrets before committing.

## Checks

```powershell
cd backend; .\.venv\Scripts\python -m pytest -q     # starts its own fixture servers; no model calls
cd frontend; npm run build; npm run lint
```

`scripts/ui_check_*.py` are browser checks against saved runs, with the backend and frontend running. Only `ui_check_workspace.py --live` and `ui_check_public_site.py --live` start live runs.

### Continuous integration

`.github/workflows/ci.yml` runs on pushes to `main` and on pull requests, on Ubuntu with no secrets:

- **Backend:** `uv sync --frozen`, Chromium for the locked Playwright version, then `pytest`. Browser tests drive the local fixture apps and agents use mocked model clients. The model URL points at a dead local port and the key is empty, so no paid call can succeed.
- **Frontend:** `npm ci`, `npm run lint`, `npm run build`.

CI does not cover live model runs, the evaluation batches, `scripts/ui_check_*.py`, Docker Compose or public websites. A green run means these automated checks passed, not that a live review works.

## Which setup paths have been tested

See `docs/setup-verification.md`: native setup and Docker Compose, each from a clean clone on Windows 11.
