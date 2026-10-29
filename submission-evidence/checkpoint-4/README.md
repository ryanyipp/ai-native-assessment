# Checkpoint 4 evidence: injected stall and recovery

`run_248eaaa2a5cd-detail.json` is the full API record. The run used real Chromium, `google/gemini-3-flash-preview`, the broken fixture build, and `mode: queue_review` with `fault_injection: {worker: explorer-a, task_type: explore, stall_s: 75}` and `task_lease_s: 45`. It is labelled `provenance.injected_failure: true`.

| Seq | Event |
|---|---|
| 948 | `[INJECTED FAULT]` explorer-a stalls holding `explore:start`, attempt `att_7f0f4957c5d6` |
| 949 | Lease expired: no action or model call for 45 s. Attempt revoked. |
| 950 | 1 browser context of that attempt closed by the coordinator |
| 951 | Task returned to the queue, explorer-a excluded (attempt 1/2 used) |
| 975 | Recovered: completed by explorer-b, attempt `att_951b2a3cd2f8` |
| 983–984 | explorer-a resumes; its model call is refused (no spend) |
| 989 | explorer-a's late result rejected by the queue: attempt not current |

The real handoffs went: explorer-b → input-tester (×2 forms) → verifier (×3 candidates). R5 was **confirmed**; two R2 candidates were **inconclusive**.

- **Usage:** 26 calls (exploration 19 of its 19-call cap, testing 4, verification 3), 28,903 tokens, US$0.0339 reported, 0 truncated.
- **Unfinished:** 4 explore tasks (explorer share used), each with its reason.

Screenshots: `docs/checkpoint-4/activity.png`, `recovery-trail.png`, `task-board.png`.
