# value_area_reacceptance R13：POC 质量组合标签诊断

> 类型：Workbench / 实验报告
> 状态：已完成
> 日期：2026-07-01
> 阶段规划：[value-area-reacceptance-stage-plan.md](./value-area-reacceptance-stage-plan.md)
> 上一轮报告：[value-area-reacceptance-r12-diagnostics-bucket-recheck.md](./value-area-reacceptance-r12-diagnostics-bucket-recheck.md)

## 1. 实验问题

R12 已确认：

```text
POC edge = edge
current acceptance migration = away
```

是明显风险桶。

本轮不改变交易信号，直接基于 R12 生成的 `trade_clearings.diagnostics_json` 做组合标签诊断，回答：

```text
排除 edge / away 这类坏结构后，收益和左尾是否改善？
central / mid_edge 且 migration 非 away 是否可以作为后续过滤候选？
```

## 2. 数据来源

沿用 R12 有效样本：

```text
DCE.m2601: 450 / 451
CZCE.SR601: 452 / 453
SHFE.rb2601: 454 / 455
```

共 41 笔清算样本，直接读取：

```text
trade_clearings.diagnostics_json
```

不重新计算 profile，不改变策略信号。

## 3. 组合标签定义

### 3.1 bad=edge_or_away

```text
bad = poc_edge_bucket == edge
   or current_acceptance_migration_bucket == away
```

含义：

```text
旧 POC 靠近前日 VA 边缘，或当前短期接受区已经远离旧 POC。
```

这类样本代表旧 POC 作为短期可兑现共识锚的质量较差。

### 3.2 not_bad

```text
not_bad = not bad
```

等价于：

```text
poc_edge_bucket in {central, mid_edge}
and migration_bucket != away
```

含义：旧 POC 至少没有明显失效。

### 3.3 central_and_not_away / mid_edge_and_not_away

用于区分：

```text
POC 更居中是否比 mid_edge 更稳定？
```

## 4. 组合标签总览

| bucket | n | win_pct | tp_pct | net_pnl | avg_pnl | median_pnl | worst_pnl | loss_sum | left_tail_1000 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| all | 41 | 43.9% | 29.3% | 1890.206 | 46.103 | -171.600 | -1622.608 | -13358.154 | 4 |
| bad=edge_or_away | 16 | 12.5% | 6.2% | -8864.784 | -554.049 | -455.300 | -1550.620 | -9157.184 | 3 |
| not_bad=not(edge_or_away) | 25 | 64.0% | 44.0% | 10754.990 | 430.200 | 518.096 | -1622.608 | -4200.970 | 1 |
| central_or_mid_edge_and_not_away | 25 | 64.0% | 44.0% | 10754.990 | 430.200 | 518.096 | -1622.608 | -4200.970 | 1 |
| central_and_not_away | 8 | 87.5% | 50.0% | 6498.424 | 812.303 | 711.516 | -1622.608 | -1622.608 | 1 |
| mid_edge_and_not_away | 17 | 52.9% | 41.2% | 4256.566 | 250.386 | 455.572 | -708.800 | -2578.362 | 0 |

## 5. 关键发现

### 5.1 bad=edge_or_away 是强风险组合

全样本下：

```text
all: n=41, net_pnl=1890.206, win_pct=43.9%, left_tail_1000=4
bad: n=16, net_pnl=-8864.784, win_pct=12.5%, left_tail_1000=3
not_bad: n=25, net_pnl=10754.990, win_pct=64.0%, left_tail_1000=1
```

排除 `edge_or_away` 后，胜率、tp_pct、净收益、median pnl 都明显改善，左尾数量也明显下降。

这说明组合标签不是单纯描述性字段，而是已经接近“坏结构候选过滤器”。

### 5.2 central_and_not_away 最强，但仍有左尾

```text
central_and_not_away:
n=8, win_pct=87.5%, net_pnl=6498.424, worst_pnl=-1622.608
```

该组合整体最强，但仍出现一次较大亏损，来自 SHFE.rb2601。

这说明：

```text
central + not away 不是充分条件。
```

它能说明旧 POC 质量较好，但不能解决品种左尾和失败边界问题。

### 5.3 mid_edge_and_not_away 更稳地控制左尾

```text
mid_edge_and_not_away:
n=17, win_pct=52.9%, net_pnl=4256.566, worst_pnl=-708.800, left_tail_1000=0
```

这个组合收益不如 central，但左尾更温和。

可能解释是：

```text
central 的目标空间更大，但如果当前日结构反向迁移或品种左尾发生，亏损也可能更大；
mid_edge 的目标空间较有限，但更少出现极端亏损。
```

这需要后续结合 holding path 和品种特性确认。

## 6. 分品种结果

| bucket | n | win_pct | tp_pct | net_pnl | avg_pnl | median_pnl | worst_pnl | loss_sum | left_tail_1000 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| CZCE.SR601:bad | 8 | 25.0% | 12.5% | -1816.200 | -227.025 | -270.200 | -486.000 | -2108.600 | 0 |
| DCE.m2601:bad | 2 | 0.0% | 0.0% | -716.800 | -358.400 | -358.400 | -358.400 | -716.800 | 0 |
| SHFE.rb2601:bad | 6 | 0.0% | 0.0% | -6331.784 | -1055.297 | -915.160 | -1550.620 | -6331.784 | 3 |
| CZCE.SR601:not_bad | 7 | 85.7% | 28.6% | 2912.400 | 416.057 | 651.200 | -708.800 | -708.800 | 0 |
| DCE.m2601:not_bad | 9 | 55.6% | 44.4% | 6626.400 | 736.267 | 844.000 | -513.600 | -1464.000 | 0 |
| SHFE.rb2601:not_bad | 9 | 55.6% | 55.6% | 1216.190 | 135.132 | 455.572 | -1622.608 | -2028.170 | 1 |

分品种看，`not_bad` 对三个品种都有改善，但改善质量不同：

- DCE.m：收益主来源，结构解释最干净；
- SR：过滤坏结构后明显改善，但 tp_pct 仍偏低，说明成本/目标兑现问题仍在；
- rb：过滤后转正，但仍保留最大左尾，说明品种级左尾没有完全解决。

## 7. not_bad 内 target_to_va / raw_rr

| bucket | n | avg_target_to_va | avg_raw_rr | net_pnl | win_pct | tp_pct |
|---|---:|---:|---:|---:|---:|---:|
| target_to_va<=0.35 | 6 | 0.269 | 0.906 | 3416.232 | 100.0% | 33.3% |
| 0.35<target_to_va<=0.70 | 19 | 0.554 | 1.039 | 7338.758 | 52.6% | 47.4% |
| target_to_va>0.70 | 0 | 0.000 | 0.000 | 0.000 | 0.0% | 0.0% |
| raw_rr<1 | 13 | 0.471 | 0.683 | 4550.528 | 76.9% | 38.5% |
| raw_rr>=1 | 12 | 0.501 | 1.357 | 6204.462 | 50.0% | 50.0% |

在 `not_bad` 内，target_to_va 过大样本已经不存在；说明 edge / away 过滤本身已经移除了很多“目标过远且旧 POC 失效”的结构。

但 raw_rr 结果也提醒：

```text
raw_rr 更高不等于胜率更高；
raw_rr>=1 的 tp_pct 更高，但胜率低于 raw_rr<1。
```

这继续支持前面结论：POC / VA 提供的是“适中可兑现目标”，不是单纯更高账面 RR。

## 8. 是否适合进入过滤候选？

当前可以把 `edge_or_away` 视为过滤候选，但还不应直接固化为交易规则。

理由：

1. 样本数仍小；
2. 组合标签已明显改善结果，但存在重复样本：2 ticks / 3 ticks 会重复同一天结构；
3. `central_and_not_away` 仍有 SHFE.rb2601 左尾；
4. SR / rb 的改进不等于已经适合实盘，品种成本和尾部仍要单独判断。

更稳妥的定位是：

```text
edge_or_away = 强风险诊断标签 / 过滤候选；
central_or_mid_edge_and_not_away = 结构质量候选标签；
是否硬过滤，需要更大样本和去重日级验证。
```

## 9. 阶段结论

R13 的核心结论：

```text
POC 质量标签的组合诊断明显强于单标签解释。
```

尤其是：

```text
排除 edge_or_away 后，
全样本净收益从 1890.206 提升到 10754.990，
胜率从 43.9% 提升到 64.0%，
left_tail_1000 从 4 降到 1。
```

但这仍是诊断结论，不是最终交易规则。

下一步建议：

```text
R14：日级去重组合标签验证。
```

原因是当前 2 ticks / 3 ticks 会重复同一天结构；如果要判断标签是否真的稳定，下一步应按 trading day 去重，只保留每个 symbol/date/side 的代表样本，再看 `edge_or_away` 的解释力是否仍然成立。
