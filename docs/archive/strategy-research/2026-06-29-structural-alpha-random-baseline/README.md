# 2026-06-29 structural-alpha-random-baseline 归档索引

> 类型：Archive / 阶段归档入口\
> 状态：已结题\
> 主题：结构型 Alpha 随机对照与价值区深耕\
> 推荐入口：[structural-alpha-stage-final-report.md](./structural-alpha-stage-final-report.md)

## 1. 这个目录是什么

本目录归档的是 2026-06-28 \~ 2026-06-29 的结构型 Alpha 阶段研究。

阶段目标不是找到可上线策略，而是回答：

```text
共识价格区间附近的结构入口，
是否至少比匹配随机开仓更有信息量？
```

阶段最终结论：

```text
结构入口不是整体等同随机；
方向层部分有效，原始风险空间层普遍不足；
价值区 VAH / VAL 重新接受是下一阶段最强主线；
成交量冲击降级为质量标签；
前日高低点保留弱线索；
小时流动性与低波入口暂停。
```

## 2. 推荐阅读顺序

如果只想快速理解阶段结论，按这个顺序读：

1. [structural-alpha-stage-final-report.md](./structural-alpha-stage-final-report.md)\
   阶段结题报告，最重要入口。
2. [random-baseline-experiment-summary.md](./random-baseline-experiment-summary.md)\
   随机对照阶段摘要，回答“哪些结构不是随机”。
3. [value-area-deepening-summary.md](./value-area-deepening-summary.md)\
   价值区 VAH / VAL 重新接受深耕摘要，说明为什么价值区成为主线。
4. [entry-structure-experiment-summary.md](./entry-structure-experiment-summary.md)\
   原始入口实验摘要，解释为什么很多直接入口没有通过。

如果要理解阶段计划，再读：

1. [structural-alpha-short-term-plan.md](./structural-alpha-short-term-plan.md)\
   原短期计划压缩归档。
2. [random-entry-baseline-plan.md](./random-entry-baseline-plan.md)\
   随机入口基准补充计划压缩归档。

如果要查看 roadmap 原文版，再进入：

1. [raw-roadmap/README.md](./raw-roadmap/README.md)\
   原始 roadmap 文档索引。

如果要追查过程细节，再进入：

1. [raw-workbench/README.md](./raw-workbench/README.md)\
   原始 workbench 实验记录索引。

## 3. 文件说明

| 文件 / 目录                                                                            | 作用                           | 什么时候读                   |
| ---------------------------------------------------------------------------------- | ---------------------------- | ----------------------- |
| [structural-alpha-stage-final-report.md](./structural-alpha-stage-final-report.md) | 结题报告，总结阶段问题、核心结论、路线分流、下一阶段建议 | 默认第一入口                  |
| [random-baseline-experiment-summary.md](./random-baseline-experiment-summary.md)   | 随机对照结果摘要                     | 判断哪些结构优于随机时读            |
| [value-area-deepening-summary.md](./value-area-deepening-summary.md)               | 价值区深耕摘要                      | 研究下一阶段价值区主线时读           |
| [entry-structure-experiment-summary.md](./entry-structure-experiment-summary.md)   | 原始入口结构实验摘要                   | 追溯 IB、前日、成交量、流动性等入口实验时读 |
| [structural-alpha-short-term-plan.md](./structural-alpha-short-term-plan.md)       | 原短期计划压缩版                     | 需要了解阶段设计哲学时读            |
| [random-entry-baseline-plan.md](./random-entry-baseline-plan.md)                   | 随机对照补充计划压缩版                  | 需要了解随机基准规则时读            |
| [raw-roadmap/](./raw-roadmap/)                                                     | 原始 roadmap 文档                   | 只在需要查阶段计划原文时读           |
| [raw-workbench/](./raw-workbench/)                                                 | 原始 workbench 记录              | 只在需要查过程细节、参数、单轮实验记录时读   |
| [raw-scripts/](./raw-scripts/)                                                     | 阶段性研究 runner 脚本归档          | 只在需要复现当时批量实验或诊断脚本时读     |
| [raw-strategies/](./raw-strategies/)                                               | 阶段性随机基线策略代码归档          | 只在需要查看当时随机基线实现时读         |

## 4. 给 AI 的阅读建议

后续 AI 如果接手本项目，应先读：

```text
1. structural-alpha-stage-final-report.md
2. value-area-deepening-summary.md
3. random-baseline-experiment-summary.md
```

不要优先从 `raw-workbench/` 开始读。`raw-workbench/` 是过程性材料，内容多、重复多，适合查证，不适合作为理解阶段结论的入口。

如果用户问：

```text
这个阶段到底得出了什么结论？
```

优先引用：

- [structural-alpha-stage-final-report.md](./structural-alpha-stage-final-report.md)

如果用户问：

```text
为什么说价值区值得继续？
```

优先引用：

- [value-area-deepening-summary.md](./value-area-deepening-summary.md)
- [random-baseline-experiment-summary.md](./random-baseline-experiment-summary.md)

如果用户问：

```text
某一轮实验具体怎么跑的？
```

再去：

- [raw-workbench/README.md](./raw-workbench/README.md)

如果用户问：

```text
当时批量随机对照或价值区深耕脚本在哪里？
```

再去：

- [raw-scripts/README.md](./raw-scripts/README.md)

注意：`raw-scripts/` 中脚本是阶段性 runner，不是 active 工具。

如果用户问：

```text
当时的随机基线策略代码在哪里？
```

再去：

- [raw-strategies/README.md](./raw-strategies/README.md)

注意：`raw-strategies/` 中代码是阶段性随机基线策略归档，不是 active 策略。

## 5. 阶段最终保留主线

下一阶段若继续，应优先围绕：

```text
value_area_reacceptance
+ POC 空间
+ price_raw_rr 预筛
+ min_reaccept_ticks 2~3
+ max_hold_bars ≈ 12
```

但它还不是可上线策略。下一阶段重点不是继续找新入口，而是补证：

```text
账户风险预算；
品种适配；
尾部风险；
成本 / 平均盈利安全边际；
min_reaccept_ticks 的波动归一表达；
成交量冲击作为质量标签的价值。
```

## 6. 暂缓方向

本阶段暂缓继续深耕：

```text
主动止盈 / 分段目标 / MFE 回撤退出；
prevday_volume_filter 的完整随机对照；
IB 的重新实现；
rolling value area 的状态分桶随机对照；
500/1000 seeds 的正式随机分布。
```

原因：

```text
阶段核心问题已经回答；
继续补齐这些不会改变当前主结论，
应留给下一阶段按新目标决定是否展开。
```

