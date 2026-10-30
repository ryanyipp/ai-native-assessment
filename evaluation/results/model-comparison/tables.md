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
