# creator-studio fixture

A minimal creator dashboard used as FlowLens's controlled review target.
Synthetic data only. Drafts persist in `data/drafts.json` (ignored by Git).

Start (from the repository root, using the backend environment):

```powershell
backend\.venv\Scripts\python -m uvicorn app:app --app-dir fixtures\creator-studio --port 5174
```

`POST /__fixture/reset` clears drafts for tests. Runtime agents receive only the
browser and supplied requirements, never this source.
