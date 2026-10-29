# Manual review of confirmed findings (batch-cp5)

Reviewed by Claude (lead session) against the saved verification records in `runs/*.json`.

| Run | Condition | Inputs | Assertion | Observed in fresh replays | Verdict |
|---|---|---|---|---|---|
| run_9191ff906668 | single_agent | Publish date 2026-06-14 | validation_message_present, field Publish date | /scheduled/:id, "Post scheduled.", no alert | Valid: R5 explicitly requires rejection with a validation message; date is before the studio date 2026-06-15 |
| run_1204b1110946 | queue_review | 2026-06-14 | same | same | Valid |
| run_08666f8f7aba | single_agent | 2026-06-14 | same | same | Valid |
| run_2028e64471e5 | queue_review | 2026-06-14 | same | same | Valid |
| run_e6af408a1d14 | single_agent | 2026-06-14 | same | same | Valid |
| run_6250423b8bfc | queue_review | 2026-06-14 | same | same | Valid |

- All six assertions encode R5 faithfully. A field-scoped validation check passes on the corrected build, because its page alert names the field (verified in the checkpoint-2 re-check runs).
- No corrected-build run confirmed anything.
- Inconclusive results were reviewed by type: R2 candidates judged not explicit, and observations with no requirement. None should have been confirmed.
- Caveat: every run chose the same boundary date (one day before the studio date). Other past dates were not exercised in this batch.
