# value_area_reacceptance：1m 微观路径与实际 RR 口径重整记录

> 类型：Workbench / 当日实验重整记录
> 状态：已归档
> 日期：2026-07-01
> 当前主题：[value-area-reacceptance/README.md](../../../research/themes/value-area-reacceptance/README.md)
> 所属归档：[value_area_reacceptance POC / VA 质量诊断阶段归档](../value-area-reacceptance-quality-summary.md)

## 1. 为什么重整

今天早期记录先按旧 RR 口径推进了 1m 周期、near-POC、MFE trailing、过滤器等实验，随后发现并修正了一个关键统计 / 入场过滤口径问题。

旧口径：

```text
min_price_raw_rr = raw POC target distance / strict_failure distance
```

但固定风险预算实际使用：

```text
stop_distance = strict_failure distance × stop_widen_multiplier
```

R17 之后的 near-POC 实验还会改变实际执行止盈目标，因此旧口径没有把：

```text
实际执行 target distance
实际预算 stop distance
```

放在同一个风险口径下比较。

R22 后修正为：

```text
min_price_raw_rr = execution target distance / actual stop distance
```

因此，旧记录中的净收益、胜率、过滤效果等交易结论不能直接作为最终判断。本文按修正后的 actual RR 口径重整今天实验，只保留仍然可靠的结构性观察，并重新梳理有效交易结论。

## 2. 仍然有效的结构性观察

虽然旧 RR 口径影响交易结论，但以下结构性观察仍有参考价值：

```text
1. 1m 交易机会比 5m 更多；
2. 1m 胜率和中位数曾明显优于 5m；
3. 1m 与 5m 的 entry → POC tick 尺度接近，中位数约十几 ticks；
4. 1m 暴露出更多接近 POC 但未精确触达 POC 的路径；
5. POC 单点目标偏刚性，near-POC / 80% target 有研究价值；
6. SHFE.rb2601 在 1m 下明显拖累结果；
7. 简单 MFE trailing 和简单 KDJ 阈值过滤没有表现出优先价值。
```

这些结论描述的是路径形态和样本结构，不依赖旧 RR 过滤是否完全正确。

## 3. R22：RR 口径修正事件

### 3.1 修正内容

策略中保留：

```text
strict_failure = 结构失败边界；
stop_price = 实际硬止损 / 固定风险预算边界。
```

但修正 RR 过滤，使其与固定风险预算一致：

```text
actual_stop_distance = abs(stop_price - entry)
execution_target_distance = abs(execution_target - entry)
actual_rr = execution_target_distance / actual_stop_distance
```

过滤条件变为：

```text
actual_rr >= min_price_raw_rr
```

这使 `min_price_raw_rr` 从“raw POC 相对结构失败边界”变成“实际执行目标相对实际预算止损”的最低要求。

### 3.2 最小复核

R22 没有完整重跑所有旧实验，只做最小复核。

有效回测 ID：

```text
590~605
```

关键对照：

| group | n | win_pct | net_pnl | median_pnl | worst_R | loss_ge_0.8R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| OLD_1m_A4_all | 56 | 51.8% | -3702 | 90 | -0.836 | 1 |
| R22_1m_A4_all | 35 | 45.7% | -4646 | -266 | -0.836 | 1 |
| OLD_1m_A4_no_rb | 31 | 61.3% | +2248 | 132 | -0.690 | 0 |
| R22_1m_A4_no_rb | 15 | 53.3% | +1772 | 198 | -0.590 | 0 |
| OLD_5m_poc_all | 41 | 43.9% | +1890 | -171.6 | -0.811 | 1 |
| R22_5m_poc_all | 33 | 33.3% | -1748 | -266 | -0.834 | 1 |

### 3.3 R22 影响

R22 后需要降级的旧结论：

```text
1. “5m 当前正收益主线”不能再直接沿用旧结果；
2. “1m 不适合作为直接交易周期”不能只基于旧 RR 净收益判断；
3. “A4_no_rb 为正”仍成立，但样本从 31 降到 15，需要重新校准 RR 参数。
```

关键解释：

```text
修正后，同样的 min_price_raw_rr=0.5 变得更严格；
旧口径的 0.5 不是实际 0.5R；
新口径的 0.5 才是 execution target / actual stop >= 0.5。
```

因此，R22 不是证明策略失效，而是说明需要在新口径下重新校准 `min_price_raw_rr`。

## 4. R23：actual RR 参数重新校准

### 4.1 实验问题

R23 原始问题是：

```text
R22 后新口径 min_price_raw_rr=0.5 比旧口径更严格，
降低到 0.2~0.4 是否能恢复旧口径的交易数和期望？
```

固定候选：

```text
1m A4_no_rb；
target_distance_ratio = 0.8；
symbols = DCE.m2601 / CZCE.SR601；
min_reaccept_ticks = 2 / 3。
```

扫描：

```text
min_price_raw_rr = 0.2 / 0.3 / 0.4 / 0.5 / 0.6
```

有效回测 ID：

```text
606~625
```

### 4.2 总体结果

| min_price_raw_rr | n | win_pct | breakeven_win_pct | win_edge_pct | payoff | expectancy_R | net_pnl | worst_R |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.2 | 31 | 61.3% | 55.6% | +5.7% | 0.800 | 0.036 | +2248 | -0.690 |
| 0.3 | 30 | 63.3% | 57.5% | +5.8% | 0.738 | 0.038 | +2304 | -0.690 |
| 0.4 | 21 | 57.1% | 55.5% | +1.6% | 0.801 | 0.012 | +514 | -0.690 |
| 0.5 | 15 | 53.3% | 46.2% | +7.1% | 1.163 | 0.059 | +1772 | -0.590 |
| 0.6 | 11 | 63.6% | 42.2% | +21.4% | 1.368 | 0.184 | +4052 | -0.540 |

### 4.3 R23 结论

R23 与原始假设不完全一致。

```text
降低 RR 到 0.2~0.4 可以恢复交易数，
但 payoff 仍低于 1 或接近 0.8，
胜率优势很薄，长期期望偏弱。
```

更高的 0.5 / 0.6 虽然交易数减少，但：

```text
payoff 改善；
breakeven_win_pct 下降；
win_edge_pct 扩大；
expectancy_R 改善。
```

因此，actual RR 口径下，不应继续沿着“降低 RR 恢复交易数”的方向推进。

## 5. R24：高 actual RR 阈值扩展

### 5.1 实验问题

R23 发现 `min_price_raw_rr=0.6` 比更低 RR 档更有吸引力，因此 R24 继续测试 0.7 及以上。

固定同 R23：

```text
1m A4_no_rb；
target_distance_ratio = 0.8；
symbols = DCE.m2601 / CZCE.SR601；
min_reaccept_ticks = 2 / 3。
```

扫描：

```text
min_price_raw_rr = 0.7 / 0.8 / 0.9 / 1.0
```

有效回测 ID：

```text
626~641
```

### 5.2 总体结果

| min_price_raw_rr | n | win_pct | breakeven_win_pct | win_edge_pct | payoff | expectancy_R | net_pnl | avg_pnl | median_pnl | worst_R | loss_ge_0.5R | loss_ge_0.8R |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.7 | 10 | 60.0% | 37.9% | +22.1% | 1.635 | 0.197 | +3932 | 393.200 | 370 | -0.540 | 1 | 0 |
| 0.8 | 7 | 71.4% | 25.3% | +46.1% | 2.951 | 0.340 | +4758 | 679.714 | 520 | -0.240 | 0 | 0 |
| 0.9 | 5 | 80.0% | 20.1% | +59.9% | 3.974 | 0.396 | +3962 | 792.400 | 520 | -0.133 | 0 | 0 |
| 1.0 | 4 | 75.0% | 17.0% | +58.0% | 4.897 | 0.455 | +3642 | 910.500 | 967 | -0.133 | 0 | 0 |

### 5.3 设计 RR 与实际 payoff

`min_price_raw_rr` 是入场前最低 actual RR 门槛，不是回测后实际盈亏比。回测后的实际盈亏比用：

```text
payoff = avg_win / abs(avg_loss)
```

当前样本中，实际 payoff 普遍高于设计 RR 下限：

| min_price_raw_rr | n | design_rr | realized_payoff | win_pct | breakeven_win_pct | expectancy_R |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.2 | 31 | 0.2 | 0.800 | 61.3% | 55.6% | 0.036 |
| 0.3 | 30 | 0.3 | 0.738 | 63.3% | 57.5% | 0.038 |
| 0.4 | 21 | 0.4 | 0.801 | 57.1% | 55.5% | 0.012 |
| 0.5 | 15 | 0.5 | 1.163 | 53.3% | 46.2% | 0.059 |
| 0.6 | 11 | 0.6 | 1.368 | 63.6% | 42.2% | 0.184 |
| 0.7 | 10 | 0.7 | 1.635 | 60.0% | 37.9% | 0.197 |
| 0.8 | 7 | 0.8 | 2.951 | 71.4% | 25.3% | 0.340 |
| 0.9 | 5 | 0.9 | 3.974 | 80.0% | 20.1% | 0.396 |
| 1.0 | 4 | 1.0 | 4.897 | 75.0% | 17.0% | 0.455 |

判断正期望的核心关系：

```text
win_pct > breakeven_win_pct
```

当前所有 RR 档位在样本内都满足正期望，但强度不同：

```text
0.2~0.4：弱正期望，payoff 不足；
0.5~0.7：期望改善，但仍有一定亏损尾部；
0.8：样本仍有 7 笔，payoff / win_edge / worst_R 综合最好；
0.9~1.0：指标更漂亮，但样本过少。
```

### 5.4 分品种观察

R24 中 `min_price_raw_rr=0.8`：

| symbol | n | win_pct | breakeven_win_pct | payoff | expectancy_R | net_pnl | worst_R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DCE.m2601 | 3 | 66.7% | 13.6% | 6.368 | 0.520 | +3122 | -0.133 |
| CZCE.SR601 | 4 | 75.0% | 40.5% | 1.469 | 0.205 | +1636 | -0.240 |

含义：

```text
0.8 不是完全靠 DCE.m 单独撑起来；
SR 仍保留 4 笔且为正；
但样本仍然很小，必须扩样验证。
```

## 6. 当前阶段结论

### 6.1 关于 1m

不能再沿用早期表述：

```text
1m 不适合作为直接交易周期。
```

更准确应改为：

```text
在旧 RR 口径和固定 0.5 参数下，1m 直接交易表现不稳定；
修正 actual RR 口径后，1m A4_no_rb 在较高 RR 门槛下出现正期望候选；
但样本很小，尚不能升格为可交易主线。
```

### 6.2 关于 near-POC

near-POC / 80% target 的价值仍然成立：

```text
它解决的是 POC 单点过刚性的问题；
但它必须和 actual RR 过滤一起看；
低 RR 的 near-POC 容易产生小赢大亏结构。
```

### 6.3 关于 rb

当前 1m 直接交易候选暂时排除 rb：

```text
rb 在 1m 下贡献主要负收益；
剔除 rb 后，m / SR 的 1m A4 才出现可研究的正期望结构；
这不是永久禁止 rb，而是 rb 需要单独诊断。
```

### 6.4 关于 RR 最适区间

仅从当前正期望与实际盈亏比 / RR 分析看：

```text
主候选：min_price_raw_rr = 0.8；
保守候选：min_price_raw_rr = 0.7；
宽松候选：min_price_raw_rr = 0.6；
暂不采用：0.9 / 1.0，因为样本过少。
```

如果只能选一个扩样候选：

```text
min_price_raw_rr = 0.8
```

理由：

```text
n=7；
payoff=2.951；
win_pct=71.4%；
breakeven_win_pct=25.3%；
expectancy_R=0.340；
worst_R=-0.240；
loss_ge_0.5R=0；
DCE.m 与 SR 均为正。
```

## 7. 不再优先推进的方向

基于今天实验，以下方向暂缓：

```text
1. 简单 MFE trailing：会切断可恢复路径，未改善核心失败；
2. 简单 KDJ 阈值过滤：误伤 DCE.m，高质量样本减少；
3. 继续降低 RR 门槛：只能恢复交易数，不能明显改善 payoff；
4. 继续提高到 0.9 / 1.0：样本过少，统计意义不足；
5. 直接迁移 5m edge_or_away 到 1m：语义不稳定。
```

## 8. 下一步建议

下一步不应继续在同一小样本上调参，而应扩样验证：

```text
候选策略：1m A4_no_rb；
候选 RR：0.6 / 0.7 / 0.8，重点 0.8；
观察指标：n、win_pct、breakeven_win_pct、payoff、expectancy_R、worst_R、loss_ge_0.5R、分品种稳定性。
```

扩样判断标准：

```text
1. win_pct 是否仍显著高于 breakeven_win_pct；
2. realized_payoff 是否仍 > 1.5，最好 > 2；
3. expectancy_R 是否仍为正；
4. SR 是否仍为正，而不是完全依赖 DCE.m；
5. 样本扩大后 worst_R 是否仍收敛。
```

如果扩样后 0.8 仍保持正期望，再考虑整理为正式候选策略；如果扩样后优势消失，则 1m 仍只作为结构诊断和执行层研究材料。
