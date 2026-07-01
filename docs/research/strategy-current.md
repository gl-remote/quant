# 策略当前研究进度

> 类型：Research / 当前策略研究状态
> 状态：活跃 / 当前样本形成 1m 候选，等待扩大样本复验
> 最近更新：2026-07-01
> 最新阶段归档：[value_area_reacceptance POC / VA 质量诊断阶段归档](../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/value-area-reacceptance-quality-summary.md)
> 长期框架：[策略长期共识：共识价格区间下的账户风险结构塑形框架](../roadmap/strategy-research-framework.md)

## 1. 当前一句话结论

```text
当前最值得继续的主线仍是 value_area_reacceptance。

R22 修正 actual RR 口径后，旧 5m POC 单点主线被降级；
当前样本内最强候选转为：
1m + m/SR + A4_ratio_80 + actual RR=0.8 + min_reaccept_ticks=2/3。
```

边界：

```text
该结论不包含 SHFE.rb；
不代表所有 1m 设置都优于 5m；
不是最终上线规则；
下一步必须扩大样本复验。
```

## 2. 当前主题

| 主题 | 状态 | 文档 |
| --- | --- | --- |
| value_area_reacceptance | 主线 / 当前样本形成 1m 候选 / 等待扩样复验 | [value-area-reacceptance.md](./themes/value-area-reacceptance.md) |

当前候选摘要：

```text
value_area_reacceptance
+ 1m execution
+ previous-day 5m close-profile POC / VA
+ min_reaccept_ticks 2 / 3
+ A4_ratio_80 near-POC target
+ actual RR >= 0.8
+ no-rb: DCE.m / CZCE.SR only
```

当前候选参数：

```text
execution period = 1m
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
min_reaccept_ticks = 2 / 3
min_reaccept_va_width_ratio = 0
min_target_ticks = 8
min_price_raw_rr = 0.8  # actual RR 口径
symbols = DCE.m / CZCE.SR
exclude = SHFE.rb
```

详细定义、统计结果、分品种结论和下一阶段问题见主题文件。

## 3. 当前阶段状态

最新阶段归档：

- [value_area_reacceptance POC / VA 质量诊断阶段归档](../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/value-area-reacceptance-quality-summary.md)
- [R1~R26 原始实验记录](../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/)

阶段性结论：

```text
value_area_reacceptance 的结构 alpha 雏形仍成立，
但旧 5m POC 单点主线已被降级。

策略有效性不来自“目标更远”，
而来自旧 VA 边界被快速拒绝后，
价格仍能回到一个位置合理、未失效、可兑现的 POC 附近区域。
```

关键口径修正：

```text
旧口径：
min_price_raw_rr = raw POC target distance / strict_failure distance

新口径：
min_price_raw_rr = execution target distance / actual stop distance
```

因此：

```text
R1~R21 中涉及净收益、胜率、过滤强弱的交易结论需要降级；
R22 之后的交易结论以 actual RR 口径为准。
```

## 4. 当前最重要结果

### 4.1 actual RR 校准

在 `1m + A4_no_rb` 下：

| min_price_raw_rr | n | realized_payoff | win_pct | breakeven_win_pct | expectancy_R | worst_R |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.6 | 11 | 1.368 | 63.6% | 42.2% | 0.184 | -0.540 |
| 0.7 | 10 | 1.635 | 60.0% | 37.9% | 0.197 | -0.540 |
| 0.8 | 7 | 2.951 | 71.4% | 25.3% | 0.340 | -0.240 |
| 0.9 | 5 | 3.974 | 80.0% | 20.1% | 0.396 | -0.133 |
| 1.0 | 4 | 4.897 | 75.0% | 17.0% | 0.455 | -0.133 |

当前判断：

```text
0.8 是当前样本内最平衡候选；
0.9 / 1.0 指标更漂亮，但样本过少；
0.2~0.4 可恢复交易数，但 payoff 不足。
```

### 4.2 1m vs 5m

在 m/SR、A4、actual RR=0.6~0.8 下：

| period | n | win_pct | breakeven_win_pct | payoff | expectancy_R | net_pnl | median_pnl | worst_R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1m | 28 | 64.3% | 37.5% | 1.669 | 0.228 | 12742 | 420 | -0.540 |
| 5m | 29 | 34.5% | 22.7% | 3.412 | 0.105 | 6080 | -266 | -0.290 |

当前判断：

```text
在 m/SR、A4 near-POC、actual RR=0.6~0.8 的候选条件下，
1m 的正期望强于 5m。
```

### 4.3 target 模式稳定性

固定 `1m + m/SR + actual RR=0.8`：

| target | n | win_pct | breakeven_win_pct | payoff | expectancy_R | net_pnl | median_pnl | worst_R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A0_poc | 10 | 60.0% | 39.6% | 1.527 | 0.175 | 3492 | 370 | -0.540 |
| A1_band_1 | 10 | 60.0% | 39.6% | 1.527 | 0.175 | 3492 | 370 | -0.540 |
| A4_ratio_80 | 7 | 71.4% | 25.3% | 2.951 | 0.340 | 4758 | 520 | -0.240 |

当前判断：

```text
A4_ratio_80 明显优于原始 POC / ±1 tick band；
主要改善来自 SR，说明 1m 优势不是 DCE.m 单独撑起。
```

## 5. POC 质量标签状态

R1~R15 中最有解释力的坏结构标签仍保留为诊断字段：

```text
edge_or_away = poc_edge_bucket == edge
            or current_acceptance_migration_bucket == away
```

但当前状态降级为：

```text
有解释力的结构诊断标签；
暂不作为真实 entry filter。
```

原因：

```text
1. R15 的强 shadow 结果来自旧 RR 口径；
2. 1m 中直接迁移 5m edge_or_away 语义不稳定；
3. actual RR + 1m 候选下仍需重新扩样复验。
```

当前不要把 `would_filter_edge_or_away` 当作真实过滤条件。

## 6. 分品种结论

当前分品种判断：

```text
DCE.m：当前 1m 候选中的强贡献品种；
SR：A4_ratio_80 后从弱正期望改善为明显正期望，是 1m 优于 5m 的关键差异；
rb：当前 1m 结构中的主要负贡献，暂时排除主候选，后续单独诊断。
```

当前不能说：

```text
rb 永久不可交易；
DCE.m / SR 已经跨样本稳定。
```

只能说：

```text
在当前样本和当前参数下，m/SR 是候选组合，rb 是负面对照。
```

## 7. 下一步优先级

优先做：

```text
1. 扩大样本复验当前 1m 候选；
2. 固定候选参数：1m + m/SR + A4_ratio_80 + actual RR=0.8 + ticks=2/3；
3. 观察 win_pct、breakeven_win_pct、realized_payoff、expectancy_R、worst_R；
4. 重点验证 SR 是否继续为正，而不是完全依赖 DCE.m；
5. 单独诊断 rb 是否存在可救子集。
```

当前不建议做：

```text
1. 不继续小样本调参；
2. 不继续切更细标签桶；
3. 不继续降低 RR 门槛；
4. 不直接采用 RR=0.9 / 1.0；
5. 不继续 MFE trailing / KDJ 阈值过滤；
6. 不直接启用 edge_or_away 真实过滤；
7. 不直接切换 range-profile 或 15m。
```

## 8. 文档地图

| 目的 | 文档 |
| --- | --- |
| 当前状态入口 | 本文件 |
| value_area_reacceptance 主题状态 | [themes/value-area-reacceptance.md](./themes/value-area-reacceptance.md) |
| 最新阶段归档 | [value_area_reacceptance POC / VA 质量诊断阶段归档](../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/value-area-reacceptance-quality-summary.md) |
| 最新阶段原始记录 | [raw-workbench](../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/) |
| R16-R24 actual RR 重整 | [value-area-reacceptance-r16-r24-1m-actual-rr-summary.md](../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r16-r24-1m-actual-rr-summary.md) |
| R25 1m vs 5m | [value-area-reacceptance-r25-1m-vs-5m-actual-rr.md](../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r25-1m-vs-5m-actual-rr.md) |
| R26 稳定性检查 | [value-area-reacceptance-r26-1m-stability-check.md](../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r26-1m-stability-check.md) |
| 上一阶段归档入口 | [结构型 Alpha 随机对照阶段归档 README](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/README.md) |
| 上一阶段结题报告 | [structural-alpha-stage-final-report.md](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/structural-alpha-stage-final-report.md) |
| 长期框架 | [strategy-research-framework.md](../roadmap/strategy-research-framework.md) |

## 9. 给 AI 的工作规则

后续 AI 接手时：

1. 先读本文件；
2. 再读 [value_area_reacceptance 主题状态](./themes/value-area-reacceptance.md)；
3. 再读 [最新阶段归档摘要](../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/value-area-reacceptance-quality-summary.md)；
4. 不要从 `raw-workbench` 开始理解阶段结论；
5. 不要重复铺开随机对照，除非用户明确要求做覆盖审计；
6. 不要继续广撒新入口；
7. 不要在当前样本上继续切更细标签桶；
8. 新实验过程写入 `docs/workbench`；
9. 若发现回测、数据、vnpy 成交配对、成本口径问题，先写入 `docs/issues` 并暂停受影响实验；
10. 阶段稳定后，再归档到 `docs/archive/strategy-research`。

## 10. 当前状态

```text
value_area_reacceptance POC / VA 质量诊断阶段已归档；
R22 actual RR 修正后，当前样本形成 1m 候选；
候选为 1m + m/SR + A4_ratio_80 + actual RR=0.8 + ticks=2/3；
不扩大样本时，不建议继续做策略发现型实验；
下一步优先扩大样本复验当前候选。
```
