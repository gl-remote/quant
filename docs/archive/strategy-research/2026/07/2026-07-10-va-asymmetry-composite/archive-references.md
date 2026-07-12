# va-asymmetry-composite · Archive 引用清单

> 类型：Archive Reference Index
> 版本：v0.1（立题初始登记）
> 最近更新：2026-07-09
> 主题 README：theme:va-asymmetry-composite#README

本文件回答：`docs/archive/strategy-research/` 中哪些目录与本主题相关？
各自是什么关系？采用 **Pull 模式**：引用触发登记，不引用不登记（立题时登记高相关
批次，后续若新增引用再追加）。

## 关系类型词表（与 quant-research-layout 一致）

| 类型 | 含义 |
|------|------|
| 继承 | archive 是本主题的前置 / 上游研究，结论直接支撑本主题假设与参数 |
| 方法论遗产 | archive 沉淀的分析框架、判据、统计工具被本主题直接继承 |
| 数据复用 | archive 中的事件采样、baseline 事件集被本主题直接复用 |
| 代码复用 | archive 中的 `raw-scripts/` 或策略代码被本主题改造重用 |
| 铺垫 | archive 中的旁证 / 副产品级观察暗示了本主题假设 |
| 反例 | archive 中的假设被证伪，本主题明确避开该路径 |

---

## Archive 目录清单（立题时登记 5 个 · 按关系强度排序）

### archive:2026-07-09-poc-va-shaping（⭐ 直接起点）
- **关系类型：继承（最直接）+ 数据复用 + 代码复用**
- **说明**：本主题的**直接起点归档**。在 poc-value-area-asymmetry 分类器 v4.0 上
  完成塑形参数扫描（240 组合 × 6 tier）、最优塑形参数确认（多头 SL1.0 ATR·6~10h
  / 空头 SL2.0~2.5 ATR·8~10h / Trailing 无效）、L_seg2_low_flat 淘汰判定（塑
  形后 IR<0）、期货保证金制度下的风控 v2 口径（单笔 2% + 名义 100% 上限，年化
  15.45% / Sharpe 2.23 / MaxDD −7.51 / 胜率 60.3% / 盈亏比 1.41）。
  本主题**阶段 0 baseline（B0）完全复现该归档的最优口径**；
  临时脚本 `poc_va_risk_managed_v2.py` 等直接被改造为本主题阶段 0 的模拟代码。
- **关键引用点**：
  - README：archive:2026-07-09-poc-va-shaping#README（核心结论、参数、上游数据路径）
  - 原始数据：`project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline.parquet`（登记在该批次 §上游数据）
  - 塑形参数扫描结果：`poc_va_shaping_scan_results.csv`（240 组合 × 6 tier）
  - 风控 v2 汇总：`poc_va_risk_managed_v2.csv`（tier 分档表）

### archive:2026-07-08-poc-va-asymmetry（⭐ Alpha 源全阶段归档）
- **关系类型：继承（Alpha 源）+ 数据复用**
- **说明**：分类器 v4.0 产生的全阶段研究（阶段 1 测量 → 阶段 2 护栏 → 阶段 3 稳健
  性 → 阶段 4 三维深化 + 合并降级）。本主题分类器 tier 定义、rolling rank 窗口、
  warmup 口径、per-contract rank 约束、(contract, date) cluster bootstrap、
  FDR 校正、KF-22（数据边界）、KF-23（制度依赖 vs 过拟合）、KF-24（品种异质
  性三大类型）、KF-29（合并降级优于精细）全部**硬继承**。
  `classifier_v31_timeline.parquet` 由该批次阶段 4 产出。
- **关键引用点**：
  - 阶段 4 分类器 v4：archive:2026-07-08-poc-va-asymmetry#stage4-classifier-v4
  - 阶段 3 稳健性（KF-16~23）：archive:2026-07-08-poc-va-asymmetry#stage3-robustness
  - 全阶段摘要：archive:2026-07-08-poc-va-asymmetry#stage-summary

### archive:2026-07-06-structural-shaping-alpha-stage1（⭐ 方法论 + 工具资产）
- **关系类型：方法论遗产（核心 4 条 KF）+ 代码复用**
- **说明**：本主题**方法论前置约束的来源**（9 条中 4 条直接来自本批次 KF）。
  - KF-1：塑形本身无独立 alpha → 本主题 alpha 只来自分类器，塑形是变现条件
  - KF-4：「少输」型 paired 显著性 ≠ 独立 alpha → 本阶段 1 每方向 gatekeeper 必做二维拆分（mean + 尺度）
  - KF-5：扁平 ATR 成本模型跨品种低估 4.5 倍 → 本主题 realistic-cost 硬约束（§0.3）
  - KF-7：5m tail alpha 是重采样伪影 → 本主题交易时钟 1h，阶段 2+ 做跨周期护栏
  - KF-9：归因必须用 ν = μ − σ²/2 → 本主题 strategy-math-spec.md §9 硬约束
  工具资产复用：`first_passage_designer.py` 的查询模式（塑形参数快速查询）、
  `compare_cost_models.py` 的 realistic-cost 计算函数、ν_implied 反算函数。
- **关键引用点**：
  - Gatekeeper 报告（KF + 成本模型 + ν_implied）：archive:2026-07-06-structural-shaping-alpha-stage1#stage1-gatekeeper-report
  - First-Passage 对照表：archive:2026-07-06-structural-shaping-alpha-stage1#first-passage-lookup-tables
  - 阶段总结：archive:2026-07-06-structural-shaping-alpha-stage1#stage-summary

### archive:2026-07-05-value-area-rolling-reacceptance-freeze（反例 + 方法论遗产）
- **关系类型：反例（4 条假设）+ 方法论遗产（4 条约束）**
- **说明**：value-area 家族最终证伪批次。**反例部分（本主题明确避开）**：
  POC 特殊性（fixed & rolling）作为均值锚、reacceptance 触发器特殊性、
  4+ ATR 距离档 mean-reversion edge、rolling POC 独立回归锚价值。
  本主题不触碰以上任何一条（见 README §3.1 的独立性声明）。
  **方法论遗产（本主题继承）**：ATR 归一化、期望净值判据、cluster bootstrap、
  多层对照、配对差异检验、Cross-sampling 护栏。
- **关键引用点**：
  - 冻结摘要（4 假设证伪 + 共同教训）：archive:2026-07-05-value-area-rolling-reacceptance-freeze#freeze-summary

### archive:2026-07-03-value-area-reacceptance-stage-b（反例背景 + C3 Feature 参考）
- **关系类型：反例背景 + 铺垫（C3 Feature 复用候选）**
- **说明**：value-area-reacceptance 主题 Stage B 的 feature-only 降级归档。
  C3 特征（次次尝试且未触碰 POC）在 Group_P 上 ret_mean +1.10，但在 Group_M
  上 concentration risk 高（单样本主导 87%）。本主题**阶段 2 末尾可选探索**：
  在 va-composite 的事件集上叠加 C3 过滤器，观察高置信度事件（C3 = 1）是否
  进一步提升 IR（仅当阶段 2 现有自由度用尽、仍想追增量时启用，不计入主搜索空间）。
- **关键引用点**：
  - Stage B 双 Q 判据总结：archive:2026-07-03-value-area-reacceptance-stage-b#stage-b-sweep-summary
  - C3 定义语义：theme:value-area-reacceptance（冻结）#strategy-math-spec

---

## 未列入本清单的 Archive（Pull 模式）

以下 archive 与本主题**当前无直接关系**，若后续研究中出现真实引用再追加：

- archive:2026-06-26-indicator-baseline
- archive:2026-06-27-low-validation-cost
- archive:2026-06-29-structural-alpha-random-baseline（若做 dirandom 反事实时需要 random baseline 对照实现 → 到时追加登记）
- archive:2026-07-01-value-area-reacceptance-quality
- archive:2026-07-02-value-area-reacceptance-expansion

---

## 关联主题（非 archive · 走命名引用协议）

| 主题 | 关系 | 主要引用 |
|:---|:---|:---|
| theme:poc-value-area-asymmetry | Alpha 源（上游活跃主题，主动性研究暂停） | classifier-math-spec v4.0（tier 定义、3 维 rank、rolling 窗口） |
| theme:structural-shaping-alpha | 塑形工具 + 方法论（上游活跃主题，阶段 1 待冻结） | first-passage-designer-math-spec + KF-1/4/5/7/9 |
| family:value-area | 反例家族（已冻结） | 家族 README 共同教训 + 方法论遗产 |
| theme:value-area-reacceptance | C3 Feature 候选（已冻结，feature-only） | strategy-math-spec.md §C3 定义 |

---

## 变更记录

| 版本 | 日期 | 变更 |
|:---:|:---:|:---|
| v0.1 | 2026-07-09 | 立题初始登记：5 个 archive（2 继承 + 1 方法论 + 1 反例 + 1 铺垫）· 4 个关联主题登记 |
