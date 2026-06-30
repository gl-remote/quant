# structural-alpha-r1 Alpha 研究规划

> 类型：Archive / 工程支撑规划归档  
> 状态：已归档；诊断通道已落地，真实 `StructureCandidate` 待实现  
> 完成日期：2026-06-30  
> Git 参考：`2fd6858` 诊断层通道；`ba4cf11` clearing diagnostics reporting pipeline  
> 创建日期：2026-06-29  
> 来源：由 [structural-alpha-r1 工程支撑总览](overview.md) 拆分  
> 关联 roadmap：[策略短期研究计划](../../../roadmap/strategy-short-term-plan.md)、[策略长期共识](../../../roadmap/strategy-research-framework.md)  
> 文档边界：本文只定义结构型 Alpha 的研究对象、共识价格区间、失败边界与盈利上界；不定义账户风险预算、成交撮合、清算账务或报告聚合。

## 1. 定位

`structural-alpha-r1` 的研究目标不是扩大参数搜索，而是验证一个结构型交易假设是否具备可解释的优势：

```text
共识价格区间
→ 明确失败边界
→ 可估算的短期盈利上界
→ 可被风险预算和执行系统验证
```

Alpha 研究层只回答：

- 为什么进场；
- 市场正在围绕哪个共识价格区间重新定价；
- 多空方向假设是什么；
- 严格失败边界在哪里；
- 盈利上界在哪里；
- 接受 / 拒绝证据是否足够客观；
- 收益能否解释为结构优势，而不是参数偶然性。

## 2. 行业分层位置

本文对应量化系统中的：

```text
Research / Alpha Definition
```

它位于以下链路的最上游：

```text
Alpha 定义
→ Pre-trade Risk / Position Sizing
→ Execution / Backtest Simulation
→ Clearing / Accounting
→ Performance Analytics / Reporting
```

Alpha 层只产出候选结构，不直接决定最终仓位，不计算成交后 PnL，也不负责绩效归因。

## 3. 范围

### 3.1 目标

- 定义 `structural-alpha-r1` 的最小结构假设；
- 提供客观共识价格区间；
- 为每个候选结构生成严格失败边界和盈利上界；
- 记录接受 / 拒绝证据；
- 为风险预算和执行模拟提供稳定输入。

### 3.2 非目标

当前阶段不做：

- 大规模 Optuna / Bayesian search；
- Walk-Forward；
- 多体系复杂叠加；
- 通用策略脚手架；
- 仓位计算；
- 成交配对、手续费、滑点和 PnL 计算；
- 报告图表展示。

## 4. 第一阶段共识价格区间

优先支持无需复杂成交量 profile 的客观区间：

| 区间 | 说明 | 优先级 |
|------|------|--------|
| 前日高 / 低点 | 高频可观察边界 | P0 |
| 昨收 | 日内参考锚点 | P0 |
| 开盘区间高 / 低点 | 日内早期边界 | P1 |
| Initial Balance 高 / 低点 | 更明确的早盘共识区间 | P1 |

后置候选：

| 区间 | 后置原因 |
|------|----------|
| VAH / VAL / POC | 需要 profile 计算 |
| 密集成交区边缘 | 需要成交分布或价格停留统计 |
| 假突破极值 | 需要事件状态机 |
| 重新接受 / 拒绝 | 需要边界外停留和回收判断 |

## 5. Alpha 结构字段

建议形成独立的 `StructureCandidate` / `StructuralAlphaContext` 模型。

| 字段 | 说明 |
|------|------|
| `experiment_version` | 例如 `structural-alpha-r1` |
| `consensus_zone_type` | previous_day_high_low、opening_range、initial_balance 等 |
| `structure_source` | Price Action、Auction / Market Profile、Wyckoff 等 |
| `traditional_explanation` | 传统解释 |
| `structural_explanation` | 结构塑形解释 |
| `direction_hypothesis` | long / short |
| `entry_boundary` | 入场参考边界 |
| `strict_failure_boundary` | 严格失败边界 |
| `expected_profit_boundary` | 预期盈利上界 |
| `acceptance_rejection_evidence` | 接受 / 拒绝证据类型 |
| `fast_retouch_bars` | 严格边界快速再触及所用 K 线数 |
| `fast_retouch` | 是否快速再触及 |

## 6. 输出契约

Alpha 层应输出结构化对象，而不是 markdown 表格或日志字符串。

建议最小 artifact：

```text
StructureCandidate
├── identity
├── consensus_zone
├── direction_hypothesis
├── entry_boundary
├── strict_failure_boundary
├── expected_profit_boundary
└── evidence
```

字段应尽量使用数字、枚举和布尔值。展示格式化只在报告层处理。

### 6.1 当前技术落点（2026-06-30）

本轮尚未实现真实 `StructureCandidate`，但已经为 Alpha 层预留了稳定通道：

```text
Signal.alpha: AlphaDiagnostics
→ decision_payload.diagnostics.alpha
→ backtest_trades.decision_payload_json
→ trade_clearings.diagnostics_json
→ clearing_diagnostics.json / report
```

当前规则：

- `Signal.alpha` 必须非空；
- 既有策略可临时使用 `placeholder_diagnostics` 跑通；
- clearing 会过滤 `{"placeholder": true}`，避免把占位当作真实结构解释；
- 如果策略填了真实 alpha 字段但缺少结构族推荐字段，clearing 记录 warning，不阻断 run。

因此，Alpha 研究层下一步不需要重新设计通道，而应直接实现 `StructureCandidate` 并填充到 `Signal.alpha`。

## 7. 与其他模块的边界

| 模块 | Alpha 层提供 | Alpha 层不负责 |
|------|--------------|----------------|
| Pre-trade Risk | 入场价、失败边界、盈利上界、方向 | 风险预算、下单手数、拒绝原因 |
| Execution / Backtest | 结构候选、退出参考边界 | 撮合、MAE / MFE、exit reason |
| Clearing / Accounting | 无直接账务输入 | 手续费、滑点、gross / net PnL |
| Analytics / Report | 结构标签和解释字段 | 胜率、盈亏比、归因、图表 |

## 8. 第一阶段实施顺序

1. 定义 `structural-alpha-r1` 的结构候选模型；
2. 支持前日高 / 低点与昨收；
3. 输出 entry / strict failure / expected profit 三类边界；
4. 记录接受 / 拒绝证据；
5. 将结构候选传递给风险预算预筛；
6. 后续再扩展开盘区间和 Initial Balance。

## 9. 验收标准

- 每个候选结构都有明确共识价格区间；
- 每个候选结构都有严格失败边界；
- 每个候选结构都有预期盈利上界；
- 多空方向假设可被枚举化记录；
- 接受 / 拒绝证据不依赖自然语言拼接；
- Alpha 层不计算仓位、成交后成本或 PnL；
- 下游风险预算和执行模拟可以直接消费结构候选 artifact。
