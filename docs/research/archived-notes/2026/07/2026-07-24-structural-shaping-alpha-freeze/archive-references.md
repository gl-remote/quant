# structural-shaping-alpha · Archive 引用清单

> 类型：Archive Reference Index
> 状态：初始（2026-07-06）
> 主题 README：theme:structural-shaping-alpha#README

本文件回答一个问题：**`docs/research/archived-notes/` 中哪些目录与本
主题相关？各自是什么关系？**

只登记"命名引用 + 关系标签"，不复述归档内容、不承载策略公式、不承载实验流水。
主题目录内其他文档需要引用 archive 时走**命名引用协议**（前缀 `archive:`），
本文件作为主索引。

## 关系类型词表

| 类型 | 含义 |
|------|------|
| 反例 | archive 中的假设被证伪，与本主题假设正交或颠倒 |
| 方法论遗产 | archive 沉淀的分析框架、判据、统计工具被本主题直接继承 |
| 数据复用 | archive 中的事件采样、baseline 事件集被本主题直接复用 |
| 代码复用 | archive 中的 `raw-scripts/` 或策略代码被本主题改造重用 |
| 继承 | archive 是本主题的前置研究，结论直接支撑本主题假设 |
| 铺垫 | archive 中的旁证 / 副产品级观察暗示了本主题假设 |

## Archive 目录清单

### archive:2026/07/2026-07-06-structural-shaping-alpha-stage1
- 关系类型：阶段归档（自登记）
- 说明：本主题阶段 1 gatekeeper 完整归档批次。含
  `stage1-gatekeeper-report.md`（原 workbench）·
  `first-passage-lookup-tables.md`（首达定理对照表）·
  `raw-scripts/`（3 份 runner 副本）。9 条 KF + First-Passage Designer
  工具在本批次内定型；主题不冻结（阶段 2 待外部触发）。
- 相关文件：archive:2026/07/2026-07-06-structural-shaping-alpha-stage1#stage-summary

### archive:2026/06/2026-06-29-structural-alpha-random-baseline
- 关系类型：方法论遗产 + 铺垫
- 说明：确立"random 入场 baseline + no_trigger baseline"的双对照范式，
  本主题的入场固定策略（random 采样 / no_trigger）直接继承该批次的
  采样定义与统计工具（`raw-scripts/run_structural_random_baselines.py`
  等）。同批次也观察到"结构选择差异 >> 入场信号差异"的副产品，
  是本主题的第一个铺垫。

### archive:2026/07/2026-07-01-value-area-reacceptance-quality
- 关系类型：反例
- 说明：value-area 家族的 reacceptance 质量分类假设批次；本主题不复用其
  reacceptance 触发器与 POC 质量标签，仅将其作为"入场信号维度深度调参
  未产生独立 alpha"的反例证据。

### archive:2026/07/2026-07-02-value-area-reacceptance-expansion
- 关系类型：反例
- 说明：value-area reacceptance 扩样与结构诊断批次；结论进一步证伪
  reacceptance 特殊性。本主题不复用其入场结构，仅作为反例。

### archive:2026/07/2026-07-03-value-area-reacceptance-stage-b
- 关系类型：反例
- 说明：value-area reacceptance 家族首次冻结批次；主策略降级为
  feature-only。反例，不复用其入场结构。

### archive:2026/07/2026-07-05-value-area-rolling-reacceptance-freeze
- 关系类型：反例 + 方法论遗产 + 数据复用（潜在）
- 说明：value-area 家族最终证伪批次（4 阶段完整证伪 POC 特殊性 / rolling
  独立价值 / reacceptance 触发器 / 距离档 edge）。本主题**继承**其四大
  方法论约束（ATR 归一化 / 期望净值 / cluster bootstrap / 多层对照），
  假设正交（结构塑形独立 alpha vs 触发器均值回归），不复用其结论。
  Stage 4b 的 15m no_trigger baseline 事件采样可作为本主题阶段 3 的
  跨周期稳健性数据来源（数据复用，尚未启动）。
- 相关文件：archive:2026/07/2026-07-05-value-area-rolling-reacceptance-freeze#freeze-summary

## Archive 家族反向索引

以下 archive 属于 **value-area 家族**（对应 `family:value-area`），
本主题与该家族的整体关系见家族级 README：

- family:value-area

家族级 README 承载"共同教训 + 方法论遗产"的完整叙述；本文件只登记
archive 与本主题的**个体关系**。

## 未列入本清单的 archive

以下 archive 与本主题**无直接关系**，仅作为项目全景说明：

- archive:2026/06/2026-06-26-indicator-baseline（指标基线，已被后续 structural-alpha
  批次取代）；
- archive:2026/06/2026-06-27-low-validation-cost（低验证成本策略批次，属于独立策略
  家族，与本主题无假设/数据/代码交集）。

若后续研究中发现新的引用关系，追加到"Archive 目录清单"节即可。
