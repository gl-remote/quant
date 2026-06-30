# structural-alpha-r1 工程支撑总览

> 类型：Archive / 工程支撑规划归档  
> 状态：已归档；一期工程支撑已部分落地，Alpha / Risk 真实业务对象待实现  
> 完成日期：2026-06-30  
> Git 参考：`2fd6858` 诊断层通道；`ba4cf11` clearing diagnostics reporting pipeline  
> 创建日期：2026-06-28  
> 拆分日期：2026-06-29  
> 关联 roadmap：[工程长期路线图](../../../roadmap/engineering-roadmap.md)、[策略短期研究计划](../../../roadmap/strategy-short-term-plan.md)、[策略长期共识](../../../roadmap/strategy-research-framework.md)  
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

### 4.2 当前落地状态（2026-06-30）

本轮工程已经完成两条基础通道：

1. **策略决策诊断通道**
   - `Signal.alpha` / `Signal.risk` / `Signal.execution` 已改为 dataclass 诊断层；
   - 三层诊断层都要求非空；
   - 既有策略通过临时 `placeholder_diagnostics` 跑通；
   - 真实 `StructureCandidate`、`RiskBudgetDecision`、`ExecutionTradeDiagnostics` 仍未实现。

2. **Clearing → Analytics → Report 通道**
   - `workspace/clearing` 已作为独立业务域落地；
   - `RunFinalizer` 已统一触发 clearing workflow；
   - DB 已落地 `trade_clearings`、`account_ledger_entries`、`position_ledger_entries`，并给 `trade_clearings` 增加 `diagnostics_json`、`exit_reason`、`mae`、`mfe`；
   - clearing 会从开仓 / 平仓成交的 `decision_payload` 透传真实诊断字段；占位诊断视为无效，不进入结构诊断 JSON；
   - MAE / MFE、holding bars、强平 exit reason 可由 clearing 基于成交和 K 线派生；
   - 报告侧已导出 `clearing_diagnostics.json`，并补充 JSON Schema 契约与前端结构诊断视图。

当前完成的是“工程通道”和“报告消费骨架”，不是结构型 Alpha 业务对象本身。只要策略后续按 `alpha` / `risk` / `execution` 推荐字段填充，clearing 和 report 可以直接消费；若字段缺失，clearing 只记录 warning，不阻断 run。

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
| P0 | MAE / MFE、holding bars、exit reason | Execution / Backtest / Clearing | 部分完成：MAE / MFE、holding bars、强平 exit reason 已由 clearing 派生；策略主动退出原因仍依赖 execution 诊断字段 |
| P0 | trade-level clearing ledger 最小口径 | Clearing / Accounting | 已完成一期：`trade_clearings`、account / position ledger 骨架、summary 回填 |
| P1 | 结构诊断报告 | Analytics / Report | 部分完成：`clearing_diagnostics.json`、前端结构诊断 tab 已有；结构解释质量依赖策略真实填充 alpha/risk |
| P1 | 结果 diff 工具 | Analytics / Report | 部分完成：同一 run 内前两个品种 / backtest 的 clearing diagnostics diff 已有；策略族退出结构实验编排未做 |
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

当前最小工程包的完成度：

| 项目 | 状态 | 说明 |
|------|------|------|
| A. `StructureCandidate` | 待做 | 诊断层 `alpha` 的 dataclass 通道已存在，但真实结构候选对象尚未实现 |
| B. `RiskBudgetDecision` | 待做 | 诊断层 `risk` 的 dataclass 通道已存在，但真实风险预算对象尚未实现 |
| C. `ExecutionTradeDiagnostics` | 部分完成 | 诊断层 `execution` 通道已存在；clearing 可消费 `exit_reason`，但策略侧仍未系统化填充 |
| D. `ClearingTradeLedger` 最小口径 | 已完成一期 | FIFO 配对、强平、成本 / PnL、account / position ledger 骨架、summary 回填已落地 |
| E. `structural-alpha-r1` 严格失败退出最小策略 | 待做 | 当前只有通用诊断通道和既有策略占位，没有结构型最小策略 |
| F. MAE / MFE + exit reason 输出 | 部分完成 | MAE / MFE 和 holding bars 已由 clearing 派生；强平 exit reason 已有；策略主动退出原因依赖 execution 推荐字段 |

完成这些后，再加入主动止盈、时间退出、止损放宽对照和报告视图。

核心原则：**先让实验能被正确解释，再让实验跑得更多。**

## 10. 本轮完成度评估（2026-06-30）

从系统链路看，本轮完成度约为：

```text
诊断数据通道：完成
Clearing 一期：基本完成
Analytics / Report 一期：部分完成
真实结构型 Alpha 业务：未开始
```

更细拆分：

| 维度 | 完成度 | 判断 |
|------|--------|------|
| 策略 → decision_payload → DB 通道 | 高 | 三层诊断 dataclass、非空校验、占位装饰器已落地 |
| 清算事实层 | 中高 | `trade_clearings`、account / position ledger 骨架、强平、summary 已有；生产级 margin / daily settlement 后置 |
| 诊断字段透传 | 中 | 真实字段可透传，占位会被过滤；但当前既有策略仍主要是占位 |
| MAE / MFE / holding bars | 中高 | 已由 clearing 基于持仓区间 K 线派生，long / short 方向已测试 |
| exit reason | 中 | 强平原因已稳定；策略退出原因需要 execution 诊断真实填充 |
| 报告 JSON 与契约 | 中高 | `clearing_diagnostics.json` 已导出，并有 JSON Schema 与契约测试 |
| 前端结构诊断视图 | 中 | 已能展示成本后指标、MAE / MFE、exit reason 分布和 diff；结构解释深度依赖后续字段 |
| Alpha / Risk 业务对象 | 低 | 仍是规划阶段，下一步应优先实现 `StructureCandidate` |

因此，本轮工作可以视为完成了 `structural-alpha-r1` 的**工程底座一期**：数据已经有通道、清算已经有权威落点、报告已经有消费入口。下一阶段不宜继续扩展报告外观，而应进入真实 Alpha / Risk 字段填充，让报告从“可展示”变成“可解释”。
