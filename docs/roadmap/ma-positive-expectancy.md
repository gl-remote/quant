# MA 策略正期望优化规划

> 状态：进行中
> 开发分支：experiment/ma-positive-expectancy
> 开分支 hash：88d2563
> 实现提交 hash：1adf61a
> 目标版本：0.5.0-dev
> 最后更新：2026-06-26

## 一、目标

围绕现有 [ma_strategy.py](file:///Users/gaolei/Documents/src/quant/workspace/strategies/ma_strategy.py)，持续优化 MA baseline 的入场、出场、过滤和参数搜索机制，直到找到在多品种、多时间窗口、扣除交易成本后仍具备长期正期望的位置。

本任务不是追求单次回测最优，而是建立一套可重复的策略验证闭环：

1. 先修复会污染优化结果的退化解与统计口径问题；
2. 再用多品种、多窗口验证排除单品种偶然性；
3. 最后只保留在样本外和参数邻域中仍稳定的规则或参数组合。

## 二、验收标准

候选 MA 版本必须同时满足以下条件，才允许进入 paper trading 前置评估：

| 维度 | 最低要求 |
|------|----------|
| 样本范围 | 至少覆盖 3 个以上高流动性品种，且包含趋势和震荡品种 |
| 时间窗口 | 至少覆盖 3 个非重叠窗口，另做 walk-forward 验证 |
| 收益期望 | 扣除手续费和滑点后，总体期望为正 |
| 风险收益 | 综合夏普 ≥ 0.5，最大回撤 < 20% |
| 交易活跃度 | 排除零交易、极低交易次数、单笔收益主导的退化结果 |
| 参数鲁棒性 | 最优点附近参数邻域不能出现收益断崖 |
| 可解释性 | 每次改动必须能解释改善来源：入场、过滤、出场、仓位或成本敏感性 |

若 MA 无法满足上述标准，应明确记录失败原因，并将 MA 固化为工具链 baseline，不再继续消耗主线研发时间。

## 三、当前问题

| 问题 | 影响 | 处理优先级 |
|------|------|------------|
| 优化器会选择低交易活跃度退化解 | 污染最优参数，导致回测看似稳定但不可交易；2026-06-26 基线显示每条回测仅 1 笔交易 | P0 |
| 入场条件由多组 AND 条件隐式叠加 | 信号稀疏，且不同指标信息增量不清晰 | P0 |
| SMA、MACD、KDJ 条件存在相关性或逻辑冲突 | 过滤掉大量趋势段，保留的信号不一定更优 | P0 |
| 缺少趋势强度/波动率环境识别 | 震荡市假信号和低波动噪声交易较多 | P1 |
| 出场规则叠加但缺少归因统计 | 不知道收益改善来自固定止盈、ATR、移动止盈还是冷却期 | P1 |
| 交易成本敏感性不足 | 多数短周期信号可能被手续费和滑点吞噬 | P1 |
| 参数邻域稳定性未验证 | 容易选到尖峰最优和窗口过拟合 | P1 |

## 四、实施阶段

### 阶段 0：基线冻结与退化解修复

目标：确保后续优化建立在可信统计口径上。

- [x] 固定当前 MA baseline 版本、默认参数和回测命令。
- [x] 修复或规避优化器低交易活跃度退化解：加入最小交易次数、最小持仓活跃度或惩罚项。
- [ ] 报告中显式展示交易次数、平均持仓时间、成本占收益比例。
- [x] 对现有默认参数跑一次多品种基线，作为后续对照组。

阶段产物：baseline run 列表、失败/退化样本记录、修复后的优化目标定义。

### 阶段 0 实验记录

#### 2026-06-26：现有工具链最小基线

| 项目 | 结果 |
|------|------|
| 命令 | `uv run python main.py backtest --env backtest --pattern "DCE\\.m" --strategy ma --mode search --optimizer bayesian --trials 5 --early-stop-patience 0 --capital 100000 --contract-size 10` |
| 策略版本 | `v2.0.0-ma7` |
| Git hash | `88d2563` |
| Run ID | `3` |
| 回测 ID | `145` ~ `159` |
| 品种 | `DCE.m2601`、`DCE.m2603`、`DCE.m2605` |
| Trial 数 | 5 |
| 最优 score | `-22.1790` |
| 最优参数 | `atr_stop_loss_multiplier=2.6`、`atr_take_profit_multiplier=2.7`、`trailing_activation_atr=1.1`、`trailing_drawdown_ratio=0.1`、`kdj_oversold=26`、`kdj_overbought=62` |
| 平均收益率 | `-0.29%` |
| 收益范围 | `-8.18%` ~ `6.75%` |
| 平均夏普 | `-3.20` |
| 交易次数 | 每条回测均为 `1` 笔 |
| 平均手续费 | `133.31` |

结论：现有工具链能跑通多品种 MA 参数搜索，但当前结果不能作为正期望证据。所有 trial 在每个品种上都只有 1 笔交易，属于低交易活跃度退化样本；个别正收益和高夏普来自单笔持仓，统计意义不足。下一步不应继续扩大 trial 数，而应先修复优化目标和/或放宽信号结构，使优化器至少满足最小交易次数约束。

新增约束建议：

- 优化目标中加入 `min_total_trades`，低于阈值直接惩罚。
- 汇总多品种结果时同时惩罚“单品种收益主导”和“多数品种无交易/极少交易”。
- baseline 命令必须显式传 `--env backtest`；现有 `scripts/tools/backtest-ma.sh` 未传 env，后续应修正脚本或文档命令。

#### 2026-06-26：加入低交易活跃度惩罚后复跑

| 项目 | 结果 |
|------|------|
| 代码改动 | [optimizer.py](file:///Users/gaolei/Documents/src/quant/workspace/backtest/optimizer.py) 增加 `MIN_TRADES_PER_RESULT=10` 与 `calculate_optimization_score` |
| 测试 | `uv run pytest workspace/tests/backtest/test_optimizer.py --tb=short`，3 passed |
| 命令 | `uv run python main.py backtest --env backtest --pattern "DCE\\.m" --strategy ma --mode search --optimizer bayesian --trials 3 --early-stop-patience 0 --capital 100000 --contract-size 10` |
| Run ID | `4` |
| 回测 ID | `160` ~ `168` |
| Trial 数 | 3 |
| 得分 | 所有 trial 均为 `-999.0000` |
| 交易次数 | 每条回测仍为 `1` 笔 |
| 平均收益率 | `1.98%`，但无统计意义 |
| 平均夏普 | `-0.84` |

结论：优化器退化解保护生效，单笔交易结果不会再被当作可优化目标。但这也暴露出当前 MA 入场结构过严：在现有数据范围和参数空间内，优化器没有找到任何满足最小交易次数的候选。下一轮应进入阶段 1，先做信号结构拆解，而不是继续调整风控参数。

下一轮计划：

- 增加可配置的信号消融开关，至少支持仅 SMA、SMA+MACD、SMA+KDJ、SMA+MACD+KDJ。
- 优先让基线产生足够交易样本，再谈收益优化。
- 记录每组信号组合的交易次数、平均收益、平均夏普和成本占比。


### 阶段 1：信号结构拆解

目标：确认当前每个入场条件是否真的提供独立信息增量。

- [x] 增加可配置的信号消融开关，避免每次都改代码才能消融。
- [x] 分别运行以下消融实验：
  - 仅 SMA 趋势；
  - SMA + MACD；
  - SMA + KDJ；
  - SMA + MACD + KDJ；
  - 去掉 1m 或 5m 重复确认。
- [ ] 统计每个条件对交易次数、胜率、盈亏比、回撤和成本占比的影响。
- [x] 增加反向信号退出或换向机制，让消融实验能产生完整交易样本。
- [ ] 降低仓位和加入趋势/冷却过滤，控制反向退出导致的过度交易。

阶段产物：信号条件贡献表，明确保留/移除哪些条件。

### 阶段 1 实验记录

#### 2026-06-26：信号 profile 消融第一次尝试

代码改动：

- [ma_strategy.py](file:///Users/gaolei/Documents/src/quant/workspace/strategies/ma_strategy.py) 增加 `signal_profile`，支持 `sma_only` / `sma_macd` / `sma_kdj` / `full`。
- [persister.py](file:///Users/gaolei/Documents/src/quant/workspace/backtest/persister.py) 与 [config.py](file:///Users/gaolei/Documents/src/quant/workspace/strategies/utils/config.py) 过滤非数值策略参数，避免 `signal_profile` 这类实验标签写入 `backtest_params.param_value` 时失败。
- 测试：`uv run pytest workspace/tests/strategies/test_ma_strategy.py workspace/tests/backtest/test_optimizer.py --tb=short`，19 passed；相关文件 ruff 通过。

实验配置：

| profile | 配置文件 | run_id | backtest_id |
|---------|----------|--------|-------------|
| `sma_only` | `project_data/ma_ablation_sma_only.toml` | `8` | `178` ~ `180` |
| `sma_macd` | `project_data/ma_ablation_sma_macd.toml` | `9` | `181` ~ `183` |
| `sma_kdj` | `project_data/ma_ablation_sma_kdj.toml` | `10` | `184` ~ `186` |
| `full` | `project_data/ma_ablation_full.toml` | `11` | `187` ~ `189` |

统一参数：`sma_short=3`、`sma_long=10`、`position_ratio=1.0`、`stop_loss_ratio=0.3`、`take_profit_ratio=0.5`、ATR 止盈止损倍数均为 `5.0`，目的是先观察信号活跃度而不是优化收益。

结果汇总：

| profile | 品种结果 | 交易数 | 结论 |
|---------|----------|--------|------|
| `sma_only` | 三个品种收益均为正，约 `10.52%` ~ `14.51%` | 每品种 `1` 笔 | 只有开仓，不能视为稳定正期望 |
| `sma_macd` | 两亏一盈，约 `-15.73%` ~ `12.87%` | 每品种 `1` 笔 | MACD 过滤改变方向但未解决样本不足 |
| `sma_kdj` | 两亏一盈，约 `-13.81%` ~ `12.36%` | 每品种 `1` 笔 | KDJ 过滤未改善交易活跃度 |
| `full` | 三个品种收益均为正，约 `7.62%` ~ `13.89%` | 每品种 `1` 笔 | 看似正收益，但仍是单笔持仓样本 |

关键发现：消融后仍然每个品种只有一条 `open` 成交，没有对应平仓成交。问题不只是入场条件过严，而是 MA 当前只靠止盈止损出场，缺少“反向信号退出/换向”或更有效的时间退出机制。只放宽入场条件无法形成足够交易样本。

下一轮计划：

- 增加可配置的反向信号退出：持多时满足 short profile 则平多，持空时满足 long profile 则平空。
- 先不直接换向，避免同一 bar 平仓再开仓带来的撮合语义复杂化；先验证平仓交易次数是否恢复。
- 复跑四组 profile，重点观察完整交易数、成本占比和收益是否仍为正。

#### 2026-06-26：反向信号退出实验

代码改动：

- [ma_strategy.py](file:///Users/gaolei/Documents/src/quant/workspace/strategies/ma_strategy.py) 增加 `exit_on_reverse_signal`。
- 持多时满足当前 profile 的 short 方向 key 则 `reverse_short_exit`；持空时满足 long 方向 key 则 `reverse_long_exit`。
- 先只平仓，不在同一 bar 反手开仓。
- 测试：`uv run pytest workspace/tests/strategies/test_ma_strategy.py workspace/tests/backtest/test_optimizer.py --tb=short`，21 passed；相关文件 ruff 通过。

实验配置：沿用上一轮四个 `project_data/ma_ablation_*.toml`，统一增加 `exit_on_reverse_signal = true`。

结果汇总：

| profile | run_id | backtest_id | 总交易数 | 平均收益率 | 收益范围 | 平均手续费 | 结论 |
|---------|--------|-------------|----------|------------|----------|------------|------|
| `sma_only` | `12` | `190` ~ `192` | `1251` | `-161.83%` | `-251.42%` ~ `-51.19%` | `56321.91` | 交易数恢复，但严重过度交易并爆仓 |
| `sma_macd` | `13` | `193` ~ `195` | `265` | `-34.45%` | `-142.00%` ~ `19.70%` | `11631.19` | 两个品种正收益，但 DCE.m2601 爆仓拖垮整体 |
| `sma_kdj` | `14` | `196` ~ `198` | `35` | `-11.56%` | `-26.70%` ~ `12.36%` | `1529.91` | 交易数较合理，但整体仍为负 |
| `full` | `15` | `199` ~ `201` | `3` | `11.34%` | `7.62%` ~ `13.89%` | `133.25` | 仍几乎不退出，样本不足 |

关键发现：

- 反向信号退出可以恢复交易样本，但 `sma_only` 过于频繁，手续费和滑点迅速吞噬账户，甚至爆仓。
- `sma_macd` 有两个品种表现为正，但单个品种极端亏损，说明缺少市场环境过滤或仓位约束。
- `sma_kdj` 交易次数较合理但收益为负，暂不优先。
- `full` 仍是稀疏信号，不能作为统计证据。

下一轮计划：

- 以 `sma_macd + exit_on_reverse_signal` 作为候选方向继续，而不是 `sma_only`。
- 将 `position_ratio` 从 `1.0` 降到更接近实盘的 `0.1`，先排除杠杆/仓位导致的爆仓噪声。
- 增加最低趋势持续过滤或冷却期，减少 DCE.m2601 上的高频反复开平。
- 复跑时重点看：交易数是否 ≥ 10、最大回撤是否明显下降、成本占收益比例是否可接受。

### 阶段 2：趋势与波动过滤

目标：减少明显不适合 MA 的市场环境。

- [ ] 增加趋势强度过滤候选：ADX、均线斜率、价格通道斜率。
- [ ] 增加波动率过滤候选：ATR 分位数、近 N 日波动率分位数、极低波动剔除。
- [ ] 检查过滤器是否只是减少交易，还是真实改善单位风险收益。
- [ ] 分别验证过滤器对趋势品种与震荡品种的影响。

阶段产物：过滤器候选清单与入选标准。

### 阶段 3：出场与持仓管理优化

目标：让盈利来自可解释的持仓管理，而不是单次参数碰巧。

- [ ] 拆分固定止盈、固定止损、ATR 止盈止损、移动止盈、冷却期的贡献。
- [ ] 增加时间止损候选：持仓超过 N 根 K 线仍无收益则退出。
- [ ] 检查止盈止损参数对不同波动率品种是否需要归一化。
- [ ] 输出出场原因归因：每类出场的次数、平均收益、平均持仓时长。

阶段产物：出场规则贡献表，确定默认出场组合。

### 阶段 4：多品种、多窗口与参数鲁棒性验证

目标：排除单品种、单窗口和尖峰参数造成的假正期望。

- [ ] 选择至少 3 个高流动性品种，覆盖趋势和震荡特征。
- [ ] 每个品种至少跑 3 个非重叠窗口。
- [ ] 对候选参数做邻域扫描，输出参数热区而不是单点最优。
- [ ] 用 walk-forward 验证训练窗口参数在后续窗口中的表现。
- [ ] 对手续费和滑点做敏感性分析。

阶段产物：候选版本验收报告，决定 MA 是否进入 paper trading 前置评估。

## 五、优先改动范围

| 文件/模块 | 预期改动 |
|-----------|----------|
| [ma_strategy.py](file:///Users/gaolei/Documents/src/quant/workspace/strategies/ma_strategy.py) | 调整 MA 信号、过滤、出场组合；保留 baseline 可回滚 |
| [optimizer.py](file:///Users/gaolei/Documents/src/quant/workspace/backtest/optimizer.py) | 排除零交易退化解，加入活跃度/交易次数约束 |
| [test_ma_strategy.py](file:///Users/gaolei/Documents/src/quant/workspace/tests/strategies/test_ma_strategy.py) | 补充策略信号、风控、退化解保护测试 |
| [backtests_run.py](file:///Users/gaolei/Documents/src/quant/workspace/cli/workflows/backtests_run.py) | 如需，补充回测结果归因字段或日志 |
| [report](file:///Users/gaolei/Documents/src/quant/workspace/report) | 如需，展示条件贡献、出场归因、参数鲁棒性结果 |

## 六、记录要求

每轮实验至少记录：

- 策略版本号与代码提交；
- 回测命令、品种、窗口、手续费、滑点；
- 参数组合与搜索空间；
- 总收益、夏普、最大回撤、交易次数、成本占比；
- 与上一轮相比改善来自哪里；
- 是否进入下一阶段，若否，失败原因是什么。

## 七、风险与退出条件

| 风险 | 处理 |
|------|------|
| MA 本身结构性无效 | 允许失败；失败后将 MA 固化为 baseline，转向通道突破/布林带/RSI 等新策略 |
| 优化结果过拟合 | 以 walk-forward 和参数邻域稳定性作为硬门槛 |
| 成本吞噬收益 | 成本敏感性不过关则不进入下一阶段 |
| 过度堆叠规则 | 每个新增规则必须有消融实验支持，否则回滚 |

退出条件：连续两轮完整多品种、多窗口实验仍无法达到最低验收标准，暂停 MA 主线优化，仅保留必要 baseline 维护。
