# time-barrier-selection

> 类型：Research / 活跃主题
> 状态：活跃（立题 2026-07-28）
> 开发分支：`experiment/time-barrier-selection`
> 开分支 hash：`032d73ad7aacfc76c68d4d4351d7f520d6c6e7cc`（`dev/0.6` HEAD）
> 上游数学契约：`theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha`

## 1. 一句话定位

在塑形理论 `theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha` 的容器 $(K_S, K_T, T)$ 中，本主题**只研究单个合约的时间维 $T$**：找到"波动率相对小、漂移相对稳定"的持仓周期，使得给定 $(K_S, K_T)$ 下单笔期望净收益 $\mathbb{E}[E_{\text{net}}] = \mathbb{E}[X_\tau] - 2c > 0$。

**为什么单独立题**：when-barrier-shaping-yields-alpha 的 §10（KF-27）已给出"分布输入闭式解"用于 $(K_S, K_T, \tau_\text{q})$ 优化，但其**时间维默认按 $T \to \infty$ 处理**（FPT 长期区）；对于单合约实盘持仓，$T$ 是硬约束——它决定 (a) 是否触及 $T^\ast$ 长期区 / 过渡区导致 time-exit 概率非零，(b) 单笔期望持仓 bar 数是否满足 $\mathbb{E}[E_{\text{net}}] > 2c$ 的成本覆盖门槛。本主题把 $T$ 从"参数"升级为"决策变量"。

## 2. 文档地图

| 文件 | 回答的问题 |
|------|-----------|
| [research-status.md](research-status.md) | 当前一句话结论 / 关键发现清单 / 下一步 |
| [experiment-plan.md](experiment-plan.md) | 玉米 5m 持仓周期扫描的候选矩阵、判据、验证顺序 |
| [strategy-math-spec.md](strategy-math-spec.md) | 时间维塑形的数学契约（占位：广度扫描通过后再补完整规格，见 `quant-research-methodology` §8） |
| [parameter-selection-spec.md](parameter-selection-spec.md) | 参数分层规则（占位） |
| [implementation-notes.md](implementation-notes.md) | 工程实现细节（占位） |
| [archive-references.md](archive-references.md) | 与本主题相关的 archive 目录索引 |

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
`theme:time-barrier-selection#experiment-plan`（实验计划）
