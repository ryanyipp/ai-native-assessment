# Stall recovery on the submitted code: `run_3e59bd16c130`

**Scripted evidence with an injected failure.** The model is a scripted stand-in (`mocked_model: true`, `live: false`); the stall comes from `fault_injection` (`provenance.injected_failure: true`, events prefixed `[INJECTED FAULT]`). The API, queue, coordinator, real Chromium and the creator-studio broken fixture are real. No model cost (US$0.00, 9 scripted calls).

## Code and configuration

- **Commit** `a97ef33`; backend source fingerprint `04c1a114b98a63ef`. Since `f1c689d`, which produced the earlier evidence in the parent folder, the queue, lease, watchdog and fencing code is unchanged, but the explorer task code around it changed (shared exploration memory, which also releases a revoked attempt's reservations). This rerun checks recovery with that code.
- **Server:** `scripts/scripted_server.py --port 8010 --data artifacts/scripted-recovery-2026-11-02`, run natively; its database and screenshots stay in that git-ignored folder.
- **Check:** `scripts/recovery_demo.py` with its documented settings: target `http://localhost:5174/`, `mode: queue_review`, limits `task_lease_s: 45`, `max_model_calls: 40`, `max_cost_usd: 0.5`, `max_duration_s: 300`, fault `{worker: explorer-a, task_type: explore, stall_s: 75}`. The stall (75 s) exceeds the lease (45 s), so the lease expires mid-stall.
- **Date:** 2 Nov 2026, 14:08–14:11 UTC.

## Timeline

| Seq | Time (UTC) | Event |
|---|---|---|
| 4 | 14:08:03.078 | explorer-a claims `explore:start`, attempt `att_97d6a2c1ea40` |
| 7 | 14:08:11.136 | Injected: explorer-a stalls for 75 s with its browser context open |
| 8 | 14:08:54.614 | Lease expires (no action or model call for 45 s); attempt revoked |
| 9 | 14:08:54.930 | Coordinator closes explorer-a's browser context |
| 10 | 14:08:55.206 | Task returned to the queue, explorer-a excluded |
| 11 | 14:08:55.881 | explorer-b claims it (attempt 2), opens the start URL in its own context and workspace |
| 28–29 | 14:09:16.1 | explorer-b completes the task; `task_recovered` |
| 34 | 14:09:26.499 | explorer-a wakes; its model call is refused |
| 36 | 14:09:28.167 | Its late result is rejected |
| 98 | 14:11:27.409 | Run completed; R5 confirmed |

## Results

**Recovery: passed.** `recovery-output.txt`: 8/8 checks of `recovery_demo.py`. `extra-checks-output.txt`: 12/12 further checks by `recovery_extra_checks.py` on the saved record, including that the context was fenced before the task was released, that explorer-b used a different context and workspace and began with the task's setup (opening the start URL), and that explorer-a recorded no browser action after expiry.

**Run status:** `completed` (queue drained, 6 tasks done; R5 confirmed). This is separate from recovery: a recovered run can still end `partial` for other reasons.

`run_3e59bd16c130-detail.json` is the full API record (run, tasks, events, actions, states, findings, verifications, model calls).

## Launcher stall option does not cause a takeover

The launcher's **Inject a stall** option sends `stall_s: 75` but no `task_lease_s`, so the run gets the default lease of 300 s. A 75 s stall is shorter than the lease: explorer-a resumes before it expires and no recovery happens. The three launcher-started injected runs in the demo database (`run_156b7b84dc3b`, `run_bcd20230e89c`, `run_89c829d6a0f5`) all have a 300 s lease and no `lease_expired`, `task_reassigned` or `result_rejected` event. Recovery is shown by API or script runs that set a lease shorter than the stall, as here and in `../checkpoint-4/`.
