# Attribution

- No code was reused from agentic-test-explorer or other projects. Everything in `backend/`, `fixtures/` and `frontend/src/` is new.
- `frontend/` was scaffolded with `npm create vite` (react-ts template). Template files were then replaced or edited.
- Libraries: FastAPI, Pydantic, Playwright, httpx, uvicorn, React, React Flow (`@xyflow/react`), Tailwind CSS, Vite, dagre, Radix UI primitives, Lucide icons, Inter and JetBrains Mono (via Fontsource), and axe-core (dev), each under its own licence. They are used as dependencies, not copied.
- Assistant contributions: Claude (lead session) wrote the checkpoint 0–1 code, tests and docs, the workspace UI redesign and its browser checks, and all of checkpoint 2: the fixture scheduling form, contracts, input-tester and verifier agents, review orchestration, assertion evaluator, UI extensions, tests and evaluation scripts. Ryan reviews it.
- Checkpoint 2 added no new dependencies.
- Checkpoint 3 (shared queue, queue_review workers, task board, tests and checks) was written by Claude (lead session) and added no new dependencies.
- Checkpoint 4 (leases, fencing, recovery, fault injection, call reservation) was written by Claude (lead session) and added no new dependencies.
- Later work was also written by Claude: the lead session plus a second, parallel Claude session in the same repository. It covers the reports, the evaluation scripts and batches, the ticket-desk and leave-desk fixtures, exploration memory, form-control handling, execution-failure handling, the verifier's applicability check, the evidence dialog and the landing page. Every commit after the initial one carries a Claude co-author trailer. Ryan chose the scope, ran and recorded the demos, and reviewed the changes.
- No dependency was added after 29 Oct 2026, the last change to `backend/pyproject.toml` or `frontend/package.json`.
- The landing-page demo video was recorded by Ryan and re-encoded with ffmpeg (H.264). ffmpeg was used as a local tool, not as a project dependency.
