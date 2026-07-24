# Stage 4b (15m) · Reacceptance 触发器特殊性检验 (2026-07-05 20:37:01)

周期：15 分钟（从 5m 聚合）

MIN_DISTANCE_ATR = 4.0, OBSERVE_N = 27 bars ≈ 405min

STOP_ATR = 1.5, COST_ATR = 0.05, ATR_WINDOW = 20

目标锚：PrevClose，bootstrap n=5000

总交易数: 11033

## 1. 触发器样本数分布

| trigger           |   agri_czce |   agri_dce |   black |   energy_chem |   metals |
|:------------------|------------:|-----------:|--------:|--------------:|---------:|
| breakout_reversal |         415 |        927 |     483 |           447 |      740 |
| long_body_reject  |         187 |        430 |     204 |           149 |      262 |
| no_trigger        |         429 |        918 |     478 |           447 |      647 |
| random_time       |           8 |         16 |       8 |            24 |       36 |
| reacceptance      |           7 |         16 |       7 |            21 |       37 |
| volume_spike      |         563 |       1054 |     606 |           561 |      906 |

## 2. 板块 × 触发器 期望净值（ATR/笔）

| trigger | agri_czce | agri_dce | black | energy_chem | metals |
|---|---|---|---|---|---|
| reacceptance | - | - | - | -0.071(n=21) | -0.148(n=37) |
| no_trigger | -0.039(n=429) | +0.079(n=918) | -0.163(n=478) | -0.069(n=447) | -0.033(n=647) |
| long_body_reject | -0.075(n=187) | +0.051(n=430) | -0.164(n=204) | -0.118(n=149) | +0.053(n=262) |
| volume_spike | +0.017(n=563) | +0.023(n=1054) | -0.279(n=606) | -0.109(n=561) | -0.063(n=906) |
| random_time | - | - | - | -0.027(n=24) | +0.181(n=36) |
| breakout_reversal | -0.167(n=415) | +0.112(n=927) | -0.090(n=483) | -0.085(n=447) | -0.081(n=740) |

## 3. 单触发器 vs 0（每板块）

| sector | trigger | n | mean | cluster CI | cluster p |
|---|---|---|---|---|---|
| agri_czce | no_trigger | 429 | -0.039 | [-0.180, +0.124] | 0.7100 |
| agri_czce | long_body_reject | 187 | -0.075 | [-0.350, +0.174] | 0.7070 |
| agri_czce | volume_spike | 563 | +0.017 | [-0.124, +0.205] | 0.4508 |
| agri_czce | breakout_reversal | 415 | -0.167 | [-0.360, +0.041] | 0.9466 |
| agri_dce | no_trigger | 918 | +0.079 | [-0.068, +0.218] | 0.1572 |
| agri_dce | long_body_reject | 430 | +0.051 | [-0.150, +0.236] | 0.3034 |
| agri_dce | volume_spike | 1054 | +0.023 | [-0.127, +0.163] | 0.3824 |
| agri_dce | breakout_reversal | 927 | +0.112 | [-0.079, +0.294] | 0.1258 |
| black | no_trigger | 478 | -0.163 | [-0.281, -0.035] | 0.9940 |
| black | long_body_reject | 204 | -0.164 | [-0.464, +0.181] | 0.8298 |
| black | volume_spike | 606 | -0.279 | [-0.445, -0.085] | 0.9978 |
| black | breakout_reversal | 483 | -0.090 | [-0.205, +0.024] | 0.9424 |
| energy_chem | reacceptance | 21 | -0.071 | [-0.452, +0.883] | 0.6286 |
| energy_chem | no_trigger | 447 | -0.069 | [-0.276, +0.151] | 0.7130 |
| energy_chem | long_body_reject | 149 | -0.118 | [-0.564, +0.342] | 0.7018 |
| energy_chem | volume_spike | 561 | -0.109 | [-0.331, +0.174] | 0.7684 |
| energy_chem | random_time | 24 | -0.027 | [-1.550, +0.892] | 0.5898 |
| energy_chem | breakout_reversal | 447 | -0.085 | [-0.256, +0.129] | 0.7868 |

## 4. 每触发器 vs no_trigger baseline（H1: trigger > no_trigger）

| sector | trigger | n_trig | n_base | mean_diff | cluster CI | p |
|---|---|---|---|---|---|---|
| agri_czce | long_body_reject | 187 | 429 | -0.036 | [-0.357, +0.250] | 0.5952 |
| agri_czce | volume_spike | 563 | 429 | +0.056 | [-0.161, +0.286] | 0.3008 |
| agri_czce | breakout_reversal | 415 | 429 | -0.128 | [-0.376, +0.122] | 0.8412 |
| agri_dce | long_body_reject | 430 | 918 | -0.028 | [-0.272, +0.210] | 0.5812 |
| agri_dce | volume_spike | 1054 | 918 | -0.056 | [-0.269, +0.147] | 0.6944 |
| agri_dce | breakout_reversal | 927 | 918 | +0.033 | [-0.207, +0.268] | 0.3816 |
| black | long_body_reject | 204 | 478 | -0.001 | [-0.325, +0.366] | 0.5022 |
| black | volume_spike | 606 | 478 | -0.116 | [-0.328, +0.113] | 0.8486 |
| black | breakout_reversal | 483 | 478 | +0.074 | [-0.099, +0.236] | 0.1876 |
| energy_chem | reacceptance | 21 | 447 | -0.002 | [-0.472, +0.962] | 0.4984 |
| energy_chem | long_body_reject | 149 | 447 | -0.049 | [-0.549, +0.445] | 0.6104 |
| energy_chem | volume_spike | 561 | 447 | -0.041 | [-0.362, +0.307] | 0.5836 |
| energy_chem | random_time | 24 | 447 | +0.042 | [-1.540, +0.983] | 0.4962 |
| energy_chem | breakout_reversal | 447 | 447 | -0.016 | [-0.306, +0.277] | 0.5500 |

## 5. ALL_ex_metals 聚合

| trigger | n | mean | cluster CI | p_vs_0 | diff vs no_trigger | diff CI | diff p |
|---|---|---|---|---|---|---|---|
| reacceptance | 51 | -0.112 | [-0.523, +0.400] | 0.7050 | -0.088 | [-0.501, +0.417] | 0.6482 |
| no_trigger | 2272 | -0.023 | [-0.107, +0.066] | 0.7008 | - | - | - |
| long_body_reject | 970 | -0.045 | [-0.184, +0.102] | 0.7262 | -0.021 | [-0.183, +0.145] | 0.6054 |
| volume_spike | 2784 | -0.071 | [-0.166, +0.024] | 0.9188 | -0.047 | [-0.176, +0.081] | 0.7610 |
| random_time | 56 | -0.255 | [-0.866, +0.331] | 0.8134 | -0.231 | [-0.859, +0.362] | 0.7906 |
| breakout_reversal | 2272 | -0.020 | [-0.118, +0.086] | 0.6546 | +0.003 | [-0.127, +0.139] | 0.4918 |

