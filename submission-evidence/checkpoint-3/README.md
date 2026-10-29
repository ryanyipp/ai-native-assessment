# Checkpoint 3 evidence: shared queue with two explorers

`run_72e3868cc54e-detail.json` is the full API record of the live run. It includes tasks, events, states with sightings, handoffs, test cases, verifications and model calls. The run used real Chromium, `google/gemini-3-flash-preview` through OpenRouter, and the broken fixture build on :5174. It was started with `POST /api/runs`, `mode: queue_review`.

- **Result:** partial. Explorer budget share used; 2 explore tasks unfinished; 1 tester task blocked by a truncated model reply.
- **Usage:** 21 calls (explorer-a 10, explorer-b 6, input-tester 4, verifier 1), 25,431 tokens, US$0.0361 reported.
- **Claims:** explorer-a 4 tasks, explorer-b 3, input-tester 2, verifier 2. Each was claimed once, with its own attempt id and lease.
- **Handoffs:**
  - `form_to_tester` explorer-a → input-tester (×2: the draft form and the scheduling form);
  - `candidate_to_verifier` input-tester → verifier (×2). The R5 past-date candidate was **confirmed**; the observation without a requirement was **inconclusive**.
- **New work consumed:** the tester's outcome state "Scheduled post — Post scheduled." became `explore:ec74b49ccfe0be8e` (queued by input-tester), which explorer-b claimed and completed. A second tester state was claimed by explorer-a but stopped unfinished when the budget share ran out.
- **Dependencies:** both verify tasks `depends_on` the scheduling-form test task and were claimed only after it finished.
- **Isolation:** every task, test case and replay used its own context and workspace (9 of 9 worker/task groups distinct). Five states carry sightings from more than one worker.

Screenshots: `docs/checkpoint-3/queue-map.png`, `queue-activity.png`, `queue-task-board.png`.
