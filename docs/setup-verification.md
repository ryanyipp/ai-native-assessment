# Setup verification (2026-10-30)

Every test ran from a **separate `git clone` of the committed repository**, made in a temporary folder outside this checkout.

- **Commits tested:** `5b8ae14` for the native path. `a2e9a47` for Docker; it adds the Compose fix found during testing and the smoke-check script.
- **What the clone had:** no `.env`, no API key in the environment, no virtual environment, no `node_modules`, no database and no artifacts.
- **Isolation:** the clone's servers used other ports, so the servers already running from the main checkout were not used or changed. No model calls were made.

## Paths tested

| Path | Result |
|---|---|
| **Native, Windows 11, PowerShell/Git Bash** | Passed |
| `py -3.12 -m uv sync --frozen` (new `.venv`) | OK (2.7 s: packages came from this machine's uv download cache) |
| `python -m playwright install chromium` into a **new, empty** `PLAYWRIGHT_BROWSERS_PATH` | OK: Chromium 1248 and the headless shell downloaded (1 min 12 s) |
| `npm ci` (new `node_modules`) | OK (18 s; npm's download cache was available) |
| `python -m flowlens.demo load` into the empty database | 7 runs loaded; 562 evidence files, **0 SHA-256 mismatches** |
| `npm run build`, `npm run lint` | OK |
| `uv run --frozen pytest -q` (Chromium from the new browser path) | **75 passed** |
| Fixtures on 6174–6177, backend on 18000, frontend on 15173 (`FLOWLENS_ALLOWED_ORIGINS`, `FRONTEND_PORT`, `FLOWLENS_API_URL`) | Running |
| `scripts/check_setup.py` | **18/18**: health with no key, 7 demo runs loaded and labelled, previews of all four fixtures, live runs refused and disabled, map, findings, screenshot through the UI proxy, report banners, Markdown report for the failed run, no page errors |
| **Docker Compose, Docker Desktop 29.1.3 (Linux engine), Compose v5.0.1** | Passed |
| First `docker compose build` | **Failed:** every fixture service declared the same build and image tag, so the parallel builds collided ("image … already exists"). Fixed in `a2e9a47`: only the backend builds, and the fixtures reuse its image with `pull_policy: never`. |
| `docker compose build --no-cache --pull` | OK in 2 min 39 s, including `playwright install --with-deps chromium` (system libraries plus a fresh Chromium download). Images: backend 2.23 GB, frontend 791 MB. |
| `docker compose up -d` with host ports 25173, 28000 and 25174–25177 | All six services running; the 7 demo runs loaded at start |
| `scripts/check_setup.py` against the stack (fixtures previewed at `http://localhost:5174`–`5177`, inside the shared namespace) | **18/18** |
| Fixture workspace creation inside the backend container (creator-studio, ticket-desk) | OK |
| Image contents | No `/app/.env` and no `/app/evaluation` |
| `docker compose restart backend` | The demo load skipped all 7 existing runs (7 runs, no duplicates) |
| `docker compose down -v` | Removed the test containers, network and volume. The images were kept. |

Screenshots: `setup-check-native-demo-report.png` (native) and `setup-check-docker-demo-run.png` (Docker).

## Not tested

- **Native setup on macOS or Linux.** The bash commands in `docs/setup.md` are written for them but were not run. On Linux, `--with-deps` needs `sudo`.
- **A live run in either setup.** No model calls were allowed. The path to the model was checked only up to the "no key: refused" response.
- **A machine without uv, npm or Docker download caches.** Downloads came from the internet, but uv and npm reused their local caches.
- Docker on a host other than Windows with Docker Desktop.
- `.env` with a real key inside Compose. Compose is set up to read it if present; that was not exercised.

## Also changed while preparing

- **`.env.example`** previously set `FLOWLENS_ALLOWED_ORIGINS` to 5174 and 5175 only, so copying it would have blocked ticket-desk. It is now empty, which uses the full default.
- **`.gitattributes`** keeps `demo/**` byte-exact. Line-ending conversion would otherwise change JSON evidence files and break their recorded hashes.
- **Frontend proxy:** the target and port are configurable (`FLOWLENS_API_URL`, `FRONTEND_PORT`), and `vite preview` uses the same proxy, as Docker does.
