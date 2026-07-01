# value_area_reacceptance POC / VA 质量诊断阶段归档

> 类型：Archive / 策略实验摘要
> 状态：已完成 / 当前样本形成 1m 候选，等待跨样本复验
> 日期：2026-07-01
> 原始记录：[`raw-workbench/`](./raw-workbench/)
> 追加记录：[`value-area-reacceptance-r16-r24-1m-actual-rr-summary.md`](./raw-workbench/value-area-reacceptance-r16-r24-1m-actual-rr-summary.md)、[`value-area-reacceptance-r25-1m-vs-5m-actual-rr.md`](./raw-workbench/value-area-reacceptance-r25-1m-vs-5m-actual-rr.md)、[`value-area-reacceptance-r26-1m-stability-check.md`](./raw-workbench/value-area-reacceptance-r26-1m-stability-check.md)
> 关联路线：[`strategy-research-framework.md`](../../../roadmap/strategy-research-framework.md)

## 1. 阶段问题

本阶段研究对象是 `value_area_reacceptance`：

```text
前日价值区边界被突破失败后，价格重新接受回价值区，
以旧 POC 或 POC 附近共识区作为短期可兑现目标。
```

阶段问题经历两次推进：

```text
R1~R15：诊断 POC / VA 质量，寻找坏结构标签；
R16~R26：修正 actual RR 口径后，重新评估 1m 微观路径是否优于 5m。
```

本阶段不是最终上线阶段。当前结论只说明：

```text
当前样本中已经形成一个 1m 候选结构，
但还没有完成跨合约、跨月份、更长历史验证。
```

## 2. 关键口径修正：actual RR

R22 发现并修正了 `min_price_raw_rr` 的口径问题。

旧口径：

```text
min_price_raw_rr = raw POC target distance / strict_failure distance
```

但固定风险预算使用的是：

```text
stop_distance = strict_failure distance × stop_widen_multiplier
```

且 near-POC / 80% target 会改变实际执行目标。因此旧口径没有把实际 target 与实际 stop 放在同一风险口径下。

R22 后修正为：

```text
actual_stop_distance = abs(stop_price - entry)
execution_target_distance = abs(execution_target - entry)
min_price_raw_rr = execution_target_distance / actual_stop_distance
```

影响：

```text
1. R1~R21 中涉及净收益、胜率、过滤强弱的交易结论需要降级；
2. 结构性观察仍可保留，例如 POC 单点偏刚性、rb 拖累、1m 路径更细；
3. R22 之后的交易结论以 actual RR 口径为准。
```

## 3. 当前候选结构

R22~R26 后的当前候选：

```text
strategy = value_area_reacceptance
execution period = 1m
profile source = previous-day 5m close-profile POC / VA
symbols = DCE.m2601 / CZCE.SR601
exclude = SHFE.rb2601
take_profit_mode = poc
target_distance_ratio = 0.8
target_band_ticks = 0
min_price_raw_rr = 0.8   # actual RR 口径
min_reaccept_ticks = 2 / 3
max_hold_bars = 60
stop_widen_multiplier = 1.5
strict_close_exit = true
max_trades_per_day = 1
min_target_ticks = 8
```

含义：

```text
用 1m 捕捉更细的 reacceptance 路径；
用 80% POC 距离兑现 near-POC；
用 actual RR=0.8 过滤小赢大亏结构；
暂时排除 rb，保留 m/SR。
```

## 4. POC / VA 定义

当前仍使用前一交易日的 5m close-profile：

```text
profile: price -> accumulated volume
```

POC：

```text
成交量最大的 price bucket；
并列时选择离 session close 更近的价格。
```

VA：

```text
从 POC 开始，按相邻 bucket 成交量贪婪扩展，
直到覆盖 value_area_ratio=70% 的成交量。
```

range-profile 作为诊断字段保留，但没有替代主线 close-profile。

阶段判断保持：

```text
close-profile POC 并非完全错误；
关键问题不是换 profile，
而是 POC 是否是可兑现目标，以及执行目标是否过于单点刚性。
```

## 5. 主要实验结论

### 5.1 R1~R15：POC 质量标签阶段

R15 主线旧口径结果：

```text
n=41
win_pct=43.9%
tp_pct=29.3%
net_pnl=1890.206
median_pnl=-171.600
worst_pnl=-1622.608
```

分品种：

```text
DCE.m2601   net_pnl=5909.600
CZCE.SR601  net_pnl=1096.200
SHFE.rb2601 net_pnl=-5115.594
```

最有解释力的 POC 质量标签：

```text
POC edge distance
current-day acceptance migration
```

组合标签：

```text
edge_or_away = poc_edge_bucket == edge
            or current_acceptance_migration_bucket == away
```

旧口径下 shadow 结果很强：

```text
raw:             n=41, win_pct=43.9%, net_pnl=1890.206
shadow_kept:     n=25, win_pct=64.0%, net_pnl=10754.990
shadow_filtered: n=16, win_pct=12.5%, net_pnl=-8864.784
```

但 R22 后需要降级为：

```text
edge_or_away 是有解释力的结构诊断标签；
不能直接作为 actual RR 口径下的最终真实过滤器；
1m 中直接迁移 5m edge_or_away 语义不稳定。
```

### 5.2 R16~R21：1m 路径探索与失败尝试

保留的结构观察：

```text
1. 1m 交易机会更多；
2. 1m 与 5m 的 entry → POC tick 尺度接近；
3. 1m 暴露出更多接近 POC 但未精确触达 POC 的路径；
4. POC 单点目标偏刚性；
5. SHFE.rb2601 在 1m 下拖累明显。
```

失败方向：

```text
简单 MFE trailing：过早切断可恢复路径；
简单 KDJ 阈值过滤：误伤高质量交易；
直接迁移 5m edge_or_away 到 1m：语义不稳定。
```

### 5.3 R23~R24：actual RR 校准

在 `1m + A4_no_rb` 下扫描 actual RR。

关键结果：

| min_price_raw_rr | n | realized_payoff | win_pct | breakeven_win_pct | expectancy_R | worst_R |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.6 | 11 | 1.368 | 63.6% | 42.2% | 0.184 | -0.540 |
| 0.7 | 10 | 1.635 | 60.0% | 37.9% | 0.197 | -0.540 |
| 0.8 | 7 | 2.951 | 71.4% | 25.3% | 0.340 | -0.240 |
| 0.9 | 5 | 3.974 | 80.0% | 20.1% | 0.396 | -0.133 |
| 1.0 | 4 | 4.897 | 75.0% | 17.0% | 0.455 | -0.133 |

判断：

```text
0.2~0.4 能恢复交易数，但 payoff 过低；
0.9~1.0 指标漂亮但样本过少；
0.8 是当前样本内最平衡候选。
```

### 5.4 R25：actual RR 口径下 1m vs 5m

在 m/SR、A4、actual RR=0.6~0.8 下重新比较 1m 与 5m。

| period | n | win_pct | breakeven_win_pct | payoff | expectancy_R | net_pnl | median_pnl | worst_R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1m | 28 | 64.3% | 37.5% | 1.669 | 0.228 | 12742 | 420 | -0.540 |
| 5m | 29 | 34.5% | 22.7% | 3.412 | 0.105 | 6080 | -266 | -0.290 |

结论：

```text
在 m/SR、A4 near-POC、actual RR=0.6~0.8 的候选条件下，
1m 的正期望强于 5m。
```

边界：

```text
该结论不包含 rb；
不代表所有 1m 设置优于 5m；
样本仍小，必须扩样复验。
```

### 5.5 R26：1m 候选稳定性检查

固定：

```text
1m + m/SR + actual RR=0.8
```

比较 target 模式：

| target | n | win_pct | breakeven_win_pct | payoff | expectancy_R | net_pnl | median_pnl | worst_R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A0_poc | 10 | 60.0% | 39.6% | 1.527 | 0.175 | 3492 | 370 | -0.540 |
| A1_band_1 | 10 | 60.0% | 39.6% | 1.527 | 0.175 | 3492 | 370 | -0.540 |
| A4_ratio_80 | 7 | 71.4% | 25.3% | 2.951 | 0.340 | 4758 | 520 | -0.240 |

结论：

```text
A4_ratio_80 明显优于原始 POC / ±1 tick band；
主要改善来自 SR，说明 1m 优势不是 DCE.m 单独撑起；
min_reaccept_ticks=2/3 均为正，但 3 ticks 样本过少，不建议单独收窄。
```

## 6. 当前阶段判断

本阶段最新结论：

```text
value_area_reacceptance 的结构 alpha 雏形仍成立，
但旧 5m POC 单点主线已被降级。

在修正 actual RR 后，当前样本内最强候选转为：
1m + m/SR + A4_ratio_80 + actual RR=0.8 + min_reaccept_ticks=2/3。
```

更精确地说：

```text
该策略显示出“更短周期更可靠”的倾向，
但只在 near-POC、actual RR、排除 rb 的候选条件下成立。
```

当前不能说：

```text
1m 已经是可上线主线；
rb 永久不可交易；
0.8 是全局最优 RR；
edge_or_away 已经可以真实过滤。
```

当前可以说：

```text
1. POC 单点过刚性，80% POC 距离更适合作为 1m 执行目标；
2. actual RR 过滤是必要口径，低 RR 会恢复交易数但削弱 payoff；
3. m/SR 在 1m A4 + RR=0.8 下都呈正期望；
4. rb 在当前 1m 结构中是主要负贡献，应单独诊断；
5. 不扩大样本时，继续调参的边际价值已很低。
```

## 7. 保留与暂缓

### 7.1 保留

保留策略代码：

```text
workspace/strategies/value_area_reacceptance_strategy.py
```

保留关键参数能力：

```text
target_distance_ratio
target_band_ticks
min_price_raw_rr  # actual RR 口径
would_filter_edge_or_away
```

### 7.2 暂缓

| 方向 | 当前处理 | 原因 |
| --- | --- | --- |
| 继续小样本调参 | 暂停 | R26 后稳定性检查已足够，继续切桶易过拟合 |
| MFE trailing | 暂缓 | 未改善核心失败，且压缩右尾 |
| KDJ 阈值过滤 | 暂缓 | 误伤高质量样本 |
| 继续降低 RR | 暂缓 | 只恢复交易数，payoff 不足 |
| RR 0.9 / 1.0 | 暂缓 | 样本过少 |
| rb 混入主候选 | 暂缓 | rb 是当前主要负贡献 |
| edge_or_away 真实过滤 | 暂缓 | 旧口径下强，actual RR + 1m 下仍需复验 |

## 8. 下一阶段最小方案

下一步不应继续在当前小样本上调参，而应扩样验证当前候选。

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

若扩样通过，再考虑整理为正式候选策略；若扩样失败，则 1m 仍降级为结构诊断和执行层研究材料。

## 9. 原始记录

早期原始记录：

```text
raw-workbench/value-area-reacceptance-r1-risk-budget.md
...
raw-workbench/value-area-reacceptance-r15-shadow-filter.md
```

追加记录：

```text
raw-workbench/value-area-reacceptance-r16-r24-1m-actual-rr-summary.md
raw-workbench/value-area-reacceptance-r25-1m-vs-5m-actual-rr.md
raw-workbench/value-area-reacceptance-r26-1m-stability-check.md
```
