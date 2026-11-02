# Live injected-stall runs (2 Nov 2026)

Three real-model runs with a deliberately injected stall. `run_b77f96c4fdc7` ran on the submitted fixes and is the reference result; the two earlier runs below exposed the problems those fixes address and are kept unchanged.

## `run_b77f96c4fdc7`: recovery and both defects confirmed (submitted code)

**Real-model evidence with a deliberately injected failure.** `google/gemini-3-flash-preview` through OpenRouter (`live: true`, `mocked_model: false`, `injected_failure: true`), real Chromium, Ticket Desk broken build. Started from the launcher with **Inject a stall**.

**Code.** Backend commit `7fdb5ac`, source fingerprint `3ccb720d7bd0cec1`; the running container's backend and frontend source matched `7fdb5ac` file for file.

**Configuration.** Target `http://ticket-broken.localhost:5176/`, `queue_review`, goal "Test and check the pages and inputs", requirements T1–T4 (in the record). Fault `{worker: explorer-a, task_type: explore, stall_s: 75}`, `task_lease_s: 45`. Other limits: 60 model calls, US$0.50, 2 verification replays, launcher defaults otherwise.

**Files.** `run_b77f96c4fdc7/` is the export made by `python -m flowlens.demo export`: `records.json` (521 records, 182 events) and `files/` (192 screenshots, observations, handoffs and model-call records). Every evidence file is present and matches its recorded SHA-256, and every artifact referenced by actions, transitions, findings and verifications is included; `.gitattributes` keeps this folder byte-exact. `run_b77f96c4fdc7-detail.json` is the same run as returned by `GET /api/runs/{id}`. The folder has the same layout as a run in `demo/runs/`.

### Timeline (seconds after the stall)

| Event | Time (UTC) | After stall | What was recorded |
|---|---|---|---|
| 8795 | 15:17:42.400 | – | explorer-a claims `explore:start`, attempt `att_99ba1f068dd9` |
| 8798 | 15:17:43.267 | 0 s | **Injected:** explorer-a stalls for 75 s with its browser context open (lease 45 s) |
| 8799 | 15:18:28.214 | 44.9 s | Lease expired: no action or model call for 45 s; attempt revoked |
| 8800 | 15:18:28.239 | 45.0 s | Coordinator closes explorer-a's browser context |
| 8801 | 15:18:28.278 | 45.0 s | Task returned to the queue, explorer-a excluded |
| 8802 | 15:18:28.390 | 45.1 s | explorer-b claims attempt 2 in its own context and workspace |
| 8822 | 15:18:36.884 | 53.6 s | Task recovered: completed by explorer-b |
| 8912 | 15:18:58.310 | 75.0 s | explorer-a resumes |
| 8914 | 15:18:58.394 | 75.1 s | **Refused:** explorer-a's follow-up-task write (`late_action_rejected`) |
| 8915 | 15:18:58.415 | 75.1 s | **Rejected:** explorer-a's late result (`result_rejected`) |
| – | 15:19:12.037 | 88.8 s | Run finished |

**Safety result.** After its lease expired, the expired attempt queued no follow-up tasks and recorded no browser actions; the task kept explorer-b's result. Its refused write and rejected result remain recorded as events (8914, 8915), with the stall itself labelled `[INJECTED FAULT]`.

### Outcome

`completed`, 12 model calls (6 exploration, 4 testing, 2 verification), US$0.0160535 reported, 89.8 s from creation to finish. 4 test cases, 2 candidates, both confirmed:

| Requirement | Tester input | Verifier assertion | Replay 1 | Replay 2 |
|---|---|---|---|---|
| T1 | 7 tickets (Bob, bob@example.com) | `validation_message_present`, field `Tickets` | confirmed | confirmed |
| T4 | Cancel the booking, check page `/` | `text_or_value_retained`, `expected: "Harbour Jazz Night · 2 ticket(s)"`, `expect_present: false` | confirmed | confirmed |

The verifier judged both requirements applicable (to `Tickets` and `Yes, cancel booking`). For T4 the listed text was on the check page before the cancellation, so the removal check was meaningful.

**Independence.** Each finding was reported by the input tester and verified by the separate verifier worker, in fresh browser contexts and workspaces, without seeing the tester's verdict. It still shares the tester's model (the same Gemini model for every worker) and repeats the tester's recorded reproduction steps, so a wrong step or a shared model blind spot would affect both.

## Earlier runs (before the fixes)

**Real-model evidence with an injected failure.** Both runs below used `google/gemini-3-flash-preview` through OpenRouter (`live: true`, `mocked_model: false`), real Chromium and a broken fixture build, and were started from the launcher with **Inject a stall** (`injected_failure: true`, `[INJECTED FAULT]` events; 75 s stall, 45 s lease). The backend was the Docker build from `52ec5a7`-era code; the frontend included the launcher fix `5cbc0b1`. Both files are full API records, exported unchanged. The runs also stay in the demo database.

### `run_c19d17f7a20d`: Creator Studio, recovery and a late write

- **Recovery worked.** explorer-a stalled at 14:34:36 UTC; its lease expired at 14:35:20.9, its browser context was closed, the task was reassigned, explorer-b claimed it 0.3 s later and completed it, and explorer-a's late result was rejected at 14:35:51.2. Run `completed`, US$0.012.
- **Late write.** After waking, explorer-a made no model call or browser action, but queued a ready explore task (event 8552) before its result was rejected. This led to the fix that refuses follow-up tasks from an expired attempt (`backend/tests/unit/test_late_writes_and_removal_checks.py`).
- **No verification:** the requirements box was empty, so the three findings stayed review observations.

### `run_2ddb5120a763`: Ticket Desk, a false "not reproduced"

- **Recovery worked**, as above (lease expired 14:38:55.7, late result rejected 14:39:25.9). Run `completed`, US$0.016. T1 was confirmed in both replays.
- **T4 was wrongly not reproduced.** The tester saw the cancelled booking still listed. The verifier chose `text_or_value_retained` for booking id `843f9467` with `expect_present: false`. The check page never shows booking ids, so the check held trivially in both replays and the defect read as gone. In the demo-video run `run_7bbdcc167bb6`, the verifier checked the listed booking text and confirmed T4.
- **Guard added afterwards:** a removal check now needs its text on the check page before the action in the same replay. Applied to this run's saved check-page observations, it rejects both replays as inconclusive; applied to `run_7bbdcc167bb6` and `run_316a8e760e37`, it leaves their confirmed T4 replays unchanged. The record here is from before the guard and shows the original outcome.
