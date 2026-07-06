# First-Passage Designer · 数学 Spec

> 类型：Reference / 数学规范
> 状态：草案 v2（2026-07-06 重构 · 分为 5 大部分）
> 定位：**分布形态设计器** —— GBM 假设下解析计算 barrier 组合的
> 首达概率、期望净值、持仓时间，作为**结构塑形 combo 设计的解析基准**
> 上游主题：`theme:structural-shaping-alpha`（KF-1..8）
> 上游 Roadmap：[strategy-research-framework.md](../../../roadmap/strategy-research-framework.md)

***

## 阅读指南

本文档同时服务两类读者，按不同顺序阅读：

| 读者 | 推荐入口 | 阅读顺序 |
|------|---------|---------|
| **产品/策略设计者** | [Part I 模型选择](#part-i--模型选择what--why) | I → V → 附录 |
| **数学审查者** | [Part II 数学基础](#part-ii--数学基础math-foundation) | II → III → IV → 附录 |
| **AI/工程实现者** | [Part V 实现指南](#part-v--实现指南implementation-guide) | V →（回查 II-IV 对应公式）|

**符号约定**（全文统一）：

| 符号 | 含义 | 单位 |
|------|------|------|
| $S_t$ | 时刻 $t$ 的价格 | 元 |
| $X_t = \ln(S_t/S_0)$ | 对数价格（以入场价 $S_0$ 归一化）| 无量纲 |
| $\mu$ | GBM 漂移率 | 时间$^{-1}$ |
| $\nu = \mu - \sigma^2/2$ | 对数空间漂移率（Itô 修正）| 时间$^{-1}$ |
| $\sigma$ | GBM 波动率 | 时间$^{-1/2}$ |
| $\lambda = 2\nu/\sigma^2$ | 无量纲漂移比 | 无量纲 |
| $K_S > 0$ | 止损距离（ATR 归一化） | ATR |
| $K_T > 0$ | 止盈距离（ATR 归一化） | ATR |
| $a = -K_S$ | 止损下界（对数空间） | ATR |
| $b = +K_T$ | 止盈上界（对数空间） | ATR |
| $T$ | 时间上限 | 时间 |
| $\tau$ | 首达停时 | 时间 |
| $\tau^* = \min(\tau, T)$ | 实际出场时刻 | 时间 |
| $c$ | 单边交易成本（ATR 归一化）| ATR |
| $r_{\text{acct}}$ | 单笔账户风险预算 | 无量纲 |
| $P^{\text{target}}$ | 目标胜率 | 无量纲 |
| $f_{\max}$ | 凯利仓位上限 | 无量纲 |

***

## ⚠️ 关键警告 · μ 与 ν 的区别不能混淆

**本项目最容易犯的错误之一**：把"$\mu > 0$"直接当作"市场有真实正漂移"。
**这个直觉在 GBM 下是错的**。

### 数学事实

由 Itô 引理，对数价格 $X_t = \ln(S_t/S_0)$ 的漂移是 $\nu = \mu - \sigma^2/2$，
**不是 $\mu$**。首达概率 $P_{\text{win}}(\lambda)$ 由 $\lambda = 2\nu/\sigma^2$
决定：

- **$\nu = 0$**（即 $\mu = \sigma^2/2$）：$X_t$ 是 martingale → $E[\text{gross}] \equiv 0$
- **$\nu > 0$**（即 $\mu > \sigma^2/2$）：真正的正漂移 → $E[\text{gross}] > 0$
- **$\nu < 0$**（即 $\mu < \sigma^2/2$）：真正的负漂移 → $E[\text{gross}] < 0$

**当 $\mu = 0$ 时，$\nu = -\sigma^2/2 < 0$** —— 即使 $\mu = 0$，对数价格
仍然有**轻微负漂移**（Itô 凸性修正）。

### 归因判据必须用 $\nu$，不能用 $\mu$

| 判据 | 表述 | 用于什么 |
|------|------|---------|
| ❌ **不要用** $\mu / \sigma$ | 会把 Itô 凸性修正误判为"市场有漂移" | 直觉表达（口语中可粗糙用）|
| ✅ **必须用** $\nu / \sigma$ | 对数空间的"真实漂移强度" | 归因、判决、$\mu_{\text{implied}}$ 反算 |

**决策阈值**（本 spec 采用）：

| $\|\nu / \sigma\|$ | 归因 |
|--------------------|------|
| $< 0.02$ | **martingale · GBM 无漂移完美对齐** |
| $< 0.10$ | 接近 martingale · 微弱漂移或非 GBM 溢价 |
| $\ge 0.10$ | 显著隐含正/负漂移（GBM 可解释）|

### 本项目实测印证

`theme:structural-shaping-alpha` §8.11 所有 combo 的实测 $\nu_{\text{implied}}$
反算结果 **全部 $|\nu/\sigma| \le 0.04$**（见 [first-passage-lookup-tables.md 表 5](../../../workbench/first-passage-lookup-tables.md)）：

- **A @ 5m real**：$\nu/\sigma = -0.001$ → 完美 martingale
- **M/N @ SCALE=5**：$\nu/\sigma = +0.002$ → 完美 martingale（正 mean 来自 Itô 凸性 + 长期区放大）
- **L @ 15m**：$\nu/\sigma = +0.028$ → 接近 martingale（微弱溢价可能来自非 GBM 属性）

**含义**：本主题所有"看似正 mean"的 combo，**没有一个来自真实市场正漂移**——
它们全部是 GBM 的 Itô 凸性 + 时间尺度放大效应。**KF-1 martingale 恒等式
在实测中精确成立**。

### 归因升级的含义

本项目 framework §1 "承认不能预测未来" 现在有精确数学定义：

**不能预测的是 $\nu > 0$，不是 $\mu > 0$**。

未来任何策略主题声称"找到方向 alpha"时，**必须证明 $\nu_{\text{implied}} > 0$
且显著**，不能只看 $\mu > 0$。这是一个**远高于"$\mu > 0$"** 的门槛。

***

# Part I · 模型选择（What & Why）

## 1.1 我们建模的问题

**问题**：入场后价格 $S_t$ 在设定的止损 $a$、止盈 $b$、时间上限 $T$ 之间演化，
问：**首次触达 $a$ 或 $b$ 的概率是多少？平均持仓时间是多少？单笔期望收益
是多少？**

**这是一个"三边框内的随机过程首达问题"**：

```
    价格
     ↑
   b ┤━━━━━━━━━━━━━ 止盈上界（吸收）
     │       ╱╲
     │      ╱  ╲       ╱
     │  ╱╲ ╱    ╲     ╱
   0 ┤─╱──╲──────╲───╱────  入场价 S_0
     │╱    ╲      ╲ ╱
     │      ╲      ╱
   a ┤━━━━━━━╲━━━━━━━━━━━━  止损下界（吸收）
     └──────────────┴──── 时间
                    T（时间上限）
```

**三种可能的出场路径**：

1. 价格先触到 $b$ → 止盈出场
2. 价格先触到 $a$ → 止损出场
3. 在时间 $T$ 内既没触 $a$ 也没触 $b$ → time_exit 出场

**问题的完整数学描述**：给定价格过程 $\{S_t\}$，求：

- **首达止盈概率** $P_{\text{win}} = P(X_\tau = b)$
- **首达止损概率** $P_{\text{loss}} = P(X_\tau = a)$
- **Time-exit 概率** $P_{\text{time}} = P(\tau > T)$
- **平均出场时间** $E[\tau^*]$，其中 $\tau^* = \min(\tau, T)$
- **单笔期望收益** $E[\text{gross}] = E[X_{\tau^*}]$

## 1.2 我们选择的价格过程模型：几何布朗运动（GBM）

**GBM 定义**：价格 $S_t$ 满足随机微分方程

$$
dS_t / S_t = \mu \, dt + \sigma \, dW_t
$$

- $\mu$：漂移率（价格的长期趋势速度）
- $\sigma$：波动率（价格的随机波动强度）
- $W_t$：标准 Wiener 过程（"完全无记忆的连续随机游走"）

**取对数变换后**（Itô 引理）：

$$
X_t = \ln(S_t/S_0) \Rightarrow dX_t = \nu \, dt + \sigma \, dW_t, \quad \nu = \mu - \sigma^2/2
$$

**为什么选 GBM**（五个理由，按重要性排序）：

1. **假设最少**：只需两个参数 $(\mu, \sigma)$ 描述整个价格过程 —— 假设越少，
   越少偷偷引入错觉
2. **首达问题有精确解析解**：$P_{\text{win}}, E[\tau], E[\text{gross}]$
   都能用初等函数写出来 —— 不需要数值模拟，秒级计算
3. **恒等式最干净**：$\mu = 0$ 时期望恒 = 0（martingale + Optional Stopping），
   直接给出"无漂移下任何 barrier 组合期望 = 0"这条本项目 KF-1 的
   **数学根源**
4. **与本项目研究哲学契合**：framework §1 明确"承认不能稳定预测未来"，
   GBM 是**"最诚实的价格模型"**——所有未来收益都归结为 $(\mu, \sigma)$，
   $\mu$ 未知即诚实承认"我们不知道市场走向"
5. **可退化到无漂移子模型**：$\mu \to 0$ 时 GBM 退化为几何 martingale，
   工具可以在同一个数学框架下同时处理"无漂移"和"有漂移"两种假设

**GBM 假设的三条硬约束**（$P_{\text{win}}$ 精确解成立的前提）：

- 价格连续（无跳空）
- 收益率对数正态分布
- 波动率恒定（$\sigma$ 不随时间变化）

**这些约束在真实市场里都不完全成立**（详见 §1.6），因此工具输出是**理想化基准**，
实测偏差 = 市场非 GBM 属性带来的"溢价/亏损"。

## 1.3 模型的三层结构

工具输出的所有量按 **"从纯数学 → 加漂移 → 校准实测"** 三层展开：

### 第一层 · 数学恒等式（$\mu = 0$ 或 $\lambda = 0$）

**核心恒等式**：

$$
\boxed{E[\text{gross}] \equiv 0, \quad E[\text{net}] \equiv -2c}
$$

**含义**：无漂移假设下，**任何**双侧 barrier 组合（不管你怎么调 $K_S, K_T, T$）
期望净值恒等于负成本。**这是数学事实，不是猜测**。

**用途**：
- 排除"数学上必输"的参数组合（回答"哪些止盈位置肯定不该设"）
- 作为"零假设"基准：如果实测 $E[\text{net}] \ne -2c$，则市场必然存在
  某种非 GBM 属性或非零漂移

### 第二层 · 有漂移分析（$\mu \ne 0$）

**核心工具**：$P_{\text{win}}^{\infty}(\lambda)$ 的 Gerstein-Ito 公式，其中
$\lambda = 2\nu/\sigma^2$。

**输出**：
- **μ 敏感性表**：对不同 $\mu$ 假设，$E[\text{net}]$ 是多少
- **盈亏平衡漂移 $\mu^*$**：让 $E[\text{net}] = 0$ 所需的最小 μ
- **止盈可行区间 $[K_T^{\min}, K_T^{\max}]$**：在给定 μ 假设下哪些止盈位置
  数学上可行

**用途**：
- **让 μ 假设显式化**：策略设计者必须明确"我在赌市场有多大漂移"
- **判断合理性**：$\mu^* > \sigma$ 意味着这个 combo 需要不合理的强漂移才能盈利

### 第三层 · 实测校准（$\mu_{\text{implied}}$ 反算）

**核心工具**：从实测 $E[\text{net}]^{\text{obs}}$ 反解 $\mu_{\text{implied}}$。

**用途**：
- **归因**：实测正 mean 是"市场有隐含正漂移"还是"GBM 之外的属性"（fat tail 等）
- **假设检验**：反算的 $\mu_{\text{implied}}$ 若过大，说明 GBM 假设不够，
  需要引入非 GBM 特性（跳空 / 波动率聚集）

## 1.4 短期 vs 长期的关键分界（用户核心诉求）

用户诉求原话：

> "模型要加上短期完全是随机游走，长期可能有趋势时间。这样我们就知道
> 入场应该在什么点位肯定不能止盈了至少。"

**GBM 模型天然支持这个诉求**，因为它有一个**数学分界 $T^*$**：

$$
\boxed{T^* := \frac{[\max(K_S, K_T)]^2}{\sigma^2}}
$$

**物理含义**：$T^*$ 是"无漂移下平均触达 barrier 所需时间"的量级。

**三档区间**：

| 区间 | 条件 | 行为 | 决策 |
|------|------|------|------|
| **短期区** | $T \ll T^*$ | 首达定理支配 · μ 影响可忽略 | 无 μ 假设时 $E[\text{net}] \approx -2c$ · 必输 |
| **过渡区** | $T \sim T^*$ | 完整解析 · μ 部分影响 | μ 敏感性至关重要 |
| **长期区** | $T \gg T^*$ | 漂移主导 · $E[\text{gross}] \to \nu T$ | μ 决定一切 |

**回答用户诉求**：**如果 $T < T^*$ 且没有 μ ≠ 0 的假设理由，任何止盈都是浪费**
—— 不是"这个止盈位置错了"，而是"数学告诉你这个时间区间里没有止盈能挽救期望"。

## 1.5 输出与应用场景

**给定 combo 参数 $(K_S, K_T, T)$ 和市场假设 $(\mu, \sigma, c)$，工具输出**：

| 输出 | 含义 | 层次 |
|------|------|------|
| $P_{\text{win}}, P_{\text{loss}}$ | 首达概率 | 第一/二层 |
| $E[\text{gross}], E[\text{net}]$ | 单笔期望收益 | 第一/二层 |
| $E[\tau]$ | 平均持仓时间 | 第一/二层 |
| $T^*$ | 短期/长期分界 | 第一层 |
| $\mu^*$ | 盈亏平衡漂移 | 第二层 |
| $[K_T^{\min}, K_T^{\max}]$ | 止盈可行区间 | 第二层 |
| $T^\dagger$ | 临界离场时限 | 第二层 |
| $f_{\text{Kelly}}, f_{\text{final}}$ | 建议仓位 | 第二层 |
| $\mu_{\text{implied}}, \sigma_{\text{implied}}$ | 实测反算 | 第三层 |

**5 项核心应用场景**：

1. **数学预筛**：先用 μ=0 算 $E[\text{net}]$，负值就直接淘汰 combo，省去实测算力
2. **假设显式化**：策略设计者明确"我假设 μ = 多少"，工具告诉 μ 假设下的可行区间
3. **胜率反解 R:R**：给定目标胜率，工具反解需要的止盈距离（首达定理硬约束）
4. **凯利仓位**：给定 combo 期望 + 账户风控预算，工具算最终仓位（含部分凯利）
5. **实测归因**：实测 mean 显著正时，工具反算 μ_implied，判断归因是"市场有漂移"
   还是"非 GBM 属性"

## 1.6 模型的边界与警告（诚实标注）

**工具的价值边界必须明确**：

### 1.6.1 不建模的东西

| 属性 | 影响 |
|------|------|
| **Fat tail** | 工具低估极端事件概率 |
| **波动率聚集**（GARCH）| $\sigma$ 时变，工具用常数近似 |
| **跳空** | GBM 无跳，无法建模隔夜穿破 stop |
| **均值回归** | GBM 是 martingale，无回归 |
| **微观结构噪声** | 高频尺度失效 |

### 1.6.2 不承担的任务

- **不做方向预测**：与 framework §1 "承认不能预测未来" 一致，工具不告诉你
  "做多还是做空"、"什么时候入场"
- **不寻找"最优参数"**：GBM 假设下 μ 未知时，"最优 $K_T$" 数学上无解
  （μ=0 恒 = 0；μ≠0 时最优 = ∞），任何"最优"表述都在偷偷假设 μ
- **不做参数调优**：不给"最佳 $(K_S, K_T, T)$" 数值，只回答"给定这组参数，
  理论量是多少"
- **不是决策器**，是**假设显式化器** —— 让每个决策的"隐藏 μ 假设"曝光

### 1.6.3 μ 假设的诚实性警告

**工具输出所有涉及 $\mu \ne 0$ 的决策都依赖 μ 假设**：

- 若假设错误（假设 $\mu > 0$ 但实际 $\mu = 0$），会给出**假的 wide 判决**
- 工具**必须搭配 §4.1 μ_implied 反算**验证假设合理性
- 使用工作流：**先用 μ=0 硬淘汰 → 再用 μ 假设列 what-if → 最后用实测反算校准**

### 1.6.4 什么时候工具会失效

**GBM 假设严重违背时**（如极端跳空、突发波动率跳变），工具输出与实测差距大 —— 但这个差距本身就是有价值的信号（说明当前市场处于非 GBM 制度）。**工具的"失败"就是提醒"这里需要引入更复杂的模型"**。

***

# Part II · 数学基础（Math Foundation）

## 2.1 价格过程

价格 $S_t$ 满足几何布朗运动（GBM）：

$$
dS_t / S_t = \mu \, dt + \sigma \, dW_t
$$

其中 $W_t$ 为标准 Wiener 过程。

以入场价 $S_0$ 归一化的对数价格：

$$
X_t = \ln(S_t / S_0), \quad X_0 = 0
$$

由 Itô 引理，$X_t$ 满足带漂移 $\nu = \mu - \sigma^2/2$、扩散 $\sigma$ 的算术
布朗运动（ABM）：

$$
dX_t = \nu \, dt + \sigma \, dW_t
$$

**为什么用 $\nu$ 而不是 $\mu$**：$\nu$ 是对数空间的漂移率，扣除了 Itô 引理的
凸性修正 $\sigma^2/2$。首达问题在对数空间处理更干净。

## 2.2 双侧吸收边界

- **止损下界**：$a = -K_S$
- **止盈上界**：$b = +K_T$
- **首达停时**：$\tau = \inf\{t > 0: X_t \le a \text{ 或 } X_t \ge b\}$
- **实际出场**：$\tau^* = \min(\tau, T)$

## 2.3 首达概率（$T = \infty$）

在无时间约束下，$X_t$ 必然先触达 $a$ 或 $b$ 之一（GBM 递归返回性）。

**首达止盈概率**（$X_\tau = b$）：

$$
\boxed{P_{\text{win}}^{\infty}(\lambda; K_S, K_T) =
\begin{cases}
\dfrac{1 - e^{-\lambda K_S}}{e^{\lambda K_T} - e^{-\lambda K_S}} \cdot e^{\lambda K_T}
  = \dfrac{e^{\lambda K_T} \cdot (1 - e^{-\lambda K_S})}{e^{\lambda K_T} - e^{-\lambda K_S}}
  & \lambda \ne 0 \\[10pt]
\dfrac{K_S}{K_S + K_T} & \lambda = 0
\end{cases}}
$$

其中 $\lambda = 2\nu / \sigma^2$。

**首达止损概率**：

$$
P_{\text{loss}}^{\infty} = 1 - P_{\text{win}}^{\infty}
$$

**极限验证**：$\lambda \to 0$ 时 Taylor 展开：

$$
e^{\lambda K_T} \to 1 + \lambda K_T, \quad e^{-\lambda K_S} \to 1 - \lambda K_S
$$

代入：

$$
P_{\text{win}}^{\infty}(\lambda \to 0) \to \frac{(1 + \lambda K_T)(1 - (1 - \lambda K_S))}
{(1 + \lambda K_T) - (1 - \lambda K_S)}
= \frac{\lambda K_S (1 + \lambda K_T)}{\lambda (K_T + K_S) + O(\lambda^2)}
\to \frac{K_S}{K_S + K_T}
$$

**与实测对齐**：本主题 workbench §8.3 的 A/B/C/E/G/H/I combo 实测胜率精确
匹配 $\lambda = 0$ 公式，误差 ≤ 0.02，是 KF-6 的数学根源。

## 2.4 平均首达时间（$T = \infty$）

**$\lambda \ne 0$**：

$$
E[\tau] = \frac{K_S \cdot P_{\text{loss}}^{\infty} - K_T \cdot P_{\text{win}}^{\infty}}{-\nu}
$$

（推导：对 $\phi(x) = x$ 应用 Dynkin 公式）

**$\lambda = 0$**（对上式取极限或直接用 Optional Stopping）：

$$
\boxed{E[\tau] \bigg|_{\lambda = 0} = \frac{K_S \cdot K_T}{\sigma^2}}
$$

**物理直觉**：barrier 越远、$\sigma$ 越小，平均持仓越长。

## 2.5 期望收益

**Gross 期望**（不含成本）：

$$
E[\text{gross}] = P_{\text{win}}^{\infty} \cdot K_T - P_{\text{loss}}^{\infty} \cdot K_S
$$

**$\lambda = 0$ 恒等式**（**本项目 KF-1 的数学根源**）：

$$
\boxed{E[\text{gross}] \bigg|_{\lambda = 0}
= \frac{K_S}{K_S + K_T} \cdot K_T - \frac{K_T}{K_S + K_T} \cdot K_S \equiv 0}
$$

**推广**：由 Optional Stopping Theorem 应用于 martingale $X_t$（$\lambda = 0$），
**任何有限 stopping time 出场规则** $\sigma$-代数（time exit / trailing / breakeven）
都有 $E[X_\sigma] = 0$。**这是本项目 KF-2 的数学根源**。

**Net 期望**：

$$
E[\text{net}] = E[\text{gross}] - 2c
$$

**$\lambda = 0$ 情形**：

$$
\boxed{E[\text{net}] \bigg|_{\lambda = 0} \equiv -2c}
$$

**$\lambda \ne 0$ 情形**：$P_{\text{win}}^{\infty}(\lambda)$ 关于 $\lambda$ 单调递增，
因此 $E[\text{gross}]$ 关于 $\lambda$ 单调递增：

- $\lambda > 0$（正漂移）：$E[\text{gross}] > 0$
- $\lambda < 0$（负漂移）：$E[\text{gross}] < 0$

## 2.6 有限时间修正（$T < \infty$）

### 2.6.1 Time-exit 概率

$P(\tau > T)$ = 时间 $T$ 内 $X_t$ 未触达任何 barrier 的概率。

**$\lambda = 0$ 情形**（用镜像法 / Fourier 级数）：

$$
\boxed{P(\tau > T)\bigg|_{\lambda=0}
= \frac{4}{\pi} \sum_{n=0}^{\infty} \frac{1}{2n+1}
\sin\left(\frac{(2n+1)\pi K_S}{K_S + K_T}\right)
\exp\left(-\frac{(2n+1)^2 \pi^2 \sigma^2 T}{2(K_S + K_T)^2}\right)}
$$

**数值实现**：前 5-10 项足以收敛（收敛速率 $e^{-n^2}$）。

**$\lambda \ne 0$ 情形**：类似 Fourier 级数，含额外 $e^{\nu x/\sigma^2}$ 因子，见附录。

### 2.6.2 Time-exit 条件期望

给定 $\tau > T$（time_exit 样本），$X_T$ 的条件期望：

$$
E[X_T \mid \tau > T] = \int_a^b x \cdot p(x, T \mid \tau > T) \, dx
$$

其中 $p(x, T \mid \tau > T)$ 由 Feynman-Kac 公式或 Fourier 级数给出。

**$\lambda = 0$ 简化**：对称性下，若 $K_S = K_T$，$E[X_T \mid \tau > T] = 0$。
若 $K_S \ne K_T$，条件期望偏向距离较远侧。

### 2.6.3 有限时间完整期望

$$
E[\text{gross}](T) = E[X_\tau \cdot \mathbf{1}_{\tau < T}] + E[X_T \cdot \mathbf{1}_{\tau > T}]
$$

- 前项 = $P_{\text{win}}(T) \cdot K_T - P_{\text{loss}}(T) \cdot K_S$
- 后项 = $E[X_T \mid \tau > T] \cdot P(\tau > T)$

## 2.7 短期/长期分界 $T^*$

**定义**：

$$
\boxed{T^* := \frac{[\max(K_S, K_T)]^2}{\sigma^2}}
$$

**物理直觉**：$T^*$ 是"无漂移下平均触达 barrier 所需时间"的量级。

**三档区间**：

| 区间 | 条件 | 行为 |
|------|------|------|
| **短期区** | $T \ll T^*$ | 首达定理支配 · μ 影响可忽略 · $E[\text{gross}] \approx 0$ |
| **过渡区** | $T \sim T^*$ | 完整解析 · μ 部分影响 |
| **长期区** | $T \gg T^*$ | 漂移主导 · $E[\text{gross}] \to \nu \cdot T$ |

**决策规则**（回答用户"什么点位肯定不能止盈"）：

- **$T \ll K_T^2 / \sigma^2$**：止盈物理不可达（触达概率极低）
- **$K_T^2/\sigma^2 \ll T \ll T^*$**：处于短期区 → $E[\text{gross}] \approx 0$
  → 任何止盈都是 -2c → **必输区**
- **$T \gtrsim K_T / |\mu|$**：漂移开始主导 → 期望依赖 μ 假设

***

# Part III · 核心导出量（Derived Quantities）

## 3.1 μ 敏感性 $E[\text{net}](\mu)$

给定 $(K_S, K_T, T, \sigma, c)$，$E[\text{net}]$ 作为 $\mu$ 的函数：

$$
E[\text{net}](\mu) = E[\text{gross}](\lambda(\mu)) - 2c
$$

其中 $\lambda(\mu) = 2(\mu - \sigma^2/2)/\sigma^2$。

**输出形式**（工具应实现）：

对 $\mu \in \{-\sigma, -0.5\sigma, 0, +0.5\sigma, +\sigma\} / \text{day}$
（或用户指定档位），输出 5 个 $E[\text{net}]$ 值，形成敏感性表。

## 3.2 盈亏平衡漂移 $\mu^*$

**定义**：使 $E[\text{net}](\mu) = 0$ 的 $\mu$：

$$
\mu^* := \{\mu : E[\text{gross}](\lambda(\mu)) = 2c\}
$$

**求解**：由 $P_{\text{win}}^{\infty}$ 关于 $\lambda$ 单调，
$E[\text{gross}]$ 关于 $\mu$ 单调递增，唯一解，用 `scipy.optimize.brentq` 在
区间 $[-\sigma, +\sigma]$ 内找零点。

**决策规则**：

| $\mu^*$ 范围 | 业务含义 |
|------------|---------|
| $\mu^* > \sigma$ | 需要过强正漂移 → **淘汰** |
| $0 < \mu^* < 0.5\sigma$ | 中等正漂移要求 → **验证市场 μ 现实性** |
| $\mu^* \le 0$ | 任何 μ ≥ 0 都能盈利 → **相对稳健** |

## 3.3 止盈可行区间 $[K_T^{\min}, K_T^{\max}]$

### 3.3.1 输入五参数

| 参数 | 符号 | 含义 |
|------|------|------|
| 账户风险预算 | $r_{\text{acct}}$ | 单笔最大账户亏损比例（如 2-3%）|
| 目标胜率 | $P^{\text{target}}$ | 希望的胜率 |
| 凯利上限 | $f_{\max}$ | 单笔最大凯利仓位比例 |
| 时间上限 | $T$ | 最长持仓时间 |
| 市场假设 | $(\mu, \sigma, c)$ | 漂移、波动、成本 |

### 3.3.2 反解 $K_S$（风控约束）

设账户 $A$、手数 $n_{\text{lots}}$、tick 价值 $v_{\text{tick}}$、
真实 ATR（元）$\text{ATR}_{\yen}$：

$$
K_S \le \frac{r_{\text{acct}} \cdot A}{n_{\text{lots}} \cdot v_{\text{tick}} \cdot \text{ATR}_{\yen}}
$$

**含义**：止损位置由风控预算硬约束。

### 3.3.3 反解 $K_T^{P}$（目标胜率）

**$\lambda = 0$**：由首达定理直接反解：

$$
K_T^P = K_S \cdot \frac{1 - P^{\text{target}}}{P^{\text{target}}}
$$

**胜率-R:R 对照表**（$K_S = 1.5$）：

| $P^{\text{target}}$ | $K_T^P$ | R:R |
|---------------------|---------|-----|
| 25% | 4.5 | 1:3 |
| 33% | 3.0 | 1:2 |
| 50% | 1.5 | 1:1 |
| 67% | 0.75 | 2:1 |
| 75% | 0.5 | 3:1 |

**$\lambda \ne 0$**：用 Newton 迭代反解 $P_{\text{win}}^{\infty}(\lambda; K_S, K_T) = P^{\text{target}}$。

### 3.3.4 反解 $K_T^{\min}$（凯利正 edge）

**约束**：$E[\text{net}] > 0$

$$
P_{\text{win}}^{\infty}(\lambda; K_S, K_T) \cdot K_T
- [1 - P_{\text{win}}^{\infty}(\lambda; K_S, K_T)] \cdot K_S > 2c
$$

**$\lambda = 0$ 情形**：不等式化简为 $-2c > 0$ → 永不成立 → $K_T^{\min} = +\infty$。

**这是本项目 KF-1 的凯利视角**：$\mu = 0$ 下任何 barrier 组合都凯利负 edge。

**$\lambda \ne 0$ 情形**：用 `scipy.optimize.brentq` 在 $(0, K_T^{\max})$ 找零点。

### 3.3.5 反解 $K_T^{\max}$（物理可达）

**约束**：$K_T$ 必须在时间 $T$ 内够得到。

$$
\boxed{K_T^{\max} = k \cdot \sigma \sqrt{T}}
$$

**三档安全系数**：

| $k$ | 触达概率（$\lambda = 0$）|
|-----|----------------------|
| 1 | ≈ 68% |
| **2** | ≈ 95%（推荐）|
| 3 | ≈ 99.7% |

### 3.3.6 可行区间综合判决

$$
\boxed{K_T \in [K_T^{\min}, K_T^{\max}]}
$$

| 情况 | 条件 | 决策 |
|------|------|------|
| **空集** | $K_T^{\min} > K_T^{\max}$ | **淘汰**（数学必输） |
| **窄区间** | $K_T^{\max} / K_T^{\min} < 1.5$ | **慎选**（高敏感）|
| **宽区间** | $K_T^{\max} / K_T^{\min} > 3$ | **强候选** |

**推荐取值**（在宽区间内）：几何均值

$$
K_T^{\text{推荐}} = \sqrt{K_T^{\min} \cdot K_T^{\max}}
$$

## 3.4 临界离场时限 $T^\dagger$

**定义**：在 barrier 未触达的样本中，条件期望浮盈达到最大的时刻：

$$
T^\dagger := \text{argmax}_t \, E[X_t \mid \tau > t]
$$

**$\lambda = 0$ 特例**：对称性下 $E[X_t \mid \tau > t] \equiv 0$（$K_S = K_T$），
**$T^\dagger$ 不存在** —— 因为浮盈期望始终 = 0。

**$\lambda > 0$ 情形**：$E[X_t \mid \tau > t]$ 先随 $t$ 上升（漂移累积），
后由于 barrier 吸收下降。$T^\dagger$ 是抛物线顶点。

**近似解**：

$$
T^\dagger \approx \frac{K_T}{\mu} \cdot k_{\text{drift}}, \quad k_{\text{drift}} \approx 0.5
$$

**精确解**：需要有限时间 Fourier 级数（§2.6）。

**决策规则**：
- $t < T^\dagger$：**保持**
- $t \ge T^\dagger$：**无条件离场**

## 3.5 凯利仓位

**建议仓位**：

$$
f^* = \frac{E[\text{net}]}{K_S \cdot K_T}
$$

**部分凯利**（避免破产风险）：

$$
f_{\text{Kelly}} = \alpha \cdot f^*, \quad \alpha \in [0.25, 0.5]
$$

**最终仓位**：

$$
f_{\text{final}} = \min(f_{\text{Kelly}}, f_{\max})
$$

若 $f^* \le 0$：**不该开仓**。

## 3.6 Trailing 简化（L combo）

标准 chandelier trailing 涉及最大值过程 $M_t = \sup_{s \le t} X_s$ 的联合分布，
需 Levy 反射原理。**本 spec 只给 L combo 简化版**：

- **规则**：MFE ≥ $K_{\text{arm}}$ 时 stop 移到 entry（$L_{\text{trail}} = K_{\text{arm}}$）
- **两阶段解法**：
  - **阶段 1**：$(a, b) = (-K_S, +K_{\text{arm}})$，无 armed 前的首达
  - **阶段 2**：conditional on armed，以 armed 时刻的 $M_t$ 为原点，
    等价问题 $(a', b') = (-K_{\text{arm}}, +\infty)$，出场规则为
    "回到 entry 或 T 到期"

完整 chandelier trailing 留作 v3 拓展。

***

# Part IV · 实测校准接口

## 4.1 μ_implied 反算

给定实测 $E[\text{net}]_{\text{obs}}$ 和已知 $(K_S, K_T, T, \sigma, c)$，
反解使理论 $E[\text{net}](\mu) = E[\text{net}]_{\text{obs}}$ 的 $\mu$：

$$
\mu_{\text{implied}} := \{\mu : E[\text{net}](\mu) = E[\text{net}]_{\text{obs}}\}
$$

**求解**：`scipy.optimize.brentq` 在合理区间内找零点。

**用途**：**将实测正 mean 归因为"市场隐含正漂移"**。

**判决规则**：

| $\mu_{\text{implied}}$ | 归因 |
|------------------------|------|
| $\gg 0$ | 市场有实测隐含正漂移（GBM 假设支持）|
| $\approx 0$ | 实测正 mean 来自 GBM 之外（fat tail / 跳空 / 波动率聚集）|
| $< 0$ | 市场有负漂移（罕见）|

## 4.2 σ_implied 反算

给定实测 $E[\tau]$ 和已知 $(K_S, K_T)$，反解 $\sigma_{\text{implied}}$，
用于**跨周期 σ 一致性检查**。

## 4.3 λ 分布拟合

对每个合约的历史事件序列，从 $(K_S, K_T, T, P_{\text{win}}^{\text{obs}}, E[\text{net}]^{\text{obs}})$
反算 $\lambda$，形成**跨品种、跨时段的 $\lambda$ 分布**。

**用途**：**"市场 μ 分布"的实测直接测量**，作为未来主题的输入。

***

# Part V · 实现指南（Implementation Guide）

## 5.1 v1 实现范围

- ✅ **§2.3** $P_{\text{win}}^{\infty}(\lambda; K_S, K_T)$ 精确解析
- ✅ **§2.4** $E[\tau]$ 精确解析（$T = \infty$）
- ✅ **§2.5** $E[\text{gross}], E[\text{net}]$ 精确解析（$T = \infty$）
- ✅ **§2.7** $T^*$ 短期/长期分界
- ✅ **§3.1-3.2** μ 敏感性 + $\mu^*$ 求解
- ✅ **§3.3** 止盈可行区间反解
- ✅ **§3.5** 凯利仓位计算
- ✅ **§4.1** μ_implied 反算

## 5.2 v2 拓展

- ⏳ **§2.6.1** $P(\tau > T)$ Fourier 级数
- ⏳ **§2.6.2** $E[X_T \mid \tau > T]$ 条件期望
- ⏳ **§3.4** 精确 $T^\dagger$（依赖 §2.6.2）
- ⏳ **§3.6** L combo 两阶段简化 trailing

## 5.3 v3 拓展

- ⏳ 完整 chandelier trailing（Levy 反射）
- ⏳ 事件-level GBM 假设检验（Kolmogorov-Smirnov）
- ⏳ 波动率制度分层

## 5.4 输入接口

```python
@dataclass
class MarketParams:
    """市场假设参数（用户提供）。"""
    sigma: float          # 每单位时间波动率 (ATR / sqrt(time_unit))
    mu: float = 0.0       # 漂移率 (ATR / time_unit，默认 0)
    cost: float = 0.05    # 单边成本 (ATR)
    time_unit: str = "hour"  # 时间单位


@dataclass
class ComboParams:
    """combo 参数（策略设计者提供）。"""
    K_S: float            # 止损距离 (ATR)
    K_T: float            # 止盈距离 (ATR)
    T: float              # 时间上限 (time_unit)


@dataclass
class RiskParams:
    """账户风控参数（framework §5 约束）。"""
    r_acct: float = 0.03           # 单笔账户风险预算
    P_target: float = 0.33         # 目标胜率
    f_max: float = 0.03            # 凯利上限
    account: float = 100000        # 账户规模（元）
    contract_spec: Optional[ContractSpec] = None
    kelly_fraction: float = 0.5    # 部分凯利系数 α
```

## 5.5 核心函数签名

```python
def p_win(lam: float, K_S: float, K_T: float) -> float:
    """§2.3 首达止盈概率。lam = 2*nu/sigma^2。"""

def e_tau_infty(lam: float, K_S: float, K_T: float, sigma: float, nu: float) -> float:
    """§2.4 平均首达时间（T=infty）。lam=0 时用简化公式。"""

def e_gross_infty(lam: float, K_S: float, K_T: float) -> float:
    """§2.5 Gross 期望（T=infty）。"""

def e_net_infty(lam: float, K_S: float, K_T: float, c: float) -> float:
    """§2.5 Net 期望（T=infty）。"""

def t_star(K_S: float, K_T: float, sigma: float) -> float:
    """§2.7 短期/长期分界。"""

def mu_star(K_S: float, K_T: float, sigma: float, c: float,
            mu_range: tuple[float, float] = (-1.0, 1.0)) -> float:
    """§3.2 盈亏平衡漂移。brentq 求解 E[net](mu) = 0。"""

def mu_sensitivity(K_S: float, K_T: float, sigma: float, c: float,
                   mu_grid: list[float]) -> dict[float, float]:
    """§3.1 μ 敏感性表。"""

def solve_K_T_min(K_S: float, mu: float, sigma: float, c: float,
                  K_T_upper: float) -> float:
    """§3.3.4 凯利正 edge 下界。brentq 求解 E[net] = 0。"""

def solve_K_T_max(sigma: float, T: float, k_safety: float = 2.0) -> float:
    """§3.3.5 物理可达上界。"""

def solve_feasible_range(
    combo: ComboParams,
    market: MarketParams,
    risk: RiskParams,
) -> FeasibleRangeResult:
    """§3.3 完整反解流程。"""

def mu_implied(K_S: float, K_T: float, T: float, sigma: float, c: float,
               E_net_obs: float) -> float:
    """§4.1 μ_implied 反算。"""

def first_passage_designer(
    combo: ComboParams,
    market: MarketParams,
    risk: Optional[RiskParams] = None,
) -> FirstPassageResult:
    """主入口，聚合所有输出。"""
```

## 5.6 输出结构

```python
@dataclass
class FirstPassageResult:
    """§1.2 完整输出。"""
    # 首达（§2.3）
    P_win: float
    P_loss: float
    # 期望（§2.5）
    E_gross: float
    E_net: float
    E_tau: float
    # 分界（§2.7）
    T_star: float
    regime: Literal["short_term", "transition", "long_term"]
    # μ 敏感性（§3.1-3.2）
    mu_star: float
    mu_sensitivity: dict[float, float]
    # 恒等式检查
    is_zero_drift_identity: bool
    # 元信息
    inputs: dict
    warnings: list[str]


@dataclass
class FeasibleRangeResult:
    """§3.3 可行区间。"""
    # 输入回显
    r_acct: float
    P_target: float
    f_max: float
    T: float
    mu: float
    sigma: float
    c: float
    # 反解
    K_S: float
    K_T_target: float
    K_T_min: float
    K_T_max: float
    K_T_recommended: float
    # 时限
    E_tau: float
    T_dagger: Optional[float]  # v2 才实现
    # 仓位
    f_kelly: float
    f_final: float
    # 判决
    verdict: Literal["empty", "narrow", "wide", "no_kelly_edge"]
    reasoning: str
```

## 5.7 数值稳定性建议

- **$\lambda \to 0$ 附近**：直接判断 $|\lambda| < 10^{-6}$ 走 $\lambda = 0$ 分支，
  避免 $e^{\lambda K} - 1$ 除法精度损失
- **$\lambda \cdot K_T \to \pm \infty$**：预先检查上溢，若 $|\lambda \cdot \max(K_S, K_T)| > 50$
  返回极限值（$P_{\text{win}} \to 1$ 或 $0$）
- **`brentq` 区间**：$\mu^*$ 求解用 $[-2\sigma, +2\sigma]$；
  $K_T^{\min}$ 求解用 $(0.01 \cdot K_S, K_T^{\max})$
- **Fourier 级数收敛**：$e^{-n^2}$ 极快，前 10 项误差 < $10^{-15}$

## 5.8 单元测试建议

**基础恒等式**：
- $\lambda = 0$: $P_{\text{win}} = K_S/(K_S+K_T) \pm 10^{-10}$
- $\lambda = 0$: $E[\text{gross}] \approx 0 \pm 10^{-10}$
- $\lambda = 0$: $E[\text{net}] = -2c \pm 10^{-10}$
- $\lambda = 0$: $E[\tau] = K_S K_T / \sigma^2 \pm 10^{-10}$

**极限验证**：
- $K_T \to \infty$：$P_{\text{win}} \to 0$（$\lambda \le 0$）或 $\to 1$（$\lambda > 0$，指数快）
- $K_T \to 0$：$P_{\text{win}} \to 1$
- $\sigma \to 0$：$P_{\text{win}} \to \mathbf{1}_{\mu > 0}$（漂移决定方向）

**对齐本主题实测**：
- Combo A @ 5m（$K_S=1.5, K_T=3, T=6.7h$）：$P_{\text{win}} = 1/3 \pm 0.02$
- Combo E @ 5m（$K_S=1.5, K_T=2, T=6.7h$）：$P_{\text{win}} = 1.5/3.5 = 0.429 \pm 0.02$
- Combo G @ 5m（$K_S=1, K_T=1$）：$P_{\text{win}} = 0.5 \pm 0.02$

***

# Part VI · 应用场景与本主题连接

## 6.1 校准场景 A · Combo A（短期区经典）

**输入**：$K_S=1.5, K_T=3, T=6.7h, \sigma_{5m} \approx 0.5/\sqrt{h}, c=0.05$

**预期输出**：
- $P_{\text{win}}^{\infty} = 1/3$（对齐实测 33.6%）
- $E[\text{gross}] = 0$
- $E[\text{net}] = -0.10$（扁平 $c$）/ $-0.45$（realistic $c$）
- $T^* = 9/0.25 = 36h$，$T/T^* = 0.19 \ll 1$ → 短期区
- **结论**：数学必输，无需实测

## 6.2 校准场景 L @ 15m（过渡区候选）

**输入**：$K_S=1.5, K_T=3$ (armed), $T=20h, \sigma_{15m} \approx 0.9/\sqrt{h}, c=0.05$

**预期输出**：
- $T^* \approx 11h$，$T/T^* \approx 1.8$ → 过渡区
- $\mu_{\text{implied}}$ 从实测 +0.041 反算 → $\mu \approx 0.05\text{-}0.15\sigma$/day
- **结论**：L 通过跨周期护栏的原因是过渡区 + 实测隐含正漂移

## 6.3 校准场景 M/N @ 5m×SCALE=5（伪影验证）

**输入**：$K_S=7.5, K_T=3$ (armed), $T=33h, \sigma_{5m} \approx 0.5/\sqrt{h}$

**预期输出**：
- $\mu_{\text{implied}}$ 从实测 +0.30 反算 → $\mu$ 需极大
- **结论**：$\mu_{\text{implied}}$ 不合理 → M/N 不是 GBM 假设可解释 → 支持 KF-7 重采样伪影

## 6.4 可行区间判决表

| combo | $K_S$ | $K_T$ | μ 假设 | $K_T^{\min}$ | $K_T^{\max}$ | verdict |
|-------|-------|-------|--------|--------------|--------------|---------|
| A @ 5m | 1.5 | 3.0 | 0 | +∞ | 4.5 | **empty** → 淘汰 |
| A @ 5m | 1.5 | 3.0 | $0.3\sigma$ | 0.8 | 4.5 | wide → 强候选 |
| L @ 15m | 1.5 | 3.0 (armed) | 0 | +∞ | 8.0 | **empty** |
| L @ 15m | 1.5 | 3.0 (armed) | $0.08\sigma$ | 2.5 | 8.0 | narrow → 慎选 |

## 6.5 决策工作流

```
1. framework §5 反解 K_S（无 μ 依赖）
2. §3.1 μ 敏感性表：μ ∈ {-0.3σ, 0, +0.3σ}
3. §3.3 联立求解可行区间（每档 μ）
4. 分类：
   a. μ=0 空集 + μ>0 empty：数学必输 → 淘汰
   b. μ=0 空集 + μ>0 narrow：仅在假设正漂移时可行 → 需要 μ 依据
   c. μ=0 空集 + μ>0 wide：强候选，进实测
5. 实测后 §4.1 反算 μ_implied，检验假设合理性
```

***

# Part VII · 附录

## A. 边界与限制

### A.1 GBM 假设无法建模的属性

| 属性 | 影响 |
|------|------|
| **Fat tail** | 工具会低估极端事件概率 |
| **波动率聚集**（GARCH）| $\sigma$ 时变，工具用常数近似 |
| **跳空** | GBM 无跳，无法建模隔夜穿破 stop |
| **均值回归** | GBM 是 martingale，无回归 |
| **微观结构噪声** | 高频尺度失效 |

**含义**：工具输出是**理想化基准**，实测偏差 = 市场非 GBM 属性溢价。

### A.2 跨周期 σ 不一致

$\sigma_{5m} \ne \sigma_{15m}/\sqrt{3}$ 精确成立 —— 波动率时序非平稳。
工具允许用户为每个周期独立指定 $\sigma$。

### A.3 μ 假设的诚实性警告

**工具输出所有决策都依赖 μ 假设**：

- 若假设错误（假设 $\mu > 0$ 但实际 $\mu = 0$），会给出**假的 wide 判决**
- 工具**必须搭配 §4.1 μ_implied 反算**验证假设合理性
- **工具不是决策器，是假设显式化器** —— 让每个决策的"隐藏 μ 假设"曝光

## B. 与本项目 KF 的对齐

| KF | Spec 位置 | 数学表述 |
|----|-----------|---------|
| **KF-1** 结构塑形无独立 alpha | §2.5 + §3.3.4 | $\lambda = 0$ 下 $E[\text{gross}] \equiv 0$；凯利正 edge $K_T^{\min} = +\infty$ |
| **KF-2** Trailing 负 edge | §2.5 + §3.6 | Martingale + Optional Stopping：trailing 不改变 $E[X_\sigma]$ |
| **KF-6** barrier 距离档决定塑形 | §2.7 | $T^*$ 分界；短期区 $E[\text{net}] \equiv -2c$ |
| **KF-7** 5m×SCALE 伪影 | §4.1 | $\mu_{\text{implied}}$ 反算显示 M/N 需要不合理 μ |
| **KF-8** 数学 edge ≠ 工业可用 | §3.5 | 凯利 $f^*$ 通常 ≪ $f_{\max}$，需部分凯利 |

## C. 关联文档

- 上游主题：[experiment-plan.md](experiment-plan.md)
- 上游 workbench：[structural-shaping-alpha-gatekeeper.md](../../../workbench/structural-shaping-alpha-gatekeeper.md) §8.1-§8.11
- 长期共识：[strategy-research-framework.md](../../../roadmap/strategy-research-framework.md)
- 相关 skill：`quant-research-methodology`
