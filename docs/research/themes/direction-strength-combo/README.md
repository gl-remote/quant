# direction-strength-combo · 方向+强度配合主题

> 类型：Research / 主题目录索引
> 状态：**待启动**（2026-07-17 立题 · 尚未确定研究计划与实验矩阵）

## 1. 问题定义

> **核心问题**：既然单独识别方向（通道 A）和单独识别强度（通道 B）都面临挑战，
> 能否找到一种**同时编码方向和强度信息的结构性特征**，实现两者的配合？

**上游背景**：
- KF-B6 已证明：|ν|/σ 无法从价量数据精确预测（8 个跨类型因子全 L4）
- va-asymmetry 主题已找到方向 edge（A3_skew + ATR + trend 的 tier 分类器）
- KF-26 混合期望公式表明：方向已知时，强度越高，E_gross 越大（E_gross ∝ x²）

**"配合"的三种可行模式**：
1. **结构性特征隐含编码**：某些特征（如 A3_skew 大小）天然同时代表方向偏置程度和潜在强度
2. **强度做粗粒度过滤**：不精确预测 |ν|/σ，只做"波动率极低时段排除"等条件过滤，提升方向信号信噪比
3. **联合分布建模**：条件期望 E[gross|direction_known ∧ strength_condition] 的数学结构

## 2. 文档地图

| 文档 | 作用 | 状态 |
|------|------|------|
| [research-status.md](research-status.md) | 主题现状 · 结论 · 边界 · 下一步 · 关键发现清单 | 待写 |
| [screening-methodology.md](screening-methodology.md) | 方向+强度配合的数学规格 · 筛选流程 · 判据 | 待写 |
| [experiment-plan.md](experiment-plan.md) | 候选矩阵 · 验证顺序 · 判定标准 | 待写 |
| [parameter-selection-spec.md](parameter-selection-spec.md) | 参数选择规格（分层 · 判据 · 流程） | 占位 |
| [implementation-notes.md](implementation-notes.md) | 工程实现细节 | 占位 |
| [archive-references.md](archive-references.md) | 关联 archive 索引 | 待写 |

## 3. 阅读顺序

1. 先读本 README 理解问题定义
2. 读 [screening-methodology.md](screening-methodology.md) 理解数学规格和筛选流程
3. 读 [experiment-plan.md](experiment-plan.md) 了解候选矩阵
4. 读 [research-status.md](research-status.md) 了解当前状态和关键发现

## 4. 上游依赖

| 依赖 | 类型 | 说明 |
|------|------|------|
| kf:structural-shaping-alpha#KF-26 | 数学基础 | 双通道 alpha 框架 · E_gross^mix 公式 |
| kf:structural-shaping-alpha#KF-27 | 工程接口 | 分布输入闭式解 · 参数优化器 |
| kf:structural-shaping-alpha#KF-19 | 实证基础 | 通道 A（方向 alpha）已实证 |
| kf:strength-factor-screening#KF-B6 | 边界约束 | |ν|/σ 无法从价量数据精确预测 |
| theme:va-asymmetry-composite | 分类器 | A3_skew + ATR + trend 的 tier 分类器 |

## 5. 保留资产

待确认。
