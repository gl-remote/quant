# structural-alpha-r6：压力释放后的低波动收敛再启动

类型：Workbench / 策略实验记录  
状态：执行中  
创建日期：2026-06-28  
最后更新：2026-06-28

## 来源规划

- 来源规划：[strategy-short-term-plan.md](../roadmap/strategy-short-term-plan.md)
- 研究框架：[strategy-research-framework.md](../roadmap/strategy-research-framework.md)

## 开发信息

- 开发分支：experiment/structural-alpha-r6-low-volatility-restart
- 开分支 hash：6159e93
- 实现提交 hash：待回填

## 核心问题

不再把单一价位边界作为主要研究对象，而是研究状态切换：压力释放后进入低波动收敛，再次突破收敛区间时，是否存在可交易方向优势。

```text
压力释放
→ 低波动收敛
→ 再次启动
→ 明确失败边界和 R 目标
```

## 明确排除

- 不继续围绕等高 / 等低、POC、IB 或前日高低点做边界微调。
- 不把成交量作为主条件。
- 第一轮不做 Optuna / Walk-Forward，只做固定参数诊断。

## 结构定义

### 压力释放

过去 `impulse_lookback` 根 5m K 线中，最近一根满足：

```text
true_range / ATR >= min_impulse_atr
abs(close - open) / true_range >= min_impulse_body_ratio
```

方向：

```text
close >= open → up
close < open  → down
```

### 低波动收敛

最近 `compression_bars` 根 5m K 线满足：

```text
compression_width / ATR <= max_compression_width_atr
average_bar_range / ATR <= max_compression_bar_range_atr
```

其中：

```text
compression_width = max(high) - min(low)
average_bar_range = avg(high - low)
```

### 再启动入场

当前 5m close 突破收敛区间：

```text
close >= compression_high + min_breakout_ticks * price_tick → long
close <= compression_low  - min_breakout_ticks * price_tick → short
```

方向模式：

| mode | 说明 |
| --- | --- |
| `breakout` | 只跟随收敛区间突破方向 |
| `impulse_continuation` | 只做压力释放方向延续 |
| `impulse_reversal` | 只做压力释放反方向修复 |

### 失败边界和目标

严格失败边界：

```text
long:  compression_low  - failure_buffer_ticks * price_tick
short: compression_high + failure_buffer_ticks * price_tick
```

目标：

```text
long:  entry + strict_distance * take_profit_r
short: entry - strict_distance * take_profit_r
```

## 固定参数第一轮计划

品种：优先 DCE.m2601，后续用 DCE.c2601 / CZCE.SR601 / SHFE.rb2601 做交叉验证。

统一约束：

```text
kline_period = 5m
last_entry_time = 14:00
force_flat_time = 14:50
max_trades_per_day = 1
risk_per_trade = 0.02
max_position_ratio = 0.3
```

候选组：

| 组 | 参数摘要 |
| --- | --- |
| A | compression 6 / impulse 12 / min_impulse_atr 1.5 / width_atr 1.0 / avg_range_atr 0.45 / breakout / 1R |
| B | A + 1.5R |
| C | A + impulse_continuation |
| D | A + impulse_reversal |
| E | compression 4 / width_atr 0.8 / avg_range_atr 0.4 / breakout / 1R |
| F | compression 8 / width_atr 1.2 / avg_range_atr 0.5 / breakout / 1R |

## 工程实现

| 项目 | 状态 | 说明 |
| --- | --- | --- |
| 策略 | 已完成 | `workspace/strategies/low_volatility_restart_strategy.py` |
| 测试 | 已完成 | `workspace/tests/strategies/test_low_volatility_restart_strategy.py` |
| 数据需求 | 已完成 | `5m` 执行周期历史窗口 |
| 入场 | 已完成 | 压力释放 + 低波收敛 + 区间突破 |
| 退出 | 已完成 | stop loss、strict failure close、take profit、force flat、time exit |

验证：

```text
ruff check workspace/strategies/low_volatility_restart_strategy.py workspace/tests/strategies/test_low_volatility_restart_strategy.py
ruff format workspace/strategies/low_volatility_restart_strategy.py workspace/tests/strategies/test_low_volatility_restart_strategy.py
ruff format --check workspace/strategies/low_volatility_restart_strategy.py workspace/tests/strategies/test_low_volatility_restart_strategy.py
uv run mypy workspace/strategies/low_volatility_restart_strategy.py workspace/tests/strategies/test_low_volatility_restart_strategy.py
uv run pytest workspace/tests/strategies/test_low_volatility_restart_strategy.py --tb=short
```

结果：`8 passed`。

## 第一轮固定参数结果

### DCE.m2601 严格低波组

统一约束：

```text
kline_period = 5m
last_entry_time = 14:00
force_flat_time = 14:50
max_trades_per_day = 1
```

| id | 参数摘要 | trades | win rate | net pnl | max drawdown | 观察 |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| `382` | A：compression 6 / impulse 12 / impulse_atr 1.5 / width_atr 1.0 / avg_range_atr 0.45 / breakout / 1R | 0 | N/A | 0 | 0 | 条件过严，无样本 |
| `383` | B：A + 1.5R | 0 | N/A | 0 | 0 | 无样本 |
| `384` | C：A + impulse_continuation | 0 | N/A | 0 | 0 | 无样本 |
| `385` | D：A + impulse_reversal | 0 | N/A | 0 | 0 | 无样本 |
| `386` | E：compression 4 / width_atr 0.8 / avg_range_atr 0.4 / breakout / 1R | 0 | N/A | 0 | 0 | 无样本 |
| `387` | F：compression 8 / width_atr 1.2 / avg_range_atr 0.5 / breakout / 1R | 0 | N/A | 0 | 0 | 无样本 |

判断：严格定义下，“压力释放后低波收敛再启动”在 DCE.m2601 上样本过少，不能直接进入收益判断。

### DCE.m2601 放宽门槛诊断

为了区分“结构太稀疏”和“有样本但无优势”，追加放宽门槛组：

| id | 参数摘要 | trades | win rate | net pnl | max drawdown | 观察 |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| `388` | compression 3 / impulse 24 / impulse_atr 1.0 / width_atr 2.0 / avg_range_atr 1.0 / breakout / 1R | 122 | 35.59% | -29,783 | -30,569 | 放宽后样本充足，但明显亏损 |
| `389` | compression 4 / impulse 24 / impulse_atr 0.8 / width_atr 2.5 / avg_range_atr 1.2 / breakout / 1R | 120 | 43.10% | -17,026 | -17,527 | 相对最好，但仍远低于通过线 |
| `390` | compression 3 / impulse 24 / impulse_atr 0.5 / width_atr 5.0 / avg_range_atr 5.0 / breakout / 1R | 122 | 45.90% | -21,063 | -25,444 | 近似退化为普通短周期突破，仍亏损 |
| `391` | `389` 参数 + impulse_continuation | 104 | 48.98% | -4,740 | -9,027 | 延续方向显著减亏，但成本后仍为负 |
| `392` | `389` 参数 + impulse_reversal | 112 | 41.82% | -25,260 | -25,942 | 反向修复明显失败 |
| `393` | `389` 参数 + 1.5R | 120 | 41.07% | -17,270 | -19,785 | 提高 R 未改善期望；本组出现少量成交配对 warning，仅作方向参考 |

DCE.m2601 判断：

```text
严格低波定义样本不足；
放宽后可产生样本，但突破本身没有方向优势；
压力释放方向延续比反向修复更好，但仍未覆盖成本和滑点。
```

### 跨品种验证

采用 DCE.m2601 中样本较稳定的放宽突破组：

```text
compression_bars = 4
impulse_lookback = 24
min_impulse_atr = 0.8
max_compression_width_atr = 2.5
max_compression_bar_range_atr = 1.2
direction_mode = breakout
take_profit_r = 1.0
```

| id | symbol | trades | win rate | net pnl | max drawdown | 观察 |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| `394` | DCE.c2601 | 120 | 37.50% | -26,940 | -26,942 | 明显失败 |
| `395` | CZCE.SR601 | 122 | 52.54% | -12,330 | -20,373 | 胜率过半但盈亏比/成本不够 |
| `396` | SHFE.rb2601 | 122 | 55.74% | -17,380 | -21,425 | 胜率较高但亏损仍明显 |

跨品种判断：

```text
这个结构不是单品种偶然失败。
即使部分品种胜率超过 50%，平均盈利不足以覆盖平均亏损、手续费和滑点。
```

## 临时结论

压力释放后的低波动收敛再启动，作为独立结构暂未通过第一轮固定参数诊断。

当前更接近的结论是：

```text
低波收敛描述的是“波动状态”，不是天然方向优势。
压力释放方向延续比反向修复更合理，但优势不足以覆盖成本。
如果继续挖，应该把它降级为环境过滤器，而不是主入场结构。
```

后续不建议继续在当前定义下做 tick 阈值或 ATR 阈值微调。若要继续，只建议测试：

```text
已有强共识边界 / 趋势背景
+ 压力释放后低波收敛
+ 只做压力释放方向延续
```

也就是把 r6 用作“行情状态过滤”，而不是单独生成交易。
