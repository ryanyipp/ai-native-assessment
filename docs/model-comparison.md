# Model comparison: single agent and shared queue

**Recommendation: use `google/gemini-3-flash-preview` in `queue_review` for the live demo.** It was the only condition to find every known defect, and it had no false confirmations. It is also the most expensive, at about US$0.027 per run.

This is 72 scored live runs, 2 per model, mode and target. The sample is small, so treat these as directional results.

## Results at a glance

| Model | Mode | Known defects found | False confirmations (fixtures) | Goal met | Median run | US$ per run | Truncated replies |
|---|---|---|---|---|---|---|---|
| Gemini 3 Flash Preview | queue | **6/6** | **0** | 10/12 | 58 s | 0.0268 | 13 |
| Gemini 3 Flash Preview | single | 4/6 | 1 | 12/12 | 33 s | 0.0082 | 2 |
| GPT-5 Nano | queue | 3/6 | 2 | 9/12 | 60 s | 0.0038 | 11 |
| GPT-5 Nano | single | 1/6 | 3 | 9/12 | 75 s | 0.0027 | 5 |
| DeepSeek V4 Flash | queue | 1/6 | 0 | 10/12 | 115 s | 0.0049 | 83 |
| DeepSeek V4 Flash | single | 0/6 | 0 | 12/12 | 75 s | 0.0022 | 19 |

**Total spend: US$0.59 of the US$2 ceiling**, including 2 smoke runs. OpenRouter's key usage rose by US$0.5870, which matches the recorded costs. No call lacked a reported cost, and every planned cell ran.

## Addendum: Claude Haiku 5.5 (fixtures only)

Haiku was added after the main batch, on the two local fixtures only, so its figures compare with the fixture rows below and not with the 12-run table above. The recommendation stays Gemini in `queue_review`.

| Model | Mode | Known defects found | False confirmations | Goal met | Median run | Model latency p50 | US$ per run | Truncated replies |
|---|---|---|---|---|---|---|---|---|
| Gemini 3 Flash Preview | queue | 6/6 | 0 | 8/8 | 58 s | 2.2 s | 0.0295 | 6 |
| Gemini 3 Flash Preview | single | 4/6 | 1 | 8/8 | 33 s | 2.1 s | 0.0093 | 2 |
| **Haiku 5.5** | **queue** | **3/6** | **0** | **8/8** | **60 s** | **3.6 s** | **0.0053** | **1** |
| **Haiku 5.5** | **single** | **3/6** | **0** | **8/8** | **40 s** | **2.6 s** | **0.0027** | **0** |
| GPT-5 Nano | queue | 3/6 | 2 | 8/8 | 59 s | 2.7 s | 0.0035 | 2 |
| GPT-5 Nano | single | 1/6 | 3 | 7/8 | 80 s | 3.7 s | 0.0030 | 1 |
| DeepSeek V4 Flash | queue | 1/6 | 0 | 8/8 | 108 s | 7.3 s | 0.0053 | 54 |
| DeepSeek V4 Flash | single | 0/6 | 0 | 8/8 | 75 s | 6.9 s | 0.0024 | 15 |

- **Result:** Haiku had the cleanest output of the four: no unusable runs, 1 truncated reply and no false confirmations in 16 runs. All 8 corrected-build runs stayed clear.
- **Detection:** it found D1 in all 4 Creator Studio broken runs, and DT2 in 2 of 4 Ticket Desk broken runs (rep 1 of each mode). It never found the cancelled-booking defect.
- **Model settings:** ID `anthropic/claude-haiku-5.5`, US$0.10/0.50 per million tokens on the main providers. Same reasoning request as the other models. It has no temperature parameter, so temperature 0 was not applied. Prompts, assertions and limits were unchanged.
- **Harness settings:** the run reservation was US$0.04, because US$0.17 would have allowed one run under the US$0.30 cap. It covers 100k input and 60k output tokens. All 16 runs were served by Claude Platform on AWS.
- **Spend:** US$0.0670 of US$0.30, including 1 smoke run (`run_307817e31e18`). Key usage rose by US$0.0667.
- **Limits:** 2 repetitions per cell. These runs followed the main batch and used a later commit, but the scenario was generated from the original and no prompt or assertion changed.

Records: [`evaluation/results/model-comparison-haiku/`](../evaluation/results/model-comparison-haiku/) and [scenario_haiku.json](../evaluation/model-comparison/scenario_haiku.json).

## Method

- **Models:** the current Gemini model plus two inexpensive alternatives. Prices and parameters were checked on OpenRouter's API on 2026-10-31 and are recorded in [scenario.json](../evaluation/model-comparison/scenario.json). Each run used one model for every role.
- **Frozen inputs:** goals, requirements, limits and the goal evidence were committed before the scored batch. Every run used code commit and backend fingerprint recorded in `scored.jsonl`, and both were identical across all 72 runs.
- **Limits:** 30 model calls, US$0.15, 12 steps and 900 s per run. Fault injection was off.
- **Execution:** one process ran one review at a time, with the first mode alternating. Fresh browser contexts were used, plus new workspaces on the fixtures. No run was repeated or dropped.
- **Budget:** each run needed a US$0.17 reservation below the ceiling. Spend was the larger of recorded cost and key usage.
- **Goal met:** every URL pattern frozen for that target appeared in a successful recorded action.
- **Verification:** queue runs use a separate verifier. Single-agent runs are self-checks, because the same context chose the assertion. Code evaluates the assertion in both modes.

## Reliability

- **Gemini had no unusable runs.** Its misses in single mode were both Ticket Desk's second defect, which requires reaching the cancel flow.
- **DeepSeek mostly failed through truncation.** It had 102 truncated replies, and these stopped test plans and assertions. This may reflect the frozen output caps (800 and 1,400 tokens) rather than the model's ability, but no run tested a larger cap.
- **GPT-5 Nano confirmed behaviour no requirement states.** All 5 of its false confirmations concern R2 and empty fields, which the answer key lists as ambiguous. R2 says a draft has a title and a caption, and Nano treated that as making them mandatory. One run, `run_58497e376755`, failed after repeated invalid decisions.
- **Gemini's false confirmation was a self-check error.** In `run_46eda7d5b57b`, the agent checked `/drafts/new`, an empty form, for saved values. The assertion then correctly failed on the wrong page.

Across all models, the queue found 10 of 18 known defects against 5 of 18 for single-agent runs. False confirmations were 2 and 4.

The queue's cost is that it uses its budget. Most queue runs ended **partial** because the explorers used their call share. A partial result means the review stopped at a limit, not that it failed.

## Speed and cost

- **Speed:** Gemini single was fastest at a median of 33 s, and Gemini's model latency was also lowest (p50 about 2 s, against 3–4 s for Nano and 6–7 s for DeepSeek).
- **Browser time:** it was small next to model time in every condition, so model latency drives run length.
- **Cost:** DeepSeek and Nano cost roughly a fifth to a seventh of Gemini. All three are cheap enough for a demo, so cost should not decide this choice.

## Public sites

| Site | What happened | Limitation |
|---|---|---|
| TodoMVC (`demo.playwright.dev`) | **No requirement was tested in any of the 12 runs.** FlowLens found no form, because the todo input is not treated as one. Single mode met the goal in 5 of 6 runs; queue mode in 0 of 6. | Todos live in client-side storage. Each queue task starts in a fresh context, so the todos are gone and the reach step can fail, as in `run_e4e3c45f8740`. The 3-step task limit leaves too few actions to rebuild them. |
| The Internet (`the-internet.herokuapp.com`) | H1 and H2 were tested in all conditions, with no verified outcome. Goal met in 10 of 12 runs. | Shared server with no workspace isolation. No ad blocker was used, and no ad problem was recorded. The explorers could leave the journey, because other examples are one click away. |

Neither site has an answer key, so defect detection is unknown. No public run confirmed a finding, so there is nothing to review as a false confirmation there.

**For the demo, use a fixture or a site with real forms and server-side pages, and avoid TodoMVC in queue mode.**

## Limits of this sample

- With 2 repetitions per cell, a single run changes a result visibly. Differences such as 6/6 and 4/6 are not statistically established.
- Two small fixtures and two public sites do not represent websites in general. The fixtures were also used to develop FlowLens.
- Fixture defects are few and known. These results say nothing about coverage.
- Temperature 0 was not applied to GPT-5 Nano, which has no such parameter.
- OpenRouter chose the provider for each call, and 12 served these runs. Latency and truncation may vary by provider.
- Model latency counts only ok calls and excludes waiting for a call slot.
- Goal met shows the page was reached, not that a journey was fully understood.

## Records

Everything is in [`evaluation/results/model-comparison/`](../evaluation/results/model-comparison/): `scored.jsonl` (run IDs, code version, outcomes), `smoke.jsonl`, `ledger.jsonl`, `batch.log` and `scores.json`. `scripts/model_report.py` regenerates the tables below from saved records.

Smoke runs, not scored: `run_a3c579334b57` (DeepSeek) and `run_f8f9e38f7b0b` (GPT-5 Nano).

## Full results

### Summary by model, mode and target

Medians across repetitions. Defects are found/known across runs; `n/a` means no answer key.

| Model | Mode | Target | Runs | Completed | Goal met | Reqs tested (union) | Reqs verified (union) | Defects | False conf. | Unfinished | Elapsed s | Calls | US$ total | Trunc. | Retries |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Gemini | queue | creator-broken | 2 | 0 | 2/2 | R2,R3,R4,R5 | R5 | 2/2 | 0 | 6 | 58 | 24 | 0.0606 | 0 | 0 |
| Gemini | single | creator-broken | 2 | 2 | 2/2 | R3,R4,R5 | R5 | 2/2 | 0 | 0 | 45 | 10 | 0.0263 | 1 | 1 |
| DeepSeek | single | creator-broken | 2 | 2 | 2/2 | R3,R4,R5 | – | 0/2 | 0 | 0 | 115 | 10 | 0.0059 | 3 | 3 |
| DeepSeek | queue | creator-broken | 2 | 0 | 2/2 | – | – | 0/2 | 0 | 4 | 66 | 15 | 0.0099 | 10 | 10 |
| GPT-5 Nano | queue | creator-broken | 2 | 0 | 2/2 | R2,R3,R4,R5 | R2,R5 | 2/2 | 0 | 5 | 70 | 24 | 0.0083 | 1 | 1 |
| GPT-5 Nano | single | creator-broken | 2 | 0 | 2/2 | R2,R3,R4,R5 | R2,R5 | 1/2 | 1 | 2 | 89 | 18 | 0.0076 | 0 | 1 |
| Gemini | single | creator-corrected | 2 | 2 | 2/2 | R2,R3,R4,R5 | R3 | 0/0 | 1 | 0 | 41 | 10 | 0.0217 | 1 | 1 |
| Gemini | queue | creator-corrected | 2 | 0 | 2/2 | R2,R3,R4,R5 | – | 0/0 | 0 | 9 | 55 | 24 | 0.0649 | 3 | 4 |
| DeepSeek | queue | creator-corrected | 2 | 0 | 2/2 | R4,R5 | – | 0/0 | 0 | 4 | 97 | 20 | 0.0096 | 16 | 17 |
| DeepSeek | single | creator-corrected | 2 | 0 | 2/2 | R4,R5 | – | 0/0 | 0 | 3 | 105 | 8 | 0.0050 | 7 | 7 |
| GPT-5 Nano | single | creator-corrected | 2 | 0 | 1/2 | R2,R4,R5 | R2 | 0/0 | 2 | 2 | 82 | 17 | 0.0066 | 0 | 0 |
| GPT-5 Nano | queue | creator-corrected | 2 | 0 | 2/2 | R2,R4,R5 | R2 | 0/0 | 2 | 8 | 60 | 24 | 0.0085 | 0 | 1 |
| Gemini | queue | ticket-broken | 2 | 0 | 2/2 | T2,T3,T4,T5 | T2,T5 | 4/4 | 0 | 3 | 62 | 24 | 0.0634 | 2 | 2 |
| Gemini | single | ticket-broken | 2 | 2 | 2/2 | T2,T3,T4 | T2 | 2/4 | 0 | 0 | 31 | 8 | 0.0144 | 0 | 0 |
| DeepSeek | single | ticket-broken | 2 | 1 | 2/2 | T2,T3,T4 | – | 0/4 | 0 | 1 | 60 | 6 | 0.0037 | 3 | 3 |
| DeepSeek | queue | ticket-broken | 2 | 0 | 2/2 | T2,T3,T4,T5 | T5 | 1/4 | 0 | 2 | 110 | 22 | 0.0120 | 14 | 15 |
| GPT-5 Nano | queue | ticket-broken | 2 | 2 | 2/2 | T2,T3,T4 | T2 | 1/4 | 0 | 0 | 53 | 18 | 0.0057 | 1 | 2 |
| GPT-5 Nano | single | ticket-broken | 2 | 1 | 2/2 | T2,T3,T4 | – | 0/4 | 0 | 1 | 48 | 9 | 0.0042 | 1 | 1 |
| Gemini | single | ticket-corrected | 2 | 2 | 2/2 | T2,T3,T4 | – | 0/0 | 0 | 0 | 26 | 7 | 0.0121 | 0 | 0 |
| Gemini | queue | ticket-corrected | 2 | 0 | 2/2 | T2,T3,T4,T5 | – | 0/0 | 0 | 2 | 46 | 18 | 0.0473 | 1 | 1 |
| DeepSeek | queue | ticket-corrected | 2 | 1 | 2/2 | T2,T3,T4,T5 | – | 0/0 | 0 | 1 | 124 | 24 | 0.0109 | 14 | 14 |
| DeepSeek | single | ticket-corrected | 2 | 2 | 2/2 | T2,T3,T4 | – | 0/0 | 0 | 0 | 55 | 8 | 0.0044 | 2 | 2 |
| GPT-5 Nano | single | ticket-corrected | 2 | 1 | 2/2 | T3 | – | 0/0 | 0 | 1 | 72 | 13 | 0.0058 | 0 | 0 |
| GPT-5 Nano | queue | ticket-corrected | 2 | 2 | 2/2 | T2,T3,T4 | – | 0/0 | 0 | 0 | 50 | 17 | 0.0051 | 0 | 0 |
| Gemini | queue | todomvc | 2 | 0 | 0/2 | – | – | n/a | unknown | 6 | 36 | 16 | 0.0228 | 0 | 2 |
| Gemini | single | todomvc | 2 | 2 | 2/2 | – | – | n/a | unknown | 0 | 16 | 6 | 0.0092 | 0 | 0 |
| DeepSeek | single | todomvc | 2 | 2 | 2/2 | – | – | n/a | unknown | 0 | 27 | 6 | 0.0014 | 0 | 0 |
| DeepSeek | queue | todomvc | 2 | 0 | 0/2 | – | – | n/a | unknown | 2 | 117 | 14 | 0.0059 | 11 | 12 |
| GPT-5 Nano | queue | todomvc | 2 | 0 | 0/2 | – | – | n/a | unknown | 5 | 65 | 15 | 0.0084 | 5 | 6 |
| GPT-5 Nano | single | todomvc | 2 | 0 | 1/2 | – | – | n/a | unknown | 2 | 38 | 8 | 0.0037 | 2 | 3 |
| Gemini | single | the-internet | 2 | 2 | 2/2 | H1,H2 | – | n/a | unknown | 0 | 41 | 8 | 0.0142 | 0 | 0 |
| Gemini | queue | the-internet | 2 | 0 | 2/2 | H1,H2 | – | n/a | unknown | 3 | 78 | 22 | 0.0631 | 7 | 7 |
| DeepSeek | queue | the-internet | 2 | 1 | 2/2 | H1,H2 | – | n/a | unknown | 1 | 136 | 21 | 0.0102 | 18 | 18 |
| DeepSeek | single | the-internet | 2 | 2 | 2/2 | H1,H2 | – | n/a | unknown | 0 | 102 | 10 | 0.0059 | 4 | 4 |
| GPT-5 Nano | single | the-internet | 2 | 1 | 1/2 | H1,H2 | – | n/a | unknown | 1 | 84 | 10 | 0.0048 | 2 | 2 |
| GPT-5 Nano | queue | the-internet | 2 | 1 | 1/2 | H1,H2 | – | n/a | unknown | 1 | 97 | 20 | 0.0090 | 4 | 4 |

### Model and mode rollup

| Model | Mode | Runs | Failed | Unusable | Goal met | Keyed defects | False conf. (keyed) | Elapsed s (median) | Model latency ms p50/p95 (median of runs) | Browser ms p50/p95 | Input tokens | Output tokens | US$ | Trunc. | Retries | Failed calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Gemini | queue | 12 | 0 | 0 | 10/12 | 6/6 | 0 | 58 | 2237/7226 | 116/615 | 239,439 | 67,452 | 0.3221 | 13 | 16 | 0 |
| Gemini | single | 12 | 0 | 0 | 12/12 | 4/6 | 1 | 33 | 2008/2846 | 44/148 | 112,462 | 13,884 | 0.0979 | 2 | 2 | 0 |
| DeepSeek | single | 12 | 0 | 1 | 12/12 | 0/6 | 0 | 75 | 6130/14200 | 94/148 | 113,143 | 57,665 | 0.0262 | 19 | 19 | 0 |
| DeepSeek | queue | 12 | 0 | 1 | 10/12 | 1/6 | 0 | 115 | 7410/15308 | 100/467 | 210,199 | 139,616 | 0.0584 | 83 | 86 | 0 |
| GPT-5 Nano | queue | 12 | 0 | 0 | 9/12 | 3/6 | 2 | 60 | 3068/6856 | 100/488 | 209,706 | 86,803 | 0.0450 | 11 | 14 | 0 |
| GPT-5 Nano | single | 12 | 1 | 1 | 9/12 | 1/6 | 3 | 75 | 3946/6736 | 47/146 | 184,889 | 58,508 | 0.0326 | 5 | 7 | 0 |

### Individual runs

| Model | Mode | Target | Rep | Run | Status | Goal | Tested | Verified | Defects | False | Unfin. | s | Calls | In | Out | US$ | Model p50/p95 ms | Browser p50/p95 ms | Trunc. | Retries |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Gemini | queue | creator-broken | 1 | `run_66e7d1b88ede` | partial | yes | R2,R3,R4,R5 | R5 | 1/1 | 0 | 2 | 58 | 24 | 21350 | 6266 | 0.0295 | 2226/7257 | 121/687 | 0 | 0 |
| Gemini | single | creator-broken | 1 | `run_0b249c8f7291` | completed | yes | R3,R4,R5 | R5 | 1/1 | 0 | 0 | 44 | 9 | 10726 | 2446 | 0.0127 | 2083/7518 | 42/146 | 0 | 0 |
| DeepSeek | single | creator-broken | 1 | `run_39a560dd89cd` | completed | yes | R3,R4,R5 | – | 0/1 | 0 | 0 | 133 | 10 | 11429 | 7317 | 0.0032 | 8531/37747 | 39/145 | 1 | 1 |
| DeepSeek | queue | creator-broken | 1 | `run_2fcd160295d3` | partial | yes | – | – | 0/1 | 0 | 2 | 68 | 16 | 13264 | 10315 | 0.0051 | 5424/13731 | 153/528 | 5 | 5 |
| GPT-5 Nano | queue | creator-broken | 1 | `run_c218fae89578` | partial | yes | R3,R4,R5 | R5 | 1/1 | 0 | 2 | 76 | 24 | 19613 | 6701 | 0.0037 | 2694/14101 | 104/481 | 0 | 0 |
| GPT-5 Nano | single | creator-broken | 1 | `run_16ace0619e76` | partial | yes | R2 | R2 | 0/1 | 1 | 1 | 98 | 18 | 22544 | 7539 | 0.0041 | 3628/7983 | 47/151 | 0 | 0 |
| Gemini | single | creator-corrected | 1 | `run_46eda7d5b57b` | completed | yes | R3,R4,R5 | R3 | 0/0 | 1 | 0 | 47 | 10 | 11505 | 2459 | 0.0131 | 2106/8535 | 46/160 | 1 | 1 |
| Gemini | queue | creator-corrected | 1 | `run_e876403810ba` | partial | yes | R3,R4,R5 | – | 0/0 | 0 | 4 | 58 | 24 | 21427 | 7008 | 0.0317 | 2242/7055 | 122/650 | 1 | 1 |
| DeepSeek | queue | creator-corrected | 1 | `run_2939d367c5c4` | partial | yes | – | – | 0/0 | 0 | 2 | 78 | 16 | 13531 | 10948 | 0.0037 | 8015/20286 | 98/449 | 7 | 8 |
| DeepSeek | single | creator-corrected | 1 | `run_fd6bc12516b4` | partial | yes | R4,R5 | – | 0/0 | 0 | 1 | 132 | 9 | 10066 | 6041 | 0.0022 | 7307/55408 | 102/150 | 3 | 3 |
| GPT-5 Nano | single | creator-corrected | 1 | `run_80cf22c27984` | partial | no | R2 | R2 | 0/0 | 1 | 1 | 83 | 16 | 19205 | 5027 | 0.0030 | 3207/9074 | 46/125 | 0 | 0 |
| GPT-5 Nano | queue | creator-corrected | 1 | `run_26cb5031e8c7` | partial | yes | R2,R4,R5 | – | 0/0 | 0 | 4 | 62 | 24 | 19601 | 7259 | 0.0039 | 2645/7977 | 105/487 | 0 | 0 |
| Gemini | queue | ticket-broken | 1 | `run_b136420c0fdf` | partial | yes | T2,T3,T4,T5 | T2,T5 | 2/2 | 0 | 1 | 62 | 25 | 21603 | 7273 | 0.0326 | 2232/5313 | 122/625 | 0 | 0 |
| Gemini | single | ticket-broken | 1 | `run_6e1d56ed792e` | completed | yes | T2,T3,T4 | T2 | 1/2 | 0 | 0 | 30 | 8 | 9081 | 899 | 0.0072 | 1983/2652 | 38/122 | 0 | 0 |
| DeepSeek | single | ticket-broken | 1 | `run_a2c56ac3891c` | completed | yes | T2,T3,T4 | – | 0/2 | 0 | 0 | 73 | 6 | 6503 | 3062 | 0.0011 | 4893/41668 | 38/129 | 0 | 0 |
| DeepSeek | queue | ticket-broken | 1 | `run_8017f3ef313a` | partial | yes | T2,T3,T4,T5 | T5 | 1/2 | 0 | 1 | 117 | 25 | 23571 | 15562 | 0.0059 | 7440/12918 | 91/452 | 8 | 8 |
| GPT-5 Nano | queue | ticket-broken | 1 | `run_051affcc2b49` | completed | yes | T2,T3,T4 | – | 0/2 | 0 | 0 | 58 | 17 | 14474 | 5340 | 0.0029 | 2931/12983 | 98/281 | 1 | 1 |
| GPT-5 Nano | single | ticket-broken | 1 | `run_827cbfface99` | completed | yes | T2,T3 | – | 0/2 | 0 | 0 | 27 | 4 | 3683 | 1946 | 0.0010 | 4969/5694 | 37/146 | 0 | 0 |
| Gemini | single | ticket-corrected | 1 | `run_3679b7e1d5e2` | completed | yes | T2,T3,T4 | – | 0/0 | 0 | 0 | 27 | 7 | 7584 | 723 | 0.0060 | 2381/3941 | 41/137 | 0 | 0 |
| Gemini | queue | ticket-corrected | 1 | `run_28092cf77999` | partial | yes | T2,T3,T4,T5 | – | 0/0 | 0 | 1 | 47 | 17 | 14419 | 4930 | 0.0220 | 2604/10462 | 50/358 | 1 | 1 |
| DeepSeek | queue | ticket-corrected | 1 | `run_7d1cf49d1a19` | partial | yes | T2,T3,T4,T5 | – | 0/0 | 0 | 1 | 116 | 25 | 22722 | 14293 | 0.0056 | 7259/13478 | 101/433 | 7 | 7 |
| DeepSeek | single | ticket-corrected | 1 | `run_566f70f67d22` | completed | yes | T2,T3,T4 | – | 0/0 | 0 | 0 | 59 | 8 | 8999 | 4536 | 0.0025 | 6444/10082 | 41/135 | 1 | 1 |
| GPT-5 Nano | single | ticket-corrected | 1 | `run_bc70c5397d1c` | completed | yes | T3 | – | 0/0 | 0 | 0 | 63 | 12 | 14492 | 4796 | 0.0026 | 4625/6186 | 37/131 | 0 | 0 |
| GPT-5 Nano | queue | ticket-corrected | 1 | `run_3894c4267d00` | completed | yes | T2,T3,T4 | – | 0/0 | 0 | 0 | 49 | 17 | 14424 | 4493 | 0.0025 | 2619/6737 | 101/498 | 0 | 0 |
| Gemini | queue | todomvc | 1 | `run_e4e3c45f8740` | partial | no | – | – | n/a | unknown | 3 | 44 | 19 | 19201 | 1179 | 0.0131 | 2097/2656 | 92/307 | 0 | 1 |
| Gemini | single | todomvc | 1 | `run_cee1f15891de` | completed | yes | – | – | n/a | unknown | 0 | 14 | 6 | 6814 | 458 | 0.0048 | 1744/2295 | 84/182 | 0 | 0 |
| DeepSeek | single | todomvc | 1 | `run_573cd5ecf9e6` | completed | yes | – | – | n/a | unknown | 0 | 24 | 6 | 7064 | 1350 | 0.0005 | 3452/4872 | 94/201 | 0 | 0 |
| DeepSeek | queue | todomvc | 1 | `run_21877d425884` | partial | no | – | – | n/a | unknown | 1 | 126 | 15 | 15017 | 8132 | 0.0029 | 5599/40973 | 100/226 | 7 | 7 |
| GPT-5 Nano | queue | todomvc | 1 | `run_b0d39ad6ff91` | partial | no | – | – | n/a | unknown | 2 | 53 | 12 | 10607 | 7481 | 0.0035 | 5179/6231 | 92/292 | 3 | 3 |
| GPT-5 Nano | single | todomvc | 1 | `run_8e0431c0f388` | partial | yes | – | – | n/a | unknown | 1 | 54 | 12 | 15169 | 4848 | 0.0027 | 4020/5747 | 86/184 | 0 | 0 |
| Gemini | single | the-internet | 1 | `run_ae152319c98d` | completed | yes | H1,H2 | – | n/a | unknown | 0 | 42 | 8 | 10775 | 582 | 0.0071 | 2004/2886 | 1713/2809 | 0 | 0 |
| Gemini | queue | the-internet | 1 | `run_6ad9ad5fd3b7` | partial | yes | H1,H2 | – | n/a | unknown | 1 | 81 | 22 | 25386 | 6862 | 0.0333 | 2462/7735 | 2017/2952 | 4 | 4 |
| DeepSeek | queue | the-internet | 1 | `run_8e813b86dee9` | completed | yes | H1,H2 | – | n/a | unknown | 0 | 139 | 21 | 21312 | 13074 | 0.0052 | 8481/14020 | 2088/2993 | 10 | 10 |
| DeepSeek | single | the-internet | 1 | `run_88382bd67007` | completed | yes | H1,H2 | – | n/a | unknown | 0 | 87 | 9 | 12313 | 4963 | 0.0023 | 5156/15488 | 2039/2560 | 1 | 1 |
| GPT-5 Nano | single | the-internet | 1 | `run_de932c562c5e` | completed | yes | H1,H2 | – | n/a | unknown | 0 | 62 | 7 | 7517 | 3237 | 0.0017 | 4428/5904 | 2012/2659 | 1 | 1 |
| GPT-5 Nano | queue | the-internet | 1 | `run_95e85c9b9605` | completed | no | H1,H2 | – | n/a | unknown | 0 | 91 | 20 | 22151 | 8051 | 0.0042 | 3625/5701 | 2013/2908 | 1 | 1 |
| Gemini | single | creator-broken | 2 | `run_260b64b1cfeb` | completed | yes | R3,R4,R5 | R5 | 1/1 | 0 | 0 | 46 | 10 | 11453 | 2611 | 0.0136 | 2568/7417 | 42/144 | 1 | 1 |
| Gemini | queue | creator-broken | 2 | `run_94026034ff96` | partial | yes | R2,R3,R4,R5 | R5 | 1/1 | 0 | 4 | 58 | 24 | 21362 | 6828 | 0.0312 | 2253/7305 | 127/605 | 0 | 0 |
| DeepSeek | queue | creator-broken | 2 | `run_cd378809a843` | partial | yes | – | – | 0/1 | 0 | 2 | 64 | 14 | 11549 | 9765 | 0.0047 | 7112/15027 | 111/456 | 5 | 5 |
| DeepSeek | single | creator-broken | 2 | `run_d5f38a06e40c` | completed | yes | R3,R4,R5 | – | 0/1 | 0 | 0 | 97 | 10 | 11992 | 7179 | 0.0027 | 10311/16557 | 43/174 | 2 | 2 |
| GPT-5 Nano | single | creator-broken | 2 | `run_d615568ddb58` | partial | yes | R3,R4,R5 | R5 | 1/1 | 0 | 1 | 80 | 17 | 21253 | 5973 | 0.0035 | 3023/7648 | 50/143 | 0 | 1 |
| GPT-5 Nano | queue | creator-broken | 2 | `run_d10edfe47b74` | partial | yes | R2,R4,R5 | R2,R5 | 1/1 | 0 | 3 | 63 | 25 | 20544 | 9059 | 0.0047 | 3222/6030 | 98/517 | 1 | 1 |
| Gemini | queue | creator-corrected | 2 | `run_dcb7f0d9c900` | partial | yes | R2,R3,R4,R5 | – | 0/0 | 0 | 5 | 52 | 25 | 21954 | 7385 | 0.0331 | 2670/8088 | 110/698 | 2 | 3 |
| Gemini | single | creator-corrected | 2 | `run_c88af76765d5` | completed | yes | R2,R3,R4,R5 | – | 0/0 | 0 | 0 | 35 | 9 | 10482 | 1097 | 0.0085 | 2002/3056 | 51/150 | 0 | 0 |
| DeepSeek | single | creator-corrected | 2 | `run_bf863960654b` | partial | yes | – | – | 0/0 | 0 | 2 | 77 | 8 | 7947 | 6426 | 0.0028 | 12425/17933 | 106/110 | 4 | 4 |
| DeepSeek | queue | creator-corrected | 2 | `run_080bcf544f63` | partial | yes | R4,R5 | – | 0/0 | 0 | 2 | 115 | 24 | 21134 | 14086 | 0.0058 | 6732/15588 | 112/478 | 9 | 9 |
| GPT-5 Nano | queue | creator-corrected | 2 | `run_97e001b7d063` | partial | yes | R2,R4,R5 | R2 | 0/0 | 2 | 4 | 59 | 25 | 20413 | 9008 | 0.0046 | 3205/6706 | 58/600 | 0 | 1 |
| GPT-5 Nano | single | creator-corrected | 2 | `run_f658c0adbdb9` | partial | yes | R2,R4,R5 | R2 | 0/0 | 1 | 1 | 80 | 18 | 22927 | 6234 | 0.0036 | 2796/5155 | 47/147 | 0 | 0 |
| Gemini | single | ticket-broken | 2 | `run_6cd826575b63` | completed | yes | T2,T3,T4 | T2 | 1/2 | 0 | 0 | 31 | 8 | 8937 | 907 | 0.0072 | 2012/2710 | 40/124 | 0 | 0 |
| Gemini | queue | ticket-broken | 2 | `run_619c5b2bc20c` | partial | yes | T2,T3,T4,T5 | T2,T5 | 2/2 | 0 | 2 | 62 | 22 | 18944 | 7094 | 0.0308 | 2383/7194 | 109/480 | 2 | 2 |
| DeepSeek | queue | ticket-broken | 2 | `run_61c7f16a2120` | partial | yes | T2,T3,T4 | – | 0/2 | 0 | 1 | 102 | 18 | 15903 | 12386 | 0.0061 | 7398/21136 | 43/498 | 6 | 7 |
| DeepSeek | single | ticket-broken | 2 | `run_f35475146474` | partial | yes | – | – | 0/2 | 0 | 1 | 48 | 7 | 7342 | 4357 | 0.0025 | 5817/12329 | 121/145 | 3 | 3 |
| GPT-5 Nano | single | ticket-broken | 2 | `run_5094637bd59f` | partial | yes | T2,T3,T4 | – | 0/2 | 0 | 1 | 70 | 14 | 16598 | 5954 | 0.0032 | 3677/10063 | 40/108 | 1 | 1 |
| GPT-5 Nano | queue | ticket-broken | 2 | `run_f4b43cd0fc74` | completed | yes | T2 | T2 | 1/2 | 0 | 0 | 48 | 19 | 15629 | 5087 | 0.0028 | 2745/9536 | 96/382 | 0 | 1 |
| Gemini | queue | ticket-corrected | 2 | `run_3ef22a8f2809` | partial | yes | T2,T3,T4,T5 | – | 0/0 | 0 | 1 | 46 | 19 | 16610 | 5657 | 0.0253 | 2159/8104 | 64/300 | 0 | 0 |
| Gemini | single | ticket-corrected | 2 | `run_31e6c04c4d52` | completed | yes | T2,T3,T4 | – | 0/0 | 0 | 0 | 25 | 7 | 7658 | 775 | 0.0062 | 2317/2807 | 39/126 | 0 | 0 |
| DeepSeek | single | ticket-corrected | 2 | `run_95ba80519682` | completed | yes | T2,T3,T4 | – | 0/0 | 0 | 0 | 51 | 7 | 7566 | 4252 | 0.0019 | 4721/12739 | 35/127 | 1 | 1 |
| DeepSeek | queue | ticket-corrected | 2 | `run_558acfaadbd8` | completed | yes | T2,T3,T4,T5 | – | 0/0 | 0 | 0 | 131 | 23 | 20417 | 12554 | 0.0053 | 10014/14794 | 88/453 | 7 | 7 |
| GPT-5 Nano | queue | ticket-corrected | 2 | `run_31012bae8720` | completed | yes | T2,T3,T4 | – | 0/0 | 0 | 0 | 50 | 17 | 14163 | 4788 | 0.0026 | 2584/15348 | 103/490 | 0 | 0 |
| GPT-5 Nano | single | ticket-corrected | 2 | `run_190201bc0f9c` | partial | yes | T3 | – | 0/0 | 0 | 1 | 80 | 14 | 17804 | 5551 | 0.0031 | 3873/14190 | 34/129 | 0 | 0 |
| Gemini | single | todomvc | 2 | `run_8d6f91092bb9` | completed | yes | – | – | n/a | unknown | 0 | 17 | 6 | 6758 | 352 | 0.0044 | 1844/2504 | 91/3328 | 0 | 0 |
| Gemini | queue | todomvc | 2 | `run_dd1137649359` | partial | no | – | – | n/a | unknown | 3 | 28 | 12 | 11179 | 1350 | 0.0096 | 1996/3251 | 94/219 | 0 | 1 |
| DeepSeek | queue | todomvc | 2 | `run_e553d9090b96` | partial | no | – | – | n/a | unknown | 1 | 109 | 12 | 11293 | 6678 | 0.0030 | 9519/41995 | 98/571 | 4 | 5 |
| DeepSeek | single | todomvc | 2 | `run_c293eac43077` | completed | yes | – | – | n/a | unknown | 0 | 30 | 6 | 7071 | 1688 | 0.0008 | 3869/6534 | 95/162 | 0 | 0 |
| GPT-5 Nano | single | todomvc | 2 | `run_58497e376755` | failed | no | – | – | n/a | unknown | 1 | 21 | 3 | 2531 | 2301 | 0.0010 | 6746/6977 | 193/193 | 2 | 3 |
| GPT-5 Nano | queue | todomvc | 2 | `run_7abe4b186020` | partial | no | – | – | n/a | unknown | 3 | 77 | 18 | 17139 | 9983 | 0.0049 | 5131/6974 | 87/301 | 2 | 3 |
| Gemini | queue | the-internet | 2 | `run_f332f0ad24c7` | partial | yes | H1,H2 | – | n/a | unknown | 2 | 76 | 22 | 26004 | 5620 | 0.0299 | 2145/5477 | 2071/2891 | 3 | 3 |
| Gemini | single | the-internet | 2 | `run_74ca34cb2cf9` | completed | yes | H1,H2 | – | n/a | unknown | 0 | 39 | 8 | 10689 | 575 | 0.0071 | 1619/2263 | 1710/2553 | 0 | 0 |
| DeepSeek | single | the-internet | 2 | `run_2b6355c66723` | completed | yes | H1,H2 | – | n/a | unknown | 0 | 116 | 11 | 14851 | 6494 | 0.0036 | 6764/12913 | 1839/2905 | 3 | 3 |
| DeepSeek | queue | the-internet | 2 | `run_3c5f2f67c320` | partial | yes | H1,H2 | – | n/a | unknown | 1 | 132 | 21 | 20486 | 11823 | 0.0050 | 7423/18448 | 2097/2961 | 8 | 8 |
| GPT-5 Nano | queue | the-internet | 2 | `run_942e5c425edd` | partial | yes | H1,H2 | – | n/a | unknown | 1 | 103 | 21 | 20948 | 9553 | 0.0048 | 4899/6508 | 2146/3117 | 3 | 3 |
| GPT-5 Nano | single | the-internet | 2 | `run_3a5db80d818c` | partial | no | H1,H2 | – | n/a | unknown | 1 | 106 | 14 | 21166 | 5102 | 0.0031 | 4246/6495 | 1835/2657 | 1 | 1 |

### Haiku individual runs

| Model | Mode | Target | Rep | Run | Status | Goal | Tested | Verified | Defects | False | Unfin. | s | Calls | In | Out | US$ | Model p50/p95 ms | Browser p50/p95 ms | Trunc. | Retries |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Haiku 5.5 | queue | creator-broken | 1 | `run_36a713835d66` | partial | yes | R3,R4,R5 | R5 | 1/1 | 0 | 3 | 75 | 24 | 32161 | 8345 | 0.0074 | 4198/7309 | 112/665 | 0 | 0 |
| Haiku 5.5 | single | creator-broken | 1 | `run_520761cb0184` | completed | yes | R2,R3,R4,R5 | R5 | 1/1 | 0 | 0 | 48 | 9 | 15889 | 3107 | 0.0031 | 2728/5367 | 104/164 | 0 | 0 |
| Haiku 5.5 | single | creator-corrected | 1 | `run_c23605d51a57` | completed | yes | R2,R3,R4,R5 | – | 0/0 | 0 | 0 | 42 | 9 | 14312 | 3048 | 0.0030 | 2586/4224 | 41/143 | 0 | 0 |
| Haiku 5.5 | queue | creator-corrected | 1 | `run_f3bc0212f972` | partial | yes | R3,R4,R5 | – | 0/0 | 0 | 3 | 72 | 23 | 31085 | 8399 | 0.0073 | 4045/5149 | 122/1080 | 0 | 1 |
| Haiku 5.5 | queue | ticket-broken | 1 | `run_57409b479aa2` | partial | yes | T2,T3,T5 | T2 | 1/2 | 0 | 1 | 54 | 18 | 22483 | 5695 | 0.0051 | 3523/4879 | 106/576 | 0 | 1 |
| Haiku 5.5 | single | ticket-broken | 1 | `run_7bdf18a452de` | completed | yes | T2,T3,T4 | T2 | 1/2 | 0 | 0 | 38 | 8 | 13800 | 2670 | 0.0027 | 2638/3937 | 41/147 | 0 | 1 |
| Haiku 5.5 | single | ticket-corrected | 1 | `run_64b885bfe644` | completed | yes | T2,T3,T4 | – | 0/0 | 0 | 0 | 31 | 7 | 11744 | 2462 | 0.0024 | 2614/4725 | 39/144 | 0 | 1 |
| Haiku 5.5 | queue | ticket-corrected | 1 | `run_eb161404c9f3` | completed | yes | T2,T3 | – | 0/0 | 0 | 0 | 24 | 8 | 10390 | 2540 | 0.0023 | 3018/4943 | 110/215 | 0 | 0 |
| Haiku 5.5 | single | creator-broken | 2 | `run_3696e1a7e2c3` | completed | yes | R3,R4,R5 | R5 | 1/1 | 0 | 0 | 49 | 10 | 16295 | 3704 | 0.0035 | 3007/4754 | 40/134 | 0 | 1 |
| Haiku 5.5 | queue | creator-broken | 2 | `run_2e2413b2f04d` | partial | yes | R3,R4,R5 | R5 | 1/1 | 0 | 2 | 65 | 23 | 30516 | 8485 | 0.0073 | 3618/4887 | 110/575 | 0 | 0 |
| Haiku 5.5 | queue | creator-corrected | 2 | `run_a6400f713c06` | partial | yes | R3,R4,R5 | – | 0/0 | 0 | 1 | 66 | 23 | 30396 | 8308 | 0.0072 | 3771/4530 | 109/611 | 0 | 0 |
| Haiku 5.5 | single | creator-corrected | 2 | `run_95197f0db9f3` | completed | yes | R2,R3,R4,R5 | – | 0/0 | 0 | 0 | 42 | 9 | 15381 | 3190 | 0.0031 | 2623/5865 | 59/168 | 0 | 1 |
| Haiku 5.5 | single | ticket-broken | 2 | `run_13d1f77808e7` | completed | yes | T2,T3,T4 | – | 0/2 | 0 | 0 | 28 | 6 | 9141 | 1609 | 0.0017 | 2729/5310 | 38/131 | 0 | 0 |
| Haiku 5.5 | queue | ticket-broken | 2 | `run_8404dfb697b9` | completed | yes | T2,T3,T4 | – | 0/2 | 0 | 0 | 44 | 13 | 17198 | 4550 | 0.0040 | 3139/4741 | 107/484 | 1 | 1 |
| Haiku 5.5 | queue | ticket-corrected | 2 | `run_1decb11fd77e` | completed | yes | T2,T3 | – | 0/0 | 0 | 0 | 21 | 8 | 9695 | 2134 | 0.0020 | 3025/4021 | 51/537 | 0 | 0 |
| Haiku 5.5 | single | ticket-corrected | 2 | `run_cf2bf545f377` | completed | yes | T2,T3 | – | 0/0 | 0 | 0 | 27 | 6 | 9152 | 1563 | 0.0017 | 2384/4304 | 53/144 | 0 | 0 |
