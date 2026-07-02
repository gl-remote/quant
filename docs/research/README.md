# Research 文档入口

> 类型：Research / 当前研究入口\
> 状态：活跃\
> 用途：给人和 AI 快速了解当前研究状态、主题主线、成果和应避免重复的方向。

## 1. 目录定位

`docs/research` 用来保存当前仍在活跃维护的研究状态和主题索引。

它不同于：

| 目录 | 用途 |
|------|------|
| `docs/roadmap` | 阶段规划、未来计划、评价标准 |
| `docs/workbench` | 当前实验过程记录、参数对照、临时结论 |
| `docs/archive` | 已结题阶段归档、压缩复盘 |
| `docs/issues` | 回测、数据、框架、统计口径等问题 |
| `docs/research` | 当前研究状态、主题主线、已确认成果、下一步入口 |

## 2. 当前策略研究入口

先读：

- [strategy-current.md](./strategy-current.md)

该文件只维护总入口：

```text
当前一句话结论；
当前主题列表；
当前候选参数；
下一步优先级；
文档地图；
AI 接手规则。
```

## 3. 当前主题

| 主题 | 状态 | 文档 |
| --- | --- | --- |
| value_area_reacceptance | 活跃 / R29 扩样未通过 / R30 结构分支验证 | [themes/value-area-reacceptance.md](./themes/value-area-reacceptance.md) |

主题文件承载该主线的完整现状：

```text
策略结构；
固定参数；
POC / VA 定义；
首笔 VA reacceptance 与第 2/3 笔 continuation/retry 的拆分；
当前统计结果；
下一阶段扩样计划。
```

## 4. 当前主线摘要

```text
value_area_reacceptance 仍是活跃研究主题，但旧实盘候选规则已降级为 value_area_reacceptance_baseline；
R29 扩样未通过，不能继续把 R28 DCE.p 四样本视为已验证主线；
随机入场基准显示 VA reacceptance 事件仍有信息量。

当前下一步是 R30 结构分支验证：
1. VA 边界 → POC 的多次回归测试；
2. failed reacceptance / continuation 对照线。

不要继续在旧 baseline 上调 reentry_take_profit_r。
```

## 5. 关键文档

当前归档：

- [R29 扩样与随机基准复验](../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r29-expanded-validation.md)
- [R28 value_area_reacceptance 结构诊断](../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r28-structure-diagnosis.md)
- [R27 扩样复验](../archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/value-area-reacceptance-r27-expanded-sample.md)

最新阶段归档：

- [value_area_reacceptance POC / VA 质量诊断阶段归档](../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/value-area-reacceptance-quality-summary.md)
- [R1~R15 原始实验记录](../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/)

上一阶段归档：

- [结构型 Alpha 随机对照阶段归档](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/README.md)

如果需要追溯上一阶段详细实验过程，再从归档目录进入：

- [raw-roadmap](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/raw-roadmap/README.md)
- [raw-workbench](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/raw-workbench/README.md)

## 6. 给 AI 的阅读顺序

后续 AI 接手策略研究时：

```text
1. 先读 docs/research/strategy-current.md；
2. 再读当前主题文件 docs/research/themes/value-area-reacceptance.md；
3. 需要 R27-R29 实验细节时读 docs/archive/strategy-research/2026-07-02-value-area-reacceptance-expansion/；
4. 只有需要查旧阶段过程时，才进入 archive raw-workbench；
5. 不要继续在旧 baseline 上调 reentry_take_profit_r；
6. 下一步围绕 R30 多次 VA 回归 / continuation 分支做结构验证；
7. 新实验过程写入 docs/workbench；
8. 阶段稳定后再归档到 docs/archive。
```
