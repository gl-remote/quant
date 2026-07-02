---
name: "quant-research-docs"
description: "Defines quant research document boundaries and archive rules. Invoke when writing workbench, roadmap, issue, or archive docs."
---

# Quant Research Docs

本 skill 记录 quant 项目研究文档的目录边界、写法和归档规则。

## 目录边界

| 目录 | 用途 |
|------|------|
| `docs/roadmap` | 阶段规划、研究方向、评价标准；不写具体实验过程 |
| `docs/workbench` | 当前研究中的实验记录、参数对照、中间结果、临时结论 |
| `docs/issues` | 实验中发现的底层框架问题，不是策略结论 |
| `docs/archive/strategy-research` | 已完成、压缩、可长期引用的策略实验摘要 |

## Roadmap 边界

- roadmap 只维护阶段目标、评价标准和候选方向。
- 不把具体实验方向、开发分支、开分支 hash、参数对照和中间结果直接写入 roadmap。
- 若需要说明文档边界，可以在 roadmap 顶部 meta 中写“文档边界”。

## Workbench 写法

实验过程默认先写入 `docs/workbench/`，包括：

- 实验问题；
- 结构塑形定义；
- 固定参数组；
- 参数对照和初步结果；
- 受框架 issue 影响的部分；
- 临时结论。

策略数学规格文档由 `quant-strategy-spec` 规则约束；研究计划与实验记录不要重复完整策略公式。

## Archive 写法

归档前必须压缩，只保留未来有用的信息：

- 核心问题；
- 实验定义；
- 固定参数；
- 关键结果；
- 结论；
- 对后续研究有用的信息；
- 必要复现备注。

删除：

- 过程性计划；
- 重复判断标准；
- 过期工具限制；
- 不存在策略的可执行命令；
- 不再有长期价值的中间描述。

归档路径：

```text
docs/workbench/<name>.md
-> docs/archive/strategy-research/<name>.md
```

移动后必须修正相对链接：

- archive -> roadmap：`../../roadmap/...`
- archive -> issues：`../../issues/...`
- issue -> archive：`../archive/strategy-research/...`

## Issues 工作流

当策略实验中发现问题不再属于策略逻辑，而可能来自以下层面时，先写 `docs/issues/` 并暂停受影响实验：

- 回测引擎统计口径异常；
- DataFeed / 缓存 / 周期加载不一致；
- vnpy 桥接、开平仓、成交配对异常；
- CLI / runner 与策略 `data_requirements` 不一致；
- 指标、成本、滑点、手续费、PnL 等基础口径存在疑问。

issue 修复后：

- 状态改为“已验证”；
- 回填 `修复提交 hash`；
- 若关联实验已归档，issue 链接应指向 archive 路径。

## 策略代码保留 / 删除规则

- 已通过或仍在活跃研究的策略，可以保留在 `workspace/strategies/`。
- 未通过实验的临时策略代码，默认不要污染长期策略目录。
- 删除失败实验策略代码时，文档中不能留下直接可执行但实际不存在的 `--strategy <name>` 命令。
- 若未来需要复现失败实验，在 archive 文档中保留结构定义和参数，让后续按定义重新实现最小策略。
