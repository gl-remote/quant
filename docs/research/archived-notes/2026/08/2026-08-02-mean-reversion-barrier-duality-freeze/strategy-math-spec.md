# 数学规格 · mean-reversion-barrier-duality

> 类型：Theme / strategy-math-spec
> 状态：初稿（2026-08-02）· 阶段 0：OU 合成数据已验证，真实数据未校准
> 本文是主题唯一的策略行为定义；其他文档不得改变策略语义。

---

## 1. 目标

回答一个数学问题：

> **给定均值回归型对数价格过程与"入场于偏离处、近 barrier 指向均衡"的双 barrier 容器，在什么条件下低盈亏比 / 高胜率（$R=K_T/K_S<1$）使期望净收益与风险调整收益最优？**

回答方式：以 OU 过程为均值回归原型，推导双 barrier 首达胜率闭式、小回归强度展开、最优盈亏比 $R^\ast(\kappa)$ 的单调性，并给出 $R<1$ 严格最优的四条充分条件。与 `theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha` 的趋势通道 B 形成镜像。

---

## 2. 记号与前提

### 2.1 概率空间

$(\Omega,\mathcal{F},\{\mathcal{F}_t\},\mathbb{P})$，$W_t$ 标准 Wiener 过程。

### 2.2 价格过程（均值回归原型）

对数价格 $X_t=\ln(S_t/S_0)$ 服从 Ornstein–Uhlenbeck：

$$dX_t=-\kappa X_t\,dt+\sigma\,dW_t,\qquad X_0=0,\qquad \kappa\ge0,\ \sigma>0.$$

- $\kappa=0$ 退化为零漂移 BM（鞅，Doob 保守律适用）；
- $\kappa>0$ 时均衡为 0，位移 $X_t$ 被 $-\kappa X_t$ 拉回，$\mathbb{E}[X_t]=X_0 e^{-\kappa t}$；
- 平稳方差 $\sigma^2/(2\kappa)$，均值回归半衰期 $\ln2/\kappa$。

### 2.3 入场于偏离处

**定义 2.3（回归入场）**：多头在价格低于均衡 $d$ 处入场，即入场点 $x_0=-d$（$d>0$）；空头为镜像 $x_0=+d$。$d$ 称为**入场偏离**。

> 这是与趋势通道的关键几何差异：趋势通道 B 入场于中心 $x_0=0$、靠过程逃离到尾部获利；本主题入场于偏离处、靠过程回到中心获利。

### 2.4 双 barrier 容器（$R<1$ 朝向）

以多头为坐标（空头镜像）：

$$K_T>0\text{（止盈距离，指向均衡 0）},\qquad K_S>0\text{（止损距离，背离均衡）},\qquad T\in(0,\infty]\text{（时间上限）}.$$

止盈位于 $0$（相对入场的距离 $K_T=d$，即取 $d=K_T$），止损位于 $-(K_T+K_S)$。定义

$$\boxed{\,R:=\frac{K_T}{K_S}\,}$$

$R<1$ 即"止盈近、止损远"——低盈亏比 / 高胜率朝向。容器宽度 $L:=K_T+K_S$。

### 2.5 首达停时与事件

$$\tau:=\inf\{t\ge0:X_t\notin(-(K_T+K_S),\,0)\}\wedge T,$$

$$A_{\text{win}}=\{\tau<T,X_\tau=0\},\quad A_{\text{loss}}=\{\tau<T,X_\tau=-(K_T+K_S)\},\quad A_{\text{time}}=\{\tau=T\}.$$

### 2.6 单笔收益

单边成本 $c\ge0$（ATR 计）：

$$E_{\text{gross}}:=\mathbb{E}[X_\tau-x_0],\qquad E_{\text{net}}:=E_{\text{gross}}-2c.$$

以入场点为基准，赢 $+K_T$、亏 $-K_S$、时间退出取终端价。

### 2.7 量纲表

| 符号 | 含义 | 量纲 |
|---|---|---|
| $X_t$ | 对数价格 | ATR |
| $\kappa$ | 回归速率 | $\text{time}^{-1}$ |
| $\sigma$ | 波动率 | $\text{time}^{-1/2}$ |
| $K_S,K_T,L$ | 距离 | ATR |
| $R=K_T/K_S$ | 盈亏比 | 无量纲 |
| $T,\tau$ | 时间 | bar 或小时 |
| $c$ | 单边成本 | ATR |
| $\kappa/\sigma^2$ | 回归强度（规范不变量） | $\text{ATR}^{-2}$ |

---

## 3. 零回归基线（Doob 保守律）

**命题 3.1（$\kappa=0$ 下 $R<1$ 必亏）**：当 $\kappa=0$（零漂移 BM），对任意 $K_S,K_T,T$ 与任意 $\mathcal{F}_t$-adapted 出场停时，

$$E_{\text{gross}}\big|_{\kappa=0}=0,\qquad E_{\text{net}}=-2c<0.$$

**证明**：$X_t=\sigma W_t$ 是鞅，$\tau\le T<\infty$ 一致有界，Doob OST 给出 $\mathbb{E}[X_\tau]=X_0$。以入场点为基准 $\mathbb{E}[X_\tau-x_0]=0$。扣双边成本即得。$\blacksquare$

**含义**：低盈亏比 / 高胜率策略**必须**以真实均值回归型条件漂移为前提。这是 KF-1 的数学根据，也与 `theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha` 推论 5.2 一致。

---

## 4. OU 首达胜率（闭式）

### 4.1 胜率 ODE

**命题 4.1（OU 首达胜率）**：设 $T=\infty$，从 $x\in(-(K_T+K_S),0)$ 出发首达 0（赢）的概率 $p(x)$ 满足

$$\frac{\sigma^2}{2}p''(x)-\kappa x\,p'(x)=0,\qquad p(-(K_T+K_S))=0,\quad p(0)=1.$$

**解**：

$$\boxed{\,p(x)=\frac{\displaystyle\int_{-(K_T+K_S)}^{x}\exp\!\left(\frac{\kappa u^2}{\sigma^2}\right)du} {\displaystyle\int_{-(K_T+K_S)}^{0}\exp\!\left(\frac{\kappa u^2}{\sigma^2}\right)du}\,}$$

用虚误差函数表示：$\int e^{a u^2}du=\frac{\sqrt{\pi}}{2\sqrt{a}}\operatorname{erfi}(\sqrt{a}\,u)$，故

$$p(x)=\frac{\operatorname{erfi}\!\big(\sqrt{\kappa/\sigma^2}\,x\big)-\operatorname{erfi}\!\big(-\sqrt{\kappa/\sigma^2}(K_T+K_S)\big)} {\operatorname{erfi}(0)-\operatorname{erfi}\!\big(-\sqrt{\kappa/\sigma^2}(K_T+K_S)\big)}.$$

**证明**：生成元 $\mathcal{L}p=\tfrac{\sigma^2}{2}p''-\kappa x p'=0$（边界吸收，调和函数）；一阶 ODE 令 $q=p'$ 得 $q'/q=(2\kappa/\sigma^2)x$，积分即得。$\blacksquare$

### 4.2 入场点胜率

取入场点 $x=-K_T$：

$$p_{\text{win}}:=p(-K_T)=\frac{\displaystyle\int_{-(K_T+K_S)}^{-K_T}\exp\!\left(\frac{\kappa u^2}{\sigma^2}\right)du} {\displaystyle\int_{-(K_T+K_S)}^{0}\exp\!\left(\frac{\kappa u^2}{\sigma^2}\right)du}.$$

---

## 5. 小回归强度展开

**定理 5.1（小 κ 胜率与期望）**：对 $\kappa/\sigma^2$ 小，

$$\boxed{\,p_{\text{win}}=\frac{K_S}{K_T+K_S}+\frac{\kappa}{\sigma^2}\frac{K_TK_S(2K_T+K_S)}{3(K_T+K_S)}+O(\kappa^2)\,}$$

$$\boxed{\,E_{\text{gross}}=\frac{\kappa}{\sigma^2}\frac{K_TK_S(2K_T+K_S)}{3}+O(\kappa^2)\,}$$

**证明**：把 $e^{\kappa u^2/\sigma^2}=1+\frac{\kappa}{\sigma^2}u^2+O(\kappa^2)$ 代入命题 4.1 的积分比。记 $a=K_T+K_S$：

分子 $\int_{-a}^{-K_T}(1+\frac{\kappa}{\sigma^2}u^2)du=K_S+\frac{\kappa}{\sigma^2}\frac{a^3-K_T^3}{3}$，
分母 $\int_{-a}^{0}(1+\frac{\kappa}{\sigma^2}u^2)du=a+\frac{\kappa}{\sigma^2}\frac{a^3}{3}$。

展开比值并用 $a-K_T=K_S$、$a^3-K_T^3=K_S(a^2+aK_T+K_T^2)=K_S((K_T+K_S)^2+(K_T+K_S)K_T+K_T^2)=K_S(3K_T^2+3K_TK_S+K_S^2)$。又 $p_0=K_S/a$，胜率增量

$$\delta p=\frac{1}{a}\frac{\kappa}{\sigma^2}\frac{a^3-K_T^3}{3}-\frac{K_S}{a}\frac{1}{a}\frac{\kappa}{\sigma^2}\frac{a^3}{3} =\frac{\kappa}{\sigma^2}\frac{(a^3-K_T^3)-K_Sa^2}{3a}.$$

化简 $(a^3-K_T^3)-K_Sa^2=a^3-(a-K_S)^3-K_Sa^2=3aK_SK_T-K_S^3-K_Sa^2$，代入 $a=K_T+K_S$ 得 $K_TK_S(2K_T+K_S)$。故 $\delta p=\frac{\kappa}{\sigma^2}\frac{K_TK_S(2K_T+K_S)}{3a}$。

$E_{\text{gross}}=p_{\text{win}}K_T-(1-p_{\text{win}})K_S=(K_T+K_S)(p_{\text{win}}-K_S/a)=(K_T+K_S)\delta p=\frac{\kappa}{\sigma^2}\frac{K_TK_S(2K_T+K_S)}{3}$。$\blacksquare$

### 5.1 与趋势通道 B 的对偶

| 维度 | 趋势通道 B（`when-barrier-shaping` §11） | 本主题（均值回归通道） |
|---|---|---|
| 过程 | 未知符号常数漂移（持续 / 逃离中心） | OU（指向均衡 / 回到中心） |
| 入场点 | 中心 $x_0=0$ | 偏离处 $x_0=-K_T$ |
| 小强度展开 | $E\sim\tfrac{x^2}{3}K_S^3R(R-1)$ | $E\sim\tfrac{\kappa}{\sigma^2}\tfrac{K_TK_S(2K_T+K_S)}{3}$ |
| 正期望需要 | $R>1$ | 任意 $R>0$（$\kappa>0$ 即可） |
| 最优朝向 | 止盈远、止损近 | 止盈近、止损远（强 κ 下） |

**关键差异**：趋势通道的 $R(R-1)$ 因子在 $R<1$ 时翻负，所以趋势下 $R<1$ 是错的；回归通道不含此因子，正期望对所有 $R$ 成立，$R$ 的选择由风险调整 / 频率 / 成本目标决定，强 κ 下落到 $R<1$。

---

## 6. 平均持仓时间

**命题 6.1（平均首达时间）**：$m(x)=\mathbb{E}_x[\tau]$ 满足

$$\frac{\sigma^2}{2}m''(x)-\kappa x\,m'(x)=-1,\qquad m(-(K_T+K_S))=m(0)=0.$$

强回归（$\kappa$ 大）时 $m(-K_T)\approx K_T/(\kappa K_T)=1/\kappa$ 量级（回到均衡的时间），$R$ 越小（$K_T$ 越小）持仓越短。这是 $R<1$ 在"按时间计成本 / 高频"目标下占优的机制。闭式可用 $\operatorname{erfi}$ / Dawson 积分表示，数值用三对角 ODE 求解。

---

## 7. 最优盈亏比与 $R<1$ 的充分条件

### 7.1 最优 $R^\ast$ 随 κ 单调下降（数值定律）

**命题 7.1（$R^\ast$ 单调性，数值已证 / 解析待补）**：固定容器宽度 $L=K_T+K_S$、固定 $\sigma$，在年化 Sharpe 目标

$$\mathrm{Sharpe}_{\text{年}}=\frac{E_{\text{net}}}{\sigma_{\text{trade}}\sqrt{\mathbb{E}[\tau]}}$$

下，最优 $R^\ast(\kappa)$ 随回归强度 $\kappa$ 单调下降。存在交叉点 $\kappa_c$ 使 $R^\ast(\kappa_c)=1$；$\kappa>\kappa_c$ 时 $R^\ast<1$（低盈亏比 / 高胜率最优）。

**数值锚点（$L=2,\sigma=1,T=\infty$，ODE 求解）**：

| $\kappa$ | 0.10 | 0.25 | 0.50 | 1.00 | 1.50 | 2.00 | ≥3.0 |
|---|---|---|---|---|---|---|---|
| $R^\ast_{\text{年Sh}}$ | 4.00 | 3.90 | 1.10 | 0.42 | 0.30 | 0.25 | 0.15–0.47 |
| $p_{\text{win}}$ | 24% | 32% | 73% | 96% | 99% | 99.9% | ~100% |

交叉点 $\kappa_c\approx0.7\text{–}1.0$（该数值依赖 $L,\sigma$ 归一化，真实数据需重新校准）。

> **未闭合**：解析单调性证明待补（可对 $\kappa$ 隐式求导，或用强 κ 渐近 $p_{\text{win}}\to1$ 直接论证 $R^\ast\to0$）。当前以数值定律形式入库，标记为 KF-3。

### 7.2 $R<1$ 严格最优的四条充分条件

**定理 7.2**：在均值回归设定（§2）下，以下任一条件成立时，风险调整目标的最优点满足 $R^\ast<1$：

1. **强均值回归**：$\kappa/\sigma^2$ 足够大（年化 Sharpe 口径下数值临界 $\kappa\gtrsim\kappa_c$），使得 $p_{\text{win}}\to1$，此时加大 $K_T$（提高 $R$）只增加持仓时间与反向漂移风险而几乎不提高胜率；
2. **按时间计持有成本**：存在成本率 $c_t>0$，净收益 $E_{\text{net}}=E_{\text{gross}}-2c-c_t\mathbb{E}[\tau]$。因 $\partial\mathbb{E}[\tau]/\partial K_T>0$，时间成本惩罚大 $K_T$，把 $R^\ast$ 压低至 1 以下；
3. **下行风险敏感目标**：目标为下行偏差调整收益（如 Sortino / 回撤惩罚）。$R<1$ 在强 κ 下使 $P_{\text{loss}}<1\%$，损失尾被压缩，下行调整收益在 $R<1$ 达峰；
4. **结构性紧止损约束**：$K_S$ 被流动性 / 跳空下限钉在某 $K_S^{\min}$（无法放宽止损），而近止盈 $K_T<K_S^{\min}$ 是唯一可调方向，可行域本身落在 $R<1$。

**证明思路**：(1) 强 κ 渐近 $p\to1$，$E_{\text{gross}}\to K_T$、$\sigma_{\text{trade}}\to0$ 但 $\mathbb{E}[\tau]\propto K_T$，年化 Sharpe $\sim K_T/(\sigma_{\text{trade}}\sqrt{K_T})\propto\sqrt{K_T}$ 看似随 $K_T$ 增——但需计入 $p<1$ 的损失尾与时间成本，数值上 $R^\ast\to0$；严格渐近见附录待补。(2) $\partial E_{\text{net}}/\partial K_T$ 含 $-c_t\partial\mathbb{E}[\tau]/\partial K_T<0$，FOC 左移。(3)(4) 由目标 / 可行域定义直接得。$\blacksquare$

**反例边界**：在"固定 $L$ + 单笔 Sharpe + 弱 $\kappa$（$\kappa<\kappa_c$）+ 仅每笔固定成本"下，最优在 $R\approx1.1\text{–}1.7$（数值 $\kappa=0.5$ 时 $R^\ast_{\text{笔}}=1.30$），**不是 $R<1$**。故 $R<1$ 最优不是无条件结论。

---

## 8. 净期望与成本现实化

$$E_{\text{net}}=p_{\text{win}}K_T-(1-p_{\text{win}})K_S-2c-c_t\mathbb{E}[\tau].$$

- 每笔成本 $2c$ 用**每合约真实成本**（佣金 + 滑点，随合约 / 波动率变），禁用扁平 0.05 ATR（继承方法护栏；`quant-research-methodology` §5.1）；
- $R<1$ 单笔毛利小、频率高，$E_{\text{net}}>0$ 对 $c$ 极敏感，阶段 1 必须报告成本前后对照；
- 时间退出比例 $P(\tau=T)$ 必须报告——高胜率若靠无限等待（$T\to\infty$）做出则无效（KF-6）。

---

## 9. 关键结论汇总（Boxed）

$$\boxed{\,dX_t=-\kappa X_t\,dt+\sigma\,dW_t,\quad x_0=-K_T,\quad R=K_T/K_S\,}$$

$$\boxed{\,\kappa=0\Rightarrow E_{\text{gross}}=0,\ E_{\text{net}}=-2c<0\quad(\text{Doob 保守律})\,}$$

$$\boxed{\,p(x)=\frac{\int_{-(K_T+K_S)}^{x}e^{\kappa u^2/\sigma^2}\,du}{\int_{-(K_T+K_S)}^{0}e^{\kappa u^2/\sigma^2}\,du}\,}$$

$$\boxed{\,p_{\text{win}}=\frac{K_S}{K_T+K_S}+\frac{\kappa}{\sigma^2}\frac{K_TK_S(2K_T+K_S)}{3(K_T+K_S)}+O(\kappa^2)\,}$$

$$\boxed{\,E_{\text{gross}}=\frac{\kappa}{\sigma^2}\frac{K_TK_S(2K_T+K_S)}{3}+O(\kappa^2)\,}$$

$$\boxed{\,R^\ast(\kappa)\text{ 随 }\kappa\text{ 单调下降；}\kappa>\kappa_c\Rightarrow R^\ast<1\,}$$

---

## 附录 A · 静态一致性检查（初稿自评）

| 类别 | 结论 |
|---|---|
| 符号一致性 | $\kappa,\sigma,X_t,K_S,K_T,L,R,T,\tau,c,p_{\text{win}},E_{\text{gross}},E_{\text{net}}$ 全文一致，定义前均引入 |
| 量纲 | §2.7 已列；$\kappa/\sigma^2$ 为 $\text{ATR}^{-2}$，与 $K_TK_S(2K_T+K_S)$（$\text{ATR}^3$）相乘得 ATR，量纲正确 |
| 命题/证明配对 | 命题 3.1 / 4.1 / 6.1，定理 5.1 / 7.2 均附证明或证明思路 |
| 极限一致性 | $\kappa\to0$ 时 $p_{\text{win}}\to K_S/(K_T+K_S)$，与 BM 首达 $K_S/L$ 一致；$E_{\text{gross}}\to0$ 与 Doob 一致 |
| 已知未闭合 | 命题 7.1 解析单调性、强 κ 渐近、有限 $T$ Fourier/谱展开解（当前用 $T=\infty$） |
| KaTeX | 块级公式无尾部标点；$R^\ast$ 用 `\ast` |

**未闭合项不阻塞阶段 1 实验**，但提炼 theorem 前需补齐命题 7.1 解析证明与有限 $T$ 解。

## 附录 B · 与 structural-shaping-alpha 的接口

- 复用：Doob OST、首达记号、$R=K_T/K_S$、成本 $2c$、通道 A（方向 alpha）；
- 差异：过程从 GBM 常数漂移推广到 OU 均值回归；入场点从中心改为偏离处；最优朝向从 $R>1$ 镜像为 $R<1$；
- 命名引用：`theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha`、`theorem:structural-shaping-alpha#winrate-payoff-tradeoff-under-frictions`。
