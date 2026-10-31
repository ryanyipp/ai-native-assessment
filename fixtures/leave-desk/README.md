# leave-desk fixture (held out)

A third small app: an employee leave-request site with its own broken and corrected builds.

**Status:** held out. It was frozen before any agent ran on it, and no FlowLens evaluation has used it yet.

```powershell
backend\.venv\Scripts\python -m uvicorn app:app --app-dir fixtures\leave-desk --port 5178
$env:LEAVE_DESK_MODE='corrected'; $env:LEAVE_DESK_DATA='fixtures\leave-desk\data\corrected.json'; backend\.venv\Scripts\python -m uvicorn app:app --app-dir fixtures\leave-desk --port 5179
```

- `LEAVE_DESK_MODE` and `LEAVE_DESK_DATA` are evaluation-only.
- Workspaces use the `ld_ws` cookie and `POST /__fixture/workspaces`. Each starts with the same seeded requests and profile.
- The expected defects are only in `evaluation/leave-desk/answer_key.json`.
- `scripts/check_leave_desk.py` checks both builds with Playwright and no model calls.
