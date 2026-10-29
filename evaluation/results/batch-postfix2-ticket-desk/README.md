# batch-postfix2-ticket-desk: live validation of 071c86c (POST-FIX REGRESSION, not held-out evidence)

ticket-desk is a known regression fixture. The code is 071c86c, plus tooling-only commit 0b31409 (staged run limit and scorer breakdown). One tracked process ran sequentially, with no fault injection. Scores are in `report.md`; full records are in `runs/`.

**Stage 1 (gate):** one broken-build run per condition. Both confirmed DT2 through the verifier, and the assertions and evidence were checked by hand. The batch then continued.

**Stage 2 stopped early:** 8 of 12 runs completed (2 repetitions per cell, not 3). The cap guard reserves the per-run worst case (US$0.15) before each run, so after US$0.145 it refused the third repetition. Actual runs cost US$0.006–0.034. Nothing else was run.

**Spend:** US$0.1450 of the additional US$0.275 (8 runs, 121 calls, 137,204 tokens).

| | single_agent | queue_review |
|---|---|---|
| DT2 (more than 6 tickets accepted), broken | **2/2 confirmed** | **2/2 confirmed** |
| DT5 (cancelled booking still listed), broken | 0/2: **unresolved for this condition** | **2/2 confirmed** |
| False confirmations (broken and corrected) | 0 | 0 |
| Inconclusive: verifier output (invalid, truncated, no assertion) | 0 | 0 |
| Inconclusive: requirement (unclear, not explicit) | 0 | 0 |
| Tester replies truncated and repaired | 0 | 2 (one per broken run; both repaired once) |

**Manual inspection:**
- **DT2:** all four confirmations used `validation_message_present` on Tickets (or page-wide) with 7 tickets. Every fresh replay landed on `/bookings/:id` with "Booking confirmed." and no validation message, which violates T2.
- **DT5:** both confirmations used the check page `/`. In each replay's own workspace, the recipe created a booking and code clicked "Yes, cancel booking". The list still showed "Harbour Jazz Night · 2 ticket(s)" before and after (`element_visible` / `text_or_value_retained` with `expect_present: false`).
- **Corrected build:** the testers judged T2 and T5 as expected, so nothing reached the verifier.

**DT5 and the single agent:** it never reached the cancel dialog, so the action-only form was never discovered or tested. This is an exploration gap, not a verifier failure, and it remains **unresolved for single_agent**.

**Comparison with batch-postfix-ticket-desk (the failed run before 071c86c):** DT2 went from 0/6 to 4/4, and verifier-output inconclusives from 4 to 0. That earlier batch's `requirement` entries for T2 come from code that misfiled a missing assertion as "not explicit"; manual inspection there showed a missing assertion.
