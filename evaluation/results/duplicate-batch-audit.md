# Audit: duplicated evaluation batches (batch-heldout, batch-cs-queue-rerun)

**What happened.** A batch launched with a shell `&` appeared killed: Git Bash `ps` listed nothing, but the Windows process kept running. A second copy was then started. Both processes ran the same plan at the same time and appended to the same `runs.jsonl` files, giving 6 runs per cell instead of 3.

**Data isolation: held.** This is checked from the saved records (`duplicate-batch-audit.json`):
- `batch-heldout`: 24 runs and 178 workspace contexts; none shared between runs, and no action ran outside a provisioned workspace.
- `batch-cs-queue-rerun`: 12 runs and 165 workspace contexts; same result.
- Every exploration, test case and replay provisioned its own fixture workspace, and FlowLens records are keyed by run id.

**Uncertainty that remains.**
- **Load:** runs overlapped in time (23 and 11 overlapping run pairs). Each fixture build was a single server process shared by both batches. It serialises writes to one JSON file under a lock, so pages may have been slower under load.
- **Elapsed times are inflated** for these batches and should not be compared with sequential batches.
- **Model concurrency:** each batch process had its own limit of 2 concurrent model calls, so up to 4 calls ran at once against the provider. Any provider-side latency or rate effects are unknown.
- **Outcomes:** timing-sensitive outcomes (none observed: no lease expiries or setup failures) cannot be fully ruled out as load effects.
- **One mid-launch run:** the first copy's run `run_89aacf588084` was the first held-out run. It is kept and counted.

**Prevention.** `scripts/eval_batch.py` now refuses to start if any other `eval_batch.py` process is in the OS process table (PowerShell `Win32_Process` on Windows) or if `evaluation/.batch.lock` exists. Batches are run in the foreground or as one tracked background task, never with a shell `&`.
