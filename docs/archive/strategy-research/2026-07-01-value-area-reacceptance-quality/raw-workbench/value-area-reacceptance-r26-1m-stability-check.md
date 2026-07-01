# value_area_reacceptance R26：1m 候选稳定性检查

> 类型：Workbench / 单轮实验记录  
> 状态：已完成  
> 日期：2026-07-01  
> 前置记录：[R25 actual RR 口径下 1m 与 5m 对照](./value-area-reacceptance-r25-1m-vs-5m-actual-rr.md)

## 1. 实验问题

R25 显示：

```text
在 m/SR、A4 near-POC、actual RR=0.6~0.8 的候选条件下，
1m 的正期望强于 5m。
```

但 R25 的主候选依赖：

```text
period = 1m
target_distance_ratio = 0.8
min_price_raw_rr = 0.8
min_reaccept_ticks = 2 / 3 合并
symbols = DCE.m2601 / CZCE.SR601
```

本轮不扩大样本，只做稳定性检查：

```text
1. A4_ratio_80 是否真的优于原始 POC / POC band；
2. min_reaccept_ticks=2 与 3 哪个贡献更大；
3. 当前正期望是否只由单一品种或单笔大盈利撑起。
```

## 2. 实验设置

固定：

```text
period = 1m
symbols = DCE.m2601 / CZCE.SR601
min_price_raw_rr = 0.8
max_hold_bars = 60
stop_widen_multiplier = 1.5
strict_close_exit = true
min_target_ticks = 8
```

测试 target 模式：

| variant | target_band_ticks | target_distance_ratio | 含义 |
| --- | ---: | ---: | --- |
| A0_poc | 0 | 1.0 | 原始 POC 单点目标 |
| A1_band_1 | 1 | 1.0 | POC ±1 tick 区域目标 |
| A4_ratio_80 | 0 | 0.8 | entry → POC 距离 80% 兑现 |

同时拆解：

```text
min_reaccept_ticks = 2 / 3
```

有效回测 ID：

```text
666~677
```

## 3. target 模式总览

| target | n | win_pct | breakeven_win_pct | win_edge_pct | payoff | expectancy_R | net_pnl | median_pnl | worst_R | loss_ge_0.5R | loss_ge_0.8R | best_R | best_pnl_share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A0_poc | 10 | 60.0% | 39.6% | 20.4% | 1.527 | 0.175 | 3492 | 370 | -0.540 | 1 | 0 | 0.987 | 56.5% |
| A1_band_1 | 10 | 60.0% | 39.6% | 20.4% | 1.527 | 0.175 | 3492 | 370 | -0.540 | 1 | 0 | 0.987 | 56.5% |
| A4_ratio_80 | 7 | 71.4% | 25.3% | 46.1% | 2.951 | 0.340 | 4758 | 520 | -0.240 | 0 | 0 | 0.987 | 41.5% |

观察：

```text
A4_ratio_80 明显优于 A0/A1；
A4 交易数更少，但 win_pct、payoff、expectancy_R、median、worst_R 全部改善；
A4 没有 loss_ge_0.5R，亏损尾部更收敛。
```

A0 与 A1 在本轮完全相同，说明：

```text
在 actual RR=0.8 的较高门槛下，±1 tick band 没有额外改变成交结果；
真正起作用的是 80% distance target，而不是 1 tick band。
```

## 4. min_reaccept_ticks 拆解

| target | ticks | n | win_pct | breakeven_win_pct | win_edge_pct | payoff | expectancy_R | net_pnl | median_pnl | worst_R | loss_ge_0.5R | loss_ge_0.8R | best_R | best_pnl_share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A0_poc | 2 | 6 | 50.0% | 35.3% | 14.7% | 1.831 | 0.140 | 1684 | 127 | -0.540 | 1 | 0 | 0.987 | 117.2% |
| A0_poc | 3 | 4 | 75.0% | 45.1% | 29.9% | 1.220 | 0.226 | 1808 | 537 | -0.340 | 0 | 0 | 0.707 | 78.2% |
| A1_band_1 | 2 | 6 | 50.0% | 35.3% | 14.7% | 1.831 | 0.140 | 1684 | 127 | -0.540 | 1 | 0 | 0.987 | 117.2% |
| A1_band_1 | 3 | 4 | 75.0% | 45.1% | 29.9% | 1.220 | 0.226 | 1808 | 537 | -0.340 | 0 | 0 | 0.707 | 78.2% |
| A4_ratio_80 | 2 | 5 | 60.0% | 22.4% | 37.6% | 3.458 | 0.312 | 3124 | 520 | -0.240 | 0 | 0 | 0.987 | 63.2% |
| A4_ratio_80 | 3 | 2 | 100.0% | 0.0% | 100.0% | 0.000 | 0.408 | 1634 | 817 | 0.110 | 0 | 0 | 0.707 | 86.5% |

观察：

```text
A4 下 ticks=2 和 ticks=3 都为正；
ticks=3 更干净，但只有 2 笔，不能单独作为结论；
ticks=2 提供主要样本，仍保持正期望且 worst_R 只有 -0.24。
```

因此当前不建议只保留 ticks=3：

```text
min_reaccept_ticks = 2 / 3 合并仍是更稳妥候选。
```

## 5. 分品种稳定性

| target | symbol | n | win_pct | breakeven_win_pct | win_edge_pct | payoff | expectancy_R | net_pnl | median_pnl | worst_R | loss_ge_0.5R | loss_ge_0.8R | best_R | best_pnl_share |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A0_poc | CZCE.SR601 | 7 | 57.1% | 53.7% | 3.5% | 0.864 | 0.026 | 370 | 220 | -0.540 | 1 | 0 | 0.608 | 328.6% |
| A0_poc | DCE.m2601 | 3 | 66.7% | 13.6% | 53.1% | 6.368 | 0.520 | 3122 | 1414 | -0.133 | 0 | 0 | 0.987 | 63.2% |
| A1_band_1 | CZCE.SR601 | 7 | 57.1% | 53.7% | 3.5% | 0.864 | 0.026 | 370 | 220 | -0.540 | 1 | 0 | 0.608 | 328.6% |
| A1_band_1 | DCE.m2601 | 3 | 66.7% | 13.6% | 53.1% | 6.368 | 0.520 | 3122 | 1414 | -0.133 | 0 | 0 | 0.987 | 63.2% |
| A4_ratio_80 | CZCE.SR601 | 4 | 75.0% | 40.5% | 34.5% | 1.469 | 0.204 | 1636 | 370 | -0.240 | 0 | 0 | 0.688 | 84.1% |
| A4_ratio_80 | DCE.m2601 | 3 | 66.7% | 13.6% | 53.1% | 6.368 | 0.520 | 3122 | 1414 | -0.133 | 0 | 0 | 0.987 | 63.2% |

关键变化：

```text
A4 对 DCE.m 的结果基本不变；
A4 的主要价值在 SR：
  SR net_pnl 从 +370 提高到 +1636；
  SR payoff 从 0.864 提高到 1.469；
  SR expectancy_R 从 0.026 提高到 0.204；
  SR worst_R 从 -0.540 收敛到 -0.240。
```

这说明 R25 中 1m 优于 5m，并不只是 DCE.m 强；A4 对 SR 的改善是关键。

## 6. 单笔贡献检查

A4_ratio_80 的单笔清算：

| symbol | ticks | open_time | net_pnl | close_reason |
| --- | ---: | --- | ---: | --- |
| DCE.m2601 | 2 | 2025-10-22 09:24:00 | +1974 | time_exit |
| DCE.m2601 | 2 | 2025-11-24 13:47:00 | -266 | time_exit |
| DCE.m2601 | 3 | 2025-10-22 09:25:00 | +1414 | time_exit |
| CZCE.SR601 | 2 | 2025-09-19 14:03:00 | +520 | force_flat |
| CZCE.SR601 | 2 | 2025-09-25 10:48:00 | -480 | time_exit |
| CZCE.SR601 | 2 | 2025-10-22 09:18:00 | +1376 | take_profit |
| CZCE.SR601 | 3 | 2025-09-19 14:06:00 | +220 | force_flat |

观察：

```text
A4 的盈利不是单一品种单一交易独自撑起；
最大单笔 +1974，占总净收益约 41.5%；
DCE.m 与 SR 都有正贡献；
SR 仍有一笔 -480，但没有接近 0.5R 的亏损。
```

仍需注意：

```text
A4 样本只有 7 笔，仍然不能替代扩样验证。
```

## 7. 结论

R26 支持当前候选的稳定性：

```text
1m + no-rb + actual RR=0.8 + A4_ratio_80
```

不是单纯由“POC 单点”或“±1 tick band”带来的偶然结果。

更具体：

```text
1. A4_ratio_80 明显优于 A0_poc / A1_band_1；
2. A4 对 SR 的改善最关键，使 SR 从弱正期望变成明显正期望；
3. min_reaccept_ticks=2 / 3 都为正，但 ticks=3 样本过少，不建议单独收窄；
4. 当前结果不是完全由单笔盈利撑起，但样本仍小。
```

当前候选保持为：

```text
period = 1m
symbols = DCE.m2601 / CZCE.SR601
exclude = SHFE.rb2601
target_distance_ratio = 0.8
target_band_ticks = 0
min_price_raw_rr = 0.8
min_reaccept_ticks = 2 / 3
```

## 8. 下一步

不扩大样本时，已经没有必要继续做大网格。

若继续做小验证，优先级应低于扩样，但可以考虑：

```text
1. 检查 A4 下 time_exit 的 MFE/target，判断是否还需要更早兑现；
2. 检查 rb 是否存在单独可救的高 RR 子集；
3. 检查当前候选是否对 max_hold_bars=60 敏感。
```

更推荐的下一步仍然是扩样验证：

```text
固定 R26 候选，扩大时间样本或合约样本，验证 win_pct、payoff、expectancy_R 和 SR 稳定性。
```
