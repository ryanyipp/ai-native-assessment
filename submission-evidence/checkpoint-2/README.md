# Checkpoint 2 evidence: explorer → input tester → verifier

All runs used real Chromium against the local creator-studio fixture:
- **Broken build** on :5174 (`CREATOR_STUDIO_MODE=broken`).
- **Corrected build** on :5175 (`CREATOR_STUDIO_MODE=corrected`).
- Studio clock fixed at 2026-06-15.

The live runs used `google/gemini-3-flash-preview` through OpenRouter. The build label is recorded on each run as `target_build` and was never given to an agent. Costs are the provider-reported figures.

`attempts.jsonl` holds every attempt in order, including failed and superseded ones. Nothing was deleted.

## All attempts

| Run | What | Status | Calls (explorer/tester/verifier) | Tokens in/out | Reported US$ | Outcome |
|---|---|---|---|---|---|---|
| `run_eb3e50ed6997` | Live chain, broken | completed (*) | 12 (8/4/0) | 8,512 / 4,497 | 0.01775 | Both tester plans were truncated: hidden reasoning used 764 of 800 output tokens. 0 cases. (*) The run was recorded as completed by the code at the time; this was fixed afterwards and a blocked tester now marks a run `partial`. |
| `run_5f08da7d0fc8` | Live chain, broken | completed | 11 (4/4/3) | 7,986 / 5,308 | 0.01992 | R5 confirmed. **Two R2 false positives "confirmed":** R2 ("a draft has a title and a caption") was read as "both required", and a field-scoped assertion would have wrongly failed on the corrected build too. Both issues were fixed before the next run. |
| `run_a72265bf97b5` | Live chain, broken | completed | 16 (8/4/4) | 12,477 / 8,012 | 0.03027 | R5 **confirmed** (2/2 replays). The R2 candidates became inconclusive because the verifier judged R2 not explicit. The R3 and no-requirement observations were inconclusive. |
| `run_44704dfc5083` | Live chain, corrected | **partial** | 10 (6/4/0) | 7,137 / 7,386 | 0.02573 | The past-date case showed the alert "Publish date cannot be in the past."; the tester judged it as expected, so there was no candidate. The draft-form plan was truncated again (1,918 hidden reasoning tokens), so that task is blocked and the run is partial. |
| `run_bce1185f4e5f` | Browser-only re-check of `fnd_9085ebc18319` on corrected | completed | 0 | 0 | 0 | **not_reproduced** with the same assertion (2/2 replays held). |
| `run_db4f36872772` | Live chain, broken (final code) | completed | 15 (6/4/5) | 11,439 / 7,852 | 0.02928 | R5 **confirmed** (2/2). The two R2 candidates and one no-requirement observation were inconclusive. |
| `run_40e786578fef` | Browser-only re-check of `fnd_b2da8101d83d` on corrected | completed | 0 | 0 | 0 | **not_reproduced** with the same assertion (2/2). |

Checkpoint 2 total: 64 model calls, 80,606 tokens, US$0.1229 reported. The overall pool after checkpoint 2 is US$0.1318 of US$10.

## Selected chain: `run_db4f36872772` → `run_40e786578fef`

`broken-run/r5-chain.json` holds the finding, its test case, both verification attempts and both handoffs. Other folders:
- `broken-run/handoffs/`: the stored `form_to_tester` and `candidate_to_verifier` handoff artifacts.
- `broken-run/tester-evidence/`: screenshots and observations from the tester's fresh context.
- `broken-run/verifier-replay-1/`, `-2/`: separate fresh contexts and workspaces, with screenshots, observations and an attempt log.
- `broken-run/model-calls/`: the tester's and verifier's prompts and replies.
- `recheck-corrected/`: the same assertion on the corrected build.
- `corrected-run/`: the corrected-build live run's cases and the past-date case's evidence.

The model was real in every live run. The tests in `backend/tests/integration/test_review.py` use a scripted model, are labelled `mocked_model`, and are not evidence of model behaviour.
