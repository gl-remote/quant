# 回测执行与交易诊断规划

> 类型：Workbench / Backtest Execution 规划草案  
> 状态：草案  
> 创建日期：2026-06-29  
> 来源：由 [structural-alpha-r1 工程支撑总览](overview.md) 拆分  
> 文档边界：本文只规划回测中的入场、退出、成交模拟和交易生命周期诊断；不定义 Alpha 结构、不做交易前风险预算、不承担清算账务和报告归因。

## 1. 定位

本模块用于把 Alpha 候选结构和风险预算决策转化为可回测的交易生命周期。

它对应量化系统中的：

```text
Execution Simulation / Backtest Engine / Trade Lifecycle Diagnostics
```

核心问题：

- 结构候选如何触发入场；
- 严格失败边界如何触发退出；
- 主动止盈、时间退出、止损放宽对照如何执行；
- 每笔交易经历了多少不利 / 有利波动；
- exit reason 是否符合预期。

## 2. 目标

- 实现 `structural-alpha-r1` 最小策略骨架；
- 支持严格失败边界退出；
- 支持主动止盈和时间退出对照；
- 支持有限止损放宽 + 同步降仓对照；
- 输出 MAE / MFE、holding bars、exit reason；
- 将交易生命周期诊断写入 artifact。

## 3. 输入

| 输入 | 来源 | 说明 |
|------|------|------|
| `StructureCandidate` | Alpha Research | 结构边界、方向、证据 |
| `RiskBudgetDecision` | Pre-trade Risk | 是否通过、实际手数、风险边界 |
| bar / tick data | DataFeed | 回测行情 |
| `exit_policy` | Strategy config | strict、take_profit、time_exit、relaxed_stop |
| cost model reference | Backtest config | 供成交模拟估算，不负责最终账务口径 |

## 4. 输出

建议形成独立的 `ExecutionTradeDiagnostics` 模型。

| 字段 | 说明 |
|------|------|
| `exit_policy` | strict、take_profit、time_exit、relaxed_stop 等 |
| `strict_stop_distance` | 严格失败距离 |
| `actual_stop_distance` | 实际止损距离 |
| `stop_relaxation_multiple` | 止损放宽倍数 |
| `position_adjustment_multiple` | 为维持风险预算所需仓位调整倍数 |
| `actual_volume` | 实际执行手数，来自风险预算 |
| `mae` | 最大不利波动 |
| `mfe` | 最大有利波动 |
| `mae_r` | MAE / 严格失败距离 |
| `mfe_r` | MFE / 严格失败距离 |
| `exit_reason` | strict_failure、take_profit、time_exit、relaxed_stop、abnormal 等 |
| `holding_bars` | 持仓 K 线数 |
| `fast_retouch` | 是否快速再触及严格边界 |

## 5. 最小对照组

每个候选结构至少输出三组对照：

| 对照 | 说明 |
|------|------|
| 严格失败边界退出 | 验证原始结构是否具备低验证成本和足够原始盈亏比 |
| 主动止盈 / 时间退出 | 验证是否能在盈利上界附近提高兑现质量 |
| 有限止损放宽 + 同步降仓 | 验证吸收噪声后胜率提升是否覆盖盈亏比下降和仓位下降 |

## 6. exit reason 契约

建议使用枚举：

| exit reason | 含义 |
|-------------|------|
| `strict_failure` | 严格失败边界触发 |
| `take_profit` | 预期盈利上界或主动止盈触发 |
| `time_exit` | 时间退出触发 |
| `relaxed_stop` | 放宽后的实际止损触发 |
| `abnormal` | 数据、成交或状态异常退出 |

## 7. 与清算系统的边界

执行 / 回测层可以产生成交事件和交易生命周期诊断，但不应拥有最终账务口径。

```text
Execution / Backtest
→ fills / trade lifecycle
→ Clearing / Accounting
→ gross_pnl / net_pnl / commission / slippage_cost / equity
```

本模块不负责：

- 统一手续费口径；
- 统一滑点成本口径；
- 成交配对后的 realized PnL；
- 账户权益曲线；
- 保证金和现金流水；
- 日终结算。

## 8. Artifact 建议

优先选择最小侵入方式：

1. 在回测 trade artifact 中增加 `execution_diagnostics` 字段；
2. 结构化记录 MAE / MFE、exit reason、holding bars；
3. 字段缺失显式为 `null`；
4. report writer 原样导出；
5. 后续查询需求稳定后再考虑数据库 schema 扩展。

不要：

- 把展示字符串写入 artifact；
- 依赖 markdown 表格作为数据源；
- 让不同策略自由拼接字段名。

## 9. 第一阶段实施顺序

1. 实现 `structural-alpha-r1` 最小策略骨架；
2. 接入 `StructureCandidate` 和 `RiskBudgetDecision`；
3. 支持严格失败边界退出；
4. 输出 `exit_reason` 和 `holding_bars`；
5. 计算 MAE / MFE 与 R 化指标；
6. 增加主动止盈和时间退出对照；
7. 增加有限止损放宽 + 同步降仓对照。

## 10. 验收标准

- 三类退出结构可以在同一候选区间下对比；
- 每笔 structural-alpha 交易都有结构化执行诊断；
- `exit_reason` 可枚举、可统计；
- MAE / MFE 和 R 化指标可复现；
- 执行层不自行定义最终净收益口径；
- 清算层可以消费成交事件并生成统一账务结果。
