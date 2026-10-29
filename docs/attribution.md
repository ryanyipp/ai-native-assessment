# Attribution

- No code was reused from agentic-test-explorer or other projects. Everything in `backend/`, `fixtures/` and `frontend/src/` is new.
- `frontend/` was scaffolded with `npm create vite` (react-ts template). Template files were then replaced or edited.
- Libraries: FastAPI, Pydantic, Playwright, httpx, uvicorn, React, React Flow (`@xyflow/react`), Tailwind CSS, Vite, dagre, Radix UI primitives, Lucide icons, Inter and JetBrains Mono (via Fontsource), and axe-core (dev), each under its own licence. They are used as dependencies, not copied.
- Assistant contributions: Claude (lead session) wrote the checkpoint 0–1 code, tests and docs, the workspace UI redesign and its browser checks, and all of checkpoint 2: the fixture scheduling form, contracts, input-tester and verifier agents, review orchestration, assertion evaluator, UI extensions, tests and evaluation scripts. Ryan reviews it.
- Checkpoint 2 added no new dependencies.
