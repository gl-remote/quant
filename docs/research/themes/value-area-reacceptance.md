# value_area_reacceptance 主题研究现状

> 类型：Research / 主题状态
> 状态：活跃 / 当前样本形成 1m 候选，等待扩大样本复验
> 最近更新：2026-07-01
> 最新阶段归档：[value_area_reacceptance POC / VA 质量诊断阶段归档](../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/value-area-reacceptance-quality-summary.md)
> 原始记录：[R1~R15 raw-workbench](../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/)
> 追加记录：[R16-R24 actual RR](../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r16-r24-1m-actual-rr-summary.md)、[R25 1m vs 5m](../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r25-1m-vs-5m-actual-rr.md)、[R26 稳定性检查](../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r26-1m-stability-check.md)
> 返回总入口：[strategy-current.md](../strategy-current.md)

## 1. 主题一句话结论

```text
value_area_reacceptance 的结构 alpha 雏形仍成立，
但旧 5m POC 单点主线已被降级。

R22 修正 actual RR 口径后，当前样本内最强候选转为：
1m + m/SR + A4_ratio_80 + actual RR=0.8 + min_reaccept_ticks=2/3。
```

更精确地说：

```text
该策略显示出“更短周期更可靠”的倾向，
但只在 near-POC、actual RR、排除 rb 的候选条件下成立；
当前仍需跨合约、跨月份、更长历史复验。
```

## 2. 当前候选结构

当前候选版本：

```text
value_area_reacceptance
+ 1m execution
+ previous-day 5m close-profile POC / VA
+ min_reaccept_ticks 2 / 3
+ A4_ratio_80 near-POC target
+ actual RR >= 0.8
+ no-rb: DCE.m / CZCE.SR only
```

候选参数：

```text
strategy = value_area_reacceptance
engine = vnpy
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

当前候选不是最终上线规则。它是下一阶段扩样验证对象。

## 3. 关键口径：actual RR

R22 修正了 `min_price_raw_rr` 的含义。

旧口径：

```text
raw POC target distance / strict_failure distance
```

问题：

```text
固定风险预算使用 stop_distance = strict_distance × stop_widen_multiplier；
near-POC 又会改变实际执行 target；
旧口径没有用实际 target 与实际 stop 的同一风险口径。
```

当前口径：

```text
actual_stop_distance = abs(stop_price - entry)
execution_target_distance = abs(execution_target - entry)
min_price_raw_rr = execution_target_distance / actual_stop_distance
```

因此：

```text
R1~R21 中涉及净收益、胜率、过滤强弱的交易结论需要降级；
R22 之后的交易结论以 actual RR 口径为准。
```

## 4. 当前交易结构

交易结构：

```text
前日 VAL 下破失败后重新接受回价值区内 → 做多；
前日 VAH 上破失败后重新接受回价值区内 → 做空；
等待 1m 收盘价进入价值区内侧 2~3 ticks；
使用实际执行 target / 实际 stop distance >= 0.8 做入场前 RR 过滤；
目标不是精确 POC 单点，而是 entry → POC 距离的 80%。
```

当前理解：

```text
策略有效性不来自“目标更远”，
而来自旧 VA 边界被快速拒绝后，
价格仍能回到一个位置合理、未失效、可兑现的 POC 附近区域。
```

## 5. POC / VA 当前定义

当前仍使用前一交易日的 5m close-profile：

```text
profile: price -> accumulated volume
```

POC：

```text
成交量最大的 price bucket；
并列时选择离 session close 更近的价格。
```

VAH / VAL：

```text
从 POC 开始，按相邻 bucket 成交量贪婪扩展，
直到覆盖 value_area_ratio=70% 的成交量。
```

range-profile 同时作为诊断字段保留，但没有替代主线 close-profile。

当前判断：

```text
close-profile POC 并非完全错误；
关键问题不是换 profile，
而是 POC 是否是可兑现目标，以及执行目标是否过于单点刚性。
```

## 6. 当前最重要结果

### 6.1 actual RR 校准

在 `1m + A4_no_rb` 下：

| min_price_raw_rr | n | realized_payoff | win_pct | breakeven_win_pct | expectancy_R | worst_R |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.6 | 11 | 1.368 | 63.6% | 42.2% | 0.184 | -0.540 |
| 0.7 | 10 | 1.635 | 60.0% | 37.9% | 0.197 | -0.540 |
| 0.8 | 7 | 2.951 | 71.4% | 25.3% | 0.340 | -0.240 |
| 0.9 | 5 | 3.974 | 80.0% | 20.1% | 0.396 | -0.133 |
| 1.0 | 4 | 4.897 | 75.0% | 17.0% | 0.455 | -0.133 |

判断：

```text
0.8 是当前样本内最平衡候选；
0.9 / 1.0 指标更漂亮，但样本过少；
0.2~0.4 可恢复交易数，但 payoff 不足。
```

### 6.2 1m vs 5m

在 m/SR、A4、actual RR=0.6~0.8 下：

| period | n | win_pct | breakeven_win_pct | payoff | expectancy_R | net_pnl | median_pnl | worst_R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1m | 28 | 64.3% | 37.5% | 1.669 | 0.228 | 12742 | 420 | -0.540 |
| 5m | 29 | 34.5% | 22.7% | 3.412 | 0.105 | 6080 | -266 | -0.290 |

判断：

```text
在 m/SR、A4 near-POC、actual RR=0.6~0.8 的候选条件下，
1m 的正期望强于 5m。
```

### 6.3 target 模式稳定性

固定 `1m + m/SR + actual RR=0.8`：

| target | n | win_pct | breakeven_win_pct | payoff | expectancy_R | net_pnl | median_pnl | worst_R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A0_poc | 10 | 60.0% | 39.6% | 1.527 | 0.175 | 3492 | 370 | -0.540 |
| A1_band_1 | 10 | 60.0% | 39.6% | 1.527 | 0.175 | 3492 | 370 | -0.540 |
| A4_ratio_80 | 7 | 71.4% | 25.3% | 2.951 | 0.340 | 4758 | 520 | -0.240 |

判断：

```text
A4_ratio_80 明显优于原始 POC / ±1 tick band；
主要改善来自 SR，说明 1m 优势不是 DCE.m 单独撑起。
```

## 7. POC 质量标签状态

R1~R15 中最有解释力的坏结构标签仍保留为诊断字段：

```text
edge_or_away = poc_edge_bucket == edge
            or current_acceptance_migration_bucket == away
```

但状态降级为：

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

## 8. 分品种结论

当前分品种判断：

```text
DCE.m：当前 1m 候选中的强贡献品种；
SR：A4_ratio_80 后从弱正期望改善为明显正期望，是 1m 优于 5m 的关键差异；
rb：当前 1m 结构中的主要负贡献，暂时排除主候选，后续单独诊断。
```

当前不能说：

```text
rb 永久不可交易；
DCE.m / SR 已经跨样本稳定；
```

只能说：

```text
在当前样本和当前参数下，m/SR 是候选组合，rb 是负面对照。
```

## 9. 当前不建议继续的方向

| 方向 | 当前处理 | 原因 |
| --- | --- | --- |
| 继续小样本调参 | 暂停 | R26 后稳定性检查已足够，继续切桶易过拟合 |
| MFE trailing | 暂缓 | 未改善核心失败，且压缩右尾 |
| KDJ 阈值过滤 | 暂缓 | 误伤高质量样本 |
| 继续降低 RR | 暂缓 | 只恢复交易数，payoff 不足 |
| RR 0.9 / 1.0 | 暂缓 | 样本过少 |
| rb 混入主候选 | 暂缓 | rb 是当前主要负贡献 |
| edge_or_away 真实过滤 | 暂缓 | 旧口径下强，actual RR + 1m 下仍需复验 |
| 直接切换 range-profile | 暂缓 | close-profile 仍有解释力，当前问题不是 profile 替换 |
| 直接切换 15m | 暂缓 | 15m 会让信号变慢和模糊 |

## 10. 下一阶段待验证

下一步应扩样验证当前候选，而不是继续当前小样本调参。

固定候选：

```text
period = 1m
symbols = DCE.m / CZCE.SR
exclude = SHFE.rb
target_distance_ratio = 0.8
target_band_ticks = 0
min_price_raw_rr = 0.8
min_reaccept_ticks = 2 / 3
```

扩样观察指标：

```text
n
win_pct
breakeven_win_pct
realized_payoff
expectancy_R
net_pnl
median_pnl
worst_R
loss_ge_0.5R
分品种稳定性，尤其 SR 是否继续为正
```

通过标准：

```text
1. win_pct 仍显著高于 breakeven_win_pct；
2. realized_payoff 仍 > 1.5，最好 > 2；
3. expectancy_R 仍为正；
4. SR 仍为正，而不是完全依赖 DCE.m；
5. worst_R / loss_ge_0.5R 不重新恶化。
```

如果扩样通过，再考虑整理为正式候选策略；如果扩样失败，则 1m 仍降级为结构诊断和执行层研究材料。

## 11. 关联文档

| 目的 | 文档 |
| --- | --- |
| 总入口 | [strategy-current.md](../strategy-current.md) |
| 最新阶段归档 | [value_area_reacceptance POC / VA 质量诊断阶段归档](../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/value-area-reacceptance-quality-summary.md) |
| R16-R24 actual RR 重整 | [value-area-reacceptance-r16-r24-1m-actual-rr-summary.md](../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r16-r24-1m-actual-rr-summary.md) |
| R25 1m vs 5m | [value-area-reacceptance-r25-1m-vs-5m-actual-rr.md](../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r25-1m-vs-5m-actual-rr.md) |
| R26 稳定性检查 | [value-area-reacceptance-r26-1m-stability-check.md](../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r26-1m-stability-check.md) |
| R1~R15 原始记录 | [raw-workbench](../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/) |
