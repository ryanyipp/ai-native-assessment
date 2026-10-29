## Reading these results

**Held-out app (`batch-heldout`).** ticket-desk was frozen in `25a6701` before either condition ran, and no prompt was changed afterwards.
- **DT2** (more than 6 tickets accepted) was confirmed in **6/6** single-agent and **6/6** shared-queue broken-build runs. Every confirmation used 7 tickets, and the replays reached the booking confirmation.
- **DT5** (a cancelled booking is still listed) was **missed in all 12** broken-build runs. It needs a multi-step check through a form with no fields, and neither condition's tester looks at that. This is a capability gap of both conditions.
- **No false confirmations** in either condition. The corrected build produced no confirmations.
- **Exploration:** the shared queue recorded more reference states (mean 5.3 vs 4.0 on the broken build), reaching the booking confirmation and cancel dialog more often.
- **Cost:** the shared queue cost about 2.6× more (US$0.022 vs 0.008 per broken-build run) and took about 1.6× longer. 7 of its 12 runs ended partial with unfinished explore tasks.

**Creator-studio queue re-run after the frontier change (`batch-cs-queue-rerun`).**
- **Fewer redundant tasks:** duplicate states fell from 5 to about 4 per run, and unfinished tasks from 6–7 to 1–4. Skipped variations are recorded as `skipped` tasks with reasons.
- **But D1 was found in only 4/6 broken-build runs (3/3 in batch-cp5).** The two misses are queue-mode failures:
  - `run_2117356c2fec`: the verifier, checking R2 candidates from the draft form, used up the shared call pool before the scheduling tester could assess its cases. The testing reserve is protected from explorers but not from a concurrently running verifier.
  - `run_c249ce51edbe`: the scheduling-form test plan was rejected as invalid JSON twice, so the task was blocked.

  Neither was fixed or retried after being seen.

**Overall.** On these two small apps, the single-agent baseline matched the shared-queue system on defect detection and false confirmations, at roughly a third of the cost and in less time. The queue observed somewhat more reference states, and it failed in queue-specific ways: unfinished exploration, a budget contention miss, and a blocked tester. These results show **no multi-agent advantage** in detection.

## Limitations

- **Accidental doubled runs.** A first batch process that appeared killed kept running: Git Bash `ps` does not show Windows processes. Two batch processes therefore ran the same plan at the same time. `batch-heldout` and `batch-cs-queue-rerun` hold 6 runs per cell instead of 3, run under doubled load (which affects elapsed time). Every run is kept and scored, and none is excluded. New live spend for this part: US$0.718 of the US$1 cap.
- **Small sample:** two small apps, three known defects, about six runs per cell. Means are descriptive only.
- **State matching uses the summary:** the summary carries only the first status or alert message, so a page with several messages can match the wrong reference entry.
- **No coverage claim:** reference states and transitions are a listed subset of meaningful pages. Unmatched states read 0 because the list covers everything these runs reached, not the whole site.
- **Boundary inputs only:** every confirmation used the boundary input (one day before the studio date, or 7 tickets). Other invalid values were not exercised.
- **Self-checks:** single-agent confirmations are self-checks (`independence: self`) that code replayed and evaluated.
- **Excluded runs:** the checkpoint-4 injected-stall run is recovery evidence and not part of any batch.
