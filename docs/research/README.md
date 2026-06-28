# Research 文档入口

> 类型：Research / 当前研究入口  
> 状态：活跃  
> 用途：给人和 AI 快速了解当前研究状态、成果、主线和应避免重复的方向。

## 1. 目录定位

`docs/research` 用来保存当前仍在活跃维护的研究状态和成果索引。

它不同于：

| 目录 | 用途 |
|------|------|
| `docs/roadmap` | 阶段规划、未来计划、评价标准 |
| `docs/workbench` | 当前实验过程记录、参数对照、临时结论 |
| `docs/archive` | 已结题阶段归档、压缩复盘 |
| `docs/issues` | 回测、数据、框架、统计口径等问题 |
| `docs/research` | 当前研究状态、已确认成果、主线入口 |

## 2. 当前策略研究入口

先读：

- [strategy-current.md](./strategy-current.md)

该文件维护：

```text
当前主线；
已确认成果；
暂缓方向；
下一步验证；
关键归档链接；
AI 接手规则。
```

## 3. 关键归档

当前策略研究的上一阶段归档：

- [结构型 Alpha 随机对照阶段归档](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/README.md)

如果需要追溯详细实验过程，再从归档目录进入：

- [raw-roadmap](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/raw-roadmap/README.md)
- [raw-workbench](../archive/strategy-research/2026-06-29-structural-alpha-random-baseline/raw-workbench/README.md)

## 4. 给 AI 的阅读顺序

后续 AI 接手策略研究时：

```text
1. 先读 docs/research/strategy-current.md
2. 再读其引用的 archive 结题报告和摘要
3. 只有需要查过程细节时，才进入 raw-workbench
4. 新实验过程写入 docs/workbench
5. 阶段稳定后再归档到 docs/archive
```
