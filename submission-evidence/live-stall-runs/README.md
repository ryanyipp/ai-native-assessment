# Live injected-stall runs (2 Nov 2026)

**Real-model evidence with an injected failure.** Both runs used `google/gemini-3-flash-preview` through OpenRouter (`live: true`, `mocked_model: false`), real Chromium and a broken fixture build, and were started from the launcher with **Inject a stall** (`injected_failure: true`, `[INJECTED FAULT]` events; 75 s stall, 45 s lease). The backend was the Docker build from `52ec5a7`-era code; the frontend included the launcher fix `5cbc0b1`. Both files are full API records, exported unchanged. The runs also stay in the demo database.

## `run_c19d17f7a20d`: Creator Studio, recovery and a late write

- **Recovery worked.** explorer-a stalled at 14:34:36 UTC; its lease expired at 14:35:20.9, its browser context was closed, the task was reassigned, explorer-b claimed it 0.3 s later and completed it, and explorer-a's late result was rejected at 14:35:51.2. Run `completed`, US$0.012.
- **Late write.** After waking, explorer-a made no model call or browser action, but queued a ready explore task (event 8552) before its result was rejected. This led to the fix that refuses follow-up tasks from an expired attempt (`backend/tests/unit/test_late_writes_and_removal_checks.py`).
- **No verification:** the requirements box was empty, so the three findings stayed review observations.

## `run_2ddb5120a763`: Ticket Desk, a false "not reproduced"

- **Recovery worked**, as above (lease expired 14:38:55.7, late result rejected 14:39:25.9). Run `completed`, US$0.016. T1 was confirmed in both replays.
- **T4 was wrongly not reproduced.** The tester saw the cancelled booking still listed. The verifier chose `text_or_value_retained` for booking id `843f9467` with `expect_present: false`. The check page never shows booking ids, so the check held trivially in both replays and the defect read as gone. In the demo-video run `run_7bbdcc167bb6`, the verifier checked the listed booking text and confirmed T4.
- **Guard added afterwards:** a removal check now needs its text on the check page before the action in the same replay. Applied to this run's saved check-page observations, it rejects both replays as inconclusive; applied to `run_7bbdcc167bb6` and `run_316a8e760e37`, it leaves their confirmed T4 replays unchanged. The record here is from before the guard and shows the original outcome.
