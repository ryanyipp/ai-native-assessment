### Summary by model, mode and target

Medians across repetitions. Defects are found/known across runs; `n/a` means no answer key.

| Model | Mode | Target | Runs | Completed | Goal met | Reqs tested (union) | Reqs verified (union) | Defects | False conf. | Unfinished | Elapsed s | Calls | US$ total | Trunc. | Retries |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Haiku 5.5 | queue | creator-broken | 2 | 0 | 2/2 | R3,R4,R5 | R5 | 2/2 | 0 | 5 | 70 | 24 | 0.0147 | 0 | 0 |
| Haiku 5.5 | single | creator-broken | 2 | 2 | 2/2 | R2,R3,R4,R5 | R5 | 2/2 | 0 | 0 | 48 | 10 | 0.0066 | 0 | 1 |
| Haiku 5.5 | single | creator-corrected | 2 | 2 | 2/2 | R2,R3,R4,R5 | – | 0/0 | 0 | 0 | 42 | 9 | 0.0061 | 0 | 1 |
| Haiku 5.5 | queue | creator-corrected | 2 | 0 | 2/2 | R3,R4,R5 | – | 0/0 | 0 | 4 | 69 | 23 | 0.0145 | 0 | 1 |
| Haiku 5.5 | queue | ticket-broken | 2 | 1 | 2/2 | T2,T3,T4,T5 | T2 | 1/4 | 0 | 1 | 49 | 16 | 0.0091 | 1 | 2 |
| Haiku 5.5 | single | ticket-broken | 2 | 2 | 2/2 | T2,T3,T4 | T2 | 1/4 | 0 | 0 | 33 | 7 | 0.0044 | 0 | 1 |
| Haiku 5.5 | single | ticket-corrected | 2 | 2 | 2/2 | T2,T3,T4 | – | 0/0 | 0 | 0 | 29 | 6 | 0.0041 | 0 | 1 |
| Haiku 5.5 | queue | ticket-corrected | 2 | 2 | 2/2 | T2,T3 | – | 0/0 | 0 | 0 | 23 | 8 | 0.0043 | 0 | 0 |

### Model and mode rollup

| Model | Mode | Runs | Failed | Unusable | Goal met | Keyed defects | False conf. (keyed) | Elapsed s (median) | Model latency ms p50/p95 (median of runs) | Browser ms p50/p95 | Input tokens | Output tokens | US$ | Trunc. | Retries | Failed calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Haiku 5.5 | queue | 8 | 0 | 0 | 8/8 | 3/6 | 0 | 60 | 3570/4883 | 110/576 | 183,924 | 48,456 | 0.0426 | 1 | 3 | 0 |
| Haiku 5.5 | single | 8 | 0 | 0 | 8/8 | 3/6 | 0 | 40 | 2630/4740 | 41/144 | 105,714 | 21,353 | 0.0212 | 0 | 4 | 0 |

### Individual runs

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
