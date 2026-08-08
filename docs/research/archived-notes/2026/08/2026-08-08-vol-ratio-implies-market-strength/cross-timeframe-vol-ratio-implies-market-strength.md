# 跨周期波动率比值蕴含市场强度存在性 · 草稿

> **文档定位**：纯数学推导。证明：**跨周期波动率比 $R > R_{\text{GBM}}$ 蕴含存在特定周期 $\tau^\ast$，在该周期上市场强度 $\mathcal{S}(\tau^\ast) > 0$**。无需 fBm 单一 Hurst 假设、无需常数漂移假设。
>
> **状态**：workbench 草稿 · 待数据验证闭合后再考虑入库 theorems。
>
> **起源**：研究者命题"高跨期波动率比值说明长周期波动率远大于短周期，那么至少存在一个特定周期，市场强度是高的"。
>
> **与已有定理的关系**：与 [theorem:structural-shaping-alpha#hurst-evolution-and-trend-alpha-decay](../../../../theorems/theory-library/structural-shaping-alpha/hurst-evolution-and-trend-alpha-decay.md) 互补——后者在单一 $H$ 假设下推导 $H \to s_{\text{eff}}$ 的显式映射；本文放宽为尺度依赖 $H(\tau)$，用纯数学给出存在性命题。

---

## 目录

1. [动机与核心命题](#1-动机与核心命题)
2. [基础定义](#2-基础定义)
3. [核心引理：标度积分](#3-核心引理标度积分)
4. [主定理：跨周期比值蕴含市场强度存在性](#4-主定理跨周期比值蕴含市场强度存在性)
5. [从局部 Hurst 到市场强度](#5-从局部-hurst-到市场强度)
6. [完整传递链](#6-完整传递链)
7. [注记与边界](#7-注记与边界)
8. [与 GBM 翻译的桥接](#8-与-gbm-翻译的桥接)
9. [与已有定理的关系](#9-与已有定理的关系)
10. [未闭合问题](#10-未闭合问题)

---

## 1. 动机与核心命题

研究者观察到：在 ATR 跨周期比值研究中，$R_{\text{bar}} = \text{ATR}_{1h} / \text{ATR}_{15m}$ 的中位数 1.82 小于理论 GBM 值 2.0（[factor-library/atr-cross-timeframe-ratio/evidence.md](../../../../theorems/factor-library/atr-cross-timeframe-ratio/evidence.md)）。这说明主流市场平均而言呈现波动率子扩散（$H < 1/2$）。

但反过来问：**如果 $R > R_{\text{GBM}}$，是否能推出"市场强度"非零？**

直觉上，$R > R_{\text{GBM}}$ 意味着长周期累积波动远超短周期，这对应某种趋势凝聚或持续性漂移，似乎应当对应"某尺度上市场强度高"。本文用纯数学严格化这一直觉。

**核心命题（非正式）**：跨周期波动率比严格超过 GBM 基线，蕴含存在区间内某个特定周期，在该周期上市场强度严格为正。

---

## 2. 基础定义

放宽 fBm 的单一 $H$ 假设，允许 $H$ 随尺度变化。

### 2.1 波动率标度曲线

设价格过程 $\{S_t\}$ 的对数收益在尺度 $\tau$ 上的标准差为 $\sigma_\tau$。假设 $\sigma_\tau$ 作为 $\tau$ 的函数在 $[\tau_{\min}, \tau_{\max}]$ 上连续可微且严格正。

### 2.2 局部 Hurst 指数

**定义 2.1（局部 Hurst 指数）**：

$$
\boxed{\;H(\tau) := \frac{d \ln \sigma_\tau}{d \ln \tau}\;}
$$

这是波动率标度曲线在双对数坐标下的局部斜率。

- $H \equiv 1/2$：尺度不变，对应 GBM（独立增量）；
- $H > 1/2$：该尺度上增量正相关（persistent，趋势凝聚）；
- $H < 1/2$：该尺度上增量负相关（anti-persistent，均值回归）。

**注 2.2**：单一 $H$ 的 fBm 是 $H(\tau) \equiv H$ 的特例。实际市场的 $H(\tau)$ 通常非恒定（如 [hur...](../../../../theorems/theory-library/structural-shaping-alpha/hurst-evolution-and-trend-alpha-decay.md) §2.5 的时代演化，或同一时点不同尺度上的子扩散/趋势凝聚共存）。

### 2.3 跨周期波动率比

**定义 2.3**：对 $\tau_1 < \tau_2$，

$$
R(\tau_1, \tau_2) := \frac{\sigma_{\tau_2}}{\sigma_{\tau_1}}
$$

GBM 基线：$R_{\text{GBM}}(\tau_1, \tau_2) := \sqrt{\tau_2 / \tau_1}$。

### 2.4 区间平均 Hurst

**定义 2.4**：

$$
\overline{H}(\tau_1, \tau_2) := \frac{1}{\ln(\tau_2/\tau_1)} \int_{\ln \tau_1}^{\ln \tau_2} H(\tau) \, d\ln \tau
$$

则 $\ln R(\tau_1, \tau_2) = \overline{H}(\tau_1, \tau_2) \cdot \ln(\tau_2/\tau_1)$。

---

## 3. 核心引理：标度积分

**引理 3.1（标度积分）**：

$$
\boxed{\;\ln R(\tau_1, \tau_2) = \int_{\ln \tau_1}^{\ln \tau_2} H(\tau) \, d\ln \tau\;}
$$

**证明**：

$$
\ln R(\tau_1, \tau_2) = \ln \sigma_{\tau_2} - \ln \sigma_{\tau_1} = \int_{\ln \tau_1}^{\ln \tau_2} d\ln \sigma_\tau = \int_{\ln \tau_1}^{\ln \tau_2} \frac{d\ln \sigma_\tau}{d\ln \tau} \, d\ln \tau = \int_{\ln \tau_1}^{\ln \tau_2} H(\tau) \, d\ln \tau
$$

最后一步用定义 2.1。$\square$

**推论 3.2**：

$$
\ln R(\tau_1, \tau_2) - \ln R_{\text{GBM}}(\tau_1, \tau_2) = \int_{\ln \tau_1}^{\ln \tau_2} \left(H(\tau) - \tfrac{1}{2}\right) d\ln \tau
$$

**证明**：$\ln R_{\text{GBM}} = \frac{1}{2} \ln(\tau_2/\tau_1) = \int_{\ln \tau_1}^{\ln \tau_2} \frac{1}{2} \, d\ln \tau$。与引理 3.1 相减即得。$\square$

---

## 4. 主定理：跨周期比值蕴含市场强度存在性

**定理 4.1（存在性）**：

$$
\boxed{\;R(\tau_1, \tau_2) > R_{\text{GBM}}(\tau_1, \tau_2) \;\Longrightarrow\; \exists\, \tau^\ast \in (\tau_1, \tau_2): H(\tau^\ast) > \tfrac{1}{2}\;}
$$

**证明**：

由 $R > R_{\text{GBM}}$ 与推论 3.2：

$$
\int_{\ln \tau_1}^{\ln \tau_2} \left(H(\tau) - \tfrac{1}{2}\right) d\ln \tau = \ln R - \ln R_{\text{GBM}} > 0
$$

由 $H(\tau)$ 的连续性（来自 $\sigma_\tau$ 的连续可微性假设），被积函数 $f(\tau) := H(\tau) - 1/2$ 在闭区间 $[\ln \tau_1, \ln \tau_2]$ 上连续。

由积分中值定理：存在 $\xi \in (\ln \tau_1, \ln \tau_2)$ 使得

$$
f(\xi) = \frac{1}{\ln(\tau_2/\tau_1)} \int_{\ln \tau_1}^{\ln \tau_2} f(\tau) \, d\ln \tau > 0
$$

令 $\tau^\ast := e^\xi \in (\tau_1, \tau_2)$，则 $H(\tau^\ast) > 1/2$。$\square$

**注 4.2（严格不等号的必要性）**：$R = R_{\text{GBM}}$ 只给出 $\overline{H} = 1/2$，不能保证存在 $\tau^\ast$ 使 $H(\tau^\ast) > 1/2$——$H$ 可能在 $1/2$ 附近对称振荡，积分为零但处处不超过 $1/2$。严格 $R > R_{\text{GBM}}$ 是存在性的必要条件。

**注 4.3（逆命题不成立）**：存在 $\tau^\ast$ 使 $H(\tau^\ast) > 1/2$ **不能**推出 $R > R_{\text{GBM}}$——其他尺度上 $H < 1/2$ 可能拉低积分。只有 $H(\tau) > 1/2$ 在整个 $[\tau_1, \tau_2]$ 上成立时才有 $R > R_{\text{GBM}}$。

形式化：$H(\tau) > 1/2 \; \forall \tau \in [\tau_1, \tau_2] \Rightarrow R > R_{\text{GBM}}$（充分条件，非必要）。

### 4.5 子区间非平凡版本

#### 4.5.1 平凡性诊断

定理 4.1 在 $c$ 可取区间端点时平凡：取 $c \in (\tau_1, \tau_2)$ 任意，$H(c)$ 是中值定理给的存在性点，但不保证它落在任何**预设的子区间**内。

更严重的是，当 $c$ 取区间 $[\tau_1, \tau_2]$ 本身时（即用区间平均 $\overline{H}(\tau_1, \tau_2)$ 代替点值 $H(c)$），$H$ 由 $R$ 直接决定：

$$\overline{H}(\tau_1, \tau_2) = \frac{\ln R(\tau_1, \tau_2)}{\ln(\tau_2/\tau_1)}$$

此时 $R > R_{\text{GBM}} \Leftrightarrow \overline{H} > 1/2$ 是**定义自洽**，不是经验发现。

#### 4.5.2 非平凡问题陈述

**问题**：给定 $R(a, b)$，能否推出某个**真子区间** $[a, c] \subset [a, b]$（$a < c < b$）上 $\overline{H}(a, c) > 1/2$？

关键区别：$\overline{H}(a, c) = \ln(\sigma_c / \sigma_a) / \ln(c/a)$ 依赖 $\sigma_c$，而 $\sigma_c$ 是 $[a, b]$ 内部的未知值，**不由 $R(a, b)$ 单独决定**。

#### 4.5.3 积分可加性引理

**引理 4.5（积分可加性）**：对任意 $c \in (a, b)$，

$$\overline{H}(a, c) \cdot \ln\frac{c}{a} + \overline{H}(c, b) \cdot \ln\frac{b}{c} = \overline{H}(a, b) \cdot \ln\frac{b}{a}$$

**证明**：由引理 3.1，$\ln R(a, c) + \ln R(c, b) = \ln R(a, b)$。展开即得。$\square$

**推论 4.6（剩余子区间约束）**：定义 $\Delta := \overline{H}(a, b) - 1/2$（全区间超出 GBM 的部分），则

$$\left(\overline{H}(a, c) - \tfrac{1}{2}\right) \ln\frac{c}{a} + \left(\overline{H}(c, b) - \tfrac{1}{2}\right) \ln\frac{b}{c} = \Delta \cdot \ln\frac{b}{a}$$

**证明**：引理 4.5 两边减 $\frac{1}{2} \ln(b/a) = \frac{1}{2}[\ln(c/a) + \ln(b/c)]$。$\square$

#### 4.5.4 子区间非平凡定理

**定理 4.7（子区间存在性，非平凡版本）**：

设 $R(a, b) > R_{\text{GBM}}(a, b)$（即 $\Delta > 0$）。定义权重

$$w_c := \frac{\ln(c/a)}{\ln(b/a)} \in (0, 1)$$

则对任意 $c \in (a, b)$：

$$\overline{H}(a, c) > \tfrac{1}{2} \;\Longleftrightarrow\; \overline{H}(c, b) < \overline{H}(a, b) + \frac{(1 - w_c)}{w_c} \cdot \frac{\Delta}{1}$$

等价地，定义 $\delta_c := \overline{H}(c, b) - 1/2$（剩余子区间超出量），则

$$\boxed{\;\overline{H}(a, c) > \tfrac{1}{2} \;\Longleftrightarrow\; \delta_c < \frac{\Delta}{1 - w_c}\;}$$

**证明**：由推论 4.6，$(\overline{H}(a, c) - 1/2) \cdot w_c \cdot \ln(b/a) + \delta_c \cdot (1 - w_c) \cdot \ln(b/a) = \Delta \cdot \ln(b/a)$。两边除 $\ln(b/a)$：

$$(\overline{H}(a, c) - \tfrac{1}{2}) w_c + \delta_c (1 - w_c) = \Delta$$

故 $\overline{H}(a, c) > 1/2 \Leftrightarrow \overline{H}(a, c) - 1/2 > 0 \Leftrightarrow \delta_c < \Delta / (1 - w_c)$。$\square$

#### 4.5.5 物理含义

定理 4.7 把"子区间 $[a,c]$ 上 $H > 1/2$"转化为"**剩余子区间 $[c,b]$ 上 $H$ 不超过某个上界**"。

- 全区间超 GBM 的量 $\Delta$ 是"预算"
- 这个预算在子区间 $[a,c]$ 和 $[c,b]$ 之间分配
- $[a,c]$ 上 $H > 1/2$ 当且仅当 $[c,b]$ 上 $H$ 不超过 $\Delta / (1-w_c) + 1/2$

**关键**：这个等价关系是**精确的**，不依赖中值定理的"存在性"——它给出了 $\overline{H}(a,c) > 1/2$ 的充要条件。

#### 4.5.6 仍需额外信息的困境

定理 4.7 把问题从"$R(a,b) \Rightarrow \overline{H}(a,c) > 1/2$"转化为"$R(a,b) \Rightarrow \overline{H}(c,b) < \text{某上界}$"——后者仍依赖 $\overline{H}(c,b)$，而 $\overline{H}(c,b)$ 不由 $R(a,b)$ 单独决定。

**核心困境不变**：单凭 $R(a,b)$ 一个标量，无法约束 $H(\tau)$ 在内部点的值。要闭合，仍需形状假设（P0-P4，见 [hurst-shape-assumptions-testability.md](hurst-shape-assumptions-testability.md)）。

#### 4.5.7 Lipschitz 假设下的非平凡推论

引入 [P1 Lipschitz 假设](hurst-shape-assumptions-testability.md#5-p1-lipschitz-平滑性假设)：$|H(\tau) - H(\tau')| \le L |\ln \tau - \ln \tau'|$。

**定理 4.8（Lipschitz 下的子区间下界）**：在 P1 下，对任意 $c \in (a, b)$，

$$\overline{H}(a, c) \ge \overline{H}(a, b) - L \cdot \frac{\int_a^c \ln\frac{c}{\tau} \, d\ln\tau + \int_c^b \ln\frac{\tau}{c} \, d\ln\tau}{\ln(c/a)}$$

简化（利用 Lipschitz 把 $H(\tau)$ 偏离 $\overline{H}(a,b)$ 的程度约束在 $L \cdot d(\tau)$ 内）：

$$\overline{H}(a, c) \ge \overline{H}(a, b) - L \cdot \tilde{d}(c)$$

其中 $\tilde{d}(c)$ 是 $c$ 到区间 $[a, b]$ 端点的最大对数距离的函数。

**可盈利充分条件**（结合 [§11.5](#11.5-临界-hurst-与临界比值) 的 $H^\ast$）：

$$\boxed{\;\overline{H}(a, b) \ge H^\ast(c) + L \cdot \tilde{d}(c) \;\Longrightarrow\; \overline{H}(a, c) \ge H^\ast(c)\;}$$

即：若全区间平均 $\overline{H}(a,b)$ 足够高（超过 $H^\ast + L \tilde{d}$），则子区间 $[a,c]$ 上 $\overline{H}$ 也超过 $H^\ast$——可盈利。

#### 4.5.8 与实证的对照

[简报 §7](hurst-vs-rbar-briefing.md#七h-曲线分叉点量化分析) 的分叉点分析显示：
- 高 R 组（$\overline{H}(15\text{m}, 1\text{h}) \approx 0.52$，$\Delta \approx 0.02$）
- 子区间 $[5\text{m}, 15\text{m}]$ 上 $\overline{H} \approx 0.475 < 1/2$

代入定理 4.7：$\overline{H}(5\text{m}, 15\text{m}) > 1/2 \Leftrightarrow \delta_{15\text{m}} < \Delta / (1 - w_{15\text{m}})$

但 $5\text{m} < 15\text{m}$，所以 $[5\text{m}, 15\text{m}]$ 不是 $[15\text{m}, 1\text{h}]$ 的子区间——这说明实测的"短周期不跟随"是**区间外部**的信息，不是定理 4.7 所描述的**区间内部子区间**问题。

**正确对照**：要检验定理 4.7，需在 $[15\text{m}, 1\text{h}]$ 内部取子区间（如 $[15\text{m}, 30\text{m}]$），看 $\overline{H}(15\text{m}, 30\text{m})$ 是否满足充要条件——这需要 30m 数据，当前不可得。

#### 4.5.9 小结

| 版本 | 定理 | 性质 | 可实践性 |
|------|------|------|----------|
| 原（§4.1） | $R > R_{\text{GBM}} \Rightarrow \exists c \in (a,b): H(c) > 1/2$ | 平凡（c 可取区间本身） | 低 |
| 非平凡（§4.5.4） | $\overline{H}(a,c) > 1/2 \Leftrightarrow \delta_c < \Delta/(1-w_c)$ | 精确充要条件，但需 $\overline{H}(c,b)$ | 中（需额外观测） |
| Lipschitz（§4.5.7） | $\overline{H}(a,b) \ge H^\ast + L\tilde{d} \Rightarrow \overline{H}(a,c) \ge H^\ast$ | 充分条件，仅需 $L$ | **高**（可实践门槛） |

子区间非平凡版本把问题从"存在性"推进到"充要条件"，但仍需形状假设才能闭合为可实践门槛。Lipschitz 假设下的版本（定理 4.8）给出可实践的充分条件——这与 [hurst-shape-assumptions-testability.md §5](hurst-shape-assumptions-testability.md#5-p1-lipschitz-平滑性假设) 的 P1 检验对接。

---

## 5. 从局部 Hurst 到市场强度

### 5.1 广义市场强度

为避免与 [structural-shaping-alpha#when-barrier-shaping-yields-alpha §3.3](../../../../theorems/theory-library/structural-shaping-alpha/when-barrier-shaping-yields-alpha.md) 的 $s = \nu/\sigma$ 混淆，本文定义基于自相关的广义市场强度。

**定义 5.1（广义市场强度）**：在尺度 $\tau$ 上，设 lag-1 增量自相关为 $\rho_1(\tau)$，定义

$$
\boxed{\;\mathcal{S}(\tau) := \frac{\arcsin \rho_1(\tau)}{\pi}\;}
$$

$\mathcal{S} = 0$ 对应独立增量；$\mathcal{S} > 0$ 对应趋势凝聚；$\mathcal{S} < 0$ 对应均值回归。

**注 5.2（与顺势概率的关系）**：由 [引理 3.1 Sheppard 公式](../../../../theorems/theory-library/structural-shaping-alpha/hurst-evolution-and-trend-alpha-decay.md#L103)，$P_{\text{顺}}(\tau) = 1/2 + \mathcal{S}(\tau)$。故 $\mathcal{S} > 0 \Leftrightarrow P_{\text{顺}} > 1/2$。

### 5.2 局部 Hurst 到自相关

**命题 5.3（局部 Hurst 到自相关）**：在 fBm 局部近似下，尺度 $\tau$ 上的 lag-1 增量自相关

$$
\rho_1(\tau) \approx 2^{2H(\tau) - 1} - 1
$$

**注 5.4**：此步**不是纯数学**——严格 fBm 假设 $H(\tau) \equiv H$ 全局恒定。对 $H(\tau)$ 非恒定的一般过程，此关系是局部 fBm 近似。本文主定理（§4）不依赖此命题；本命题仅用于把 $H > 1/2$ 翻译为 $\mathcal{S} > 0$。

**推论 5.5**：若命题 5.3 成立，则

$$
H(\tau^\ast) > \tfrac{1}{2} \;\Longrightarrow\; \rho_1(\tau^\ast) > 0 \;\Longrightarrow\; \mathcal{S}(\tau^\ast) > 0
$$

**证明**：$H > 1/2 \Rightarrow 2^{2H-1} > 1 \Rightarrow \rho_1 > 0 \Rightarrow \arcsin(\rho_1) > 0 \Rightarrow \mathcal{S} > 0$。$\square$

---

## 6. 完整传递链

**主结论（合成）**：

$$
\boxed{\;R(\tau_1, \tau_2) > \sqrt{\tau_2/\tau_1} \;\Longrightarrow\; \exists\, \tau^\ast \in (\tau_1, \tau_2): \mathcal{S}(\tau^\ast) > 0\;}
$$

**传递链**：

$$
R > R_{\text{GBM}} \xRightarrow[\text{中值定理}]{\text{§4}} \exists\, \tau^\ast: H(\tau^\ast) > \tfrac{1}{2} \xRightarrow[\text{fBm 局部近似}]{\text{§5.2}} \rho_1(\tau^\ast) > 0 \xRightarrow[\text{Sheppard}]{\text{§5.1}} P_{\text{顺}}(\tau^\ast) > \tfrac{1}{2} \xRightarrow[\text{定义}]{\text{§5.1}} \mathcal{S}(\tau^\ast) > 0
$$

- **前三步**（$R > R_{\text{GBM}} \Rightarrow H(\tau^\ast) > 1/2$）：纯数学，无 fBm 假设、无 $\nu \ne 0$ 假设，仅依赖波动率标度曲线可微性。
- **后三步**（$H(\tau^\ast) > 1/2 \Rightarrow \mathcal{S}(\tau^\ast) > 0$）：依赖 fBm 局部近似（命题 5.3）。

---

## 7. 注记与边界

### 7.1 存在性 vs 构造性

本定理是**存在性**命题：保证 $\tau^\ast \in (\tau_1, \tau_2)$ 存在，但不给出 $\tau^\ast$ 的具体值。定位 $\tau^\ast$ 需要额外信息（如对 $H(\tau)$ 的非参数估计）。

### 7.2 广义市场强度 $\mathcal{S}$ 与 GBM 市场强度 $s = \nu/\sigma$ 的区分

这是最关键的区分：

- **$s = \nu/\sigma$**（[when-barrier-shaping §3.3](../../../../theorems/theory-library/structural-shaping-alpha/when-barrier-shaping-yields-alpha.md)）：捕获**常数漂移**。纯 fBm 在 $\nu = 0$ 时 $s = 0$，即便 $H > 1/2$ 也是如此。
- **$\mathcal{S} = \arcsin(\rho_1)/\pi$**（本文）：捕获**增量自相关**带来的趋势凝聚。在 fBm 框架下 $\nu = 0$ 但 $H > 1/2$ 时 $\mathcal{S} > 0$。

$\mathcal{S}$ 是比 $s$ 更本源的市场强度度量——它能在 $\nu = 0$ 的纯 fBm 框架下识别趋势凝聚，而 $s$ 不能。

仅当 $\nu \ne 0$ 时两者都为正：$s$ 来自漂移，$\mathcal{S}$ 来自自相关，二者独立。

### 7.3 严格不等号的必要性

$R = R_{\text{GBM}}$ 不能推出存在 $\tau^\ast$。反例：$H(\tau) = 1/2 + \epsilon \sin(2\pi \ln \tau / \ln(\tau_2/\tau_1))$ 在整数个周期上积分为零，但处处不超过 $1/2$ 时也存在 $H \le 1/2$。

实测中需注意：$R$ 的估计噪声可能让 $R \approx R_{\text{GBM}}$ 难以判定严格不等号方向。

### 7.4 假设清单

| 假设 | 用于 | 严格性 |
|------|------|--------|
| $\sigma_\tau$ 在 $[\tau_1, \tau_2]$ 连续可微 | §2.2、§4 定理 | 数学 |
| $H(\tau)$ 连续 | §4 中值定理 | 数学（来自上一条） |
| fBm 局部近似 $\rho_1 \approx 2^{2H-1} - 1$ | §5.2 命题 5.3 | 工程 |
| Sheppard 公式（联合高斯） | §5.1 定义 5.1 | 数学（增量联合高斯时严格） |

主定理（§4）只依赖前两条纯数学假设。

---

## 8. 与 GBM 翻译的桥接

若要把本文的 $\mathcal{S}$ 翻译为 [structural-shaping-alpha](../../../../theorems/theory-library/structural-shaping-alpha/when-barrier-shaping-yields-alpha.md) 框架的 $s_{\text{eff}}$，需引入工程近似。

**假设 8.1（短窗累积近似）**：即 [hurst-evolution §4.1 假设 4.1](../../../../theorems/theory-library/structural-shaping-alpha/hurst-evolution-and-trend-alpha-decay.md#L138)——在 barrier 触达时窗内，fBm 的方向凝聚可用等价 GBM 漂移 $s_{\text{eff}}$ 近似。

**推论 8.2（等价 GBM 翻译）**：在假设 8.1 下，

$$
s_{\text{eff}}(\tau^\ast) \approx \sqrt{2\pi} \cdot \mathcal{S}(\tau^\ast) / \sqrt{\tau^\ast} > 0
$$

使该尺度上的 barrier 塑形产生正的 $\Delta P_{\text{win}}$（[推论 4.3](../../../../theorems/theory-library/structural-shaping-alpha/hurst-evolution-and-trend-alpha-decay.md#L156)）。

**注 8.3**：此步**不是纯数学**——假设 8.1 是"$H \ne 1/2$ 的 fBm barrier 问题无闭式，需与等价 GBM 拟合"的工程近似（见 [Molchan 2003](../../../../theorems/theory-library/structural-shaping-alpha/hurst-evolution-and-trend-alpha-decay.md) fBm 首达无闭式解的证明）。

---

## 9. 与已有定理的关系

### 9.1 与 hurst-evolution-and-trend-alpha-decay 的互补

| 维度 | hurst-evolution | 本文 |
|------|----------------|------|
| $H$ 假设 | 单一全局 $H$ | 尺度依赖 $H(\tau)$ |
| 结论形式 | 显式映射 $H \to s_{\text{eff}}$ | 存在性 $\exists \tau^\ast$ |
| 严格性 | 含假设 4.1 工程近似 | 主定理纯数学 |
| 适用 | 跨时代演化叙事 | 单一时点跨尺度存在性 |

两者共享 fBm 自相关结构，但本文不要求 $H$ 全局恒定，更贴近实际市场的多尺度结构。

### 9.2 与 when-barrier-shaping-yields-alpha 的连接

- **$s = \nu/\sigma$** 是 [when-barrier §3.3](../../../../theorems/theory-library/structural-shaping-alpha/when-barrier-shaping-yields-alpha.md) 的决策变量；
- **$\mathcal{S}$** 是本文定义的更本源度量，在 $\nu = 0$ 时仍能识别趋势凝聚；
- 在 $\nu \ne 0$ 且 $H > 1/2$ 时两者都为正，$s$ 来自漂移、$\mathcal{S}$ 来自自相关，互不替代。

未来若要把本文结论用于 barrier 塑形决策，需通过假设 8.1 翻译为 $s_{\text{eff}}$。

### 9.3 与 atr-cross-timeframe-ratio 因子的连接

[因子库 atr-cross-timeframe-ratio/definition.md](../../../../theorems/factor-library/atr-cross-timeframe-ratio/definition.md) 的 $R_{\text{bar}} = \text{ATR}_{1h} / \text{ATR}_{15m}$ 是本文 $R(\tau_1, \tau_2)$ 在 $\tau_1 = 15\text{m}, \tau_2 = 1\text{h}$ 的工程实现。

该因子的"共振扩张"象限（$S_H \ge 1 \wedge S_L \ge 1$，见 [definition.md](../../../../theorems/factor-library/atr-cross-timeframe-ratio/definition.md) 四象限定义）对应 $R$ 偏离 GBM 基线的方向性状态。

按本文主定理：
- "共振扩张"象限若 $R > R_{\text{GBM}}$（需用实际 ATR 窗口换算验证），蕴含某尺度 $\tau^\ast \in (15\text{m}, 1\text{h})$ 上 $\mathcal{S} > 0$；
- 但该因子实测中位 $R_{\text{bar}} = 1.82 < 2.0$，说明主流市场平均 $H < 1/2$，存在性定理不触发——这与该因子"状态/制度因子"（非方向 alpha）的定位一致。

---

## 10. 未闭合问题

1. **$\tau^\ast$ 的定位**：本定理只给存在性，不给 $\tau^\ast$ 的显式值。定位需对 $H(\tau)$ 做非参数估计（如多尺度 R/S 或小波方差）。

2. **从 $\mathcal{S} > 0$ 到可交易 alpha**：$\mathcal{S} > 0$ 只说明存在趋势凝聚，不说明可交易。barrier 塑形的可交易性需通过假设 8.1 翻译为 $s_{\text{eff}}$ 后用 [when-barrier §11](../../../../theorems/theory-library/structural-shaping-alpha/when-barrier-shaping-yields-alpha.md) 的盈亏下界 $x_{\min}$ 检验。

3. **$H(\tau)$ 估计器分歧**：[hurst-evolution 附录 B.6](../../../../theorems/theory-library/structural-shaping-alpha/hurst-evolution-and-trend-alpha-decay.md#L313) 指出 R/S 估计 $H \approx 0.60$ 与波动率子扩散反算 $H_\sigma \approx 0.448$ 存在分歧。本文 $H(\tau)$ 依赖 $\sigma_\tau$ 的导数，更接近 $H_\sigma$ 口径——这意味着本文存在性定理的触发条件（$R > R_{\text{GBM}}$）与 R/S 口径下 $H > 1/2$ 不直接等价。

4. **多周期联合**：本文只考虑单一 $[\tau_1, \tau_2]$ 区间。若同时观测多个区间 $[\tau_1, \tau_2], [\tau_2, \tau_3], \dots$，可构造更精细的 $\tau^\ast$ 定位——但需新的定理形式。

5. **非平稳性**：本文假设 $\sigma_\tau$ 是过程的稳态性质。实际市场 $H(\tau)$ 时变（见 [hur... §2.5 时代演化](../../../../theorems/theory-library/structural-shaping-alpha/hurst-evolution-and-trend-alpha-decay.md)）。本文定理在每个时点局部成立，但跨时点比较需额外假设。

---

## 11. 从存在性到可盈利的鸿沟

§4 主定理给出**存在性**：$R > R_{\text{GBM}} \Rightarrow \exists\, \tau^\ast: H(\tau^\ast) > 1/2$。但"存在趋势凝聚"远不等于"可通过塑形盈利"。本节分析三个递进问题：

1. $r$ 至少多大才能"可盈利"？
2. 能从 $a, b$ 算出 $c$ 吗？
3. 若要求 $c = 5\text{m}$ 或 $15\text{m}$，对 $a, b, r$ 有何要求？

### 11.1 问题陈述与符号

沿用前文记号：区间 $[a, b]$，比值 $r := R(a, b) = \sigma_b / \sigma_a$，GBM 基线 $r_0 := \sqrt{b/a}$。

引入 [when-barrier §11.3](../../../../theorems/theory-library/structural-shaping-alpha/when-barrier-shaping-yields-alpha.md) 的盈亏下界：

$$
x_{\min}(c_{\text{cost}}, K_S, R) = \sqrt{\frac{6 c_{\text{cost}}}{K_S^3 \, R(R-1)}}
$$

其中 $c_{\text{cost}}$ 为单边成本（ATR 计），$K_S$ 为止损距离，$R = K_T / K_S$ 为盈亏比。

### 11.2 两层条件：存在性 vs 可盈利

| 层次 | 条件 | 来源 |
|------|------|------|
| 存在性 | $r > r_0 = \sqrt{b/a}$ | §4 主定理 |
| 可盈利 | $s_{\text{eff}}(c) \ge x_{\min}$ | [when-barrier §11.3](../../../../theorems/theory-library/structural-shaping-alpha/when-barrier-shaping-yields-alpha.md) |

$r > r_0$ 只保证 $\exists c \in (a, b): H(c) > 1/2$，但 $H(c)$ 可以**任意接近 $1/2$**（当 $r$ 任意接近 $r_0$ 时），此时 $s_{\text{eff}} \to 0$，覆盖不了成本。

### 11.3 核心困境：标量 r 无法约束函数 H(τ)

设区间平均 $\overline{H} = \ln r / \ln(b/a)$。由中值定理，存在 $c$ 使 $H(c) = \overline{H}$；但 $H(c)$ 可以任意偏离 $\overline{H}$。

**反例**：$H(\tau) = 1/2 + \epsilon \sin(2\pi \ln \tau / \ln(b/a))$ 在区间上 $\overline{H} = 1/2$（$r = r_0$），但存在子区间 $H > 1/2$。反之，$H$ 可在大部分区间 $< 1/2$，仅在窄峰处 $> 1/2$，使 $\overline{H}$ 很高但 $H(c)$ 在指定点未必高。

**结论**：单凭标量 $r$（一个数）无法约束函数 $H(\tau)$（一条曲线）在指定点 $c$ 的值。要闭合"可盈利"问题，必须引入额外约束。

### 11.4 恒定 H 假设下可闭合

设 $H(\tau) \equiv H$ 恒定（fBm 假设），则 $H = \overline{H} = \ln r / \ln(b/a)$，可直接反算。

由 [hurst-evolution 命题 4.2](../../../../theorems/theory-library/structural-shaping-alpha/hurst-evolution-and-trend-alpha-decay.md#L145)：

$$
s_{\text{eff}}(H, c) \approx \frac{\sqrt{2\pi} \cdot \delta(H)}{\sqrt{c}}, \qquad \delta(H) = \frac{\arcsin(2^{2H-1} - 1)}{\pi}
$$

可盈利条件 $s_{\text{eff}} \ge x_{\min}$ 化为：

$$
\delta(H) \ge \frac{x_{\min} \sqrt{c}}{\sqrt{2\pi}}
$$

### 11.5 临界 Hurst 与临界比值

定义临界 $\delta^\ast(c) := x_{\min} \sqrt{c} / \sqrt{2\pi}$，反解临界 Hurst：

$$
\boxed{\;H^\ast(c) = \tfrac{1}{2} + \tfrac{1}{2} \log_2\!\left(1 + \sin\!\left(\pi \, \delta^\ast(c)\right)\right)\;}
$$

**证明**：由 $\delta(H) = \arcsin(2^{2H-1} - 1)/\pi$ 反解。设 $\delta \ge \delta^\ast$，则 $\arcsin(2^{2H-1} - 1) \ge \pi \delta^\ast$，故 $2^{2H-1} - 1 \ge \sin(\pi \delta^\ast)$，$2H - 1 \ge \log_2(1 + \sin(\pi \delta^\ast))$。$\square$

**临界比值**（恒定 $H$ 下的充分条件）：

$$
\boxed{\;r \ge r^\ast(a, b, c) := (b/a)^{H^\ast(c)}\;}
$$

### 11.6 问题 2：能从 a, b 算出 c 吗？

**不能**。三个独立原因：

1. **中值定理不构造性**：只给 $\exists c \in (a, b)$，不给具体值。

2. **恒定 $H$ 下 $c$ 不唯一**：$H(\tau) \equiv H$ 时任意 $c \in (a, b)$ 都满足 $H(c) = \overline{H}$，$c$ 退化为自由参数。

3. **非恒定 $H$ 下需额外信息**：要定位 $c$ 必须知道 $H(\tau)$ 的形状——如多尺度 R/S 估计、小波方差、或同时观测多个子区间 $[a, c'], [c', b]$ 反推 $H$ 在 $c'$ 附近的局部值。

### 11.7 问题 3：c = 5m 或 15m 对 a, b, r 的要求

#### 11.7.1 必要条件

$$
a < c < b
$$

对 $c = 5\text{m}$：需 $a < 5\text{m}$ 且 $b > 5\text{m}$（如 $a = 1\text{m}, b = 15\text{m}$ 或 $1\text{h}$）。
对 $c = 15\text{m}$：需 $a < 15\text{m}$ 且 $b > 15\text{m}$（如 $a = 5\text{m}, b = 1\text{h}$）。

#### 11.7.2 恒定 H 假设下的充分条件

$$
r \ge (b/a)^{H^\ast(c)}
$$

#### 11.7.3 $H^\ast(c)$ 的尺度依赖分析

由 $\delta^\ast(c) = x_{\min} \sqrt{c} / \sqrt{2\pi}$：

- $c$ 越小 → $\delta^\ast$ 越小 → $H^\ast$ 越接近 $1/2$ → 对 $H$ 的要求越宽松；
- $c$ 越大 → $\delta^\ast$ 越大 → $H^\ast$ 越高 → 对 $H$ 的要求越严格。

直观解释：$s_{\text{eff}} \propto 1/\sqrt{c}$，短周期 barrier 触达快、per-bar 口径下 $s_{\text{eff}}$ 更大，更容易覆盖成本。

| $c$ | $\sqrt{c}$ 相对值 | $s_{\text{eff}}$ 相对值 | $\delta^\ast$ 要求 | $H^\ast$ 要求 |
|-----|------------------|------------------------|-------------------|--------------|
| 5m | $\sqrt{5}$ | 大 | 低 | 低 |
| 15m | $\sqrt{15}$ | 中 | 中 | 中 |
| 1h | $\sqrt{60}$ | 小 | 高 | 高 |

**初步结论**：$c = 5\text{m}$ 比 $c = 15\text{m}$ 更容易触发可盈利条件——这与"高频更容易做塑形"的直觉一致。

#### 11.7.4 $x_{\min}$ 尺度归一化陷阱

**关键陷阱**：上述分析假设 $x_{\min}$ 与 $c$ 独立，但实际并非如此。

由 [when-barrier §2.4](../../../../theorems/theory-library/structural-shaping-alpha/when-barrier-shaping-yields-alpha.md) 的量纲约定，$K_S, K_T, c_{\text{cost}}$ 均以 ATR 归一化。若在尺度 $c$ 上做 barrier 塑形：

- $K_S^{(c)}$ 按 $c$-bar 的 ATR 归一化，$K_S^{(c)} \propto \sigma_c \sqrt{c}$；
- $c_{\text{cost}}^{(c)}$（单边成本）也按 $c$-bar 的 ATR 归一化。

若 $K_S$ 和 $c_{\text{cost}}$ 都按 $\sqrt{c}$ 缩放（即 barrier 宽度与成本同步随周期放大），则

$$
x_{\min} = \sqrt{\frac{6 c_{\text{cost}}}{K_S^3 R(R-1)}} \propto \frac{\sqrt{c_{\text{cost}}}}{K_S^{3/2}} \propto \frac{c^{1/4}}{c^{3/4}} = c^{-1/2}
$$

此时 $\delta^\ast(c) = x_{\min} \sqrt{c} / \sqrt{2\pi} \propto c^{-1/2} \cdot c^{1/2} = c^0$——**$\delta^\ast$ 与 $c$ 无关**！

这意味着 §11.7.3 的"短周期更易盈利"结论在严格 ATR 归一化下**消失**——所有周期对 $H$ 的要求相同。

**工程含义**：是否短周期更易盈利，取决于 $K_S$ 和 $c_{\text{cost}}$ 的实际缩放行为。若 barrier 宽度固定（不随周期缩放）而成本按 ATR 归一化，则短周期占优；若两者严格同步缩放，则周期无关。

### 11.8 综合结论

| 问题 | 一般 $H(\tau)$ 情形 | 恒定 $H$ 假设 |
|------|---------------------|--------------|
| $r$ 至少多大可盈利 | 不能从 $r$ 单独推出（需 $H$ 形状） | $r \ge (b/a)^{H^\ast(c)}$ |
| 能算 $c$ 吗 | 不能（中值定理不构造） | $c$ 在 $(a, b)$ 内不唯一 |
| $c=5\text{m}/15\text{m}$ 的要求 | 无法保证 $H(c) > 1/2$ | $a < c < b$ 且 $r \ge (b/a)^{H^\ast(c)}$ |

**核心困境**：单凭 $r$（一个标量）无法约束 $H(\tau)$（一个函数）在指定点的值。恒定 $H$ 假设是最强的简化，使问题闭合；一旦放宽，需要多尺度观测或 $H(\tau)$ 的形状先验。

### 11.9 工程含义与下一步

1. **存在性是"弱信号"**：$r > r_0$ 只说明市场在某尺度上有趋势凝聚，不等于可交易。从存在性到可盈利需穿越 $\delta^\ast$ 门槛。

2. **恒定 $H$ 是可用的一阶近似**：在缺乏多尺度数据时，用恒定 $H = \overline{H}$ 给出 $r^\ast$ 下界，是保守还是乐观取决于 $H(\tau)$ 的形状先验。

3. **短周期优势依赖成本结构**：§11.7.4 的陷阱说明"短周期更易盈利"不是免费的——需实际校准 $K_S, c_{\text{cost}}$ 的尺度缩放行为。

4. **下一步闭合方向**：
   - 用多尺度 ATR 数据估计 $H(\tau)$ 形状（非参数）；
   - 把 $H(\tau)$ 形状作为先验，构造 $c$ 的构造性定位定理；
   - 在 ATR 跨周期比值因子库数据上验证 $r^\ast$ 门槛的实证覆盖率。

---

## 附录 · 符号表

| 符号 | 含义 | 量纲 |
|------|------|------|
| $\tau$ | 时间尺度 | time |
| $\sigma_\tau$ | 尺度 $\tau$ 上的波动率 | price $\cdot$ time$^{-1/2}$ |
| $H(\tau)$ | 局部 Hurst 指数 | 无量纲 |
| $\overline{H}(\tau_1, \tau_2)$ | 区间平均 Hurst | 无量纲 |
| $R(\tau_1, \tau_2)$ | 跨周期波动率比 | 无量纲 |
| $R_{\text{GBM}}$ | GBM 基线比 $= \sqrt{\tau_2/\tau_1}$ | 无量纲 |
| $\rho_1(\tau)$ | lag-1 增量自相关 | 无量纲 |
| $\mathcal{S}(\tau)$ | 广义市场强度 $= \arcsin \rho_1 / \pi$ | 无量纲 |
| $P_{\text{顺}}(\tau)$ | 顺势概率 $= 1/2 + \mathcal{S}$ | 无量纲 |
| $s = \nu/\sigma$ | GBM 市场强度（when-barrier §3.3） | time$^{-1/2}$ |
| $s_{\text{eff}}$ | Hurst 诱导的等价 GBM 强度 | time$^{-1/2}$ |
| $a, b$ | 跨周期比值的两端周期 | time |
| $c$ | 待定位的可盈利周期 | time |
| $r$ | 跨周期波动率比 $= \sigma_b / \sigma_a$ | 无量纲 |
| $r_0$ | GBM 基线比 $= \sqrt{b/a}$ | 无量纲 |
| $x_{\min}$ | 盈亏下界（when-barrier §11.3） | 无量纲（ATR 归一化） |
| $c_{\text{cost}}$ | 单边成本（ATR 计） | ATR |
| $K_S, K_T$ | 止损/止盈距离 | ATR |
| $\delta(H)$ | Hurst 诱导的顺势概率增量 $= \arcsin(2^{2H-1}-1)/\pi$ | 无量纲 |
| $\delta^\ast(c)$ | 临界 $\delta$ $= x_{\min}\sqrt{c}/\sqrt{2\pi}$ | 无量纲 |
| $H^\ast(c)$ | 临界 Hurst（恒定 $H$ 下可盈利的下界） | 无量纲 |
| $r^\ast(a,b,c)$ | 临界比值 $= (b/a)^{H^\ast(c)}$ | 无量纲 |

---

## 版本历史

| 日期 | 版本 | 变更 |
|------|-----|------|
| 2026-08-08 | v0.1 | workbench 草稿；从研究讨论提炼主定理与传递链 |
| 2026-08-08 | v0.2 | 增补 §11「从存在性到可盈利的鸿沟」：临界 $H^\ast(c)$、临界比值 $r^\ast$、$x_{\min}$ 尺度归一化陷阱 |
| 2026-08-08 | v0.3 | 增补 §4.5「子区间非平凡版本」：积分可加性引理、充要条件定理 4.7、Lipschitz 下子区间下界定理 4.8 |
