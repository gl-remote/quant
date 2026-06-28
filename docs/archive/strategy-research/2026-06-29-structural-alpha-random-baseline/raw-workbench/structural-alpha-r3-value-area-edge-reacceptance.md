# structural-alpha-r3：前日价值区边缘接受 / 拒绝

> 类型：Workbench / 策略实验记录  
> 状态：执行中  
> 创建日期：2026-06-28  
> 最后更新：2026-06-28  
> 来源规划：[策略短期研究计划：结构型 Alpha 验证](../roadmap/strategy-short-term-plan.md)  
> 研究框架：[策略长期共识：共识价格区间下的账户风险结构塑形框架](../roadmap/strategy-research-framework.md)  
> 开发分支：`experiment/structural-alpha-r3-value-area-edge`  
> 开分支 hash：`9c619c4`  
> 实现提交 hash：待补

## 1. 核心问题

本轮实验接在 IB 和前日高低点重新接受之后，验证更接近 Auction / Market Profile 的共识边界：

```text
前一交易日 VAH / VAL / POC
→ 当日突破 VAH / VAL 后无法维持
→ 重新接受回前日价值区内
→ 是否比 IB、前日高低点提供更好的接受 / 拒绝质量
→ 是否能用 POC 或对侧价值区边缘定义更清晰盈利上界
→ 是否能改善成本后期望和安全边际
```

本轮不做：

```text
不做 Optuna
不做 Walk-Forward
不叠加 MACD / KDJ / 均线趋势确认
不同时引入前日高低点作为过滤
不为凑交易数放宽价值区定义
```

## 2. 实验定义

| 项目 | 定义 |
| --- | --- |
| 实验版本 | `structural-alpha-r3` |
| 策略代号 | `value_area_reacceptance` |
| 候选共识价格区间 | 前一交易日 VAH / VAL / POC |
| 结构来源 | Auction / Market Profile / 成交密集区 |
| 传统解释 | 价格尝试离开前日价值区后无法维持，重新回到被市场接受的价值区 |
| 结构塑形解释 | VAH / VAL 是成交接受区边缘；假突破极值提供严格失败边界；POC / 对侧边缘提供短期盈利上界 |
| 方向假设 | 上破 VAH 后重新收回 VAH 下方做空；下破 VAL 后重新收回 VAL 上方做多 |
| 严格失败边界 | 假突破极值外加 `failure_buffer_ticks` |
| 目标止盈 | POC / 对侧价值区边缘 / R 倍数 |
| 时间退出 | 入场后 `max_hold_bars` 或日内 `force_flat_time` |
| 入场方式 | 边界外触发突破状态后，收盘价重新回到前日价值区内并满足最小突破幅度 |
| 退出方式 | 严格失败边界、主动止盈、时间退出、日内强平 |

### 2.1 价值区计算

第一轮使用最小可复现定义：

```text
前一交易日日内 K 线
→ 按 price_tick 聚合成交量分布
→ POC = 成交量最大价格桶
→ 从 POC 向上下相邻价格桶扩展
→ 覆盖 value_area_ratio（默认 70%）成交量
→ 最高选中价格 = VAH
→ 最低选中价格 = VAL
```

`profile_mode` 对照：

| 模式 | 定义 | 用途 |
| --- | --- | --- |
| `range` | 单根 K 线成交量均匀分摊到 high-low 覆盖的 tick 桶 | 更接近区间成交分布，但假设更强 |
| `close` | 单根 K 线成交量归入 close 所在 tick 桶 | 更保守、更简单，但 POC 可能更噪声 |

### 2.2 多头结构

```text
已知前日 VAH / VAL / POC
→ 价格向下跌破 VAL 至少 min_breakout_ticks
→ 价格收盘重新回到 VAL 上方
→ 做多
→ 严格失败边界 = 假突破低点 - failure_buffer_ticks
→ 盈利上界 = POC / VAH / R 倍数
```

### 2.3 空头结构

```text
已知前日 VAH / VAL / POC
→ 价格向上突破 VAH 至少 min_breakout_ticks
→ 价格收盘重新回到 VAH 下方
→ 做空
→ 严格失败边界 = 假突破高点 + failure_buffer_ticks
→ 盈利上界 = POC / VAL / R 倍数
```

## 3. 固定参数组

第一轮只做固定参数诊断，不做参数搜索。

| 参数 | 初始值 | 说明 |
| --- | ---: | --- |
| `kline_period` | `5m` | 延续 r2 当前较优确认周期，降低 1m 噪声和交易成本 |
| `profile_mode` | `range` / `close` | 价值区计算方式对照 |
| `value_area_ratio` | `0.7` | 传统 70% 价值区 |
| `trade_start_time` | `09:00` | 开始寻找重新接受 |
| `last_entry_time` | `14:30` | 最晚入场时间 |
| `force_flat_time` | `14:55` | 日内强制平仓 |
| `price_tick` | `1.0` | 第一轮按主品种最小变动 |
| `min_breakout_ticks` | `2` / `4` | 最小假突破距离 |
| `failure_buffer_ticks` | `1` | 严格失败边界 buffer |
| `take_profit_mode` | `poc` / `opposite` / `r` | 主动止盈目标对照 |
| `take_profit_r` | `1.0` / `2.0` | R 倍数止盈对照 |
| `max_hold_bars` | `6` / `12` | 5m 下 30 / 60 分钟时间退出 |
| `stop_widen_multiplier` | `1.0` / `1.5` | 严格失败与有限放宽对照 |
| `risk_per_trade` | `0.02` | 单次账户风险目标 |
| `max_position_ratio` | `0.3` | 仓位上限 |
| `max_trades_per_day` | `1` | 控制日内重复交易 |

初始测试范围：

| 项目 | 值 |
| --- | --- |
| 主品种 | `DCE.m2601` |
| 跨品种 | `CZCE.SR601`、`DCE.c2601`、`DCE.cs2601`、`SHFE.rb2601` |
| 周期 | `5m`，必要时补 `1m` |
| 回测引擎 | `vnpy` |
| 模式 | `single` |
| 数据口径 | 真实收益以 `backtest_daily.net_pnl` / `backtests.total_net_pnl` 为准 |

## 4. 实验过程记录

### 4.1 第 0 轮：工程接入与最小策略实现

目标：

```text
实现 value_area_reacceptance 最小策略
→ 能被 CLI 动态加载
→ 能用 --mode single 和 --strategy-params 固定参数回测
→ 验证价值区计算、重新接受入场、严格失败退出、主动止盈和时间退出可运行
```

当前进展：

| 项目 | 状态 | 说明 |
| --- | --- | --- |
| 独立分支 | 已完成 | `experiment/structural-alpha-r3-value-area-edge` |
| 开分支 hash | 已记录 | `9c619c4` |
| 最小策略代码 | 已完成 | `workspace/strategies/value_area_reacceptance_strategy.py` |
| 单元测试 | 已完成 | `workspace/tests/strategies/test_value_area_reacceptance_strategy.py` |
| 基础验证 | 已完成 | `ruff check`、`ruff format --check`、`uv run mypy`、局部 pytest 均通过 |
| 最小回测 | 已完成 | 回测 ID `262` |
| 固定参数对照 | 已完成 | 回测 ID `262`~`269`、`274`~`279` |
| 跨品种确认 | 已完成 | 回测 ID `270`~`273`、`280`~`283` |

验证命令：

```text
ruff check workspace/strategies/value_area_reacceptance_strategy.py workspace/tests/strategies/test_value_area_reacceptance_strategy.py
ruff format --check workspace/strategies/value_area_reacceptance_strategy.py workspace/tests/strategies/test_value_area_reacceptance_strategy.py
uv run mypy workspace/strategies/value_area_reacceptance_strategy.py
uv run pytest workspace/tests/strategies/test_value_area_reacceptance_strategy.py --tb=short
```

CLI 入口仍沿用已知规避方式：

```text
PYTHONPATH=workspace uv run python main.py backtest --env backtest --engine vnpy --mode single --strategy value_area_reacceptance ...
```

### 4.2 DCE.m2601 固定参数对照

| id | 参数摘要 | trades | win rate | avg win | avg loss | net pnl | max drawdown | 结论 |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `262` | 5m + range profile + breakout 2 + POC + 6 bars + 严格止损 | 76 | 57.14% | 437.50 | 742.00 | -14,222.61 | -14,222.61 | range 分布 + 浅突破明显失败 |
| `263` | 5m + range + breakout 4 + POC + 6 bars + 严格止损 | 59 | 53.57% | 419.33 | 824.62 | -10,393.75 | -10,393.75 | 加深突破仍失败 |
| `264` | 5m + range + breakout 4 + POC + 6 bars + 1.5x 放宽 | 59 | 53.57% | 347.33 | 695.38 | -8,983.53 | -8,983.53 | 放宽仅减亏，未改善结构 |
| `265` | 5m + range + breakout 4 + 对侧边缘 + 12 bars + 1.5x 放宽 | 56 | 42.31% | 543.64 | 885.33 | -14,835.47 | -14,835.47 | 更远盈利上界无法兑现 |
| `266` | 5m + range + breakout 4 + 2R + 6 bars + 1.5x 放宽 | 60 | 39.29% | 515.45 | 668.24 | -10,611.12 | -10,611.12 | R 倍数目标失败 |
| `267` | 5m + close profile + breakout 2 + POC + 6 bars + 严格止损 | 72 | 50.00% | 675.88 | 555.88 | -5,299.89 | -5,959.31 | close profile 明显优于 range，但仍负 |
| `268` | 5m + close + breakout 4 + POC + 6 bars + 1.5x 放宽 | 52 | 58.33% | 563.57 | 336.00 | +98.79 | -2,640.73 | 勉强转正，但安全边际极薄 |
| `269` | 5m + close + breakout 4 + 对侧边缘 + 12 bars + 1.5x 放宽 | 52 | 56.52% | 826.92 | 720.00 | -3,946.96 | -7,329.71 | 更远目标降低稳定性 |
| `274` | 同 `268`，但严格止损 | 52 | 58.33% | 630.71 | 401.00 | -343.82 | -3,179.10 | 1.5x 放宽是转正关键，但幅度很小 |
| `275` | close + breakout 4 + POC + 12 bars + 1.5x 放宽 | 52 | 52.17% | 878.33 | 430.91 | +1,368.95 | -3,088.44 | 主品种最佳，但仍需跨品种确认 |
| `276` | close + value area 60% + POC + 6 bars + 1.5x 放宽 | 44 | 42.86% | 561.11 | 604.17 | -4,072.25 | -4,320.86 | 价值区收窄失败 |
| `277` | close + value area 80% + POC + 6 bars + 1.5x 放宽 | 58 | 53.57% | 577.33 | 807.69 | -7,010.20 | -8,078.20 | 价值区放宽失败 |
| `278` | close + breakout 6 + POC + 6 bars + 1.5x 放宽 | 40 | 52.63% | 285.00 | 326.67 | -3,232.84 | -3,845.19 | 更深突破样本变少且不改善 |
| `279` | 1m + close + breakout 4 + POC + 30 bars + 1.5x 放宽 | 62 | 48.15% | 530.77 | 767.14 | -9,443.39 | -9,443.39 | 1m 噪声和成本明显恶化 |

观察：

1. `close` profile 明显优于 `range` profile；`range` 口径在本数据上会把价值区边缘变成更差的机械边界。
2. POC 目标优于对侧价值区边缘和 2R，说明真正可兑现空间主要在回到 POC 附近，而不是穿越整个价值区。
3. 主品种最佳组 `275` 成本后 `+1,368.95`，但最大回撤 `-3,088.44`，利润规模小于一次普通亏损簇风险。
4. `268` 与 `274` 的差异显示：转正依赖 1.5x 止损放宽，严格止损下仍略负。
5. `value_area_ratio` 从 0.7 改为 0.6 或 0.8 都明显退化，参数邻域不形成稳定平台。

### 4.3 跨品种确认

采用主品种两个相对较优结构确认。

#### 4.3.1 `268` 结构：6 bars 时间退出

```text
5m + close profile + value_area_ratio 0.7 + breakout 4 ticks + POC + 6 bars + 1.5x 放宽 + 每日最多 1 笔
```

| id | symbol | trades | win rate | avg win | avg loss | net pnl | max drawdown | 结论 |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `268` | `DCE.m2601` | 52 | 58.33% | 563.57 | 336.00 | +98.79 | -2,640.73 | 主品种勉强转正 |
| `270` | `CZCE.SR601` | 56 | 57.69% | 393.33 | 330.00 | -2,398.31 | -2,634.95 | 失败，成本吞噬 |
| `271` | `DCE.c2601` | 38 | 66.67% | 280.00 | 866.00 | -6,001.81 | -6,234.07 | 胜率高但亏损过大 |
| `272` | `DCE.cs2601` | 38 | 46.67% | 185.00 | 543.13 | -10,694.26 | -10,694.26 | 明显失败 |
| `273` | `SHFE.rb2601` | 48 | 43.48% | 462.00 | 633.85 | -11,721.60 | -12,566.43 | 明显失败 |

#### 4.3.2 `275` 结构：12 bars 时间退出

```text
5m + close profile + value_area_ratio 0.7 + breakout 4 ticks + POC + 12 bars + 1.5x 放宽 + 每日最多 1 笔
```

| id | symbol | trades | win rate | avg win | avg loss | net pnl | max drawdown | 结论 |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `275` | `DCE.m2601` | 52 | 52.17% | 878.33 | 430.91 | +1,368.95 | -3,088.44 | 主品种最佳 |
| `280` | `CZCE.SR601` | 56 | 61.54% | 475.00 | 371.00 | -777.97 | -2,500.97 | 接近但仍负 |
| `281` | `DCE.c2601` | 38 | 73.33% | 322.73 | 992.50 | -4,891.94 | -5,517.54 | 胜率高但尾部亏损压垮 |
| `282` | `DCE.cs2601` | 38 | 55.56% | 222.50 | 694.38 | -10,974.61 | -10,974.61 | 明显失败 |
| `283` | `SHFE.rb2601` | 52 | 53.85% | 429.29 | 815.00 | -11,212.75 | -12,340.39 | 明显失败 |

观察：

1. 主品种最佳结构不能跨品种转正，5 个品种中只有 `DCE.m2601` 为正。
2. `CZCE.SR601` 接近盈亏平衡，但仍为负；其余品种亏损明显。
3. `DCE.c2601` 出现高胜率但平均亏损远大于平均盈利，说明失败边界并未稳定限制尾部。
4. `DCE.cs2601`、`SHFE.rb2601` 对同结构极不友好，跨品种一致性不成立。

### 4.4 exit reason 分解

选取主品种最佳组和跨品种确认组：

| id | symbol / 结构 | reason | 次数 | gross pnl | commission | 观察 |
| ---: | --- | --- | ---: | ---: | ---: | --- |
| `275` | `DCE.m2601` / 12 bars | `take_profit` | 16 | +6,030 | 494.37 | POC 止盈确实贡献主要正收益 |
| `275` | `DCE.m2601` / 12 bars | `time_exit` | 6 | -2,120 | 185.82 | 未触达 POC 后时间退出偏负 |
| `275` | `DCE.m2601` / 12 bars | `strict_failure_close` | 1 | -1,690 | 37.04 | 单次失败足以侵蚀多笔盈利 |
| `280` | `CZCE.SR601` / 12 bars | `take_profit` | 17 | +5,310 | 700.31 | 止盈有效，但成本后仍不足 |
| `281` | `DCE.c2601` / 12 bars | `take_profit` | 11 | +2,370 | 430.40 | 盈利单笔太小 |
| `281` | `DCE.c2601` / 12 bars | `stop_loss` | 1 | -2,200 | 49.15 | 单次止损接近吞掉全部止盈 |
| `282` | `DCE.cs2601` / 12 bars | `take_profit` | 10 | +1,675 | 841.56 | 成本占比过高 |
| `283` | `SHFE.rb2601` / 12 bars | `strict_failure_close` | 5 | -6,500 | 464.51 | 严格失败频繁且幅度大 |

## 5. 关键诊断

| 诊断项 | 当前结果 | 含义 |
| --- | --- | --- |
| 候选区间是否客观 | 通过 | VAH / VAL / POC 可由前日 K 线和成交量分布客观计算 |
| 严格失败边界是否清晰 | 通过 | 假突破极值外加 buffer 可定义严格失败边界 |
| 盈利上界是否可定义 | 通过 | POC 是可预先定义且最有效的短期盈利上界 |
| 价格原始盈亏比 | 局部通过 | 主品种 `275` 的 POC 目标可兑现，但对侧边缘和 R 倍数目标失败 |
| 账户原始盈亏比 | 未通过 | 正收益只出现在单一主品种，且安全边际薄 |
| 接受 / 拒绝质量 | 偏弱 | POC 止盈贡献正收益，但失败边界在多品种不能稳定限制尾部亏损 |
| 止损放宽效果 | 风险较高 | 主品种转正依赖 `1.5x` 放宽，严格止损下不稳定 |
| 成本空间 | 未通过 | 多品种中成本吞噬明显，`DCE.cs2601` 的 POC 止盈 gross pnl 仅 `1,675`，手续费已 `841.56` |
| 跨品种一致性 | 未通过 | 最佳结构迁移到 4 个品种全部为负 |
| 参数邻域 | 未通过 | `value_area_ratio` 0.6 / 0.8、1m、breakout 6、range profile 均退化 |
| 尾部风险 | 未通过 | `DCE.c2601`、`SHFE.rb2601` 单次止损 / strict failure 可吞掉多笔止盈 |

失败层级：

```text
共识边界和盈利上界可以定义
→ POC 作为盈利上界在 DCE.m2601 局部有效
→ 但有效性依赖 close profile + 0.7 价值区 + 4 ticks + 1.5x 放宽 + 特定时间退出
→ 参数邻域不稳定
→ 跨品种无法转正
→ 尾部亏损和成本吞噬使账户口径不成立
```

## 6. 临时结论

### 6.1 第一阶段判断

当前判断：

```text
前日价值区边缘接受 / 拒绝方向，比 IB 和前日高低点更接近结构型 alpha，但本轮仍未通过。
```

主要证据：

1. 主品种 `DCE.m2601` 的 `close profile + POC` 结构出现局部正收益，说明 VAH / VAL / POC 比纯极值边界更有诊断价值。
2. 但正收益只在少数组合中出现，且安全边际很薄：`268` 仅 `+98.79`，`275` 为 `+1,368.95`，最大回撤约 `-3,088.44`。
3. 跨品种确认失败：`275` 结构迁移到 `CZCE.SR601`、`DCE.c2601`、`DCE.cs2601`、`SHFE.rb2601` 全部为负。
4. 参数邻域不稳定：价值区比例、profile 口径、突破深度、1m 周期、对侧边缘目标和 R 倍数目标均没有形成稳定平台。
5. 本轮不进入 Optuna / Walk-Forward。

阶段动作：

| 动作 | 结论 | 说明 |
| --- | --- | --- |
| 继续围绕同一入口微调 | 暂停 | 已完成 profile、突破深度、止损放宽、目标、时间退出、跨品种确认 |
| 保留策略代码 | 暂时保留 | 方向虽未通过，但比前两轮更接近有效结构，代码可用于后续更强接受 / 拒绝证据实验 |
| 下一步若继续价值区方向 | 只做结构升级 | 不能继续调参数；必须增加更强的接受 / 拒绝定义，例如二次测试失败、边界外停留时间、回到 POC 前的 MAE 限制等 |
| 是否换候选区间 | 倾向换 | 可考虑“密集成交区边缘 / 支撑阻力边缘”，但需避免主观画线和参数叠加 |

### 6.2 深挖：接受质量过滤

第一阶段失败后，没有继续做大规模参数搜索，而是只验证“接受质量”是否能解释收益来源并压住尾部亏损。

新增过滤参数：

| 参数 | 含义 | 结构问题 |
| --- | --- | --- |
| `min_reaccept_ticks` | 重新接受后必须回到 VAH / VAL 内侧至少 N ticks | 排除刚好贴边收回、接受质量弱的样本 |
| `max_breakout_bars` | 边界外突破状态最多持续 N 根 K | 排除边界外停留太久、可能已经真实接受新区间的样本 |
| `min_target_ticks` | 入场到 POC 至少 N ticks | 排除盈利上界太近、容易被成本吞噬的样本 |
| `min_price_raw_rr` | 入场到 POC / 入场到严格失败边界的最低价格原始盈亏比 | 排除价格空间不足的样本 |

验证：

```text
ruff check workspace/strategies/value_area_reacceptance_strategy.py workspace/tests/strategies/test_value_area_reacceptance_strategy.py
ruff format --check workspace/strategies/value_area_reacceptance_strategy.py workspace/tests/strategies/test_value_area_reacceptance_strategy.py
uv run mypy workspace/strategies/value_area_reacceptance_strategy.py
uv run pytest workspace/tests/strategies/test_value_area_reacceptance_strategy.py --tb=short
```

结果：12 条局部单元测试通过。

#### 6.2.1 DCE.m2601 深挖对照

基准仍使用第一阶段主品种最佳结构：

```text
5m + close profile + value_area_ratio 0.7 + breakout 4 ticks + POC + 12 bars + 1.5x 放宽 + 每日最多 1 笔
```

| id | 新增过滤 | trades | win rate | avg win | avg loss | net pnl | max drawdown | 观察 |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `284` | `min_reaccept_ticks=1` | 52 | 52.17% | 878.33 | 430.91 | +1,368.95 | -3,088.44 | 与基准等价，1 tick 内侧过滤无效 |
| `285` | `min_reaccept_ticks=2` | 48 | 50.00% | 915.45 | 535.45 | +185.57 | -3,396.98 | 更深重新接受反而削弱 |
| `286` | `max_breakout_bars=1` | 16 | 28.57% | 2,030.00 | 868.00 | -1,838.71 | -3,354.43 | 过严，样本少且失败 |
| `287` | `max_breakout_bars=2` | 20 | 44.44% | 1,115.00 | 868.00 | -1,686.85 | -3,409.79 | 仍失败 |
| `288` | `min_target_ticks=6` | 28 | 46.15% | 1,183.33 | 527.14 | +1,074.26 | -2,157.99 | 降低回撤、保留正收益，但样本减少 |
| `289` | `min_target_ticks=8` | 22 | 50.00% | 1,300.00 | 636.00 | +1,281.20 | -1,850.74 | 回撤继续降低，样本更少 |
| `290` | `min_price_raw_rr=1.0` | 12 | 40.00% | 2,100.00 | 850.00 | +360.66 | -1,850.74 | 样本过少，不能独立支撑结论 |
| `291` | `min_reaccept_ticks=1 + max_breakout_bars=1` | 16 | 28.57% | 2,030.00 | 868.00 | -1,838.71 | -3,354.43 | 与 `max_breakout_bars=1` 等价失败 |
| `292` | `min_reaccept_ticks=1 + min_target_ticks=6` | 28 | 46.15% | 1,183.33 | 527.14 | +1,074.26 | -2,157.99 | 与 `min_target_ticks=6` 等价 |
| `293` | `max_breakout_bars=1 + min_target_ticks=6` | 10 | 25.00% | 1,400.00 | 936.67 | -2,484.37 | -2,484.37 | 过度过滤失败 |
| `294` | 三过滤叠加 | 10 | 25.00% | 1,400.00 | 936.67 | -2,484.37 | -2,484.37 | 过度过滤失败 |

观察：

1. 真正有效的过滤不是“更深重新接受”或“边界外停留更短”，而是 **入场到 POC 的可捕获空间**。
2. `min_target_ticks=6/8` 把交易数从 52 降到 28/22，同时把最大回撤从约 `-3,088` 降到 `-2,158` / `-1,851`，说明成本空间过滤有结构意义。
3. 但主品种净利润没有显著放大，仍在 `+1,000` 左右，不是强 alpha。
4. `max_breakout_bars` 过滤显著恶化，说明“边界外只停留很短”不是本样本中的优势来源。

#### 6.2.2 跨品种确认

采用两个相对有意义的过滤结构：

```text
A: 基准 + min_target_ticks=6
B: 基准 + min_target_ticks=8
```

| id | symbol | 过滤 | trades | win rate | avg win | avg loss | net pnl | max drawdown | 结论 |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `288` | `DCE.m2601` | `min_target_ticks=6` | 28 | 46.15% | 1,183.33 | 527.14 | +1,074.26 | -2,157.99 | 主品种仍正，回撤改善 |
| `295` | `CZCE.SR601` | `min_target_ticks=6` | 28 | 61.54% | 597.50 | 338.00 | +804.74 | -1,154.88 | 从负转正，改善明显 |
| `296` | `DCE.c2601` | `min_target_ticks=6` | 4 | 100.00% | 365.00 | 0.00 | +202.81 | -78.81 | 转正但样本极少 |
| `297` | `DCE.cs2601` | `min_target_ticks=6` | 4 | 50.00% | 480.00 | 240.00 | -592.01 | -658.85 | 仍负，样本极少 |
| `298` | `SHFE.rb2601` | `min_target_ticks=6` | 32 | 43.75% | 632.86 | 934.44 | -8,760.97 | -10,595.54 | 明显失败 |
| `289` | `DCE.m2601` | `min_target_ticks=8` | 22 | 50.00% | 1,300.00 | 636.00 | +1,281.20 | -1,850.74 | 主品种仍正，回撤继续改善 |
| `299` | `CZCE.SR601` | `min_target_ticks=8` | 24 | 54.55% | 661.67 | 266.00 | +651.57 | -1,103.46 | 仍正 |
| `300` | `DCE.c2601` | `min_target_ticks=8` | 4 | 100.00% | 380.00 | 0.00 | +187.99 | -93.63 | 转正但样本极少 |
| `301` | `DCE.cs2601` | `min_target_ticks=8` | 0 | - | - | - | 0.00 | 0.00 | 无评价样本 |
| `302` | `SHFE.rb2601` | `min_target_ticks=8` | 22 | 45.45% | 590.00 | 795.00 | -4,946.94 | -6,781.51 | 仍明显失败但较 `min_target_ticks=6` 减亏 |

exit reason 分解显示：

| id | symbol / 过滤 | reason | 次数 | gross pnl | commission | 观察 |
| ---: | --- | --- | ---: | ---: | ---: | --- |
| `288` | `DCE.m2601` / 6 ticks | `take_profit` | 5 | +6,100 | 152.24 | 少量 POC 止盈贡献主要收益 |
| `289` | `DCE.m2601` / 8 ticks | `take_profit` | 4 | +5,500 | 123.78 | 更强空间过滤后收益更集中 |
| `295` | `CZCE.SR601` / 6 ticks | `take_profit` | 4 | +2,850 | 167.23 | 过滤后可转正 |
| `299` | `CZCE.SR601` / 8 ticks | `take_profit` | 3 | +2,370 | 132.75 | 仍能保持正收益 |
| `298` | `SHFE.rb2601` / 6 ticks | `strict_failure_close` | 4 | -5,460 | 367.19 | 失败边界频繁吞噬收益 |
| `302` | `SHFE.rb2601` / 8 ticks | `strict_failure_close` | 2 | -2,600 | 171.18 | 减亏但仍不能转正 |

### 6.3 深挖后判断

深挖后的判断需要从“未通过但有线索”升级为：

```text
价值区边缘方向存在更明确的结构线索：
有效部分不是单纯重新接受，而是“重新接受后到 POC 有足够可捕获空间”。
```

但它仍未达到通过标准：

1. `min_target_ticks` 过滤能让 `DCE.m2601` 和 `CZCE.SR601` 同时转正，这是本轮最有价值的新证据。
2. `DCE.c2601` 转正但样本只有 4 条，不能作为有效跨品种证据。
3. `DCE.cs2601` 无样本或略负，无法评价。
4. `SHFE.rb2601` 在两个过滤组下仍明显亏损，说明该结构对部分品种的失败边界质量很差。
5. 收益主要由少数 `take_profit` 贡献，交易机会明显减少，尚未形成稳定平台。

阶段结论：

```text
当前入口不应直接进入 Optuna / Walk-Forward。
但价值区方向值得再深挖一轮，重点从“接受质量”进一步收敛到“POC 空间 + 品种适配 + 失败边界质量”。
```

建议下一步不再继续微调 `min_target_ticks`，而是做一个更明确的新问题：

```text
structural-alpha-r4-value-area-poc-space

只研究：
VAH / VAL 重新接受后，入场到 POC 的空间足够大时，
哪些品种 / 哪些价值区形态能稳定把 POC 空间兑现，
并且失败边界不会被单次 strict failure 吞掉多笔盈利。
```

r4 最小预筛应先做：

```text
POC 距离分桶
→ strict failure 距离分桶
→ price_raw_rr 分桶
→ 按品种统计 POC 命中率、strict failure 率、time_exit 期望
→ 若分桶后只有 DCE.m / SR 有效，则把结论定位为品种结构适配，而不是通用 alpha
```

### 6.4 再深挖：POC 空间与价格原始盈亏比分桶

现有 `backtest_trades` 没有持久化 `signal.diagnostics`，因此本轮先用轻量方式把入场时诊断编码进 exit reason：

```text
<exit_reason>|td=<target_distance_bucket>|rr=<price_raw_rr_bucket>
```

分桶定义：

| 字段 | 分桶 |
| --- | --- |
| `td` | `lt6`、`6_8`、`8_12`、`ge12` |
| `rr` | `lt0_5`、`0_5_1`、`1_1_5`、`ge1_5` |

基准回测重新跑 5 个品种，不加 `min_target_ticks`，以便观察完整样本中的空间分布：

| id | symbol | trades | win rate | net pnl | max drawdown |
| ---: | --- | ---: | ---: | ---: | ---: |
| `303` | `DCE.m2601` | 52 | 52.17% | +1,368.95 | -3,088.44 |
| `304` | `CZCE.SR601` | 56 | 61.54% | -777.97 | -2,500.97 |
| `305` | `DCE.c2601` | 38 | 73.33% | -4,891.94 | -5,517.54 |
| `306` | `DCE.cs2601` | 38 | 55.56% | -10,974.61 | -10,974.61 |
| `307` | `SHFE.rb2601` | 52 | 53.85% | -11,212.75 | -12,340.39 |

#### 6.4.1 单条件过滤结果

| filter | symbol | trades | net after commission | wins | losses | 观察 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `target_ge6` | `DCE.m2601` | 12 | +2,694.43 | 5 | 6 | 正，但胜率一般 |
| `target_ge6` | `CZCE.SR601` | 11 | +3,528.90 | 7 | 3 | 明显改善 |
| `target_ge6` | `DCE.c2601` | 2 | +641.38 | 2 | 0 | 样本太少 |
| `target_ge6` | `DCE.cs2601` | 1 | -329.46 | 0 | 1 | 不可评价 |
| `target_ge6` | `SHFE.rb2601` | 15 | -6,012.34 | 6 | 9 | 仍失败 |
| `target_ge8` | `DCE.m2601` | 9 | +4,882.01 | 5 | 3 | 最强空间过滤明显改善 |
| `target_ge8` | `CZCE.SR601` | 10 | +3,083.38 | 6 | 3 | 继续为正 |
| `target_ge8` | `DCE.c2601` | 1 | +520.78 | 1 | 0 | 样本太少 |
| `target_ge8` | `SHFE.rb2601` | 11 | -2,758.24 | 5 | 6 | 明显减亏但仍负 |
| `rr_ge05` | `DCE.m2601` | 10 | +5,604.98 | 5 | 4 | RR 过滤非常强 |
| `rr_ge05` | `CZCE.SR601` | 11 | +4,514.15 | 8 | 3 | RR 过滤非常强 |
| `rr_ge05` | `DCE.c2601` | 5 | +888.69 | 3 | 0 | 样本少但方向一致 |
| `rr_ge05` | `DCE.cs2601` | 3 | -865.43 | 1 | 2 | 仍失败 |
| `rr_ge05` | `SHFE.rb2601` | 18 | -4,673.40 | 9 | 9 | 减亏但仍负 |

#### 6.4.2 组合过滤结果

| filter | symbol | trades | net after commission | wins | losses | 观察 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `target_ge8_rr_ge05` | `DCE.m2601` | 8 | +4,710.51 | 4 | 3 | 显著强于原始全样本 |
| `target_ge8_rr_ge05` | `CZCE.SR601` | 9 | +3,100.97 | 6 | 3 | 显著强于原始全样本 |
| `target_ge8_rr_ge05` | `DCE.c2601` | 1 | +520.78 | 1 | 0 | 样本太少 |
| `target_ge8_rr_ge05` | `SHFE.rb2601` | 11 | -2,758.24 | 5 | 6 | 仍失败 |
| `target_ge8_rr_ge1` | `DCE.m2601` | 5 | +2,887.31 | 2 | 2 | 更严后收益仍正但样本太少 |
| `target_ge8_rr_ge1` | `CZCE.SR601` | 4 | +825.90 | 2 | 2 | 样本太少，优势下降 |
| `target_ge8_rr_ge1` | `DCE.c2601` | 1 | +520.78 | 1 | 0 | 不可评价 |
| `target_ge8_rr_ge1` | `SHFE.rb2601` | 9 | -737.53 | 5 | 4 | 大幅减亏但仍负 |

#### 6.4.3 exit reason 分解

在更严格的 `target_ge8_rr_ge1` 下：

| symbol | exit reason | trades | net after commission | wins | losses | 观察 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `DCE.m2601` | `take_profit` | 2 | +4,124.06 | 2 | 0 | POC 命中贡献主要收益 |
| `DCE.m2601` | `time_exit` | 3 | -1,236.74 | 0 | 2 | 未命中 POC 的时间退出拖累 |
| `CZCE.SR601` | `take_profit` | 1 | +722.85 | 1 | 0 | POC 命中有效但样本少 |
| `CZCE.SR601` | `time_exit` | 3 | +103.04 | 1 | 2 | 时间退出接近持平 |
| `SHFE.rb2601` | `take_profit` | 2 | +2,012.76 | 2 | 0 | POC 命中也有效 |
| `SHFE.rb2601` | `strict_failure_close` | 1 | -1,395.93 | 0 | 1 | 单次失败侵蚀明显 |
| `SHFE.rb2601` | `time_exit` | 5 | -738.55 | 3 | 2 | 未命中 POC 的路径质量不足 |

### 6.5 再深挖后判断

本轮把线索进一步收窄：

```text
VAH / VAL 重新接受本身不是 alpha；
POC 空间足够大也不是单独充分条件；
更有效的是：POC 空间足够大 + 价格原始盈亏比不太差。
```

当前最有价值的结构线索是：

```text
target_distance >= 8 ticks
且 price_raw_rr >= 0.5
```

它能让：

```text
DCE.m2601: +4,710.51 / 8 笔
CZCE.SR601: +3,100.97 / 9 笔
DCE.c2601: +520.78 / 1 笔
SHFE.rb2601: -2,758.24 / 11 笔
```

判断：

1. `DCE.m2601` 和 `CZCE.SR601` 已经从“局部刚转正”升级成“空间分桶后有明显正收益”。
2. `SHFE.rb2601` 在空间 / RR 过滤后大幅减亏，但仍不能转正，失败来自 `strict_failure_close` 和 `time_exit`，不是 POC 不可达本身。
3. `DCE.c2601`、`DCE.cs2601` 样本太少，不支持判断。
4. 这个方向 **仍不适合直接 Optuna**，但已经值得进入 r4：专门研究 POC 空间分桶、路径质量和品种适配。

下一轮不应该继续问：

```text
min_target_ticks 到底取 6、7、8、9？
```

而应该问：

```text
在 target_distance >= 8 且 price_raw_rr >= 0.5 的样本里，
哪些入场后的早期路径特征能过滤掉 time_exit 和 strict_failure？
```

候选路径诊断：

```text
入场后 1~2 根 K 是否先向 POC 推进
入场后 MAE 是否小于 strict_distance 的某个比例
重新接受后的第一根 K 是否收在价值区内侧而非边缘
POC 是否位于价值区中部而不是贴近 VAH / VAL
分品种确认：只把 DCE.m / SR 作为当前有效候选，不强行通用化到 rb
```

