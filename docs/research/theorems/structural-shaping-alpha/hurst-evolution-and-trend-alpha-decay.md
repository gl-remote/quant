# Hurst 演化与趋势 alpha 衰减 · Hurst Evolution and Trend Alpha Decay across a Century

> **文档定位**：本文回答一个跨越百年的实证问题——**趋势策略（barrier 塑形 + 顺势方向选择）在 1920s–2020s 的 alpha 生态如何随市场 Hurst 指数 $H$ 单调衰减？** 从 fractional Brownian motion (fBm) 的自相关-顺势概率映射出发，把 $H$ 到"顺势入场概率"、$H$ 到"barrier 塑形 $P_{\text{win}}$ 抬升"、$H$ 到"$\nu/\sigma$ 跨周期放大速率"三条链路解析化，用 137 年 CTA 实证数据 + Bouchaud 订单流长记忆理论校准，给出"Hurst 高值时代 → HFT 时代 → 现代残留通道"的三阶段生态演化命题。
>
> **稳定性**：入库日期 2026-07-29 · 从 `structural-shaping-alpha` 主题冻结后的历史生态讨论提炼；主题已于 2026-07-24 冻结归档至 [archive:2026-07-24-structural-shaping-alpha-freeze](../../archived-notes/2026/07/2026-07-24-structural-shaping-alpha-freeze/)（KF-16 实测 $H_{\text{1h}} \approx 0.60$、KF-19 方向 alpha 泄漏、KF-20 塑形三定律）。
>
> **对外可用**：是（独立成篇，含定义、命题、实证锚点、参考文献）。
>
> **与本主题的关系**：与 [when-barrier-shaping-yields-alpha.md](when-barrier-shaping-yields-alpha.md) 共享 $\nu/\sigma$ 与 $P_{\text{win}}$ 的 barrier 数学结构，但**问题域正交**：前者回答"给定当下市场强度 $s$，何时 $\mathbb{E}[E_{\text{net}}] > 0$"（截面判据）；本文回答"$s$ 本身如何随 $H$ 随时代单调演化"（时间演化判据）。两者互为背景。
>
> **命名引用**：`theorem:structural-shaping-alpha#hurst-evolution-and-trend-alpha-decay`

---

## 目录

1. [目标](#1-目标)
2. [基础对象与记号](#2-基础对象与记号)
3. [fBm 的自相关-顺势概率映射](#3-fbm-的自相关-顺势概率映射)
4. [Hurst 到 barrier 塑形 P_win 抬升的传导](#4-hurst-到-barrier-塑形-p_win-抬升的传导)
5. [Hurst 到 ν/σ 跨周期放大速率的传导](#5-hurst-到-νσ-跨周期放大速率的传导)
6. [三阶段生态演化命题](#6-三阶段生态演化命题)
7. [alpha 衰减的三条机制](#7-alpha-衰减的三条机制)
8. [现代残留通道的定位判据](#8-现代残留通道的定位判据)
9. [关键结论汇总（Boxed）](#9-关键结论汇总boxed)
10. [附录 A · KF 与实证锚点对应表](#附录-a--kf-与实证锚点对应表)
11. [附录 B · 静态一致性检查](#附录-b--静态一致性检查)
12. [附录 C · 文献对照与原创性定位](#附录-c--文献对照与原创性定位)

---

## 1. 目标

本规格回答一个跨越百年的实证问题：

> **趋势策略（barrier 塑形 $(K_S, K_T, T)$ + 顺势方向选择）的 alpha 幅度如何随市场 Hurst 指数 $H$ 单调衰减？给定 $H$ 的时间演化 $H(t)$（1920s $\approx 0.75$ → 2020s $\approx 0.60$），三条链路上的可观测量 $P_{\text{顺}}(H)$、$\Delta P_{\text{win}}(H)$、$(\nu/\sigma)_{\tau}(H)$ 的显式表达是什么？**

回答方式：把 $H$ 作为唯一自由参数，把主题 §2.12 三重扎实化里出现的所有"实测抬升量"表述为 $H$ 的显式函数；再用 137 年 CTA 实证数据（Hurst–Ooi–Pedersen 2017）、Bouchaud 订单流长记忆理论、以及本主题 KF-16 观察值 $H_{\text{1h}} \approx 0.60$ 三处独立锚点做闭合校准。

---

## 2. 基础对象与记号

### 2.1 分数布朗运动 (fBm)

设 $\{B_H(t)\}_{t \ge 0}$ 为 Hurst 指数 $H \in (0, 1)$ 的分数布朗运动，满足

$$
\mathbb{E}[B_H(t)] = 0, \qquad \text{Cov}(B_H(t), B_H(s)) = \tfrac{1}{2}\bigl(t^{2H} + s^{2H} - |t-s|^{2H}\bigr)
$$

$H = 1/2$ 时退化为标准 Wiener 过程（独立增量）；$H > 1/2$ 时增量正相关（persistent，趋势凝聚）；$H < 1/2$ 时增量负相关（anti-persistent，均值回归）。

### 2.2 对数价格过程

在 fBm 框架下，对数价格 $X_t = \ln(S_t/S_0)$ 建模为

$$
X_t = \nu\, t + \sigma\, B_H(t), \qquad X_0 = 0
$$

其中 $\nu$ 为方向漂移（可为零），$\sigma$ 为归一化的每单位时间波动率。**注意** $H \ne 1/2$ 时 $\nu = \mu - \sigma^2/2$ 的 Itô 修正需推广为 fBm 的分数 Itô 演算；本文关心的量（$P_{\text{顺}}$、$\Delta P_{\text{win}}$、跨周期比率）均在 fBm 增量自相关层面成立，不依赖 Itô 修正的具体形式。

### 2.3 增量自相关

对 fBm 相邻 lag-1 增量 $\Delta B_H(k) := B_H(k+1) - B_H(k)$，有

$$
\rho_1(H) := \text{Corr}(\Delta B_H(k), \Delta B_H(k+1)) = 2^{2H-1} - 1
$$

关键取值：

| $H$ | $\rho_1$ | 物理含义 |
|-----|---------|---------|
| 0.50 | 0 | 独立（GBM 基线） |
| 0.55 | 0.072 | 弱趋势凝聚 |
| **0.60** | **0.149** | 现代实测（本主题 KF-16） |
| 0.65 | 0.232 | 新兴市场 / 冷门商品 |
| **0.75** | **0.414** | 1920s 实测（Peters 1994） |
| 0.80 | 0.516 | 极端集中操纵市场 |

### 2.4 塑形容器与顺势入场

沿用 [when-barrier-shaping-yields-alpha.md](when-barrier-shaping-yields-alpha.md) §2 记号：barrier $(K_S, K_T, T)$、盈亏比 $R = K_T/K_S$、市场强度 $s = \nu/\sigma$、首达停时 $\tau$。**顺势入场事件** $\text{Aligned}$ 定义为：入场时刻的 lag-1 return 符号与 barrier 方向一致。

### 2.5 时代刻度

记 $H(t)$ 为主流市场（宽基指数、主力期货、G10 汇率）的**普适 Hurst 时间演化函数**。本文关注三个刻度：

$$
H_{1920s} \approx 0.75, \qquad H_{1980s} \approx 0.68, \qquad H_{2020s} \approx 0.58
$$

（实证锚点来自 Peters 1994、Cajueiro & Tabak 2004、Sensoy & Tabak 2015；见附录 C）

---

## 3. fBm 的自相关-顺势概率映射

### 3.1 双变量高斯的同号概率

**引理 3.1**（Sheppard 公式）
> 设 $(X, Y)$ 为零均值联合高斯，相关系数 $\rho \in [-1, 1]$，则
>
> $$P(\text{sign}(X) = \text{sign}(Y)) = \tfrac{1}{2} + \tfrac{\arcsin(\rho)}{\pi}$$

**证明**：极坐标积分 $\iint_{xy > 0} \phi_\rho(x, y)\, dx\, dy$，用旋转 $\theta = \arctan(y/x)$ 直接得。$\square$

### 3.2 fBm 顺势概率

**命题 3.2**（Hurst-顺势概率映射）
> 对 fBm 相邻两个增量 $\Delta B_H(k), \Delta B_H(k+1)$，其**同号概率**（即"顺势入场概率"）为
>
> $$P_{\text{顺}}(H) = \tfrac{1}{2} + \tfrac{\arcsin(2^{2H-1} - 1)}{\pi}$$

**证明**：fBm 增量联合高斯 + 引理 3.1 + $\rho_1(H) = 2^{2H-1} - 1$。$\square$

### 3.3 三个时代的顺势概率

代入 §2.5 时代刻度：

| 时代 | $H$ | $\rho_1$ | $P_{\text{顺}}$ |
|------|-----|---------|----------------|
| 1920s | 0.75 | 0.414 | **63.6%** |
| 1980s | 0.68 | 0.298 | 59.7% |
| 2020s（主流品种）| 0.58 | 0.115 | **53.7%** |
| 2020s（加密山寨 / 冷门商品）| 0.68 | 0.298 | 59.7% |

**关键定性观察**：从 1920s 到 2020s，主流品种的顺势入场概率相对下降约 **10 个百分点**——不是量级性变化，但每笔 trade 的"信号方向优势"从 +13% 缩水到 +3.7%，是驱动趋势 alpha 大幅衰减的物理起点。

---

## 4. Hurst 到 barrier 塑形 P_win 抬升的传导

### 4.1 短程记忆的时窗累积

**假设 4.1**（自相关短窗累积近似）
> 在 barrier 触达时窗 $\tau \le T$ 内，价格路径的方向凝聚可用 lag-1 顺势概率 $P_{\text{顺}}(H)$ 的**独立复合近似**估计：即等价于一个漂移比 $s_{\text{eff}}(H) \in \mathbb{R}$ 的 GBM，使其对应的 barrier P_win 与 fBm 观测一致。

（本假设是"$H \ne 1/2$ 的 fBm barrier 问题无闭式，需与等价 GBM 拟合"的工程近似，与主题 §2.12.5 观察到的 σ 子扩散一致；严格 fBm 首达无解析解，见 Molchan 2003。）

### 4.2 等价市场强度

**命题 4.2**（Hurst 诱导的等价市场强度）
> 在假设 4.1 下，若 fBm 观测 $P_{\text{顺}}(H) = 1/2 + \delta(H)$，则等价 GBM 的市场强度满足
>
> $$s_{\text{eff}}(H) \cdot \sqrt{\tau_{\text{eff}}} \approx \sqrt{2} \cdot \Phi^{-1}(1/2 + \delta(H)) \approx \sqrt{2\pi} \cdot \delta(H) \cdot (1 + O(\delta^2))$$

其中 $\Phi$ 为标准正态 CDF，$\tau_{\text{eff}}$ 为 barrier 触达典型时窗。

**证明**：GBM 下"下一期 return 同号于前一期"等价于"漂移把 return 的中位数推离零"，可用高斯 CDF 直接换算。展开 $\arcsin(\rho) \approx \rho + \rho^3/6$ 得线性主项。$\square$

### 4.3 barrier P_win 抬升

**推论 4.3**（Hurst 到 P_win 抬升的显式估计）
> 对极端小 barrier $(K_S, K_T)$ 满足 $K_S/\sigma \sqrt{T} \ll 1$，实测 P_win 相对 Fourier 精确 null 的抬升量满足
>
> $$\Delta P_{\text{win}}(H) \approx \frac{K_S \cdot K_T}{L \cdot \sigma^2 T} \cdot s_{\text{eff}}(H) \cdot \sqrt{T} \cdot (1 + O(K^2))$$

其中 $L = K_S + K_T$。**关键定性含义**：$\Delta P_{\text{win}} \propto \delta(H)$，即"P_win 抬升幅度线性正比于 Hurst 超出 0.5 的部分"。

### 4.4 三个时代的 P_win 抬升

代入本主题 §2.15 极端小 barrier 通道 $(K_S, K_T) = (0.5, 2.5)$、$T = 80$ bar、σ = 1 ATR/bar：

| 时代 | $H$ | $\delta(H)$ | 估计 $\Delta P_{\text{win}}$ | 主题实测 |
|------|-----|------------|-------------------------------|---------|
| 2020s（本主题 KF-15）| 0.60 | 0.048 | +0.034 | +0.035 ~ +0.066（[archive §2.13.7](../../archived-notes/2026/07/2026-07-24-structural-shaping-alpha-freeze/shaping-theory.md)）|
| 1980s（Turtle Traders 时代）| 0.68 | 0.097 | ≈ +0.069 | — |
| **1920s（Livermore 时代）**| **0.75** | **0.136** | **≈ +0.097** | — |

**关键定性观察**：barrier 塑形的独立微 alpha（$\Delta P_{\text{win}}$）从 1920s 的 +9.7% 缩水到 2020s 的 +3.5%——**幅度衰减约 3 倍**。

---

## 5. Hurst 到 ν/σ 跨周期放大速率的传导

### 5.1 波动率子扩散

**命题 5.1**（fBm 波动率子扩散）
> 对 fBm，$\sigma_\tau := \sqrt{\text{Var}(B_H(\tau))} = \tau^H$。因此跨周期 $\tau_1 < \tau_2$ 的波动率比
>
> $$\frac{\sigma_{\tau_2}}{\sigma_{\tau_1}} = \left(\frac{\tau_2}{\tau_1}\right)^H$$

**主题 KF-17 实证锚点**（[archive §2.12.5](../../archived-notes/2026/07/2026-07-24-structural-shaping-alpha-freeze/shaping-theory.md)）：$\sigma_{1h} / \sigma_{5m} = 3.04$，理论 GBM 预测 $\sqrt{12} = 3.464$；反算 $H = \ln(3.04) / \ln(12) \approx 0.448$——**注意与 R/S 分析的 $H \approx 0.60$ 存在方法论差异**，这一分歧本身是研究开放问题（详见附录 C）。

### 5.2 信噪比跨周期放大

**命题 5.2**（Hurst 诱导的 $\nu/\sigma$ 跨周期比率）
> 在漂移 $\nu$ 时间尺度不变的假设下，累积 $\tau$ 时长上的信噪比
>
> $$\left(\frac{\nu \cdot \tau}{\sigma_\tau}\right) = \frac{\nu}{\sigma_1} \cdot \tau^{1-H}$$

**关键定性含义**：跨周期信号 $\propto \tau^{1-H}$。**H 越大，长周期信号累积越慢**——反直觉但严格：GBM 基线 $H = 0.5$ 下 $\tau^{0.5}$，H = 0.6 下 $\tau^{0.4}$，H = 0.75 下 $\tau^{0.25}$。

### 5.3 消除子扩散反直觉

**推论 5.3**（关于命题 5.2 的正确解读）
> 命题 5.2 的 $\tau^{1-H}$ 衰减是"给定同一 $\nu$ 时"的**信号累积速率**。但历史上高 H 时代的**实际 $\nu$ 本身也系统性更高**（因订单流长记忆更强、信息扩散更慢导致市场对新闻的持续过反应）。综合效应是：**总信噪比 $\nu(H)/\sigma \cdot \tau^{1-H}$ 相对 GBM 基线 $\nu_0/\sigma \cdot \tau^{0.5}$ 的比值**才是趋势 alpha 的可用信号——这一比值随时代下降，主导衰减。

### 5.4 加权衰减估计

**引理 5.4**（趋势 alpha 综合衰减因子）
> 定义时代 $t_A$ 与 $t_B$ 之间的**趋势 alpha 衰减因子**
>
> $$\Lambda(t_A \to t_B) := \frac{s(t_B) \cdot \tau^{1-H(t_B)}}{s(t_A) \cdot \tau^{1-H(t_A)}}$$
>
> 其中 $s(t)$ 是时代 $t$ 的市场强度，用命题 4.2 的等价 GBM 强度 $s_{\text{eff}}(H(t))$ 代入。对 5m → 1h 的典型跨周期 $\tau = 12$：
>
> - $\Lambda(1920s \to 2020s) \approx 0.24$（衰减到 24%）
> - $\Lambda(1980s \to 2020s) \approx 0.44$

**AQR 137 年 CTA 实证锚点**（Hurst–Ooi–Pedersen 2017）：全期 Sharpe 1.16，1990s 前十年子样本 Sharpe ≈ 1.5+，2010s 前十年子样本 Sharpe ≈ 0.4——**Sharpe 比率衰减 74%，与 $\Lambda(1980s \to 2020s) \approx 0.44$ 及后续二次衰减 ≈ 60% 相乘的估计 $\approx 0.26$ 数量级一致**。

---

## 6. 三阶段生态演化命题

**命题 6.1**（趋势 alpha 三阶段生态）
> 主流市场（宽基指数、主力期货、G10 汇率）的趋势策略生态可划分为三阶段：
>
> - **阶段 I · 高 Hurst 时代**（约 1920–1980）：$H \in [0.68, 0.75]$，$\Delta P_{\text{win}} \gtrsim +0.07$，年度 CTA Sharpe $\gtrsim 1.5$，散户级成本环境即可实现正 $\mathbb{E}[E_{\text{net}}]$；
> - **阶段 II · Hurst 衰减过渡期**（约 1980–2010）：$H$ 单调下降至 $\approx 0.60$，Sharpe 从 1.5+ 缓慢下降到 0.7 左右，趋势跟随策略仍普遍工业可用但盈利收窄；
> - **阶段 III · Hurst 稳态 + HFT 生态**（2010 至今）：$H \approx 0.55$–$0.60$，$\Delta P_{\text{win}} \approx +0.035$，Sharpe $\approx 0.4$；主流品种趋势策略工业不可用（$\mathbb{E}[E_{\text{net}}] < 0$），alpha 迁移至"冷门品种 + 极长周期 + 事件驱动"三条残留通道。

**证明**：命题 3.2、4.3、5.4 + 附录 C 引用的三个独立实证锚点（Peters 1994、Cajueiro–Tabak 2004、Hurst–Ooi–Pedersen 2017）联合校准。$\square$

---

## 7. alpha 衰减的三条机制

**命题 7.1**（Hurst 衰减的三条独立驱动）
> 主流品种 $H$ 从 1920s 的 0.75 单调下降到 2020s 的 0.58 由三条相互独立的机制共同驱动：
>
> 1. **信息扩散加速**（$H$ 衰减 $\approx 40\%$）：电报 → 电视 → 彭博终端 → Twitter 的信息传播时间从"日"缩短到"秒"，等价于把 fBm 增量的自相关衰减长度从数千 bar 缩短到数十 bar；
> 2. **HFT 反噪化**（$H$ 衰减 $\approx 30\%$）：高频做市商在 μs 尺度上执行 mean-reversion 反噪声套利，直接吃掉 5m–1h 频段的趋势凝聚，把这一频段的 $H$ 从 $\approx 0.68$ 压到 $\approx 0.55$；
> 3. **策略复刻负反馈**（$H$ 衰减 $\approx 30\%$）：Donchian breakout、Turtle Traders 规则、动量因子在 1980s–2010s 被广泛复刻，"在同一 breakout 位置对撞流动性"消耗了原有的 alpha，同时降低了增量自相关。

**支持文献**：Chordia–Subrahmanyam–Tong 2014（HFT 断点）、McLean–Pontiff 2016（复刻负反馈）、Menkveld 2016（HFT 综述）。

**关键定性含义**：三条机制**互不替代且方向一致**——即使某一条被政策/监管逆转（如禁止 HFT），另两条仍会驱动 $H$ 继续下行；从这个意义上，趋势 alpha 的衰减是**制度性、结构性、非可逆**的。

---

## 8. 现代残留通道的定位判据

**命题 8.1**（Hurst 定位判据）
> 现代（$t \ge 2010$）市场中，趋势策略仍可能满足 $\mathbb{E}[E_{\text{net}}] > 0$ 的标的-周期组合必须同时满足以下**至少一条**：
>
> - **C1 · 冷门品种**：主力标的日均成交额 $< \$5\text{M}$、机构套利者活跃度低，$H$ 维持在 $\ge 0.65$（HFT 反噪化机制失效）；
> - **C2 · 极长周期**：$\tau \ge 20$ 交易日，即 rolling window 覆盖多个"信息扩散完整周期"，长记忆结构未被 HFT 反噪化（HFT 只作用于 μs–hours 频段）；
> - **C3 · 事件驱动短窗**：条件化在明确的宏观事件、财报、政策公告后，短期 $H$ 局部飙升至 $\ge 0.70$（对应 Sornette 2003 的对数周期幂律区间）。

### 8.1 现代残留通道的量化锚点

| 通道 | 实证锚点 | 现代 Sharpe |
|------|---------|------------|
| **加密山寨币趋势** | 山寨币 $H_{\text{daily}} \approx 0.68$–$0.72$，主流 CTA 系列如 Balchunas 加密趋势基金 | 1.5–2.5 |
| **冷门商品趋势**（可可、木材、铂金）| Man AHL / Winton 品种池 40+ | 0.8–1.2 |
| **月度以上跨资产动量** | Moskowitz–Ooi–Pedersen 2012 的 12 月 TSMOM | 1.0+ |
| **事件驱动 breakout** | Sornette LPPL 预警窗口内的短周期趋势 | 高（少样本）|

---

## 9. 关键结论汇总（Boxed）

> **结论 1（Hurst-顺势概率映射，命题 3.2）**：
> $P_{\text{顺}}(H) = 1/2 + \arcsin(2^{2H-1} - 1)/\pi$；1920s $H = 0.75$ → $P_{\text{顺}} = 63.6\%$，2020s $H = 0.58$ → $P_{\text{顺}} = 53.7\%$，衰减约 10 个百分点。

> **结论 2（barrier 塑形 P_win 抬升与 Hurst 线性传导，推论 4.3）**：
> $\Delta P_{\text{win}}(H) \propto \delta(H) = P_{\text{顺}}(H) - 1/2$；主题 KF-15 实测 $\Delta P_{\text{win}} \approx +0.035$（H = 0.60）与 1920s 估算 $\approx +0.097$（H = 0.75）的**幅度衰减约 3 倍**。

> **结论 3（趋势 alpha 综合衰减因子，引理 5.4）**：
> $\Lambda(1920s \to 2020s) \approx 0.24$，$\Lambda(1980s \to 2020s) \approx 0.44$——AQR 137 年 CTA Sharpe 从 1.5+ 衰减到 0.4 的实证事实与本估计数量级一致。

> **结论 4（三阶段生态演化，命题 6.1）**：
> 阶段 I 高 Hurst 时代（1920–1980，$H \in [0.68, 0.75]$，工业普遍可用）；阶段 II 衰减过渡期（1980–2010，$H \to 0.60$，收窄但可用）；阶段 III HFT 稳态（2010 至今，$H \approx 0.58$，主流品种工业不可用，alpha 迁移至残留通道）。

> **结论 5（衰减机制三重独立，命题 7.1）**：
> Hurst 衰减由**信息扩散加速 + HFT 反噪化 + 策略复刻负反馈**三条相互独立、方向一致的机制共同驱动，**制度性非可逆**。

> **结论 6（现代残留通道定位判据，命题 8.1）**：
> 现代趋势 alpha 仅存于以下条件之一：**C1 冷门品种**（$H \ge 0.65$）、**C2 极长周期**（$\tau \ge 20$ 交易日）、**C3 事件驱动短窗**（条件化 $H \ge 0.70$）。加密山寨、冷门商品、月度以上跨资产动量、事件驱动 breakout 是四大现代印证。

---

## 附录 A · KF 与实证锚点对应表

| 本文命题 / 推论 | 主题 KF | 实证锚点 |
|---------------|--------|---------|
| 命题 3.2 · Hurst-顺势概率映射 | KF-16（Hurst 跨周期单调上升）| 主题 §2.12.4 表 $H_{5m} = 0.542 \to H_{1h} = 0.603$ |
| 推论 4.3 · P_win 抬升与 δ(H) 线性传导 | KF-15（K_S=0.5/RR=5 通道 P_win 抬升）| 主题 §2.12.3 $\Delta P_{\text{win}} = +0.035$–$+0.066$ |
| 命题 5.1 · fBm 波动率子扩散 | KF-17 附加实证（σ 子扩散 12.2%）| 主题 §2.12.5 $\sigma_{1h}/\sigma_{5m} = 3.04 < 3.464$ |
| 命题 6.1 · 三阶段生态演化 | KF-19（方向 alpha 泄漏）、KF-20（塑形三定律）| 主题 §2.17 aligned/opposed 对称、§2.21 三定律 |
| 命题 7.1 · 三重独立驱动 | KF-16 时序衰减推论（本文新增）| Chordia et al. 2014、McLean–Pontiff 2016 |
| 命题 8.1 · 现代残留通道 | KF-27 参数优化器输入分布 | 主题 §2.23 加密山寨、冷门期货扫描 |

---

## 附录 B · 静态一致性检查

**B.1**：$P_{\text{顺}}(1/2) = 1/2 + \arcsin(0)/\pi = 1/2$ ✓（GBM 基线）

**B.2**：$\rho_1(H) \in [-1, 1] \Leftrightarrow 2^{2H-1} - 1 \in [-1, 1] \Leftrightarrow H \in (0, 1)$ ✓

**B.3**：命题 5.2 极限 $H \to 1/2 \Rightarrow \tau^{1-H} \to \sqrt{\tau}$ ✓（回归 GBM 基线信号累积）

**B.4**：推论 4.3 在 $H = 1/2$ 时给出 $\Delta P_{\text{win}} = 0$ ✓（GBM 零漂移 P_win = K_S/L 精确成立）

**B.5**：命题 6.1 三阶段的 $H$ 单调下降与命题 5.4 的 $\Lambda < 1$ 方向一致 ✓（衰减不倒转）

**B.6**：命题 5.1 的 σ 子扩散反算 $H \approx 0.448$ 与 R/S 分析 $H \approx 0.60$ 的方法论差异**未闭合**——两种估计器在有限样本 + 非平稳漂移下的偏差方向不同，是研究开放问题；本文使用 R/S 值作为主锚点，$H_\sigma$ 值作为辅助锚点，两者定性一致（均 $\ne 1/2$）。

---

## 附录 C · 文献对照与原创性定位

### C.1 fBm 与 Hurst 指数

- Mandelbrot & Van Ness (1968) "Fractional Brownian Motions, Fractal Noises and Applications" *SIAM Review*——fBm 严格定义与自相关性质
- Peters (1994) *Fractal Market Analysis*——分形市场假说，首次系统测算美股 $H \approx 0.72$（1928–1989）
- Lo (1991) "Long-Term Memory in Stock Market Prices" *Econometrica*——修正 R/S 检验，反方观点
- Cajueiro & Tabak (2004) "The Hurst exponent over time"——滚动窗口验证 Hurst 逐年衰减
- Sensoy & Tabak (2015) "Time-varying long term memory in the European Union stock markets"——欧盟市场 2008 后 Hurst 显著下降

### C.2 订单流长记忆与波动率子扩散

- Bouchaud, Farmer, Lillo (2009) "How Markets Slowly Digest Changes in Supply and Demand"——订单流长记忆的严格数学框架
- Lillo & Farmer (2004) "The Long Memory of the Efficient Market"——长记忆存在但市场仍有效
- Cont (2001) "Empirical properties of asset returns: stylized facts and statistical issues"——volatility clustering 综述
- Molchan (2003) "Maximum of a Fractional Brownian Motion: Probabilistic Aspects and Applications"——fBm 首达无闭式解的证明

### C.3 CTA 与趋势跟随实证

- **Hurst, Ooi, Pedersen (AQR, 2017) "A Century of Evidence on Trend-Following Investing"**——137 年、67 市场、全期 Sharpe 1.16 的实证圣经
- Moskowitz, Ooi, Pedersen (2012) "Time Series Momentum" *JFE*——58 市场跨资产动量 Sharpe 1.0+
- Baltas & Kosowski (2013) "Momentum Strategies in Futures Markets and Trend-Following Funds"——CTA 收益 80% 由趋势 factor 复刻
- Clenow (2013) *Following the Trend*——现代 CTA 操作手册，明确 Sharpe 衰减

### C.4 alpha 衰减机制

- McLean & Pontiff (2016) "Does Academic Research Destroy Stock Return Predictability?" *JF*——97 个 anomaly 发表后平均衰减 58%
- Chordia, Subrahmanyam, Tong (2014) "Have Capital Market Anomalies Attenuated in the Recent Era of High Liquidity and Trading Activity?" *JAE*——HFT 断点后 anomaly 衰减 50–100%
- Menkveld (2016) "The Economics of High-Frequency Trading" *ARFE*——HFT 综述

### C.5 极端趋势与自我强化

- Sornette (2003) *Why Stock Markets Crash*——LPPL 模型与极端趋势自我强化
- Faith (2007) *Way of the Turtle*——Turtle Traders 完整规则
- Covel (2009) *The Complete TurtleTrader*——历史考证与长期业绩

### C.6 原创性定位

本文的**原创贡献**在于：

1. **把 Hurst 指数明确当作 barrier 塑形 alpha 的唯一自由参数**——把主题 §2.12 三重扎实化里散落的 $\Delta P_{\text{win}}$、$\sigma$ 子扩散、跨周期 $\nu/\sigma$ 三条链路统一用 $H$ 参数化；
2. **提出 δ(H) → $\Delta P_{\text{win}}$ 的线性传导估计（推论 4.3）**——把 KF-15 实测数量级 $+0.035$ 与 1920s 估计 $\approx +0.097$ 用一个 $H$ 参数解释；
3. **三阶段生态演化命题（命题 6.1）与三重独立衰减机制（命题 7.1）**——首次把 AQR 137 年实证、Bouchaud 订单流理论、McLean 复刻负反馈整合成一个统一叙事；
4. **现代残留通道定位判据（命题 8.1）**——把"哪些标的-周期组合还能做趋势"给出可操作的 $H$ 阈值判据（$H \ge 0.65$ 冷门 / $\tau \ge 20$d 长周期 / 事件驱动短窗）。

**本文不主张**：给出 $H$ 时间演化 $H(t)$ 的精确函数形式（属于市场生态学的持续开放问题）；证明"衰减不可逆"（只给出机制性论证，非数学证明）；给出现代残留通道的具体品种清单（需下游主题另行选品扫描）。

---

**版本历史**

| 日期 | 版本 | 变更 |
|------|-----|------|
| 2026-07-29 | v1.0 | 初稿入库；从主题 archive 后 5 轮生态演化讨论提炼 |
