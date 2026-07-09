# value_area_reacceptance R10：VA width 归一化 reaccept 深度尝试

> 类型：Workbench / 实验报告
> 状态：已完成
> 日期：2026-06-30
> 阶段规划：[value-area-reacceptance-stage-plan.md](./value-area-reacceptance-stage-plan.md)
> 上一轮报告：[value-area-reacceptance-r9-poc-quality-tags.md](./value-area-reacceptance-r9-poc-quality-tags.md)

## 1. 实验问题

R3 显示 `min_reaccept_ticks = 2~3` 对结果非常敏感；R5~R9 又显示当前 POC / VA 定义本身存在锚点质量问题。

本轮做一轮轻量归一化尝试，回答：

```text
fixed ticks 的正反馈是否只是 VA width 的代理？
把重新接受深度改成 previous VA width 的比例后，结果是否更稳定？
```

本轮不改变 POC / VA 定义，不切换 profile，不做 Optuna，也不扩大参数搜索。

## 2. 实验实现

在策略参数中增加：

```text
min_reaccept_va_width_ratio: float = 0.0
```

重新接受深度计算改为：

```text
min_reaccept = max(
    min_reaccept_ticks * price_tick,
    min_reaccept_va_width_ratio * (VAH - VAL),
)
```

本轮为了做纯归一化对照，固定：

```text
min_reaccept_ticks = 0
min_reaccept_va_width_ratio = 0.10 / 0.15
```

因此本轮不是 fixed ticks 与 ratio 混合，而是用 `VA width * ratio` 作为重新接受进入价值区内部的最低深度。

## 3. 参数与样本

除 reaccept 深度外，其余参数沿用 R5~R9 主线：

```text
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

对照样本：

| 组别 | DCE.m2601 | CZCE.SR601 | SHFE.rb2601 |
|------|-----------|------------|-------------|
| fixed 2 ticks | 401 | 403 | 409 |
| fixed 3 ticks | 402 | 404 | 410 |
| VA width 10% | 437 | 439 | 441 |
| VA width 15% | 438 | 440 | 442 |

说明：`backtests.total_trades` 是成交记录数，`trade_clearings` 是完整开平清算笔数；本轮主要用清算笔数评价交易事件。

## 4. 汇总结果

| symbol | variant | backtest_id | trade_records | clearings | total_return | total_net_pnl | max_drawdown | win_pct | tp_pct |
|--------|---------|-------------|---------------|-----------|--------------|---------------|--------------|---------|--------|
| DCE.m2601 | fixed 2 ticks | 401 | 12 | 6 | 3.5168% | 3516.800 | -480.000 | 50.00% | 33.33% |
| DCE.m2601 | fixed 3 ticks | 402 | 10 | 5 | 2.3928% | 2392.800 | -480.000 | 40.00% | 40.00% |
| DCE.m2601 | VA width 10% | 437 | 12 | 6 | 2.3792% | 2379.200 | -480.000 | 50.00% | 33.33% |
| DCE.m2601 | VA width 15% | 438 | 10 | 5 | 1.4352% | 1435.200 | -300.000 | 40.00% | 40.00% |
| CZCE.SR601 | fixed 2 ticks | 403 | 18 | 9 | 0.2134% | 213.400 | -1040.000 | 55.56% | 22.22% |
| CZCE.SR601 | fixed 3 ticks | 404 | 12 | 6 | 0.8828% | 882.800 | -400.000 | 50.00% | 16.67% |
| CZCE.SR601 | VA width 10% | 439 | 16 | 8 | -0.4378% | -437.800 | -1040.000 | 50.00% | 25.00% |
| CZCE.SR601 | VA width 15% | 440 | 12 | 6 | -0.2558% | -255.800 | -700.000 | 33.33% | 33.33% |
| SHFE.rb2601 | fixed 2 ticks | 409 | 16 | 8 | -3.3142% | -3314.180 | -3990.000 | 25.00% | 25.00% |
| SHFE.rb2601 | fixed 3 ticks | 410 | 14 | 7 | -1.8014% | -1801.414 | -2370.000 | 42.86% | 42.86% |
| SHFE.rb2601 | VA width 10% | 441 | 14 | 7 | -2.0210% | -2020.992 | -2560.000 | 28.57% | 28.57% |
| SHFE.rb2601 | VA width 15% | 442 | 14 | 7 | -2.9898% | -2989.816 | -2360.000 | 28.57% | 28.57% |

## 5. 主要变化

### 5.1 DCE.m2601：归一化保留事件数，但明显压缩收益

DCE.m2601 的归一化结果没有破坏交易数量：

```text
fixed 2 ticks: 6 笔清算，net_pnl = 3516.8
VA width 10%: 6 笔清算，net_pnl = 2379.2

fixed 3 ticks: 5 笔清算，net_pnl = 2392.8
VA width 15%: 5 笔清算，net_pnl = 1435.2
```

这说明 VA width 归一化确实能生成与 2~3 ticks 相近的样本数量，但收益明显下降。

关键原因之一是：归一化深度在某些较宽 VA 日期上会把入场进一步推迟，导致 entry 更靠近 POC，目标空间被压缩。

典型例子：

```text
2025-10-22 DCE.m2601 long
fixed 2/3 ticks: entry = 2863, take_profit, net_pnl = 2581.6
VA width 10%/15%: entry = 2867, take_profit, net_pnl = 1444.0
```

该样本仍然兑现 POC，但归一化确认更深，损失了最有价值的回归空间。

### 5.2 CZCE.SR601：归一化没有改善观察样本，反而转负

CZCE.SR601 的 fixed ticks 组本来只是观察级别，但仍为正：

```text
fixed 2 ticks: net_pnl = 213.4
fixed 3 ticks: net_pnl = 882.8
```

归一化后两组都转负：

```text
VA width 10%: net_pnl = -437.8
VA width 15%: net_pnl = -255.8
```

这说明 SR 的问题不是简单的 tick 尺度不适配。归一化深度会改变样本构成，但没有把样本稳定推向更好的 POC 兑现结构。

### 5.3 SHFE.rb2601：仍然是负面对照，归一化不能修复左尾

SHFE.rb2601 归一化后仍为负：

```text
fixed 2 ticks: net_pnl = -3314.18
fixed 3 ticks: net_pnl = -1801.414
VA width 10%: net_pnl = -2020.992
VA width 15%: net_pnl = -2989.816
```

VA width 10% 相比 fixed 2 ticks 有所改善，但仍明显为负；VA width 15% 又明显变差。

这继续支持 R9 结论：rb 的问题不在于重新接受深度是否按 VA 宽度归一化，而在于 POC / VA 锚点质量和左尾结构本身不稳定。

## 6. 解释

本轮最重要的发现不是“某个 ratio 更好”，而是：

```text
VA width 归一化不能替代 POC / VA 质量判断。
```

fixed 2~3 ticks 的正反馈并不只是 VA width 的代理。原因包括：

1. **回归 POC 是短窗口事件**
   重新接受确认太深，会延迟入场，压缩 entry 到 POC 的可兑现空间。

2. **VA width 本身不等于有效噪声尺度**
   较宽 VA 可能来自多峰、迁移或历史成交密集区，而不一定代表当前日可用的接受区宽度。

3. **归一化不能识别 POC 是否仍是有效锚**
   如果旧 POC 已经失效，进入价值区更深也不能修复目标无效问题。

4. **固定 tick 可能隐含“快速重新接受”的时间语义**
   2~3 ticks 的效果可能部分来自“较早确认，保留 POC 回归空间”，而不是来自绝对深度本身。

## 7. 阶段结论

本轮暂不支持把 `min_reaccept_ticks` 直接替换为 `min_reaccept_va_width_ratio`。

更准确的结论是：

```text
reaccept 深度可以被记录为 VA width fraction，
但不应在当前阶段作为主过滤器替代 fixed ticks。
```

R10 对 R5~R9 的结论形成补充：

```text
2~3 ticks 的敏感性不是单纯尺度归一化问题；
它更像是当前 POC / VA 锚点脆弱时，
在“足够进入价值区”和“不能错过 POC 回归窗口”之间形成的经验折中。
```

因此下一步不应继续扩大 ratio 网格，而应回到 R9 的方向：

```text
先把 POC edge distance、current-day acceptance migration、local band、multi-modal、close-vs-range divergence
写入诊断 payload / clearing 统计；
用更大样本验证 POC 是否仍是短期可兑现共识锚。
```
