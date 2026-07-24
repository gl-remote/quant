# value_area_reacceptance R27：扩样复验

> 类型：Archive / 扩样复验记录
> 状态：已完成 / 外推样本未通过 / 转入结构诊断
> 日期：2026-07-01
> 关联当前状态：[strategy-current.md](../../../research/strategy-current.md)
> 前置归档：[value_area_reacceptance POC / VA 质量诊断阶段归档](../2026-07-01-value-area-reacceptance-quality/value-area-reacceptance-quality-summary.md)

## 1. 实验目标

本轮目标从“扩样证明当前候选可全行情稳定赚钱”修正为：

```text
1. 承认 value_area_reacceptance 大概率不适合强趋势行情；
2. 不再试图让它覆盖明显不赚钱的行情时期；
3. 重点改为识别它赚钱的行情窗口，并验证赚钱窗口内收益是否稳定、亏损是否可控；
4. 对不赚钱时期只做归因与排除条件观察，不急于通过调参强行救回。
```

当前候选先作为诊断探针继续使用，而不是作为待上线规则。

对当前候选做分批扩样复验：

```text
value_area_reacceptance
+ 1m execution
+ previous-day close-profile POC / VA
+ A4_ratio_80
+ actual RR >= 0.8
+ min_reaccept_ticks = 2 / 3
```

本轮遵守三个约束：

```text
1. 不一次性跑大批量，避免运行和报告构建时间过长；
2. 每批结束后先记录异常现象，再调整下一批计划；
3. 每批补充 trend_label 与 active_label，避免把行情状态或流动性问题误判为策略问题。
```

## 2. 固定参数

```text
strategy = value_area_reacceptance
engine = vnpy
mode = single
kline_period = 1m
profile_mode = close
value_area_ratio = 0.7
min_breakout_ticks = 4
failure_buffer_ticks = 1
take_profit_mode = poc
target_distance_ratio = 0.8
target_band_ticks = 0
max_hold_bars = 60
stop_widen_multiplier = 1.5
strict_close_exit = true
max_trades_per_day = 1
min_reaccept_va_width_ratio = 0
min_target_ticks = 8
min_price_raw_rr = 0.8
```

每个品种分别跑：

```text
min_reaccept_ticks = 2 / 3
```

## 3. R27-B1：第一批样本

### 3.1 样本与回测 ID

| backtest_id | symbol | ticks | 样本区间 | clearing_n |
| ---: | --- | ---: | --- | ---: |
| 678 | DCE.m2603 | 2 | 2025-11-03 ~ 2026-01-30 | 1 |
| 679 | DCE.m2603 | 3 | 2025-11-03 ~ 2026-01-30 | 1 |
| 680 | CZCE.SR605 | 2 | 2026-01-05 ~ 2026-05-19 | 8 |
| 681 | CZCE.SR605 | 3 | 2026-01-05 ~ 2026-05-19 | 6 |

说明：

```text
backtests.total_trades 是开/平成交条数；
本记录优先使用 trade_clearings 的完整开平配对作为交易笔数。
```

### 3.2 结果总览

| symbol | ticks | n | wins | losses | win_pct | net_pnl | avg_pnl | worst_pnl | best_pnl | avg_win | avg_loss | payoff | breakeven_win_pct |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DCE.m2603 | 2 | 1 | 0 | 1 | 0.0% | -1287 | -1287 | -1287 | -1287 | - | 1287 | - | - |
| DCE.m2603 | 3 | 1 | 0 | 1 | 0.0% | -1287 | -1287 | -1287 | -1287 | - | 1287 | - | - |
| CZCE.SR605 | 2 | 8 | 3 | 5 | 37.5% | -3178 | -397 | -1580 | 1012 | 975 | 1221 | 0.799 | 55.6% |
| CZCE.SR605 | 3 | 6 | 1 | 5 | 16.7% | -4460 | -743 | -1518 | 1012 | 1012 | 1094 | 0.925 | 51.9% |

第一批合并观察：

| symbol | n | net_pnl | avg_pnl | wins | losses |
| --- | ---: | ---: | ---: | ---: | ---: |
| CZCE.SR605 | 14 | -7638 | -546 | 4 | 10 |
| DCE.m2603 | 2 | -2574 | -1287 | 0 | 2 |

注意：ticks=2 与 ticks=3 存在重叠交易，合并表只用于观察压力，不应当当作独立样本统计。

## 4. 不符合预期现象

### 4.1 SR605 没有延续旧样本 SR 的正贡献

旧样本中 SR 在 A4_ratio_80 后从弱正期望改善为明显正期望；但第一批新增 `CZCE.SR605` 两组均转负：

```text
SR605 ticks=2: n=8, win_pct=37.5%, net_pnl=-3178, payoff=0.799
SR605 ticks=3: n=6, win_pct=16.7%, net_pnl=-4460, payoff=0.925
```

这与“SR 是 1m 优势关键贡献”的旧样本结论冲突，需要优先复核 SR 的跨月份稳定性。

### 4.2 ticks=3 没有更干净，反而更弱

旧 R26 中 ticks=3 更干净但样本少；第一批新增样本中：

```text
SR605 ticks=3 比 ticks=2 少 2 笔，但胜率更低、净亏更大；
DCE.m2603 ticks=2/3 触发同一笔亏损，没有形成区分度。
```

因此暂时不能把 ticks=3 当作更高质量确认条件。

### 4.3 strict_failure_close 是主要亏损来源

按 exit_reason 聚合：

| exit_reason | n | net_pnl | avg_pnl | wins | losses |
| --- | ---: | ---: | ---: | ---: | ---: |
| strict_failure_close | 9 | -12456 | -1384 | 0 | 9 |
| take_profit | 1 | 1012 | 1012 | 1 | 0 |
| time_exit | 6 | 1232 | 205 | 3 | 3 |

亏损不是来自 time_exit 慢性磨损，而是大量重新失败后触发 strict failure。

### 4.4 旧 edge_or_away 诊断没有直接救回第一批

第一批按 `would_filter_edge_or_away` 观察：

| symbol | ticks | edge_or_away | n | net_pnl | wins | losses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| CZCE.SR605 | 2 | 0 | 3 | -1976 | 1 | 2 |
| CZCE.SR605 | 2 | 1 | 5 | -1202 | 2 | 3 |
| CZCE.SR605 | 3 | 0 | 3 | -3536 | 0 | 3 |
| CZCE.SR605 | 3 | 1 | 3 | -924 | 1 | 2 |
| DCE.m2603 | 2 | 0 | 1 | -1287 | 0 | 1 |
| DCE.m2603 | 3 | 0 | 1 | -1287 | 0 | 1 |

这支持当前文档判断：`edge_or_away` 只能作为诊断字段，不能直接作为真实过滤器。

按 POC edge / migration 组合看，第一批最差的不是单一 `edge_or_away`：

| poc_edge | migration | n | net_pnl | wins | losses |
| --- | --- | ---: | ---: | ---: | ---: |
| central | mid | 4 | -5500 | 0 | 4 |
| mid_edge | mid | 3 | -3598 | 0 | 3 |
| edge | away | 2 | -2816 | 0 | 2 |
| mid_edge | away | 4 | -1334 | 1 | 3 |
| mid_edge | near_poc | 1 | 1012 | 1 | 0 |
| edge | mid | 2 | 2024 | 2 | 0 |

## 5. 初步判断

第一批对当前候选不利：

```text
1. 新增 SR605 显著转负，直接冲击“SR 稳定正贡献”的假设；
2. DCE.m2603 样本极少但为负，暂不能说明 DCE.m 跨月份稳定；
3. 亏损集中在 strict_failure_close，说明新样本中 reacceptance 后再次失败的比例偏高；
4. edge_or_away 不能解释或修复这批亏损。
```

但第一批仍不能直接推翻主线：

```text
1. DCE.m2603 只有 1 个独立 clearing；
2. SR605 是单一 SR 月份；
3. ticks=2/3 之间有重叠，不能简单合并成独立交易数；
4. 仍需继续小批量观察其他新增月份。
```

## 6. 下一批计划调整

原计划是直接继续扩大 m/SR。第一批出现 SR605 明显转负后，下一批调整为：

```text
1. 继续固定 R26 候选参数，不急于调参；
2. 下一批优先跑 DCE.m2605 与 CZCE.SR609；
3. 仍然只跑 ticks=2/3；
4. 重点观察：
   - SR605 是否是单月异常，还是 SR 扩样整体转弱；
   - DCE.m 新月份是否恢复正贡献；
   - strict_failure_close 是否持续集中；
   - ticks=3 是否继续劣于 ticks=2。
```

暂不做：

```text
1. 不立刻降低 RR；
2. 不立刻启用 edge_or_away 过滤；
3. 不立刻重启 target / max_hold 网格；
4. 不把 rb 混入主候选复验。
```

## 7. R27-B2：第二批样本

### 7.1 样本与回测 ID

| backtest_id | symbol | ticks | 样本区间 | clearing_n |
| ---: | --- | ---: | --- | ---: |
| 682 | DCE.m2605 | 2 | 2026-01-05 ~ 2026-04-01 | 5 |
| 683 | DCE.m2605 | 3 | 2026-01-05 ~ 2026-04-01 | 2 |
| 684 | CZCE.SR609 | 2 | 2026-05-06 ~ 2026-07-01 | 3 |
| 685 | CZCE.SR609 | 3 | 2026-05-06 ~ 2026-07-01 | 1 |

### 7.2 结果总览

| symbol | ticks | n | wins | losses | win_pct | net_pnl | avg_pnl | worst_pnl | best_pnl | avg_win | avg_loss | payoff | breakeven_win_pct |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DCE.m2605 | 2 | 5 | 2 | 3 | 40.0% | -3336 | -667 | -2235 | 505 | 260 | 1285 | 0.202 | 83.2% |
| DCE.m2605 | 3 | 2 | 0 | 2 | 0.0% | -2473 | -1237 | -2226 | -247 | - | 1237 | - | - |
| CZCE.SR609 | 2 | 3 | 1 | 2 | 33.3% | -1672 | -557 | -1518 | 154 | 154 | 913 | 0.169 | 85.5% |
| CZCE.SR609 | 3 | 1 | 0 | 1 | 0.0% | -56 | -56 | -56 | -56 | - | 56 | - | - |

第二批合并观察：

| symbol | n | net_pnl | avg_pnl | wins | losses |
| --- | ---: | ---: | ---: | ---: | ---: |
| CZCE.SR609 | 4 | -1728 | -432 | 1 | 3 |
| DCE.m2605 | 7 | -5809 | -830 | 2 | 5 |

同样注意：ticks=2 与 ticks=3 存在重叠交易，合并表只用于压力观察。

## 8. 第二批不符合预期现象

### 8.1 DCE.m2605 也没有恢复旧样本中的强贡献

旧样本中 DCE.m 是当前 1m 候选的强贡献品种；但第二批 `DCE.m2605` 两组均转负：

```text
m2605 ticks=2: n=5, win_pct=40.0%, net_pnl=-3336, payoff=0.202
m2605 ticks=3: n=2, win_pct=0.0%, net_pnl=-2473
```

这说明第一批 `m2603` 的负结果不一定只是样本太少；至少 m 的新增月份没有立即恢复旧样本强贡献。

### 8.2 SR609 交易数明显减少，但仍未转正

`SR609` 交易数少于 `SR605`，但结果仍为负：

```text
SR609 ticks=2: n=3, net_pnl=-1672
SR609 ticks=3: n=1, net_pnl=-56
```

这进一步削弱“SR 扩样继续稳定正贡献”的假设。SR605 不是单独足以解释的唯一异常点。

### 8.3 ticks=3 连续两批弱于 ticks=2

两批样本中 ticks=3 均没有表现出旧 R26 中的“更干净”：

| batch | symbol | ticks=2 net_pnl | ticks=3 net_pnl |
| --- | --- | ---: | ---: |
| B1 | CZCE.SR605 | -3178 | -4460 |
| B1 | DCE.m2603 | -1287 | -1287 |
| B2 | DCE.m2605 | -3336 | -2473 |
| B2 | CZCE.SR609 | -1672 | -56 |

虽然 SR609 ticks=3 的亏损较小，但只有 1 笔，不足以说明质量更高。整体看，ticks=3 主要是减少交易，并没有稳定改善胜率或期望。

### 8.4 亏损来源从 strict_failure 扩展到 stop_loss

第二批 exit_reason：

| exit_reason | n | net_pnl | avg_pnl | wins | losses |
| --- | ---: | ---: | ---: | ---: | ---: |
| stop_loss | 2 | -4461 | -2231 | 0 | 2 |
| strict_failure_close | 2 | -2853 | -1427 | 0 | 2 |
| force_flat | 1 | -308 | -308 | 0 | 1 |
| time_exit | 6 | 85 | 14 | 3 | 3 |

第一批主要是 strict_failure_close；第二批出现两笔更大的 stop_loss。异常不只是严格失败边界触发，也包括扩大止损后的完整止损命中。

## 9. B1+B2 阶段性汇总

按批次、品种、ticks：

| batch | symbol | ticks | n | net_pnl | wins | losses | win_pct |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| B1 | CZCE.SR605 | 2 | 8 | -3178 | 3 | 5 | 37.5% |
| B1 | CZCE.SR605 | 3 | 6 | -4460 | 1 | 5 | 16.7% |
| B1 | DCE.m2603 | 2 | 1 | -1287 | 0 | 1 | 0.0% |
| B1 | DCE.m2603 | 3 | 1 | -1287 | 0 | 1 | 0.0% |
| B2 | CZCE.SR609 | 2 | 3 | -1672 | 1 | 2 | 33.3% |
| B2 | CZCE.SR609 | 3 | 1 | -56 | 0 | 1 | 0.0% |
| B2 | DCE.m2605 | 2 | 5 | -3336 | 2 | 3 | 40.0% |
| B2 | DCE.m2605 | 3 | 2 | -2473 | 0 | 2 | 0.0% |

B1+B2 按 exit_reason：

| exit_reason | n | net_pnl | avg_pnl | wins | losses |
| --- | ---: | ---: | ---: | ---: | ---: |
| strict_failure_close | 11 | -15309 | -1392 | 0 | 11 |
| stop_loss | 2 | -4461 | -2231 | 0 | 2 |
| force_flat | 1 | -308 | -308 | 0 | 1 |
| take_profit | 1 | 1012 | 1012 | 1 | 0 |
| time_exit | 12 | 1317 | 110 | 6 | 6 |

阶段性判断：

```text
B1+B2 对当前 R26 候选明显不利。

新增样本中，m 与 SR 都没有复制旧样本的正贡献；
主要问题不是目标无法兑现后的 time_exit，而是 reacceptance 后继续反向失败，
表现为 strict_failure_close 与 stop_loss 贡献了几乎全部大亏。
```

但仍然不建议立即调参：

```text
1. 当前只有两批、四个合约月份；
2. ticks=2/3 有重叠，不能当作独立样本加总；
3. 需要先确认这是“当前候选失效”，还是“2603/2605/605/609 这段行情状态不适配”。
```

## 10. 下一步计划调整

目标修正后，下一批不再把重点放在“救回全样本收益”。计划调整为：

```text
1. 先把 B1+B2 中的亏损期视为可能的强趋势 / 不适配行情样本；
2. 后续实验优先观察：赚钱交易或赚钱月份是否集中在某类行情窗口；
3. 重点指标从全样本 net_pnl 转为：赚钱窗口内的胜率、payoff、回撤形态、exit_reason 是否稳定；
4. 不赚钱时期只做识别与排除，不用降低 RR、放宽 entry 或扩大止损去强行适配。
```

下一批仍可保留两个小样本角色，但解释方式改变：

```text
1. rb 新月份作为强趋势 / 负面对照，验证该结构在强趋势里是否继续明显不适配；
2. 非 m/SR 新品种作为结构泛化观察，寻找是否存在更适合 reacceptance 的行情窗口；
3. 如果样本集中 strict_failure / stop_loss，优先归类为不适配窗口，而不是立即调参；
4. 如果出现赚钱窗口，下一步才围绕该窗口验证收益稳定性。
```

候选下一批：

```text
SHFE.rb2605 / SHFE.rb2610 作为负面对照；
DCE.p2601 或 DCE.i2601 作为非 m/SR 扩展观察。
```

## 11. R27-B3：第三批样本

### 11.1 样本与回测 ID

| backtest_id | symbol | ticks | 样本区间 | clearing_n | 角色 |
| ---: | --- | ---: | --- | ---: | --- |
| 686 | SHFE.rb2605 | 2 | 2026-01-05 ~ 2026-04-01 | 3 | rb 负面对照；趋势检测待确认 |
| 687 | SHFE.rb2605 | 3 | 2026-01-05 ~ 2026-04-01 | 1 | rb 负面对照；趋势检测待确认 |
| 688 | DCE.p2601 | 3 | 2025-09-01 ~ 2025-12-02 | 16 | 非 m/SR 结构观察 |
| 689 | DCE.p2601 | 2 | 2025-09-01 ~ 2025-12-02 | 20 | 非 m/SR 结构观察 |

说明：`688/689` 的入库顺序与 ticks 顺序相反；记录时按实际 `min_reaccept_ticks` 为准。

### 11.2 结果总览

| symbol | ticks | n | wins | losses | win_pct | net_pnl | avg_pnl | worst_pnl | best_pnl | avg_win | avg_loss | payoff | breakeven_win_pct |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| SHFE.rb2605 | 2 | 3 | 0 | 3 | 0.0% | -3429 | -1143 | -1547 | -467 | - | 1143 | - | - |
| SHFE.rb2605 | 3 | 1 | 0 | 1 | 0.0% | -467 | -467 | -467 | -467 | - | 467 | - | - |
| DCE.p2601 | 2 | 20 | 8 | 12 | 40.0% | -360 | -18 | -1180 | 1540 | 909 | 636 | 1.429 | 41.2% |
| DCE.p2601 | 3 | 16 | 9 | 7 | 56.3% | 930 | 58 | -1180 | 1460 | 731 | 806 | 0.906 | 52.5% |

### 11.3 按 exit_reason 观察

| symbol | ticks | exit_reason | n | net_pnl | avg_pnl | wins | losses |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| SHFE.rb2605 | 2 | strict_failure_close | 2 | -2962 | -1481 | 0 | 2 |
| SHFE.rb2605 | 2 | time_exit | 1 | -467 | -467 | 0 | 1 |
| SHFE.rb2605 | 3 | time_exit | 1 | -467 | -467 | 0 | 1 |
| DCE.p2601 | 2 | stop_loss | 7 | -3060 | -437 | 0 | 7 |
| DCE.p2601 | 2 | strict_failure_close | 4 | -3665 | -916 | 0 | 4 |
| DCE.p2601 | 2 | take_profit | 5 | 6020 | 1204 | 5 | 0 |
| DCE.p2601 | 2 | time_exit | 4 | 345 | 86 | 3 | 1 |
| DCE.p2601 | 3 | stop_loss | 3 | -1460 | -487 | 0 | 3 |
| DCE.p2601 | 3 | strict_failure_close | 4 | -4185 | -1046 | 0 | 4 |
| DCE.p2601 | 3 | take_profit | 5 | 5460 | 1092 | 5 | 0 |
| DCE.p2601 | 3 | time_exit | 4 | 1115 | 279 | 4 | 0 |

### 11.4 不符合预期现象

#### 11.4.1 rb2605 继续符合负面对照预期

`rb2605` 两组都没有胜笔：

```text
rb2605 ticks=2: n=3, win_pct=0.0%, net_pnl=-3429
rb2605 ticks=3: n=1, win_pct=0.0%, net_pnl=-467
```

这符合“rb 负面对照”的预期；但补充趋势检测后，`rb2605` 的整体样本标签并不是 `strong_trend`，因此这里不能继续简单归因为“强趋势不适配”。更准确的说法是：`rb` 在该参数结构下仍然是负面对照，但负贡献可能来自品种微观结构、波动路径或 reacceptance 失败，而不只是整体强趋势。

#### 11.4.2 p2601 出现了第一个新增样本中的赚钱窗口信号

`DCE.p2601` 与 B1/B2 的 m/SR 不同：

```text
p2601 ticks=2: n=20, net_pnl=-360，接近持平，payoff=1.429
p2601 ticks=3: n=16, net_pnl=930，win_pct=56.3%
```

这支持目标修正后的方向：不追求全行情适配，而是寻找 `reacceptance` 结构在哪些窗口赚钱更稳定。

#### 11.4.3 ticks=3 在 p2601 中反而更好

B1/B2 中 ticks=3 主要表现为减少交易但没有改善质量；B3 的 `p2601` 中 ticks=3 变成正收益：

```text
ticks=2: n=20, net_pnl=-360, win_pct=40.0%, payoff=1.429
ticks=3: n=16, net_pnl=930, win_pct=56.3%, payoff=0.906
```

这说明 `min_reaccept_ticks=3` 不是普遍无效，而可能需要依赖行情窗口。下一步不应简单删除 ticks=3，而应观察它在赚钱窗口中是否更稳定。

#### 11.4.4 p2601 仍有明显失败交易，但盈利出口足以覆盖

`p2601` 并不是没有失败：

```text
strict_failure_close + stop_loss 仍然存在；
take_profit 与 time_exit 贡献了主要正收益。
```

关键差异是：B1/B2 中失败出口压倒盈利出口；B3 的 `p2601` 中盈利出口开始能覆盖失败出口。这更接近当前修正后的研究问题。

### 11.5 POC edge / migration 观察

| symbol | ticks | poc_edge | migration | n | net_pnl | wins | losses |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: |
| DCE.p2601 | 2 | edge | away | 9 | 1410 | 5 | 4 |
| DCE.p2601 | 2 | central | mid | 5 | 975 | 2 | 3 |
| DCE.p2601 | 2 | edge | mid | 1 | 100 | 1 | 0 |
| DCE.p2601 | 2 | mid_edge | near_poc | 1 | -300 | 0 | 1 |
| DCE.p2601 | 2 | mid_edge | away | 2 | -920 | 0 | 2 |
| DCE.p2601 | 2 | mid_edge | mid | 2 | -1625 | 0 | 2 |
| DCE.p2601 | 3 | central | mid | 4 | 1275 | 2 | 2 |
| DCE.p2601 | 3 | edge | mid | 2 | 760 | 2 | 0 |
| DCE.p2601 | 3 | edge | away | 7 | 380 | 4 | 3 |
| DCE.p2601 | 3 | mid_edge | mid | 3 | -1485 | 1 | 2 |
| SHFE.rb2605 | 2 | edge | away | 2 | -1882 | 0 | 2 |
| SHFE.rb2605 | 2 | central | mid | 1 | -1547 | 0 | 1 |
| SHFE.rb2605 | 3 | edge | away | 1 | -467 | 0 | 1 |

`edge + away` 在 B1 里不能救回 SR/m，但在 `p2601` 中转正；它暂时仍只能作为窗口诊断字段，不能直接变成过滤器。

## 12. B3 后计划调整

B3 后，研究重心从“结构是否整体失效”进一步转为“赚钱窗口是否存在且是否稳定”：

```text
1. rb2605 继续验证了强趋势 / rb 负面对照不适配；
2. p2601 提供了新增样本中的第一个赚钱窗口信号；
3. 下一步优先围绕 p2601 的相邻或对照品种验证，而不是回头优化 m/SR；
4. 仍然固定 R26 参数，只观察窗口稳定性，不调 entry/target/stop。
```

候选下一批：

```text
DCE.y2601：油脂链相邻样本，观察 p2601 是否是油脂链窗口；
DCE.i2601：非 m/SR、非油脂链对照，观察正信号是否可泛化。
```

## 13. 已跑样本趋势强度补充检测

使用脚本：

```bash
uv run python scripts/analysis/sample_trend_check.py --markdown \
  project_data/market_data/csv/DCE.m2603.tqsdk.1m.csv \
  project_data/market_data/csv/CZCE.SR605.tqsdk.1m.csv \
  project_data/market_data/csv/DCE.m2605.tqsdk.1m.csv \
  project_data/market_data/csv/CZCE.SR609.tqsdk.1m.csv \
  project_data/market_data/csv/SHFE.rb2605.tqsdk.1m.csv \
  project_data/market_data/csv/DCE.p2601.tqsdk.1m.csv
```

趋势检测先将 1m CSV 聚合为日线，再给整个样本打标签：

```text
strong_trend / trend_bias / non_strong_trend
```

### 13.1 趋势检测结果

| symbol | daily_rows | range | trend_label | net_change_pct | close_location | efficiency_ratio | trend_atr | directional_consistency | strong_window_ratio |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| DCE.m2603 | 63 | 2025-11-03 ~ 2026-01-30 | non_strong_trend | 3.10% | 0.562 | 0.085 | 2.52 | 0.500 | 0.000 |
| CZCE.SR605 | 87 | 2026-01-05 ~ 2026-05-19 | non_strong_trend | 1.94% | 0.698 | 0.048 | 1.78 | 0.500 | 0.062 |
| DCE.m2605 | 57 | 2026-01-05 ~ 2026-04-01 | non_strong_trend | 4.13% | 0.338 | 0.098 | 2.49 | 0.527 | 0.300 |
| CZCE.SR609 | 40 | 2026-05-06 ~ 2026-07-01 | trend_bias | -2.60% | 0.247 | 0.154 | 2.91 | 0.590 | 0.000 |
| SHFE.rb2605 | 57 | 2026-01-05 ~ 2026-04-01 | non_strong_trend | 1.07% | 0.627 | 0.037 | 1.04 | 0.509 | 0.000 |
| DCE.p2601 | 61 | 2025-09-01 ~ 2025-12-02 | trend_bias | -8.06% | 0.317 | 0.171 | 5.15 | 0.561 | 0.091 |

### 13.2 与回测结果对照

| symbol | trend_label | R27 表现 | 对照结论 |
| --- | --- | --- | --- |
| DCE.m2603 | non_strong_trend | 负，样本极少 | 亏损不能归因为整段强趋势。 |
| CZCE.SR605 | non_strong_trend | 明显负 | SR605 失效不是简单强趋势问题。 |
| DCE.m2605 | non_strong_trend | 明显负 | m2605 失效也不是简单强趋势问题。 |
| CZCE.SR609 | trend_bias | 负但交易数少 | 有轻微趋势偏向，但不足以解释为强趋势过滤问题。 |
| SHFE.rb2605 | non_strong_trend | 负面对照继续负 | rb 负贡献不能直接归因为强趋势，仍需作为品种/结构负面对照。 |
| DCE.p2601 | trend_bias | ticks=3 转正，ticks=2 接近持平 | 赚钱窗口并不要求完全震荡；轻度趋势偏向下也可能有效。 |

### 13.3 新结论

```text
1. B1-B3 已跑样本中，没有任何一个被简单趋势检测标为 strong_trend；
2. 因此，当前 R27 的失败不能直接解释为“样本整体都是强趋势”；
3. 更可能的问题是：某些品种 / 月份中，reacceptance 后的失败路径更强，导致 strict_failure_close / stop_loss 覆盖了盈利出口；
4. p2601 的正信号说明策略不一定只适合完全震荡，轻度趋势偏向下也可能赚钱；
5. 后续每批需要同时记录 trend_label 与 exit_reason，避免把亏损过早归因为强趋势。
```

对后续实验的影响：

```text
1. “强趋势不适配”仍作为假设保留，但当前批次没有直接证据支持；
2. 下一步不应只找强趋势过滤器，而应比较不同 trend_label 下的 exit_reason 结构；
3. 若未来出现 strong_trend 样本，再验证 strict_failure / stop_loss 是否显著上升；
4. B4 的 DCE.y2601 / DCE.i2601 也必须同步补 trend_label。
```

## 14. R27-B4：第四批样本

### 14.1 样本、回测 ID 与趋势标签

| backtest_id | symbol | ticks | 样本区间 | clearing_n | trend_label | 角色 |
| ---: | --- | ---: | --- | ---: | --- | --- |
| 690 | DCE.y2601 | 2 | 2025-09-01 ~ 2025-12-02 | 17 | non_strong_trend | 油脂链相邻样本 |
| 691 | DCE.y2601 | 3 | 2025-09-01 ~ 2025-12-02 | 15 | non_strong_trend | 油脂链相邻样本 |
| 692 | DCE.i2601 | 2 | 2025-09-01 ~ 2025-12-02 | 0 | non_strong_trend | 非 m/SR、非油脂链对照 |
| 693 | DCE.i2601 | 3 | 2025-09-01 ~ 2025-12-02 | 0 | non_strong_trend | 非 m/SR、非油脂链对照 |

趋势检测：

| symbol | daily_rows | trend_label | net_change_pct | close_location | efficiency_ratio | trend_atr | directional_consistency | strong_window_ratio |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| DCE.y2601 | 61 | non_strong_trend | -1.29% | 0.584 | 0.037 | 1.16 | 0.533 | 0.000 |
| DCE.i2601 | 61 | non_strong_trend | 3.70% | 0.680 | 0.074 | 2.13 | 0.559 | 0.000 |

### 14.2 结果总览

| symbol | ticks | n | wins | losses | win_pct | net_pnl | avg_pnl | worst_pnl | best_pnl | avg_win | avg_loss | payoff | breakeven_win_pct |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DCE.y2601 | 2 | 17 | 9 | 8 | 52.9% | 525 | 31 | -975 | 1125 | 725 | 750 | 0.967 | 50.8% |
| DCE.y2601 | 3 | 15 | 7 | 8 | 46.7% | -2225 | -148 | -975 | 1125 | 654 | 850 | 0.769 | 56.5% |
| DCE.i2601 | 2 | 0 | 0 | 0 | - | 0 | - | - | - | - | - | - | - |
| DCE.i2601 | 3 | 0 | 0 | 0 | - | 0 | - | - | - | - | - | - | - |

说明：`DCE.i2601` 两组成功完成回测，但没有触发交易，不纳入收益质量判断。

### 14.3 按 exit_reason 观察

| symbol | ticks | exit_reason | n | net_pnl | avg_pnl | wins | losses |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| DCE.y2601 | 2 | strict_failure_close | 8 | -6000 | -750 | 0 | 8 |
| DCE.y2601 | 2 | take_profit | 6 | 4450 | 742 | 6 | 0 |
| DCE.y2601 | 2 | time_exit | 3 | 2075 | 692 | 3 | 0 |
| DCE.y2601 | 3 | strict_failure_close | 8 | -6800 | -850 | 0 | 8 |
| DCE.y2601 | 3 | take_profit | 4 | 2900 | 725 | 4 | 0 |
| DCE.y2601 | 3 | time_exit | 3 | 1675 | 558 | 3 | 0 |

### 14.4 不符合预期现象

#### 14.4.1 y2601 没有复制 p2601 的赚钱窗口稳定性

`DCE.y2601` 与 `DCE.p2601` 同属油脂链，但表现明显弱于 `p2601`：

```text
p2601 ticks=3: n=16, net_pnl=930, win_pct=56.3%
y2601 ticks=3: n=15, net_pnl=-2225, win_pct=46.7%
```

`ticks=2` 虽然小幅正收益，但优势很薄：

```text
y2601 ticks=2: net_pnl=525, payoff=0.967, breakeven_win_pct=50.8%
```

这说明 `p2601` 的正信号不能直接推广成“油脂链整体有效”。

#### 14.4.2 ticks=3 再次没有稳定改善质量

B3 中 `p2601 ticks=3` 明显优于 ticks=2；但 B4 的 `y2601` 相反：

```text
y2601 ticks=2: net_pnl=525
y2601 ticks=3: net_pnl=-2225
```

`ticks=3` 在这里减少了 2 笔交易，但没有减少 `strict_failure_close` 数量，反而降低了盈利出口覆盖能力。

#### 14.4.3 i2601 完全无交易，是结构触发稀疏样本

`DCE.i2601` 两组均为 0 clearing：

```text
i2601 ticks=2: n=0
i2601 ticks=3: n=0
```

这不是正负收益结论，而是说明当前结构在该样本上触发条件过窄或没有形成可交易 reacceptance。

#### 14.4.4 非强趋势样本也会失败

`y2601` 与 `i2601` 都被标为 `non_strong_trend`。其中 `y2601 ticks=3` 仍然明显亏损，进一步支持 B1-B3 的补充结论：当前问题不能简单归因为强趋势，而更应关注 `strict_failure_close` 与盈利出口覆盖关系。

### 14.5 B4 后计划调整

```text
1. p2601 是目前最值得保留观察的赚钱窗口，但 y2601 没有证明油脂链整体有效；
2. non_strong_trend 不是充分条件，样本即使不强趋势也可能因 strict_failure 覆盖盈利出口；
3. i2601 无交易，后续不要优先投入该样本做参数细化；
4. 下一批应继续找“有足够交易数 + 非 m/SR + 非 strong_trend”的样本，而不是围绕 i2601；
5. 如果要验证 p2601 稳定性，优先找同类但不同月份的 DCE.p2509，或找 y2509 作为油脂链旧月份对照。
```

## 15. R27-B5：第五批样本

### 15.1 样本、回测 ID 与趋势标签

| backtest_id | symbol | ticks | 样本区间 | clearing_n | trend_label | 角色 |
| ---: | --- | ---: | --- | ---: | --- | --- |
| 695 | DCE.p2509 | 2 | 2025-05-06 ~ 2025-08-01 | 13 | strong_trend | p2601 跨月份复验 |
| 697 | DCE.p2509 | 3 | 2025-05-06 ~ 2025-08-01 | 12 | strong_trend | p2601 跨月份复验 |
| 696 | DCE.y2509 | 2 | 2025-05-06 ~ 2025-08-01 | 11 | trend_bias | 油脂链旧月份对照 |
| 698 | DCE.y2509 | 3 | 2025-05-06 ~ 2025-08-01 | 9 | trend_bias | 油脂链旧月份对照 |

趋势检测：

| symbol | daily_rows | trend_label | net_change_pct | close_location | efficiency_ratio | trend_atr | directional_consistency | strong_window_ratio |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| DCE.p2509 | 63 | strong_trend | 11.02% | 0.751 | 0.208 | 6.74 | 0.557 | 0.000 |
| DCE.y2509 | 63 | trend_bias | 6.20% | 0.898 | 0.157 | 5.34 | 0.548 | 0.091 |

### 15.2 结果总览

| symbol | ticks | n | wins | losses | win_pct | net_pnl | avg_pnl | worst_pnl | best_pnl | avg_win | avg_loss | payoff | breakeven_win_pct |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DCE.p2509 | 2 | 13 | 6 | 7 | 46.2% | 1540 | 118 | -1020 | 1620 | 1113 | 734 | 1.516 | 39.7% |
| DCE.p2509 | 3 | 12 | 5 | 7 | 41.7% | 640 | 53 | -1020 | 1620 | 1188 | 757 | 1.569 | 38.9% |
| DCE.y2509 | 2 | 11 | 4 | 7 | 36.4% | -1825 | -166 | -775 | 1025 | 625 | 618 | 1.012 | 49.7% |
| DCE.y2509 | 3 | 9 | 3 | 6 | 33.3% | -2375 | -264 | -775 | 1025 | 458 | 625 | 0.733 | 57.7% |

### 15.3 按 exit_reason 观察

| symbol | ticks | exit_reason | n | net_pnl | avg_pnl | wins | losses |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| DCE.p2509 | 2 | stop_loss | 4 | -2560 | -640 | 0 | 4 |
| DCE.p2509 | 2 | strict_failure_close | 3 | -2580 | -860 | 0 | 3 |
| DCE.p2509 | 2 | take_profit | 5 | 5780 | 1156 | 5 | 0 |
| DCE.p2509 | 2 | time_exit | 1 | 900 | 900 | 1 | 0 |
| DCE.p2509 | 3 | stop_loss | 4 | -2560 | -640 | 0 | 4 |
| DCE.p2509 | 3 | strict_failure_close | 3 | -2740 | -913 | 0 | 3 |
| DCE.p2509 | 3 | take_profit | 4 | 4880 | 1220 | 4 | 0 |
| DCE.p2509 | 3 | time_exit | 1 | 1060 | 1060 | 1 | 0 |
| DCE.y2509 | 2 | force_flat | 1 | 225 | 225 | 1 | 0 |
| DCE.y2509 | 2 | stop_loss | 1 | -675 | -675 | 0 | 1 |
| DCE.y2509 | 2 | strict_failure_close | 5 | -3375 | -675 | 0 | 5 |
| DCE.y2509 | 2 | take_profit | 2 | 1650 | 825 | 2 | 0 |
| DCE.y2509 | 2 | time_exit | 2 | 350 | 175 | 1 | 1 |
| DCE.y2509 | 3 | force_flat | 1 | 125 | 125 | 1 | 0 |
| DCE.y2509 | 3 | strict_failure_close | 5 | -3475 | -695 | 0 | 5 |
| DCE.y2509 | 3 | take_profit | 1 | 1025 | 1025 | 1 | 0 |
| DCE.y2509 | 3 | time_exit | 2 | -50 | -25 | 1 | 1 |

### 15.4 不符合预期现象

#### 15.4.1 p2509 复制了 p2601 的正信号，而且出现在 strong_trend 标签下

`DCE.p2509` 两组均为正：

```text
p2509 ticks=2: n=13, net_pnl=1540, payoff=1.516
p2509 ticks=3: n=12, net_pnl=640, payoff=1.569
```

这强化了 `DCE.p` 这个品种窗口，而不是简单的油脂链窗口。

更重要的是，`p2509` 被趋势脚本标为 `strong_trend`。这与早先“强趋势可能不适配”的直觉相反：至少对于 `DCE.p`，强趋势标签不必然导致策略失效。

#### 15.4.2 y2509 继续没有复制 p 的正信号

`DCE.y2509` 与 B4 的 `DCE.y2601` 一样偏弱：

```text
y2601 ticks=2:  525
y2601 ticks=3: -2225
y2509 ticks=2: -1825
y2509 ticks=3: -2375
```

这进一步说明：正信号更像是 `DCE.p` 特定品种窗口，而不是油脂链整体。

#### 15.4.3 p 的盈利来自 take_profit 足够大，而不是没有失败

`p2509` 仍然有大量 `stop_loss / strict_failure_close`：

```text
p2509 ticks=2: stop_loss + strict_failure_close = -5140
p2509 ticks=3: stop_loss + strict_failure_close = -5300
```

但其 `take_profit + time_exit` 能覆盖亏损：

```text
p2509 ticks=2: take_profit + time_exit = 6680
p2509 ticks=3: take_profit + time_exit = 5940
```

这与 `p2601` 的结构一致：关键不是完全避免失败，而是盈利出口是否足够覆盖失败出口。

#### 15.4.4 ticks=2 在 p2509 中优于 ticks=3

`p2601` 是 ticks=3 更好，`p2509` 则是 ticks=2 更好：

```text
p2601: ticks=2 -360, ticks=3 +930
p2509: ticks=2 +1540, ticks=3 +640
```

因此不能把 ticks=3 固定为更优确认；在 `DCE.p` 窗口中，ticks=2/3 都应保留继续观察。

### 15.5 B5 后阶段判断

```text
1. value_area_reacceptance 不能完全否定；
2. m/SR 主线已基本失效，应降级；
3. DCE.p 出现跨月份正信号，是当前唯一值得继续验证的品种窗口；
4. y 连续两个样本没有复制 p，油脂链整体假设不成立；
5. strong_trend 本身不是充分否定条件，p2509 在 strong_trend 标签下反而盈利；
6. 后续重点应从“过滤强趋势”转为“识别哪些品种/路径下盈利出口能覆盖 strict_failure / stop_loss”。
```

候选下一批：

```text
DCE.p 的更多月份优先；
若没有更多 p 月份，则用其他非 m/SR 且有足够交易数的农产品/化工样本做横向对照。
```

## 16. 已跑样本活跃度补充检测

使用脚本：

```bash
uv run python scripts/analysis/sample_activity_check.py --markdown \
  project_data/market_data/csv/DCE.m2603.tqsdk.1m.csv \
  project_data/market_data/csv/CZCE.SR605.tqsdk.1m.csv \
  project_data/market_data/csv/DCE.m2605.tqsdk.1m.csv \
  project_data/market_data/csv/CZCE.SR609.tqsdk.1m.csv \
  project_data/market_data/csv/SHFE.rb2605.tqsdk.1m.csv \
  project_data/market_data/csv/DCE.p2601.tqsdk.1m.csv \
  project_data/market_data/csv/DCE.y2601.tqsdk.1m.csv \
  project_data/market_data/csv/DCE.i2601.tqsdk.1m.csv \
  project_data/market_data/csv/DCE.p2509.tqsdk.1m.csv \
  project_data/market_data/csv/DCE.y2509.tqsdk.1m.csv
```

该脚本只检查 CSV 自身的成交活跃度，不验证“是否主力连续合约”。当前标签口径：

```text
active / thin / suspicious
```

### 16.1 活跃度检测结果

| symbol | daily_rows | range | active_label | total_volume | median_daily_volume | median_bar_volume | zero_volume_bar_ratio | active_day_ratio |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |
| DCE.m2603 | 63 | 2025-11-03 ~ 2026-01-30 | active | 7188862 | 105371 | 156 | 0.011 | 1.000 |
| CZCE.SR605 | 87 | 2026-01-05 ~ 2026-05-19 | active | 16472761 | 199938 | 324 | 0.115 | 0.839 |
| DCE.m2605 | 57 | 2026-01-05 ~ 2026-04-01 | active | 63532951 | 935156 | 2207 | 0.000 | 1.000 |
| CZCE.SR609 | 40 | 2026-05-06 ~ 2026-07-01 | active | 16189771 | 402480 | 798 | 0.000 | 1.000 |
| SHFE.rb2605 | 57 | 2026-01-05 ~ 2026-04-01 | active | 45498896 | 773545 | 1495 | 0.000 | 1.000 |
| DCE.p2601 | 61 | 2025-09-01 ~ 2025-12-02 | active | 34896277 | 567885 | 1211 | 0.000 | 1.000 |
| DCE.y2601 | 61 | 2025-09-01 ~ 2025-12-02 | active | 17550318 | 275140 | 585 | 0.000 | 1.000 |
| DCE.i2601 | 61 | 2025-09-01 ~ 2025-12-02 | active | 18200320 | 282670 | 535 | 0.000 | 1.000 |
| DCE.p2509 | 63 | 2025-05-06 ~ 2025-08-01 | active | 39971442 | 613173 | 1325 | 0.000 | 1.000 |
| DCE.y2509 | 63 | 2025-05-06 ~ 2025-08-01 | active | 21704041 | 327951 | 734 | 0.000 | 1.000 |

### 16.2 数据边界修正

```text
1. 本轮样本使用的是具体合约交割前约 4 个月窗口；
2. 当前补充检测显示，这些 CSV 从成交量角度均为 active；
3. 因此目前不能把 m/SR 或 y 的负结果解释为“明显低流动性样本”；
4. i2601 无交易也不是因为 CSV 成交稀疏，而是当前策略结构没有触发；
5. 但 active_label 不等于“当时为主力合约”，主力/次主力归属仍未验证。
```

对结论的影响：

```text
1. DCE.p 的正信号更可信一些，因为 p2509/p2601 都是 active；
2. m/SR 的失效也更有信息量，因为不是明显 thin/suspicious 数据导致；
3. 后续实验记录必须同时列出 trend_label 与 active_label；
4. 若未来要进入上线级验证，需要再做主力合约 / 持仓排名 / 换月阶段验证。
```

## 17. R27-B6：m 旧正样本补充复验

### 17.1 样本、回测 ID 与样本标签

本批目的：在 `DCE.p` 样本不足时，回头检查旧主线 `DCE.m` 是否还能在更多历史月份复现正贡献。

重要口径修正：本批回测入库后确认 `kline_interval=5m`，不是本轮固定的 `1m` 口径。因此 B6 只能作为旁证和数据流程提醒，不能与 B1-B5 / B7 的 1m 结果直接比较，也不能用于恢复或否定 `DCE.m` 主线。

| backtest_id | symbol | ticks | 样本区间 | clearing_n | trend_label | active_label | 角色 |
| ---: | --- | ---: | --- | ---: | --- | --- | --- |
| 699 | DCE.m2509 | 2 | 2025-05-06 ~ 2025-08-01 | 4 | non_strong_trend | active | m 旧主线补充复验 |
| 700 | DCE.m2509 | 3 | 2025-05-06 ~ 2025-08-01 | 2 | non_strong_trend | active | m 旧主线补充复验 |
| 701 | DCE.m2505 | 2 | 2025-01-02 ~ 2025-04-01 | 5 | non_strong_trend | active | m 旧主线补充复验 |
| 702 | DCE.m2505 | 3 | 2025-01-02 ~ 2025-04-01 | 3 | non_strong_trend | active | m 旧主线补充复验 |

补充样本检测：

| symbol | csv_range | daily_rows | trend_label | active_label | median_daily_volume | active_day_ratio |
| --- | --- | ---: | --- | --- | ---: | ---: |
| DCE.m2509 | 2025-06-24 ~ 2025-08-01 | 29 | non_strong_trend | active | 1006065 | 1.000 |
| DCE.m2505 | 2025-01-02 ~ 2025-04-01 | 58 | non_strong_trend | active | 1616752 | 1.000 |

注意：`DCE.m2509` 的名义回测区间是 `2025-05-06 ~ 2025-08-01`，但 CSV 实际起点是 `2025-06-24`，因此该样本不能当作完整 4 个月窗口，只能作为弱证据。

### 17.2 结果总览

| symbol | ticks | n | wins | losses | win_pct | net_pnl | avg_pnl | worst_pnl | best_pnl | avg_win | avg_loss | payoff |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DCE.m2509 | 2 | 4 | 2 | 2 | 50.0% | -510 | -128 | -1246 | 1092 | 851 | 1106 | 0.769 |
| DCE.m2509 | 3 | 2 | 2 | 0 | 100.0% | 1551 | 776 | 459 | 1092 | 776 | - | - |
| DCE.m2505 | 2 | 5 | 2 | 3 | 40.0% | -2993 | -599 | -2327 | 2394 | 1274 | 1847 | 0.690 |
| DCE.m2505 | 3 | 3 | 1 | 2 | 33.3% | -1734 | -578 | -2327 | 2114 | 2114 | 1924 | 1.099 |

### 17.3 按 exit_reason 观察

| symbol | ticks | exit_reason | n | net_pnl | avg_pnl | wins | losses |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| DCE.m2509 | 2 | force_flat | 1 | 610 | 610 | 1 | 0 |
| DCE.m2509 | 2 | stop_loss | 2 | -2212 | -1106 | 0 | 2 |
| DCE.m2509 | 2 | take_profit | 1 | 1092 | 1092 | 1 | 0 |
| DCE.m2509 | 3 | force_flat | 1 | 459 | 459 | 1 | 0 |
| DCE.m2509 | 3 | take_profit | 1 | 1092 | 1092 | 1 | 0 |
| DCE.m2505 | 2 | force_flat | 1 | 154 | 154 | 1 | 0 |
| DCE.m2505 | 2 | stop_loss | 2 | -3875 | -1938 | 0 | 2 |
| DCE.m2505 | 2 | strict_failure_close | 1 | -1666 | -1666 | 0 | 1 |
| DCE.m2505 | 2 | take_profit | 1 | 2394 | 2394 | 1 | 0 |
| DCE.m2505 | 3 | stop_loss | 1 | -2327 | -2327 | 0 | 1 |
| DCE.m2505 | 3 | strict_failure_close | 1 | -1521 | -1521 | 0 | 1 |
| DCE.m2505 | 3 | take_profit | 1 | 2114 | 2114 | 1 | 0 |

### 17.4 不符合预期现象

#### 17.4.1 m2509 ticks=3 转正，但交易数太少且样本不完整

`DCE.m2509 ticks=3` 结果为正：

```text
n=2, wins=2, net_pnl=1551
```

但该组只有 2 笔清算交易，且 CSV 实际只覆盖 `2025-06-24 ~ 2025-08-01`。因此它不能直接恢复 `DCE.m` 主线，只能说明 `m` 仍可能存在个别赚钱窗口。

#### 17.4.2 m2505 明确没有复现旧正样本

`DCE.m2505` 两组都为负：

```text
ticks=2: net_pnl=-2993
ticks=3: net_pnl=-1734
```

亏损主要来自 `stop_loss + strict_failure_close`：

```text
m2505 ticks=2: stop_loss + strict_failure_close = -5541
m2505 ticks=3: stop_loss + strict_failure_close = -3848
```

虽然存在 take_profit，但不足以覆盖失败出口。

#### 17.4.3 m 的问题仍不是整体强趋势或成交稀疏

`m2509/m2505` 都被标为：

```text
trend_label = non_strong_trend
active_label = active
```

因此这一批继续支持前面的判断：`DCE.m` 扩样失败不能简单归因为整体强趋势，也不能解释为明显低流动性 CSV。

#### 17.4.4 清算阶段出现未配对余量告警

运行日志中，`699/701/702` 出现过“平仓有余量未配对”告警。当前仍以 `trade_clearings` 作为主统计口径，但该现象需要保留为数据/清算质量提示：如果后续某一结论高度依赖这些样本，需要再单独检查成交配对。

### 17.5 B6 后阶段判断

```text
1. B6 因周期口径为 5m，不能用于恢复或否定 DCE.m 的 1m 主线；
2. 它只作为旁证提示：m 旧正样本需要重新按显式 kline_period=1m 复跑后才能比较；
3. 当前最清晰的 1m 正信号仍然是 DCE.p，而不是 DCE.m；
4. 后续若继续做 m，应显式写入 kline_period=1m，并作为对照和结构拆解样本。
```

下一步建议：

```text
1. 继续优先寻找更多 DCE.p 可用月份；
2. 如果暂时没有 p 数据，则不要急着扩大品种，而是做结构拆解：比较 DCE.p 正样本与 DCE.m/y/SR 负样本中 stop_loss、strict_failure_close、take_profit 的触发前路径；
3. 对 m2509 这类样本不完整且周期口径不一致的结果，暂不纳入强结论。
```

## 18. R27-B7：DCE.p 新月份补充复验

### 18.1 数据补充与运行口径

本批补拉并回测两个 `DCE.p` 新月份：

```bash
uv run python main.py export --env backtest --symbol DCE.p2605 --source tqsdk --interval 1m
uv run python main.py export --env backtest --symbol DCE.p2505 --source tqsdk --interval 1m
```

第一次回测曾漏传 `kline_period=1m`，CLI 尝试加载 5m 元数据并中止，未生成回测。正式回测已显式传入：

```json
{"kline_period":"1m"}
```

因此本批 `703-706` 的 `kline_interval` 已确认均为 `1m`。

### 18.2 样本、回测 ID 与样本标签

| backtest_id | symbol | ticks | kline_interval | 样本区间 | clearing_n | trend_label | active_label |
| ---: | --- | ---: | --- | --- | ---: | --- | --- |
| 703 | DCE.p2605 | 2 | 1m | 2026-01-05 ~ 2026-04-01 | 26 | strong_trend | active |
| 704 | DCE.p2605 | 3 | 1m | 2026-01-05 ~ 2026-04-01 | 23 | strong_trend | active |
| 705 | DCE.p2505 | 2 | 1m | 2025-01-02 ~ 2025-04-01 | 19 | strong_trend | active |
| 706 | DCE.p2505 | 3 | 1m | 2025-01-02 ~ 2025-04-01 | 14 | strong_trend | active |

样本检测：

| symbol | daily_rows | range | trend_label | net_change_pct | close_location | efficiency_ratio | trend_atr | active_label | median_daily_volume |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | --- | ---: |
| DCE.p2605 | 57 | 2026-01-05 ~ 2026-04-01 | strong_trend | 16.19% | 0.813 | 0.251 | 6.88 | active | 472164 |
| DCE.p2505 | 58 | 2025-01-02 ~ 2025-04-01 | strong_trend | 8.04% | 0.765 | 0.125 | 3.71 | active | 999946 |

### 18.3 结果总览

| symbol | ticks | n | wins | losses | win_pct | net_pnl | avg_pnl | worst_pnl | best_pnl | avg_win | avg_loss | payoff |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DCE.p2605 | 2 | 26 | 10 | 16 | 38.5% | -1230 | -47 | -1340 | 2020 | 1041 | 727 | 1.431 |
| DCE.p2605 | 3 | 23 | 10 | 13 | 43.5% | -225 | -10 | -1580 | 2020 | 1052 | 826 | 1.273 |
| DCE.p2505 | 2 | 19 | 6 | 13 | 31.6% | -3625 | -191 | -1350 | 1860 | 1178 | 823 | 1.432 |
| DCE.p2505 | 3 | 14 | 6 | 8 | 42.9% | 380 | 27 | -1390 | 1860 | 1325 | 946 | 1.400 |

### 18.4 按 exit_reason 观察

| symbol | ticks | exit_reason | n | net_pnl | avg_pnl | wins | losses |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| DCE.p2605 | 2 | force_flat | 1 | -380 | -380 | 0 | 1 |
| DCE.p2605 | 2 | forced_close | 1 | 75 | 75 | 1 | 0 |
| DCE.p2605 | 2 | stop_loss | 2 | -1585 | -793 | 0 | 2 |
| DCE.p2605 | 2 | strict_failure_close | 10 | -9085 | -909 | 0 | 10 |
| DCE.p2605 | 2 | take_profit | 7 | 8290 | 1184 | 7 | 0 |
| DCE.p2605 | 2 | time_exit | 5 | 1455 | 291 | 2 | 3 |
| DCE.p2605 | 3 | force_flat | 1 | -460 | -460 | 0 | 1 |
| DCE.p2605 | 3 | forced_close | 1 | 75 | 75 | 1 | 0 |
| DCE.p2605 | 3 | stop_loss | 3 | -3005 | -1002 | 0 | 3 |
| DCE.p2605 | 3 | strict_failure_close | 7 | -6680 | -954 | 0 | 7 |
| DCE.p2605 | 3 | take_profit | 6 | 7710 | 1285 | 6 | 0 |
| DCE.p2605 | 3 | time_exit | 5 | 2135 | 427 | 3 | 2 |
| DCE.p2505 | 2 | stop_loss | 9 | -7470 | -830 | 0 | 9 |
| DCE.p2505 | 2 | strict_failure_close | 3 | -2990 | -997 | 0 | 3 |
| DCE.p2505 | 2 | take_profit | 5 | 6570 | 1314 | 5 | 0 |
| DCE.p2505 | 2 | time_exit | 2 | 265 | 133 | 1 | 1 |
| DCE.p2505 | 3 | stop_loss | 5 | -4460 | -892 | 0 | 5 |
| DCE.p2505 | 3 | strict_failure_close | 3 | -3110 | -1037 | 0 | 3 |
| DCE.p2505 | 3 | take_profit | 6 | 7950 | 1325 | 6 | 0 |

### 18.5 不符合预期现象

#### 18.5.1 p 正信号被削弱，但没有完全消失

新增两个 `p` 月份后，表现从“明确正”降为“接近持平到弱正/弱负”：

```text
p2601: ticks=2 -360, ticks=3 +930
p2509: ticks=2 +1540, ticks=3 +640
p2605: ticks=2 -1230, ticks=3 -225
p2505: ticks=2 -3625, ticks=3 +380
```

这说明 `DCE.p` 不是稳定单边盈利，但相比 `m/SR/y/rb`，仍然是当前最接近可研究窗口的品种。

#### 18.5.2 ticks=3 在新增 p 月份中继续更稳

新增两个月份里，ticks=3 都优于 ticks=2：

```text
p2605: ticks=2 -1230，ticks=3 -225
p2505: ticks=2 -3625，ticks=3 +380
```

这与 `p2601` 一致，但与 `p2509` 不一致。因此不能简单定论为 ticks=3 全局更优；只能说在多数 p 样本中，ticks=3 对失败交易有一定压缩作用。

#### 18.5.3 强趋势仍不是充分否定条件

`p2605/p2505` 都是 `strong_trend`，但结果并非全部崩溃：

```text
p2605 ticks=3 接近持平；
p2505 ticks=3 小幅为正。
```

因此趋势标签只能作为解释变量，不能作为直接排除规则。

#### 18.5.4 p 的核心矛盾非常清楚：take_profit 很强，但 strict_failure/stop_loss 仍然过重

新增 `p` 样本里，盈利出口依然有能力产生大额正贡献：

```text
p2605 ticks=2: take_profit + time_exit = 9745
p2605 ticks=3: take_profit + time_exit = 9845
p2505 ticks=2: take_profit + time_exit = 6835
p2505 ticks=3: take_profit = 7950
```

但失败出口也很重：

```text
p2605 ticks=2: stop_loss + strict_failure_close = -10670
p2605 ticks=3: stop_loss + strict_failure_close = -9685
p2505 ticks=2: stop_loss + strict_failure_close = -10460
p2505 ticks=3: stop_loss + strict_failure_close = -7570
```

所以后续结构拆解重点应是：为什么某些月份的 reacceptance 后失败路径更容易持续，而不是继续扩大品种或盲目调参。

### 18.6 B7 后阶段判断

```text
1. DCE.p 的正信号被削弱，但没有被完全否定；
2. p 不是稳定赚钱品种，但仍明显比 m/SR/y/rb 更值得继续做结构拆解；
3. 新增 p 样本支持 ticks=3 相对更稳的倾向，但证据还不够作为最终参数结论；
4. strong_trend 不能作为排除条件；
5. 当前下一步应从“继续扩品种”转为“结构拆解”：比较 p 正/负月份中 strict_failure_close、stop_loss 与 take_profit 的触发前价格路径。
```








