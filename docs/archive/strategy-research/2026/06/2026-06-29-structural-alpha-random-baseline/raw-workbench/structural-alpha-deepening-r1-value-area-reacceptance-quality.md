# structural-alpha-deepening-r1-value-area-reacceptance-quality

> 类型：Workbench / 结构入口深耕实验  
> 状态：第一轮完成，出现强改善线索  
> 日期：2026-06-28  
> 前序随机对照：[随机对照阶段总表](./structural-alpha-random-baseline-summary.md)  
> 原始价值区对照：[价值区多 seed 随机对照](./structural-alpha-random-baseline-r2-value-area-multiseed.md)

## 1. 本轮问题

前序随机对照显示：

```text
价值区 VAH / VAL 重新接受方向明显优于随机方向；
但原始入场 / strict failure 风险空间没有显著优于同事件同方向随机。
```

因此本轮不再验证方向是否存在，而是尝试回答：

```text
在同一个价值区方向假设下，
更严格的重新接受质量是否能改善风险空间，
并显著优于同事件同方向随机？
```

## 2. 实验设计

固定基础参数：

```text
symbol = DCE.m2601
kline_period = 5m
profile_mode = close
value_area_ratio = 0.7
min_breakout_ticks = 4
failure_buffer_ticks = 1
take_profit_mode = poc
max_hold_bars = 12
stop_widen_multiplier = 1.5
strict_close_exit = true
max_trades_per_day = 1
min_target_ticks = 8
min_price_raw_rr = 0.5
```

随机对照：

```text
same-direction random：同事件同方向随机风险空间
random-direction random：同事件随机方向
random_seeds = 30
workers = 4
```

本轮只做 4 个简单变体，不做参数搜索：

| 变体 | 参数 | 含义 |
|------|------|------|
| `baseline` | 无 | r2 原始口径 |
| `quick_reaccept` | `max_breakout_bars = 1` | 只保留边界外停留不超过 1 根 K 的快速重新接受 |
| `deep_reaccept` | `min_reaccept_ticks = 2` | 重新接受必须至少收回边界内 2 ticks |
| `quick_deep_reaccept` | `max_breakout_bars = 1`, `min_reaccept_ticks = 2` | 快速 + 深度重新接受 |

输出文件：

```text
project_data/research/random_baseline/value_area_deepening_r1_20260628_233957.csv
project_data/research/random_baseline/value_area_deepening_r1_20260628_233957.json
```

## 3. 结果总表

| 变体 | 原结构收益 | 原结构胜率 | 交易数 | vs 同方向随机收益分位 | vs 同方向随机胜率优势 | vs 随机方向收益分位 | vs 随机方向胜率优势 | 判断 |
|------|-----------:|-----------:|-------:|----------------------:|----------------------:|--------------------:|--------------------:|------|
| `baseline` | `+1.15%` | `44.44%` | `20` | `66.67%` | `+2.02pp` | `100%` | `+9.57pp` | 方向强，风险空间一般 |
| `quick_reaccept` | `-2.22%` | `25.00%` | `10` | `16.67%` | `0.00pp` | `36.67%` | `-1.61pp` | 快速条件恶化 |
| `deep_reaccept` | `+3.52%` | `60.00%` | `12` | `100%` | `+12.98pp` | `100%` | `+26.80pp` | 强改善 |
| `quick_deep_reaccept` | `+0.61%` | `50.00%` | `6` | `53.33%` | `0.00pp` | `96.67%` | `+18.22pp` | 交易过少，风险空间不优 |

## 4. 关键发现

### 4.1 `deep_reaccept` 明显优于原始口径

`deep_reaccept` 结果：

| 指标 | 数值 |
|------|------:|
| total_return | `+3.5231%` |
| total_net_pnl | `+3,523.14` |
| max_drawdown | `-512.59` |
| win_rate | `60.00%` |
| win_trades / loss_trades | `3 / 2` |
| total_trades | `12` |
| avg_win | `1,733.33` |
| avg_loss | `280.00` |
| win_loss_ratio | `6.1905` |
| total_commission | `396.86` |
| total_slippage | `720.00` |

相对同方向随机：

```text
same-direction random net_pnl_mean = +1,796.04
same-direction random net_pnl_median = +1,917.00
structure_net_pnl_percentile = 100%
structure_win_rate_edge_mean = +12.98pp
```

这和 r2 的结论不同。r2 中原始口径无法证明风险空间优于同方向随机；但本轮 `deep_reaccept` 说明：

```text
要求重新接受至少收回边界内 2 ticks，
可能显著改善入场 / strict failure 风险空间质量。
```

### 4.2 “快速重新接受”不是好条件

`quick_reaccept` 结果：

```text
total_return = -2.22%
win_rate = 25.00%
同方向随机收益分位 = 16.67%
```

说明：

```text
边界外停留越短不一定越好；
快速收回可能只是噪声抽动，未必代表更高质量接受。
```

### 4.3 “快速 + 深度”样本过少且不优于同方向随机

`quick_deep_reaccept` 虽然相对随机方向仍明显更好，但同方向随机收益分位只有 `53.33%`，交易数仅 `6`。

说明：

```text
过度收紧条件会让样本过少；
并且风险空间没有比同方向随机更好。
```

### 4.4 当前最有价值变量是“重新接受深度”，不是“重新接受速度”

本轮最清晰的结构线索：

```text
min_reaccept_ticks = 2
```

它可能代表：

```text
价格不是刚刚贴边回到价值区内，
而是被市场重新接受到边界内侧一段距离，
从而减少边界附近噪声和快速再击穿。
```

这直接对应此前 roadmap 中的“接受 / 拒绝质量”概念。

## 5. 阶段结论

本轮对前序判断形成修正：

```text
价值区方向层有效；
原始风险空间未通过；
但加入重新接受深度后，风险空间出现显著改善。
```

这说明结构入口确实值得深耕，不应因原始 strict failure 未通过就放弃。

当前最值得保留的下一轮候选：

```text
value_area_reacceptance
+ min_reaccept_ticks = 2
+ min_target_ticks = 8
+ min_price_raw_rr = 0.5
```

## 6. 口径风险

与 r2 一样，`random-direction` 仍出现少量：

```text
平仓有余量未配对
```

因此 `random-direction` 结果继续只作为方向信息参考。

但本轮关键改善来自 `same-direction random`：

```text
deep_reaccept vs same-direction random = 100% 收益分位
```

该结论不依赖随机方向基准，因此比 r2 的方向结论更有价值。

## 7. 下一轮建议

下一轮不要扩大太多方向，只围绕 `deep_reaccept` 做稳健性检查：

```text
1. seeds 从 30 扩到 100；
2. min_reaccept_ticks 做 1 / 2 / 3 邻域；
3. 检查 DCE.m2601 外的 CZCE.SR601；
4. 输出 MAE / MFE、strict failure 快速再触及率；
5. 检查账户风险预算和亏损簇。
```

如果 `min_reaccept_ticks = 2` 在多 seed、多品种、邻域参数中仍显著优于同方向随机，则价值区结构可以进入下一阶段风险预算补证。
