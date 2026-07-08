# Stage 4b · Reacceptance 触发器特殊性检验 (2026-07-05 20:30:48)

MIN_DISTANCE_ATR = 4.0, OBSERVE_N = 80, STOP_ATR = 1.5, COST_ATR = 0.05

目标锚：PrevClose（统一），bootstrap n=5000

总交易数: 57753

## 1. 触发器样本数分布

| trigger           |   agri_czce |   agri_dce |   black |   energy_chem |   metals |
|:------------------|------------:|-----------:|--------:|--------------:|---------:|
| breakout_reversal |        2684 |       5010 |    2611 |          2490 |     3995 |
| long_body_reject  |        2126 |       4328 |    2308 |          1568 |     1927 |
| no_trigger        |        1137 |       2134 |    1106 |           978 |     1360 |
| random_time       |         150 |        239 |     122 |           149 |      278 |
| reacceptance      |         149 |        228 |     121 |           145 |      282 |
| volume_spike      |        3526 |       6465 |    3262 |          2940 |     3935 |

## 2. 板块 × 触发器 期望净值（ATR/笔）

| trigger | agri_czce | agri_dce | black | energy_chem | metals |
|---|---|---|---|---|---|
| reacceptance | -0.179(n=149) | -0.006(n=228) | +0.068(n=121) | +0.253(n=145) | -0.173(n=282) |
| no_trigger | +0.135(n=1137) | +0.016(n=2134) | -0.091(n=1106) | -0.049(n=978) | -0.119(n=1360) |
| long_body_reject | +0.034(n=2126) | +0.016(n=4328) | -0.134(n=2308) | -0.001(n=1568) | +0.005(n=1927) |
| volume_spike | +0.199(n=3526) | -0.082(n=6465) | -0.138(n=3262) | -0.018(n=2940) | -0.166(n=3935) |
| random_time | -0.040(n=150) | +0.113(n=239) | -0.275(n=122) | -0.115(n=149) | -0.283(n=278) |
| breakout_reversal | +0.026(n=2684) | -0.019(n=5010) | -0.095(n=2611) | -0.044(n=2490) | -0.067(n=3995) |

## 3. 单触发器期望净值 vs 0（每板块）

| sector | trigger | n | mean | 95% CI | cluster CI | p_one_sided |
|---|---|---|---|---|---|---|
| agri_czce | reacceptance | 149 | -0.179 | [-0.470, +0.135] | [-0.533, +0.182] | 0.8716 (cluster p=0.8502) |
| agri_czce | no_trigger | 1137 | +0.135 | [-0.048, +0.321] | [-0.077, +0.373] | 0.0782 (cluster p=0.1248) |
| agri_czce | long_body_reject | 2126 | +0.034 | [-0.074, +0.147] | [-0.102, +0.175] | 0.2761 (cluster p=0.3066) |
| agri_czce | volume_spike | 3526 | +0.199 | [+0.077, +0.332] | [-0.120, +0.649] | 0.0014 (cluster p=0.2746) |
| agri_czce | random_time | 150 | -0.040 | [-0.416, +0.369] | [-0.386, +0.293] | 0.5784 (cluster p=0.6104) |
| agri_czce | breakout_reversal | 2684 | +0.026 | [-0.074, +0.123] | [-0.127, +0.187] | 0.3039 (cluster p=0.3702) |
| agri_dce | reacceptance | 228 | -0.006 | [-0.237, +0.240] | [-0.305, +0.337] | 0.5198 (cluster p=0.5140) |
| agri_dce | no_trigger | 2134 | +0.016 | [-0.094, +0.131] | [-0.113, +0.137] | 0.3918 (cluster p=0.4178) |
| agri_dce | long_body_reject | 4328 | +0.016 | [-0.059, +0.091] | [-0.126, +0.163] | 0.3432 (cluster p=0.4180) |
| agri_dce | volume_spike | 6465 | -0.082 | [-0.144, -0.020] | [-0.142, -0.019] | 0.9949 (cluster p=0.9942) |
| agri_dce | random_time | 239 | +0.113 | [-0.223, +0.457] | [-0.228, +0.477] | 0.2611 (cluster p=0.2666) |
| agri_dce | breakout_reversal | 5010 | -0.019 | [-0.092, +0.052] | [-0.139, +0.093] | 0.7002 (cluster p=0.6484) |
| black | reacceptance | 121 | +0.068 | [-0.233, +0.382] | [-0.301, +0.564] | 0.3358 (cluster p=0.3710) |
| black | no_trigger | 1106 | -0.091 | [-0.242, +0.066] | [-0.197, +0.012] | 0.8755 (cluster p=0.9554) |
| black | long_body_reject | 2308 | -0.134 | [-0.234, -0.032] | [-0.307, +0.027] | 0.9954 (cluster p=0.9490) |
| black | volume_spike | 3262 | -0.138 | [-0.222, -0.054] | [-0.237, -0.050] | 0.9992 (cluster p=0.9998) |
| black | random_time | 122 | -0.275 | [-0.704, +0.210] | [-0.665, +0.084] | 0.8739 (cluster p=0.9422) |
| black | breakout_reversal | 2611 | -0.095 | [-0.191, +0.003] | [-0.272, +0.048] | 0.9725 (cluster p=0.8896) |
| energy_chem | reacceptance | 145 | +0.253 | [-0.091, +0.624] | [-0.336, +0.966] | 0.0889 (cluster p=0.2410) |
| energy_chem | no_trigger | 978 | -0.049 | [-0.204, +0.115] | [-0.145, +0.073] | 0.7197 (cluster p=0.8078) |
| energy_chem | long_body_reject | 1568 | -0.001 | [-0.124, +0.132] | [-0.104, +0.060] | 0.5039 (cluster p=0.4586) |
| energy_chem | volume_spike | 2940 | -0.018 | [-0.111, +0.077] | [-0.120, +0.142] | 0.6399 (cluster p=0.6028) |
| energy_chem | random_time | 149 | -0.115 | [-0.468, +0.272] | [-0.490, +0.247] | 0.7266 (cluster p=0.6702) |
| energy_chem | breakout_reversal | 2490 | -0.044 | [-0.145, +0.060] | [-0.157, +0.139] | 0.7992 (cluster p=0.7036) |

## 4. 每触发器 vs no_trigger baseline（非配对 cluster bootstrap 差值）

H1: trigger > no_trigger.

| sector | trigger | n_trig | n_base | mean_diff | cluster 95% CI | p_one_sided |
|---|---|---|---|---|---|---|
| agri_czce | reacceptance | 149 | 1137 | -0.315 | [-0.725, +0.099] | 0.9318 |
| agri_czce | long_body_reject | 2126 | 1137 | -0.101 | [-0.364, +0.155] | 0.7484 |
| agri_czce | volume_spike | 3526 | 1137 | +0.064 | [-0.355, +0.570] | 0.4360 |
| agri_czce | random_time | 150 | 1137 | -0.175 | [-0.581, +0.220] | 0.8044 |
| agri_czce | breakout_reversal | 2684 | 1137 | -0.109 | [-0.382, +0.159] | 0.7578 |
| agri_dce | reacceptance | 228 | 2134 | -0.022 | [-0.354, +0.342] | 0.5490 |
| agri_dce | long_body_reject | 4328 | 2134 | +0.000 | [-0.184, +0.186] | 0.4908 |
| agri_dce | volume_spike | 6465 | 2134 | -0.097 | [-0.235, +0.042] | 0.9120 |
| agri_dce | random_time | 239 | 2134 | +0.097 | [-0.271, +0.487] | 0.3028 |
| agri_dce | breakout_reversal | 5010 | 2134 | -0.035 | [-0.203, +0.134] | 0.6626 |
| black | reacceptance | 121 | 1106 | +0.159 | [-0.225, +0.664] | 0.2252 |
| black | long_body_reject | 2308 | 1106 | -0.043 | [-0.244, +0.150] | 0.6542 |
| black | volume_spike | 3262 | 1106 | -0.047 | [-0.194, +0.093] | 0.7392 |
| black | random_time | 122 | 1106 | -0.184 | [-0.572, +0.178] | 0.8350 |
| black | breakout_reversal | 2611 | 1106 | -0.004 | [-0.209, +0.178] | 0.5140 |
| energy_chem | reacceptance | 145 | 978 | +0.302 | [-0.304, +1.034] | 0.2068 |
| energy_chem | long_body_reject | 1568 | 978 | +0.048 | [-0.107, +0.169] | 0.2476 |
| energy_chem | volume_spike | 2940 | 978 | +0.031 | [-0.129, +0.214] | 0.3536 |
| energy_chem | random_time | 149 | 978 | -0.066 | [-0.465, +0.315] | 0.5878 |
| energy_chem | breakout_reversal | 2490 | 978 | +0.005 | [-0.162, +0.217] | 0.4744 |

## 5. ALL_ex_metals 聚合 · 触发器对比

| trigger | n | mean | 95% CI | cluster CI | p_vs_0 | diff vs no_trigger | diff CI | diff p |
|---|---|---|---|---|---|---|---|---|
| reacceptance | 643 | +0.026 | [-0.127, +0.173] | [-0.185, +0.262] | 0.4256 | +0.019 | [-0.208, +0.267] | 0.4382 |
| no_trigger | 5355 | +0.007 | [-0.068, +0.080] | [-0.068, +0.087] | 0.4412 | - | - | - |
| long_body_reject | 10330 | -0.016 | [-0.066, +0.033] | [-0.092, +0.065] | 0.6620 | -0.024 | [-0.130, +0.084] | 0.6594 |
| volume_spike | 16193 | -0.020 | [-0.065, +0.026] | [-0.106, +0.100] | 0.6802 | -0.028 | [-0.148, +0.122] | 0.6714 |
| random_time | 660 | -0.045 | [-0.234, +0.151] | [-0.230, +0.139] | 0.6832 | -0.052 | [-0.257, +0.150] | 0.6832 |
| breakout_reversal | 12795 | -0.030 | [-0.075, +0.015] | [-0.099, +0.039] | 0.7974 | -0.037 | [-0.141, +0.066] | 0.7550 |

## 6. 判决要点

- **reacceptance 特殊 ↔ 假设成立**：reacceptance vs no_trigger 差值 > 0 且 cluster CI 排除 0
- **reacceptance 不特殊 ↔ 主题真实资产是距离档**：所有触发器 vs no_trigger 差值 CI 都跨 0
- **触发器排名**：单锚点 vs 0 显著 + diff vs baseline 显著的触发器可考虑

