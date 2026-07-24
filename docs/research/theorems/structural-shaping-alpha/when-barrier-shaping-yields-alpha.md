# 何时 barrier 塑形能产出正净期望 · When Barrier Shaping Yields Alpha

> **文档定位**：本文回答一个数学问题——**在什么条件下，一个双 barrier 塑形容器 $(K_S, K_T, T)$ 能够满足 $\mathbb{E}[E_{\text{net}}] > 0$？** 从 Sharpe 借鉴定义"市场强度" $s := \nu/\sigma$ 出发，通过 Doob OST 两前提对偶结构给出**完备的充分条件分类**，闭式最优参数与盈亏下界。
>
> **稳定性**：入库日期 2026-07-24 · 从主题 `structural-shaping-alpha` 的活跃 spec 提炼；主题已于 2026-07-24 冻结归档至 [archive:2026-07-24-structural-shaping-alpha-freeze](../../archived-notes/2026/07/2026-07-24-structural-shaping-alpha-freeze/)；已通过一致性检查（附录 B）。
>
> **对外可用**：是（独立成篇、逻辑闭合、记号自洽）。
>
> **命名对应**：主题的 27 个 KF 与本文定义/命题的对应表见附录 A；文献对照见附录 C。

---

## 目录

1. [目标](#1-目标)
2. [基础对象与记号](#2-基础对象与记号)
3. [从 Sharpe 到市场强度](#3-从-sharpe-到市场强度)
4. [首达问题与解析解](#4-首达问题与解析解)
5. [Martingale 恒等式与 Doob 保守律](#5-martingale-恒等式与-doob-保守律)
6. [有限时间修正（Fourier 精确解）](#6-有限时间修正fourier-精确解)
7. [Doob OST 两前提与两条 alpha 通道](#7-doob-ost-两前提与两条-alpha-通道)
8. [通道 A · 方向 alpha 放大律](#8-通道-a--方向-alpha-放大律)
9. [通道 B · 强段择时非对称塑形](#9-通道-b--强段择时非对称塑形)
10. [分布输入闭式解（KF-27）](#10-分布输入闭式解kf-27)
11. [盈亏平衡下界与识别器精度](#11-盈亏平衡下界与识别器精度)
12. [关键结论汇总（Boxed）](#12-关键结论汇总boxed)
13. [附录 A · 数学规格与 KF 对应表](#附录-a--数学规格与-kf-对应表)
14. [附录 B · 静态一致性检查](#附录-b--静态一致性检查)
15. [附录 C · 文献对照与原创性定位](#附录-c--文献对照与原创性定位)

---

## 1. 目标

本规格回答一个数学问题：

> **给定几何布朗运动（GBM）价格过程与双 barrier 塑形容器 $(K_S, K_T, T)$，在什么条件下 barrier 触达停时 $\tau$ 下的期望净收益 $\mathbb{E}[E_{\text{net}}] > 0$？**

回答方式：借鉴 Sharpe 比率定义**对数空间市场强度** $s := \nu/\sigma$，把主题所有 alpha 通道统一表述为"某个 Doob OST 前提失效 + $s$ 满足特定条件"。

---

## 2. 基础对象与记号

### 2.1 概率空间

设 $(\Omega, \mathcal{F}, \{\mathcal{F}_t\}_{t \ge 0}, \mathbb{P})$ 为过滤概率空间，$W_t$ 为标准 Wiener 过程，$\{\mathcal{F}_t\}$ 为 $W$ 的自然过滤。

### 2.2 价格过程

标的价格 $S_t$ 满足几何布朗运动

$$
\frac{dS_t}{S_t} = \mu\, dt + \sigma\, dW_t, \qquad S_0 > 0
$$

其中 $\mu \in \mathbb{R}$ 为漂移率，$\sigma > 0$ 为波动率。

### 2.3 对数价格

定义

$$
X_t := \ln\!\left(\frac{S_t}{S_0}\right), \qquad X_0 = 0
$$

### 2.4 塑形容器

以 $S_0$ 为入场价、ATR 为单位归一化，定义

$$
K_S > 0 \text{（止损距离）}, \quad K_T > 0 \text{（止盈距离）}, \quad T \in (0, \infty] \text{（时间上限）}, \quad R := K_T / K_S \text{（盈亏比）}
$$

### 2.5 首达停时

$$
\tau := \inf\{\, t \ge 0 : X_t \notin (-K_S, K_T) \,\} \wedge T
$$

### 2.6 事件

$$
A_{\text{win}} := \{ \tau < T,\ X_\tau = K_T \}, \quad A_{\text{loss}} := \{ \tau < T,\ X_\tau = -K_S \}, \quad A_{\text{time}} := \{ \tau = T \}
$$

三者两两不交且并为 $\Omega$。

### 2.7 单笔收益

设单边成本 $c \in [0, \infty)$（ATR 计），则

$$
E_{\text{gross}} := \mathbb{E}[X_\tau], \qquad E_{\text{net}} := E_{\text{gross}} - 2c
$$

### 2.8 量纲约定表

| 符号 | 含义 | 量纲 |
|------|------|------|
| $S_t, K_S, K_T$ | 价格 / 距离 | ATR |
| $t, T, \tau$ | 时间 | bar 或小时 |
| $\mu$ | 漂移率 | $\text{time}^{-1}$ |
| $\sigma$ | 波动率 | $\text{time}^{-1/2}$ |
| $\nu$ | 对数漂移 | $\text{time}^{-1}$ |
| $s = \nu/\sigma$ | 市场强度 | $\text{time}^{-1/2}$ |
| $c$ | 单边成本 | ATR |
| $\lambda = 2\nu/\sigma^2$ | 无量纲漂移比 | 无量纲 |

---

## 3. 从 Sharpe 到市场强度

### 3.1 传统 Sharpe

**定义 3.1（Sharpe 比率）**：给定资产收益率 $\mu$ 与无风险利率 $r_f$，Sharpe 比率定义为

$$
\mathrm{SR} := \frac{\mu - r_f}{\sigma}
$$

在无风险利率归零场景下 $\mathrm{SR} = \mu/\sigma$。它是"per-unit-time 单位波动风险的超额漂移"。

### 3.2 Itô 修正

**引理 3.2（Itô 引理下的对数漂移）**：设 $S_t$ 满足 §2.2 的 GBM，则对数价格 $X_t = \ln(S_t/S_0)$ 满足

$$
dX_t = \nu\, dt + \sigma\, dW_t, \qquad \nu := \mu - \tfrac{1}{2}\sigma^2
$$

**证明.** 令 $f(s) = \ln s$，$f'(s) = 1/s$，$f''(s) = -1/s^2$。由 Itô 引理

$$
dX_t = f'(S_t)\, dS_t + \tfrac{1}{2} f''(S_t) (dS_t)^2 = \frac{dS_t}{S_t} - \tfrac{1}{2}\sigma^2\, dt = (\mu - \tfrac{1}{2}\sigma^2)\, dt + \sigma\, dW_t
$$
$\blacksquare$

### 3.3 市场强度

**定义 3.3（对数空间市场强度）**：类比 Sharpe，定义**市场强度**为

$$
\boxed{\;s := \frac{\nu}{\sigma} = \frac{\mu}{\sigma} - \frac{\sigma}{2}\;}
$$

**注 3.4（与 Sharpe 的关系）**：$s$ 是"对数空间的 per-unit-time Sharpe"，与传统 Sharpe 相差 Itô 凸性项 $\sigma/2$。当 $\sigma \ll 1$（高频、per-bar 尺度）时 $s \approx \mu/\sigma \approx \mathrm{SR}$。

**注 3.5（尺度依赖）**：$s$ 有 $\text{time}^{-1/2}$ 量纲。若时间刻度按 $t \mapsto t/\Delta t$ 归一化到"per bar"，则 $s$ 变为无量纲的 per-bar Sharpe，与 $\lambda$ 通过 $\lambda = 2s/\sigma_\text{bar}$ 相连（$\sigma_\text{bar}$ 为 per-bar 波动率）。

> **📚 文献批注（Sharpe 起源）**：$\mathrm{SR}$ 由 Sharpe (1966, 1994) 提出；其估计的分布理论由 Lo (2002) 系统给出（详见 §11.5）；精确非中心 t 分布由 Benhamou (2018) 给出，可作为主题渐进公式的精细化替代。本主题定义 $s = \nu/\sigma$ 严格来说是"对数空间 per-time-unit Sharpe"——文献中把它作为 GBM 参数 $\lambda$ 的等价形式使用（Akyildirim et al. 2021 的 statistical arbitrage 公式），但**未把它作为"市场强度"这一决策变量单独立义**。附录 C 详细比较。

### 3.4 决策阈值

由后文命题 5.1 与 §11.1 推导可得（暂列结果）：

| $\lvert s \rvert$ 范围 | 归因 | 依据 |
|------------|------|------|
| $\lvert s \rvert < 0.02$ | martingale · 完美对齐 | 命题 5.1 |
| $0.02 \le \lvert s \rvert < 0.10$ | 微弱漂移或非 GBM 溢价 | 见 §6 |
| $\lvert s \rvert \ge 0.10$ | 显著隐含漂移 | per-bar Sharpe · 400 bar 下 $t \ge 2$（见 §11.4） |

---

## 4. 首达问题与解析解

### 4.1 无量纲漂移比

**定义 4.1**：

$$
\lambda := \frac{2\nu}{\sigma^2} = \frac{2s}{\sigma}
$$

### 4.2 无限时间首达概率

**命题 4.2（$T = \infty$ 首达止盈概率）**：设 $T = \infty$，则

$$
P_{\text{win}}^{\infty}(\lambda; K_S, K_T) =
\begin{cases}
\dfrac{e^{\lambda K_T}\left(1 - e^{-\lambda K_S}\right)}{e^{\lambda K_T} - e^{-\lambda K_S}} & \lambda \ne 0 \\[8pt]
\dfrac{K_S}{K_S + K_T} = \dfrac{1}{1 + R} & \lambda = 0
\end{cases}
$$

**证明.** 记 $\varphi(x) := e^{-\lambda x}$。对 $\lambda \ne 0$，$\varphi(X_t) = e^{-\lambda X_t}$ 应用 Itô 引理

$$
d\varphi(X_t) = -\lambda \varphi(X_t)\, dX_t + \tfrac{1}{2}\lambda^2 \sigma^2 \varphi(X_t)\, dt = \varphi(X_t)\left[-\lambda \nu + \tfrac{1}{2}\lambda^2 \sigma^2\right] dt + \text{martingale part}
$$

代入 $\lambda = 2\nu/\sigma^2$，漂移项化为 $-\lambda \nu + \tfrac{1}{2}\lambda^2 \sigma^2 = 0$，故 $\varphi(X_t)$ 是鞅。Doob OST 给出

$$
\varphi(0) = 1 = P_{\text{win}} \cdot e^{-\lambda K_T} + (1 - P_{\text{win}}) \cdot e^{\lambda K_S}
$$

解出 $P_{\text{win}}$ 即得公式。$\lambda = 0$ 情形对 $X_t$ 自身应用 OST：$0 = P_{\text{win}} K_T - (1 - P_{\text{win}}) K_S \Rightarrow P_{\text{win}} = K_S/(K_S + K_T)$。$\blacksquare$

### 4.3 平均首达时间

**命题 4.3**：$\lambda = 0$ 时 $\mathbb{E}[\tau] = K_S K_T / \sigma^2$。

**证明.** 对 $X_t^2 - \sigma^2 t$ 应用 OST：$0 = \mathbb{E}[X_\tau^2] - \sigma^2 \mathbb{E}[\tau] = P_{\text{win}} K_T^2 + (1 - P_{\text{win}}) K_S^2 - \sigma^2 \mathbb{E}[\tau]$，代入 $P_{\text{win}} = K_S/(K_S+K_T)$ 化简即得。$\blacksquare$

### 4.4 短期 / 过渡 / 长期分界

**定义 4.4**：$T^\ast := \max(K_S, K_T)^2 / \sigma^2$，为"无漂移下平均触达 barrier 的时间量级"。

| 区间 | 条件 | $\mathbb{P}(\tau = T)$（$\lambda = 0$） |
|------|------|---------------------------------------|
| 短期区 | $T/T^\ast > 3$ | $< 10^{-4}$ |
| 过渡区 | $1 < T/T^\ast \le 3$ | $\in [10^{-4}, 0.3]$ |
| 长期区 | $T/T^\ast \le 1$ | $\ge 0.3$ |

---

## 5. Martingale 恒等式与 Doob 保守律

### 5.1 核心恒等式

**命题 5.1（Martingale 恒等式）**：在 $\lambda = 0$（即 $s = 0$，$\nu = 0$）下，对任意 $(K_S, K_T)$ 与任意有限停时 $\tau'$（不必是首达停时），

$$
\boxed{\;\mathbb{E}[X_{\tau'}]\big|_{\nu = 0} = 0 \quad \Longleftrightarrow \quad E_{\text{gross}} \equiv 0\;}
$$

**证明.** $\nu = 0$ 时 $X_t = \sigma W_t$ 是鞅。$\tau' \le T < \infty$ 一致有界，Doob OST 直接给出 $\mathbb{E}[X_{\tau'}] = X_0 = 0$。对首达停时 $\tau$，$\mathbb{E}[X_\tau] = P_{\text{win}} K_T - (1 - P_{\text{win}}) K_S = 0$，与命题 4.2 的 $P_{\text{win}} = K_S/(K_S+K_T)$ 自洽。$\blacksquare$

### 5.2 Doob 保守律

**推论 5.2（Doob 保守律 · KF-1）**：在 $\nu = 0$ 下，无论 $(K_S, K_T, T, \text{trailing}, \text{breakeven}, \dots)$ 如何取值，只要出场规则是 $\mathcal{F}_t$-adapted 停时，皆有

$$
E_{\text{net}} = E_{\text{gross}} - 2c = -2c < 0
$$

**证明.** OST 保证 $E_{\text{gross}} = 0$；扣双边成本得 $E_{\text{net}} = -2c$。$\blacksquare$

**含义**：**塑形本身不创造 alpha**——这是塑形三定律的第一定律。

> **📚 文献批注（保守律的先驱）**：本推论与 **Rogers & Imkeller (2001)** 的核心结论一致——他们证明"**已知漂移下最优止损不存在**"（"for reasonable model parameters, it is never optimal to place trading stops when the drift of the P&L is known"，转引自 Di Graziano 2014）。**Di Graziano (2014)** 在 Markov-modulated diffusion 框架下把这一结论推广到随机漂移，并首次用效用函数（CARA）方法反解闭式 $\varphi(a,b)$。**Glynn & Iglehart (1995)** 对 trailing stop 版本证明了相似结论。本主题的推论 5.2 是 GBM + 有限成本下的直接实例；不同点：本主题不引入效用函数，只用 Doob OST + 成本簿记，因此结论对**任意风险偏好**（不必 CARA）都成立。

### 5.3 期望收益的一般式

**引理 5.3**：对一般 $\lambda \in \mathbb{R}$，

$$
E_{\text{gross}}(\lambda; K_S, K_T) = P_{\text{win}}^{\infty}(\lambda) \cdot K_T - \left(1 - P_{\text{win}}^{\infty}(\lambda)\right) \cdot K_S
$$

---

## 6. 有限时间修正（Fourier 精确解）

### 6.1 命题

**命题 6.1（有限时间 Fourier 级数解）**：设 $\nu = 0$，$L := K_S + K_T$，入场点从下界起算的坐标 $x_0 = K_S$。则

$$
P_{\text{win}}^{\text{finiteT}}(T; K_S, K_T) = \frac{2}{\pi} \sum_{n=1}^{\infty} \frac{(-1)^{n+1}}{n} \sin\!\left(\frac{n\pi K_S}{L}\right) \left(1 - e^{-n^2 \pi^2 \sigma^2 T / (2 L^2)}\right)
$$

$$
\mathbb{P}(\tau > T) = \frac{4}{\pi} \sum_{n \text{ 奇}} \frac{\sin(n\pi K_S / L)}{n}\, e^{-n^2 \pi^2 \sigma^2 T / (2 L^2)}
$$

**证明思路.** 求解热方程 $\partial_t u = \tfrac{1}{2}\sigma^2 \partial_{xx} u$ 于 $(0, L)$ 上，Dirichlet 边界，初始 $u(0, x) = \mathbb{1}[x = x_0]$；分离变量得傅里叶正弦级数展开。$P_{\text{win}}^{\text{finiteT}}$ 是右边界通量对时间的积分。$\blacksquare$

> **📚 文献批注（双 barrier 首达）**：一维扩散双 barrier 首达停时的矩、密度理论由 **Wang & Yin (2008)** 系统总结。**Xu & Zhu (2013)** 用 Girsanov 变换给出时间依赖 barrier 的密度（可推广主题的 barrier 至线性时变）。**Alachal (1990–1996)** 的 Integrated Brownian Motion 系列给出更一般泛函（如停时+终末位置联合分布）的闭式，可作为主题"barrier 触达+累积浮盈联合分布"未来拓展的理论工具。主题命题 6.1 是这些结果在"零漂移 + 双吸收 barrier + 常数 $\sigma$"最简特例的直接应用；不同点：**主题首次把 Fourier 解作为 barrier 型策略的"标准 null"方法论沉淀**（KF-17），文献未做此定位。

### 6.2 极限一致性

**推论 6.2**：$\lim_{T \to \infty} P_{\text{win}}^{\text{finiteT}}(T) = P_{\text{win}}^{\infty}(\lambda = 0) = K_S / L$。

**证明.** $T \to \infty$ 时级数中 $e^{-n^2 \pi^2 \sigma^2 T / (2 L^2)} \to 0$，得

$$
P_{\text{win}}^{\infty} = \frac{2}{\pi} \sum_{n=1}^{\infty} \frac{(-1)^{n+1}}{n} \sin\!\left(\frac{n \pi K_S}{L}\right)
$$

该级数正是 $x \mapsto K_S / L$ 于 $x = K_S$ 处的傅里叶展开值。$\blacksquare$

### 6.3 方法论沉淀

**注 6.3（KF-17 · 标准 null 升级）**：所有 barrier 结构的 null 假设应从 $P_{\text{win}}^{\infty}$ 升级为 $P_{\text{win}}^{\text{finiteT}}$；否则长期区 $T/T^\ast < 1$ 归因可能符号搞反（如 KF-11 修正）。

---

## 7. Doob OST 两前提与两条 alpha 通道

### 7.1 OST 两前提

**定理 7.1（Doob 可选停时定理）**：若

1. **(P1) 鞅性**：$X_t$ 在测度 $\mathbb{Q}$ 下是 $\mathcal{F}_t$-鞅；
2. **(P2) 可测停时**：$\tau$ 是 $\mathcal{F}_t$-adapted 停时，$\{\tau \le t\} \in \mathcal{F}_t$；
3. 有界性：$\tau$ 一致有界或 $\{X_{t \wedge \tau}\}$ 一致可积。

则 $\mathbb{E}_\mathbb{Q}[X_\tau] = \mathbb{E}_\mathbb{Q}[X_0]$。

### 7.2 两条通道的数学根源

**命题 7.2（alpha 通道的对偶结构）**：Doob 保守律（推论 5.2）唯一可通过打破 P1 或 P2 而失效。相应地存在两条独立通道：

| 通道 | 打破 | 数学机制 | 主题命名 |
|------|------|----------|----------|
| A | P1 | 条件测度 $\mathbb{P}(\cdot \mid \text{方向筛选})$ 下 $X_t$ 非鞅 | 方向 alpha 放大律 (KF-19) |
| B | P2 | 入场信息含 $\lvert s \rvert$ → $\tau$ 非 $\mathcal{F}_t$-adapted | 强段择时 (KF-26) |

**证明思路.** 若 P1、P2 均成立，OST 给出 $E_{\text{gross}} = 0$。要令 $E_{\text{gross}} > 0$，必须至少破坏其一。$\blacksquare$

---

## 8. 通道 A · 方向 alpha 放大律

### 8.1 条件测度

**定义 8.1**：设 $D \in \{+1, -1\}$ 为方向指示（多空），若 $D$ 依赖过去路径 $\mathcal{F}_{t_0}$（$t_0$ 为入场时刻），则条件测度

$$
\mathbb{P}^{\text{aligned}}(\cdot) := \mathbb{P}(\cdot \mid D = \mathrm{sign}(\nu_{\text{cond}}))
$$

下的条件漂移 $\nu_{\text{cond}} \ne 0$。

### 8.2 分解

**命题 8.2（方向筛选下的期望分解）**：

$$
\mathbb{E}^{\text{aligned}}[X_\tau] = \underbrace{\mathbb{E}^{\text{DirRandom}}[X_\tau]}_{= 0 \text{（Doob）}} + \underbrace{\Delta_{\text{direction}}}_{> 0}
$$

**实证（KF-19）**：$K_S=4, R=2, 5\text{m}$ 上 $\Delta_{\text{direction}} = +0.25$ ATR/笔。

> **📚 文献批注（方向 alpha 放大的先驱）**：条件测度改变鞅性从而打破保守律，是 **Rogers & Imkeller (2001)** 首先形式化的思路（Bayesian 未知漂移）。**Di Graziano (2014)** 用 Markov-modulated diffusion（$\mu(y_t)$ 依据隐藏链切换）把此思路做成可校准的工程方法。**Ekström & Lindberg (2011)** 处理"漂移在未观测随机时点从 $\mu_1 > r$ 跳到 $\mu_2 < r$"的最优清仓问题，用 quickest-detection filtering 给出恒定 barrier 最优；主题的"aligned/opposed 分组"可类比为该条件流形上的两个分片。**Lopez de Prado (2018) 的 Meta-Labeling**（Primary 定 side + Secondary 定 size）从 ML 工程角度**发现**了同一现象，但未从 Doob OST 的 P1 前提失效角度给出**数学根源**。**本主题的原创点**：在 §7.2 明确把方向 alpha 兑现归结为"P1 鞅性失效"这一唯一数学机制。

---

## 9. 通道 B · 强段择时非对称塑形

### 9.1 强段公理

**公理 9.1（强段可识别性）**：存在识别器 $f: \mathcal{F}_{t_0} \to \mathbb{R}_+$，使入场时刻 $t_0$ 后单笔窗口内 $|s| = |\nu|/\sigma$ 近似为常数 $x > 0$，且 $\mathrm{sign}(\nu)$ 未知（记为 $\varepsilon \in \{\pm 1\}$，先验各 $1/2$）。

### 9.2 混合期望

**命题 9.2（KF-26 混合期望公式）**：在公理 9.1 + DirRandom（$D$ 独立于 $\varepsilon$）下，设 $\lambda := 2x/\sigma_\text{bar}$，则

$$
\boxed{\;
E_{\text{gross}}^{\text{mix}}(x, K_S, K_T) = \frac{K_T + K_S}{2}\left[P_{\text{win}}^{\infty}(+\lambda) + P_{\text{win}}^{\infty}(-\lambda)\right] - K_S
\;}
$$

**证明.** 以多头视角建模：每 bar 有效对数漂移为 $D \cdot \nu$，其中 $D$ 是策略方向、$\nu$ 是真实漂移。乘积 $D \cdot \mathrm{sign}(\nu) \in \{\pm 1\}$ 由独立性各占 $1/2$，故有效 $\lambda_{\text{eff}} \in \{+\lambda, -\lambda\}$ 各 $1/2$。全概率公式：

$$
P_{\text{win}}^{\text{mix}} = \tfrac{1}{2}\left[P_{\text{win}}(+\lambda) + P_{\text{win}}(-\lambda)\right]
$$

代入 $E_{\text{gross}} = P_{\text{win}} K_T - (1 - P_{\text{win}}) K_S$ 得目标式。$\blacksquare$

### 9.3 P2 违反的严格陈述

**命题 9.3**：在公理 9.1 下，$\tau$ 依赖 $|s|$ 通过入场决策 → $\tau$ 不是 $\mathcal{F}_t$-adapted → OST 的 P2 失效 → $E_{\text{gross}}^{\text{mix}}$ 可以非零。

### 9.4 正 alpha 的充分条件

**推论 9.4**：若 $R > 1$（非对称塑形）且 $|\lambda| K_T \gg 1$（强段饱和），则 $P_{\text{win}}(+\lambda) \to 1$，$P_{\text{win}}(-\lambda) \to 0$，

$$
E_{\text{gross}}^{\text{mix}} \to \frac{K_T - K_S}{2} > 0
$$

**证明.** 直接代入命题 9.2。$\blacksquare$

> **📚 文献批注（通道 B 的文献空白）**：**这是本主题最强的原创点**。综合检索的 barrier 型策略文献均**假设方向已知**：
> - **Akyildirim et al. (2021)** · Statistical Arbitrage — 单边 "long-until-barrier"；
> - **Leung & Li (2015)** · OU pairs trading — 已知均值回归方向；
> - **Leung & Zhang (2019)** · Trailing stop — 已知多头；
> - **Ekström & Lindberg (2011)** · Momentum — 已知多头（漂移正）。
>
> **主题的通道 B 结构**（"只知 $|\nu|/\sigma$ 强段，方向随机 + 非对称 barrier"）**在检索到的文献中未找到对应结果**。数学根源上，它对应 Doob OST 的 P2 前提（可测停时）失效——这一分类在文献中亦未被显式提出。**这是主题相对现有 barrier 策略理论的第一条独立贡献**。

---

## 10. 分布输入闭式解（KF-27）

### 10.1 分布输入

**定义 10.1**：设品种 $|s| = |\nu|/\sigma$ 服从密度 $f_D$、支撑于 $\mathbb{R}_+$ 的分布 $D$，两阶矩 $(\mu_D, \sigma_D)$。择时门槛 $\tau_\text{q} \in [0, 1]$ 表示"仅在 $|s| \ge x^\ast_{\tau_\text{q}}$ 段入场"（$x^\ast_{\tau_\text{q}}$ 为 $D$ 的 $\tau_\text{q}$ 上分位）。

### 10.2 目标函数

**定义 10.2**：条件期望与年化 Sharpe

$$
\begin{aligned}
E_{\text{gross}}(K_S, K_T, \tau_\text{q}) &= \frac{\int_{x^\ast_{\tau_\text{q}}}^{\infty} E_{\text{gross}}^{\text{mix}}(x; K_S, K_T)\, f_D(x)\, dx}{\mathbb{P}(|s| \ge x^\ast_{\tau_\text{q}})}, \\[4pt]
N_{\text{year}}(\tau_\text{q}) &= \mathbb{P}(|s| \ge x^\ast_{\tau_\text{q}}) \cdot \frac{T_{\text{year}}}{\mathbb{E}[\tau_{\text{FPT}}]}, \\[4pt]
\mathrm{Sharpe}_{\text{年}} &= \sqrt{N_{\text{year}}} \cdot \frac{E_{\text{gross}} - 2c}{\sigma_{\text{trade}}}
\end{aligned}
$$

### 10.3 一阶最优条件

**命题 10.3（FOC）**：内点极值 $(K_S^\ast, K_T^\ast, \tau_\text{q}^\ast)$ 满足

$$
\begin{aligned}
\partial_{\tau_\text{q}} \mathrm{Sharpe}_{\text{年}} &= 0 \quad\Longleftrightarrow\quad E_{\text{gross}}^{\text{mix}}(x^\ast_{\tau_\text{q}^\ast}) = \mathbb{E}[E_{\text{gross}}^{\text{mix}}(x) \mid x \ge x^\ast_{\tau_\text{q}^\ast}], \\
\partial_{K_T} \mathrm{Sharpe}_{\text{年}} &= 0 \quad\Longleftrightarrow\quad K_T^\ast \text{ 使 } P_{\text{win}}(+\lambda) \text{ 于 } D \text{ 支撑 } \text{恰达饱和缘}, \\
\partial_{K_S} \mathrm{Sharpe}_{\text{年}} &\le 0 \quad\Longrightarrow\quad K_S^\ast = K_S^{\min} \text{（KF-23 跳空下限）}
\end{aligned}
$$

### 10.4 实证锚点

**引理 10.4（玉米 1h）**：$D = \mathrm{FoldedNormal}(0.198,\, 0.108)$，$c = 0.077$，$K_S^{\min} = 1.0$，$\sigma_\text{bar} = 1$，$T_{\text{year}} = 1625\,\text{h}$：

$$
\boxed{\;K_S^\ast = 3.0,\quad K_T^\ast = 9.0,\quad R^\ast = 3,\quad \tau_\text{q}^\ast = 0.647,\quad \mathrm{Sharpe}_{\text{年}} = +1.66\;}
$$

> **📚 文献批注（分布输入的对照）**：**Akyildirim et al. (2021)** 用点估计 $|\nu|/\sigma$ 优化 statistical arbitrage 的 Sharpe，采用 bootstrapping 验证经验命中概率；主题的 KF-27 **对整条分布 $D(\mu_D, \sigma_D)$ 做积分**，相当于把 Akyildirim 的点估计升级为分布积分。**Bailey & Lopez de Prado (2014) · Deflated Sharpe Ratio (DSR)** 应作为下游"识别信号"研究项目的补丁——多重比较（K 次策略挖掘）会让 $\mathrm{Sharpe}_{\text{年}} = 1.66$ 需按 $\sqrt{2\ln K}$ 折减。主题当前未做 DSR 修正，是引理 10.4 已知的乐观偏差来源之一（附录 C 单列）。

---

## 11. 盈亏平衡下界与识别器精度

### 11.1 小 $\lambda$ 展开

**引理 11.1**：设 $\lambda K_T$ 与 $\lambda K_S$ 均小，则

$$
P_{\text{win}}^{\infty}(\pm \lambda) = \frac{K_S}{K_S + K_T}\left[1 \pm \frac{\lambda K_T}{2} + \frac{\lambda^2 K_T(K_T - K_S)}{12} + \mathcal{O}(\lambda^3)\right]
$$

**证明.** 对 $P_{\text{win}}^{\infty}(\lambda) = e^{\lambda K_T}(1 - e^{-\lambda K_S})/(e^{\lambda K_T} - e^{-\lambda K_S})$ 做 $\lambda$ 的 Taylor 展开，逐阶匹配即得。$\blacksquare$

### 11.2 混合期望展开

**命题 11.2（$E_{\text{gross}}^{\text{mix}}$ 二阶展开）**：由引理 11.1 与命题 9.2，奇次项对消，

$$
\boxed{\;E_{\text{gross}}^{\text{mix}}(x) \approx \frac{x^2 \cdot K_S^3 \cdot R(R-1)}{3} + \mathcal{O}(x^4)\;}
$$

**证明.** 代入 $\lambda = 2x/\sigma_\text{bar}$（取 $\sigma_\text{bar} = 1$）、$K_T = R K_S$：

$$
P^+ + P^- = \frac{2 K_S}{K_T + K_S}\left[1 + \frac{\lambda^2 K_T(K_T - K_S)}{12}\right] + \mathcal{O}(\lambda^4)
$$

代入命题 9.2 化简得 $E_{\text{gross}}^{\text{mix}} \approx \tfrac{\lambda^2}{12} K_S K_T (K_T - K_S) = \tfrac{x^2}{3} K_S^3 R(R-1)$。$\blacksquare$

### 11.3 盈亏平衡下界

**定理 11.3（品种无关下界）**：使 $E_{\text{net}} = 0$ 的最小强度为

$$
\boxed{\;x_{\min}(c, K_S, R) = \sqrt{\frac{6c}{K_S^3 \cdot R(R-1)}}\;}
$$

**推论 11.4（Doob 保守律的严格映射）**：$R \to 1 \Rightarrow x_{\min} \to \infty$——对称塑形下不存在有限强度可覆盖成本，与推论 5.2 一致。

> **📚 文献批注（品种无关下界的对照）**：**Di Graziano (2014)** 在 CARA 效用下给出闭式 $\varphi(a, b)$，但形式依赖风险厌恶参数 $\gamma$，不是"品种无关下界"。**Leung & Li (2015)** 给出"higher stop-loss level implies lower take-profit level"的定性结论，与本主题的 $x_{\min} \propto K_S^{-3/2}$ 单调关系方向一致，但未给出闭式。**本主题的原创点**：$x_{\min}$ 只依赖 $(c, K_S, R)$、不依赖风险偏好或分布尾部，是**跨品种可直接比较**的最简下界公式；小 $\lambda$ 二阶展开是把 KF-26 混合公式（命题 9.2）与 §7.2 通道 B 数学根源结合的直接推论。

### 11.4 识别器 se 目标

**定义 11.5（识别器）**：识别器 $f$ 输出 $\hat{x} = f(\mathcal{F}_{t_0})$ 为 $|s|$ 的估计，标准误 $\mathrm{se}(f) := \sqrt{\mathbb{E}[(\hat{x} - x)^2]}$。

**命题 11.6（95% 单侧置信度约束）**：欲使 $\mathbb{P}(x \ge x_{\min} \mid \hat{x}) \ge 0.95$，需

$$
\hat{x} \ge x_{\min} + z_{0.95} \cdot \mathrm{se}(f), \qquad z_{0.95} = 1.645
$$

**推论 11.7（KF-27 最优点识别器 se 目标）**：设 KF-27 最优工作点 $x^\ast = x^\ast_{\tau_\text{q}^\ast}$，则

$$
\boxed{\;\mathrm{se}^{\text{目标}} := \frac{x^\ast - x_{\min}}{z_{0.95}}\;}
$$

玉米 1h：$\mathrm{se}^{\text{目标}} = (0.13 - 0.055)/1.645 \approx 0.046 \approx 0.05$。

### 11.5 se 的样本量诠释

**引理 11.8（Lo 2002 · Sharpe 标准误）**：对独立同分布样本 $\{r_i\}_{i=1}^{T}$，$\widehat{\mathrm{SR}} := \bar{r}/\hat{s}$ 满足

$$
\mathrm{se}(\widehat{\mathrm{SR}}) \approx \sqrt{\frac{1 + \tfrac{1}{2}\mathrm{SR}^2}{T}} \approx \frac{1}{\sqrt{T}}\text{（}|\mathrm{SR}| \ll 1\text{）}
$$

**推论 11.9**：$\mathrm{se}^{\text{目标}} \le 0.05 \Rightarrow T \ge 400$ bar。这是**通道 B 识别器的最小观测窗口下限**。

> **📚 文献批注（Sharpe 标准误）**：引理 11.8 是 **Lo (2002) · The Statistics of Sharpe Ratios** 的直接引用（IID 正态假设下的渐进标准误）。Lo 论文示例："样本 60 观测下真实 SR=1.5 时 SE=0.188；SR=3 时 SE=0.303"——与主题的"400 bar → SE≈0.05"数量级完全一致。**Benhamou (2018)** 给出精确非中心 t 分布，$\mathrm{SE}$ 精度从 $O(1/N)$ 提升到 $O(1/N^{3/2})$，是主题下游研究可采用的更紧估计。**Pav (Notes on Sharpe ratio, 2024)** 系统整理 Sharpe 作为 t-statistic 的性质，可作为置信区间构造的参考。**Lo (2002) 也处理了自相关修正**（AR(1)/AR(p)），当下游识别器输出序列有自相关时（如波动率突破触发的相邻信号）主题 se KPI 需按此修正。

---

## 12. 关键结论汇总（Boxed）

**【KF-1 · Doob 保守律】**

$$
\boxed{\;\nu = 0 \;\Rightarrow\; E_{\text{gross}} \equiv 0 \;\Rightarrow\; E_{\text{net}} \equiv -2c\;}
$$

**【市场强度定义】**

$$
\boxed{\;s := \frac{\nu}{\sigma} = \frac{\mu - \sigma^2/2}{\sigma}\;}
$$

**【首达恒等式】**

$$
\boxed{\;P_{\text{win}}^{\infty}\big|_{s=0} = \frac{1}{1 + R}\;}
$$

**【KF-26 混合公式】**

$$
\boxed{\;E_{\text{gross}}^{\text{mix}} = \frac{K_T + K_S}{2}\left[P^{+}(\lambda) + P^{-}(\lambda)\right] - K_S\;}
$$

**【KF-27 最优参数】**

$$
\boxed{\;(K_S^\ast, K_T^\ast, \tau_\text{q}^\ast) = \arg\max_{(K_S, K_T, \tau_\text{q})} \mathrm{Sharpe}_{\text{年}}\;}
$$

**【小 $\lambda$ 展开】**

$$
\boxed{\;E_{\text{gross}}^{\text{mix}} \approx \frac{x^2 \, K_S^3 \, R(R-1)}{3}\;}
$$

**【盈亏下界】**

$$
\boxed{\;x_{\min} = \sqrt{\frac{6c}{K_S^3 \, R(R-1)}}\;}
$$

**【识别器 se 目标】**

$$
\boxed{\;\mathrm{se}^{\text{目标}} = \frac{x^\ast - x_{\min}}{z_{0.95}}\;}
$$

**【识别窗口下限】**

$$
\boxed{\;\mathrm{se}(f) \le 0.05 \;\Rightarrow\; T \ge 400\text{ bar}\;}
$$

---

## 附录 A · 数学规格与 KF 对应表

| KF | shaping-theory.md 位置 | 本规格位置 | 数学对象 |
|----|-----------------------|-----------|---------|
| KF-1 | §1.4, §2.1 | 推论 5.2 | Doob 保守律 |
| KF-6 | §1.5, §2.14.4 | 定义 4.4 | $T^\ast$ 分界 |
| KF-9 | §1.2 | 引理 3.2 + 定义 3.3 | Itô 修正与 $s$ 定义 |
| KF-10 | §3.1 | 命题 5.1 | FPT $\lambda=0$ 标准 null |
| KF-11 | §2.7, §2.14.2 | 命题 6.1 + 注 6.3 | Fourier null 修正 |
| KF-14 | §2.10 | 命题 6.1 + $T^\ast$ | 跨周期 time_exit 不变性 |
| KF-15 | §2.11–§2.15 | 命题 6.1 残差 | 极小 $K_S$ 微 alpha 区 |
| KF-17 | §2.13 | 命题 6.1 | Fourier 精确解为标准 null |
| KF-18 | §2.16 | 命题 6.1 双通道 | $P_{\text{win}}$ + $\mathbb{P}(\tau>T)$ 探测器 |
| KF-19 | §2.17 | 命题 8.2 | 方向筛选破 P1 |
| KF-20 | §2.21 | 推论 5.2 + 命题 7.2 + 命题 8.2 | 塑形三定律 |
| KF-22 | §2.19 | 引理 11.8 | Sharpe SE / Bootstrap CI |
| KF-23 | §2.20.1 | 命题 10.3 之 $K_S^{\min}$ | 跳空修正 |
| KF-26 | §2.22 | 命题 9.2 | 混合期望公式 |
| KF-27 | §2.23 | 定义 10.1–10.2, 命题 10.3, 引理 10.4 | 分布输入闭式解 |

---

## 附录 B · 静态一致性检查

按 [quant-math-spec](../../../../.trae/skills/quant-math-spec/SKILL.md) 检查清单本轮结果：

| 类别 | 结论 |
|------|------|
| 符号一致性 | $s, \nu, \sigma, \lambda, K_S, K_T, R, T, T^\ast, \tau, x, x_{\min}, x^\ast$ 全文一致，定义前均已引入 |
| 量纲 | §2.8 表已列出所有量纲；$\lambda$ 无量纲、$s$ 为 $\text{time}^{-1/2}$ 显式声明 |
| 命题/证明配对 | 命题 4.2 / 4.3 / 5.1 / 6.1 / 6.2 / 7.2 / 8.2 / 9.2 / 9.4 / 10.3 / 11.2 / 11.3 / 11.6 / 11.9 均附证明或证明思路 |
| Boxed 结论 | §12 收敛 9 条 boxed 结论，与正文命题一一对应 |
| KF 覆盖 | 附录 A 覆盖 KF-1/6/9/10/11/14/15/17/18/19/20/22/23/26/27；KF-2/7/8/12/13/16/21/24/25 属实证/方法论层，不进入数学规格 |
| 孤立符号 | $\varepsilon$（命题 9.2）与 $D$（§8.1, 9.2）区分为"真实漂移方向"与"策略方向"，无同名冲突 |

**本轮无需修复**。

---

## 附录 C · 文献对照与原创性定位

本附录汇总主题在主流学术文献中的定位、每一节的先驱贡献者、主题相对文献的**四条原创点**。检索日期 2026-07-24。

### C.1 参考文献清单

| 类别 | 文献 | 与主题的关系 |
|------|------|------------|
| **Barrier ML 工程** | Lopez de Prado (2018) · *Advances in Financial Machine Learning*, Ch. 3 | Triple-Barrier Method 是主题塑形容器 $(K_S, K_T, T)$ 的工程原型；Meta-Labeling 对应通道 A |
| **Barrier ML 工程** | Bailey & Lopez de Prado (2014) · Deflated Sharpe Ratio | 多重比较修正，主题下游研究应引入 |
| **Statistical Arbitrage** | [Akyildirim, Goncu, Hekimoglu, Nguyen, Sensoy (2021)](https://www.researchgate.net/publication/348917220_Statistical_arbitrage_Factor_investing_approach) · Statistical arbitrage: Factor investing approach | 与主题最贴近；GBM + hitting probability + Sharpe 目标；但只用单边 barrier 且点估计 $\|\nu\|/\sigma$ |
| **最优止损理论** | Rogers & Imkeller (2001) · [Kalikow et al.] | 首次证明"已知漂移下最优止损不存在"（主题推论 5.2 的先驱） |
| **最优止损理论** | [Di Graziano (2014)](http://spekulant.com.pl/article/Trading%20strategies/OptimalTradingStops_Graziano_1401.pdf) · Optimal Trading Stops and Algorithmic Trading | Markov-modulated diffusion + CARA 效用；把 Rogers-Imkeller 推广到随机漂移 |
| **最优止损理论** | Glynn & Iglehart (1995) | GBM 正漂移下 trailing 从不最优（对应主题 KF-25 结论） |
| **均值回归 / 双停时** | [Leung & Li (2015)](https://ar5iv.labs.arxiv.org/html/1411.5062) · Optimal Mean Reversion Trading with Transaction Costs and Stop-Loss | OU 过程双停时；主题 KF-27 的 $K_S \uparrow \Rightarrow K_T^\ast$ 单调走向的类比结论 |
| **Trailing stop** | [Leung & Zhang (2019)](https://arxiv.org/pdf/1701.03960) · Optimal Trading with a Trailing Stop | 线性扩散 + trailing 的最优双停时；主题 §3.5.5 v3 拓展可直接引用 |
| **Momentum quickest detection** | [Ekström & Lindberg (2011)](https://www2.math.uu.se/~ereks021/momentum.pdf) · Optimal Closing of a Momentum Trade | 漂移随机切换的最优清仓；主题 KF-19 跨周期泄漏的类比 |
| **Sharpe 统计学** | [Lo (2002)](https://traders.studentorg.berkeley.edu/papers/The-Statistics-of-Sharpe-Ratios.pdf) · The Statistics of Sharpe Ratios | 引理 11.8 的原始来源（渐进标准误 + 自相关修正） |
| **Sharpe 统计学** | [Benhamou (2018)](https://arxiv.org/pdf/1808.04233v2) · Connecting Sharpe ratio and Student t-statistic | 精确非中心 t 分布；引理 11.8 的精细化替代 |
| **Sharpe 统计学** | Pav (2024) · A Short Sharpe Course | Sharpe 作为 t-statistic 的系统整理 |
| **双 barrier 首达** | [Wang & Yin (2008)](https://www.researchgate.net/publication/23636264_Moments_of_the_first_passage_time_of_one-dimensional_diffusion_with_two-sided_barriers) · Moments of first passage time with two-sided barriers | 一维扩散双 barrier 停时矩的一般理论；命题 4.3 的推广 |
| **双 barrier 首达** | [Xu & Zhu (2013)](https://pdfs.semanticscholar.org/b511/76ae9f35e123aeadd91bc2c9dceb36f584f7.pdf) · First exit time with double linear time-dependent barriers | Girsanov 变换给出时变 barrier 密度；主题 barrier 拓展 |
| **双 barrier 首达** | Alachal (1990–1996) · Integrated Brownian Motion | 停时 + 终末位置联合分布；主题"barrier 触达 + 累积浮盈"未来拓展 |

### C.2 主题各节的先驱贡献者对照

| 主题命题/定义 | 先驱者 | 主题的推进 |
|--------------|--------|-----------|
| §3.3 市场强度 $s = \nu/\sigma$ | Sharpe (1966)；Itô (1951) | 首次把 $s$ 单独立义为"决策变量"而非"过程参数" |
| §4.2 首达闭式 $P_\text{win}^\infty$ | 经典结果（Karlin-Taylor 教材） | 与 Akyildirim (2021) 相同；主题给出 Doob 鞅化的简证 |
| §5.2 Doob 保守律（推论 5.2） | Rogers & Imkeller (2001), Di Graziano (2014) | 剥离效用函数依赖，对任意风险偏好成立 |
| §6.1 Fourier 精确解 | Wang & Yin (2008), 经典热方程谱分解 | 首次把 Fourier 解沉淀为 barrier 策略的"标准 null"（KF-17 方法论） |
| §7.2 两通道对偶（P1 / P2） | 无直接对应 | **原创**：把 alpha 通道分类归结为 Doob OST 前提失效 |
| §8.2 通道 A 分解 | Rogers-Imkeller Bayesian 未知漂移；Ekström-Lindberg quickest detection；Lopez de Prado Meta-Labeling | 显式给出 P1 失效的严格数学表述 |
| §9.2 通道 B 混合公式 | 无直接对应 | **原创**：文献均假设方向已知；本主题的"只知强度不知方向"是新方向 |
| §10 KF-27 分布输入 | Akyildirim (2021) 点估计 | **原创**：升级为分布积分 $\int f_D(x) g(x) dx$ |
| §11.3 品种无关下界 $x_\min$ | Di Graziano (2014) CARA 闭式 | **原创**：不依赖效用函数的最简下界 $\sqrt{6c/(K_S^3 R(R-1))}$ |
| §11.5 Sharpe 标准误 | Lo (2002), Benhamou (2018) | 直接引用 Lo 结果作为 $\text{se}^\text{目标}$ KPI 的数学根据 |

### C.3 主题相对文献的四条原创贡献

$$
\boxed{
\begin{aligned}
&\textbf{① Doob OST 两前提作为对偶轴（§7.2）} \\
&\textbf{② 通道 B 混合期望公式（命题 9.2，KF-26）} \\
&\textbf{③ 分布输入闭式解（§10，KF-27）} \\
&\textbf{④ 品种无关下界 } x_\min = \sqrt{6c/(K_S^3 R(R-1))} \text{（定理 11.3）}
\end{aligned}
}
$$

- **①** 文献分别研究过 P1 失效（Rogers-Imkeller, Di Graziano）与 P2 失效（未见），但**没有把它们放在同一对偶框架**下作为"塑形 alpha 只有两条来源"的完备分类。
- **②** 检索到的所有 barrier 策略文献（Akyildirim, Leung 系列, Ekström-Lindberg）**均假设方向已知**；"只知 $\|\nu\|/\sigma$ 强段" 的混合公式在文献中未见。
- **③** Akyildirim (2021) 是最接近的对照，但用点估计；主题对分布积分是**从 KF-26 到 KF-27 的独立跨越**。
- **④** Di Graziano 的 CARA 闭式依赖 $\gamma$；本主题的 $x_\min$ 只依赖 $(c, K_S, R)$，是**跨品种可直接比较**的最简形式。

### C.4 主题的已知乐观偏差与文献补丁路线

| 乐观偏差来源 | 建议引用的文献补丁 |
|--------------|-------------------|
| $\mathrm{Sharpe}_{\text{年}} = 1.66$ 未做多重比较修正 | Bailey & Lopez de Prado (2014) DSR，按 $\sqrt{2\ln K}$ 折减 |
| 引理 11.8 渐进标准误精度 $O(1/N)$ | Benhamou (2018) 精确非中心 t 分布，$O(1/N^{3/2})$ |
| Sharpe 自相关修正（GARCH / 相邻信号） | Lo (2002) §5 AR(p) 修正公式 |
| 20h 强度窗口 → barrier 触达期信号衰减 | 未有直接对应文献；建议下游主题原创研究 |
| FoldedNormal 拟合尾部偏差 | 经验分布 KDE 替代 + Bootstrap CI（Akyildirim 2021 的方法） |
| $\sigma_\text{bar}$ 时变（GARCH）未纳入 KF-27 | 主题 KF-24 已给出实证证据；理论侧可引 Heston / SABR 随机波动率
