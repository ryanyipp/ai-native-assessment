### Summary by model, mode and target

Medians across repetitions. Defects are found/known across runs; `n/a` means no answer key.

| Model | Mode | Target | Runs | Completed | Goal met | Reqs tested (union) | Reqs verified (union) | Defects | False conf. | Unfinished | Elapsed s | Calls | US$ total | Trunc. | Retries |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| GPT-5 Nano | queue | creator-broken | 2 | 0 | 2/2 | R3,R4,R5 | R3,R5 | 2/2 | 1 | 5 | 76 | 24 | 0.0085 | 0 | 1 |
| GPT-5 Nano | single | creator-broken | 2 | 0 | 2/2 | R2,R3,R4,R5 | R5 | 2/2 | 0 | 2 | 81 | 18 | 0.0071 | 0 | 0 |
| Haiku 5.5 | single | creator-broken | 2 | 2 | 2/2 | R2,R3,R4,R5 | R5 | 1/2 | 0 | 0 | 50 | 10 | 0.0067 | 0 | 0 |
| Haiku 5.5 | queue | creator-broken | 2 | 0 | 2/2 | R3,R4,R5 | R5 | 2/2 | 0 | 4 | 76 | 24 | 0.0154 | 0 | 1 |
| GPT-5 Nano | single | creator-corrected | 2 | 0 | 1/2 | R2,R3,R4,R5 | R2 | 0/0 | 1 | 2 | 58 | 16 | 0.0056 | 0 | 0 |
| GPT-5 Nano | queue | creator-corrected | 2 | 0 | 2/2 | R2,R4,R5 | R2 | 0/0 | 1 | 6 | 72 | 25 | 0.0087 | 0 | 1 |
| Haiku 5.5 | queue | creator-corrected | 2 | 0 | 2/2 | R3,R4,R5 | – | 0/0 | 0 | 7 | 80 | 23 | 0.0145 | 0 | 2 |
| Haiku 5.5 | single | creator-corrected | 2 | 2 | 2/2 | R2,R3,R4,R5 | – | 0/0 | 0 | 0 | 44 | 8 | 0.0052 | 0 | 0 |
| GPT-5 Nano | queue | ticket-broken | 2 | 2 | 2/2 | T2,T3 | – | 0/4 | 0 | 0 | 51 | 17 | 0.0053 | 0 | 0 |
| GPT-5 Nano | single | ticket-broken | 2 | 0 | 2/2 | T2,T3,T4 | T2 | 1/4 | 0 | 2 | 54 | 14 | 0.0058 | 1 | 1 |
| Haiku 5.5 | single | ticket-broken | 2 | 2 | 2/2 | T2,T3,T4 | T2 | 2/4 | 0 | 0 | 38 | 7 | 0.0044 | 0 | 0 |
| Haiku 5.5 | queue | ticket-broken | 2 | 0 | 2/2 | T2,T3,T5 | T2 | 2/4 | 0 | 2 | 60 | 19 | 0.0112 | 0 | 3 |
| GPT-5 Nano | single | ticket-corrected | 2 | 0 | 2/2 | T2,T3 | – | 0/0 | 0 | 2 | 49 | 14 | 0.0052 | 0 | 2 |
| GPT-5 Nano | queue | ticket-corrected | 2 | 2 | 2/2 | T2,T3,T4 | – | 0/0 | 0 | 0 | 51 | 17 | 0.0052 | 1 | 1 |
| Haiku 5.5 | queue | ticket-corrected | 2 | 1 | 2/2 | T2,T3,T4,T5 | – | 0/0 | 0 | 1 | 59 | 18 | 0.0097 | 0 | 1 |
| Haiku 5.5 | single | ticket-corrected | 2 | 2 | 2/2 | T2,T3,T4 | – | 0/0 | 0 | 0 | 28 | 5 | 0.0034 | 0 | 0 |

### Model and mode rollup

| Model | Mode | Runs | Failed | Unusable | Goal met | Keyed defects | False conf. (keyed) | Elapsed s (median) | Model latency ms p50/p95 (median of runs) | Browser ms p50/p95 | Input tokens | Output tokens | US$ | Trunc. | Retries | Failed calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| GPT-5 Nano | queue | 8 | 0 | 0 | 8/8 | 2/6 | 2 | 58 | 2652/6667 | 144/1006 | 140,006 | 51,649 | 0.0277 | 1 | 3 | 0 |
| GPT-5 Nano | single | 8 | 0 | 0 | 7/8 | 3/6 | 1 | 56 | 2465/4406 | 96/146 | 151,316 | 40,584 | 0.0238 | 1 | 3 | 0 |
| Haiku 5.5 | single | 8 | 0 | 0 | 8/8 | 3/6 | 0 | 42 | 3020/5176 | 46/164 | 93,837 | 20,341 | 0.0196 | 0 | 0 | 0 |
| Haiku 5.5 | queue | 8 | 0 | 0 | 8/8 | 4/6 | 0 | 70 | 4151/5872 | 114/824 | 213,775 | 58,875 | 0.0508 | 0 | 7 | 0 |

### Individual runs

| Model | Mode | Target | Rep | Run | Status | Goal | Tested | Verified | Defects | False | Unfin. | s | Calls | In | Out | US$ | Model p50/p95 ms | Browser p50/p95 ms | Trunc. | Retries |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| GPT-5 Nano | queue | creator-broken | 1 | `run_7e0cf6b33f36` | partial | yes | R4,R5 | R5 | 1/1 | 0 | 3 | 64 | 24 | 20666 | 7443 | 0.0040 | 2643/6616 | 142/984 | 0 | 1 |
| GPT-5 Nano | single | creator-broken | 1 | `run_5d3d33e0990e` | partial | yes | R2,R4,R5 | R5 | 1/1 | 0 | 1 | 78 | 19 | 24423 | 6112 | 0.0037 | 2307/4350 | 97/224 | 0 | 0 |
| Haiku 5.5 | single | creator-broken | 1 | `run_18d73808963d` | completed | yes | R3,R4,R5 | – | 0/1 | 0 | 0 | 46 | 8 | 12192 | 3686 | 0.0031 | 4117/5647 | 44/145 | 0 | 0 |
| Haiku 5.5 | queue | creator-broken | 1 | `run_226e5d73cb8e` | partial | yes | R3,R4,R5 | R5 | 1/1 | 0 | 1 | 79 | 24 | 31381 | 9591 | 0.0079 | 4049/4812 | 153/881 | 0 | 1 |
| GPT-5 Nano | single | creator-corrected | 1 | `run_f0d2f4cc44d6` | partial | no | R3 | – | 0/0 | 0 | 1 | 49 | 14 | 16246 | 3774 | 0.0023 | 2045/4462 | 121/163 | 0 | 0 |
| GPT-5 Nano | queue | creator-corrected | 1 | `run_f66050b8347a` | partial | yes | R2,R5 | R2 | 0/0 | 0 | 2 | 88 | 25 | 20236 | 8699 | 0.0045 | 3387/8472 | 173/1111 | 0 | 1 |
| Haiku 5.5 | queue | creator-corrected | 1 | `run_ac50474998b0` | partial | yes | R3,R4,R5 | – | 0/0 | 0 | 4 | 92 | 23 | 29763 | 8927 | 0.0074 | 4968/7178 | 151/1131 | 0 | 1 |
| Haiku 5.5 | single | creator-corrected | 1 | `run_b3e75b1b0913` | completed | yes | R2,R3,R4,R5 | – | 0/0 | 0 | 0 | 47 | 8 | 12634 | 2501 | 0.0025 | 3032/5950 | 67/184 | 0 | 0 |
| GPT-5 Nano | queue | ticket-broken | 1 | `run_185cdeb93496` | completed | yes | T2,T3 | – | 0/2 | 0 | 0 | 57 | 17 | 14362 | 4757 | 0.0026 | 2661/5708 | 145/1028 | 0 | 0 |
| GPT-5 Nano | single | ticket-broken | 1 | `run_cce57f8dac61` | partial | yes | T2,T3,T4 | – | 0/2 | 0 | 1 | 48 | 14 | 16808 | 4174 | 0.0025 | 2487/3301 | 113/152 | 0 | 0 |
| Haiku 5.5 | single | ticket-broken | 1 | `run_13cf0bec7454` | completed | yes | T2,T3,T4 | T2 | 1/2 | 0 | 0 | 44 | 7 | 11580 | 2263 | 0.0023 | 3179/5482 | 48/178 | 0 | 0 |
| Haiku 5.5 | queue | ticket-broken | 1 | `run_42dc371c058d` | partial | yes | T2,T3,T5 | T2 | 1/2 | 0 | 1 | 65 | 18 | 21703 | 6057 | 0.0052 | 4362/6841 | 102/1042 | 0 | 1 |
| GPT-5 Nano | single | ticket-corrected | 1 | `run_417d332ade58` | partial | yes | T3 | – | 0/0 | 0 | 1 | 50 | 14 | 16133 | 4550 | 0.0026 | 2641/3522 | 50/136 | 0 | 2 |
| GPT-5 Nano | queue | ticket-corrected | 1 | `run_3731d0c5b5b4` | completed | yes | T2,T3,T4 | – | 0/0 | 0 | 0 | 60 | 17 | 14486 | 4589 | 0.0026 | 2712/4917 | 155/1401 | 0 | 0 |
| Haiku 5.5 | queue | ticket-corrected | 1 | `run_3164d89a6636` | partial | yes | T2,T4,T5 | – | 0/0 | 0 | 1 | 73 | 21 | 26692 | 6444 | 0.0059 | 4724/6223 | 89/1252 | 0 | 1 |
| Haiku 5.5 | single | ticket-corrected | 1 | `run_1825c4811da3` | completed | yes | T2,T3,T4 | – | 0/0 | 0 | 0 | 32 | 6 | 9064 | 1993 | 0.0019 | 3007/4719 | 60/176 | 0 | 0 |
| GPT-5 Nano | single | creator-broken | 2 | `run_6e665cb751c3` | partial | yes | R3,R4,R5 | R5 | 1/1 | 0 | 1 | 85 | 17 | 22350 | 5856 | 0.0035 | 2470/4826 | 121/286 | 0 | 0 |
| GPT-5 Nano | queue | creator-broken | 2 | `run_50b98dfb5d5a` | partial | yes | R3,R4,R5 | R3,R5 | 1/1 | 1 | 2 | 88 | 25 | 20876 | 8594 | 0.0045 | 2723/8247 | 175/1398 | 0 | 0 |
| Haiku 5.5 | queue | creator-broken | 2 | `run_1d15a8031a26` | partial | yes | R3,R4,R5 | R5 | 1/1 | 0 | 3 | 73 | 24 | 31360 | 8568 | 0.0074 | 4253/5520 | 123/704 | 0 | 0 |
| Haiku 5.5 | single | creator-broken | 2 | `run_206a80c0159c` | completed | yes | R2,R3,R4,R5 | R5 | 1/1 | 0 | 0 | 54 | 11 | 18463 | 3487 | 0.0036 | 2496/4736 | 45/147 | 0 | 0 |
| GPT-5 Nano | queue | creator-corrected | 2 | `run_2af807de5db3` | partial | yes | R2,R4,R5 | R2 | 0/0 | 1 | 4 | 56 | 25 | 20576 | 7872 | 0.0042 | 2470/6718 | 120/787 | 0 | 0 |
| GPT-5 Nano | single | creator-corrected | 2 | `run_bbd4445e39e4` | partial | yes | R2,R3,R4,R5 | R2 | 0/0 | 1 | 1 | 68 | 17 | 20661 | 5714 | 0.0033 | 2002/5172 | 54/139 | 0 | 0 |
| Haiku 5.5 | single | creator-corrected | 2 | `run_1d58faadba73` | completed | yes | R3,R4,R5 | – | 0/0 | 0 | 0 | 40 | 8 | 12956 | 2696 | 0.0026 | 2795/5019 | 46/153 | 0 | 0 |
| Haiku 5.5 | queue | creator-corrected | 2 | `run_bdfc6f1bb368` | partial | yes | R3,R4,R5 | – | 0/0 | 0 | 3 | 66 | 23 | 28870 | 8403 | 0.0071 | 3928/4804 | 106/505 | 0 | 1 |
| GPT-5 Nano | single | ticket-broken | 2 | `run_4acffb592b6e` | partial | yes | T2,T3,T4 | T2 | 1/2 | 0 | 1 | 61 | 15 | 17862 | 6071 | 0.0033 | 2768/4840 | 47/130 | 1 | 1 |
| GPT-5 Nano | queue | ticket-broken | 2 | `run_d10c5742bf3b` | completed | yes | T2,T3 | – | 0/2 | 0 | 0 | 46 | 17 | 14297 | 4916 | 0.0027 | 2153/12276 | 101/465 | 0 | 0 |
| Haiku 5.5 | queue | ticket-broken | 2 | `run_b6e3e72cc747` | partial | yes | T2,T3,T5 | T2 | 1/2 | 0 | 1 | 54 | 20 | 26112 | 6747 | 0.0060 | 3438/6370 | 131/766 | 0 | 2 |
| Haiku 5.5 | single | ticket-broken | 2 | `run_623ecbc4cc6e` | completed | yes | T2,T3 | T2 | 1/2 | 0 | 0 | 33 | 7 | 10988 | 1926 | 0.0021 | 2596/3900 | 39/131 | 0 | 0 |
| GPT-5 Nano | queue | ticket-corrected | 2 | `run_4c70ad735c21` | completed | yes | T2,T3,T4 | – | 0/0 | 0 | 0 | 42 | 17 | 14507 | 4779 | 0.0026 | 2306/4836 | 111/590 | 1 | 1 |
| GPT-5 Nano | single | ticket-corrected | 2 | `run_9936b0942c3f` | partial | yes | T2,T3 | – | 0/0 | 0 | 1 | 48 | 14 | 16833 | 4333 | 0.0026 | 2460/4215 | 95/128 | 0 | 0 |
| Haiku 5.5 | single | ticket-corrected | 2 | `run_74ca8c877f3b` | completed | yes | T2,T3,T4 | – | 0/0 | 0 | 0 | 24 | 4 | 5960 | 1789 | 0.0015 | 3644/5333 | 38/218 | 0 | 0 |
| Haiku 5.5 | queue | ticket-corrected | 2 | `run_f087c59ae2a2` | completed | yes | T2,T3 | – | 0/0 | 0 | 0 | 44 | 14 | 17894 | 4138 | 0.0039 | 3649/4172 | 49/508 | 0 | 0 |
