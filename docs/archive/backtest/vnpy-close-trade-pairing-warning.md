# vnpy 平仓未配对警告影响成交级统计口径

> 类型：Archive / 框架缺陷记录  
> 状态：已验证 / 已归档  
> 发现日期：2026-06-29  
> 完成日期：2026-06-30  
> 发现分支：`feature/random-entry-baseline-roadmap`  
> 关联实验：结构型 Alpha 随机对照阶段  
> 相关归档：[结构型 Alpha 随机对照阶段归档](../strategy-research/2026-06-29-structural-alpha-random-baseline/README.md)  
> 修复相关提交：`dfbcb62`、`ba4cf11`  
> 相关代码：[vnpy_backtest_bridge.py](../../../workspace/strategies/bridges/vnpy_backtest_bridge.py)，[vnpy_backtest_engine.py](../../../workspace/backtest/vnpy_backtest_engine.py)，[data_utils.py](../../../workspace/backtest/data_utils.py)，[service.py](../../../workspace/clearing/service.py)

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

- [value-area r2 multiseed](../strategy-research/2026-06-29-structural-alpha-random-baseline/raw-workbench/structural-alpha-random-baseline-r2-value-area-multiseed.md)
- [value-area r4 time-exit](../strategy-research/2026-06-29-structural-alpha-random-baseline/raw-workbench/structural-alpha-deepening-r4-value-area-time-exit-realization.md)
- [prevday reacceptance](../strategy-research/2026-06-29-structural-alpha-random-baseline/raw-workbench/structural-alpha-r2-prevday-reacceptance.md)
- [low volatility restart](../strategy-research/2026-06-29-structural-alpha-random-baseline/raw-workbench/structural-alpha-r6-low-volatility-restart.md)

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

## 排查结论

问题根因不是单一策略参数，而是回测结束时仍可能存在未闭合持仓，导致成交级 FIFO 清算在缺少最终平仓成交或兜底清算记录时出现余量。

本次按双层机制处理：

1. **bridge 层结束前强制平仓**  
   在回测最后一根真实 bar 后，如果 vnpy 持仓仍非零，由 bridge 发出 `forced_flat_at_backtest_end` 系统平仓信号，并使用 synthetic liquidation bar 的最后收盘价撮合。

2. **clearing 层兜底清算**  
   如果清算阶段仍存在未消费的 open lots，则使用最后一根 K 线 close 生成 `forced_close_at_backtest_end` 清算行，保证成交级统计、MAE / MFE、exit reason 和账户流水口径闭合。

## 修复记录

| 层级 | 处理 | 相关实现 |
|------|------|----------|
| backtest data | 在真实行情尾部追加 synthetic liquidation bar，用最后 close 构造清算撮合 bar | [data_utils.py](../../../workspace/backtest/data_utils.py) |
| bridge | 在最后一根真实 bar 后检查 `self.pos`，非零则提交 `forced_flat_at_backtest_end` 平仓信号 | [vnpy_backtest_bridge.py](../../../workspace/strategies/bridges/vnpy_backtest_bridge.py) |
| engine | 将 `last_real_bar_time` 注入 bridge，并让 synthetic bar 只用于撮合、不进入策略逻辑 | [vnpy_backtest_engine.py](../../../workspace/backtest/vnpy_backtest_engine.py) |
| clearing | 对剩余 open lots 生成 `forced_close_at_backtest_end` 清算行，并标记 `exit_reason=forced_close` | [service.py](../../../workspace/clearing/service.py) |
| tests | 增加 synthetic liquidation、raw fill、partial close + forced close、forced exit reason 回归测试 | [test_vnpy_backtest_engine.py](../../../workspace/tests/backtest/test_vnpy_backtest_engine.py)，[test_service.py](../../../workspace/tests/clearing/test_service.py) |

## 验证记录

2026-06-30 验证命令：

```bash
uv run pytest workspace/tests/backtest/test_vnpy_backtest_engine.py workspace/tests/clearing/test_service.py --tb=short
```

结果：

```text
20 passed
```

覆盖项：

- synthetic liquidation bar 使用最后 close，并标记为 `is_synthetic_liquidation`；
- raw fill 解析不再在 backtest engine 中自行错误配对；
- clearing 支持 partial close 后对剩余持仓强制清算；
- forced close 行设置 `is_forced_close=true`、`forced_close_reason=forced_close_at_backtest_end`、`exit_reason=forced_close`；
- 正常 raw close fill 不再触发旧的 `平仓有余量未配对` 误报。

## 当前结论

该 issue 已按框架口径修复并验证。后续策略研究可以恢复使用修复后的成交级 clearing 指标。

注意事项：

1. 修复前已记录过该 warning 的历史实验结果，仍应按归档说明谨慎引用；
2. 若未来在有完整 bars 的正常回测中再次出现 `平仓有余量未配对`，应视为新的最小复现并另起 issue；
3. clearing 层保留 warning 是故意的：当无 K 线数据或剩余 open lots 无法兜底清算时，仍应暴露口径异常。
