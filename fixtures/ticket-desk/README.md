# ticket-desk fixture (held-out evaluation app)

A second small app with explicit rules and its own broken and corrected builds. It was frozen before any agent ran against it; prompts were not tuned on it.

```powershell
backend\.venv\Scripts\python -m uvicorn app:app --app-dir fixtures\ticket-desk --port 5176
$env:TICKET_DESK_MODE='corrected'; $env:TICKET_DESK_DATA='fixtures\ticket-desk\data\corrected.json'; backend\.venv\Scripts\python -m uvicorn app:app --app-dir fixtures\ticket-desk --port 5177
```

- `TICKET_DESK_MODE` and `TICKET_DESK_DATA` are evaluation-only.
- Workspaces use the `td_ws` cookie and `POST /__fixture/workspaces`.
- The expected defects are only in `evaluation/ticket-desk/answer_key.json`.
