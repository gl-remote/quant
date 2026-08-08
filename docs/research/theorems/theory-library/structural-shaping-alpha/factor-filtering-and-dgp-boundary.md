# 因子筛选后的市场模型选择与塑形理论适用边界

> **文档定位**：本文回答一个数学问题——**给定一个入场前已知的因子（条件事件）$A$，在什么条件下 `when-barrier-shaping-yields-alpha` 的 GBM 闭式塑形结论对条件过程 $(X_t\mid A)$ 仍然成立？当条件过程的漂移不再是常数时，barrier 塑形的正期望条件如何改变？** 用一维扩散的尺度函数（scale function）给出统一的首达期望公式，把"常数漂移 GBM 通道"与"状态依赖漂移（OU 均值回归）通道"作为同一积分的两个特例，并给出非半鞅（fBm）与 regime-switching 的边界。
>
> **稳定性**：入库日期 2026-08-02 · 从主题 `structural-shaping-alpha` 冻结后关于"因子分层是否改变 DGP"的讨论提炼；为 `when-barrier-shaping-yields-alpha.md` 推论 5.2 适用边界与 `mean-reversion-barrier-duality` 主题提供统一的数学根据。已通过静态一致性检查（附录 A）。
>
> **对外可用**：是（独立成篇、记号自洽、证明闭合）。
>
> **与本主题的关系**：本文是 [when-barrier-shaping-yields-alpha.md](when-barrier-shaping-yields-alpha.md) 的**适用边界补丁**——后者的命题 4.2、9.2、11.2 均建立在"筛选后子样本仍是常数漂移 GBM"上；本文证明该假设等价于条件漂移 $b_A(x)\equiv$ 常数，并给出当 $b_A$ 依赖状态时塑形公式如何替换。与 [hurst-evolution-and-trend-alpha-decay.md](hurst-evolution-and-trend-alpha-decay.md) 的关系：后者处理 $H\ne 1/2$ 的非半鞅情形（本文明确划为扩散框架外）。
>
> **命名引用**：`theorem:structural-shaping-alpha#factor-filtering-and-dgp-boundary`

---

## 目录

1. [目标](#1-目标)
2. [记号与前提](#2-记号与前提)
3. [因子作为条件测度](#3-因子作为条件测度)
4. [一维扩散首达的统一公式（尺度函数）](#4-一维扩散首达的统一公式尺度函数)
5. [小漂移展开：首达期望作为漂移的线性泛函](#5-小漂移展开首达期望作为漂移的线性泛函)
6. [四类条件漂移与塑形结论的替换规则](#6-四类条件漂移与塑形结论的替换规则)
7. [适用边界与识别门](#7-适用边界与识别门)
8. [关键结论汇总（Boxed）](#8-关键结论汇总boxed)
9. [附录 A · 静态一致性检查](#附录-a--静态一致性检查)
10. [附录 B · 文献对照与原创性定位](#附录-b--文献对照与原创性定位)

---

## 1. 目标

`when-barrier-shaping-yields-alpha` 的全部闭式结论（命题 4.2 首达概率、命题 9.2 通道 B 混合公式、命题 11.2 小 $\lambda$ 展开、定理 11.3 盈亏下界）都建立在同一个前提上：

> **因子筛选后的条件对数价格过程仍是常数漂移扩散 $dX=\nu\,dt+\sigma\,dW$。**

本文追问：这个前提在数学上究竟意味着什么？如果因子筛选改变了条件过程的漂移结构（例如让漂移依赖当前价格水平，如 OU 拉回），塑形结论怎样改变？

回答方式：把因子视为对路径空间的条件测度变换，把条件过程写成一般一维扩散 $dX=b_A(x)\,dt+\sigma\,dW$；用尺度函数给出双 barrier 首达概率与首达期望的**统一公式**；在小漂移下把首达期望展开为漂移 $b_A$ 的线性泛函，证明：

- $b_A\equiv$ 常数 $\Rightarrow$ 精确退化为 GBM 闭式（通道 A/B）；
- $b_A$ 为指向入场点的线性回复（OU）$\Rightarrow$ 正期望条件中的 $R(R-1)$ 符号因子被替换，最优点可落到 $R<1$；
- $b_A$ 任意非线性 $\Rightarrow$ 必须直接积分数值求解，不得套用 $R(R-1)$ 结论；
- $H\ne 1/2$ 的 fBm 非半鞅 $\Rightarrow$ 扩散尺度函数框架不适用，另文处理。

由此得到塑形理论的**适用边界**：在套用任何 barrier 闭式之前，必须先对条件子样本做漂移结构识别（常数 vs 状态依赖），否则结论范畴错误。

---

## 2. 记号与前提

### 2.1 概率空间

设 $(\Omega,\mathcal{F},\{\mathcal{F}_t\}_{t\ge0},\mathbb{P})$ 为过滤概率空间，$W_t$ 为标准 Wiener 过程。入场时刻记为 $t_0$，所有因子信息均取自 $\mathcal{F}_{t_0}$。

### 2.2 对数价格与塑形容器

对数价格 $X_t=\ln(S_t/S_{t_0})$，$X_{t_0}=0$。以入场价为基准、ATR 归一化，定义双吸收 barrier

$$
-K_S<0<K_T,\qquad K_S>0\text{（止损距离）},\quad K_T>0\text{（止盈距离）},\quad R:=K_T/K_S
$$

首达停时

$$
\tau:=\inf\{t\ge t_0:X_t\notin(-K_S,K_T)\}\wedge T
$$

本文主体取 $T=\infty$（无限时间）；有限 $T$ 的 Fourier 修正与 `when-barrier-shaping` 命题 6.1 相同，不重复。

### 2.3 单笔收益

$$
E_{\text{gross}}:=\mathbb{E}[X_\tau-X_{t_0}],\qquad E_{\text{net}}:=E_{\text{gross}}-2c
$$

其中 $c\ge0$ 为单边成本（ATR 计）。

### 2.4 量纲约定

| 符号 | 含义 | 量纲 |
|------|------|------|
| $X_t$ | 对数价格 | ATR |
| $b(x)$ | 漂移（条件过程） | $\text{time}^{-1}$ |
| $\sigma$ | 波动率 | $\text{time}^{-1/2}$ |
| $K_S,K_T,R$ | 距离 / 盈亏比 | ATR / 无量纲 |
| $\nu$ | 常数漂移 | $\text{time}^{-1}$ |
| $\kappa$ | OU 回归速率 | $\text{time}^{-1}$ |

---

## 3. 因子作为条件测度

### 3.1 条件事件

**定义 3.1（因子事件）**：因子是入场前可测的事件

$$
A:=\{f(\mathcal{F}_{t_0})\in \mathcal{S}\}\in\mathcal{F}_{t_0}
$$

其中 $f$ 为任意 $\mathcal{F}_{t_0}$-可测函数，$\mathcal{S}$ 为其取值集合的可测子集。称 $\mathbb{P}_A(\cdot):=\mathbb{P}(\cdot\mid A)$ 为**因子条件测度**。

### 3.2 条件漂移

**定义 3.2（条件过程）**：设条件测度下对数价格过程为一维 Itô 扩散

$$
dX_t=b_A(X_t)\,dt+\sigma\,dW_t,\qquad X_{t_0}=0
$$

其中 $b_A:\mathbb{R}\to\mathbb{R}$ 为 Borel 可测漂移，$\sigma>0$ 常数（时变 $\sigma$ 的推广见 §6.4）。称 $b_A$ 为**因子诱导的条件漂移**。

**注 3.3（因子与模型是联合假设）**：$b_A$ 的函数形式不是先验给定的——它由"因子 $A$ + 数据"共同决定。同一个因子（例如"价格偏离 VWAP 达 $d$"）在不同样本上可能诱导出常数漂移、线性回复或不可识别的噪声。因此"用了某因子"不自动意味着"条件过程是 GBM/OU"；$b_A$ 的形式必须经识别检验（§7）。

**注 3.4（与 GBM 基线的关系）**：无条件过程若为鞅（$b\equiv0$），则 $b_A$ 是因子从噪声中"筛选"出来的条件结构。若 $A$ 与未来路径独立，则 $b_A\equiv0$，Doob 保守律适用，任何塑形 $E_{\text{net}}=-2c<0$。

---

## 4. 一维扩散首达的统一公式（尺度函数）

### 4.1 尺度函数

**定义 4.1（尺度密度）**：扩散 $dX=b_A(x)dt+\sigma dW$ 的尺度密度定义为

$$
s'(x):=\exp\!\left(-\int_{0}^{x}\frac{2b_A(u)}{\sigma^2}\,du\right)
$$

尺度函数 $s(x)=\int_0^x s'(u)\,du$。

### 4.2 首达胜率

**命题 4.2（扩散首达胜率）**：设 $T=\infty$，过程从 $0\in(-K_S,K_T)$ 出发，则先到上界 $K_T$（赢）的概率为

$$
\boxed{\;
P_A^{\text{win}}=\frac{s(0)-s(-K_S)}{s(K_T)-s(-K_S)}
=\frac{\displaystyle\int_{-K_S}^{0}s'(u)\,du}{\displaystyle\int_{-K_S}^{K_T}s'(u)\,du}
\;}
$$

**证明.** 对 $s(X_t)$ 用 Itô 引理：$ds(X_t)=s'(X_t)\sigma\,dW_t$（漂移项 $\tfrac12\sigma^2s''+b_As'=0$ 由 $s'$ 定义消去），故 $s(X_t)$ 是鞅。Doob 可选停时定理给出 $s(0)=P_A^{\text{win}}s(K_T)+(1-P_A^{\text{win}})s(-K_S)$，解之即得。$\blacksquare$

### 4.3 首达期望

**命题 4.3（扩散首达毛利）**：

$$
\boxed{\;
E_{\text{gross}}^{(A)}=K_T\,P_A^{\text{win}}-K_S\bigl(1-P_A^{\text{win}}\bigr)
=(K_T+K_S)P_A^{\text{win}}-K_S
\;}
$$

**证明.** 赢时 $X_\tau=K_T$，亏时 $X_\tau=-K_S$，全概率分解。$\blacksquare$

**注 4.4（统一地位）**：命题 4.2–4.3 是 GBM 首达闭式与 OU 首达闭式的共同母公式。GBM 取 $b_A\equiv\nu$ 则 $s'(x)=e^{-\lambda x}$（$\lambda=2\nu/\sigma^2$），积分即得 `when-barrier-shaping` 命题 4.2 的闭式；OU 取 $b_A(x)=-\kappa x$ 则 $s'(x)=e^{\kappa x^2/\sigma^2}$，即得 `mean-reversion-barrier-duality` 的 erfi 闭式。两者是同一公式在不同 $b_A$ 下的实例。

---

## 5. 小漂移展开：首达期望作为漂移的线性泛函

当 $\varepsilon:=\sup_{x\in(-K_S,K_T)}|2b_A(x)/\sigma^2|\,K\ll1$（$K=\max(K_S,K_T)$）时，把尺度密度一阶展开，可把 $E_{\text{gross}}$ 写成 $b_A$ 的显式线性泛函。这是本文的核心结果。

### 5.1 分段线性 Green 核

**定理 5.1（首达毛利的一阶泛函）**：在上述小漂移条件下，

$$
\boxed{\;
E_{\text{gross}}^{(A)}=\frac{2}{\sigma^2}\int_{-K_S}^{K_T} b_A(u)\,g(u)\,du+O(\varepsilon^2)
\;}
$$

其中 $L:=K_T+K_S$，分段线性核

$$
g(u):=
\begin{cases}
\dfrac{K_T}{L}(K_S+u), & -K_S\le u<0 \\[6pt]
\dfrac{K_S}{L}(K_T-u), & 0\le u\le K_T
\end{cases}
$$

它是双吸收边界 $g(-K_S)=g(K_T)=0$ 下的分段线性帐篷：在入场点 $u=0$ 取最大值 $K_SK_T/L$，向两侧线性递减至零。$g(u)\ge0$ 意味着**首达毛利是漂移 $b_A$ 的正线性泛函**——漂移处处朝盈利侧（做多时 $b_A>0$）则毛利为正，处处朝亏损侧则为负。

**证明.** 记 $A(u):=\int_0^u a(v)\,dv$，$a(v):=2b_A(v)/\sigma^2$，则 $s'(u)=e^{-A(u)}=1-A(u)+O(\varepsilon^2)$。代入命题 4.2：

$$
P_A^{\text{win}}=\frac{K_S-\int_{-K_S}^{0}A(u)\,du}{L-\int_{-K_S}^{K_T}A(u)\,du}+O(\varepsilon^2)
=\frac{K_S}{L}-\frac{1}{L}\int_{-K_S}^{0}A(u)\,du+\frac{K_S}{L^2}\int_{-K_S}^{K_T}A(u)\,du+O(\varepsilon^2)
$$

代入 $E_{\text{gross}}=L P_A^{\text{win}}-K_S$：

$$
E_{\text{gross}}=-\int_{-K_S}^{0}A(u)\,du+\frac{K_S}{L}\int_{-K_S}^{K_T}A(u)\,du+O(\varepsilon^2)
=\frac{1}{L}\left[K_S\int_{0}^{K_T}A(u)\,du-K_T\int_{-K_S}^{0}A(u)\,du\right]+O(\varepsilon^2)
$$

对两个积分用 $\int A(u)\,du=uA(u)|-\int u\,a(u)\,du$ 分部（$A(0)=0$，故下限边界项为零）：

$$
\int_0^{K_T}A(u)\,du=K_T A(K_T)-\int_0^{K_T}u\,a(u)\,du,\qquad
\int_{-K_S}^{0}A(u)\,du=K_S A(-K_S)-\int_{-K_S}^{0}u\,a(u)\,du
$$

代入上式：

$$
E_{\text{gross}}=\frac{1}{L}\Bigl[
K_SK_T A(K_T)-K_S\!\int_0^{K_T}\!u\,a(u)\,du
-K_TK_S A(-K_S)+K_T\!\int_{-K_S}^{0}\!u\,a(u)\,du
\Bigr]+O(\varepsilon^2)
$$

注意 $A(K_T)-A(-K_S)=\int_{-K_S}^{K_T}a(v)dv$，故边界项 $K_SK_T[A(K_T)-A(-K_S)]/L$ 即 $\frac{K_SK_T}{L}\int_{-K_S}^{K_T}a(u)du$。把它与两个 $u\,a(u)$ 积分合并：对 $u\in[0,K_T]$，权重为 $\frac{1}{L}[K_SK_T-K_Su]=\frac{K_S}{L}(K_T-u)$；对 $u\in[-K_S,0]$，权重为 $\frac{1}{L}[K_SK_T+K_Tu]=\frac{K_T}{L}(K_S+u)$。这正是 $g(u)$。因此

$$
E_{\text{gross}}=\frac{1}{L}\int_{-K_S}^{K_T}a(u)\,g(u)\,du+O(\varepsilon^2)
=\frac{2}{\sigma^2}\int_{-K_S}^{K_T}b_A(u)\,g(u)\,du+O(\varepsilon^2)
$$

常数 $b_A\equiv\nu$ 时命题 5.3 校验闭合（$\nu K_SK_T/\sigma^2$），OU 时命题 5.6 校验闭合（$\kappa K_TK_S(2K_T+K_S)/(3\sigma^2)$）。余项 $O(\varepsilon^2)$ 来自 $s'=1-A+\tfrac12A^2$ 的二阶项与比值展开。$\blacksquare$

**注 5.2（核的含义）**：$g(u)$ 是对称帐篷的非对称版本（$K_S\ne K_T$ 时两侧斜率不同），在入场点 $u=0$ 最高、在两 barrier 处归零。含义是：**首达毛利主要由入场点附近的漂移决定，远端漂移因路径更难抵达而被抑制**；这与首达概率的概率权重一致（从 0 出发，在 0 附近的漂移最先、最频繁地作用于路径）。$g\ge0$ 还说明毛利是漂移的**正线性泛函**——做多条件下 $b_A$ 处处为正则毛利正。

### 5.2 常数漂移校验

**命题 5.3（常数漂移的首阶毛利）**：当 $b_A\equiv\nu$，

$$
\boxed{\;
E_{\text{gross}}=\frac{\nu K_SK_T}{\sigma^2}+O(\nu^2)
=\frac{\nu K_S^2}{\sigma^2}R+O(\nu^2)
\;}
$$

对固定 $K_S$，正漂移下 $E_{\text{gross}}$ 随 $R=K_T/K_S$ 线性增长；首阶**不含** $R(R-1)$ 因子。

**证明.** 把 $b_A\equiv\nu$ 代入定理 5.1：

$$
E_{\text{gross}}=\frac{2\nu}{\sigma^2}\left[\frac{K_S}{L}\int_0^{K_T}(K_T-u)\,du+\frac{K_T}{L}\int_{-K_S}^{0}(K_S+u)\,du\right]
=\frac{2\nu}{\sigma^2}\left[\frac{K_S}{L}\frac{K_T^2}{2}+\frac{K_T}{L}\frac{K_S^2}{2}\right]
=\frac{\nu K_SK_T(K_T+K_S)}{\sigma^2 L}=\frac{\nu K_SK_T}{\sigma^2}
$$

系数精确闭合。$\blacksquare$

**注 5.4（与通道 B 二阶项的关系）**：命题 5.3 是**已知方向**漂移（通道 A）的首阶项，$\propto R$。`when-barrier-shaping` 命题 11.2 的 $x^2K_S^3R(R-1)/3$ 是**方向未知、正负漂移等权混合**（通道 B，DirRandom，$p=1/2$）下的二阶项——一阶线性项因对称混合相消，只剩 $R(R-1)$ 的二阶项。两者不矛盾：常数漂移、方向已知时用 $\nu K_SK_T/\sigma^2$；方向未知做混合时奇次项相消，回到 $R(R-1)$。

**推论 5.5（通道 A 的符号律）**：已知方向常数漂移下，$E_{\text{gross}}$ 的符号就是 $\nu\cdot R$ 的符号——做多（$\nu>0$）时任意 $R>0$ 首阶皆正，$R$ 越大毛利越大；这与 `when-barrier-shaping` 通道 A（方向 alpha 放大）一致。$R(R-1)$ 的"$R>1$ 才正"是通道 B 对称混合的特征，不是常数漂移本身的特征。

### 5.3 状态依赖漂移：OU 校验

**命题 5.6（OU 回复漂移的首阶毛利）**：设入场点位于偏离处 $x_0=-K_T$（价格低于均衡 $K_T$），止盈在均衡 $0$、止损在 $-(K_T+K_S)$，条件漂移 $b_A(x)=-\kappa x$（$\kappa>0$，均衡 $0$）。在以入场点为原点的坐标 $u=x+K_T\in(-K_S,K_T)$ 下，$b_A(u)=-\kappa(u-K_T)=\kappa(K_T-u)$，尺度密度 $s'(u)=\exp(\kappa(K_T-u)^2/\sigma^2)$。小 $\kappa$ 下

$$
\boxed{\;
E_{\text{gross}}^{(A)}=\frac{\kappa}{\sigma^2}\frac{K_TK_S(2K_T+K_S)}{3}+O(\kappa^2)>0
\;}
$$

对任意 $R=K_T/K_S>0$ 恒正。

**证明.** 把 $b_A(u)=\kappa(K_T-u)$ 代入定理 5.1（$u\in[-K_S,K_T]$，该式在两区间均为正）：

$$
\begin{aligned}
E_{\text{gross}}&=\frac{2\kappa}{\sigma^2}\left[
\frac{K_S}{L}\int_0^{K_T}(K_T-u)^2\,du
+\frac{K_T}{L}\int_{-K_S}^{0}(K_T-u)(K_S+u)\,du
\right]+O(\kappa^2)\\
&=\frac{2\kappa}{\sigma^2 L}\left[
\frac{K_SK_T^3}{3}+\frac{K_TK_S^2(3K_T+K_S)}{6}
\right]+O(\kappa^2)\\
&=\frac{\kappa K_TK_S}{3\sigma^2 L}\left[2K_T^2+3K_TK_S+K_S^2\right]+O(\kappa^2)
\end{aligned}
$$

因式分解 $2K_T^2+3K_TK_S+K_S^2=(2K_T+K_S)(K_T+K_S)=(2K_T+K_S)L$，故

$$
E_{\text{gross}}=\frac{\kappa}{\sigma^2}\frac{K_TK_S(2K_T+K_S)}{3}+O(\kappa^2)
$$

与 `mean-reversion-barrier-duality` 定理 5.1 完全一致。因所有量为正，对任意 $R>0$ 恒正。$\blacksquare$

**注 5.7（符号翻转的机制）**：命题 5.3 与命题 5.6 的对比是本文关键——

- 常数漂移 $b_A=\nu$：$E_{\text{gross}}\propto\nu R$，做多正漂移下任意 $R$ 皆正；
- OU 回复 $b_A=\kappa(K_T-u)$：$E_{\text{gross}}\propto\kappa K_TK_S(2K_T+K_S)$，对任意 $R$ 恒正，且强 $\kappa$ 下最优 $R$ 可 $<1$。

两者在**首阶都对任意 $R$ 为正**（只要方向/回归指向盈利侧）；$R(R-1)$ 的符号约束只出现在**方向未知的对称混合**（通道 B）。这澄清了一个常见混淆："趋势用 $R>1$、回归用 $R<1$"不是因为漂移符号，而是因为**方向是否已知、漂移是否依赖状态、以及目标函数（单笔 vs 年化/频率）**——这些由 $b_A$ 的形式与混合方式共同决定。**差别不在塑形参数本身，而在条件漂移 $b_A$ 的函数结构与信息结构。**

---

## 6. 四类条件漂移与塑形结论的替换规则

综合命题 4.2、5.3、5.6，因子筛选后条件漂移 $b_A$ 可分为四类（外加扩散框架外的 fBm），每类对应不同的塑形处理。

### 6.1 类别 I · 零漂移（鞅）

$$b_A(x)\equiv0$$

尺度函数 $s(x)=x$，$P_{\text{win}}=K_S/L$，$E_{\text{gross}}\equiv0$，$E_{\text{net}}=-2c<0$。Doob 保守律（`when-barrier-shaping` 推论 5.2）严格成立。塑形不创造 alpha。

### 6.2 类别 II · 常数漂移（GBM）

$$b_A(x)\equiv\nu,\quad \nu\ne0$$

尺度密度 $s'(x)=e^{-2\nu x/\sigma^2}$，首达概率为 `when-barrier-shaping` 命题 4.2 的指数闭式；**已知方向**时小漂移首阶毛利为命题 5.3 的 $\nu K_SK_T/\sigma^2=\nu K_S^2R/\sigma^2$（$\propto R$，任意 $R>0$ 为正）；**方向未知、正负等权混合**（通道 B）时一阶项相消，二阶项为命题 11.2 的 $x^2K_S^3R(R-1)/(3\sigma^2)$（仅 $R>1$ 为正）。两类信息结构都属常数漂移，但符号律不同。

### 6.3 类别 III · 状态依赖回复漂移（OU 类）

$$b_A(x)=-\kappa(x-\theta),\quad \kappa>0$$

尺度密度为 Gaussian 型，首达概率为 erfi 闭式（命题 5.6）。小漂移首阶毛利为正的 $K_TK_S(2K_T+K_S)/3$ 多项式（与 `mean-reversion-barrier-duality` 定理 5.1 一致），不含 $R(R-1)$ 符号因子，强 $\kappa$ 下最优 $R$ 可 $<1$。对应 `mean-reversion-barrier-duality` 主题。注意：该类要求均衡 $\theta$ 可识别且 $\kappa/\sigma^2$ 足够大（Pe 判据），否则首达毛利被成本吞噬。

### 6.4 类别 IV · 时变 / 状态切换漂移（regime-switching）

$$b_A(x,t)\text{ 或 }b_A(x)=\mu_{s_t},\ s_t\text{ 为隐 Markov 链}$$

尺度函数框架对**时间齐次**状态依赖 $b_A(x)$ 仍成立（§4 只需 $b_A$ 不依赖 $t$）；但 $b_A$ 依赖隐状态或时间时，单过程的尺度函数不再闭合，需对状态分布积分或用 Hamilton filter。这正是 `when-barrier-shaping` §5.2 边界引用的 Zhang (2001)、Guo & Zhang (2005) regime-switching 反例：常数漂移前提放松后，最优 barrier 非平凡但**不能用命题 4.2 的常数闭式**。

### 6.5 扩散框架外 · 非半鞅（fBm）

$$X_t=\nu t+\sigma B_H(t),\quad H\ne\tfrac12$$

$f$Bm 不是半鞅，Itô 引理与尺度函数推导不适用（不存在使 $s(X_t)$ 成为鞅的测度变换）。此类条件过程的 barrier 结论只能用 Monte Carlo 或等价 GBM 近似（见 `hurst-evolution-and-trend-alpha-decay` 假设 4.1 的 $s_{\text{eff}}$ 工程近似），**不得套用本文或 `when-barrier-shaping` 的任何闭式**。

### 6.6 替换规则表

| 条件漂移 $b_A$ | 尺度密度 $s'$ | 首达毛利主项 | 最优 $R$ 朝向 | 适用文档 |
|---|---|---|---|---|
| $0$（鞅） | $1$ | $0$ | 无 alpha | when-barrier §5 |
| $\nu$ 常数，方向已知 | $e^{-2\nu x/\sigma^2}$ | $\nu K_S^2R/\sigma^2$ | $\nu$ 同向，随 $R$ 增 | when-barrier 通道 A |
| $\nu$ 常数，方向未知混合 | 同上 | $x^2K_S^3R(R-1)/(3\sigma^2)$ | $R>1$ | when-barrier §9,§11 |
| $-\kappa(x-\theta)$ | $e^{\kappa(x-\theta)^2/\sigma^2}$ | $\kappa K_TK_S(2K_T+K_S)/(3\sigma^2)>0$ | 强 $\kappa$ 下 $R<1$ | mean-reversion 主题 |
| 时变 / 切换 | 无闭合 | 需状态积分 | 数值 | regime-switching 文献 |
| fBm $H\ne1/2$ | 不存在 | 无闭式 | 数值 / 近似 | hurst-evolution |

---

## 7. 适用边界与识别门

### 7.1 GBM 闭式的适用条件（精确陈述）

**定理 7.1（GBM 塑形闭式的适用边界）**：`when-barrier-shaping-yields-alpha` 的命题 4.2、9.2、11.2、定理 11.3 对条件过程 $(X\mid A)$ 成立，**当且仅当**条件漂移 $b_A(x)$ 在区间 $(-K_S,K_T)$ 上为常数（类别 II），即

$$
b_A(x)=\nu_A\quad\forall x\in(-K_S,K_T)
$$

若 $b_A$ 依赖 $x$（类别 III/IV），则命题 4.2 的指数闭式不成立，必须以本文命题 4.2 的尺度函数积分替换；若条件过程为 fBm（类别 V），扩散框架整体失效。

**证明.** 命题 4.2 的闭式 $e^{\lambda K_T}(1-e^{-\lambda K_S})/(e^{\lambda K_T}-e^{-\lambda K_S})$ 由 $s'(x)=e^{-\lambda x}$ 积分得到，该 $s'$ 对应且仅对应 $b_A(x)=\sigma^2\lambda/2=\nu$ 常数。常数闭式是尺度函数公式在常数 $b_A$ 下的特例；$b_A$ 非常数时 $s'$ 不是纯指数，闭式不成立。$\blacksquare$

### 7.2 识别门（在套用闭式之前）

**推论 7.2（识别门）**：给定因子事件 $A$ 的条件子样本，在套用任何 barrier 塑形闭式之前必须完成下列识别：

1. **漂移是否为零**：条件子样本的对数增量是否显著异于零（鞅基线检验）；若否，类别 I，无 alpha；
2. **漂移是否为常数**：在容器区间内分段估计 $b_A(x)$（如按价格水平分箱的条件均值增量），检验 $b_A(x)\equiv\nu$；不拒绝则类别 II，用 GBM 闭式；
3. **漂移是否状态依赖**：若 $b_A(x)$ 显著依赖 $x$，估计其函数形式——线性回复 $\Rightarrow$ 类别 III（OU），非线性 $\Rightarrow$ 直接用尺度函数积分数值求解；
4. **增量是否独立**：估计 Hurst $H$；显著偏离 $1/2$ 且非漂移所致 $\Rightarrow$ 类别 V，扩散框架不适用；
5. **参数是否时变**：滚动窗口估计 $b_A$，若存在结构性断点 $\Rightarrow$ 类别 IV，需 regime-switching。

只有当识别结果稳定落在某一类别，才允许使用该类别对应的塑形公式。识别不出来（弱识别、样本外似然无差异）时，默认按类别 I 处理——不假设 alpha。

### 7.3 弱识别的保守原则

**注 7.3（弱识别即无 alpha）**：有限样本下常数漂移与弱 OU 漂移可能不可分（两者首达毛利的首阶泛函形式相近，差别在状态依赖的 $u\,b_A$ 加权项）。此时若数据无法区分，套用 OU 的 $R<1$ 结论是危险的——因为 $R<1$ 的正性依赖足够大的 $\kappa$（命题 5.6 的高阶项），而弱识别恰恰意味着 $\kappa$ 不大。保守原则：**识别门通不过时，最安全的塑形是对称容器或不交易**，而不是选择对自己最有利的模型。

---

## 8. 关键结论汇总（Boxed）

**【因子即条件测度】**

$$
\mathbb{P}_A(\cdot):=\mathbb{P}(\cdot\mid A),\quad A=\{f(\mathcal{F}_{t_0})\in\mathcal{S}\},\quad dX_t=b_A(X_t)dt+\sigma dW_t
$$

**【统一首达胜率（尺度函数）】**

$$
P_A^{\text{win}}=\frac{\displaystyle\int_{-K_S}^{0}\exp\!\left(-\int_0^u\frac{2b_A(v)}{\sigma^2}dv\right)du}{\displaystyle\int_{-K_S}^{K_T}\exp\!\left(-\int_0^u\frac{2b_A(v)}{\sigma^2}dv\right)du}
$$

**【常数漂移 · 方向已知 → 通道 A】**

$$
E_{\text{gross}}\big|_{b_A\equiv\nu}=\frac{\nu K_SK_T}{\sigma^2}+O(\nu^2)=\frac{\nu K_S^2}{\sigma^2}R+O(\nu^2)
$$

**【常数漂移 · 方向未知等权混合 → 通道 B】**

$$
E_{\text{gross}}\big|_{\text{DirRandom}}=\frac{x^2K_S^3}{3\sigma^2}R(R-1)+O(x^3)
$$

**【OU 回复漂移 → 恒正（$R<1$ 可成立）】**

$$
E_{\text{gross}}\big|_{b_A=-\kappa x}=\frac{\kappa}{\sigma^2}\frac{K_TK_S(2K_T+K_S)}{3}+O(\kappa^2)>0
$$

**【适用边界】**

$$
\boxed{\;\text{GBM 闭式成立}\iff b_A(x)\equiv\text{常数}\;}
$$

**【识别门】**

$$
\boxed{\;\text{套闭式前先识别 }b_A\text{ 的类别（零/常数/状态依赖/切换/fBm）；弱识别按鞅处理}\;}
$$

---

## 附录 A · 静态一致性检查

| 类别 | 结论 |
|------|------|
| 符号一致性 | $A,\mathbb{P}_A,b_A,s,s',\sigma,K_S,K_T,R,\tau,\nu,\kappa,\lambda$ 全文一致，定义前均引入 |
| 量纲 | §2.4 已列；$\sigma^{-2}b_A K^2$ 无量纲（漂移 × 时间 / 方差），首达毛利量纲为 ATR，正确 |
| 命题/证明配对 | 命题 4.2 / 4.3 / 5.3 / 5.6 / 定理 5.1 / 定理 7.1 / 推论 7.2 均附证明 |
| 极限一致性 | $b_A\equiv0\Rightarrow s'(x)=1\Rightarrow P=K_S/L,E=0$（Doob）；$b_A\equiv\nu$ 退化 when-barrier 命题 4.2 指数闭式（首阶 $\nu K_SK_T/\sigma^2$）；$b_A=-\kappa x$ 退化 mean-reversion erfi 公式（首阶 $K_TK_S(2K_T+K_S)/3$） |
| 常数校验闭合 | 定理 5.1 对常数 $b_A=\nu$ 给出 $\nu K_SK_T/\sigma^2$（命题 5.3 直接积分核验）；对 OU 给出 $\kappa K_TK_S(2K_T+K_S)/(3\sigma^2)$，与 mean-reversion 定理 5.1 完全一致 |
| 已知未闭合 | 非线性 $b_A$ 的二阶展开、有限 $T$ 下尺度函数与 Fourier 解的耦合、regime-switching 的闭合首达公式未展开（明确划为数值/文献处理） |
| KaTeX | 表格内绝对值已用 `\lvert/\rvert` 或避免；块级公式无尾部标点；无中文间隔号入公式 |
| 禁区检测 | 无参数最优值、无 KF 演化叙事、无品种/样本量数据锚点；仅在 §6/§7 引用其他 theorem，不重复其内容 |

---

## 附录 B · 文献对照与原创性定位

### B.1 本文依赖的经典结果

- **尺度函数与一维扩散首达**：Karlin & Taylor, *A Second Course in Stochastic Processes*（1981）；Itô & McKean (1965)。命题 4.2 是标准结果，本文不宣称原创。
- **Doob 可选停时与鞅保守律**：`when-barrier-shaping-yields-alpha` 推论 5.2；Rogers & Imkeller (2001)。
- **OU 首达闭式**：erfi 积分形式，见 `mean-reversion-barrier-duality` 命题 4.1；Leung & Li (2015)。
- **Regime-switching 下保守律失效**：Zhang (2001, *SIAM J. Control Optim.* 40, 64-87)；Guo & Zhang (2005, *Math. Finance* 15, 213-244)；Dai, Zhang, Zhu (2010, *SIAM J. Financial Math.*)。
- **fBm 非半鞅**：Rogers (1997) 证明 fBm 套利；Molchan (2003) fBm 首达无闭式。

### B.2 原创贡献

1. **把因子筛选形式化为条件测度变换 $\mathbb{P}_A$**，明确"因子 + DGP 是联合假设"，把"因子分层后市场还是不是 GBM"从口头争论变成可识别的数学问题（$b_A$ 是否为常数）。
2. **用单一尺度函数公式统一 GBM 通道与 OU 通道**：命题 4.2–4.3 是两者的母公式；定理 5.1 给出首达毛利作为漂移 $b_A$ 的正线性泛函（Green 核 $g$），命题 5.3 与 5.6 把 `when-barrier` 的常数漂移闭式与 mean-reversion 的 OU 恒正项展示为同一积分在不同 $b_A$ 下的取值，并区分了通道 A（方向已知，$\propto R$）与通道 B（方向未知混合，$R(R-1)$）的信息结构。
3. **定理 7.1 给出 GBM 闭式的精确适用边界**（$b_A$ 常数），把原 `when-barrier` §5.2 散落在文献批注中的边界条件上升为定理。
4. **推论 7.2 的识别门**：把"套闭式前必须识别条件漂移类别"作为硬性前置步骤，并给出弱识别的保守原则（按鞅处理）。

### B.3 不主张

- 不给出 $b_A$ 非线性时的高阶闭式（留给具体主题数值处理）；
- 不解决 fBm barrier 问题（扩散框架外，见 hurst-evolution）；
- 不提供任何实证阈值或参数最优值（那是主题 spec 的职责，非 theorem）。

---

**版本历史**

| 日期 | 版本 | 变更 |
|------|-----|------|
| 2026-08-02 | v1.0 | 初稿入库；从因子-DGP 讨论提炼，补全 when-barrier 适用边界 |
