# Quantsmith Shared Contracts

跨业务域、跨语言、跨运行单元复用的共享契约。

## 当前内容

JSON Schema（Draft 2020-12）描述 `project_data/reports/` 下报告产物的字段结构：

| Schema | 描述目标 | 生产者 | 主要消费者 |
|---|---|---|---|
| `run.schema.json` | `project_data/reports/runs/r{run_id}/data/run.json` | `report.builder` | 前端 r 列表页、Python 测试 |
| `summary.schema.json` | `project_data/reports/runs/r{run_id}/data/summary.json` | 同上 | 前端 r 详情页（symbol 概览表） |
| `backtests.schema.json` | `project_data/reports/runs/r{run_id}/data/backtests.json` | 同上 | 前端 r 详情页（参数 + daily 序列） |
| `equity.schema.json` | `project_data/reports/runs/r{run_id}/data/equity.json` | 同上 | 前端净值曲线 |
| `trades.schema.json` | `project_data/reports/runs/r{run_id}/data/trades.json` | 同上 | 前端成交记录表 |
| `optuna.schema.json` | `project_data/reports/runs/r{run_id}/data/optuna.json` | 同上 | 前端 Optuna 图表 |
| `logs.schema.json` | `project_data/reports/runs/r{run_id}/data/logs.json` | 同上 | 前端运行日志面板 |
| `clearing_diagnostics.schema.json` | `project_data/reports/runs/r{run_id}/data/clearing_diagnostics.json`（可选） | 同上 | 前端结构诊断视图（成本后指标 / exit reason / R 分布 / diff） |
| `nav.schema.json` | `project_data/reports/data/nav.json` | 同上 | 前端 r 列表页（跨 run 汇总） |

## 角色定位

- 本目录定位与 [directory-roadmap.md](../../../docs/archive/infra/directory-roadmap.md) 中 `workspace/packages/contracts/` 一致：跨业务域、跨语言、跨运行单元。
- 当前 schemas 平铺存放，便于阶段 0.5 起步。后续业务域迁入 `workspace/` 后，再按消费场景（run / optimization / navigation）分子目录。
- Python 侧的 schema 加载与校验工具放在 `workspace/packages/python-contracts/`（同根 workspace 子包）。

## 变更原则

1. 任何 schema 字段变更必须**同步**更新生产者代码、契约测试、前端消费方。
2. 删除/重命名字段需要兼容期或 contract version 标注。
3. 字段类型从严不从宽（先窄后放宽，避免回退）。
4. 不在生产者代码引用 schema 强约束，schemas 仅作为单向校验护栏。

## 关联文档

- [backtest-refactor-plan.md 阶段 0.5](../../../docs/archive/backtest/backtest-refactor-plan.md)
- [directory-roadmap.md 原则 4 跨语言契约](../../../docs/archive/infra/directory-roadmap.md)
