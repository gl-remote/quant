# structural-alpha-r1 工程支撑总览

> 类型：Workbench / 工程规划总览  
> 状态：草案  
> 创建日期：2026-06-28  
> 拆分日期：2026-06-29  
> 关联 roadmap：[工程长期路线图](../../roadmap/engineering-roadmap.md)、[策略短期研究计划](../../roadmap/strategy-short-term-plan.md)、[策略长期共识](../../roadmap/strategy-research-framework.md)  
> 文档边界：本文只保留 `structural-alpha-r1` 工程支撑的总览、模块边界和实施顺序；具体设计已拆分到各子规划。

## 1. 背景

0.5 阶段的策略主线已经从指标型 baseline 调参转向结构型 Alpha 验证。当前研究重点不是寻找更复杂的预测信号，也不是扩大参数搜索，而是验证：

```text
共识价格区间
→ 明确失败边界
→ 可估算的短期盈利上界
→ 可执行的 2%~3% 单次账户风险
→ 足够的价格原始盈亏比和账户原始盈亏比
→ 可评估的胜率 / 盈亏比转化效率
→ 成本后长期正期望和安全边际
```

工程侧的首要目标是让每轮实验能稳定回答：

- 为什么进场；
- 共识价格区间是什么；
- 严格失败边界在哪里；
- 盈利上界在哪里；
- 账户风险预算是否可执行；
- 退出来自严格失败、主动止盈、时间退出还是实际止损；
- 胜率提升是否值得牺牲盈亏比和仓位；
- 收益来自结构本身，还是参数偶然性、成本口径或尾部风险遗漏。

## 2. 拆分原则

原规划不再维护一个大的 `structural diagnostics` schema，而是按量化系统常见职责拆成正交 artifact：

```text
Alpha 定义“该不该交易”
Risk 定义“能不能交易、下多少”
Execution 定义“如何成交、如何退出”
Clearing 定义“成交后账户怎么记账”
Analytics 定义“结果说明了什么”
```

对应行业分层：

```text
Research / Alpha
→ Portfolio Construction / Sizing
→ Pre-trade Risk
→ Execution / OMS / EMS / Backtest Simulation
→ Clearing / Accounting / Position Book
→ Performance / Attribution / Reporting
```

## 3. 子规划索引

| 模块 | 子文档 | 职责 |
|------|--------|------|
| Alpha Research | [alpha-research.md](alpha-research.md) | 定义共识价格区间、方向假设、严格失败边界、盈利上界和接受 / 拒绝证据 |
| Pre-trade Risk / Position Sizing | [pre-trade-risk.md](pre-trade-risk.md) | 判断结构候选是否满足账户风险预算，并计算实际可执行手数 |
| Execution / Backtest Diagnostics | [backtest-execution.md](backtest-execution.md) | 模拟入场、退出、MAE / MFE、exit reason 和交易生命周期 |
| Clearing / Accounting / PnL | [clearing-accounting.md](clearing-accounting.md) | 统一成交后成本、持仓、现金、gross / net PnL 和账户权益口径 |
| Analytics / Report / Diff | [analytics-reporting.md](analytics-reporting.md) | 聚合上游 artifact，生成结构报告、退出结构 diff 和研究判断 |

## 4. Artifact 拆分

建议逐步形成以下结构化对象：

| Artifact | 所属模块 | 说明 |
|----------|----------|------|
| `StructureCandidate` | Alpha Research | 结构候选、共识区间、方向、失败边界、盈利上界 |
| `RiskBudgetDecision` | Pre-trade Risk | 风险预算、理论手数、实际手数、拒绝原因 |
| `ExecutionTradeDiagnostics` | Execution / Backtest | MAE / MFE、exit reason、holding bars、退出策略 |
| `ClearingTradeLedger` | Clearing / Accounting | 成交配对、手续费、滑点、gross / net PnL |
| `ResearchAnalyticsSummary` | Analytics / Report | 胜率、盈亏比、盈亏平衡胜率、diff 和尾部风险摘要 |

字段应尽量使用数字、枚举和布尔值。展示格式化只在报告层处理，不在 artifact 层提前格式化。

### 4.1 当前技术选择

现阶段先不直接实现完整的 `StructureCandidate`、`RiskBudgetDecision` 和 `ExecutionTradeDiagnostics` 业务对象，而是先打通统一的决策事件载荷通道。

当前约定：

```text
Strategy.on_bar()
→ Signal.reason                  # 人类可读摘要
→ Signal.decision_payload          # 机器可读结构化上下文
→ Bridge order_id context          # 订单级归因
→ backtest trade artifact / DB
→ report / analytics / clearing context
```

技术选择如下：

1. `reason` 只保留人类摘要语义，不再作为结构化主数据载体；
2. `decision_payload` 作为策略决策事件的机器可读载荷；
3. `decision_payload` 使用统一 envelope：

```text
schema_version
source
event_type
diagnostics.strategy
diagnostics.aspects
diagnostics.alpha
diagnostics.risk
diagnostics.execution
```

4. `diagnostics.alpha` 预留给后续 `StructureCandidate`；
5. `diagnostics.risk` 预留给后续 `RiskBudgetDecision`；
6. `diagnostics.execution` 预留给后续 `ExecutionTradeDiagnostics`；
7. Bridge 内部运行时保持结构化对象，只在 vnpy / DB / report 边界序列化为 JSON 字符串；
8. Clearing 可以消费 `decision_payload` 作为交易上下文，但账务事实仍以成交记录、合约参数和成本模型为准。

这一选择的目的不是提前完成三个业务域，而是先固定跨策略、回测、清算和报告之间的结构化数据通道，避免继续把诊断信息散落在自然语言 `reason`、日志字符串或策略私有字段中。

## 5. 非目标

当前阶段不优先做：

- 大规模 Optuna / Bayesian search；
- Walk-Forward；
- 多体系复杂叠加；
- 通用策略脚手架；
- TqSdk 生命周期统一；
- Docker / 生产部署；
- 实盘风控通知；
- paper trading。

这些工作只有在结构型 Alpha 初步成立后再推进。

## 6. 总体优先级

| 优先级 | 工作项 | 所属模块 | 状态 |
|--------|--------|----------|------|
| P0 | 结构候选模型 | Alpha Research | 待做 |
| P0 | 账户风险预算预筛 | Pre-trade Risk | 待做 |
| P0 | `structural-alpha-r1` 最小策略骨架 | Execution / Backtest | 待做 |
| P0 | MAE / MFE、holding bars、exit reason | Execution / Backtest | 待做 |
| P0 | trade-level clearing ledger 最小口径 | Clearing / Accounting | 待做 |
| P1 | 结构诊断报告 | Analytics / Report | 待做 |
| P1 | 结果 diff 工具 | Analytics / Report | 待做 |
| P1 | 开盘区间、Initial Balance 等共识区间 | Alpha Research | 待做 |
| P2 | 归因和蒙特卡洛 | Analytics / Report | 后置 |
| P2 | position book、margin、daily settlement | Clearing / Accounting | 后置 |

## 7. 推荐实施顺序

```text
1. 定义 StructureCandidate
2. 实现 RiskBudgetDecision 与风险预算预筛函数
3. 给预筛补单元测试
4. 实现 structural-alpha-r1 最小策略骨架
5. 支持严格失败边界退出
6. 输出 MAE / MFE、holding bars 和 exit reason
7. 分离 execution_diagnostics 与 clearing_ledger
8. 建立最小 trade-level gross / net PnL 统一口径
9. 增加主动止盈和时间退出对照
10. 增加有限止损放宽 + 同步降仓对照
11. 报告 JSON 导出结构化 artifact
12. 前端增加结构诊断视图
13. 增加 run diff 工具
14. 扩展开盘区间和 Initial Balance 等共识区间特征
```

## 8. 总体验收标准

工程链路完成后，每轮实验至少能回答：

1. 共识价格区间是否客观；
2. 严格失败边界是否明确；
3. 盈利上界是否可估算；
4. 严格失败距离是否合理；
5. 价格原始盈亏比是否足够；
6. 账户风险预算是否可执行；
7. 账户原始盈亏比是否足够；
8. 快速再触及率是否过高；
9. 接受 / 拒绝质量是否足够；
10. 主动止盈、时间退出或止损放宽是否改善成本后期望；
11. 尾部亏损和亏损簇是否可承受；
12. 收益是否能解释为结构优势，而不是参数偶然性。

## 9. 当前最小工程包

立即开始的最小工程包：

```text
A. StructureCandidate
B. RiskBudgetDecision
C. ExecutionTradeDiagnostics
D. ClearingTradeLedger 最小口径
E. structural-alpha-r1 严格失败退出最小策略
F. MAE / MFE + exit reason 输出
```

完成这些后，再加入主动止盈、时间退出、止损放宽对照和报告视图。

核心原则：**先让实验能被正确解释，再让实验跑得更多。**
