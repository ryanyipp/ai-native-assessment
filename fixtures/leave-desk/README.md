# leave-desk fixture

A third small app: an employee leave-request site with its own broken and corrected builds.

**Status:** no longer held out. The app and answer key were frozen in `1731eeb` (1 Nov 2026) before any agent ran on it, and the app has not changed since. No scored evaluation batch uses it. On 2 Nov 2026, live runs on it (for example `run_35ace22b5bc8` and `run_118da630dc8b`) were used during development and led to code changes, so later results on it are development checks, not held-out evidence.

```powershell
backend\.venv\Scripts\python -m uvicorn app:app --app-dir fixtures\leave-desk --port 5178
$env:LEAVE_DESK_MODE='corrected'; $env:LEAVE_DESK_DATA='fixtures\leave-desk\data\corrected.json'; backend\.venv\Scripts\python -m uvicorn app:app --app-dir fixtures\leave-desk --port 5179
```

- `LEAVE_DESK_MODE` and `LEAVE_DESK_DATA` are evaluation-only.
- Workspaces use the `ld_ws` cookie and `POST /__fixture/workspaces`. Each starts with the same seeded requests and profile.
- The expected defects are only in `evaluation/leave-desk/answer_key.json`.
- `scripts/check_leave_desk.py` checks both builds with Playwright and no model calls.
