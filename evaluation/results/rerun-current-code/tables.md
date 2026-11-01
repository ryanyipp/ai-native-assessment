### Summary by model, mode and target

Medians across repetitions. Defects are found/known across runs; `n/a` means no answer key.

| Model | Mode | Target | Runs | Completed | Goal met | Reqs tested (union) | Reqs verified (union) | Defects | False conf. | Unfinished | Elapsed s | Calls | US$ total | Trunc. | Retries |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Gemini | queue | creator-broken | 2 | 0 | 2/2 | R2,R3,R4,R5 | R5 | 2/2 | 0 | 5 | 72 | 24 | 0.0611 | 0 | 0 |
| Gemini | single | creator-broken | 2 | 2 | 2/2 | R3,R4,R5 | R5 | 2/2 | 0 | 0 | 57 | 10 | 0.0264 | 1 | 1 |
| DeepSeek | single | creator-broken | 2 | 2 | 2/2 | R3,R4,R5 | R5 | 2/2 | 0 | 0 | 112 | 12 | 0.0039 | 3 | 3 |
| DeepSeek | queue | creator-broken | 2 | 0 | 2/2 | R3,R4,R5 | R5 | 1/2 | 0 | 3 | 110 | 22 | 0.0055 | 11 | 10 |
| Gemini | single | creator-corrected | 2 | 2 | 2/2 | R3,R4,R5 | – | 0/0 | 0 | 0 | 40 | 9 | 0.0208 | 1 | 1 |
| Gemini | queue | creator-corrected | 2 | 0 | 2/2 | R2,R3,R4,R5 | – | 0/0 | 0 | 7 | 65 | 24 | 0.0557 | 2 | 2 |
| DeepSeek | queue | creator-corrected | 2 | 0 | 2/2 | R3,R4,R5 | – | 0/0 | 0 | 4 | 105 | 22 | 0.0057 | 11 | 13 |
| DeepSeek | single | creator-corrected | 2 | 2 | 2/2 | R3,R4,R5 | – | 0/0 | 0 | 0 | 77 | 8 | 0.0029 | 1 | 1 |
| Gemini | queue | ticket-broken | 2 | 0 | 2/2 | T2,T3,T4,T5 | T2,T5 | 4/4 | 0 | 3 | 80 | 22 | 0.0590 | 0 | 0 |
| Gemini | single | ticket-broken | 2 | 2 | 2/2 | T2,T3,T4 | T2 | 2/4 | 0 | 0 | 36 | 8 | 0.0144 | 0 | 0 |
| DeepSeek | single | ticket-broken | 2 | 1 | 2/2 | T2,T3,T4 | – | 0/4 | 0 | 1 | 38 | 6 | 0.0015 | 1 | 2 |
| DeepSeek | queue | ticket-broken | 2 | 2 | 2/2 | T2,T3,T4,T5 | T5 | 1/4 | 0 | 0 | 114 | 22 | 0.0066 | 9 | 11 |
| Gemini | single | ticket-corrected | 2 | 2 | 2/2 | T2,T3,T4 | – | 0/0 | 0 | 0 | 36 | 7 | 0.0127 | 0 | 0 |
| Gemini | queue | ticket-corrected | 2 | 0 | 2/2 | T2,T3,T4,T5 | – | 0/0 | 0 | 3 | 87 | 22 | 0.0514 | 2 | 2 |
| DeepSeek | queue | ticket-corrected | 2 | 0 | 2/2 | T2,T3,T4,T5 | – | 0/0 | 0 | 2 | 108 | 23 | 0.0048 | 8 | 9 |
| DeepSeek | single | ticket-corrected | 2 | 2 | 2/2 | T2,T3,T4 | – | 0/0 | 0 | 0 | 44 | 6 | 0.0012 | 0 | 0 |

### Model and mode rollup

| Model | Mode | Runs | Failed | Unusable | Goal met | Keyed defects | False conf. (keyed) | Elapsed s (median) | Model latency ms p50/p95 (median of runs) | Browser ms p50/p95 | Input tokens | Output tokens | US$ | Trunc. | Retries | Failed calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Gemini | queue | 8 | 0 | 0 | 8/8 | 6/6 | 0 | 74 | 3035/6754 | 174/940 | 163,792 | 48,420 | 0.2272 | 4 | 4 | 0 |
| Gemini | single | 8 | 0 | 0 | 8/8 | 4/6 | 0 | 40 | 2168/4356 | 64/182 | 77,944 | 11,744 | 0.0742 | 2 | 2 | 0 |
| DeepSeek | single | 8 | 0 | 0 | 8/8 | 2/6 | 0 | 62 | 5872/12014 | 52/154 | 68,157 | 35,359 | 0.0094 | 5 | 6 | 0 |
| DeepSeek | queue | 8 | 0 | 0 | 8/8 | 2/6 | 0 | 109 | 6600/13380 | 120/554 | 155,451 | 103,607 | 0.0226 | 39 | 43 | 0 |

### Individual runs

| Model | Mode | Target | Rep | Run | Status | Goal | Tested | Verified | Defects | False | Unfin. | s | Calls | In | Out | US$ | Model p50/p95 ms | Browser p50/p95 ms | Trunc. | Retries |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Gemini | queue | creator-broken | 1 | `run_52d4703e30af` | partial | yes | R2,R3,R4,R5 | R5 | 1/1 | 0 | 3 | 66 | 24 | 21213 | 7399 | 0.0328 | 3025/7042 | 152/825 | 0 | 0 |
| Gemini | single | creator-broken | 1 | `run_26e821e30662` | completed | yes | R3,R4,R5 | R5 | 1/1 | 0 | 0 | 64 | 10 | 12604 | 2254 | 0.0131 | 2557/9221 | 106/200 | 0 | 0 |
| DeepSeek | single | creator-broken | 1 | `run_7a2cb135c9f8` | completed | yes | R4,R5 | R5 | 1/1 | 0 | 0 | 91 | 11 | 11907 | 6644 | 0.0019 | 5638/12109 | 74/179 | 1 | 1 |
| DeepSeek | queue | creator-broken | 1 | `run_467651dc36a2` | partial | yes | R3,R5 | R5 | 1/1 | 0 | 2 | 128 | 25 | 21384 | 14111 | 0.0035 | 6609/13164 | 156/1073 | 6 | 6 |
| Gemini | single | creator-corrected | 1 | `run_0e1e536eac57` | completed | yes | R3,R4,R5 | – | 0/0 | 0 | 0 | 36 | 9 | 10204 | 1047 | 0.0082 | 2078/3018 | 57/196 | 0 | 0 |
| Gemini | queue | creator-corrected | 1 | `run_e43cbd33057f` | partial | yes | R2,R3,R4,R5 | – | 0/0 | 0 | 3 | 68 | 24 | 21580 | 5483 | 0.0272 | 2682/6465 | 167/1270 | 1 | 1 |
| DeepSeek | queue | creator-corrected | 1 | `run_82fe7fae8411` | partial | yes | R3,R4,R5 | – | 0/0 | 0 | 2 | 108 | 23 | 21395 | 12828 | 0.0033 | 7005/15143 | 116/315 | 6 | 6 |
| DeepSeek | single | creator-corrected | 1 | `run_b2d5a0a45132` | completed | yes | R3,R4,R5 | – | 0/0 | 0 | 0 | 75 | 9 | 9176 | 5772 | 0.0018 | 7315/11918 | 49/145 | 1 | 1 |
| Gemini | queue | ticket-broken | 1 | `run_ca4a403cae45` | partial | yes | T2,T3,T4,T5 | T2,T5 | 2/2 | 0 | 1 | 83 | 24 | 21115 | 6131 | 0.0290 | 3348/5020 | 178/766 | 0 | 0 |
| Gemini | single | ticket-broken | 1 | `run_270bccedb542` | completed | yes | T2,T3,T4 | T2 | 1/2 | 0 | 0 | 36 | 8 | 8957 | 905 | 0.0072 | 2042/3123 | 66/153 | 0 | 0 |
| DeepSeek | single | ticket-broken | 1 | `run_af7e954b35ee` | partial | yes | – | – | 0/2 | 0 | 1 | 39 | 6 | 5933 | 2601 | 0.0010 | 2851/18416 | 134/155 | 1 | 2 |
| DeepSeek | queue | ticket-broken | 1 | `run_ed3bf3a726a0` | completed | yes | T2,T3,T4,T5 | T5 | 1/2 | 0 | 0 | 111 | 22 | 19242 | 14013 | 0.0043 | 6915/13596 | 144/378 | 5 | 5 |
| Gemini | single | ticket-corrected | 1 | `run_df494d7e0b72` | completed | yes | T2,T3,T4 | – | 0/0 | 0 | 0 | 43 | 7 | 8123 | 809 | 0.0065 | 2728/5590 | 148/341 | 0 | 0 |
| Gemini | queue | ticket-corrected | 1 | `run_61b5f4d1bdda` | partial | yes | T2,T3,T4,T5 | – | 0/0 | 0 | 1 | 104 | 20 | 17778 | 4150 | 0.0213 | 3791/9360 | 285/1575 | 0 | 0 |
| DeepSeek | queue | ticket-corrected | 1 | `run_cccd1821ae94` | partial | yes | T2,T3,T4,T5 | – | 0/0 | 0 | 1 | 104 | 24 | 21085 | 12768 | 0.0025 | 6831/10306 | 129/685 | 3 | 4 |
| DeepSeek | single | ticket-corrected | 1 | `run_834106954125` | completed | yes | T2,T3,T4 | – | 0/0 | 0 | 0 | 40 | 6 | 6237 | 2386 | 0.0004 | 3395/9303 | 52/153 | 0 | 0 |
| Gemini | single | creator-broken | 2 | `run_8999f4f354bf` | completed | yes | R3,R4,R5 | R5 | 1/1 | 0 | 0 | 51 | 10 | 11389 | 2536 | 0.0133 | 2063/7824 | 67/211 | 1 | 1 |
| Gemini | queue | creator-broken | 2 | `run_8ef3d0621c6c` | partial | yes | R2,R3,R4,R5 | R5 | 1/1 | 0 | 2 | 78 | 24 | 21248 | 5895 | 0.0283 | 3045/8244 | 238/1193 | 0 | 0 |
| DeepSeek | queue | creator-broken | 2 | `run_938333ea95b5` | partial | yes | R4,R5 | – | 0/1 | 0 | 1 | 90 | 18 | 14738 | 11593 | 0.0020 | 5477/16399 | 91/544 | 5 | 4 |
| DeepSeek | single | creator-broken | 2 | `run_19fdc87e98a7` | completed | yes | R3,R4,R5 | R5 | 1/1 | 0 | 0 | 133 | 12 | 13520 | 8907 | 0.0020 | 8756/21308 | 53/184 | 2 | 2 |
| Gemini | queue | creator-corrected | 2 | `run_61b1c0b22464` | partial | yes | R2,R3,R4,R5 | – | 0/0 | 0 | 4 | 61 | 24 | 21454 | 5902 | 0.0284 | 2939/6312 | 190/976 | 1 | 1 |
| Gemini | single | creator-corrected | 2 | `run_6eb75571f39b` | completed | yes | R3,R4,R5 | – | 0/0 | 0 | 0 | 45 | 9 | 10052 | 2515 | 0.0126 | 2259/8032 | 59/158 | 1 | 1 |
| DeepSeek | single | creator-corrected | 2 | `run_8e0b30695f91` | completed | yes | R3,R4,R5 | – | 0/0 | 0 | 0 | 79 | 8 | 8775 | 4329 | 0.0011 | 6105/16735 | 68/171 | 0 | 0 |
| DeepSeek | queue | creator-corrected | 2 | `run_b3ea8223790f` | partial | yes | R4,R5 | – | 0/0 | 0 | 2 | 102 | 22 | 18487 | 13301 | 0.0025 | 6590/15552 | 111/553 | 5 | 7 |
| Gemini | single | ticket-broken | 2 | `run_fe6c8f711122` | completed | yes | T2,T3,T4 | T2 | 1/2 | 0 | 0 | 35 | 8 | 8973 | 897 | 0.0072 | 1931/2702 | 63/145 | 0 | 0 |
| Gemini | queue | ticket-broken | 2 | `run_d103c84ef8e2` | partial | yes | T2,T3,T4,T5 | T2,T5 | 2/2 | 0 | 2 | 78 | 21 | 18136 | 6988 | 0.0300 | 3300/6107 | 171/904 | 0 | 0 |
| DeepSeek | queue | ticket-broken | 2 | `run_3698ad92cd65` | completed | yes | T2,T3,T4,T5 | – | 0/2 | 0 | 0 | 117 | 23 | 19757 | 13578 | 0.0024 | 6365/11481 | 62/554 | 4 | 6 |
| DeepSeek | single | ticket-broken | 2 | `run_6072abaf4bac` | completed | yes | T2,T3,T4 | – | 0/2 | 0 | 0 | 37 | 6 | 6199 | 2010 | 0.0004 | 4094/8858 | 48/139 | 0 | 0 |
| Gemini | queue | ticket-corrected | 2 | `run_d80157f76dd6` | partial | yes | T2,T3,T4,T5 | – | 0/0 | 0 | 2 | 71 | 24 | 21268 | 6472 | 0.0301 | 2704/7619 | 142/515 | 2 | 2 |
| Gemini | single | ticket-corrected | 2 | `run_b87e5064201a` | completed | yes | T2,T3,T4 | – | 0/0 | 0 | 0 | 28 | 7 | 7642 | 781 | 0.0062 | 2368/2756 | 57/169 | 0 | 0 |
| DeepSeek | single | ticket-corrected | 2 | `run_908dcd015598` | completed | yes | T2,T3,T4 | – | 0/0 | 0 | 0 | 48 | 6 | 6410 | 2710 | 0.0008 | 6364/11114 | 51/150 | 0 | 0 |
| DeepSeek | queue | ticket-corrected | 2 | `run_3815042b5035` | partial | yes | T2,T3,T4,T5 | – | 0/0 | 0 | 1 | 111 | 22 | 19363 | 11415 | 0.0023 | 6032/13095 | 123/1207 | 5 | 5 |
