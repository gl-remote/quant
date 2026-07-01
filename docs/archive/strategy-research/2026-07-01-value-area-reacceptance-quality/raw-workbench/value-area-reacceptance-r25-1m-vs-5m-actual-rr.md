# value_area_reacceptance R25：actual RR 口径下 1m 与 5m 对照

> 类型：Workbench / 单轮实验记录
> 状态：已完成
> 日期：2026-07-01
> 前置记录：[R16-R24 actual RR 重整记录](./value-area-reacceptance-r16-r24-1m-actual-rr-summary.md)

## 1. 实验问题

R22 修正了 RR 过滤口径后，R23/R24 显示：

```text
1m A4_no_rb 在 min_price_raw_rr=0.6~0.8 下出现正期望候选，
其中 0.8 的 payoff / expectancy_R / worst_R 最好。
```

但此前“1m 是否优于 5m”的判断来自旧 RR 口径，已经不能直接沿用。

本轮重新测试：

```text
在修正后的 actual RR 口径下，
使用当前候选条件，
1m 是否已经优于 5m？
```

## 2. 实验设置

固定策略：

```text
strategy = value_area_reacceptance
profile_mode = close
value_area_ratio = 0.7
min_breakout_ticks = 4
failure_buffer_ticks = 1
take_profit_mode = poc
stop_widen_multiplier = 1.5
strict_close_exit = true
max_trades_per_day = 1
min_reaccept_ticks = 2 / 3
min_reaccept_va_width_ratio = 0
min_target_ticks = 8
target_distance_ratio = 0.8
target_band_ticks = 0
symbols = DCE.m2601 / CZCE.SR601
```

说明：

```text
no_rb 是当前 1m 候选前提；
SHFE.rb2601 在前序实验中表现为主要负贡献，暂不混入 1m vs 5m 对照。
```

周期设置：

| period | backtest.interval | strategy.kline_period | max_hold_bars |
| --- | --- | --- | ---: |
| 1m | 1m | 1m | 60 |
| 5m | 5m | 5m | 12 |

RR 扫描：

```text
min_price_raw_rr = 0.6 / 0.7 / 0.8
```

有效回测 ID：

```text
642~665
```

## 3. 总体结果：period × RR

| period | rr | n | win_pct | breakeven_win_pct | win_edge_pct | payoff | expectancy_R | net_pnl | median_pnl | worst_R | loss_ge_0.5R | loss_ge_0.8R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1m | 0.6 | 11 | 63.6% | 42.2% | 21.4% | 1.368 | 0.184 | 4052 | 320 | -0.540 | 1 | 0 |
| 1m | 0.7 | 10 | 60.0% | 37.9% | 22.1% | 1.635 | 0.197 | 3932 | 370 | -0.540 | 1 | 0 |
| 1m | 0.8 | 7 | 71.4% | 25.3% | 46.1% | 2.951 | 0.340 | 4758 | 520 | -0.240 | 0 | 0 |
| 5m | 0.6 | 11 | 36.4% | 24.9% | 11.5% | 3.022 | 0.100 | 2204 | -266 | -0.290 | 0 | 0 |
| 5m | 0.7 | 9 | 33.3% | 21.4% | 12.0% | 3.682 | 0.108 | 1938 | -266 | -0.240 | 0 | 0 |
| 5m | 0.8 | 9 | 33.3% | 21.4% | 12.0% | 3.682 | 0.108 | 1938 | -266 | -0.240 | 0 | 0 |

## 4. 聚合对照

把 0.6 / 0.7 / 0.8 三档合并观察：

| period | n | win_pct | breakeven_win_pct | win_edge_pct | payoff | expectancy_R | net_pnl | median_pnl | worst_R | loss_ge_0.5R | loss_ge_0.8R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1m | 28 | 64.3% | 37.5% | 26.8% | 1.669 | 0.228 | 12742 | 420 | -0.540 | 2 | 0 |
| 5m | 29 | 34.5% | 22.7% | 11.8% | 3.412 | 0.105 | 6080 | -266 | -0.290 | 0 | 0 |

观察：

```text
1m 的 win_pct、win_edge_pct、expectancy_R、net_pnl、median_pnl 均优于 5m；
5m 的 payoff 更高、worst_R 更收敛，但胜率过低，中位数为负；
在当前候选条件下，1m 的概率期望更强。
```

## 5. 分品种结果

| period | rr | symbol | n | win_pct | breakeven_win_pct | win_edge_pct | payoff | expectancy_R | net_pnl | median_pnl | worst_R | loss_ge_0.5R | loss_ge_0.8R |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1m | 0.6 | CZCE.SR601 | 8 | 62.5% | 55.2% | 7.3% | 0.811 | 0.058 | 930 | 270 | -0.540 | 1 | 0 |
| 1m | 0.6 | DCE.m2601 | 3 | 66.7% | 13.6% | 53.1% | 6.368 | 0.520 | 3122 | 1414 | -0.133 | 0 | 0 |
| 1m | 0.7 | CZCE.SR601 | 7 | 57.1% | 50.0% | 7.1% | 0.999 | 0.058 | 810 | 220 | -0.540 | 1 | 0 |
| 1m | 0.7 | DCE.m2601 | 3 | 66.7% | 13.6% | 53.1% | 6.368 | 0.520 | 3122 | 1414 | -0.133 | 0 | 0 |
| 1m | 0.8 | CZCE.SR601 | 4 | 75.0% | 40.5% | 34.5% | 1.469 | 0.204 | 1636 | 370 | -0.240 | 0 | 0 |
| 1m | 0.8 | DCE.m2601 | 3 | 66.7% | 13.6% | 53.1% | 6.368 | 0.520 | 3122 | 1414 | -0.133 | 0 | 0 |
| 5m | 0.6 | CZCE.SR601 | 3 | 0.0% | 100.0% | -100.0% | 0.000 | -0.281 | -1688 | -580 | -0.290 | 0 | 0 |
| 5m | 0.6 | DCE.m2601 | 8 | 50.0% | 20.4% | 29.6% | 3.896 | 0.243 | 3892 | 364 | -0.203 | 0 | 0 |
| 5m | 0.7 | CZCE.SR601 | 2 | 0.0% | 100.0% | -100.0% | 0.000 | -0.240 | -960 | -480 | -0.240 | 0 | 0 |
| 5m | 0.7 | DCE.m2601 | 7 | 42.9% | 19.2% | 23.7% | 4.208 | 0.207 | 2898 | -266 | -0.203 | 0 | 0 |
| 5m | 0.8 | CZCE.SR601 | 2 | 0.0% | 100.0% | -100.0% | 0.000 | -0.240 | -960 | -480 | -0.240 | 0 | 0 |
| 5m | 0.8 | DCE.m2601 | 7 | 42.9% | 19.2% | 23.7% | 4.208 | 0.207 | 2898 | -266 | -0.203 | 0 | 0 |

分品种观察：

```text
DCE.m：1m 与 5m 都为正，但 1m 的 expectancy_R 更高；
SR：1m 在 0.6~0.8 下均为正，5m 在三档下均为负；
因此 R25 中 1m 优于 5m 的关键差异来自 SR。
```

## 6. 结论

在当前候选条件下：

```text
1m 已经优于 5m。
```

但这个结论有明确边界：

```text
1. 使用的是 R22 后 actual RR 口径；
2. 使用 near-POC A4，即 target_distance_ratio=0.8；
3. 排除了 SHFE.rb2601；
4. 只比较 DCE.m2601 / CZCE.SR601；
5. 样本仍然很小。
```

更准确表达：

```text
在 m/SR、A4 near-POC、actual RR=0.6~0.8 的候选条件下，
1m 的正期望强于 5m；
其中 rr=0.8 的 1m 综合表现最好。
```

当前主候选仍是：

```text
period = 1m
symbols = DCE.m2601 / CZCE.SR601
target_distance_ratio = 0.8
min_price_raw_rr = 0.8
```

## 7. 下一步

不要再在同一小样本上继续调参。下一步应扩样验证当前候选：

```text
1. 固定 1m A4_no_rb + actual RR=0.8；
2. 扩大时间样本或合约样本；
3. 检查 win_pct 是否仍高于 breakeven_win_pct；
4. 检查 realized payoff 是否仍 > 1.5；
5. 检查 SR 是否仍为正；
6. 检查 worst_R / loss_ge_0.5R 是否仍收敛。
```
