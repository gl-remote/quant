# value_area_reacceptance 主题

> 类型：Theme / 目录索引
> 状态：活跃 / R30 多次 POC 回归 spec 阶段
> 最近更新：2026-07-03

VA reacceptance 主题当前研究状态、数学规格、实验计划、参数选择、工程实现细节全部在本目录内。

## 文档地图

| 目的 | 文档 |
| --- | --- |
| 主题当前研究进度（先看这个） | [research-status.md](research-status.md) |
| 数学规格（策略契约） | [strategy-math-spec.md](strategy-math-spec.md) |
| 实验计划 | [experiment-plan.md](experiment-plan.md) |
| 参数选择规格（待研究后填充） | [parameter-selection-spec.md](parameter-selection-spec.md) |
| 工程实现细节（待实现后填充） | [implementation-notes.md](implementation-notes.md) |

## 阅读顺序

```text
README.md                     (本文)
    ↓
research-status.md            主题结论 / 边界 / 下一步
    ↓
strategy-math-spec.md         精确的数学规格，作为实现契约
    ↓
experiment-plan.md            候选矩阵与验证顺序
    ↓
parameter-selection-spec.md   实验后填充的参数选择规则
    ↓
implementation-notes.md       代码实现层的具体优化与细节选择
```

## 与外部文档的关系

- 全局研究入口：[../../strategy-current.md](../../strategy-current.md)
- 长期框架：[../../../roadmap/strategy-research-framework.md](../../../roadmap/strategy-research-framework.md)
- 历史归档：见 [research-status.md §8 关联文档](research-status.md#8-关联文档)

## 工作规则

- 策略实现代码必须以 [strategy-math-spec.md](strategy-math-spec.md) 为准；
- spec 修改必须触发一次「静态一致性检查」（详见 `.trae/skills/quant-math-spec`）；
- 实验流水账写到 `docs/workbench/`，不回填到本目录；
- 阶段稳定后再归档到 `docs/archive/strategy-research/`，同时更新 [research-status.md](research-status.md) 的关联链接。
