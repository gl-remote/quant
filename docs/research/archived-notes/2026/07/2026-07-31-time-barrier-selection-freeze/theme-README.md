# time-barrier-selection

> 类型：Research / 🧊 **已冻结**（2026-07-31，主题使命完成）
> 状态：立题（2026-07-28）→ Stage 1 归档（方向修正）→ Stage 2/3/4 完成 → 冻结（2026-07-31）
> 冻结批次：`archive:2026-07-31-time-barrier-selection-freeze`
> 方向修正批次：`archive:2026-07-31-time-barrier-selection-redirection`
> theorem 沉淀：`theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha` §10.5（p-混合闭式）
> 开发分支：`experiment/time-barrier-selection`
> 上游数学契约：`theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha`

## 1. 一句话定位

在塑形理论 `theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha` 的容器 $(K_S, K_T, T)$ 中，本主题**只研究市场强度的时间维 $T$**：先描述性测量"市场强度 $|s| = |\nu|/\sigma$ 的分布"在**不同周期**（1m/5m/15m/1h）和**不同品种**（c/m/rb）上的结构（Stage 2/3 已完成：μ_D 跨周期跨品种量级一致 0.04–0.07、ρ_1 收敛到 0、mean(|s|) 递增斜率品种相关），再据此为下游塑形实验提供 $T$ 取值先验（Stage 4）。

**为什么单独立题**：当 barrier-shaping-yields-alpha 的 §10（KF-27）已给出"分布输入闭式解"用于 $(K_S, K_T, \tau_\text{q})$ 优化，但其**时间维默认按 $T \to \infty$ 处理**（FPT 长期区）；对于单合约实盘持仓，$T$ 是硬约束。本主题把 $T$ 从"参数"升级为"决策变量"，先把市场本身的强度分布跨周期、跨品种摸清（Stage 2/3），再决定塑形容器在哪个周期 / 哪个 $T$ 最有意义（Stage 4）。

## 2. 文档地图

| 文件 | 回答的问题 | 状态 |
|------|-----------|------|
| [research-status.md](research-status.md) | 主题一句话结论 / KF 清单 / 冻结状态 | 🧊 KF-1..9，已冻结 |
| [archive-references.md](archive-references.md) | 本主题相关 archive 批次索引 | ✅ 已登记 2 批次 |
| **Stage 1 归档** | `archive:2026-07-31-time-barrier-selection-redirection` | 🧊 方向修正批次 |
| **Stage 2/3/4 冻结批次** | `archive:2026-07-31-time-barrier-selection-freeze` | 🧊 主题最终归档 |
| **沉淀到 theorem** | `theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha` §10.5 | ✅ p-混合闭式（命题 10.6/10.7/10.8）|

## 3. 上游依赖

- **数学契约**（不复述、只引用）：
  - `theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha` — 双 barrier 塑形的两条 alpha 通道、Doob 保守律、Fourier 有限时间 null、$T^\ast$ 分界；
  - `theorem:structural-shaping-alpha#winrate-payoff-tradeoff-under-frictions` — 胜率-盈亏比的市场刚性边界与摩擦修正；
  - `theorem:structural-shaping-alpha#piecewise-static-kelly-vs-fixed-risk` — 仓位管理（本主题只做单笔期望，仓位管理由该 theorem 覆盖，不重复）。

- **方法论约束**：见 [strategy-current.md §5](../../strategy-current.md#5-下一步) 的 12 条前置约束（ATR 归一化、期望净值判据、随机对照、cluster bootstrap 等）。

## 4. 引用护栏声明（域内 / 域外）

按 `quant-project` skill 的"归档文档引用规则"，本主题引用 `structural-shaping-alpha` 结论时的**域内使用范围**：

- ✅ **域内**：ATR 归一化度量、双 barrier 塑形容器 $(K_S, K_T, T)$、期望净值 $\mathbb{E}[E_{\text{net}}]$ 判据、Doob 保守律作为零 alpha null、Fourier 有限时间 null；
- ⚠️ **需重新验证**：本主题**跨时间粒度**（5m）与原主题的实证锚点（1h + FoldedNormal(0.198, 0.108)）不同；`x_{\min}(c, K_S, R) = \sqrt{6c/(K_S^3 R(R-1))}$ 的下界在 ATR 归一化后**scale-invariant**（可直接引用），但 5m 品种的 $|s|$ 分布 $D$ 需重新拟合，不能复用玉米 1h 的 $(K_S^\ast = 3.0, K_T^\ast = 9.0)$ 结论；
- ❌ **域外**：任何"5m 最优 $T = XX$ bar"或"5m Sharpe = XX"的结论必须来自本主题实证，不得从 1h 主题外推。

## 5. 命名引用

`theme:time-barrier-selection`（主题目录本身）·
`theme:time-barrier-selection#research-status`（关键发现清单）·
`archive:2026-07-31-time-barrier-selection-redirection#raw-docs/experiment-plan`（Stage 1 旧实验计划）
