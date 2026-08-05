# Volume Spike Regime Shift · 策略数学规格

> **⚠️ r1 证伪归档（2026-08-05）**：本规格定义的"1h 成交量同时段 z-score 放量"因子经 Stage 0–8 验证，不构成方向信号也不构成跨品种稳健风险 gate。左尾效应在 lookback N=20 下存在、N=60/120 下消失（KF-7），判定为短窗 σ 估计 artefact。本文档保留作为研究记录与方法论参照，**不作为策略实现依据**。详见 [research-status.md](research-status.md) 与 workbench stage8 报告。

> **文档定位**：主题研究期数学契约（已归档）。
> 回答一个问题：**当最新 1h 成交量相对过去 20 周期均值显著放大（z-score 越界）时，后续 $h$ 根 bar 的市场性质（漂移、波动、Hurst、barrier 首达）是否发生可统计的变化？**
> 这不是策略 alpha 研究，而是**因子效力研究 / 制度刻画**：评估"成交量异常"这一单一外生因子切分市场后，条件子样本的 DGP 与无条件样本差异有多大、差异是否稳健，为后续策略的 regime gate 提供数学依据。
>
> **与已有定理的关系**：本规格是 `theorem:structural-shaping-alpha#factor-filtering-and-dgp-boundary` 的实证姊妹篇——该定理给出"条件漂移 $b_A$ 为常数 iff GBM 闭式仍成立"的理论边界；本规格负责**测量**因子 $A$=成交量 spike 触发后 $b_A$、$\sigma_A$、$H_A$ 实际变成什么。

---

## 1. 记号与前提

### 1.1 标的与周期

- 周期固定 1h；符号 $S_t$ 为第 $t$ 根 1h bar 的收盘价，$V_t$ 为该 bar 成交量（合约手数，合约规格已通过 `CONTRACT_SPECS` 统一口径，但跨品种比较时用 z-score 自身无量纲）。
- 每个合约 $c$（形如 `DCE.m2601`）独立计算滚动统计量，**不跨合约池化**（参考 quant-research-methodology §9 数据边界与 KF-22）。
- 时间索引：$t$ 为 1h bar 在该合约内的整数序号；同一交易日内多根 bar 共享 `session_date`。

### 1.2 过滤概率空间

设 $(\Omega, \mathcal{F}, \{\mathcal{F}_t\}, \mathbb{P})$ 为过滤概率空间，所有因子信息取自 $\mathcal{F}_t$（事件 bar 收盘时已知），后续观测从 $\mathcal{F}_{t+1}$ 开始，**无 look-ahead**。

### 1.3 对数收益

$$
r_{t+1} := \ln S_{t+1} - \ln S_t
$$

ATR 归一化：$\sigma_t^{\text{ATR}}$ 为 $t$ 时刻已实现的 ATR(14, SMA-TR 口径)，与 structural-shaping gatekeeper 一致，便于跨主题比较。

---

## 2. 因子定义

### 2.1 滚动成交量均值与标准差（同时段口径）

在每根 bar $t$ 收盘后，用**不含当根 bar** 的过去 $N=20$ 根**同一 hour-of-day** 的 bar 估计：

$$
\mu_t^V := \frac{1}{N}\sum_{\substack{i\in\mathcal{H}(t)\\ i<t}} V_i, \qquad
\varsigma_t^V := \sqrt{\frac{1}{N-1}\sum_{\substack{i\in\mathcal{H}(t)\\ i<t}}(V_i - \mu_t^V)^2}
$$

其中 $\mathcal{H}(t):=\{i:\operatorname{hour}(i)=\operatorname{hour}(t)\}$ 为历史上与当根 bar 同一交易时段的 bar 集合，按时间倒序取最近 $N$ 根。要求 $\varsigma_t^V > 0$ 且 $N$ 根均有效，否则事件丢弃。

> **设计选择 1（trailing，不含当根）**：z-score 衡量的是"当前 bar 相对历史"的异常，必须排除自身，否则均值/方差被当根污染。
>
> **设计选择 2（同时段 rolling，r1→r1.5 修订）**：1h K 线的成交量在不同 hour-of-day 上结构性差异极大——夜盘/日盘开盘 bar 成交量系统性高于盘中。Stage 1 实测发现，全时段 rolling 口径下 $Z\ge2$ 事件 75% 集中在 09:00 与 21:00 两个开盘 bar，spike 实际是"开盘 bar 效应"代理变量。改用同时段 rolling 后，spike 事件在各时段近似均匀分布（每时段 12–20%），并揭露了被开盘效应掩盖的波动放大效应（详见 workbench:volume-spike-regime-shift-r1-stage1_5）。

### 2.2 成交量 z-score（核心因子）

$$
Z_t := \frac{V_t - \mu_t^V}{\varsigma_t^V}
$$

$Z_t$ 无量纲、跨品种可比；这是本研究唯一的外生切分变量。

### 2.3 事件集合（Spike 组与基线组）

给定阈值 $z_0>0$：

- **Spike 组（处理组）**：$\mathcal{A}^+(z_0) := \{t : Z_t \ge z_0\}$（放量）；可选 $\mathcal{A}^-(z_0) := \{t : Z_t \le -z_0\}$（缩量）作为对称对照。
- **Baseline 组（对照组）**：$\mathcal{B}(z_\ell, z_u) := \{t : z_\ell \le Z_t < z_u\}$，取 $z_\ell=-0.5, z_u=0.5$（成交量正常带）作为**紧邻分布中心**的对照，而非全样本，以控制"被选中"本身的选择性偏差（参考 regime_split_er.py 的全局分位切桶设计）。
- 主实验只研究**放量** $\mathcal{A}^+$；缩量 $\mathcal{A}^-$ 作为稳健性附录。

### 2.4 候选阈值与极端档

$$
z_0 \in \{1.5,\, 2.0,\, 2.5,\, 3.0,\, 4.0,\, 5.0\}
$$

- **主规格 $z_0=2.0$**：样本量充足，用于主判决与 FDR 控制；
- **常规档 $z_0\in\{1.5, 2.5, 3.0\}$**：参数稳健性扫描（quant-research-methodology §4）；
- **极端档 $z_0\in\{4.0, 5.0\}$**：专门观察信息冲击 / 大单 / 新闻驱动的极端放量是否切出与温和放量**本质不同**的制度。极端档单独报告，**不参与主 FDR 判决**，只看方向、量级与五分位图尾部形状。

> **不依赖正态假设**：$z_0$ 是"样本标准差倍数"的相对截断，不是正态分位点。成交量序列右偏重尾，$Z_t$ 的真实尾概率必须在 Stage 0 实测。$P(Z\ge 5)$ 在正态下约 $3\times10^{-7}$，但重尾下可能大几个数量级；实际命中率以数据为准。

### 2.5 小样本降级规则

每个 $z_0$ 档独立统计 $n_{\text{events}}$ 与 $n_{\text{clusters}}$（cluster = `(contract, session_date)`）：

- $n_{\text{clusters}} \ge 200$：正常做 cluster bootstrap 推断；
- $30 \le n_{\text{clusters}} < 200$：报告 point estimate 与 bootstrap CI，但结论标记"信度中等"，不单独作为硬证据；
- $n_{\text{clusters}} < 30$：该档**只做描述性报告**（事件清单、逐事件后窗路径、分品种 sign），不报告 p 值、不做"显著/不显著"判决，避免在小样本上造假精度（quant-research-methodology §9）。

极端档若触发小样本降级，补救方向（r2 候选，不在 r1 做）：扩大 lookback $N$（60/120 让 σ 估计更稳）、扩品种、降时间粒度、事后按事件性质（跳空 / 开盘 / 数据发布）归因。

---

## 3. 事件后市场性质的度量

对每个事件 $t\in\mathcal{A}^+(z_0)$ 或 $t\in\mathcal{B}$，定义后窗 $h\in\{1,3,6,12,20\}$ 根 1h bar（约 1h / 半日 / 1 日 / 2 日 / 4 日）。

### 3.1 度量向量

在事件 $t$ 上定义 $h$ 期响应向量 $\mathbf{Y}_t(h)$。**包含 pre 与 post 两个对称窗**：pre 窗 $[t-h, t-1]$、post 窗 $[t+1, t+h]$；spike bar 本身不进入任一窗口。比较模式分两种：

- **横截面**（spike vs baseline）：仅用 post 窗，比较两组条件期望；
- **事件研究**（spike 自身前后）：用 paired diff $Y_{\text{post}}-Y_{\text{pre}}$，并在 baseline 上做 placebo 后取 DiD，扣除市场自身漂移与波动聚集。

| 分量 | 定义 | 含义 |
|------|------|------|
| $r^{(h)}_t$ | $\sum_{i=1}^{h} r_{t+i} = \ln S_{t+h} - \ln S_t$（post）；pre 对称取 $[t-h,t-1]$ | 累计对数收益（方向漂移） |
| $\sigma^{(h)}_t$ | post/pre 窗内对数收益的样本标准差（per-bar） | 已实现波动率 |
| $\lvert r\rvert^{(h)}_t$ | post/pre 窗内 $\lvert r\rvert$ 的均值 | 平均绝对收益（稳健波动） |
| $s^{(h)}_t$ | $\mathrm{mean}(r)/\sigma(r)$（per-bar Sharpe 近似） | 市场强度（有向性） |
| $d_t\cdot r^{(h,\text{post})}_t$ | spike bar 方向 $d_t=\operatorname{sgn}(r_t)$ 乘以 post 累计收益 | 动量/反转 signed 响应 |
| $\text{Hit}^{(h,K_T,K_S,\mathbf{d})}_t$ | post 窗 $[t+1, t+h]$ 内，价格沿方向 $\mathbf{d}\in\{+1,-1,\text{random}\}$ 首达 $+K_T$（ATR 单位）早于 $-K_S$ 的指示变量 | barrier 首达命中（横截面对照用，事件研究不重复） |
| $\tau^{(h,K_T,K_S)}_t$ | 上述首达停时（若未触发记为 $h+1$ 并标 `time_exit`） | 首达时间 |
| $H_t^{(h)}$ | post/pre 窗 $h$ 根对数收益序列的 R/S Hurst 估计（$h\ge 20$ 时才有意义，$h<20$ 此分量置 NaN） | 短窗趋势/回归性 |

### 3.2 Barrier 容器配置

沿 structural-shaping-alpha 已证框架（`theorem:structural-shaping-alpha#when-barrier-shaping-yields-alpha`），固定三组对称/非对称容器（ATR 单位）：

- 对称：$(K_S, K_T) = (1.0, 1.0)$，$R=1$
- 趋势型：$(K_S, K_T) = (1.0, 2.0)$，$R=2$
- 回归型：$(K_S, K_T) = (2.0, 1.0)$，$R=0.5$

每个容器沿三个方向评估：

- $\mathbf{d}=+1$（多）
- $\mathbf{d}=-1$（空）
- $\mathbf{d}=\text{random}$（固定种子抛硬币，DirRandom 基线，用于消除方向选择偏差，同 structural-shaping gatekeeper）

时间窗 $h$ 作为 barrier 的 `time_exit` 上界（以 bar 计），即 $\tau \wedge (h+1)$。

### 3.3 条件度量作为 $Z_t$ 分桶的函数

除了 spike/baseline 二分外，对 $Z_t$ 做五分位切桶（按全体合约池内的全局分位切点，**不按合约独立切**以保持桶语义一致；但每合约的 $Z_t$ 本身独立计算），在每桶内估计上述度量的均值与中位数：

$$
\hat\theta_q(h) := \frac{1}{\lvert\mathcal{C}_q\rvert}\sum_{t\in\mathcal{C}_q} g\bigl(\mathbf{Y}_t(h)\bigr),
\quad q=1,\ldots,5
$$

其中 $g$ 是某个分量的提取函数。单调性 / 非线性用于判断因子是"阈值型"还是"线性型"。

---

## 4. 统计假设与检验

### 4.1 主假设（Spike vs Baseline 的制度差异）

对每个度量分量 $g$、每个后窗 $h$，检验

$$
H_0:\ \mathbb{E}[g(\mathbf{Y}(h)) \mid Z \ge z_0] = \mathbb{E}[g(\mathbf{Y}(h)) \mid \lvert Z\rvert < 0.5]
$$

备择为双侧（差异可能是漂移、波动、首达概率任意方向）。

报告：

- 点估计 $\Delta_g(h) := \hat\theta_{\text{spike}} - \hat\theta_{\text{baseline}}$
- cluster bootstrap 95% CI（cluster = `(contract, session_date)`，见 §4.3）
- 双侧 p-value = $2\cdot\min\{P(\Delta^*\le 0), P(\Delta^*>0)\}$

### 4.2 次假设（方向漂移）

专门检验 spike 后是否存在方向漂移。由于 spike 本身不带方向（可能是放量上涨也可能是放量下跌），**主检验用绝对收益与波动率分量**；方向漂移拆成两个子假设：

- **H1a（动量）**：spike bar 的收益方向 $d_t=\operatorname{sgn}(r_t)$ 在 $h$ 期内延续：
  $$\mathbb{E}[d_t \cdot r^{(h)}_t \mid Z\ge z_0] > 0$$
- **H1b（反转）**：反向：
  $$\mathbb{E}[-d_t \cdot r^{(h)}_t \mid Z\ge z_0] > 0$$

用 signed 响应 $d_t \cdot r^{(h)}_t$ 的单侧 cluster bootstrap。DirRandom 方向作为零基准：若 spike 组沿随机方向也产生正期望，说明存在非方向依赖的波动放大或 drift magnitude 效应。

### 4.3 Cluster bootstrap（必选）

事件独立性结构：同一合约、同一交易日内的多根 1h bar 共享日级特征（隔夜跳空、日盘波动率制度），不能把 $n_{\text{events}}$ 当独立观察数（quant-research-methodology §9）。

- cluster key：`(contract, session_date)`；
- 算法：`workspace/research/bootstrap.py:cluster_bootstrap`，5000 次重采样；
- 同时报告 $n_{\text{events}}$ 与 $n_{\text{clusters}}$（形如 "n_events=2400 · n_indep≈480"）；
- 小样本（某桶 $n_{\text{clusters}}<30$）必须标注"信度不足"，结论降级为观察。

### 4.4 多重比较校正

扫描维度：$z_0 \times h \times g \times \text{容器}$ 总数大（~6 × 5 × 6 × 3 ≈ 540），必须控制 FWER/FDR：

- 主结论只看 $z_0=2.0$ 的核心 6 个度量分量 × 5 个 $h$（30 个检验），用 **Benjamini–Hochberg FDR ≤ 0.10**；
- 常规档 $\{1.5, 2.5, 3.0\}$ 作为**稳健性**，不计入主判决，只看方向与量级一致性；
- 极端档 $\{4.0, 5.0\}$ 按 §2.5 规则处理：样本充足时单独做一组 FDR，样本不足时只做描述性报告，不与主检验混合校正。

---

## 5. 制度归属判定

### 5.1 判决分类

对每个度量分量 $g$ × 后窗 $h$：

| 判决 | 条件 |
|------|------|
| **Spike 制度成立** | $\Delta$ 的 95% CI 排除 0，FDR 控制后 $q<0.10$，且跨品种保留率 ≥ 70%（见 §5.2） |
| **方向敏感** | 只在多/空某一方向上成立（可能是品种或时段结构性偏差） |
| **阈值型** | 只在 $z_0\ge z_*$ 出现，五分位图上呈非线性跳变 |
| **线性型** | 五分位图单调，$\Delta$ 随 $z_0$ 近似线性 |
| **无差异** | CI 含 0 或跨品种保留率 < 50% |

### 5.2 跨品种保留率

按品种前缀（`m, rb, cu, ...`）分组，在每组独立重算 $\Delta_g^{(p)}(h)$；保留率

$$
\text{retention}_g(h) := \frac{1}{P}\sum_{p=1}^{P}\mathbf{1}\{\operatorname{sign}(\Delta_g^{(p)})=\operatorname{sign}(\Delta_g)\}
$$

只有 sign 一致（不要求显著）才计入保留。这是 quant-research-methodology §10.3 区分"制度依赖"与"过拟合"的关键。

### 5.3 与 confounder 的正交性

成交量 spike 与**波动率制度**天然相关（放量日常伴高 ATR）。为避免把"高波动制度"误判为"成交量 spike 效应"，必须做：

1. **二维拆分**：按 (ATR rank 3-way × spike/baseline) 拆 6 格，在每个 ATR 档内重算 $\Delta$；
2. **ATR 匹配对照**：从 baseline 组中为每个 spike 事件按 ATR 最近邻匹配 1–3 个对照（caliper ≤ 0.1 ATR rank），做 paired 检验；
3. 报告**两种对照下结论是否一致**——若 ATR 匹配后 $\Delta$ 消失，则原效应来自波动率制度而非成交量本身。

---

## 6. 适用边界与反例

- **非半鞅 / fBm 情形**：若 spike 后 $H$ 显著偏离 0.5，GMB barrier 闭式失效，结论需用 `factor-filtering-and-dgp-boundary` §6 的非半鞅分支处理；
- **Regime-switching 情形**：若 spike 触发的是状态切换（后窗 $\sigma$ 出现双模态），按该定理 §6 的 switching 分支，不能用单一 $b_A$ 常数近似；
- **过夜 / 换月**：1h bar 跨 session 边界时，后窗累计必须处理交易时段跳空；建议**事件后窗不跨交易日**，跨日的 $h$ 拆成"日 session 内累计 + 隔夜"两段报告；
- **合约寿命**：每合约至少 60 个交易日（~420 根 1h bar）才纳入，否则 rolling 统计样本不足。

---

## 7. 输出规格

### 7.1 事件级长表（CSV/Parquet）

每行一个事件：

```
contract, prefix, session_date, t, Z_t, r_t, entry_price, entry_atr,
h, r_h, sigma_h, absr_h, H_h,
barrier_id, side, hit, tau_bars, exit_reason
```

### 7.2 聚合表（Markdown / JSON）

每个 $(z_0, h, g, \text{container}, \text{side})$：

```
n_events, n_clusters, mean_spike, mean_baseline, delta,
ci_lo, ci_hi, p_two_sided, q_bh, retention_by_prefix
```

### 7.3 图（可选，研究阶段）

- $Z$ 五分位图：各 $g(h)$ 随 quintile 的变化；
- $\Delta_g(h)$ 随 $h$ 衰减曲线（spike 效应记忆期）；
- 二维 ATR × spike 热力图。

---

## 8. 未决项（r1.5 阶段更新）

1. ~~是否对成交量做去时段化？~~ **r1.5 已采用同时段 z-score**（§2.1 修订）。
2. 是否区分**主动买/卖量**（tick 规则分类）？1h K 线无 direction，需要更细粒度数据，r1 不做。
3. Spike 方向（spike bar 收阳/收阴）是否单独分层？r1 在 §4.2 signed 检验里处理，不单独切。
4. 阈值 $z_0$ 与后窗 $h$ 是否数据驱动选择？r1 只扫描固定网格，不用优化器选（避免过拟合）。
5. 同时段口径下极端档（4σ/5σ）的实际命中率待 Stage 3 重测；r1 的 Stage 0 数字基于全时段口径，不再适用。
