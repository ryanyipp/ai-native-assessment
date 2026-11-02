# Launcher stall option: request and takeover (`run_2c08c8b801c9`)

**Scripted evidence with an injected failure.** The model is a scripted stand-in (`mocked_model: true`, `live: false`), and the stall is the launcher's **Inject a stall** option (`provenance.injected_failure: true`, `[INJECTED FAULT]` events). The launcher UI, API, queue, coordinator, real Chromium and the creator-studio broken fixture are real. No model cost (US$0.00, 9 scripted calls). No real-model run was made.

## What changed

Before `5cbc0b1`, the option sent a 75 s stall but no lease, so runs got the 300 s default and no takeover happened (`run_156b7b84dc3b`, `run_bcd20230e89c`, `run_89c829d6a0f5`; see `../current-code/README.md`). It now also sends `task_lease_s: 45` when the stall is enabled in shared-queue mode, and nothing extra otherwise.

## Request check (no run created)

`request-capture-output.txt`: `launcher_stall_check.py capture` filled the launcher in the browser and captured the `POST /api/runs` body, then aborted it before it reached the backend.

| Launcher state | `task_lease_s` | `fault_injection` |
|---|---|---|
| Shared queue, stall off | not sent (300 s default) | not sent |
| Shared queue, stall on | 45 | `explorer-a`, `explore`, 75 s |
| Stall ticked, then single agent selected | not sent | not sent |

Run against the rebuilt frontend container (`localhost:5173`, built from `5cbc0b1` source) and a local preview of the same build; both passed.

## Takeover through the launcher

The container UI can only reach the demo backend, which makes paid calls. So `launcher_stall_check.py e2e` submitted the form through a local preview of the same frontend build (port 5274) proxied to the scripted-model server (`scripts/scripted_server.py --port 8010`, commit `5cbc0b1`, backend fingerprint `04c1a114b98a63ef`). Limits came from the launcher: 60 calls, US$0.50, `task_lease_s` 45, `max_duration_s` 600.

| Seq | Time (UTC) | Event |
|---|---|---|
| 101 | 14:23:21.208 | Injected fault configured |
| 102 | 14:23:21.227 | explorer-a claims `explore:start`, attempt `att_90f2ee3a98f1` |
| 105 | 14:23:24.110 | explorer-a stalls for 75 s (lease 45 s) |
| 106 | 14:24:08.725 | Lease expires; attempt revoked |
| 107 | 14:24:08.769 | Its browser context is closed |
| 108 | 14:24:08.807 | Task returned to the queue, explorer-a excluded |
| 109 | 14:24:09.042 | explorer-b claims attempt 2 in its own context and workspace, starting from the start URL |
| 127 | 14:24:14.571 | Task recovered, completed by explorer-b |
| 186 | 14:24:39.312 | explorer-a resumes |
| 189 | 14:24:39.909 | explorer-a's ending code queues a `skipped` explore task (see below) |
| 190 | 14:24:39.947 | explorer-a's late result rejected |
| 197 | 14:24:41.608 | Run completed |

`activity-recovery.png` shows these events in the Activity tab.

**Recovery: takeover succeeded.** `extra-checks-output.txt`: 11 of 12 checks passed. Check 5a ("late model call refused") found no refused call because explorer-a made none: on waking, exploration memory showed nothing left for it, so it stopped without a model call or browser action. There was nothing to refuse; the late result was still rejected.

**Run status:** `completed` (6 tasks done, 1 skipped). This is separate from recovery.

## Gap found

After its lease expired, explorer-a still wrote one queue record: a `skipped` explore task (event 189) from the end of its explore task, which queues follow-up tasks for states it recorded before the stall. That step does not check that the attempt is still current. The task was skipped, so no work ran from it, and the result itself was rejected. In `../current-code/` explorer-a's late model call was refused first, so it never reached that step. Not fixed here.
