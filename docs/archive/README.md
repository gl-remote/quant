# Archive — 已归档设计记录

> 该目录存放**已归档的历史设计记录**，仅供回溯演进过程。
> 当前代码不保证与归档文档完全一致，以代码本身为准。

---

## 管理规则

### 归档时机

- 对应功能/重构全部完成后即时归档
- 从 `docs/roadmap/` 移至 `docs/archive/`
- 移动前补全 metadata header（见 [归档规范](../../../.trae/rules/project_rules.md#21-文件头-metadata)）
- 不修改正文内容（保留完整演进记录）

### 业务域目录

文件按业务域划分子目录：

| 目录 | 用途 |
|------|------|
| `aspects/` | 方向/风控切面 DSL 体系 |
| `backtest/` | 回测链路重构与优化 |
| `strategy-research/` | 策略研究复盘与阶段性结论 |
| `strategy/` | 策略工程设计改进 |
| `infra/` | 基础设施、报告模块、目录规划 |
| `deprecated/` | 已废弃的历史方案（仅供参考） |

新增归档文件时放入对应目录，若无对应目录则创建新的业务域目录。

### metadata header

每个 `.md` 文件在标题后紧跟 metadata 块：

```markdown
> 类型：已实现设计记录 / 历史设计记录
> 状态：已实现 / 已完成 / 已废弃 / ...
> 完成日期：YYYY-MM-DD
> Git 参考：`commit_hash 简要描述`
```

---

## 文件清单

### aspects/ — 方向/风控切面 DSL 体系

| 文件 | 类型 | 状态 | 完成日期 | 说明 |
|------|------|------|---------|------|
| [strategy-aspects.md](aspects/strategy-aspects.md) | 已实现设计记录 | 已实现 | 2026-06-16 | Strategy Aspects 切面系统（方向 DSL 基础） |
| [risk-aspects-advisory-refactor.md](aspects/risk-aspects-advisory-refactor.md) | 已实现设计记录 | 已实现 | 2026-06-25 | 风控切面建议化重构 |
| [decorator-string-dsl.md](aspects/decorator-string-dsl.md) | 已实现设计记录 | 已实现 | 2026-06-26 | 装饰器 DSL 字符串化（Pratt Parser） |

### backtest/ — 回测

| 文件 | 类型 | 状态 | 完成日期 | 说明 |
|------|------|------|---------|------|
| [backtest-parallel.md](backtest/backtest-parallel.md) | 已实现设计记录 | 已实现 | 2026-06-19 | ParallelBacktestOptimizer 并行回测 |
| [backtest-refactor-plan.md](backtest/backtest-refactor-plan.md) | 已实现设计记录 | 阶段 0-9 已完成 | 2026-06-23 | 回测链路分阶段重构 |
| [cli-backtest-single-mode-and-strategy-params.md](backtest/cli-backtest-single-mode-and-strategy-params.md) | CLI 功能缺口记录 | 已验证 | 2026-06-27 | 显式 single 回测模式与策略参数覆盖入口 |
| [vnpy-pnl-mouth-reconciliation.md](backtest/vnpy-pnl-mouth-reconciliation.md) | 数据口径记录 | 已验证 | 2026-06-27 | vnpy daily_results 与 backtest_trades PnL 口径对账 |

### strategy-research/ — 策略研究复盘

| 文件 | 类型 | 状态 | 完成日期 | 说明 |
|------|------|------|---------|------|
| [ma-positive-expectancy.md](strategy-research/2026-06-26-indicator-baseline/ma-positive-expectancy.md) | 策略研究复盘 | 主触发方向暂停 | 2026-06-26 | MA baseline 正期望研究复盘，保留 `ma8` baseline |
| [strategy-atr-tuning.md](strategy-research/2026-06-26-indicator-baseline/strategy-atr-tuning.md) | 策略研究复盘 | 主触发方向降级 | 2026-06-27 | ATR 主触发方向降级，保留 ATR 风控模块 |

### infra/ — 基础设施

| 文件 | 类型 | 状态 | 完成日期 | 说明 |
|------|------|------|---------|------|
| [report-refactor.md](infra/report-refactor.md) | 已实现设计记录 | 主体已实现 | 2026-05-27 | 报告模块 React + Vite SPA 重构 |
| [directory-roadmap.md](infra/directory-roadmap.md) | 已实现设计记录 | 已归档 | 2026-06-24 | 目录结构长期规划 |

### deprecated/ — 已废弃的历史方案

| 文件 | 状态 | 说明 |
|------|------|------|
| [strategy-core-architecture-refactoring-v0.3.md](deprecated/strategy-core-architecture-refactoring-v0.3.md) | ⚠️ 已废弃 | 核心架构重构 v0.3（锁/缓存设计，已被更简方案取代） |
| [strategy-runtime-data.md](deprecated/strategy-runtime-data.md) | ⚠️ 已废弃 | 策略运行时数据管理（DataFeedCache/锁方案，已被更简方案取代） |
