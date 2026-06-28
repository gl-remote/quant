# structural-alpha-r4：前日共识边界 + 成交量质量过滤

> 类型：Workbench / 策略实验记录  
> 状态：执行中  
> 创建日期：2026-06-28  
> 最后更新：2026-06-28  
> 来源规划：[策略短期研究计划：结构型 Alpha 验证](../roadmap/strategy-short-term-plan.md)  
> 研究框架：[策略长期共识：共识价格区间下的账户风险结构塑形框架](../roadmap/strategy-research-framework.md)  
> 开发分支：`experiment/structural-alpha-r4-consensus-volume-filter`  
> 开分支 hash：`8984d9d`  
> 实现提交 hash：待回填

## 1. 核心问题

上一轮 `volume_shock_boundary` 的结论是：

```text
成交量爆发 K 线边界可以客观定义，严格失败边界也清楚，
但它不能单独作为主边界提供跨品种、成本后稳定正期望。
```

本轮不再把成交量爆发作为主边界，而是回到已知共识边界：

```text
前日 high / low / close / open
→ 当日对前日 high / low 的假突破与重新接受 / 拒绝
→ 成交量爆发只作为“假突破质量”或“重新接受质量”的过滤器
```

核心问题：

```text
成交量爆发不作为主边界，
只作为前日高低点假突破重新接受 / 拒绝的质量过滤器时，
是否能减少低质量重新接受、改善 r2 的成本后结果和跨品种稳定性？
```

本轮不做：

```text
不做 Optuna
不做 Walk-Forward
不叠加趋势、均线、MACD / KDJ 等二次过滤
不引入 VAH / VAL / POC
不把 volume shock bar high / low 当作主边界
```

## 2. 实验定义

| 项目 | 定义 |
| --- | --- |
| 实验版本 | `structural-alpha-r4` |
| 策略代号 | `prevday_volume_filter` |
| 主共识价格区间 | 前一交易日 high / low / close / open |
| 质量过滤来源 | 当前 bar 相对历史均量、均振幅和实体比例的 volume shock |
| 结构来源 | Price Action / 前日高低点共识边界 / 成交冲击质量过滤 |
| 方向假设 | 下破前日 low 后重新收回做多；上破前日 high 后重新收回做空 |
| 过滤假设 | 真正有效的假突破或重新接受，应该伴随相对历史更强的成交与振幅确认 |
| 严格失败边界 | 假突破极值外加 `failure_buffer_ticks` |
| 目标止盈 | 前日区间中轴 / 昨收 / 当日开盘 / 对侧边界 / R 倍数 |
| 时间退出 | 入场后 `max_hold_bars` 或日内 `force_flat_time` |
| 入场方式 | 前日边界外触发突破状态后，收盘重新回到昨日区间内，并满足可选成交量过滤 |
| 退出方式 | 严格失败边界、主动止盈、时间退出、日内强平 |

### 2.1 多头结构

```text
已知前日 Low
→ 当日向下跌破前日 Low 至少 min_breakout_ticks
→ 收盘重新回到前日 Low 上方
→ 若启用成交量过滤，则按 stage 要求 breakout / reaccept / either 出现 shock
→ 做多
→ 严格失败边界 = 假突破低点 - failure_buffer_ticks
```

### 2.2 空头结构

```text
已知前日 High
→ 当日向上突破前日 High 至少 min_breakout_ticks
→ 收盘重新回到前日 High 下方
→ 若启用成交量过滤，则按 stage 要求 breakout / reaccept / either 出现 shock
→ 做空
→ 严格失败边界 = 假突破高点 + failure_buffer_ticks
```

### 2.3 Shock 定义

当前 bar 与之前历史均值比较，不把当前 bar 纳入均值：

```text
volume_ratio = current_volume / avg_volume(volume_lookback)
range_ratio  = current_range / avg_range(range_lookback)
body_ratio   = abs(close - open) / (high - low)
```

要求：

```text
avg_volume > 0
avg_range > 0
bar_range > 0
volume_ratio >= volume_multiplier
range_ratio >= range_multiplier
body_ratio >= min_body_ratio
```

## 3. Baseline vs Filter 对照口径

Baseline 口径：

```text
使用同一策略 prevday_volume_filter
volume_filter_enabled = false
其余参数保持与 filter 组一致
```

该口径用于隔离“成交量过滤器”本身的影响，避免策略文件、诊断字段或工程路径差异造成对照污染。

可辅助参考 r2 的 `prevday_reacceptance` 结果，但正式 r4 对照优先使用同一策略的 filter off 版本。

Filter 口径：

```text
volume_filter_enabled = true
volume_filter_stage ∈ {breakout, reaccept, either}
```

解释：

| stage | 含义 |
| --- | --- |
| `breakout` | 前日边界外假突破过程中至少有一次 shock |
| `reaccept` | 重新接受 / 拒绝的当前 bar 必须是 shock |
| `either` | breakout 或 reaccept 任一环节出现 shock 即可 |

## 4. 第一轮固定参数计划

第一轮只做固定参数诊断，不做参数搜索。

| 参数 | 初始值 | 说明 |
| --- | ---: | --- |
| `kline_period` | `1m` / `5m` | 先验证 1m，若噪声和成本过高再沿用 r2/r3 的 5m 降噪口径 |
| `volume_filter_enabled` | `false` / `true` | baseline vs filter |
| `volume_filter_stage` | `breakout` / `reaccept` / `either` | 判断 shock 应出现在假突破、重新接受还是任一阶段 |
| `volume_lookback` | `20` | 成交量历史均值窗口 |
| `volume_multiplier` | `2.0` / `2.5` | 第一轮从较宽松过滤开始，避免样本直接耗尽 |
| `range_lookback` | `20` | 振幅历史均值窗口 |
| `range_multiplier` | `1.0` / `1.2` | r4 先允许成交量作为主过滤，振幅作为质量下限 |
| `min_body_ratio` | `0.0` / `0.3` | 先允许影线型扫单，再对照实体确认 |
| `min_breakout_ticks` | `2` / `4` | 沿用 r2 的前日高低点假突破幅度对照 |
| `failure_buffer_ticks` | `1` | 严格失败边界 buffer |
| `take_profit_mode` | `mid` / `close` / `r` | 沿用 r2 的目标对照 |
| `take_profit_r` | `2.0` | R 倍数止盈对照 |
| `max_hold_bars` | `30` / `60` / `6@5m` | 日内时间退出 |
| `stop_widen_multiplier` | `1.0` / `1.5` | 严格失败与有限放宽对照 |
| `risk_per_trade` | `0.02` | 单次账户风险目标 |
| `max_position_ratio` | `0.3` | 仓位上限 |
| `max_trades_per_day` | `1` | 优先降低重复噪声和成本 |

初始测试范围：

| 项目 | 值 |
| --- | --- |
| 主品种 | `DCE.m2601` |
| 跨品种 | `CZCE.SR601`、`DCE.c2601`、`DCE.cs2601`、`SHFE.rb2601` |
| 周期 | `1m` / `5m` |
| 回测引擎 | `vnpy` |
| 模式 | `single` |
| 数据口径 | 真实收益以 `backtest_daily.net_pnl` / `backtests.total_net_pnl` 为准 |

## 5. 工程接入记录

### 5.1 第 0 轮：工程最小版本

| 项目 | 状态 | 说明 |
| --- | --- | --- |
| 独立分支 | 已完成 | `experiment/structural-alpha-r4-consensus-volume-filter` |
| 开分支 hash | 已记录 | `8984d9d` |
| 最小策略代码 | 已完成 | `workspace/strategies/prevday_volume_filter_strategy.py` |
| 单元测试 | 已完成 | `workspace/tests/strategies/test_prevday_volume_filter_strategy.py` |
| 基础验证 | 已完成 | `ruff check`、`ruff format --check`、`uv run mypy`、局部 `pytest` |
| 桥接修正 | 已完成 | `Signal.diagnostics` 支持 bool / str 后，vnpy 诊断日志不再因非 float 值中断 |

验证命令：

```text
ruff check workspace/strategies/bridges/vnpy_backtest_bridge.py workspace/strategies/prevday_volume_filter_strategy.py workspace/tests/strategies/test_prevday_volume_filter_strategy.py
ruff format workspace/strategies/bridges/vnpy_backtest_bridge.py workspace/strategies/prevday_volume_filter_strategy.py workspace/tests/strategies/test_prevday_volume_filter_strategy.py
ruff format --check workspace/strategies/bridges/vnpy_backtest_bridge.py workspace/strategies/prevday_volume_filter_strategy.py workspace/tests/strategies/test_prevday_volume_filter_strategy.py
uv run mypy workspace/strategies/bridges/vnpy_backtest_bridge.py workspace/strategies/prevday_volume_filter_strategy.py workspace/tests/strategies/test_prevday_volume_filter_strategy.py
uv run pytest workspace/tests/strategies/test_prevday_volume_filter_strategy.py --tb=short
```

### 5.2 工程修正：非数值 diagnostics 触发回测中断

第一轮回测中，同一策略 `volume_filter_enabled=false` 的 baseline 一开始只产生 0 笔交易，且报告中仅有 3 个交易日；但旧 `prevday_reacceptance` 同参数可产生 44 笔交易。

排查后确认：

```text
prevday_volume_filter 的 diagnostics 中加入了 bool / str 字段
→ vnpy bridge 日志格式化使用 f"{value:.4f}"
→ 第一笔信号出现后日志格式化异常
→ 回测提前中断，最终持久化为 0 交易
```

修正：

```text
VnpyBacktestBridge._log_bar_diagnostics
→ 新增 _format_diagnostic_value
→ bool / str / numeric 分别格式化
```

修正后，同策略 baseline 的 5m 结果与 r2 最佳结构对齐：

```text
DCE.m2601 / 5m / close target / min_breakout=4 / 1.5x stop / daily 1 trade
→ 44 fills
→ net pnl -1,911.77
```

## 6. 固定参数回测结果

### 6.1 DCE.m2601：5m baseline vs filter stage

固定结构：

```text
kline_period = 5m
min_breakout_ticks = 4
take_profit_mode = close
max_hold_bars = 6
stop_widen_multiplier = 1.5
max_trades_per_day = 1
```

| id | 过滤设置 | fills | win rate | net pnl | max drawdown | 观察 |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| `348` | baseline / filter off | 44 | 66.67% | -1,911.77 | -3,974 | 对齐 r2，仍成本后为负 |
| `349` | breakout / vol 2.0 / range 1.0 / body 0 | 12 | 80.00% | -858 左右 | -1,703 | 过滤明显减少交易并改善亏损，但未转正 |
| `350` | reaccept / vol 2.0 / range 1.0 / body 0 | 8 | 25.00% | -1,126 左右 | -1,126 | 重新接受 bar 放量不是好过滤点 |
| `351` | either / vol 2.0 / range 1.0 / body 0 | 18 | 50.00% | -1,960 左右 | -2,578 | either 放宽后质量回落 |

阶段判断：

```text
breakout shock > reaccept shock > either
```

成交量爆发若有价值，主要来自“边界外假突破阶段是否有真实冲击”，而不是重新接受那根 K 是否放量。

### 6.2 DCE.m2601：周期和阈值对照

| id | 参数摘要 | fills | win rate | net pnl | max drawdown | 观察 |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| `352` | 1m baseline / close / 30 bars / 1.5x | 52 | 53.85% | -5,832 | -6,300 | 与 r2 1m 最佳附近一致，成本噪声大 |
| `353` | 1m breakout filter / vol 2.0 | 40 | 41.18% | -7,020 | -8,088 | 1m 放量过滤反而劣化 |
| `354` | 5m breakout loose / vol 1.5 | 18 | 87.50% | -760 左右 | -1,778 | 样本略多但仍未转正 |
| `355` | 5m breakout strict / vol 2.5 range 1.2 body 0.3 | 6 | 100.00% | +2.39 | -215 | 表面转正但只有 3 笔开平，且含跨 session 平仓 |

关键问题：

```text
严格过滤可以把结果推到接近打平，
但有效样本迅速耗尽，统计意义不足。
```

### 6.3 严格日内修正与跨品种验证

由于 `355` 中存在 14:30 入场、21:00 平仓的跨 session 影响，补充严格日内口径：

```text
last_entry_time = 14:00
force_flat_time = 14:50
volume_filter_stage = breakout
volume_multiplier = 2.5
range_multiplier = 1.2
min_body_ratio = 0.3
```

| id | symbol | filter | fills | win rate | net pnl | max drawdown | 观察 |
| ---: | --- | --- | ---: | ---: | ---: | ---: | --- |
| `356` | DCE.m2601 | on | 2 | 0.00% | -155 左右 | -155 | 严格日内后 m 不再转正，样本几乎耗尽 |
| `357` | CZCE.SR601 | on | 4 | 50.00% | +190 左右 | -487 | 小正但样本过少 |
| `358` | DCE.c2601 | on | 0 | N/A | 0 | 0 | 无交易 |
| `359` | SHFE.rb2601 | on | 10 | 0.00% | -2,172 左右 | -2,172 | 明显失败 |
| `360` | DCE.m2601 | baseline | 40 | 63.16% | -2,730 左右 | -4,145 | filter 大幅减亏但样本耗尽 |
| `361` | CZCE.SR601 | baseline | 40 | 47.37% | -4,762 左右 | -4,762 | filter 改善明显 |
| `362` | DCE.c2601 | baseline | 28 | 58.33% | -2,870 左右 | -2,942 | filter 直接无交易 |
| `363` | SHFE.rb2601 | baseline | 48 | 45.45% | -11,540 左右 | -12,126 | filter 减亏但仍失败 |

跨品种结论：

```text
成交量过滤能降低交易数和部分亏损，
但不是稳定正向过滤器：
- m / SR：明显减亏，但样本太少；
- c：直接无交易；
- rb：仍明显亏损；
- 没有形成成本后、跨品种的正期望证据。
```

## 7. 临时结论

本轮方向的结论：

```text
成交量爆发作为前日共识边界假突破的质量过滤器，
比“成交量爆发作为主边界”更合理，
但仍未通过结构型 alpha 标准。
```

具体判断：

1. **breakout shock 有信息量**：相比 baseline，能明显减少交易和亏损，说明成交冲击发生在边界外假突破阶段时，确实过滤掉了一部分噪音。
2. **reaccept shock 不可靠**：重新接受那根 K 放量并不能稳定提升质量。
3. **1m 不适合**：1m 放量过滤被噪声吞噬，结果比 baseline 更差。
4. **5m 严格过滤会样本耗尽**：最好的 m 结果只是靠极少数交易接近打平，严格日内修正后不再成立。
5. **跨品种不稳定**：SR 小样本转正，rb 明显失败，c 无交易。

因此，当前不建议继续沿着“前日高低点 + volume shock filter”作为独立策略方向深挖。

后续若还使用成交量，更适合降级为诊断字段或弱权重过滤，而不是硬门槛：

```text
不要：必须有 volume shock 才能入场
可以：记录 breakout volume_ratio / range_ratio，用于事后分桶分析或仓位缩放
```

下一步更值得换到新的边界来源，而不是继续调成交量阈值。
