# strength-factor-screening · 强度因子筛选主题

> 类型：Research / 主题目录索引
> 状态：**待启动**（2026-07-16 立题 · 尚未确定研究计划与实验矩阵）
> 上游：kf:structural-shaping-alpha#KF-26 · kf:structural-shaping-alpha#KF-27
> 主题 slug：`strength-factor-screening`

## 1. 主题定位

研究**强度识别类因子**的筛选规则——即用于事前识别 $|\nu|/\sigma$（对数漂移绝对强度归一化后的读数）**强段**的因子家族。

**关键区分**：本主题因子不判方向、只判强度。

| 维度 | 本主题（强度因子） | 方向因子（不属本主题） |
|---|---|---|
| 目标量 | $\|\nu\|/\sigma$ | $\text{sign}(\nu)$ |
| 输出 | "现在是否处于分布前 p% 强段" | "做多 / 做空" |
| 数学根据 | 打破 Doob OST 的**可测性**前提 | 打破 Doob OST 的**鞅性**前提 |
| 兑现路径 | 非对称塑形（RR≥2）+ DirRandom | 方向筛选 + 塑形放大 |

## 2. 上游依赖

本主题的**存在依据**完全依赖 structural-shaping-alpha 主题的两个 KF：

- **kf:structural-shaping-alpha#KF-26** · 强段择时 + DirRandom + RR≥2 非对称塑形 = 无方向 alpha 的正期望通道（闭式 $E_{\text{gross}}^{\text{mix}}$ 公式）
- **kf:structural-shaping-alpha#KF-27** · 分布输入的完整闭式参数优化器 · 输入 $(\mu_D, \sigma_D, \sigma_{\text{bar}}, c_{\text{side}})$ 反解最优 $(K_S^\ast, K_T^\ast, \tau^\ast)$

**下游 KPI**（由上游 §2.23.6 通用闭式给出）：

$$
\text{se}^{\text{目标}} = \frac{x^\ast_{\text{KF-27}} - x_{\min}}{1.645}, \quad x_{\min} = \sqrt{\frac{6c}{K_S^3 R(R-1)}}
$$

玉米 1h 参考值：$\text{se}^{\text{目标}} \approx 0.05$——本主题所有候选识别器需以此为红线。

## 3. 文档地图

**当前只建立最小索引骨架**。实验相关的四份长期文档（math-spec / experiment-plan / parameter-selection-spec / implementation-notes）在研究计划确定后再创建。

| 文档 | 状态 | 说明 |
|---|---|---|
| README.md | ✅ 本文 | 主题目录索引 |
| research-status.md | ✅ 空占位 | 一句话结论 · 边界 · 下一步 · 关键发现清单（空） |
| archive-references.md | ✅ 空占位 | 上游 shaping-theory 引用登记 |
| screening-methodology.md | ✅ v0.8 | 筛选方法说明 · §一 证明 + §二 数学工具箱（12 项） + §三 可用工具列表 + §四 标准因子筛选流程 Step 0–10（含 Step 4.5 Gate 1.5 分布对齐） + §五 工程边界条件 + §六 双置信度视角矩阵 + §七 分级因子管理（L1/L2/L3/L4） |
| experiment-plan.md | ✅ v0.1 | 实验矩阵 · 12 候选清单 + Wave 1/2/3 优先级 + M1–M5 里程碑 |
| strategy-math-spec.md | ⏳ 未建 | 需在有具体策略候选时再补（本主题以筛选为主，暂不定义策略行为） |
| parameter-selection-spec.md | ⏳ 未建 | 需在实验后创建 |
| implementation-notes.md | ⏳ 未建 | 需在工程实现开始时创建 |

## 4. 阅读顺序

新接手本主题的研究者：

1. 先读 [research-status.md](research-status.md) 确认主题当前状态（待启动）
2. 精读上游 kf:structural-shaping-alpha 的 §2.22（KF-26 数学基础）+ §2.23（KF-27 参数优化器）+ §2.23.5/§2.23.6（se KPI 推导）
3. 复用上游工具：
   - `theme:structural-shaping-alpha/raw-scripts/kf26_parameter_optimizer.py`（参数反解）
   - `theme:structural-shaping-alpha/raw-scripts/corn_1h_strength_three_views.py`（$|\nu|/\sigma$ 分布拟合）
4. 未来任何候选识别器（波动率制度切换 / 结构突破 / 板块共振 / event）都必须先通过 se ≤ se_target gate 才能立子实验

## 5. 与其他主题的关系

- **上游**：theme:structural-shaping-alpha（工具资产 + 兑现容器 + KPI 定义源）
- **下游**：暂无（本主题是终点，识别器验证后直接进入策略工程）
- **家族关系**：暂未建家族；若未来出现多个"强度类因子"主题（如按识别器种类分主题），可考虑聚合到 `strength-factor/` 家族
