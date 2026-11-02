# Setting up FlowLens

Two ways to run FlowLens with its three fixture apps:

- **[Option A: Docker Compose](#option-a-docker-compose)**: needs only Docker. Recommended for a first look.
- **[Option B: Native](#option-b-native)**: Python, Node and Playwright on your machine; one terminal per service.

Both can open the **recorded demo runs** without an API key. Live reviews need an OpenRouter key and cost money.

Commands are labelled **PowerShell** (Windows) or **bash** (macOS and Linux). Run them from the repository root unless a step says otherwise.

## Before you start (Windows)

- **Clone to a short path**, such as `C:\src\flowlens`. Some saved evidence files have long paths, and a clone into a deeply nested folder can fail with `Filename too long`. Alternatively, clone with long paths enabled:

  ```powershell
  git -c core.longpaths=true clone https://github.com/ryanyipp/ai-native-assessment.git
  ```

- **Free disk space** (Docker path): see the storage note under Option A.

## What runs where

| Service | Port | What it is |
|---|---|---|
| Frontend | 5173 | The FlowLens UI. It proxies `/api` to the backend. |
| Backend API | 8000 | FastAPI, SQLite and Playwright Chromium. The browser engine and all model calls run here. |
| creator-studio, broken | 5174 | Fixture app with a seeded past-date defect. The launcher's default target. |
| creator-studio, corrected | 5175 | The same app with the defect fixed. |
| ticket-desk, broken | 5176 | Fixture app with seeded defects (used in the demo video). |
| ticket-desk, corrected | 5177 | Its corrected build. |
| leave-desk, broken | 5178 | Fixture app with seeded defects. |
| leave-desk, corrected | 5179 | Its corrected build. |

The fixtures are review targets. Their source and `evaluation/` are never given to the runtime agents. Each fixture creates its own data file on first use. Which fixtures were used in which evaluation is described in [model-comparison.md](model-comparison.md) and the fixture READMEs.

## Configuration (optional)

Every setting has a default in `backend/src/flowlens/config.py`, and empty values fall back to it. You only need a `.env` file for live reviews or to change a default. The backend reads `.env` from the repository root; Docker Compose passes it to the backend container if it exists. `.env` is git-ignored and never copied into an image.

Create it from the template **only if you do not already have one**. A plain copy overwrites an existing `.env`, so these commands check first:

PowerShell:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

bash:

```sh
[ -f .env ] || cp .env.example .env
```

| Setting | Needed for | Notes |
|---|---|---|
| `OPENROUTER_API_KEY` | Live reviews only | Without it the UI works, saved and demo runs can be inspected and previews work, but **Start live run** is disabled. Server side only; never sent to the browser. |
| `OPENROUTER_MODEL` | | Default `google/gemini-3-flash-preview`. The launcher offers it first, then the benchmarked models. |
| `FLOWLENS_BUDGET_USD`, `FLOWLENS_RUN_BUDGET_USD` | | The overall credit pool (10) and the per-run cap (0.50). The pool counts runs made by this installation, not imported demos. |
| `FLOWLENS_MAX_OUTPUT_TOKENS`, `FLOWLENS_MAX_MODEL_CALLS_PER_RUN` | | Output cap per call (800) and calls per run (40). The launcher always sends its own limits, 60 calls by default, so the 40 applies only to API requests without limits. |
| `FLOWLENS_ALLOWED_ORIGINS` | | Fixture origins that get test-data workspaces. The default covers ports 5174–5179 on `localhost` and `127.0.0.1`; Docker Compose adds the named hosts such as `ticket-broken.localhost`. Change it only if you move the fixtures. Other websites are approved in the launcher. |
| `DATABASE_URL`, `ARTIFACTS_DIR` | | Default `artifacts/flowlens.db` and `artifacts/` in the repository root, both git-ignored. |
| `FRONTEND_PORT` | | The frontend port and the backend's allowed CORS origin (5173). |
| `FLOWLENS_API_URL` | | The backend URL the frontend proxies to (`http://127.0.0.1:8000`). Read by the frontend server; set it when the backend uses another port. |

Budget limits are checked **before** each call, so a call that starts under a limit can finish over it (at most one call per concurrent slot). This is a software guard, not a billing cap. Hitting a limit marks the run `partial`, never passing.

## Option A: Docker Compose

**Prerequisite:** Docker Desktop (Windows, macOS) or Docker Engine (Linux) with Compose v2.24 or later, running.

**Storage.** The first build downloads about 1–2 GB, but it needs more space than that: on 2 Nov 2026 the built images were about 2.2 GB (backend) and 0.8 GB (frontend), plus build cache and the data volume. Keep at least 8 GB free. On Windows, Docker Desktop keeps this in a virtual disk on `C:` that grows and does not shrink on its own; a build that fills the disk can stop Docker Desktop.

**Start** (any shell):

```sh
docker compose up --build
```

Leave that terminal running and open http://localhost:5173. To run in the background instead, add `-d`; stop with `docker compose down`.

- **Recorded runs:** loaded into the data volume at start, without an API key or model calls. Choose **Explore recorded demos**. To skip loading them, set `FLOWLENS_LOAD_DEMO=0` (see the port example below for the syntax).
- **Live reviews:** put `OPENROUTER_API_KEY` in `.env` (see Configuration), then restart the stack so the backend reads it: `docker compose down`, then `docker compose up -d`. This keeps your data.
- **Ports in use:** change the host side of a port. The targets inside FlowLens keep using `http://localhost:5174` and so on, because every service shares the backend's network namespace.

  PowerShell:

  ```powershell
  $env:FRONTEND_HOST_PORT='15173'; $env:BACKEND_HOST_PORT='18000'; docker compose up --build
  ```

  bash:

  ```sh
  FRONTEND_HOST_PORT=15173 BACKEND_HOST_PORT=18000 docker compose up --build
  ```

  Fixture host ports use `CREATOR_BROKEN_HOST_PORT`, `CREATOR_CORRECTED_HOST_PORT`, `TICKET_BROKEN_HOST_PORT`, `TICKET_CORRECTED_HOST_PORT`, `LEAVE_BROKEN_HOST_PORT` and `LEAVE_CORRECTED_HOST_PORT`.
- **Reset everything:** `docker compose down -v` removes the containers **and the data volume**: the database, artifacts and fixture data, including any live runs you made.

## Option B: Native

**Prerequisites:**

- **Python 3.12** (exactly: `backend/pyproject.toml` requires `>=3.12,<3.13`) and **uv**. On Windows: `py -3.12 -m pip install --user uv`. On macOS or Linux: `pipx install uv`.
- **Node 22 or later** with npm 10, and Git.
- About 300 MB for Chromium, downloaded by Playwright. On Linux, `--with-deps` also installs system libraries and needs `sudo`.

### Install (once)

PowerShell:

```powershell
cd backend
py -3.12 -m uv sync --frozen
.\.venv\Scripts\python -m playwright install chromium
.\.venv\Scripts\python -m flowlens.demo load        # recorded runs; no key, no model calls
cd ..\frontend
npm ci
cd ..
```

bash:

```sh
cd backend
uv sync --frozen
.venv/bin/python -m playwright install --with-deps chromium
.venv/bin/python -m flowlens.demo load
cd ../frontend
npm ci
cd ..
```

For live reviews, create `.env` and add your key as described under Configuration.

### Start (one terminal per service)

Each service keeps running in its own terminal. Open each terminal **in the repository root**. You need the backend, the frontend and at least the fixture you want to review; the launcher's default target is creator-studio broken (terminal 1).

The corrected builds are selected with environment variables. In PowerShell, `$env:` settings stay for the rest of that terminal's session, so give each fixture its own terminal.

PowerShell:

```powershell
# Terminal 1: creator-studio, broken (5174)
backend\.venv\Scripts\python -m uvicorn app:app --app-dir fixtures\creator-studio --host 127.0.0.1 --port 5174
```

```powershell
# Terminal 2: creator-studio, corrected (5175)
$env:CREATOR_STUDIO_MODE='corrected'; $env:CREATOR_STUDIO_DATA='fixtures\creator-studio\data\corrected.json'
backend\.venv\Scripts\python -m uvicorn app:app --app-dir fixtures\creator-studio --host 127.0.0.1 --port 5175
```

```powershell
# Terminal 3: ticket-desk, broken (5176)
backend\.venv\Scripts\python -m uvicorn app:app --app-dir fixtures\ticket-desk --host 127.0.0.1 --port 5176
```

```powershell
# Terminal 4: ticket-desk, corrected (5177)
$env:TICKET_DESK_MODE='corrected'; $env:TICKET_DESK_DATA='fixtures\ticket-desk\data\corrected.json'
backend\.venv\Scripts\python -m uvicorn app:app --app-dir fixtures\ticket-desk --host 127.0.0.1 --port 5177
```

```powershell
# Terminal 5: leave-desk, broken (5178)
backend\.venv\Scripts\python -m uvicorn app:app --app-dir fixtures\leave-desk --host 127.0.0.1 --port 5178
```

```powershell
# Terminal 6: leave-desk, corrected (5179)
$env:LEAVE_DESK_MODE='corrected'; $env:LEAVE_DESK_DATA='fixtures\leave-desk\data\corrected.json'
backend\.venv\Scripts\python -m uvicorn app:app --app-dir fixtures\leave-desk --host 127.0.0.1 --port 5179
```

```powershell
# Terminal 7: backend API (8000)
cd backend
.\.venv\Scripts\python -m uvicorn flowlens.main:app --host 127.0.0.1 --port 8000
```

```powershell
# Terminal 8: frontend (5173)
cd frontend
npm run dev
```

bash: the same eight terminals, with `backend/.venv/bin/python` instead of `backend\.venv\Scripts\python`, forward slashes in paths, and `export VAR=value` (or `VAR=value command`) instead of `$env:VAR='value'`. For example:

```sh
# Terminal 2: creator-studio, corrected (5175)
CREATOR_STUDIO_MODE=corrected CREATOR_STUDIO_DATA=fixtures/creator-studio/data/corrected.json \
  backend/.venv/bin/python -m uvicorn app:app --app-dir fixtures/creator-studio --host 127.0.0.1 --port 5175
```

Open http://localhost:5173.

## Recorded demo runs (no API key)

`demo/` holds eight saved runs: their records plus the screenshots and page records they reference. All but the last were recorded on earlier code (29 Oct 2026); they are shown as recorded, not re-run.

| Run | What it shows |
|---|---|
| `run_a572a9bf88c5` | A sequential review of creator-studio (broken): the past-date defect confirmed by an independent verifier. |
| `run_d50048493cc5` | A shared-queue review of ticket-desk (corrected) that drained its queue. |
| `run_a54099283d9d` | A shared-queue review that stopped early (partial) at its exploration budget. |
| `run_53d7009ff711` | A run that stopped on an internal error (failed). |
| `run_fc9eba62a54c` | The single-agent baseline: a finding confirmed only by self-check. |
| `run_15f19bf8bb46` | A public website (TodoMVC) explorer run; its checkbox claims are not evaluated. |
| `run_40e786578fef` | A re-check of an earlier finding on the corrected build: not reproduced. |
| `run_7bbdcc167bb6` | The run in the demo video (2 Nov 2026): a shared-queue review of ticket-desk (broken) with the goal "Test and check the pages and inputs". T1 (7 tickets accepted) and T4 (cancelled booking still listed) were each confirmed in two replays. |

Docker loads them at start; the native install loads them with `python -m flowlens.demo load` (above), with the backend stopped or running.

- **No API key and no model or website calls:** loading copies records into the configured database and artifacts folder.
- **Repeat-safe:** runs that already exist are skipped; `--replace` re-imports them.
- **Labelled:** every loaded run is marked as imported. The run header shows **Recorded demo result**, Diagnostics and the report say where it came from, and nothing is re-run.
- **Viewing them:** choose **Explore recorded demos** on the landing page (`/`), or open a run from the run history and use Map, Browser, Evidence, Activity, Findings and **Report**.
- **Making new runs** needs the fixtures and an API key.

## Checks

Offline checks, no model calls. PowerShell, from the repository root:

```powershell
cd backend
.\.venv\Scripts\python -m pytest -q      # starts its own fixture servers
cd ..\frontend
npm run lint
npm run build                            # runs tsc -b first
cd ..
```

bash: the same, with `.venv/bin/python` and `cd ../frontend`.

**Browser checks** (`scripts/ui_check_*.py`, `scripts/check_setup.py`) drive the UI against saved runs, with the backend and frontend running. They make no model calls and work without an API key. Runs they need are loaded automatically from `demo/` or `scripts/check-runs/` (saved runs used only by these checks); existing runs are skipped. If a prerequisite is missing, a script prints `MISSING PREREQUISITE` and exits with code 3. `check_setup.py` needs a backend with no API key.

**Paid scripts** need an explicit `--live`: `ui_check_workspace.py`, `ui_check_public_site.py`, `checkpoint2_eval.py` and `eval_batch.py`. Without it, the last two start nothing and exit with code 2.

### Continuous integration

`.github/workflows/ci.yml` runs on pushes to `main` and on pull requests, on Ubuntu 24.04 with no secrets:

- **Backend:** `uv` with Python 3.12, `uv sync --frozen`, `uv run --frozen python -m playwright install --with-deps chromium`, then `uv run --frozen pytest -q`. Browser tests drive the local fixture apps and agents use mocked model clients. The model URL points at a dead local port and the key is empty, so no paid call can succeed.
- **Frontend:** Node 22, `npm ci`, `npm run lint`, `npm run build`.

CI does not cover live model runs, the evaluation batches, the browser checks, Docker Compose or public websites, and there is no deployment step. A green run means these automated checks passed, not that a live review works.

## Which setup paths have been tested

[setup-verification.md](setup-verification.md) is a **historical record from 30 Oct 2026**: native setup (commit `5b8ae14`) and Docker Compose (commit `a2e9a47`), each from a clean clone on Windows 11, both passed. The code has changed a lot since; those checks were not repeated on the current code. A clean-clone Docker check on 2 Nov 2026 (commit `9609f6e`) did not finish because the test machine ran out of disk space, so current clean-clone setup is **unverified**. The recovered existing Docker stack on that machine was checked with saved runs only.

## Maintainers: exporting demo runs

Re-export saved runs into `demo/` with:

```sh
python -m flowlens.demo export RUN_ID ... --note RUN_ID=TEXT
```

Run it from `backend/` with the project environment. It reads the configured database and writes into `demo/`. For a run stored in the Docker volume, run it inside the backend container with `--bundle` pointing at a temporary folder, then copy the run out. Check the bundle for secrets and personal paths before committing, and update the run count in `backend/tests/unit/test_demo_bundle.py`.
