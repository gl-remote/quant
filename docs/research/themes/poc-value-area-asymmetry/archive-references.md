# poc-value-area-asymmetry · Archive 引用清单

> 类型：Archive Reference Index
> 状态：初始（2026-07-07）
> 主题 README：theme:poc-value-area-asymmetry#README

本文件回答一个问题：**`docs/archive/strategy-research/` 中哪些目录与本
主题相关？各自是什么关系？**

只登记"命名引用 + 关系标签"，不复述归档内容、不承载策略公式、不承载实验流水。
主题目录内其他文档需要引用 archive 时走**命名引用协议**（前缀 `archive:`），
本文件作为主索引。采用 pull 模式：**引用触发登记，不引用不登记**。

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

### archive:2026-07-08-poc-va-asymmetry
- 关系类型：继承（自归档 · 本主题产物）
- 说明：本主题**全阶段 1-4 合并归档批次**（从首次 commit 到当前 HEAD 的所有主题相关文件）。
  - 阶段 1（v7 · 19 合约）：A3_skew DN 侧独立方向信号测量
  - 阶段 2（v4 · 跨周期护栏 + ν_implied + OOS）：4 主线 Bonferroni 通过
  - 阶段 3（v11 · 5/5 任务）：背景划分器 7 层严格性 + 12 格经济机制 · KF P~U
  - 阶段 4（v9.1 · 143 合约）：三维 144 tier 深化 · FDR 校正 · 合并降级（KF-25~29）· v4.0 分类器契约冻结
  - 专属临时脚本 51 个（分阶段搬入 raw-scripts/）
- 相关文件：archive:2026-07-08-poc-va-asymmetry#stage1-measurement ·
  archive:2026-07-08-poc-va-asymmetry#stage2-guardrails ·
  archive:2026-07-08-poc-va-asymmetry#stage3-robustness ·
  archive:2026-07-08-poc-va-asymmetry#stage-summary ·
  archive:2026-07-08-poc-va-asymmetry#stage4-classifier-v4

### archive:2026-07-06-structural-shaping-alpha-stage1
- 关系类型：方法论遗产 + 铺垫
- 说明：本主题**方法论前置约束**完全继承本批次的 KF-1 / KF-4 / KF-5 /
  KF-7 / KF-8 / KF-9（结构塑形无独立 alpha、"少输"型 paired 显著 ≠ alpha、
  扁平成本模型跨品种低估、5m tail alpha 是重采样伪影、数学正 edge ≠ 工业
  可用 alpha、归因必须用 ν 而不是 μ）。**跳过 5m 交易尺度、直接从 1h 起测**
  的口径决策源于 KF-7。阶段 2 的 7 combo 结构塑形对比框架直接沿用本批次
  设施。
- 相关文件：archive:2026-07-06-structural-shaping-alpha-stage1#stage1-gatekeeper-report

### archive:2026-07-05-value-area-rolling-reacceptance-freeze
- 关系类型：反例 + 方法论遗产
- 说明：value-area 家族最终证伪批次。证伪的四条假设（POC 特殊性 / rolling
  独立价值 / reacceptance 触发器 / 距离档 edge）**均不被本主题触碰**（见
  README §2.1 · §10）。本主题**继承**其四大方法论约束（ATR 归一化 / 期望
  净值 / cluster bootstrap / 多层对照）。本主题假设正交：不是"POC/VA 作为
  价格锚"，而是"POC/VA 形状不对称作为特征"。
- 相关文件：archive:2026-07-05-value-area-rolling-reacceptance-freeze#freeze-summary

## Archive 家族反向索引

以下 archive 属于 **value-area 家族**（对应 `family:value-area`），
本主题与该家族的整体关系见家族级 README：

- family:value-area

家族级 README 承载"共同教训 + 方法论遗产"的完整叙述；本文件只登记
archive 与本主题的**个体关系**。

## 未列入本清单的 archive

以下 archive 与本主题**当前无直接关系**（pull 模式：真被引用时再登记）：

- archive:2026-06-26-indicator-baseline
- archive:2026-06-27-low-validation-cost
- archive:2026-06-29-structural-alpha-random-baseline
- archive:2026-07-01-value-area-reacceptance-quality
- archive:2026-07-02-value-area-reacceptance-expansion
- archive:2026-07-03-value-area-reacceptance-stage-b

若后续研究中发现新的引用关系，追加到"Archive 目录清单"节即可。
