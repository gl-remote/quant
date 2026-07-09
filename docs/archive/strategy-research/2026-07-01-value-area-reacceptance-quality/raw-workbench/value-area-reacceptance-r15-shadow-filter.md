# value_area_reacceptance R15：edge_or_away 候选过滤器影子评估

> 类型：Workbench / 实验报告
> 状态：已完成
> 日期：2026-07-01
> 阶段规划：[value-area-reacceptance-stage-plan.md](./value-area-reacceptance-stage-plan.md)
> 上一轮报告：[value-area-reacceptance-r14-day-dedup-combo-tags.md](./value-area-reacceptance-r14-day-dedup-combo-tags.md)

## 1. 实验问题

R14 已确认，日级去重后：

```text
edge_or_away 仍然显著负向，
not_bad 仍显著优于全样本。
```

本轮把该组合标签推进到“候选过滤器影子评估”：

```text
不改变 entry signal，
只在 diagnostics / clearing 层标记 would_filter=edge_or_away，
然后报告原始策略与影子过滤后的对照结果。
```

## 2. 实现范围

本轮在策略 entry diagnostics 中新增：

```text
alpha.would_filter_edge_or_away
alpha.would_filter_reason
```

标记逻辑：

```text
would_filter_edge_or_away = (
    poc_edge_bucket == "edge"
    or current_acceptance_migration_bucket == "away"
)

would_filter_reason = "edge_or_away" if would_filter_edge_or_away else "none"
```

注意：

```text
该字段只写 diagnostics，
不会阻止下单，
不会改变回测交易信号。
```

## 3. 回测样本

重新跑主线 6 组：

```text
DCE.m2601: 456 / 457
CZCE.SR601: 458 / 459
SHFE.rb2601: 460 / 461
```

参数沿用 R12~R14 主线：

```text
profile_mode = close
value_area_ratio = 0.7
min_breakout_ticks = 4
failure_buffer_ticks = 1
take_profit_mode = poc
max_hold_bars = 12
stop_widen_multiplier = 1.5
strict_close_exit = true
max_trades_per_day = 1
min_reaccept_ticks = 2 / 3
min_reaccept_va_width_ratio = 0
min_target_ticks = 8
min_price_raw_rr = 0.5
```

落库验证显示，`trade_clearings.diagnostics_json` 已包含：

```text
$.alpha.would_filter_edge_or_away
$.alpha.would_filter_reason
```

## 4. 原始清算口径影子对照

| bucket | n | win_pct | tp_pct | net_pnl | avg_pnl | median_pnl | worst_pnl | loss_sum | left_tail_1000 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| raw | 41 | 43.9% | 29.3% | 1890.206 | 46.103 | -171.600 | -1622.608 | -13358.154 | 4 |
| shadow_kept | 25 | 64.0% | 44.0% | 10754.990 | 430.200 | 518.096 | -1622.608 | -4200.970 | 1 |
| shadow_filtered | 16 | 12.5% | 6.2% | -8864.784 | -554.049 | -455.300 | -1550.620 | -9157.184 | 3 |

影子过滤在清算口径下非常明显：

```text
被过滤的样本贡献了主要亏损；
保留样本的胜率、tp_pct、median_pnl、net_pnl 均显著改善。
```

## 5. 日级去重口径：优先 2 ticks

| bucket | n | win_pct | tp_pct | net_pnl | avg_pnl | median_pnl | worst_pnl | loss_sum | left_tail_1000 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| raw | 23 | 43.5% | 26.1% | 416.020 | 18.088 | -194.246 | -1622.608 | -7853.356 | 2 |
| shadow_kept | 14 | 57.1% | 35.7% | 4613.664 | 329.547 | 498.300 | -1622.608 | -3363.312 | 1 |
| shadow_filtered | 9 | 22.2% | 11.1% | -4197.644 | -466.405 | -424.600 | -1550.620 | -4490.044 | 1 |

日级去重后，影子过滤仍成立：

```text
shadow_kept 明显优于 raw；
shadow_filtered 明显为负。
```

## 6. 日级去重口径：同结构平均 PnL

| bucket | n | win_pct | tp_pct | net_pnl | avg_pnl | median_pnl | worst_pnl | loss_sum | left_tail_1000 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| raw | 23 | 43.5% | 30.4% | 130.399 | 5.670 | -105.658 | -1622.608 | -7955.058 | 2 |
| shadow_kept | 14 | 64.3% | 42.9% | 4633.791 | 330.985 | 498.300 | -1622.608 | -3169.066 | 1 |
| shadow_filtered | 9 | 11.1% | 11.1% | -4503.392 | -500.377 | -424.600 | -1550.620 | -4785.992 | 1 |

同结构平均 PnL 口径下，结论依旧稳定。

## 7. 分品种清算口径

| bucket | n | win_pct | tp_pct | net_pnl | avg_pnl | median_pnl | worst_pnl | loss_sum | left_tail_1000 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| CZCE.SR601:raw | 15 | 53.3% | 20.0% | 1096.200 | 73.080 | 9.800 | -708.800 | -2817.400 | 0 |
| CZCE.SR601:shadow_kept | 7 | 85.7% | 28.6% | 2912.400 | 416.057 | 651.200 | -708.800 | -708.800 | 0 |
| CZCE.SR601:shadow_filtered | 8 | 25.0% | 12.5% | -1816.200 | -227.025 | -270.200 | -486.000 | -2108.600 | 0 |
| DCE.m2601:raw | 11 | 45.5% | 36.4% | 5909.600 | 537.236 | -218.400 | -513.600 | -2180.800 | 0 |
| DCE.m2601:shadow_kept | 9 | 55.6% | 44.4% | 6626.400 | 736.267 | 844.000 | -513.600 | -1464.000 | 0 |
| DCE.m2601:shadow_filtered | 2 | 0.0% | 0.0% | -716.800 | -358.400 | -358.400 | -358.400 | -716.800 | 0 |
| SHFE.rb2601:raw | 15 | 33.3% | 33.3% | -5115.594 | -341.040 | -194.246 | -1622.608 | -8359.954 | 4 |
| SHFE.rb2601:shadow_kept | 9 | 55.6% | 55.6% | 1216.190 | 135.132 | 455.572 | -1622.608 | -2028.170 | 1 |
| SHFE.rb2601:shadow_filtered | 6 | 0.0% | 0.0% | -6331.784 | -1055.297 | -915.160 | -1550.620 | -6331.784 | 3 |

分品种看：

- DCE.m：过滤影响温和，但方向正确；
- SR：过滤后收益和胜率显著改善；
- rb：过滤掉主要坏样本后清算口径转正，但仍保留一笔大左尾。

## 8. 分品种日级去重口径：优先 2 ticks

| bucket | n | win_pct | tp_pct | net_pnl | avg_pnl | median_pnl | worst_pnl | loss_sum | left_tail_1000 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| CZCE.SR601:raw | 9 | 55.6% | 22.2% | 213.400 | 23.711 | 9.800 | -708.800 | -1889.600 | 0 |
| CZCE.SR601:shadow_kept | 4 | 75.0% | 25.0% | 1101.800 | 275.450 | 498.300 | -708.800 | -708.800 | 0 |
| CZCE.SR601:shadow_filtered | 5 | 40.0% | 20.0% | -888.400 | -177.680 | -270.200 | -486.000 | -1180.800 | 0 |
| DCE.m2601:raw | 6 | 50.0% | 33.3% | 3516.800 | 586.133 | 312.800 | -513.600 | -1090.400 | 0 |
| DCE.m2601:shadow_kept | 5 | 60.0% | 40.0% | 3875.200 | 775.040 | 844.000 | -513.600 | -732.000 | 0 |
| DCE.m2601:shadow_filtered | 1 | 0.0% | 0.0% | -358.400 | -358.400 | -358.400 | -358.400 | -358.400 | 0 |
| SHFE.rb2601:raw | 8 | 25.0% | 25.0% | -3314.180 | -414.272 | -421.923 | -1622.608 | -4873.356 | 2 |
| SHFE.rb2601:shadow_kept | 5 | 40.0% | 40.0% | -363.336 | -72.667 | -105.658 | -1622.608 | -1922.512 | 1 |
| SHFE.rb2601:shadow_filtered | 3 | 0.0% | 0.0% | -2950.844 | -983.615 | -750.624 | -1550.620 | -2950.844 | 1 |

日级口径下，rb 的保留样本仍为负，进一步说明：

```text
edge_or_away 能过滤坏结构，
但不能单独修复 rb 的品种左尾。
```

## 9. 判断

R15 确认：

```text
edge_or_away 已经可以作为稳定的影子过滤标签。
```

它具备三个特征：

1. 从清算口径到日级去重口径都稳定；
2. 对 DCE.m、SR、rb 都能识别坏结构；
3. 被过滤样本整体为明显负收益。

但当前仍不建议直接变成真实 entry filter：

```text
样本仍小；
DCE.m 的 bad 日级结构只有 1 个；
rb 的 not_bad 仍保留左尾；
还没有跨合约、跨月份、更长窗口验证。
```

## 10. 阶段结论

R15 把 POC 质量标签从“事后诊断”推进到“运行时影子过滤评估”：

```text
策略现在会记录 would_filter_edge_or_away，
但不会因此跳过交易。
```

这使后续可以在报告层持续观察：

```text
raw strategy vs shadow_kept strategy vs shadow_filtered trades
```

下一步建议：

```text
R16：扩大样本的影子过滤复验。
```

优先不是改信号，而是增加验证范围：

```text
1. 选择更多合约或更长历史区间；
2. 继续保留 would_filter，不改变交易；
3. 看 shadow_kept 是否持续优于 raw；
4. 分品种判断 DCE.m 是否适合进入候选策略，SR / rb 是否应降级或排除。
```
