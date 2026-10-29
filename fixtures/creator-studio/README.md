# creator-studio fixture

A minimal creator dashboard used as FlowLens's controlled review target.
Synthetic data only. Data persists in `data/drafts.json` (ignored by Git).
Supplied requirements are in `requirements.md`.

Start (from the repository root, using the backend environment):

```powershell
# Broken build (default) on :5174
backend\.venv\Scripts\python -m uvicorn app:app --app-dir fixtures\creator-studio --port 5174
# Corrected build on :5175
$env:CREATOR_STUDIO_MODE='corrected'; backend\.venv\Scripts\python -m uvicorn app:app --app-dir fixtures\creator-studio --port 5175
```

## Evaluation-only settings

These are environment variables for evaluation tooling. They never appear in
pages, and runtime agents never receive them.

| Variable | Default | Meaning |
|---|---|---|
| `CREATOR_STUDIO_MODE` | `broken` | `broken` accepts a past publish date; `corrected` rejects it with a validation message. This is the only behavioural difference. |
| `CREATOR_STUDIO_TODAY` | `2026-06-15` | Fixed studio clock, so "past date" tests are repeatable. The scheduling form shows it as "Studio date". |
| `CREATOR_STUDIO_DATA` | `data/drafts.json` | Data file. The checkpoint 0–1 flat draft format is read as the `default` workspace. |

## Data isolation

Records are stored per workspace, chosen by the `cs_ws` cookie (no cookie →
`default`). `POST /__fixture/workspaces` creates an empty workspace and returns
its id. FlowLens's harness calls it before every tester and verifier execution
and sets the cookie on a fresh browser context, so test cases cannot see each
other's posts or drafts.

`POST /__fixture/reset` clears all workspaces. Both harness endpoints are
POST-only, so a browsing agent cannot trigger them by navigating.
