# structural-alpha-r3：成交量爆发边界接受 / 拒绝

> 类型：Workbench / 策略实验记录  
> 状态：执行中  
> 创建日期：2026-06-28  
> 最后更新：2026-06-28  
> 来源规划：[策略短期研究计划：结构型 Alpha 验证](../roadmap/strategy-short-term-plan.md)  
> 研究框架：[策略长期共识：共识价格区间下的账户风险结构塑形框架](../roadmap/strategy-research-framework.md)  
> 开发分支：`experiment/structural-alpha-r3-volume-shock-boundary`  
> 开分支 hash：`9c619c4`  
> 实现提交 hash：`ee239f1`

## 1. 核心问题

本轮不继续更换固定时间宽度边界，而是把共识边界来源改为成交行为事件：

```text
成交量异常爆发
→ 该 K 线区间发生集中换手 / 主动成交冲击 / 分歧释放
→ shock_high / shock_low / shock_mid 成为短期事件边界
→ 后续价格对该边界的接受 / 拒绝，是否比 IB 或前日高低点提供更强结构型 alpha
```

本轮优先回答：

```text
成交量爆发 K 线边界外的假突破与重新接受
→ 是否能给出清晰严格失败边界
→ 是否能定义 shock_mid / shock 对侧边界作为盈利上界
→ 是否能改善前两轮的 MFE 不足、平均盈利过小和成本吞噬问题
```

本轮不做：

```text
不做 Optuna
不做 Walk-Forward
不叠加 MACD / KDJ / 均线趋势过滤
不同时研究放量延续和放量反转
不引入 IB、前日高低点、VAH / VAL / POC 作为主边界
```

## 2. 实验定义

| 项目 | 定义 |
| --- | --- |
| 实验版本 | `structural-alpha-r3` |
| 策略代号 | `volume_shock_boundary` |
| 候选共识价格区间 | 成交量爆发 K 线的 high / low / mid |
| 结构来源 | Volume Shock / Price Action / 主动成交冲击失败 |
| 传统解释 | 放量冲击后若边界外无法维持，说明追随冲击的一侧可能失败 |
| 结构塑形解释 | 成交量爆发代表真实集中成交；shock bar 边界提供事件型共识区间；边界外极值提供严格失败边界；shock_mid / 对侧边界提供短期盈利上界 |
| 方向假设 | 放量下跌后跌破 shock_low 又重新接受做多；放量上涨后突破 shock_high 又重新拒绝做空 |
| 严格失败边界 | 重新接受前边界外极值加 / 减 `failure_buffer_ticks` |
| 目标止盈 | `shock_mid` / `opposite` / `r` |
| 时间退出 | 入场后 `max_hold_bars` 或日内 `force_flat_time` |
| 入场方式 | shock 形成后，在有效窗口内发生边界外突破，再收盘重新回到 shock 区间内 |
| 退出方式 | 严格失败边界、主动止盈、时间退出、日内强平 |

### 2.1 多头结构

```text
出现放量下跌 shock bar
→ shock_low 作为下边界
→ 后续价格跌破 shock_low 至少 min_breakout_ticks
→ 收盘重新回到 shock_low 上方
→ 做多
→ 严格失败边界 = 重新接受前低点 - failure_buffer_ticks
→ 盈利上界 = shock_mid / shock_high / R 倍数
```

### 2.2 空头结构

```text
出现放量上涨 shock bar
→ shock_high 作为上边界
→ 后续价格突破 shock_high 至少 min_breakout_ticks
→ 收盘重新回到 shock_high 下方
→ 做空
→ 严格失败边界 = 重新接受前高点 + failure_buffer_ticks
→ 盈利上界 = shock_mid / shock_low / R 倍数
```

## 3. 固定参数组

第一轮只做固定参数诊断，不做参数搜索。

| 参数 | 初始值 | 说明 |
| --- | ---: | --- |
| `kline_period` | `1m` / `5m` | 先用 1m，若成本噪声明显再补 5m |
| `volume_lookback` | `20` | 成交量均值窗口 |
| `volume_multiplier` | `2.5` / `3.0` | shock 成交量倍数 |
| `range_lookback` | `20` | 振幅均值窗口 |
| `range_multiplier` | `1.2` / `1.5` | shock 振幅倍数 |
| `min_body_ratio` | `0.5` | 实体 / 振幅最小比例 |
| `shock_valid_bars` | `30` / `60` | shock 后有效触发窗口 |
| `min_breakout_ticks` | `1` / `2` | 边界外最小突破距离 |
| `failure_buffer_ticks` | `1` | 严格失败边界 buffer |
| `take_profit_mode` | `mid` / `opposite` / `r` | 主动止盈目标对照 |
| `take_profit_r` | `1.0` / `2.0` | R 倍数止盈对照 |
| `max_hold_bars` | `30` / `60` | 时间退出 |
| `stop_widen_multiplier` | `1.0` / `1.5` | 严格失败与有限放宽对照 |
| `risk_per_trade` | `0.02` | 单次账户风险目标 |
| `max_position_ratio` | `0.3` | 仓位上限 |
| `max_trades_per_day` | `2` | 控制日内重复交易 |

初始测试范围：

| 项目 | 值 |
| --- | --- |
| 主品种 | `DCE.m2601` |
| 跨品种 | `CZCE.SR601`、`DCE.c2601`、`DCE.cs2601`、`SHFE.rb2601` |
| 周期 | `1m` / `5m` |
| 回测引擎 | `vnpy` |
| 模式 | `single` |
| 数据口径 | 真实收益以 `backtest_daily.net_pnl` / `backtests.total_net_pnl` 为准 |

## 4. 实验过程记录

### 4.1 第 0 轮：工程接入与最小策略实现

| 项目 | 状态 | 说明 |
| --- | --- | --- |
| 独立分支 | 已完成 | `experiment/structural-alpha-r3-volume-shock-boundary` |
| 开分支 hash | 已记录 | `9c619c4` |
| 最小策略代码 | 已完成 | `workspace/strategies/volume_shock_boundary_strategy.py` |
| 单元测试 | 已完成 | `workspace/tests/strategies/test_volume_shock_boundary_strategy.py`，覆盖 shock 识别、重新接受入场、退出和目标模式 |
| 基础验证 | 已完成 | `ruff check`、`ruff format --check`、`uv run mypy`、局部 `pytest` 均通过 |

验证命令：

```text
ruff check workspace/strategies/volume_shock_boundary_strategy.py workspace/tests/strategies/test_volume_shock_boundary_strategy.py
ruff format --check workspace/strategies/volume_shock_boundary_strategy.py workspace/tests/strategies/test_volume_shock_boundary_strategy.py
uv run mypy workspace/strategies/volume_shock_boundary_strategy.py workspace/tests/strategies/test_volume_shock_boundary_strategy.py
uv run pytest workspace/tests/strategies/test_volume_shock_boundary_strategy.py --tb=short
```

CLI 入口仍沿用已知规避方式：

```text
PYTHONPATH=workspace uv run python main.py backtest --env backtest --engine vnpy --mode single --strategy volume_shock_boundary ...
```

### 4.2 DCE.m2601 1m 固定参数对照

| id | 参数摘要 | trades | win rate | gross pnl | commission | slippage | net pnl | 结论 |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `323` | 1m + vol 2.5 + range 1.2 + mid + 60 bars + 每日 2 笔 | 172 | 50.79% | -3,710 | 6,659.75 | 11,900 | -22,269.75 | 宽松触发过度，成本和原始毛收益均失败 |
| `324` | 1m + vol 2.5 + range 1.2 + opposite + 60 bars + 每日 2 笔 | 194 | 50.59% | -5,230 | 7,503.94 | 13,390 | -26,123.94 | 对侧边界目标扩大后更差 |
| `325` | 1m + vol 2.5 + range 1.2 + 2R + 60 bars + 每日 2 笔 | 195 | 32.98% | -720 | 7,538.99 | 13,460 | -21,718.99 | 2R 提升平均盈利但胜率坍塌，成本后仍大亏 |
| `326` | 1m + vol 3.0 + range 1.5 + mid + 30 bars + 每日 1 笔 | 56 | 75.00% | -200 | 2,166.01 | 3,870 | -6,236.01 | 高胜率来自近目标，但平均盈利过小，成本吞噬 |
| `327` | 1m + vol 3.0 + range 1.5 + 2R + 30 bars + 每日 1 笔 | 58 | 44.83% | -1,030 | 2,243.54 | 4,010 | -7,283.54 | 2R 不能转正 |
| `328` | 同 `327` + 1.5x 止损放宽 | 58 | 46.43% | -1,980 | 2,243.55 | 4,010 | -8,233.55 | 放宽止损恶化，严格失败边界附近噪声不是唯一问题 |

观察：

1. 1m 宽松组交易过多，成本直接吞噬；且 `323`~`325` 的毛收益也全部为负。
2. 提高 shock 阈值、缩短有效窗口、每日最多 1 笔后，亏损收窄，但 `326`~`328` 毛收益仍未稳定为正。
3. `326` 胜率 75%，但平均盈利 `198.89`、平均亏损 `630`，典型“近目标高胜率但账户盈亏比不足”。
4. `327` / `328` 尝试 2R 和止损放宽后，胜率和毛收益都不能支撑成本后转正。

### 4.3 DCE.m2601 5m 降噪对照

| id | 参数摘要 | trades | win rate | gross pnl | commission | slippage | net pnl | 结论 |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `329` | 5m + vol 2.5 + range 1.2 + mid + 12 bars + 每日 1 笔 | 16 | 83.33% | 190 | 611.95 | 1,090 | -1,511.95 | 接近但样本少，平均亏损过大 |
| `330` | 5m + vol 2.5 + range 1.2 + 2R + 12 bars + 每日 1 笔 | 18 | 57.14% | 1,160 | 688.54 | 1,230 | -758.54 | 本轮 DCE.m2601 最接近转正，但仍无安全边际 |
| `331` | 5m + vol 3.0 + range 1.5 + 2R + 6 bars + 每日 1 笔 | 4 | 50.00% | -770 | 150.94 | 270 | -1,190.94 | 过滤过严，样本不足 |

观察：

1. 5m 明显降低成本和噪声，`330` 毛收益为正 `1,160`，但总成本 `1,918.54`，成本后仍 `-758.54`。
2. `329` 高胜率仍不能覆盖单次大亏，说明 shock_mid 目标偏近。
3. 更严格 shock 条件导致样本只有 4 笔成交，不能评价。
4. 原始 `329`~`331` 存在 14:30 入场、21:00 平仓的夜盘跨段污染，后续补做更严格日内退出。

### 4.4 5m 最佳结构跨品种确认

采用 `330` 结构：

```text
5m + volume_multiplier 2.5 + range_multiplier 1.2 + min_body_ratio 0.5
+ shock_valid_bars 12 + min_breakout 1 tick + 2R
+ max_hold_bars 12 + 每日最多 1 笔
```

| id | symbol | trades | win rate | gross pnl | commission | slippage | net pnl | 结论 |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `332` | `CZCE.SR601` | 16 | 12.50% | -3,110 | 699.33 | 810 | -4,619.33 | 失败，胜率极低 |
| `333` | `DCE.c2601` | 16 | 42.86% | -510 | 782.99 | 1,580 | -2,872.99 | 失败 |
| `334` | `DCE.cs2601` | 20 | 40.00% | 235 | 1,762.94 | 2,360 | -3,887.94 | 毛收益略正但成本远大于空间 |
| `335` | `SHFE.rb2601` | 40 | 50.00% | 6,150 | 3,966.15 | 2,650 | -466.15 | 毛收益较好但成本后仍未转正，且回撤较大 |

观察：

1. 跨品种只有 `SHFE.rb2601` 毛收益较强，`DCE.cs2601` 毛收益微正，其余为负。
2. 所有品种成本后均为负。
3. `335` 接近盈亏平衡，但手续费和滑点合计 `6,616.15`，超过毛收益 `6,150`。
4. 该结构没有跨品种成本后正期望证据。

### 4.5 修正夜盘跨段污染后的日内对照

为避免 14:30 入场后 21:00 夜盘开盘平仓污染，将约束改为：

```text
last_entry_time = 14:00
force_flat_time = 14:50
```

| id | symbol | trades | win rate | gross pnl | commission | slippage | net pnl | 结论 |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `336` | `DCE.m2601` | 12 | 50.00% | -140 | 465.26 | 840 | -1,445.26 | 日内严格后仍为负 |
| `337` | `SHFE.rb2601` | 28 | 35.71% | 1,710 | 2,761.53 | 1,840 | -2,891.53 | 去除夜盘污染后明显恶化 |
| `338` | `DCE.c2601` | 10 | 33.33% | 620 | 491.94 | 990 | -861.94 | 毛收益为正但成本后为负，样本少 |

观察：

1. 严格日内退出后，`SHFE.rb2601` 从 `-466.15` 恶化到 `-2,891.53`，说明原先接近盈亏平衡部分依赖跨段持有。
2. `DCE.m2601` 和 `DCE.c2601` 仍不能转正。
3. 日内约束下样本进一步减少，且成本后没有正结果。

## 5. 关键诊断

| 诊断项 | 当前结果 | 含义 |
| --- | --- | --- |
| 候选边界是否客观 | 通过 | volume shock 可由成交量倍数、振幅倍数和实体比例客观定义 |
| 严格失败边界是否清晰 | 通过 | 边界外极值加 buffer 可定义严格失败边界 |
| 成交量爆发是否改善接受质量 | 未通过 | 1m 交易过多且毛收益为负；5m 仅个别组毛收益小幅为正 |
| 盈利上界 | 偏弱 | shock_mid 胜率高但盈利过小；2R 改善平均盈利但胜率下降或样本不足 |
| 账户原始盈亏比 | 未通过 | 最接近的 `330` 毛收益 `1,160` 仍小于成本 `1,918.54` |
| 成本空间 | 未通过 | 多数组成本显著大于毛收益，所有测试成本后均为负 |
| 止损放宽 | 未通过 | `328` 放宽后净亏损扩大，不能靠吸收噪声修复 |
| 跨品种一致性 | 未通过 | `332`~`335` 全部成本后为负，且只有局部品种毛收益较好 |
| 日内执行一致性 | 未通过 | 修正夜盘跨段污染后，接近盈亏平衡结果消失或恶化 |
| 样本充足性 | 偏弱 | 5m 严格组样本过少，无法支撑继续复杂调参 |

失败层级：

```text
成交量爆发边界可以客观定义
→ 严格失败边界也清楚
→ 但边界外重新接受后的 MFE 不稳定
→ shock_mid 目标太近，2R 目标胜率不足
→ 5m 降噪后毛收益偶尔为正，但不足以覆盖成本
→ 跨品种和严格日内退出后没有正期望证据
```

## 6. 临时结论

当前判断：

```text
成交量爆发 K 线边界作为“重新接受 / 拒绝”主边界，未通过结构型 alpha 标准。
```

主要证据：

1. 1m 结构显著失败：`323`~`328` 全部成本后为负，宽松组净亏损达到 `-21%` 到 `-26%`。
2. 5m 降噪后只接近盈亏平衡，最佳 `330` 仍为 `-758.54`，没有成本安全边际。
3. 跨品种 `332`~`335` 全部成本后为负。
4. 严格日内退出修正后 `336`~`338` 仍全部为负，说明接近盈亏平衡并非稳定日内结构优势。
5. 继续围绕 `volume_multiplier`、`range_multiplier`、`shock_valid_bars`、`take_profit_r` 微调，容易变成参数筛选，不符合当前阶段实验哲学。

后续只保留一个可能升级方向：

```text
成交量爆发不能单独作为边界；若继续使用成交量，应作为“边界质量过滤”而不是主边界来源。
例如：固定共识边界附近是否发生 volume shock，再判断接受 / 拒绝质量。
```

本轮不进入 Optuna / Walk-Forward。

