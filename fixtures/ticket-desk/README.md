# ticket-desk fixture (known regression fixture)

A second small app with explicit rules and its own broken and corrected builds.

**Status:** it was held out for one evaluation (`batch-heldout`), frozen before any agent ran on it. Its defects are now known, and the correctness pass was written after seeing those results. It is therefore a **known regression fixture**: later runs on it are regression checks, not held-out evidence.

```powershell
backend\.venv\Scripts\python -m uvicorn app:app --app-dir fixtures\ticket-desk --port 5176
$env:TICKET_DESK_MODE='corrected'; $env:TICKET_DESK_DATA='fixtures\ticket-desk\data\corrected.json'; backend\.venv\Scripts\python -m uvicorn app:app --app-dir fixtures\ticket-desk --port 5177
```

- `TICKET_DESK_MODE` and `TICKET_DESK_DATA` are evaluation-only.
- Workspaces use the `td_ws` cookie and `POST /__fixture/workspaces`.
- The expected defects are only in `evaluation/ticket-desk/answer_key.json`.
