# value_area_reacceptance R12：基于 diagnostics_json 的 POC 标签分桶复验

> 类型：Workbench / 实验报告
> 状态：已完成
> 日期：2026-07-01
> 阶段规划：[value-area-reacceptance-stage-plan.md](./value-area-reacceptance-stage-plan.md)
> 上一轮报告：[value-area-reacceptance-r11-poc-quality-diagnostics.md](./value-area-reacceptance-r11-poc-quality-diagnostics.md)

## 1. 实验问题

R9 用临时脚本从 DB / CSV 事后重算 POC 质量标签，发现最有解释力的是：

```text
POC edge distance
current-day acceptance migration
```

R11 已把这些标签写入策略运行时 diagnostics，并由 clearing 透传到 `trade_clearings.diagnostics_json`。

本轮验证：

```text
不再依赖临时 profile 重算，
直接基于 diagnostics_json 做标签分桶，
看 R9 的结论是否能复现。
```

## 2. 过程修正

本轮第一版重跑 444~449 后发现：

```text
POC edge / migration 能复现，
但 local_band / multi_modal / close-vs-range divergence 全部塌缩成默认值。
```

原因是 R11 的运行时 diagnostics 只保留了前日 close-profile，未保留前日 range-profile；profile 形态类标签在运行时无法完整计算。

本轮已修正策略运行时结构快照：

```text
ValueAreaLevels.profile        = previous session close-profile
ValueAreaLevels.range_profile  = previous session range-profile
```

之后重跑 450~455，并以 450~455 作为本报告有效样本。

## 3. 回测样本

| id | symbol | ticks | total_trades | total_return | total_net_pnl | max_drawdown | status |
|---:|---|---:|---:|---:|---:|---:|---|
| 450 | DCE.m2601 | 2 | 12 | 3.5168% | 3516.800 | -480.000 | success |
| 451 | DCE.m2601 | 3 | 10 | 2.3928% | 2392.800 | -480.000 | success |
| 452 | CZCE.SR601 | 2 | 18 | 0.2134% | 213.400 | -1040.000 | success |
| 453 | CZCE.SR601 | 3 | 12 | 0.8828% | 882.800 | -400.000 | success |
| 454 | SHFE.rb2601 | 2 | 16 | -3.3142% | -3314.180 | -3990.000 | success |
| 455 | SHFE.rb2601 | 3 | 14 | -1.8014% | -1801.414 | -2370.000 | success |

说明：交易信号与 R9 / R10 主线一致；本轮收益变化不是重点，重点是 diagnostics 字段可复验。

## 4. 全样本标签分桶

### 4.1 POC edge bucket

| bucket | n | win_pct | tp_pct | poc_hit_pct | net_pnl | avg_pnl |
|---|---:|---:|---:|---:|---:|---:|
| central | 8 | 87.5% | 50.0% | 50.0% | 6498.424 | 812.303 |
| mid_edge | 17 | 52.9% | 41.2% | 41.2% | 4256.566 | 250.386 |
| edge | 16 | 12.5% | 6.2% | 6.2% | -8864.784 | -554.049 |

R9 结论复现：`edge` 是最明显风险桶；`central` 显著更强。

### 4.2 Current acceptance migration bucket

| bucket | n | win_pct | tp_pct | poc_hit_pct | net_pnl | avg_pnl |
|---|---:|---:|---:|---:|---:|---:|
| near_poc | 6 | 100.0% | 33.3% | 33.3% | 3416.232 | 569.372 |
| mid | 27 | 40.7% | 37.0% | 37.0% | 1928.022 | 71.408 |
| away | 8 | 12.5% | 0.0% | 0.0% | -3454.048 | -431.756 |

R9 方向复现：`away` 是明显风险桶。`near_poc` 胜率最好，但样本少，且 tp_pct 不一定最高；它更像“旧 POC 仍未完全失效”的标签，而不是充分获利条件。

### 4.3 Local band bucket

| bucket | n | win_pct | tp_pct | poc_hit_pct | net_pnl | avg_pnl |
|---|---:|---:|---:|---:|---:|---:|
| medium | 5 | 60.0% | 60.0% | 60.0% | 1193.800 | 238.760 |
| tight | 36 | 41.7% | 25.0% | 25.0% | 696.406 | 19.345 |

local band 有一定提示作用，但样本集中在 `tight`，`medium` 样本太少，暂不适合硬过滤。

### 4.4 Multi-modal profile

| bucket | n | win_pct | tp_pct | poc_hit_pct | net_pnl | avg_pnl |
|---|---:|---:|---:|---:|---:|---:|
| True | 30 | 36.7% | 26.7% | 26.7% | 1727.498 | 57.583 |
| False | 11 | 63.6% | 36.4% | 36.4% | 162.708 | 14.792 |

multi-modal 为 True 时胜率和 POC 命中率更低，但净收益仍为正，说明它是警示标签，不是单独硬过滤条件。

### 4.5 Close-range POC divergence bucket

| bucket | n | win_pct | tp_pct | poc_hit_pct | net_pnl | avg_pnl |
|---|---:|---:|---:|---:|---:|---:|
| medium | 23 | 47.8% | 26.1% | 26.1% | 3448.320 | 149.927 |
| high | 3 | 33.3% | 0.0% | 0.0% | -586.400 | -195.467 |
| low | 15 | 40.0% | 40.0% | 40.0% | -971.714 | -64.781 |

该结果继续支持 R8 / R9 判断：close-vs-range divergence 不能机械使用。`low` 并不一定好，`medium` 反而净收益最好；说明 close-profile POC 与 range-profile POC 接近，不等于目标更可兑现。

## 5. 分品种关键复验

### 5.1 DCE.m2601

| key | bucket | n | win_pct | tp_pct | net_pnl |
|---|---|---:|---:|---:|---:|
| poc_edge_bucket | central | 3 | 100.0% | 66.7% | 6007.200 |
| poc_edge_bucket | mid_edge | 6 | 33.3% | 33.3% | 619.200 |
| poc_edge_bucket | edge | 2 | 0.0% | 0.0% | -716.800 |
| migration_bucket | mid | 9 | 55.6% | 44.4% | 6626.400 |
| migration_bucket | away | 2 | 0.0% | 0.0% | -716.800 |

DCE.m 的主线解释非常清楚：`central` 明显最好，`edge / away` 明显失败。

### 5.2 CZCE.SR601

| key | bucket | n | win_pct | tp_pct | net_pnl |
|---|---|---:|---:|---:|---:|
| poc_edge_bucket | mid_edge | 5 | 80.0% | 40.0% | 2221.600 |
| poc_edge_bucket | central | 2 | 100.0% | 0.0% | 690.800 |
| poc_edge_bucket | edge | 8 | 25.0% | 12.5% | -1816.200 |
| migration_bucket | near_poc | 4 | 100.0% | 0.0% | 1993.200 |
| migration_bucket | mid | 8 | 37.5% | 37.5% | -310.600 |
| migration_bucket | away | 3 | 33.3% | 0.0% | -586.400 |

SR 的标签能解释明显坏样本，但不能单独解决成本/目标兑现问题。`near_poc` 有正反馈，但 tp_pct 为 0，说明它可能更像“失败概率下降”，而不是“更容易打到 POC”。

### 5.3 SHFE.rb2601

| key | bucket | n | win_pct | tp_pct | net_pnl |
|---|---|---:|---:|---:|---:|
| poc_edge_bucket | mid_edge | 6 | 50.0% | 50.0% | 1415.766 |
| poc_edge_bucket | central | 3 | 66.7% | 66.7% | -199.576 |
| poc_edge_bucket | edge | 6 | 0.0% | 0.0% | -6331.784 |
| migration_bucket | near_poc | 2 | 100.0% | 100.0% | 1423.032 |
| migration_bucket | away | 3 | 0.0% | 0.0% | -2150.848 |
| migration_bucket | mid | 10 | 30.0% | 30.0% | -4387.778 |

rb 的 `edge` 和 `away` 仍然极差，但 `central` 并没有保证盈利。该品种继续作为负面对照：POC 标签能识别部分风险，但不能修复品种级左尾问题。

## 6. 与 R9 的关系

R12 复现了 R9 最重要的结论：

```text
POC edge distance 与 current-day acceptance migration 是当前最有解释力的两个标签。
```

其中：

```text
POC edge = edge
current acceptance migration = away
```

都表现为明显风险桶。

但 R12 也进一步修正理解：

```text
central / near_poc 不是充分入场条件，
它们只是说明 POC 尚有可能作为短期可兑现锚；
是否值得交易，还要同时看失败边界、target_to_va、成本和品种左尾。
```

profile 形态类标签仍应作为诊断/警示：

```text
local band、multi-modal、close-vs-range divergence
目前不适合作为独立硬过滤器。
```

## 7. 阶段结论

R12 完成了从“临时脚本事后重算”到“运行时 diagnostics 可复验”的闭环：

```text
R9 的核心分桶结论可以直接通过 trade_clearings.diagnostics_json 复现。
```

这说明后续可以把 POC 质量标签作为标准诊断字段继续扩大样本。

当前不建议立刻做硬过滤；更合理的下一步是：

```text
R13：组合标签诊断。
```

候选组合：

```text
1. 排除 edge + away 的坏结构；
2. central/mid_edge 且 migration 非 away；
3. 在上述组合内再观察 target_to_va、raw_rr、holding path；
4. 分品种检查是否只对 DCE.m 有稳定意义。
```
