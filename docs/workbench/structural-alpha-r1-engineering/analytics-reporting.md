# 结构型 Alpha 分析、报告与 Diff 规划

> 类型：Workbench / Analytics & Reporting 规划草案  
> 状态：草案  
> 创建日期：2026-06-29  
> 来源：由 [structural-alpha-r1 工程支撑总览](overview.md) 拆分  
> 文档边界：本文只规划研究分析、报告展示、结果 diff 与归因入口；不定义 Alpha 结构、不做风险预算、不模拟成交、不计算清算账务。

## 1. 定位

本模块负责把 Alpha、风险预算、执行诊断和清算账务的结果聚合成研究判断。

它对应量化系统中的：

```text
Performance Analytics / Attribution / Research Reporting
```

核心原则：

```text
报告层不产生新事实，只消费上游 artifact 做聚合、展示和比较。
```

## 2. 目标

- 新增结构型 Alpha 研究视图；
- 展示风险预算是否可执行；
- 展示价格 / 账户原始 R 分布；
- 展示 MAE / MFE、快速再触及率和 exit reason；
- 对比不同退出结构的胜率 / 盈亏比转化效率；
- 判断胜率提升是否覆盖盈亏比下降和成本；
- 为后续归因和蒙特卡洛提供数据入口。

## 3. 输入 artifact

| 输入 | 来源 | 用途 |
|------|------|------|
| `StructureCandidate` | Alpha Research | 结构标签、边界、方向、证据 |
| `RiskBudgetDecision` | Pre-trade Risk | 通过率、拒绝原因、账户原始 R |
| `ExecutionTradeDiagnostics` | Execution / Backtest | MAE / MFE、exit reason、holding bars |
| `ClearingTradeLedger` | Clearing / Accounting | gross / net PnL、commission、slippage |
| run metadata | Backtest / CLI | 参数、时间、symbol、run id |

## 4. 报告模块

建议结构型 Alpha 报告包括：

1. 实验概览；
2. 账户风险预算预筛摘要；
3. 价格原始盈亏比分布；
4. 账户原始盈亏比分布；
5. 严格失败距离分布；
6. 盈利上界距离分布；
7. MAE / MFE 分布；
8. 严格边界快速再触及率；
9. exit reason 分布；
10. 成本后胜率、盈亏比、盈亏平衡胜率、胜率安全边际；
11. 最大单笔亏损、连续亏损和亏损簇；
12. 三类退出结构对照表。

## 5. 报告判断顺序

报告页面不应只突出收益曲线，应按以下顺序展示：

```text
风险预算是否可执行
→ 严格失败边界是否清楚
→ 盈利上界是否足够
→ 价格 / 账户原始盈亏比是否足够
→ 快速再触及率是否可接受
→ 接受 / 拒绝质量是否足够
→ 出口结构是否改善成本后期望
→ 尾部亏损是否可承受
→ 收益指标
```

## 6. 转化效率字段

建议形成 `ResearchAnalyticsSummary` 或 `ExitPolicyComparison` 模型。

| 字段 | 说明 |
|------|------|
| `exit_policy` | strict、take_profit、time_exit、relaxed_stop 等 |
| `cost_adjusted_win_rate` | 成本后胜率 |
| `cost_adjusted_payoff_ratio` | 成本后盈亏比 |
| `breakeven_win_rate` | 盈亏平衡胜率 |
| `win_rate_margin` | 胜率安全边际 |
| `conversion_efficiency` | 胜率 / 盈亏比转化效率 |
| `max_single_loss` | 最大单笔亏损 |
| `max_consecutive_losses` | 最大连续亏损 |
| `loss_cluster_summary` | 亏损簇摘要 |

## 7. Diff 工具

### 7.1 对比对象

优先支持：

- 严格失败退出 vs 主动止盈；
- 严格失败退出 vs 时间退出；
- 严格失败退出 vs 止损放宽 + 同步降仓；
- 同一结构在相邻边界参数下的结果。

### 7.2 对比字段

| 字段 | 目的 |
|------|------|
| 交易次数变化 | 判断样本是否可比 |
| 胜率变化 | 判断表面胜率提升 |
| 成本后盈亏比变化 | 判断胜率是否通过牺牲盈亏比换来 |
| 盈亏平衡胜率变化 | 判断最低胜率门槛 |
| 胜率安全边际变化 | 判断是否有安全边际 |
| 平均账户盈利变化 | 判断盈利质量 |
| 最大单笔亏损变化 | 判断尾部风险 |
| 最大连续亏损变化 | 判断亏损簇 |
| exit reason 分布变化 | 判断退出结构是否按预期工作 |
| 快速再触及率变化 | 判断是否只是用放宽止损购买噪声 |

## 8. 与其他模块的边界

| 内容 | 报告层可做 | 报告层不做 |
|------|------------|-------------|
| Alpha | 展示结构标签、边界、证据 | 重新生成共识价格区间 |
| Risk | 聚合通过率、拒绝原因 | 重新计算 actual volume |
| Execution | 聚合 MAE / MFE、exit reason | 重新模拟退出 |
| Clearing | 聚合 net PnL、成本、权益曲线 | 重新计算手续费和滑点 |

## 9. Artifact 和 Schema 原则

- report JSON 应原样包含上游结构化字段；
- 字段缺失应显式为 `null`；
- 前端只负责格式化和图表展示；
- 不使用 markdown 表格作为数据源；
- 不让不同策略自由拼接字段名；
- 指标聚合逻辑应可测试。

## 10. 第一阶段实施顺序

1. 报告 JSON 导出结构诊断字段；
2. 增加风险预算预筛摘要；
3. 增加 exit reason、MAE / MFE 分布；
4. 增加成本后胜率、盈亏比、盈亏平衡胜率；
5. 增加三类退出结构对照表；
6. 增加 run diff 工具；
7. 后续扩展归因和蒙特卡洛。

## 11. 验收标准

- 报告能展示结构诊断字段；
- diff 工具能回答胜率提升是否覆盖盈亏比下降和成本；
- 字段在 Python artifact、report JSON、前端展示之间语义一致；
- 报告层不重复计算清算账务；
- 报告判断顺序优先风险预算和结构解释，而不是收益曲线；
- 每轮实验至少能回答结构优势是否成立、是否可交易、是否有成本后安全边际。
