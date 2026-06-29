# Pre-trade 风险预算与仓位规划

> 类型：Workbench / Pre-trade Risk 规划草案  
> 状态：草案  
> 创建日期：2026-06-29  
> 来源：由 [structural-alpha-r1 工程支撑总览](overview.md) 拆分  
> 文档边界：本文只规划交易前风险预算、最小手数可交易性与仓位 sizing；不定义 Alpha 结构、不模拟成交退出、不做清算账务和绩效报告。

## 1. 定位

本模块用于在回测或执行前判断一个结构候选是否具备最低可交易性。

核心问题：

```text
给定入场价、严格失败边界、盈利上界和账户风险预算，
这笔结构交易是否能以最小手数和合约乘数约束执行？
```

它对应量化系统中的：

```text
Pre-trade Risk Check / Position Sizing / Risk Engine
```

注意：这不是清算系统。清算系统处理成交后的账务、持仓、成本和 PnL；本模块处理成交前的风险预算和下单规模。

## 2. 目标

- 在进入回测或参数对照前拒绝不可交易结构；
- 将严格失败距离映射到账户风险金额；
- 计算理论手数与实际可下单手数；
- 判断 2%~3% 单次账户风险是否可执行；
- 输出结构化拒绝原因，避免把不可交易结构误判为策略失败。

## 3. 输入

建议输入来自 Alpha 层和账户 / 合约配置。

| 输入 | 来源 | 说明 |
|------|------|------|
| `entry_price` | Alpha / Execution plan | 计划入场价格 |
| `strict_failure_boundary` | Alpha | 严格失败边界 |
| `expected_profit_boundary` | Alpha | 预期盈利上界 |
| `direction` | Alpha | long / short |
| `account_equity` | Account state / config | 账户权益 |
| `target_risk_ratio` | Risk config | 目标风险比例，例如 0.02 或 0.03 |
| `contract_multiplier` | Instrument metadata | 合约乘数 |
| `min_volume` | Instrument metadata | 最小手数 |
| `commission_estimate` | Cost model | 交易前手续费估算 |
| `slippage_estimate` | Cost model | 交易前滑点估算 |
| `gap_buffer` | Risk config | 跳空或超价缓冲 |

## 4. 输出

建议形成独立的 `RiskBudgetDecision` 模型。

| 输出 | 说明 |
|------|------|
| `strict_failure_distance` | 严格失败距离 |
| `expected_profit_distance` | 盈利上界距离 |
| `raw_price_r_multiple` | 价格原始盈亏比 |
| `target_risk_amount` | 目标账户风险金额 |
| `loss_per_min_volume` | 最小手数失败损失 |
| `theoretical_volume` | 理论手数 |
| `actual_volume` | 实际手数 |
| `account_risk_amount` | 实际风险金额 |
| `account_risk_ratio` | 实际风险比例 |
| `raw_account_r_multiple` | 账户原始盈亏比 |
| `risk_budget_passed` | 风险预算是否通过 |
| `risk_budget_reject_reason` | 不通过原因 |

## 5. 拒绝条件

预筛至少应能拒绝：

1. 严格失败边界为空；
2. 盈利上界为空；
3. 严格失败距离小于等于 0；
4. 盈利上界距离小于等于 0；
5. 价格原始盈亏比不足；
6. 最小手数下账户风险超过目标风险比例；
7. 滑点、手续费或跳空缓冲后成本空间不足；
8. 理论手数低于最小手数；
9. 账户原始盈亏比不足。

拒绝原因应使用枚举值，不使用自由文本作为主数据。

## 6. 计算边界

### 6.1 本模块负责

- 价格距离；
- 价格原始 R；
- 账户风险金额；
- 理论手数；
- 实际手数；
- 账户风险比例；
- 预估成本对可交易性的影响。

### 6.2 本模块不负责

- Alpha 结构是否成立；
- 成交是否真实发生；
- 实际手续费、实际滑点；
- 成交配对；
- realized / unrealized PnL；
- 绩效统计和图表。

## 7. 与其他模块的关系

```text
StructureCandidate
→ RiskBudgetDecision
→ ExecutionOrderPlan
```

| 上下游 | 关系 |
|--------|------|
| Alpha Research | 提供结构边界和方向 |
| Execution / Backtest | 消费 `actual_volume`、风险边界和拒绝结果 |
| Clearing / Accounting | 不直接依赖本模块结果，但可用于事后校验风险暴露 |
| Analytics / Report | 聚合通过率、拒绝原因、账户原始 R 分布 |

## 8. 第一阶段实施顺序

1. 定义 `RiskBudgetDecision` 数据模型；
2. 实现风险预算预筛函数；
3. 补充单元测试，覆盖拒绝条件；
4. 在 structural-alpha 回测入口前调用预筛；
5. 将预筛结果写入 trade / run artifact；
6. 报告层后续只读取预筛 artifact，不重复计算。

## 9. 验收标准

- 预筛失败的结构不会进入参数搜索或执行模拟；
- 风险预算计算可以解释最小手数、合约乘数、滑点和手续费估算影响；
- 拒绝原因结构化、可统计；
- 同一结构在不同账户权益下能得到不同 sizing 结果；
- 本模块不计算成交后 PnL；
- 报告层可以复用 `RiskBudgetDecision` 做通过率和分布展示。
