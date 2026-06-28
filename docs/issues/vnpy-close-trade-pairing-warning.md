# vnpy 平仓未配对警告影响成交级统计口径

> 类型：框架缺陷 / 回测链路 / 成交配对口径  
> 状态：待排查  
> 发现日期：2026-06-29  
> 发现分支：`feature/random-entry-baseline-roadmap`  
> 关联实验：结构型 Alpha 随机对照阶段  
> 相关归档：[结构型 Alpha 随机对照阶段归档](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/README.md)  
> 相关代码：[vnpy_backtest_bridge.py](../../workspace/strategies/bridges/vnpy_backtest_bridge.py)，[vnpy_backtest_engine.py](../../workspace/backtest/vnpy_backtest_engine.py)，[value_area_random_baseline_strategy.py](../../workspace/strategies/value_area_random_baseline_strategy.py)

## 背景

结构型 Alpha 随机对照阶段中，多轮实验在部分回测结果中出现：

```text
平仓有余量未配对
```

该现象主要出现在：

- 价值区 `random-direction` 随机方向基准；
- 价值区 time-exit 延长持仓到 `18/24 bars` 的部分 SR 回测；
- 早期前日高低点 SR 回测；
- 少量低波再启动对照。

相关记录：

- [value-area r2 multiseed](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/raw-workbench/structural-alpha-random-baseline-r2-value-area-multiseed.md)
- [value-area r4 time-exit](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/raw-workbench/structural-alpha-deepening-r4-value-area-time-exit-realization.md)
- [prevday reacceptance](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/raw-workbench/structural-alpha-r2-prevday-reacceptance.md)
- [low volatility restart](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/raw-workbench/structural-alpha-r6-low-volatility-restart.md)

## 现象

典型表现：

```text
平仓有余量未配对
```

在实验记录中的影响描述包括：

```text
random-direction 基准的成交配对口径需要单独复核；
SR 在 max_hold_bars >= 18 的若干回测出现 vnpy 平仓未配对警告；
后续若要正式比较 18/24 bars，需要先复核 vnpy 成交配对口径或限制跨夜 / force_flat 行为。
```

## 影响

| 影响面 | 说明 |
|--------|------|
| 成交级统计 | 可能影响 closed trades、逐笔 pnl、MAE / MFE、exit reason、亏损簇等成交级指标 |
| 随机方向基准 | `random-direction` 结果需谨慎使用，尤其是方向与目标价组合可能异常时 |
| time-exit 对照 | 长持仓、force-flat 或跨交易段退出时，可能放大配对异常 |
| 阶段结论 | 不影响价值区 `same-direction` 随机对照和 `min_reaccept_ticks=2~3` 主结论；但影响随机方向和长持仓扩展结论的严谨性 |

## 初步判断

可能原因包括：

1. 随机方向基准中，交易方向与 `target_price` / stop 组合在某些事件下不一致；
2. `force_flat`、跨交易段平仓或 vnpy 桥接层平仓方向处理导致 FIFO 配对出现余量；
3. 回测引擎持仓记录与策略层 `state.extra` 中交易状态在异常退出路径不同步；
4. 统计层对部分平仓记录的方向、数量或开平标记解释不一致。

该问题需要作为框架口径问题单独排查，不能在策略实验中直接用参数修补。

## 最小复现方向

优先复现以下两类：

```text
1. value_area_random_baseline 的 random-direction 多 seed；
2. value_area_deepening_r4 中 CZCE.SR601 + max_hold_bars = 18 / 24。
```

建议复现命令方向：

```text
uv run python scripts/tools/run_value_area_random_baseline.py ...
uv run python scripts/tools/run_value_area_deepening_r4_time_exit.py ...
```

复现时需要捕获：

- vnpy 原始成交记录；
- 桥接层发出的开平仓 action；
- 策略层 trade state；
- 最终 closed trades 配对结果；
- force-flat 时间点和持仓方向。

## 当前处理建议

1. 在修复前，实验文档中凡出现该警告的结果，只能作为方向参考；
2. `same-direction` 且无明显配对警告的结果可继续作为主要策略证据；
3. 正式比较 `random-direction`、长持仓、force-flat 效果前，必须先修复或解释该警告；
4. 修复时应增加最小回归测试，覆盖：
   - 多空随机方向；
   - target / stop 与方向组合；
   - time_exit；
   - force_flat；
   - 跨交易段退出。

## 修复记录

待补。

## 验证记录

待补。
