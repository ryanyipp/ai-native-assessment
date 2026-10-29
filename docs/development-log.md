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
