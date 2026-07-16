# 强度识别因子筛选方法

> 类型：Research / 方法说明
> 状态：v0.1 · 2026-07-16
> 上游：shaping-theory.md §2.22（KF-26）· §2.23（KF-27）· §2.23.5 · §2.23.6

## 一、这份文档要回答什么

上游 [shaping-theory](../structural-shaping-alpha/shaping-theory.md) 已经证明：
在 DirRandom 前提下、只要事前能识别 `|ν|/σ` 的强段、配合非对称塑形（RR≥2），
就能兑现一条独立于方向 alpha 的正期望通道。

**证明**：

设对数价格 $X_t$ 遵循带漂移的 Brownian motion：

$$
dX_t \;=\; \nu\,dt + \sigma\,dW_t,\qquad X_0 = 0
$$

其中 $\nu = \mu - \sigma^{2}/2$ 是 Itô 修正后的对数漂移，$\sigma$ 是波动率。
入场后设置对称化的双 barrier：下界 $-K_S$（止损）、上界 $+K_T$（止盈），
盈亏比 $R = K_T/K_S \ge 1$。定义无量纲漂移比：

$$
\lambda \;=\; \frac{2\nu}{\sigma^{2}}
$$

首达止盈的概率（$T = \infty$，$\lambda \ne 0$）有精确解析解：

$$
P_{\text{win}}(\lambda; K_S, K_T)
\;=\; \frac{e^{\lambda K_T}\bigl(1 - e^{-\lambda K_S}\bigr)}{e^{\lambda K_T} - e^{-\lambda K_S}}
$$

**关键：DirRandom 下的方向乘法**。设入场方向 $d \in \{+1, -1\}$ 各以 $1/2$ 概率取值、
且 $d$ 与 $\mathrm{sign}(\nu)$ 独立。多头视角下的等效漂移是 $d \cdot \nu$，
故 $d \cdot \mathrm{sign}(\nu)$ 也是 $\pm 1$ 各 $1/2$，等价于有效 $\lambda$ 服从：

$$
\lambda_{\text{mix}} \;=\;
\begin{cases}
+2\,|\nu|/\sigma^{2}, & \text{概率 } 1/2 \\
-2\,|\nu|/\sigma^{2}, & \text{概率 } 1/2
\end{cases}
$$

**注意**：策略只需要知道 $|\nu|/\sigma$（强度），完全不需要知道 $\mathrm{sign}(\nu)$（方向）。
方向筛选是通道 A 的活；这里的证明只用到 $|\nu|/\sigma$。

记 $\lambda_0 = 2|\nu|/\sigma^{2}$，混合胜率与毛期望：

$$
P_{\text{win}}^{\text{mix}}
\;=\; \tfrac{1}{2}\bigl[P_{\text{win}}(+\lambda_0) + P_{\text{win}}(-\lambda_0)\bigr]
$$

$$
E_{\text{gross}}^{\text{mix}}
\;=\; K_T \cdot P_{\text{win}}^{\text{mix}} - K_S \cdot \bigl(1 - P_{\text{win}}^{\text{mix}}\bigr)
\;=\; \tfrac{K_T + K_S}{2}\bigl[P_{\text{win}}(+\lambda_0) + P_{\text{win}}(-\lambda_0)\bigr] - K_S
$$

**声明**：$|\nu|/\sigma > 0$ 且 $R > 1$ 时，$E_{\text{gross}}^{\text{mix}} > 0$。

**验证**：对 $P_{\text{win}}$ 关于 $\lambda$ 在 $\lambda = 0$ 附近做 Taylor 展开
（记 $u = \lambda K_T$、$v = -\lambda K_S$）：

$$
P_{\text{win}}(\lambda)
\;=\; \frac{K_S}{K_S + K_T}
      \;+\; \frac{K_S K_T (K_T - K_S)}{2(K_S + K_T)^{2}}\,\lambda
      \;+\; O(\lambda^{2})
$$

对 $\pm \lambda_0$ 求和，**奇数阶项完全对消**，只剩偶数阶：

$$
P_{\text{win}}(+\lambda_0) + P_{\text{win}}(-\lambda_0)
\;=\; \frac{2K_S}{K_S + K_T}
      \;+\; \frac{K_S K_T (K_T - K_S)}{6(K_S + K_T)}\,\lambda_0^{2}
      \;+\; O(\lambda_0^{4})
$$

代回 $E_{\text{gross}}^{\text{mix}}$，注意 $\frac{K_T + K_S}{2} \cdot \frac{2 K_S}{K_S + K_T} = K_S$，
一阶项化简得：

$$
\boxed{\,E_{\text{gross}}^{\text{mix}}(x)
\;\approx\; \frac{x^{2}\,K_S^{3}\,R\,(R-1)}{3}\,},
\qquad x \;=\; \frac{|\nu|}{\sigma},\;\; R = \frac{K_T}{K_S}
$$

**QED 三条推论**：

1. $R = 1$ 时 $R(R-1) = 0$，$E_{\text{gross}}^{\text{mix}} \equiv 0$——这是 Doob 保守律的严格数学映射；
2. $R > 1$ 且 $x > 0$ 时 $E_{\text{gross}}^{\text{mix}} > 0$——**非对称塑形 + 强段识别足以产生正期望毛收益**；
3. 扣除双边成本 $2c$ 后盈亏平衡的最低强度：

   $$
   x_{\min} \;=\; \sqrt{\frac{6c}{K_S^{3}\,R\,(R-1)}}
   $$

   任何识别器输出的样本平均真实 $|\nu|/\sigma$ 若持续低于 $x_{\min}$，
   下游塑形容器就吸收不了成本，通道 B 落空。

上述推导完全没用到 $\mathrm{sign}(\nu)$——**这就是通道 B 独立于方向 alpha 的数学根据**。

***

## 二、数学工具箱

本节把 [shaping-theory](../structural-shaping-alpha/shaping-theory.md) 里已经沉淀的、
在本主题筛选流程里会反复调用的**数学对象**集中列出。
每条给出"是什么 / 公式 / 在本主题何处用"三段式，方便后续 experiment-plan 或 implementation-notes 直接引用。

### 2.1 首达定理（FPT）无限时间精确解

**是什么**：给定入场后带漂移的 Brownian motion + 双 barrier $(-K_S, +K_T)$，
首触上界（止盈）的概率。

**公式**（$T = \infty$，$\lambda \ne 0$）：

$$
P_{\text{win}}(\lambda; K_S, K_T)
\;=\; \frac{e^{\lambda K_T}\bigl(1 - e^{-\lambda K_S}\bigr)}{e^{\lambda K_T} - e^{-\lambda K_S}},
\qquad \lambda \;=\; \frac{2\nu}{\sigma^{2}}
$$

**零漂移恒等式**（$\lambda = 0$）：

$$
P_{\text{win}}\bigl|_{\lambda=0}
\;=\; \frac{K_S}{K_S + K_T}
\;=\; \frac{1}{1 + R},\qquad R = K_T / K_S
$$

**极限性质**：

- $K_T \to \infty$，$\lambda \le 0$：$P_{\text{win}} \to 0$
- $K_T \to 0$：$P_{\text{win}} \to 1$
- $\sigma \to 0$，$\mu > 0$：$P_{\text{win}} \to 1$

**在本主题何处用**：证明块（第一节）的核心；混合期望展开的分子；
$se_{\text{target}}$ 反演的 Taylor 系数。

**出处**：shaping-theory §1.3.1 · §1.4。

### 2.2 平均首达时间 $E[\tau_{\text{FPT}}]$

**是什么**：从入场到首次触达任一 barrier 的平均耗时（零漂移下）。

**公式**（$\lambda = 0$）：

$$
E[\tau_{\text{FPT}}]
\;=\; \frac{K_S \cdot K_T}{\sigma_{\text{bar}}^{2}}
$$

其中 $\sigma_{\text{bar}}$ 是每 bar 波动率（1h 周期取 1.0，5m 取 $1/\sqrt{12}$）。

**在本主题何处用**：Gate 2 覆盖率计算。给定 KF-27 反解的 $(\tau^\ast, K_S^\ast, K_T^\ast)$，
年化入场次数 $N_{\text{year}}^\ast = \tau^\ast \cdot T_{\text{year\_hours}} / E[\tau_{\text{FPT}}]$。
玉米 1h：$E[\tau_{\text{FPT}}] = 3 \cdot 9 / 1 = 27\,\text{h}$，$N_{\text{year}}^\ast \approx 0.647 \cdot 1625 / 27 \approx 39\,\text{笔}$
（与 shaping-theory §2.23.2 的 $N/\text{年}=39$ 完全对齐；文档正文 210 笔口径是"3 合约合并 × 5-6× 加权"，本主题以裸口径为准）。

**出处**：shaping-theory §1.5 · §4.3。

### 2.3 Fourier 有限时间精确解 $P_{\text{win}}(T)$ 与 $P(\tau > T)$

**是什么**：$T = \infty$ FPT 公式忽略了"$T$ 内触达不到 barrier → time-exit"的可能。
Fourier spectral 分解给出**任意有限 $T$ 下**的精确解。

**公式**（零漂移，$L = K_S + K_T$）：

$$
P_{\text{win}}(T)
\;=\; \frac{2}{\pi} \sum_{n=1}^{\infty}
      \frac{(-1)^{n+1}}{n}\,\sin\!\Bigl(\frac{n\pi K_S}{L}\Bigr)
      \Bigl(1 - e^{-n^{2}\pi^{2}\sigma^{2}T / (2L^{2})}\Bigr)
$$

$$
P(\tau > T)
\;=\; \frac{4}{\pi} \sum_{n\text{ odd}}
      \frac{\sin(n\pi K_S / L)}{n}\,
      e^{-n^{2}\pi^{2}\sigma^{2}T / (2L^{2})}
$$

**收敛性**：$e^{-n^{2}}$ 项收敛极快，截断到 $n = 100$ 精度 $10^{-10}$。

**极限**：$T \to \infty$ 时 $P_{\text{win}}(T) \to K_S/L$，与 §2.1 无限时间解一致。

**在本主题何处用**：
1. 当因子候选的 barrier 触达时间可能超出 $T$（$T/T^\ast < 1$ 深长期区）时，
   本主题用 Fourier null 替代 $T = \infty$ null，避免"time-exit 挤压 $P_{\text{win}}$"的偏差；
2. Gate 3 的真值 $x_t^{\text{真}}(W)$ 可用 Fourier 反演更精确（未来 v2）。

**参考实现**：`theme:structural-shaping-alpha/raw-scripts/fourier_finite_time_test.py`。

**出处**：shaping-theory §2.13.2 · KF-17。

### 2.4 Doob 停时定理（OST）

**是什么**：若 $\{X_t\}$ 是鞅、$\tau$ 是可选停时（$\{τ \le t\} \in \mathcal{F}_t$），
则 $E[X_\tau] = X_0$。

**推论**：λ=0（$\nu = 0$，$X_t$ 是鞅）下：

$$
E[X_\tau] = 0
\;\Longrightarrow\;
E[\text{gross}]\bigl|_{\lambda=0}
\;=\; K_T \cdot P_{\text{win}} - K_S \cdot (1 - P_{\text{win}})
\;\equiv\; 0
$$

**两个前提**：
- **(P1) 鞅性**：$E[X_{t+dt} \mid \mathcal{F}_t] = X_t$
- **(P2) 停时可测性**：$\tau$ 关于 $\mathcal{F}_t$ 是可测停时

**打破 OST 的两种方式**（对应两条 alpha 通道）：

| 打破的前提 | 手段 | 通道 |
|---|---|---|
| P1（鞅性）| 方向筛选让底层过程在条件测度下带漂移 | 通道 A（KF-19）|
| P2（可测性）| 强段筛选让 $\tau$ 依赖入场时 $|\nu|/\sigma$ 的信息 | 通道 B（KF-26）· **本主题** |

**在本主题何处用**：解释"为什么 DirRandom 下 $R > 1$ 塑形能产生正期望"——
入场判据（$\hat{x}_t \ge \theta_{\text{thresh}}$）让 $\tau$ 不再是无条件 filtration adapted 停时，
OST 前提 P2 失效，$E[X_\tau] \ne 0$ 成为可能。

**出处**：shaping-theory §2.21.4（补充说明段）。

### 2.5 Itô 修正与无量纲漂移比 $\lambda$

**是什么**：对数价格空间的漂移是 $\nu = \mu - \sigma^{2}/2$，不是 $\mu$；
首达概率由无量纲比 $\lambda = 2\nu/\sigma^{2}$ 决定。

**决策阈值**：

| $\lvert \nu/\sigma \rvert$ | 归因 |
|---|---|
| $< 0.02$ | martingale，GBM 无漂移完美对齐 |
| $< 0.10$ | 接近 martingale，微弱漂移或非 GBM 溢价 |
| $\ge 0.10$ | 显著隐含正/负漂移 |

**在本主题何处用**：
1. 本主题的目标量 $x_t = |\nu_t|/\sigma_t$ 就是 $\lambda_t$ 绝对值的一半（除以 $\sigma^{-1}$）；
2. 任何因子候选的输出 $\hat{x}_t$ 必须落到 $[0, +\infty)$ 且尊重 $\nu$ 的 Itô 修正；
3. 归因时**严禁用 $\mu$ 判**"漂移强弱"——Itô 凸性会让 $\mu = 0$ 时 $\nu = -\sigma^{2}/2 < 0$。

**出处**：shaping-theory §1.2 · KF-9。

### 2.6 KF-26 混合期望公式（DirRandom + 强段公理）

**是什么**：DirRandom 下 $\lambda$ 以 $1/2$ 概率取 $\pm 2|\nu|/\sigma^{2}$，
混合期望是两侧胜率的加权。

**公式**（等价的两种写法）：

$$
E_{\text{gross}}^{\text{mix}}
\;=\; \tfrac{K_T + K_S}{2}\bigl[P_{\text{win}}(+\lambda_0) + P_{\text{win}}(-\lambda_0)\bigr] - K_S
$$

$$
E_{\text{gross}}^{\text{mix}}(x)
\;\approx\; \frac{x^{2}\,K_S^{3}\,R\,(R-1)}{3}
\qquad(\text{小 }\lambda\text{ 展开})
$$

**在本主题何处用**：证明块的核心（第一节已展开）；
下游子实验估算某 $\hat{x}$ 分布下的期望毛收益时直接调用。

**出处**：shaping-theory §2.22.2 · §2.23.6.2。

### 2.7 $x_{\min}$ 与 $se_{\text{target}}$（本主题两大 KPI）

**是什么**：把 §2.6 结果与"识别器估计误差"结合，得到本主题的两条硬 KPI。

**盈亏平衡下限**：

$$
x_{\min} \;=\; \sqrt{\frac{6c}{K_S^{3}\,R\,(R-1)}}
$$

**95% 单侧置信不等式**：

$$
\hat{x} \;\ge\; x_{\min} + z_{0.95} \cdot se(f),\qquad z_{0.95} = 1.645
$$

**对偶反解**（本主题核心 KPI）：

$$
\boxed{
se_{\text{target}}
\;=\; \frac{x^{\ast} - x_{\min}}{1.645},
\qquad x^{\ast} = Q_D(1 - \tau^{\ast})
}
$$

**数值参考**（玉米 1h · $c=0.077$, $K_S^\ast=3$, $R^\ast=3$, $x^\ast=0.131$）：

- $x_{\min} \approx 0.053$
- $se_{\text{target}} \approx 0.047$（对齐上游"$se \le 0.05$ 红线"）

**在本主题何处用**：Gate 1 判据的阈值；候选因子迭代的"距可行还差多少"度量。

**出处**：shaping-theory §2.23.5 · §2.23.6.3 · §2.23.6.4。

### 2.8 双通道漂移探测器

**是什么**：判断某段样本是否真的带漂移，可以从**两个独立信号**验证。

**通道 A（$P_{\text{win}}$ 通道）**：

$$
z_A \;=\; \frac{P_{\text{win}}^{\text{obs}} - P_{\text{win}}^{\text{Fourier}}}{\text{SE}(P_{\text{win}}^{\text{obs}})}
$$

**通道 B（time-exit 通道）**：

$$
z_B \;=\; \frac{P_{\text{time\_exit}}^{\text{obs}} - P(\tau > T)_{\text{Fourier}}}{\text{SE}(P_{\text{time\_exit}}^{\text{obs}})}
$$

**判据组合**（真实漂移证据）：

- $(z_A > 2 \wedge z_B < -2)$：双通道方向一致
- $(z_A > 2 \wedge z_B\_\text{valid} = \text{False})$：$P(\tau > T)_{\text{theory}} < 10^{-3}$ 时通道 B 数值不稳定，
  仅用通道 A

**数值精度警告**：$P(\tau > T)_{\text{Fourier}} < 10^{-3}$ 的格点 $z_B$ 会爆炸（观察到 $z_B = +2367$），
下游过滤该阈值。

**在本主题何处用**：识别器候选的 fire 事件事后审计——若 fire 集合上 $z_A$ 与 $z_B$ 都不显著，
即使 Gate 1-3 通过，也应存疑（可能是评估集抽样偏差）。

**出处**：shaping-theory §2.13.6 · §2.16 · KF-17 · KF-18。

### 2.9 Hurst 指数 R/S 分析

**是什么**：衡量时间序列"趋势凝聚 vs 均值回归"的度量。

**方法**：对 20 合约 × 多周期做 rescaled range 分析：

- $H > 0.5$：趋势凝聚（超随机漫步的持续性）
- $H = 0.5$：纯随机漫步
- $H < 0.5$：均值回归

**shaping-theory 实测结果**：

| 周期 | mean H | H > 0.55 合约比例 |
|---|---|---|
| 5m | 0.542 | 40% |
| 15m | 0.558 | 65% |
| **1h** | **0.603** | **95%** |

**在本主题何处用**：Hurst 本身可以作为**候选强度识别因子**——上游 §2.22.7 列出的
"波动率制度切换"识别器一类里，Hurst 是最直接的候选之一。
参考实现：`theme:structural-shaping-alpha/raw-scripts/hurst_stratifier.py`。

**出处**：shaping-theory §2.12.4 · KF-16。

### 2.10 Cluster Bootstrap（事件非独立性处理）

**是什么**：barrier 触达事件按 (symbol, contract) 内部强相关（同合约相邻 bar 触达路径共享噪声），
不能用普通 IID bootstrap 估 CI。

**方法**：

1. 定义 cluster 单位 = `(symbol, contract)`
2. 每次 bootstrap 抽样以 cluster 为单位（有放回），而非按单 bar 抽
3. 在抽样后的 cluster 集合上重算统计量（$se$、$P_{\text{win}}$、$r_{\text{hat}}$、$\nu/\sigma$）
4. 重复 $B_{\text{boot}} = 5000$ 次，取 percentile CI

**默认参数**：$B_{\text{boot}} = 5000$，cluster 单位 `(symbol, contract)`。

**在本主题何处用**：Gate 1 严格版判据 $\text{CI}_{97.5}(se) \le se_{\text{target}}$；
Gate 3 判据 $\text{CI}_{2.5}(r) > 0$；所有下游子实验的显著性检验默认口径。

**出处**：shaping-theory §2.6.3 · §2.11.3 · §2.19.1 · KF-22。

### 2.11 截断法泄漏检测

**是什么**：因子 $f$ 是否引用未来信息的**机械验证方法**。

**方法**：

1. 对任意时刻 $t$，同时算两组：
   - $A = f(H_{\le t})$：完整历史下的输出
   - $B = f(H'_{\le t})$：把 $t$ 之后的 bar 全部人工截断（或随机化）后重跑 $f$
2. 若 $A \ne B$（数值精度容忍外），则 $f$ 存在泄漏，reject
3. 遍历 $t$ 的抽样样本 $\ge 100$ 个，全部通过才 accept 因果性

**在本主题何处用**：Gate 0 的因果性判据（第一节筛选流程第 0 步）；
任何 $\hat{x}_t$ 输出前必须先过这一关。

**参考实现**：`archive:2026-07-13-va-asymmetry-leak-chain-consolidated/2026-07-13-va-asymmetry-future-info-leak/raw-scripts/verify_leak_by_truncation.py`。

**出处**：archive:2026-07-13-va-asymmetry-leak-chain-consolidated（va-asymmetry 家族全线证伪的方法论遗产）。

### 2.12 KF-27 参数优化器（分布输入闭式）

**是什么**：给定品种/周期上 $|\nu|/\sigma$ 的分布 $D(\mu_D, \sigma_D)$ + 市场参数，
反解最优塑形容器 $(K_S^\ast, K_T^\ast, \tau^\ast)$ 及配套 $x^\ast$、$N_{\text{year}}^\ast$。

**接口**：

```python
from kf26_parameter_optimizer import FoldedNormal, optimize_all

D = FoldedNormal(mu_D=0.198, sd_D=0.108); D.fit()
best = optimize_all(D, c_side=0.077, K_S_min=1.0, K_S_max=6.0,
                    K_T_max=12.0, sigma_bar=1.0, year_hours=1625,
                    objective="sharpe_year")
# best["detail"] 内含 K_S, K_T, tau, x_star, N_year, sharpe_year, ann_pct_r1 ...
```

**玉米 1h 参考输出**：$K_S^\ast=3.0$、$K_T^\ast=9.0$、$R^\ast=3$、$\tau^\ast$=前 65% 段、
Sharpe/年 +1.66、年化 +20.2%。

**在本主题何处用**：本主题**不重新优化塑形容器**——所有 $(K_S^\ast, K_T^\ast, \tau^\ast)$ 都调用此接口。
若上游优化器升级（引入 Fourier 修正 / 经验分布替代 FoldedNormal），本主题所有阈值自动跟随刷新。

**参考实现**：`theme:structural-shaping-alpha/raw-scripts/kf26_parameter_optimizer.py`。
分布输入源：`theme:structural-shaping-alpha/raw-scripts/corn_1h_strength_three_views.py`。

**出处**：shaping-theory §2.23 · KF-27。

***

## 三、可用工具列表

第二节的数学工具箱**已经完整落成代码**，作为一个独立业务域 `research/` 沉淀在
`workspace/research/`，供本主题及后续研究直接 `import` 使用。

**导入约定**（`workspace` 是 uv 项目源码根，所有子包用扁平命名）：

```python
from research import (
    # FPT
    p_win_infty, e_gross_infty, e_net_infty, e_tau_infty, t_star,
    # Fourier
    p_win_finiteT_fourier, p_tau_gt_T_fourier,
    # Channel B
    e_gross_mix, e_gross_mix_smallx, x_min_smallx,
    # 分布
    FoldedNormal,
    # KF-27 优化器
    KF27Params, KF27Result, optimize_kf27,
    # 三层 gate 筛选
    se_target, gate1_se_precision, gate2_coverage, gate3_rank_correlation,
    run_screening, Gate1Result, Gate2Result, Gate3Result, ScreeningResult,
    # 统计与验证
    cluster_bootstrap, hurst_rs, verify_causality_by_truncation,
)
```

### 3.1 完整工具矩阵

| 数学工具 | 对应代码模块 | 关键 API | 单元测试 |
|---|---|---|---|
| **§2.1** FPT 无限时间精确解 | `research.fpt` | `p_win_infty(lam, k_s, k_t)` `e_gross_infty(lam, k_s, k_t)` `e_net_infty(lam, k_s, k_t, c_side)` `e_tau_infty(lam, k_s, k_t, sigma, nu)` `t_star(k_s, k_t, sigma)` | `test_channel_b.py :: TestPWinInfty / TestEGrossInfty / TestETauInfty / TestTStar` |
| **§2.2** 平均首达时间 | `research.fpt` | `e_tau_infty(lam=0, k_s, k_t, sigma_bar)` = $K_S K_T / \sigma_{\text{bar}}^2$ | `TestETauInfty` |
| **§2.3** Fourier 有限时间 | `research.fourier` | `p_win_finiteT_fourier(k_s, k_t, sigma, t_horizon, n_terms=100)` `p_tau_gt_T_fourier(k_s, k_t, sigma, t_horizon, n_terms=100)` | `test_channel_b.py :: TestFourier` |
| **§2.4** Doob OST | 概念性 · 无独立函数 | 由 `e_gross_infty(lam=0) ≡ 0` 隐式保证 | `TestEGrossInfty::test_doob_identity` |
| **§2.5** Itô 修正与 $\lambda$ | 隐式在 `research.fpt` 里 | 调用方按 $\lambda = 2\nu/\sigma^2$ 传参 | — |
| **§2.6** KF-26 混合期望 | `research.channel_b` | `e_gross_mix(x, k_s, k_t, sigma_bar=1.0)` （精确版） `e_gross_mix_smallx(x, k_s, k_t)` （$O(x^2)$ 近似） | `TestChannelBMix` |
| **§2.7** $x_{\min}$ / $se_{\text{target}}$ | `research.channel_b` + `research.screening` | `x_min_smallx(c_side, k_s, k_t)` `se_target(x_star, x_min, z=1.645)` `se_target_from_params(c_side, k_s, k_t, x_star)` | `TestXMin` · `TestSeTarget` |
| **§2.8** 双通道漂移探测器 | 需组合调用 · 无独立函数 | 复合调用 `p_win_finiteT_fourier` + `p_tau_gt_T_fourier` + SE 归一 | — |
| **§2.9** Hurst R/S 分析 | `research.hurst` | `hurst_rs(series, min_window=8, max_window=None)` | `test_validation_tools.py :: TestHurst` |
| **§2.10** Cluster Bootstrap | `research.bootstrap` | `cluster_bootstrap(events, cluster_key, statistic, n_boot=5000, seed=None)` → `BootstrapResult` | `TestClusterBootstrap` |
| **§2.11** 截断法泄漏检测 | `research.causality` | `verify_causality_by_truncation(factor, history, sample_indices, tolerance=1e-9)` → `CausalityResult` | `TestCausality` |
| **§2.12** KF-27 参数优化器 | `research.optimizer` + `research.distribution` | `FoldedNormal(mu_D, sd_D).fit()` `KF27Params(...)` `optimize_kf27(params, objective="sharpe_year")` → `KF27Result` | `test_distribution_optimizer.py :: TestFoldedNormal / TestKF27Optimizer` |
| **筛选流程** 完整三层 gate | `research.screening` | `run_screening(x_hat, x_truth, x_min, x_star, n_bars_total, year_bars, n_year_star)` → `ScreeningResult` `gate1_se_precision`, `gate2_coverage`, `gate3_rank_correlation` 三个独立门 | `test_screening.py :: 全部` |

### 3.2 典型调用链

**场景 A：给定品种 $|\nu|/\sigma$ 分布 → 反解最优塑形容器 + 筛选阈值**

```python
from research import FoldedNormal, KF27Params, optimize_kf27, x_min_smallx, se_target

# 1. 拟合 |ν|/σ 分布（玉米 1h 实测）
D = FoldedNormal(mu_D=0.198, sd_D=0.108).fit()

# 2. KF-27 反解最优 (K_S*, K_T*, τ*)
params = KF27Params(distribution=D, c_side=0.077, sigma_bar=1.0)
result = optimize_kf27(params, objective="sharpe_year")
# result.k_s ≈ 3.0, result.k_t ≈ 9.0, result.tau ≈ 0.65, result.sharpe_year ≈ 1.66

# 3. 反解筛选阈值
x_min = x_min_smallx(result.k_s, result.k_t) if False else x_min_smallx(
    c_side=0.077, k_s=result.k_s, k_t=result.k_t)
se_tgt = se_target(x_star=result.x_star, x_min=x_min)
# se_tgt ≈ 0.047
```

**场景 B：给定一个候选因子输出 → 三层 gate 判决**

```python
from research import run_screening, verify_causality_by_truncation

# 0. Gate 0 · 因果性硬约束
cauz = verify_causality_by_truncation(factor, history, sample_indices=[...])
assert cauz.passed, f"因子存在未来信息泄漏: {cauz.failed_indices}"

# 1-3. 完整三层 gate
screening = run_screening(
    x_hat=x_hat_series,          # 因子在评估集上的输出
    x_truth=x_truth_series,      # x^真(W) 真值代理
    x_min=x_min,
    x_star=result.x_star,
    n_bars_total=len(x_hat_series),
    year_bars=1625.0,
    n_year_star=result.n_year,
)
# screening.accepted ∈ {True, False}
# screening.reject_reason ∈ {None, "Gate1", "Gate2", "Gate3"}
# screening.gate1.se_hat / gate1.margin  · 距 se_target 的差距
# screening.gate2.n_year / gate2.ratio    · 覆盖率
# screening.gate3.r_hat                   · Spearman 相关
```

**场景 C：给 Gate 1/3 加严格版 CI 判据**

```python
from research import cluster_bootstrap

# Gate 1 严格版：CI_97.5(se) ≤ se_target
boot_se = cluster_bootstrap(
    events=eval_events,                                 # dict list · 每条含 x_hat / x_truth / symbol / contract
    cluster_key=lambda e: (e["symbol"], e["contract"]),
    statistic=lambda es: _rms_error(es),                # 用户自定义 se 估计函数
    n_boot=5000,
    seed=42,
)
gate1_strong = boot_se.ci_high <= se_tgt
```

### 3.3 与上游工具的关系

| 上游 raw-script（论文实验用） | 本域稳定实现（长期库） | 差异 |
|---|---|---|
| `theme:structural-shaping-alpha/raw-scripts/first_passage_boundary_explorer.py` | `research.fpt` | 上游是实验驱动器；本域是纯函数 |
| `theme:structural-shaping-alpha/raw-scripts/fourier_finite_time_test.py` | `research.fourier` | 上游 100 项截断；本域可配置 `n_terms` |
| `theme:structural-shaping-alpha/raw-scripts/kf26_parameter_optimizer.py` | `research.optimizer` + `research.distribution` | 上游是网格 CLI；本域拆成 `KF27Params` / `optimize_kf27` |
| `theme:structural-shaping-alpha/raw-scripts/corn_1h_strength_three_views.py` | 待补 · 计划下一步 | 需要拿到 `mu_D` / `sd_D` 的估计器 |
| `theme:structural-shaping-alpha/raw-scripts/hurst_stratifier.py` | `research.hurst` | 上游做 20 合约扫描；本域是单序列估计 |
| `archive:2026-07-13-...future-info-leak/verify_leak_by_truncation.py` | `research.causality` | 上游按主题定制；本域是通用接口 |

**边界原则**：本域**不包含**任何 I/O、数据加载、CLI 调度、绘图。
凡是"实验一次性用完"的驱动脚本仍保留在上游 `raw-scripts/`，
凡是"能被跨主题复用的纯函数"才沉淀到本域。

### 3.4 单元测试与质量门槛

```bash
# 跑本域全部测试
uv run pytest workspace/tests/research/ --tb=short -q

# 完整 lint + type check
ruff check workspace/research/ workspace/tests/research/
ruff format --check workspace/research/ workspace/tests/research/
uv run mypy workspace/research
```

覆盖用例（截至 v0.1）：**62 项测试**分布在 4 个测试文件：

- `test_channel_b.py`：FPT / Fourier / KF-26 混合期望 / $x_{\min}$（25 用例，含 Doob 极限、$R<1$ 反通道 B、玉米 1h 数值核对）
- `test_distribution_optimizer.py`：FoldedNormal + KF-27 优化器（11 用例）
- `test_screening.py`：三层 gate + `se_target` + `run_screening` 早停语义（14 用例）
- `test_validation_tools.py`：Bootstrap + Hurst + 截断法（12 用例）

**长期约定**：本域任何新增 API 必须同时提交单元测试；
任何改变数学语义的修改必须先回改 shaping-theory 的相关章节。

***

## 四、标准因子筛选流程

给定一个"疑似能识别 $|\nu|/\sigma$ 强段"的候选因子 $f$，按下述**7 步固定流程**完成 accept / reject 判决。
流程是**顺序执行、早停**——任一步失败即 reject，不必跑完后续。

### Step 0 · 立项登记（filing）

在开跑任何计算前，把下面这些信息一次性写入
`docs/workbench/strength-factor-screening/candidate-<slug>.md`：

- **因子 slug**：全小写连字符命名，全局唯一（如 `atr-regime-shift-1h` / `hurst-strat-1h`）
- **假设陈述**：一句话说明"这个因子如何从 $H_{\le t}$ 抽出 $\hat{x}_t$"
- **理论出处**：引用哪一条 KF / 哪一篇 archive / 哪一段 shaping-theory 章节
- **品种 × 周期 × 成本档**：本轮验证的三维定位（首战默认 玉米 1h + $c=0.077$）
- **预期结论**：作者事前对 se / coverage / rank corr 的估计（用于后验对比）

**判据**：任何 workbench 未登记的候选因子**不接受**进入 Step 1。这是防止"跑了半天忘了当初想验证什么"的低成本前置门。

### Step 1 · 参数准备（parameter binding）

从上游 KF-27 拉取本轮验证所需的一整套参数：

```python
from research import FoldedNormal, KF27Params, optimize_kf27, x_min_smallx, se_target

# 分布参数：由品种/周期决定（首轮玉米 1h 用 mu_D=0.198, sd_D=0.108）
D = FoldedNormal(mu_D=<mu_D>, sd_D=<sd_D>).fit()

# KF-27 反解最优塑形容器
params = KF27Params(
    distribution=D,
    c_side=<c_side>,       # 现价单边成本（ATR）
    sigma_bar=<sigma_bar>, # 周期波动率（1h=1.0）
    year_hours=1625.0,
)
kf27 = optimize_kf27(params, objective="sharpe_year")

# 反解筛选阈值
x_min = x_min_smallx(c_side=<c_side>, k_s=kf27.k_s, k_t=kf27.k_t)
se_tgt = se_target(x_star=kf27.x_star, x_min=x_min)
```

**登记要求**：把 `(K_S*, K_T*, τ*, x*, x_min, se_target, N_year*)` 全部写入候选登记文件，
后续所有 gate 判据都基于这套参数——**中途禁止改动**。

### Step 2 · Gate 0 · 因果性硬约束

任何声称因果的因子必须先过截断法：

```python
from research import verify_causality_by_truncation

sample_indices = list(range(50, len(history), max(1, len(history) // 200)))  # ≥ 100 个 t
cauz = verify_causality_by_truncation(
    factor=<f>,
    history=<H>,
    sample_indices=sample_indices,
)
assert cauz.passed, f"泄漏样本: {cauz.failed_indices[:5]}"
```

**判据**：`cauz.passed = True` 且 `cauz.max_diff ≤ 1e-9`。
**失败处理**：立即 reject，因子归为"结构性泄漏"，在 workbench 追加根因分析
（是引用了未来 bar / 依赖了下游变量 / 还是 lookup key 错位）。归档后本流程不再触碰该因子。

### Step 3 · 真值构造（truth proxy）

在评估集 $B$（去掉首尾 $W$ bar）上：

- $\hat{x}_t = f(H_{\le t})$：因子输出序列
- $x_t^{\text{真}}(W)$：用 $t$ 之后 $W$ 个 bar 的对数收益均值 / 标准差反算的 $|\nu|/\sigma$，
  作为**真值代理**（只做离线验证用，实盘决策禁止调用）

**W 的选择**：

| 周期 | W 默认值 | 依据 |
|---|---|---|
| 5m | 240 | 20h ≈ 上一个交易日 |
| 15m | 80 | 同上 |
| 1h | 20 | 20 bar ≈ 上一个交易日 |
| 日线 | 5 | 5 bar ≈ 一周 |

**注意事项**：

- 若因子本身就是"过去 K bar 的对数收益/波动"（如窗口回归），$\hat{x}_t$ 与 $x_t^{\text{真}}(W)$
  会因时间错位天然低相关，Gate 3 会失败——这属于"结构不兼容"，不算方法论问题。
- $W$ 一旦选定就写入登记文件，Gate 1 / Gate 3 全流程共享此值。

### Step 4 · Gate 1 · SE 精度

```python
from research import gate1_se_precision

g1 = gate1_se_precision(x_hat=x_hat_series, x_truth=x_truth_series, se_target_value=se_tgt)
```

**判据（宽松版）**：`g1.passed = True`，即 $\widehat{\text{se}} \le \text{se}_{\text{target}}$。

**判据（严格版 · 终审推荐）**：用 cluster bootstrap 给 se 加 CI，
要求 $\text{CI}_{97.5}(\widehat{\text{se}}) \le \text{se}_{\text{target}}$：

```python
from research import cluster_bootstrap

def _rms_error(events):
    return (sum((e["x_hat"] - e["x_truth"]) ** 2 for e in events) / len(events)) ** 0.5

boot = cluster_bootstrap(
    events=eval_events,                            # 每条含 x_hat / x_truth / symbol / contract
    cluster_key=lambda e: (e["symbol"], e["contract"]),
    statistic=_rms_error,
    n_boot=5000,
    seed=42,
)
gate1_strong = boot.ci_high <= se_tgt
```

**登记内容**：$\widehat{\text{se}}$、`g1.margin`、bootstrap CI 上下界。
**失败处理**：记录"距 se_target 的差距"，如果 $\widehat{\text{se}}$ 只是略高（如 1.2× target），
可留档进入 Step 8 的迭代池；如果 $\widehat{\text{se}} > 3 \times$ target，直接归为"结构不合"reject。

### Step 5 · Gate 2 · 覆盖率

```python
from research import gate2_coverage

threshold = x_min + 1.645 * g1.se_hat            # 用 Step 4 得到的 se_hat 反解触发阈值
g2 = gate2_coverage(
    x_hat=x_hat_series,
    threshold=threshold,
    n_bars_total=len(x_hat_series),
    year_bars=1625.0,                            # 周期年 bar 数
    n_year_star=kf27.n_year,
    ratio_threshold=0.70,
)
```

**判据**：`g2.passed = True`，即 $N_{\text{year}}(f) \ge 0.70 \cdot N_{\text{year}}^\ast$。

**登记内容**：$N_{\text{year}}(f)$、`g2.ratio`、触发阈值 $\theta_{\text{thresh}}$。
**失败处理**：$N_{\text{year}}$ 过低说明因子"读数过于谨慎"，年化收益会被稀释。
可以尝试降低阈值系数或换一个稍弱的判据，但**不允许**为了通过 Gate 2 而牺牲 Gate 1
（如把 $\theta_{\text{thresh}}$ 强行拍低到 $x_{\min}$ 附近，见 Step 8 反模式）。

### Step 6 · Gate 3 · 秩相关

```python
from research import gate3_rank_correlation

g3 = gate3_rank_correlation(x_hat=x_hat_series, x_truth=x_truth_series, threshold=0.40)
```

**判据（宽松版）**：`g3.passed = True`，即 Spearman $r \ge 0.40$。

**判据（严格版 · 终审推荐）**：bootstrap 给 $r$ 加 CI，要求 $\text{CI}_{2.5}(r) > 0$：

```python
def _spearman_r(events):
    from research.screening import _spearman_rank   # 内部工具，或用 scipy.stats.spearmanr
    xs = [e["x_hat"] for e in events]
    ys = [e["x_truth"] for e in events]
    # ... 复用 gate3 内部实现或调 scipy
    ...

boot_r = cluster_bootstrap(events=eval_events, cluster_key=..., statistic=_spearman_r, n_boot=5000, seed=42)
gate3_strong = boot_r.ci_low > 0
```

**登记内容**：$\widehat{r}$、bootstrap CI 上下界。
**失败处理**：$r < 0.40$ 但 Gate 1/2 通过 → **"精度好但方向错"陷阱**——
因子读数是"两个噪声的高精度拟合"，把它当强度识别器会持续误发信号。归档反例登记。

### Step 7 · 终审与登记（final verdict）

调用一次性组合门 `run_screening()` 做最终判决（内部按 Step 4–6 顺序早停）：

```python
from research import run_screening

verdict = run_screening(
    x_hat=x_hat_series,
    x_truth=x_truth_series,
    x_min=x_min,
    x_star=kf27.x_star,
    n_bars_total=len(x_hat_series),
    year_bars=1625.0,
    n_year_star=kf27.n_year,
    coverage_ratio=0.70,
    rank_threshold=0.40,
)
# verdict.accepted / verdict.reject_reason / verdict.gate1 / gate2 / gate3
```

**判决四种情形**：

| accepted | reject_reason | 登记路径 |
|---|---|---|
| True | None | `research-status.md` 关键发现清单追加一条 KF · 因子成为下游子主题种子 |
| False | Gate1 | `docs/workbench/strength-factor-screening/rejected_factors.md` · 附差距 |
| False | Gate2 | 同上 · 附 $N_{\text{year}}$ 与 ratio |
| False | Gate3 | 同上 · 附 $\widehat{r}$，并追加 "精度好但方向错" 标签 |

**accept 语义的边界**（重申）：

- **不等于** 样本外仍可行 → 需另做 out-of-sample 验证
- **不等于** 可实盘 → 需另做 realistic-cost 敏感性 + 名义压缩三档对照
- **不等于** 无残余风险 → Gate 3 只保证秩单调，未验证极值区尾部

### Step 8 · 反模式清单（禁止做法）

以下"擦边通过"手法**统一列为方法论证伪**，一旦观察到即使数值 accept 也强制转 reject：

- **临时调阈值让流程通过** · 三个阈值（`0.70`, `0.40`, `z=1.645`）在单次实验中禁止改动；
  确需改动的话，先在 `parameter-selection-spec.md` 登记敏感性证据。
- **改 W 让 Gate 3 通过** · $W$ 一旦在登记文件写死，全流程不得再改；换 W 视同新候选，重跑 Step 0。
- **换品种/周期让 Gate 2 通过** · 每个 (symbol, period, cost) 是独立候选，不允许跨组"挑通过组"上报。
- **让因子输出 $\hat{x} = x^{\text{真}}(W)$ 作弊** · 因子必须**只**引用 $H_{\le t}$；
  Gate 0 会截住这种情形，但仍有可能通过间接引用（如 label 泄漏）绕过——终审时需人工复查。
- **用 $\hat{x}$ 训练模型再回代 Gate 3** · 若因子内部含机器学习模型，
  评估集 $B$ 必须与训练集完全无时间重叠（走 walk-forward），不能用"训练集样本内 IC"上报 Gate 3。

### Step 9 · 方向偏向审计（direction-neutrality audit）

强度识别因子的核心假设是"因子输出 $\hat{x}$ 与 $\text{sign}(\nu)$ 无关"。若因子在 fire 事件上
系统性地偏向做多或做空，就退化成了**披着强度外壳的方向因子**——这时兑现路径必须走通道 A
（方向筛选 + 塑形），而不能用本主题的 DirRandom 假设下反解的 $(K_S^\ast, K_T^\ast, \tau^\ast)$。

**为什么在 Gate 1-3 之后单独审计**：三层 gate 只测因子对 $\|\nu\|/\sigma$ 的估计质量，
对 $\text{sign}(\nu)$ 不作任何检验。一个"IC 高但方向系统偏正"的因子可以完美通过 Gate 1-3，
但它的兑现容器和 KPI 都不适用 KF-27 反解的那一套。

**方法**：在 fire 事件集 $F(f) = \{t : \hat{x}_t \ge \theta_{\text{thresh}}\}$ 上，
用 $t$ 之后 $W$ bar 数据估计**符号真值** $\text{sign}(\nu_t)^{\text{真}}$，
然后做双侧二项检验。

```python
def _direction_audit(events, alpha=0.05):
    """事件集上的 sign(ν) 分布二项检验。"""
    from math import sqrt

    signs = [1 if e["nu_truth"] > 0 else (-1 if e["nu_truth"] < 0 else 0) for e in events]
    n_pos = sum(1 for s in signs if s > 0)
    n_neg = sum(1 for s in signs if s < 0)
    n_valid = n_pos + n_neg
    if n_valid < 30:
        return {"n_valid": n_valid, "warning": "样本不足，直接判存疑"}

    p_hat = n_pos / n_valid                                # 观测到的做多比例
    se = sqrt(p_hat * (1 - p_hat) / n_valid)
    z = (p_hat - 0.5) / se                                 # H0: p = 0.5
    passed = abs(z) < 1.96                                 # 双侧 α = 5%
    return {
        "n_pos": n_pos, "n_neg": n_neg,
        "p_hat_long": p_hat,
        "z": z, "passed": passed,
        "bias": "long" if z > 1.96 else ("short" if z < -1.96 else "neutral"),
    }

audit = _direction_audit(fire_events)
```

**判据**：`abs(z) < 1.96`（即 fire 事件的做多比例落在 $[0.5 - 1.96 \cdot \text{se}, 0.5 + 1.96 \cdot \text{se}]$ 内）。

**判决三种情形**：

| audit 结果 | 含义 | 处理 |
|---|---|---|
| `bias = "neutral"` | 方向随机 → DirRandom 假设成立 | ✅ 认定为纯强度因子，Step 10 继续 |
| `bias = "long"` 或 `"short"` | 方向系统偏向 → 混入了通道 A 信号 | ⚠️ **转投通道 A 流程** — 重跑主题外的"方向筛选"验证；本主题登记为"疑似方向因子" |
| `n_valid < 30` | fire 样本过少 | ⏸ 暂搁 · 需扩样本量或降低阈值重来 |

**补充检验（可选 · 精细版）**：分别对做多 fire 与做空 fire 集合计算条件 $E_{\text{gross}}$：

- 若 $E_{\text{gross}}^{\text{long fires}} \approx E_{\text{gross}}^{\text{short fires}}$ → 强度因子（本主题接受）
- 若 $E_{\text{gross}}^{\text{long fires}} > E_{\text{gross}}^{\text{short fires}}$（显著） → 隐含正向方向 alpha
- 若相反 → 隐含负向方向 alpha

**登记内容**：$n_{\text{long}} / n_{\text{short}}$、$\hat{p}_{\text{long}}$、$z$ 值、bias 标签、
是否补跑条件期望对比。全部写入候选登记档。

**方法论意义**：这一步是本流程与主流因子筛选的**唯一显式方向解耦**——
Alphalens / IC-IR 派不做这件事，因为它们的目标量是收益（含方向），方向偏向只是"这个因子好"的表现；
本流程必须做，因为一旦因子偏向，$(K_S^\ast, K_T^\ast, \tau^\ast)$ 反解的假设失效，
即使 Gate 1-3 通过也不能进实盘。

### Step 10 · accept 后的下游路径

因子通过全流程后进入下游子主题（本主题不实现，仅列路径）：

1. **out-of-sample 验证** · 用未参与筛选的时间段重跑 Step 4–7，允许 se 略退化但不能穿过 se_target × 1.2 上限
2. **跨品种扩展** · 用 shaping-theory §2.23.6.5 板块预估表挑同一板块相似 se_target 的品种复验
3. **cost 敏感性** · 三档成本（低/中/高）分别代入 KF-27 重算 se_target，检查因子在成本区间内是否稳健
4. **实盘接入方案** · 由下游工程主题接手，本主题只输出"因子 accept 结论 + 完整登记档案"作为交接文物

至此完成一次强度识别因子的完整生命周期：**立项 → 参数绑定 → 因果验证 → 真值对齐 → 三层 gate → 判决 → 方向解耦 → 下游**。

流程本身没有任何自由度，全部数值判据来自 shaping-theory 的 KF-26 / KF-27 数学推导——
这也是"筛选方法学"作为独立主题存在的原因：它是**上游数学到下游因子研究之间的确定性桥梁**。

***

## 五、工程边界条件

前四节的数学与流程假设 GBM 的"σ 恒定、路径连续、任意 $K_S$ 都可用"。
真实市场里三条边界约束一旦被踩，即使 Gate 1-3 全通过、方向审计也通过，
实盘照样爆——本节把 shaping-theory KF-23 / KF-24 / KF-25 与 §2.20.4 沉淀的
四条工程 gate 一次性登记。

**执行时机**：这些 gate 必须在 Step 1（参数准备）之后、Step 2（因果性）之前静默执行。
任何 gate 失败 → 该 (symbol, period, cost) 组合直接标记为"通道 B 不可行"，
本主题不再进流程；候选因子若感兴趣可以改成走通道 A（有方向 alpha 的另一主题）。

### 5.1 $K_S$ 跳空下限（KF-23）

**问题**：session gap 会直接穿透窄止损。若 $K_S < K_{S,\min}$，
即使因子完美预测强段方向，实盘也会因跳空爆掉止损，$P_{\text{win}}$ 相对 GBM 高估 20–50%。

**闭式下限**（正态跳空模型）：

$$
K_{S,\min}
\;=\; z_{0.95} \cdot \sigma_{\text{jump}},
\qquad z_{0.95} = 1.645
$$

其中 $\sigma_{\text{jump}}$ 是 $|\text{gap}| / \text{ATR}$ 的样本标准差。

**shaping-theory §2.20.4 实测下限**：

| 周期 | $\sigma_{\text{jump}}/\sigma_{\text{bar}}$ | $K_{S,\min}$ (P<5%) | $K_{S,\min}$ (P<10%) |
|---|---|---|---|
| 5m | 0.273 | **2.60** | 2.02 |
| 15m | ~0.15 (插值) | **1.50** | 1.20 |
| 1h | 0.042 | **1.00** | 0.78 |
| 日线 | 0.037 | **0.40** | 0.31 |

**判据**：`kf27.k_s >= K_S_min(period)`。若 KF-27 反解的 $K_S^\ast$ 低于对应周期下限，
说明该品种/周期的最优容器与跳空安全区间冲突——**不进本主题流程**。

**特殊警示**：$K_S < 1.5$ 时（1h 周期），跳空修正把 $P_{\text{win}}$ 从 GBM 的 0.500
拉到 0.237（-53%）——完全推翻塑形容器的期望计算。这不是"参数敏感性"问题，
是**方法论前提失效**。

### 5.2 T/T\* 上限约束（KF-6 / §2.18.5）

**问题**：$T^\ast = \max(K_S, K_T)^2 / \sigma^2$ 是"无漂移下平均触达 barrier 所需时间"。
若持仓时限 $T$ 过短、$T/T^\ast < 0.33$，barrier 触达变成小概率事件——
$P(\tau > T)$ 主导，$T = \infty$ FPT 公式失效，本主题所有 gate 判据要用 Fourier 精确解替代。

**判据**：

$$
\frac{T}{T^\ast} \;\ge\; 0.33
\quad\Longleftrightarrow\quad
T \;\ge\; \frac{\max(K_S^\ast, K_T^\ast)^2}{3\,\sigma^2}
$$

**玉米 1h 参考**：$K_T^\ast = 9$、$\sigma_{\text{bar}} = 1$ → $T^\ast = 81$ h，
$T \ge 27$ h（约 4 个交易日）即安全。日内策略若强制平仓 $\le 6$ h，
则本主题参数几乎不适用——必须缩小 $K_S$（触发 §5.1）或换周期。

**替代方案**：若 $T/T^\ast < 0.33$ 但业务上必须持仓短，
用 `research.fourier.p_win_finiteT_fourier(k_s, k_t, sigma, T)` 替代 T=∞ FPT 作为 null，
把 §2.7 里的 $x_{\min}$ / $se_{\text{target}}$ 全部按 Fourier 版本重算——
本主题目前**不实现该替代路径**（v2 规划）。

### 5.3 $\sigma_{\text{bar}}$ 跨周期换算表

跨周期比较（如"5m 因子 vs 1h 因子谁更优"）时，$\sigma_{\text{bar}}$、$W$、
$year\_bars$ 必须统一到"每小时 σ = 1 ATR"基准。

| 周期 $\Delta$ | $\sigma_{\text{bar}}$ | 真值窗口 $W$（20h 对齐） | $year\_bars$ | $T$ (24h) 对应 bar 数 |
|---|---|---|---|---|
| 5m | $1/\sqrt{12} \approx 0.289$ | 240 | 19500 | 288 |
| 15m | $0.500$ | 80 | 6500 | 96 |
| 1h | $1.000$ | 20 | 1625 | 24 |
| 日线 | $\sqrt{6.5} \approx 2.550$ | 5 | 250 | 1 |

**判据（隐式）**：因子候选跨周期扩展时（Step 10 · out-of-sample 后），
新周期的 $(\sigma_{\text{bar}}, W, year\_bars)$ 必须按上表**同时**更新，
禁止只改一个。$W$ 一旦选定就写入登记文件（Step 3 已强制）；本节补上其他两项。

### 5.4 $\sigma$ 时变的隐性误差（KF-24）

**问题**：ATR CV ≈ 18%、lag-1 自相关 0.174——入场时 ATR=1 的止损在持仓期实际可能落到 0.82–1.18，
barrier 有效宽度 ±30%。这引入 ±5% 量级的 $P_{\text{win}}$ 误差
（远小于跳空 20–50%，但对 se≤0.05 的严苛 KPI 是不可忽略的量级）。

**目前处理**：本主题**不做 σ 时变主动补偿**，把 ±5% 归入 Gate 1 的
"距 se_target 至少 20% 缓冲"（即实际观测 se 应 $\le 0.8 \cdot se_{\text{target}}$
才认为"稳过 gate"）。这与 shaping-theory §2.23.4 的分布拟合 3% 误差合计约 8%。

**未来路径**：动态用 $\text{ATR}(t) / \text{ATR}(\text{entry})$ 缩放 barrier
（trailing 类似）· 属工程实现层面，与本主题的筛选流程正交。

### 5.5 FoldedNormal 拟合精度警告

**问题**：`research.distribution.FoldedNormal.fit()` 只用前两阶矩（$\mu_D, \sigma_D$），
尾部与经验分布可能有偏差。玉米 1h 实测：拟合分布给出的 $x^\ast$ 比经验分位偏低 3%
（shaping-theory §2.23.4）。

**判据**：任何品种上线通道 B 前必做 **$\sigma_D \pm 30\%$ 敏感性核对**——
把 $\sigma_D$ 分别乘 0.7 / 1.0 / 1.3 三档，重跑 KF-27 优化器，
检查三组 $(K_S^\ast, K_T^\ast, \tau^\ast, se_{\text{target}})$ 变化幅度：

- 三组 $se_{\text{target}}$ 相对差 < 30% → 分布拟合稳健 → 用 FoldedNormal 即可
- 相对差 ≥ 30% → 换 **KDE / 直方图经验分布**（v2 路径，本主题暂不实现）

**结果登记**：$\sigma_D$ 敏感性三档结果写入候选登记档 Step 1 参数块。

### 5.6 边界条件门 · 一次性组合检查

给定 $(symbol, period, c\_side)$，本节四条边界条件的组合检查如下：

```python
from research import KF27Params, optimize_kf27, FoldedNormal

def edge_conditions_gate(mu_D, sd_D, c_side, period,
                          k_s_min_table, t_horizon_hours):
    """
    执行 §5.1 (K_S 下限) · §5.2 (T/T*) · §5.5 (σ_D 敏感性) 三条硬 gate。
    §5.3 (σ_bar 换算) 由调用方按 period 传入；§5.4 (σ 时变) 隐入 20% 缓冲。
    """
    K_S_min = k_s_min_table[period]              # 5.1 · 5m/15m/1h/日线 查表
    sigma_bar = SIGMA_BAR_TABLE[period]

    D = FoldedNormal(mu_D=mu_D, sd_D=sd_D).fit()
    kf27 = optimize_kf27(KF27Params(
        distribution=D, c_side=c_side, sigma_bar=sigma_bar,
        k_s_min=K_S_min,                         # 直接把下限传给优化器
    ), objective="sharpe_year")

    # §5.1
    if kf27.k_s < K_S_min:
        return {"pass": False, "reason": f"K_S* {kf27.k_s} < K_S_min {K_S_min}"}

    # §5.2
    t_star = max(kf27.k_s, kf27.k_t) ** 2 / sigma_bar ** 2
    if t_horizon_hours < 0.33 * t_star:
        return {"pass": False, "reason": f"T/T* = {t_horizon_hours/t_star:.2f} < 0.33"}

    # §5.5 · σ_D 敏感性
    variants = []
    for scale in [0.7, 1.0, 1.3]:
        D_var = FoldedNormal(mu_D=mu_D, sd_D=sd_D*scale).fit()
        variants.append(optimize_kf27(KF27Params(
            distribution=D_var, c_side=c_side, sigma_bar=sigma_bar,
        ), objective="sharpe_year"))
    se_targets = [(v.x_star - x_min_smallx(c_side, v.k_s, v.k_t))/1.645 for v in variants]
    if (max(se_targets) - min(se_targets)) / se_targets[1] > 0.30:
        return {"pass": False, "reason": "σ_D sensitivity > 30%, need KDE"}

    return {"pass": True, "kf27": kf27, "se_target_range": se_targets}
```

**接入位置**：Step 1（参数准备）后加一次 `edge_conditions_gate()` 调用；
若返回 `pass=False`，整个候选组合直接标记为"通道 B 不可行"，跳过 Step 2-10。

**四档周期的默认 `K_S_min` 表**（写死在候选登记档，不允许单实验修改）：

```python
K_S_MIN_TABLE = {"5m": 2.60, "15m": 1.50, "1h": 1.00, "日线": 0.40}
SIGMA_BAR_TABLE = {"5m": 1/12**0.5, "15m": 0.5, "1h": 1.0, "日线": 6.5**0.5}
```

***

## 六、双置信度视角：分类器型 vs 回归器型因子

第一至第五节的 Gate 1（SE 精度）默认因子输出是**$\|\nu\|/\sigma$ 的点估计**——
即回归器（读数直接是数字）。但实际候选因子里有大量**分类器**——
"当前是否处于强段？"输出只有 True/False（或 top-N% flag）而非具体 $\hat{x}$。

shaping-theory §2.23.5.3 明确讲了这一区分——两种"置信度"从根本上不同，
必须走**两条不同的 Gate 1 路径**。本节把它作为筛选流程的强制分岔。

### 6.1 两种置信度的定义

| 视角 | 因子形态 | 置信度含义 | Gate 1 判据 |
|---|---|---|---|
| **A · 分位置信度** | 分类器 · 输出 fire ∈ {0, 1} | fire 事件真实 $\|\nu\|/\sigma$ 落在分布前 $\tau^\ast$ 分位的概率 ≥ 95% | 命中率检验（下节 6.2） |
| **B · 参数估计置信度** | 回归器 · 输出 $\hat{x} \in \mathbb{R}^+$ | $\hat{x}$ 关于真值 $x$ 的估计标准误 ≤ $se_{\text{target}}$ | $\widehat{se} \le se_{\text{target}}$（原 §四 Step 4）|

**核心不等式统一形式**（§2.23.6.7）：

$$
\hat{x} \;\ge\; \underbrace{x_{\min}}_{\text{信号强度盈亏下限}} \;+\; \underbrace{z_{0.95} \cdot se(f)}_{\text{置信度缓冲}}
$$

两个视角是同一条不等式的**两个投影**：

- 视角 B 固定"识别器 se"、反解"最低 $\hat{x}$ 读数"
- 视角 A 固定"$\hat{x} = x^\ast$"（KF-27 最优点，前 $\tau^\ast$ 分位对应值）、
  反解"允许的最大 se"（即 $se_{\text{target}}$）

### 6.2 视角 A 的 Gate 1 判据 · 命中率检验

**因子形态**：分类器 $f: H_{\le t} \to \{0, 1\}$ · 声称"$f_t=1$ 时当前处于前 $\tau^\ast$ 强段"

**统计量**：在 fire 事件集 $F(f) = \{t : f_t = 1\}$ 上，用 $t$ 之后 $W$ bar 计算真值 $x_t^{\text{真}}$，
命中率 $\hat{h}$ 是 fire 中真值落在前 $\tau^\ast$ 分位的比例：

$$
\hat{h}(f) \;=\; \frac{|\{t \in F(f) \,:\, x_t^{\text{真}}(W) \ge x^\ast\}|}{|F(f)|}
$$

**判据（95% 单侧置信）**：

$$
\hat{h}(f) \;-\; 1.645 \cdot \text{se}(\hat{h}) \;\ge\; \tau^\ast
\qquad \text{其中 } \text{se}(\hat{h}) = \sqrt{\frac{\hat{h}(1-\hat{h})}{|F(f)|}}
$$

**为什么阈值是 $\tau^\ast$ 而非 $x^\ast$**：$\tau^\ast$ 是"随机识别器的命中率基线"
（比如 KF-27 $\tau^\ast = 0.65$ 意味随机猜"当前是强段"的命中率就是 65%，
真正的因子必须显著高于这个基线）。

**玉米 1h 数值参考**（$\tau^\ast \approx 0.65$）：

| 观察命中率 $\hat{h}$ | 有效样本 $|F|$ | $se(\hat{h})$ | $\hat{h} - 1.645 \cdot se$ | 判决 |
|---|---|---|---|---|
| 0.85 | 30 | 0.065 | 0.743 | ✅ 显著高于 0.65 |
| 0.75 | 100 | 0.043 | 0.679 | ✅ 边缘通过 |
| 0.72 | 100 | 0.045 | 0.646 | ❌ 未过基线 |
| 0.85 | 15 | 0.092 | 0.699 | ⚠️ 样本不足 · 需 $\ge 30$ |

**Bootstrap 严格版**：把命中率的 se 换成 cluster bootstrap CI 下界，
要求 $\text{CI}_{2.5}(\hat{h}) \ge \tau^\ast$。

### 6.3 视角 B 的 Gate 1 判据 · SE 精度

**因子形态**：回归器 $f: H_{\le t} \to \mathbb{R}^+$ · 输出 $\hat{x}_t$

**判据**：$\widehat{se}(f) \le se_{\text{target}}$（回到 §四 Step 4 的完整流程）

**这条路径在前四节已完整定义**，本节不重复。

### 6.4 双视角矩阵 · 玉米 1h 完整对照

$x_{\min} = 0.055$，$z_{0.95} = 1.645$：

| **视角 B 的 se** | **最低 $\hat{x}$ 读数** | 对应分布分位 | 年入场数 | 单笔 E_net | 年化@r=1% | 达标状态 |
|---|---|---|---|---|---|---|
| 0.010 | ≥ 0.071 | 前 87% | 279 | +0.03 ATR | +3% | ✅ 超额（识别器过强）|
| 0.020 | ≥ 0.088 | 前 82% | 265 | +0.08 ATR | +8% | ✅ 完全达标 |
| 0.030 | ≥ 0.104 | 前 74% | 240 | +0.15 ATR | +13% | ✅ 完全达标 |
| **0.046** = $se_{\text{target}}$ | **≥ 0.131** | **前 65%（KF-27 $\tau^\ast$）** | **210** | **+0.31 ATR** | **+20.2%** | ✅ **正好落 KF-27 最优点** |
| 0.060 | ≥ 0.154 | 前 58% | 185 | +0.42 ATR | +19% | ⚠️ 略降 |
| 0.080 | ≥ 0.187 | 前 51% | 165 | +0.55 ATR | +18% | ⚠️ 明显降 |
| 0.100 | ≥ 0.220 | 前 43% | 140 | +0.68 ATR | +15% | ⚠️ 大幅降 |
| 0.150 | ≥ 0.302 | 前 19% | 60 | +1.10 ATR | +11% | ❌ 频率不足 |
| 0.224（20h 窗口回归）| ≥ 0.424 | 前 3% | 10 | +2.20 ATR | +2% | ❌ 不可用 |

**三条读表规则**（screening-methodology 强制记忆）：

1. **信号强度要求随 se 单调上升**：识别器越粗糙、需要看到的信号越强
2. **年化率在 $se_{\text{target}}$ 处取最大**：越过最优点后"频率下降损失 > 单笔期望上升收益"
3. **同一年化数值有两条可达路径**（如 +18% 可以是 se=0.06 稠密路径，也可以是 se=0.15 稀疏路径）
   → **更小的 se 永远更优**（Sharpe 更高、回撤更小），但工程实现难度指数级上升

### 6.5 视角 A / B 的选择规则

| 因子类型 | 走视角 | 例子 |
|---|---|---|
| 二分类：event trigger（fire=1 表示"进入强段"） | **A** | 政策发布 30min flag / 板块 3+ 共振 flag |
| 多分类：分位标签（top-N% / mid / bottom） | **A**（对 top-N% 一档做命中率） | GARCH 制度切换后 60min flag |
| 单点回归：直接估 $\hat{x}$ | **B** | ATR·Hurst 融合、GARCH 均值 filter |
| 连续 score：可映射为分位 | **B 或 A**（推荐 B · 信息更充分） | 组合模型的连续输出 |

**若因子输出既有 $\hat{x}$ 也有 fire flag**（如"$\hat{x} \ge \theta_{\text{thresh}}$"型），
**同时**跑 A 与 B——两条都过才算 accept。这是最严的组合门。

### 6.6 关键约束 · 不允许"跨视角挑通过"

- **禁止**：因子先按 B 算出 $\widehat{se} = 0.08$（失败），再重新包装成"top-30% 分类器"跑视角 A 命中率通过
- **原因**：这等价于用视角 A 事后放宽了 se 目标（0.08 的回归精度对应的分类精度是"命中率略高于 $\tau^\ast$"，两条判据本来就是自洽的）
- **合规做法**：因子登记时明确 A / B 视角，此后不允许切换。切换视为新候选，重跑 Step 0（立项登记）。

### 6.7 为何主题**首选 B 视角**

- **B 视角 KPI 是 se（连续量）**：可以量化"距离可行还有多远"，指导迭代方向（补窗口 / 融合信号 / 换真值窗口 W）
- **A 视角 KPI 是命中率（二值汇总量）**：只知道"过 or 不过"，迭代反馈慢
- **B → A 有天然投影**（分类器可视为 threshold 后的回归器），但 A → B 需要重新构造 $\hat{x}$ 估计

**除非因子本质是 event trigger（如政策事件）无法产出连续 $\hat{x}$**，
否则一律推荐走 B 视角。

***




