# batch-postfix-ticket-desk: POST-FIX REGRESSION results (not held-out evidence)

ticket-desk is a known regression fixture. This batch ran the code frozen at `620cff5` (the correctness pass): 3 repetitions × 2 conditions × 2 builds, run sequentially by one tracked process, with no fault injection. 12 runs, 170 calls, 215,252 tokens, US$0.2246 reported (cap US$0.50).

- **Launch:** the first launch was refused by the new duplicate-launch guard. That was a false positive: the guard matched the launching shell. No runs or spend resulted (`refused-attempt.log`). The guard was narrowed to Python processes, and the batch was relaunched.
- **Scores:** see `report.md`.

## Result: the validation FAILED

| | single_agent | queue_review |
|---|---|---|
| DT2 (more than 6 tickets accepted) | 0/3 confirmed | 0/3 confirmed |
| DT5 (cancelled booking still listed) | 0/3 | 0/3 |
| False confirmations | 0 | 0 |

The batch-heldout result before the fixes was DT2 6/6 in both conditions.

**What worked.** In every broken-build run the tester executed the 7-ticket case, saw the booking accepted, and reported a T2 candidate. The queue explorers reached the cancel dialog, so the action-only cancel form was discovered and tested in 2 of 3 queue runs, with the list page as its check page.

**What failed, and the root cause.** The verifier step broke because of a change I made in the correctness pass: sending a JSON schema to the provider (`response_format: json_schema`, strict off).
- **single_agent:** verifier replies looped inside a string field (7,185 and 9,121 characters, 0 hidden-reasoning tokens) until the output cap. The bounded repair then gave up, so the result was inconclusive.
- **queue_review:** the verifier replied `explicit: true` but omitted the optional `assertion`, and the quote carried extra text. The code then wrongly reported this as "not explicit", which is a reason-text bug.
- **DT5:** where the cancel form was tested, the tester judged the before/after list comparison **unclear**. The candidate stayed a review observation, so it was never verified.

**Fix after this batch (not yet validated live):** provider-side schemas are off by default (`FLOWLENS_PROVIDER_JSON_SCHEMA`), while local validation and the bounded repair stay. "Explicit but no assertion" is now reported as a verifier failure. Regression tests cover both. No live run has yet confirmed that DT2 detection is restored.
