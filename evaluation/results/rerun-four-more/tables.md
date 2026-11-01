### Summary by model, mode and target

Medians across repetitions. Defects are found/known across runs; `n/a` means no answer key.

| Model | Mode | Target | Runs | Completed | Goal met | Reqs tested (union) | Reqs verified (union) | Defects | False conf. | Unfinished | Elapsed s | Calls | US$ total | Trunc. | Retries |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MiniMax | queue | creator-broken | 2 | 0 | 2/2 | R2,R3,R4,R5 | R5 | 1/2 | 0 | 8 | 120 | 25 | 0.0355 | 0 | 9 |
| MiniMax | single | creator-broken | 2 | 2 | 2/2 | R3,R4,R5 | R5 | 1/2 | 0 | 0 | 138 | 10 | 0.0193 | 1 | 3 |
| GLM | single | creator-broken | 2 | 2 | 2/2 | R2,R3,R4,R5 | R5 | 2/2 | 0 | 0 | 253 | 10 | 0.0342 | 1 | 2 |
| GLM | queue | creator-broken | 2 | 1 | 2/2 | R2,R3,R4,R5 | R5 | 2/2 | 0 | 1 | 279 | 23 | 0.0764 | 3 | 8 |
| MiniMax | single | creator-corrected | 2 | 2 | 2/2 | R3,R4,R5 | – | 0/0 | 0 | 0 | 83 | 8 | 0.0123 | 0 | 0 |
| MiniMax | queue | creator-corrected | 2 | 0 | 2/2 | R2,R3,R4,R5 | – | 0/0 | 0 | 10 | 126 | 24 | 0.0326 | 0 | 5 |
| GLM | queue | creator-corrected | 2 | 0 | 2/2 | R4,R5 | – | 0/0 | 0 | 2 | 256 | 19 | 0.0549 | 3 | 5 |
| GLM | single | creator-corrected | 2 | 1 | 2/2 | R2,R3,R4,R5 | – | 0/0 | 0 | 2 | 266 | 9 | 0.0249 | 0 | 2 |
| MiniMax | queue | ticket-broken | 2 | 0 | 2/2 | T2,T3,T4,T5 | T2,T5 | 4/4 | 0 | 5 | 148 | 25 | 0.0358 | 0 | 1 |
| MiniMax | single | ticket-broken | 2 | 2 | 2/2 | T2,T3,T4 | – | 0/4 | 0 | 0 | 53 | 6 | 0.0077 | 0 | 0 |
| GLM | single | ticket-broken | 2 | 2 | 2/2 | T2,T3,T4 | T2 | 2/4 | 0 | 0 | 138 | 8 | 0.0232 | 0 | 1 |
| GLM | queue | ticket-broken | 2 | 1 | 2/2 | T2,T3,T4,T5 | T2,T5 | 3/4 | 0 | 1 | 287 | 22 | 0.0751 | 5 | 5 |
| MiniMax | single | ticket-corrected | 2 | 2 | 2/2 | T2,T3,T4 | – | 0/0 | 0 | 0 | 64 | 8 | 0.0103 | 0 | 0 |
| MiniMax | queue | ticket-corrected | 2 | 0 | 2/2 | T2,T3,T4,T5 | – | 0/0 | 0 | 3 | 120 | 23 | 0.0305 | 0 | 0 |
| GLM | queue | ticket-corrected | 2 | 2 | 2/2 | T2,T3,T4,T5 | – | 0/0 | 0 | 0 | 174 | 16 | 0.0545 | 2 | 2 |
| GLM | single | ticket-corrected | 2 | 2 | 2/2 | T2,T3,T4 | – | 0/0 | 0 | 0 | 108 | 7 | 0.0200 | 0 | 0 |
| Qwen | single | creator-broken | 1 | 0 | 1/1 | – | – | 0/1 | 0 | 2 | 123 | 8 | 0.0123 | 4 | 4 |
| Qwen | queue | creator-broken | 1 | 0 | 1/1 | – | – | 0/1 | 0 | 2 | 114 | 16 | 0.0197 | 4 | 5 |
| Kimi | single | creator-broken | 1 | 0 | 1/1 | – | – | 0/1 | 0 | 2 | 123 | 8 | 0.0254 | 4 | 4 |
| Kimi | queue | creator-broken | 1 | 0 | 1/1 | – | – | 0/1 | 0 | 2 | 201 | 15 | 0.0360 | 5 | 5 |
| Qwen | queue | creator-corrected | 1 | 0 | 1/1 | – | – | 0/0 | 0 | 2 | 108 | 16 | 0.0188 | 4 | 4 |
| Qwen | single | creator-corrected | 1 | 0 | 1/1 | – | – | 0/0 | 0 | 2 | 123 | 8 | 0.0123 | 4 | 4 |
| Kimi | queue | creator-corrected | 1 | 0 | 1/1 | – | – | 0/0 | 0 | 2 | 258 | 15 | 0.0220 | 2 | 2 |
| Kimi | single | creator-corrected | 1 | 0 | 1/1 | – | – | 0/0 | 0 | 2 | 158 | 6 | 0.0051 | 0 | 0 |
| Qwen | single | ticket-broken | 1 | 0 | 1/1 | – | – | 0/2 | 0 | 1 | 104 | 6 | 0.0074 | 2 | 2 |
| Qwen | queue | ticket-broken | 1 | 0 | 1/1 | – | – | 0/2 | 0 | 1 | 66 | 9 | 0.0108 | 2 | 2 |
| Kimi | single | ticket-broken | 1 | 0 | 1/1 | – | – | 0/2 | 0 | 1 | 230 | 8 | 0.0062 | 0 | 3 |
| Kimi | queue | ticket-broken | 1 | 0 | 1/1 | – | – | 0/2 | 0 | 1 | 106 | 10 | 0.0133 | 0 | 0 |
| Qwen | queue | ticket-corrected | 1 | 0 | 1/1 | – | – | 0/0 | 0 | 1 | 61 | 8 | 0.0102 | 3 | 4 |

### Model and mode rollup

| Model | Mode | Runs | Failed | Unusable | Goal met | Keyed defects | False conf. (keyed) | Elapsed s (median) | Model latency ms p50/p95 (median of runs) | Browser ms p50/p95 | Input tokens | Output tokens | US$ | Trunc. | Retries | Failed calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MiniMax | queue | 8 | 0 | 0 | 8/8 | 5/6 | 0 | 130 | 7958/15374 | 88/663 | 171,704 | 83,873 | 0.1344 | 0 | 15 | 0 |
| MiniMax | single | 8 | 0 | 0 | 8/8 | 1/6 | 0 | 80 | 8250/15969 | 50/158 | 70,662 | 27,895 | 0.0496 | 1 | 3 | 0 |
| GLM | single | 8 | 0 | 0 | 8/8 | 4/6 | 0 | 160 | 12288/37788 | 50/156 | 74,637 | 34,669 | 0.1023 | 1 | 5 | 2 |
| GLM | queue | 8 | 0 | 0 | 8/8 | 5/6 | 0 | 270 | 19374/38974 | 68/458 | 134,100 | 95,916 | 0.2609 | 13 | 20 | 1 |
| Qwen | single | 3 | 0 | 2 | 3/3 | 0/3 | 0 | 123 | 23715/24286 | 137/156 | 22,033 | 16,805 | 0.0319 | 10 | 10 | 0 |
| Qwen | queue | 4 | 0 | 1 | 4/4 | 0/3 | 0 | 87 | 9451/24348 | 162/1011 | 39,277 | 31,555 | 0.0594 | 13 | 15 | 0 |
| Kimi | single | 3 | 1 | 2 | 3/3 | 0/3 | 0 | 158 | 8213/11851 | 171/181 | 16,311 | 8,956 | 0.0366 | 4 | 7 | 5 |
| Kimi | queue | 3 | 0 | 0 | 3/3 | 0/3 | 0 | 201 | 14750/49390 | 161/733 | 24,548 | 20,381 | 0.0712 | 7 | 7 | 8 |

### Individual runs

| Model | Mode | Target | Rep | Run | Status | Goal | Tested | Verified | Defects | False | Unfin. | s | Calls | In | Out | US$ | Model p50/p95 ms | Browser p50/p95 ms | Trunc. | Retries |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MiniMax | queue | creator-broken | 1 | `run_294b3b6dbd48` | partial | yes | R2,R3,R4,R5 | R5 | 1/1 | 0 | 3 | 114 | 24 | 20342 | 10289 | 0.0165 | 7114/15341 | 63/787 | 0 | 4 |
| MiniMax | single | creator-broken | 1 | `run_ae1afaa7f4a3` | completed | yes | R3,R4,R5 | R5 | 1/1 | 0 | 0 | 134 | 11 | 13093 | 5487 | 0.0095 | 8302/23287 | 54/173 | 0 | 2 |
| GLM | single | creator-broken | 1 | `run_e09a5155531d` | completed | yes | R2,R3,R4,R5 | R5 | 1/1 | 0 | 0 | 305 | 12 | 13548 | 8254 | 0.0202 | 26190/54520 | 48/209 | 1 | 2 |
| GLM | queue | creator-broken | 1 | `run_2c145ba56e79` | partial | yes | R2,R3,R4,R5 | R5 | 1/1 | 0 | 1 | 298 | 26 | 21260 | 15087 | 0.0393 | 17834/36752 | 84/308 | 1 | 4 |
| MiniMax | single | creator-corrected | 1 | `run_23a9f4be1905` | completed | yes | R3,R4,R5 | – | 0/0 | 0 | 0 | 83 | 8 | 8747 | 3798 | 0.0066 | 11009/13597 | 47/150 | 0 | 0 |
| MiniMax | queue | creator-corrected | 1 | `run_3c90838f890a` | partial | yes | R3,R4,R5 | – | 0/0 | 0 | 5 | 133 | 23 | 21011 | 9838 | 0.0160 | 8110/17556 | 143/661 | 0 | 2 |
| GLM | queue | creator-corrected | 1 | `run_a417e18e9bd9` | partial | yes | R4,R5 | – | 0/0 | 0 | 1 | 282 | 21 | 17358 | 11449 | 0.0291 | 18626/39983 | 133/617 | 2 | 3 |
| GLM | single | creator-corrected | 1 | `run_00cf948daa5b` | completed | yes | R2,R3,R4,R5 | – | 0/0 | 0 | 0 | 363 | 12 | 13968 | 8885 | 0.0215 | 33855/52988 | 63/149 | 0 | 2 |
| MiniMax | queue | ticket-broken | 1 | `run_7c4f3cb01e13` | partial | yes | T2,T3,T5 | T2,T5 | 2/2 | 0 | 3 | 164 | 26 | 23609 | 12715 | 0.0201 | 9341/16886 | 151/794 | 0 | 1 |
| MiniMax | single | ticket-broken | 1 | `run_7831eecf7e75` | completed | yes | T2,T3,T4 | – | 0/2 | 0 | 0 | 54 | 6 | 6018 | 2039 | 0.0038 | 8431/15037 | 43/149 | 0 | 0 |
| GLM | single | ticket-broken | 1 | `run_6be953cc6add` | completed | yes | T2,T3,T4 | T2 | 1/2 | 0 | 0 | 125 | 8 | 9016 | 3278 | 0.0119 | 11896/33800 | 51/160 | 0 | 0 |
| GLM | queue | ticket-broken | 1 | `run_133a7f52329d` | completed | yes | T2,T3,T4,T5 | T2,T5 | 1/2 | 0 | 0 | 280 | 22 | 18638 | 14611 | 0.0407 | 19285/37966 | 67/285 | 4 | 4 |
| MiniMax | single | ticket-corrected | 1 | `run_074ebf960dc6` | completed | yes | T2,T3,T4 | – | 0/0 | 0 | 0 | 50 | 6 | 6119 | 2081 | 0.0043 | 5071/12078 | 47/169 | 0 | 0 |
| MiniMax | queue | ticket-corrected | 1 | `run_3a94982959ab` | partial | yes | T2,T3,T4,T5 | – | 0/0 | 0 | 1 | 133 | 23 | 20926 | 10479 | 0.0161 | 8981/15913 | 54/243 | 0 | 0 |
| GLM | queue | ticket-corrected | 1 | `run_c2c49842d152` | completed | yes | T2,T3,T4,T5 | – | 0/0 | 0 | 0 | 190 | 18 | 16252 | 9960 | 0.0299 | 17369/25409 | 57/658 | 2 | 2 |
| GLM | single | ticket-corrected | 1 | `run_bdec027e4ead` | completed | yes | T2,T3,T4 | – | 0/0 | 0 | 0 | 111 | 7 | 7657 | 2593 | 0.0096 | 11303/29225 | 44/138 | 0 | 0 |
| MiniMax | single | creator-broken | 2 | `run_39a945f181e5` | completed | yes | R4,R5 | – | 0/1 | 0 | 0 | 142 | 10 | 11456 | 5722 | 0.0098 | 12435/24177 | 57/161 | 1 | 1 |
| MiniMax | queue | creator-broken | 2 | `run_50e82f30a1b5` | partial | yes | R2,R4,R5 | – | 0/1 | 0 | 5 | 126 | 26 | 23023 | 10972 | 0.0190 | 7907/15156 | 71/679 | 0 | 5 |
| GLM | queue | creator-broken | 2 | `run_1362f2073ef6` | completed | yes | R2,R3,R4,R5 | R5 | 1/1 | 0 | 0 | 260 | 20 | 15668 | 13598 | 0.0371 | 19462/40570 | 70/287 | 2 | 4 |
| GLM | single | creator-broken | 2 | `run_d72d8ffc4d7b` | completed | yes | R3,R4,R5 | R5 | 1/1 | 0 | 0 | 202 | 9 | 10035 | 4774 | 0.0141 | 12219/41776 | 57/201 | 0 | 0 |
| MiniMax | queue | creator-corrected | 2 | `run_748a70c0fe31` | partial | yes | R2,R3,R4,R5 | – | 0/0 | 0 | 5 | 119 | 25 | 21504 | 10494 | 0.0166 | 7216/12977 | 52/553 | 0 | 3 |
| MiniMax | single | creator-corrected | 2 | `run_d17aaa443fc7` | completed | yes | R3,R4,R5 | – | 0/0 | 0 | 0 | 84 | 8 | 8983 | 3601 | 0.0057 | 8198/16901 | 52/154 | 0 | 0 |
| GLM | single | creator-corrected | 2 | `run_d0b5e6292f6e` | partial | yes | – | – | 0/0 | 0 | 2 | 169 | 6 | 3830 | 810 | 0.0034 | 12357/12847 | 127/150 | 0 | 0 |
| GLM | queue | creator-corrected | 2 | `run_39e65dcd3536` | partial | yes | R4,R5 | – | 0/0 | 0 | 1 | 230 | 17 | 14337 | 9959 | 0.0258 | 20138/58885 | 110/508 | 1 | 2 |
| MiniMax | single | ticket-broken | 2 | `run_3be0ca6de7df` | completed | yes | T2,T3,T4 | – | 0/2 | 0 | 0 | 52 | 6 | 5949 | 2052 | 0.0039 | 5901/17760 | 40/148 | 0 | 0 |
| MiniMax | queue | ticket-broken | 2 | `run_f011fd223f80` | partial | yes | T2,T3,T4,T5 | T2,T5 | 2/2 | 0 | 2 | 133 | 24 | 21646 | 10029 | 0.0157 | 8009/15408 | 105/500 | 0 | 0 |
| GLM | queue | ticket-broken | 2 | `run_23c3f7052bd9` | partial | yes | T2,T3,T4,T5 | T2,T5 | 2/2 | 0 | 1 | 294 | 22 | 18584 | 12858 | 0.0345 | 20790/48575 | 57/409 | 1 | 1 |
| GLM | single | ticket-broken | 2 | `run_627a73f87fbe` | completed | yes | T2,T3,T4 | T2 | 1/2 | 0 | 0 | 151 | 8 | 8857 | 3292 | 0.0113 | 10003/50804 | 41/165 | 0 | 1 |
| MiniMax | queue | ticket-corrected | 2 | `run_0c8d76ea7b14` | partial | yes | T2,T3,T4,T5 | – | 0/0 | 0 | 2 | 107 | 23 | 19643 | 9057 | 0.0144 | 7491/13771 | 108/665 | 0 | 0 |
| MiniMax | single | ticket-corrected | 2 | `run_e1c97c59e38e` | completed | yes | T2,T3,T4 | – | 0/0 | 0 | 0 | 77 | 9 | 10297 | 3115 | 0.0059 | 5930/11716 | 54/184 | 0 | 0 |
| GLM | single | ticket-corrected | 2 | `run_1b66ecea7112` | completed | yes | T2,T3,T4 | – | 0/0 | 0 | 0 | 106 | 7 | 7726 | 2783 | 0.0104 | 14106/21343 | 50/151 | 0 | 0 |
| GLM | queue | ticket-corrected | 2 | `run_ba8e41ba49d6` | completed | yes | T2,T3,T4,T5 | – | 0/0 | 0 | 0 | 159 | 14 | 12003 | 8394 | 0.0246 | 20235/31467 | 62/830 | 0 | 0 |
| Qwen | single | creator-broken | 1 | `run_66e076d32d2e` | partial | yes | – | – | 0/1 | 0 | 2 | 123 | 8 | 7909 | 6535 | 0.0123 | 23905/24286 | 162/218 | 4 | 4 |
| Qwen | queue | creator-broken | 1 | `run_47659314d046` | partial | yes | – | – | 0/1 | 0 | 2 | 114 | 16 | 12796 | 10495 | 0.0197 | 11008/31494 | 179/1303 | 4 | 5 |
| Kimi | single | creator-broken | 1 | `run_116c5eaade42` | partial | yes | – | – | 0/1 | 0 | 2 | 123 | 8 | 7536 | 6688 | 0.0254 | 13498/39595 | 177/224 | 4 | 4 |
| Kimi | queue | creator-broken | 1 | `run_50fabad6a553` | partial | yes | – | – | 0/1 | 0 | 2 | 201 | 15 | 9619 | 10703 | 0.0360 | 14750/49390 | 152/835 | 5 | 5 |
| Qwen | queue | creator-corrected | 1 | `run_2adfac2aab00` | partial | yes | – | – | 0/0 | 0 | 2 | 108 | 16 | 12783 | 9931 | 0.0188 | 9167/24336 | 159/1326 | 4 | 4 |
| Qwen | single | creator-corrected | 1 | `run_1b61866bea59` | partial | yes | – | – | 0/0 | 0 | 2 | 123 | 8 | 7990 | 6567 | 0.0123 | 23715/24031 | 125/148 | 4 | 4 |
| Kimi | queue | creator-corrected | 1 | `run_94489c99564a` | partial | yes | – | – | 0/0 | 0 | 2 | 258 | 15 | 7608 | 6260 | 0.0220 | 16619/55091 | 161/733 | 2 | 2 |
| Kimi | single | creator-corrected | 1 | `run_f6c5f7c6d57b` | partial | yes | – | – | 0/0 | 0 | 2 | 158 | 6 | 3759 | 1025 | 0.0051 | 6508/11851 | 171/181 | 0 | 0 |
| Qwen | single | ticket-broken | 1 | `run_4165af8221d6` | partial | yes | – | – | 0/2 | 0 | 1 | 104 | 6 | 6134 | 3703 | 0.0074 | 14628/27608 | 137/156 | 2 | 2 |
| Qwen | queue | ticket-broken | 1 | `run_25169568aca0` | partial | yes | – | – | 0/2 | 0 | 1 | 66 | 9 | 7280 | 5686 | 0.0108 | 8837/24359 | 165/719 | 2 | 2 |
| Kimi | single | ticket-broken | 1 | `run_57548fede38c` | failed | yes | – | – | 0/2 | 0 | 1 | 230 | 8 | 5016 | 1243 | 0.0062 | 8213/10731 | 136/170 | 0 | 3 |
| Kimi | queue | ticket-broken | 1 | `run_2a00162093c5` | partial | yes | – | – | 0/2 | 0 | 1 | 106 | 10 | 7321 | 3418 | 0.0133 | 11476/26960 | 166/622 | 0 | 0 |
| Qwen | queue | ticket-corrected | 1 | `run_b645d73b7a18` | partial | yes | – | – | 0/0 | 0 | 1 | 61 | 8 | 6418 | 5443 | 0.0102 | 9735/23895 | 79/690 | 3 | 4 |
