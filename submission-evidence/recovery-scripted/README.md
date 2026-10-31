# Scripted recovery and cancellation evidence

**Scripted evidence.** The model is a scripted stand-in (`mocked_model: true`, `live: false`), so these runs show coordinator behaviour, not model quality. The API, queue, coordinator, real Chromium and creator-studio broken fixture are real. Code commit: `f1c689d`.

For real-model recovery evidence, see `../checkpoint-4/` (`run_248eaaa2a5cd`, made by older code).

## Reproduce

The website under review is `http://localhost:5174/`. The failure does not come from the website: it comes from `fault_injection` on `POST /api/runs`, with `stall_s: 75` and `task_lease_s: 45`.

```powershell
docker compose up -d
backend\.venv\Scripts\python scripts\scripted_server.py --port 8010
backend\.venv\Scripts\python scripts\recovery_demo.py
```

Cancellation, in three terminals:

```powershell
backend\.venv\Scripts\python scripts\scripted_server.py --port 8011 --delay 3 --data artifacts\scripted-cancel
cd frontend; $env:FRONTEND_PORT='5273'; $env:FLOWLENS_API_URL='http://127.0.0.1:8011'; npm run dev
backend\.venv\Scripts\python scripts\cancel_demo_check.py artifacts\scripted-cancel\out http://127.0.0.1:5273 http://127.0.0.1:8011 SERVER_PID
```

`scripted_server.py` needs a backend environment with dev dependencies and uses its own data folder. Its model URL is dead and its key is a placeholder, so it cannot spend credit.

## Recovery: `run_2093b8a0a670`

| Seq | Time (UTC) | Event |
|---|---|---|
| 202 | 19:51:10.042 | explorer-a claims `explore:start`, attempt `att_a68db0338a35` |
| 205 | 19:51:11.530 | Injected: explorer-a stalls for 75 s |
| 206 | 19:51:56.292 | Lease expires after 45 s; attempt revoked |
| 207 | 19:51:56.318 | Coordinator closes its browser context |
| 208 | 19:51:56.350 | Task re-queued, explorer-a excluded |
| 209 | 19:51:56.444 | explorer-b claims it (attempt 2) |
| 226-227 | 19:51:59.5 | explorer-b completes it; `task_recovered` |
| 295 | 19:52:26.606 | explorer-a wakes; its model call is refused |
| 296 | 19:52:26.713 | Its late result is rejected |
| 297 | 19:52:27.199 | Run completed; R5 confirmed |

All 8 checks passed (`recovery-output.txt`).

## Cancellation

`run_2cd82458d7ba`, `run_621f15e4c865` and `run_3d0d5bfbed86` were each started and cancelled through the real UI. Each passed 18/18 checks (`cancel-output.txt` holds the last). `cancelled-run.png` shows the terminal state.
