# 策略当前研究进度

> 类型：Research / 当前策略研究状态\
> 状态：活跃\
> 最近更新：2026-06-29\
> 上一阶段归档：[结构型 Alpha 随机对照阶段归档](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/README.md)\
> 长期框架：[策略长期共识：共识价格区间下的账户风险结构塑形框架](../roadmap/strategy-research-framework.md)

## 1. 当前一句话结论

当前策略研究已经从“寻找更多结构入口”转向：

```text
围绕价值区 VAH / VAL 重新接受主线，
验证方向 edge 能否在账户风险预算、品种适配、尾部风险和成本约束下稳定兑现。
```

结论来源：

- [结构型 Alpha 随机对照阶段结题报告](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/structural-alpha-stage-final-report.md)
- [价值区深耕摘要](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/value-area-deepening-summary.md)

## 2. 当前主线

当前最值得继续的策略结构是：

```text
value_area_reacceptance
+ POC 空间
+ price_raw_rr 预筛
+ min_reaccept_ticks 2~3
+ max_hold_bars ≈ 12
```

含义：

```text
前日 VAL 下破失败后重新接受回价值区内 → 做多，目标 POC；
前日 VAH 上破失败后重新接受回价值区内 → 做空，目标 POC；
入场不在刚刚贴边收回，而等待 5m 收盘价进入价值区内侧 2~3 ticks；
只保留到 POC 有足够空间且价格原始盈亏比不太差的样本。
```

证据来源：

- [价值区深耕摘要：当前主线版本](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/value-area-deepening-summary.md#6-当前主线版本)
- [阶段结题报告：推荐下一阶段主线](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/structural-alpha-stage-final-report.md#8-阶段决策)

## 3. 已确认成果

### 3.1 结构入口不是整体等同随机

阶段随机对照已经确认：

```text
价值区、前日高低点、成交量冲击等结构不应被视为纯随机噪声。
```

但优势层级不同：

```text
价值区：最强主线；
前日高低点：弱方向线索；
成交量冲击：质量标签；
小时流动性：当前方向暂停；
低波再启动：交易机会不足。
```

证据来源：

- [随机对照实验摘要：横向结果矩阵](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/random-baseline-experiment-summary.md#3-横向结果矩阵)
- [阶段结题报告：结构路线结论矩阵](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/structural-alpha-stage-final-report.md#4-结构路线结论矩阵)

### 3.2 方向层部分有效，原始风险空间层不足

随机对照后的关键判断：

```text
事件 / 方向可能有信息，
但当前入场价格、strict failure、止损和账户风险空间塑形没有普遍证明有效。
```

价值区原始版本的方向假设有效，但原始入场 / strict failure 没有显著优于同事件同方向随机风险空间。

证据来源：

- [随机对照实验摘要：风险空间层普遍不足](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/random-baseline-experiment-summary.md#42-风险空间层普遍不足)
- [价值区深耕摘要：深耕背景](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/value-area-deepening-summary.md#1-深耕背景)

### 3.3 价值区重新接受深度有效

最重要的正反馈是：

```text
不要在刚刚收回 VAH / VAL 时立刻进；
等待 5m K 线收盘价重新收回价值区内侧 2~3 ticks，
能显著改善风险空间质量。
```

注意：`2~3 ticks` 不是最终稳定参数，而是“重新接受需要最小确认深度”的证据。

证据来源：

- [价值区深耕摘要：深度重新接受](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/value-area-deepening-summary.md#3-深度重新接受)
- [阶段结题报告：最重要的正反馈](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/structural-alpha-stage-final-report.md#5-最重要的正反馈)

### 3.4 DCE.m 与 SR 的价值区机制不同

当前不能假设所有品种共用一个最优参数。

阶段结论：

```text
DCE.m2601 上，min_reaccept_ticks = 2 改善最明确；
CZCE.SR601 上，2 ticks 更偏胜率优势，3 ticks 对尾部风险更友好。
```

证据来源：

- [价值区深耕摘要：机制诊断](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/value-area-deepening-summary.md#4-机制诊断)
- [阶段结题报告：后续建议](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/structural-alpha-stage-final-report.md#9-后续建议)

### 3.5 time\_exit 和退出层有价值，但暂缓深耕

已确认：

```text
退出层会显著影响方向 edge 的兑现质量。
```

但本阶段不继续围绕退出策略做新一轮实验。原因是当前主任务仍是确认结构入口和风险空间是否有研究价值，而不是过早进入止盈 / 时间退出优化。

证据来源：

- [价值区深耕摘要：time\_exit 与 POC 兑现](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/value-area-deepening-summary.md#5-time_exit-与-poc-兑现)
- [阶段结题报告：退出策略](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/structural-alpha-stage-final-report.md#61-退出策略)

### 3.6 成交量冲击更适合作为质量标签

成交量爆发边界方向 / 胜率信息强，但赔率和左尾不支持直接作为主入口。

当前定位：

```text
边界冲击质量标签；
假突破事件强度变量；
后续辅助过滤候选。
```

证据来源：

- [随机对照实验摘要：高胜率结构的问题是赔率和左尾](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/random-baseline-experiment-summary.md#43-高胜率结构的问题是赔率和左尾)
- [阶段结题报告：成交量质量标签](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/structural-alpha-stage-final-report.md#62-成交量质量标签)

## 4. 当前暂缓 / 不再重复的方向

以下方向本阶段已经有足够结论，除非下一阶段明确需要，否则不要重复铺开。

| 方向                        | 当前处理       | 证据                                                                                                                                              |
| ------------------------- | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| 广撒新结构入口                   | 暂停         | [阶段结题报告](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/structural-alpha-stage-final-report.md#8-阶段决策)                |
| 继续补完所有随机对照                | 暂缓         | [归档 README：暂缓方向](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/README.md#6-暂缓方向)                                     |
| 主动止盈 / 分段目标 / MFE 回撤退出    | 暂缓，作为后续线索  | [价值区深耕摘要](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/value-area-deepening-summary.md#5-time_exit-与-poc-兑现)        |
| Initial Balance 重新实现      | 暂缓         | [随机对照摘要：未完成项](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/random-baseline-experiment-summary.md#2-已完成随机对照)         |
| 小时流动性当前方向                 | 暂停，可反向诊断   | [随机对照摘要：小时流动性](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/random-baseline-experiment-summary.md#44-小时流动性扫单当前方向暂停) |
| 低波再启动入口                   | 暂停，交易机会不足  | [随机对照摘要：结果矩阵](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/random-baseline-experiment-summary.md#3-横向结果矩阵)          |
| rolling value area 入口随机对照 | 暂缓，应改为状态分桶 | [结题报告：结构路线结论矩阵](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/structural-alpha-stage-final-report.md#4-结构路线结论矩阵)     |

## 5. 下一阶段待验证

下一阶段建议围绕价值区主线补证，而不是继续寻找新入口。

优先问题：

### 5.1 账户风险预算

需要验证：

```text
严格失败边界和实际止损边界，
在合约乘数、最小手数、滑点、跳空和 force_flat 后，
是否仍能控制在 2%~3% 单次账户风险内。
```

依据：

- [阶段结题报告：后续建议](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/structural-alpha-stage-final-report.md#9-后续建议)
- [长期框架](../roadmap/strategy-research-framework.md)

### 5.2 品种适配

需要验证：

```text
DCE.m 与 SR 的机制差异是否可解释、可规则化；
是否存在适合价值区回归的品种类型；
哪些品种应排除。
```

依据：

- [价值区深耕摘要：机制诊断](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/value-area-deepening-summary.md#4-机制诊断)

### 5.3 重新接受深度的波动归一

当前 `2~3 ticks` 不能直接视为最终参数。

后续应测试：

```text
reaccept_depth >= x * ATR；
reaccept_depth >= y% * previous_value_area_width；
reaccept_close_position 位于价值区内侧某个分位。
```

依据：

- [价值区深耕摘要：深度重新接受](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/value-area-deepening-summary.md#3-深度重新接受)

### 5.4 尾部风险和成本空间

需要验证：

```text
最大单笔亏损；
最大连续亏损；
最差亏损簇；
force_flat / stop_loss 左尾；
成本 / 平均盈利；
滑点上升后的安全边际。
```

依据：

- [阶段结题报告：对原短期计划的回答](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/structural-alpha-stage-final-report.md#7-对原短期计划的回答)

### 5.5 成交量冲击作为质量标签

不作为独立入口，后续可验证：

```text
成交量冲击是否改善价值区重新接受的接受质量；
是否降低左尾；
是否提高 POC 兑现概率。
```

依据：

- [阶段结题报告：成交量质量标签](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/structural-alpha-stage-final-report.md#62-成交量质量标签)

## 6. 当前文档地图

| 目的           | 文档                                                                                                                                                        |
| ------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 当前状态入口       | 本文件                                                                                                                                                       |
| 当前研究目录说明     | [README.md](./README.md)                                                                                                                                  |
| 上一阶段归档入口     | [结构型 Alpha 随机对照阶段归档 README](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/README.md)                                           |
| 上一阶段结题报告     | [structural-alpha-stage-final-report.md](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/structural-alpha-stage-final-report.md) |
| 随机对照摘要       | [random-baseline-experiment-summary.md](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/random-baseline-experiment-summary.md)   |
| 价值区深耕摘要      | [value-area-deepening-summary.md](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/value-area-deepening-summary.md)               |
| 原始 roadmap   | [raw-roadmap](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/raw-roadmap/README.md)                                             |
| 原始 workbench | [raw-workbench](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/raw-workbench/README.md)                                         |

## 7. 给 AI 的工作规则

后续 AI 接手时：

1. 先读本文件；
2. 再读 [上一阶段归档 README](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/README.md)；
3. 不要从 `raw-workbench` 开始理解阶段结论；
4. 不要重复铺开随机对照，除非用户明确要求做覆盖审计；
5. 不要继续广撒新入口；
6. 新实验过程写入 `docs/workbench`；
7. 若发现回测、数据、vnpy 成交配对、成本口径问题，先写入 `docs/issues` 并暂停受影响实验；
8. 阶段稳定后，再归档到 `docs/archive/strategy-research`。

## 8. 当前状态

当前状态：

```text
上一阶段已结题；
当前活跃主线等待新一阶段计划；
建议下一阶段围绕价值区主线做账户风险预算、品种适配和尾部风险补证。
```

