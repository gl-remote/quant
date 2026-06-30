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
下一步优先级；
文档地图；
AI 接手规则。
```

## 3. 当前主题

| 主题 | 状态 | 文档 |
| --- | --- | --- |
| value_area_reacceptance | 主线 / POC 质量诊断已阶段收束 / 影子过滤待复验 | [themes/value-area-reacceptance.md](./themes/value-area-reacceptance.md) |

主题文件承载该主线的完整现状：

```text
策略结构；
固定参数；
POC / VA 定义；
edge_or_away；
当前统计结果；
分品种结论；
下一阶段待验证问题。
```

## 4. 关键归档

最新阶段归档：

- [value_area_reacceptance POC / VA 质量诊断阶段归档](../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/value-area-reacceptance-quality-summary.md)
- [R1~R15 原始实验记录](../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/)

上一阶段归档：

- [结构型 Alpha 随机对照阶段归档](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/README.md)

如果需要追溯上一阶段详细实验过程，再从归档目录进入：

- [raw-roadmap](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/raw-roadmap/README.md)
- [raw-workbench](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/raw-workbench/README.md)

## 5. 给 AI 的阅读顺序

后续 AI 接手策略研究时：

```text
1. 先读 docs/research/strategy-current.md；
2. 再读当前主题文件，例如 docs/research/themes/value-area-reacceptance.md；
3. 再读主题文件引用的 archive 摘要；
4. 只有需要查过程细节时，才进入 raw-workbench；
5. 不要在当前样本继续切更细标签桶；
6. 新实验过程写入 docs/workbench；
7. 阶段稳定后再归档到 docs/archive。
```
