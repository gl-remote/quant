# structural-alpha-deepening-r3-value-area-mechanism-diagnostics

> 类型：Workbench / 结构入口深耕实验  
> 状态：第三轮完成，重新接受深度改善机制获得初步解释  
> 日期：2026-06-28  
> 前序：[价值区重新接受深度稳健性 r2](./structural-alpha-deepening-r2-value-area-reacceptance-depth-robustness.md)

## 1. 本轮问题

r2 已经确认：

```text
value_area_reacceptance
+ POC 空间
+ price_raw_rr 预筛
+ min_reaccept_ticks = 2~3
```

在 `DCE.m2601` 和 `CZCE.SR601` 上相对同方向随机风险空间显著改善。

本轮不继续加过滤，也不继续跑随机方向，而是验证：

```text
“多等 2~3 ticks 的重新接受”到底改善了什么？
```

重点观察：

```text
MAE / MFE
strict failure / stop_loss 快速触发
最大单笔亏损
连续亏损和亏损簇
成本 / 平均盈利
exit reason 分布
```

## 2. 实验设计

固定基础参数同 r2：

```text
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

变量：

```text
symbol ∈ [DCE.m2601, CZCE.SR601]
min_reaccept_ticks ∈ [1, 2, 3]
```

输出文件：

```text
project_data/research/random_baseline/value_area_deepening_r3_trades_20260628_235610.csv
project_data/research/random_baseline/value_area_deepening_r3_summary_20260628_235610.json
```

说明：

```text
total_trades 为 vn.py 原始成交数，通常包含开仓和平仓；
closed_trades 为本轮诊断配对后的平仓交易数。
```

### 2.1 关于 tick 敏感性的记录

本轮使用的是 `5m` K 线，不是逐笔 tick 或盘口数据。

因此：

```text
min_reaccept_ticks = 2~3
```

含义是：

```text
5 分钟 K 线收盘价重新收回 VAH / VAL 内侧至少 2~3 个最小变动价位。
```

这不是盘中瞬时回到边界内侧 2~3 ticks，而是 5m 收盘确认后的重新接受深度。

当前结果显示 tick 深度非常敏感，因此不能把 `2 ticks` 或 `3 ticks` 直接理解成稳定的最终参数。更稳妥的解释是：

```text
重新接受必须有最小确认深度；
刚刚贴边收回的 1 tick 接受质量不足；
2~3 ticks 在当前品种和 5m 周期下是有效候选区间。
```

后续需要检查更鲁棒的波动归一表达，例如：

```text
reaccept_depth >= x * ATR
reaccept_depth >= y% * previous_value_area_width
reaccept_close_position 位于价值区内侧某个分位
```

避免研究过度依赖具体 tick 参数。

## 3. DCE.m2601 结果

| min_reaccept_ticks | 收益 | 胜率 | 平仓数 | 平均 MAE | 平均 MFE | 最大单亏 | 最大连亏 | 最差亏损簇 | 成本/平均盈利 | TP | strict failure | time exit | 判断 |
|-------------------:|-----:|-----:|-------:|---------:|---------:|---------:|---------:|-----------:|--------------:|---:|---------------:|----------:|------|
| `1` | `+1.15%` | `44.44%` | `10` | `5.30 ticks` | `7.90 ticks` | `-1430` | `2` | `-1430` | `1.26` | `3` | `1` | `5` | 原始边界仍有大亏和成本压力 |
| `2` | `+3.52%` | `60.00%` | `6` | `4.00 ticks` | `9.83 ticks` | `-420` | `1` | `-420` | `0.64` | `2` | `0` | `3` | 明显改善 |
| `3` | `+2.40%` | `50.00%` | `5` | `4.60 ticks` | `8.80 ticks` | `-420` | `1` | `-420` | `0.49` | `2` | `0` | `3` | 仍有效，机会更少 |

### 3.1 DCE 机制解释

`min_reaccept_ticks = 2` 相比 `1 tick` 的改善不是只来自胜率：

```text
平均 MAE: 5.30 → 4.00 ticks
平均 MFE: 7.90 → 9.83 ticks
最大单亏: -1430 → -420
最大连亏: 2 → 1
最差亏损簇: -1430 → -420
成本/平均盈利: 1.26 → 0.64
strict failure: 1 → 0
```

这说明更深重新接受同时改善了两件事：

```text
1. 入场后的不利波动变小；
2. 入场后的有利波动变大。
```

因此 DCE 上 `2 ticks` 不是简单少交易，而是明显改善了边界接受质量和风险空间。

`3 ticks` 仍保持较浅回撤和较低单亏，但交易数更少，胜率低于 `2 ticks`，所以暂不把 `3` 替代为唯一主参数。

## 4. CZCE.SR601 结果

| min_reaccept_ticks | 收益 | 胜率 | 平仓数 | 平均 MAE | 平均 MFE | 最大单亏 | 最大连亏 | 最差亏损簇 | 成本/平均盈利 | TP | strict failure | time exit | 判断 |
|-------------------:|-----:|-----:|-------:|---------:|---------:|---------:|---------:|-----------:|--------------:|---:|---------------:|----------:|------|
| `1` | `+0.73%` | `54.55%` | `11` | `5.36 ticks` | `6.91 ticks` | `-560` | `2` | `-760` | `2.89` | `3` | `0` | `6` | 有方向，但成本压力大 |
| `2` | `+0.21%` | `55.56%` | `9` | `6.56 ticks` | `6.00 ticks` | `-560` | `2` | `-860` | `2.56` | `2` | `0` | `5` | 胜率高但风险空间未改善 |
| `3` | `+0.88%` | `50.00%` | `6` | `6.17 ticks` | `6.50 ticks` | `-300` | `1` | `-300` | `1.24` | `1` | `0` | `4` | 尾部改善最明显 |

### 4.1 SR 机制解释

SR 与 DCE 不同。

`2 ticks` 虽然在 r2 中相对同方向随机胜率优势最强，但本轮机制诊断显示：

```text
平均 MAE 没有下降；
平均 MFE 没有提高；
最大单亏没有下降；
最差亏损簇反而更深；
成本/平均盈利仍偏高。
```

因此 SR 上 `2 ticks` 的优势更像是方向胜率优势，而不是风险空间质量全面改善。

`3 ticks` 的收益、回撤和尾部更好：

```text
最大单亏: -560 → -300
最大连亏: 2 → 1
最差亏损簇: -760 → -300
成本/平均盈利: 2.89 → 1.24
```

但 `3 ticks` 平仓数只有 `6`，样本偏少，不能直接作为最终参数。

## 5. 快速失败率

本轮 `strict_failure_close / stop_loss` 在入场后 1 / 2 / 3 根 K 内快速触发率均为 `0`。

这说明当前参数组合下，主要问题不是：

```text
入场后立刻被 strict failure 打掉。
```

更主要的问题是：

```text
time_exit 占比较高；
部分交易无法充分到达 POC；
成本相对平均盈利仍偏高；
少数亏损簇会吞噬多笔小盈利。
```

所以后续不应只围绕“更快止损”深挖，而应同时关注：

```text
MFE 是否足以覆盖 POC 目标；
time_exit 是否拖累；
是否需要更主动的目标兑现或时间退出改造。
```

## 6. 横向结论

### 6.1 DCE 与 SR 的最优机制不同

DCE：

```text
2 ticks 同时改善 MAE、MFE、单亏、亏损簇和成本占比。
```

SR：

```text
2 ticks 改善胜率，但风险空间改善不足；
3 ticks 对尾部风险和成本占比更友好。
```

这支持 r2 的判断：

```text
重新接受深度是有效变量，
但不同品种的最优深度和改善机制可能不同。
```

### 6.2 改善不是单纯“少做几笔”

DCE 上可以明确排除“只靠少做交易”：

```text
交易减少的同时，MAE 降低、MFE 提高、最大单亏和亏损簇显著下降。
```

SR 上不能完全排除样本减少影响，尤其 `3 ticks` 只有 6 笔平仓，但尾部改善方向值得继续观察。

### 6.3 当前最大短板转向 time_exit 和成本占比

两个品种的 exit reason 都显示：

```text
time_exit 是主要退出来源。
```

这意味着当前结构的方向和边界接受质量已有改善，但 POC 兑现仍不充分。后续应检查：

```text
1. POC 目标是否过远；
2. 是否需要在 MFE 达到部分目标后主动止盈；
3. time_exit 的盈亏分布是否拖累；
4. 是否应按品种设置不同持仓窗口或目标兑现方式。
```

## 7. 阶段结论

本轮把 r2 的“重新接受深度有效”推进到机制层：

```text
DCE.m2601 上，min_reaccept_ticks = 2 明确改善接受质量、MAE/MFE、单笔亏损、亏损簇和成本占比；
CZCE.SR601 上，min_reaccept_ticks = 3 更有利于尾部风险控制，2 ticks 更偏胜率优势；
快速 strict failure 不是当前主要问题，time_exit 和成本/平均盈利是下一层瓶颈。
```

因此当前主线继续保留：

```text
value_area_reacceptance
+ POC 空间
+ price_raw_rr 预筛
+ min_reaccept_ticks 2~3
```

但下一轮不建议继续加方向过滤，优先研究：

```text
time_exit 盈亏分布
POC 目标是否过远
主动止盈 / 分段目标是否能把 MFE 转化为收益
```

## 8. 下一轮建议

下一轮建议验证：

```text
在 min_reaccept_ticks = 2~3 下，
time_exit 交易到底是小亏、小赚，还是错过 POC 后回吐？
```

具体输出：

```text
time_exit 平均 pnl
time_exit 前最大 MFE
time_exit 是否曾接近 POC
take_profit 与 time_exit 的 MAE/MFE 对比
不同 max_hold_bars 下的 time_exit 占比和收益变化
```

如果发现大量 time_exit 曾有足够 MFE 但未兑现，则下一步可研究主动止盈；如果 time_exit 本身 MFE 不足，则说明 POC 目标过远或场景质量仍不足。
