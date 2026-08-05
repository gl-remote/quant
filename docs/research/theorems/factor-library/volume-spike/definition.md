# 因子定义：成交量放量与均线偏离

> 因子库条目 · volume-spike
> 日期：2026-08-05
> 状态：已归档（经验确认，但不建议作为独立 alpha）
> 适用：商品期货 1h；适合作为已有趋势策略的减仓/止盈过滤器，不适合裸空或反转开仓
> 原始研究：[volume-spike-trend-exhaustion-1h-daily-findings.md](../../../archived-notes/2026/08/2026-08-05-volume-spike-regime-shift/volume-spike-trend-exhaustion-1h-daily-findings.md)、[volume-as-factor-conditioner.md](../../../archived-notes/2026/08/2026-08-05-volume-spike-regime-shift/volume-as-factor-conditioner.md)、[volume-spike-skew-spec.md](../../../archived-notes/2026/08/2026-08-05-volume-spike-regime-shift/volume-spike-skew-spec.md)
>
> 本文件只承载可直接编码的数学定义。证据数字见 `evidence.md`，失效条件见 `boundary.md`。

---

## 0. 符号约定

| 符号 | 含义 |
|---|---|
| $t$ | 当前 1h bar 索引（信号触发 bar） |
| $C_t, V_t$ | 第 $t$ 根 1h bar 的收盘价、成交量 |
| $h(t)$ | bar $t$ 的小时标签（hour-of-day，用于同时段分组） |
| $r_t = \log(C_t / C_{t-1})$ | 1h 对数收益 |
| $N=20$ | 同时段 z-score 的 lookback |
| $H=100$ | 信号后窗（约 20 个交易日） |
| $L=120$ | 长期均线长度（约 24 个交易日） |
| $W=15$ | volume profile 窗口长度（小时） |
| $B=50$ | volume profile 价格桶数 |

---

## 1. 同时段成交量 z-score（Volume Spike）

### 1.1 定义

对每个 1h bar，用**相同 hour-of-day** 的历史成交量计算 z-score：

$$
Z_t = \frac{V_t - \mu^{(h)}_t}{\sigma^{(h)}_t}
$$

$$
\mu^{(h)}_t = \frac{1}{N}\sum_{j=1}^{N} V_{t-j}\,\mathbf{1}_{\{h(t-j)=h(t)\}}, \qquad
(\sigma^{(h)}_t)^2 = \frac{1}{N-1}\sum_{j=1}^{N} \left(V_{t-j}-\mu^{(h)}_t\right)^2\mathbf{1}_{\{h(t-j)=h(t)\}}
$$

$N=20$，求和只取与 $t$ 相同时段的历史 bar。

### 1.2 为什么必须同时段

商品期货有强日内时段效应（09:00/21:00 开盘成交量显著大于盘中）。全时段 rolling z 会把开盘 bar 系统性标记为 spike（75% 的 $Z\ge2$ 事件集中在开盘 bar），实质是"开盘效应"代理（KF-1）。

### 1.3 离散分组

| 组 | 条件 |
|---|---|
| 缩量 | $Z_t < -0.5$ |
| 正常 | $\lvert Z_t\rvert < 0.5$ |
| 放量 | $1.5 \le Z_t < 2.5$ |
| 极端放量 | $Z_t \ge 2.5$ |

阈值 0.5–1.5 之间为过渡带，不参与分组。

---

## 2. 事前市场强度 $s_{\text{pre}}$

信号触发前 100 根 1h bar 的 per-bar Sharpe（对数收益均值/标准差）：

$$
s_{\text{pre}} = \frac{\frac{1}{100}\sum_{j=1}^{100} r_{t-j}}
{\sqrt{\frac{1}{99}\sum_{j=1}^{100}(r_{t-j}-\bar r)^2}}
$$

**样本选择条件，不是预测变量。** 分层：

| 层 | 条件 | 含义 |
|---|---|---|
| 高 s_pre | $s_{\text{pre}} \ge +0.10$ | 已上涨的强趋势 |
| 中 s_pre | $-0.10 < s_{\text{pre}} < +0.10$ | 震荡/弱趋势 |
| 低 s_pre | $s_{\text{pre}} \le -0.10$ | 已下跌的强趋势 |

控制 MADEV 后 $s_{\text{pre}}$ 残差 IC 翻正（+0.24），它不是趋势耗尽的驱动变量（KF-28）。

---

## 3. 价格偏离均线 MADEV

价格相对长期简单移动平均的算术偏离：

$$
\text{MADEV}^{(L)}_t = \frac{C_t - \text{MA}^{(L)}_t}{\text{MA}^{(L)}_t}, \qquad
\text{MA}^{(L)}_t = \frac{1}{L}\sum_{j=0}^{L-1} C_{t-j}
$$

主规格 $L=120$。这是因子库的**核心预测变量**——30 个常见技术因子（MRET、RSI、PARK、VWAP_DEV、OBV 等）的成交量条件翻转都是 MADEV 一个维度的投影（KF-24）。

注意：
- 用算术偏离而非 $\log(C_t/\text{MA}_t)$，是因为它直接对应策略里的"价格离均线百分之几"；
- $L=200$ 在缩量端 IC 更高（+0.51 vs $L=120$ 的 +0.20），但当前数据样本量限制，主规格仍用 $L=120$。

---

## 4. 成交量分布偏度 Volume Profile Skew

### 4.1 时间窗

对信号 bar $t$，取信号 bar 之前 14 小时至信号 bar 结束的 1m 数据，共 $W=15$ 小时：

$$
\mathcal{W}_t = \{\tau : t_{\text{start}} \le \tau \le t_{\text{end}}\}, \qquad
t_{\text{end}} = t + 1\text{h}, \quad t_{\text{start}} = t - 14\text{h}
$$

即窗口覆盖 $[t-14\text{h}:00,\ t+1\text{h}:00]$。窗口包含信号 bar 本身及其结束时刻；用于判断信号发生时最近 15 小时的成交量分布。若要构造严格事前信号，应把右边界改为信号 bar 开始时刻，并重新验证。

### 4.2 volume-at-price 分布

对窗口内所有 1m bar（开高低收量为 $O_\tau, H_\tau, L_\tau, C_\tau, V^{(m)}_\tau$）：

1. 取窗口价格范围 $[P_{\min}, P_{\max}] = [\min_\tau L_\tau,\ \max_\tau H_\tau]$；
2. 分为 $B=50$ 个等宽价格桶，桶中心 $P_i = P_{\min} + (i+0.5)\Delta P$，$\Delta P = (P_{\max}-P_{\min})/B$；
3. 对每个 1m bar，找到其价格触及的桶集合：
   $$\mathcal{I}_\tau = \{i : [P_i-\Delta P/2,\ P_i+\Delta P/2] \cap [L_\tau, H_\tau] \neq \emptyset\}$$
4. **按触及桶数平均分配**（不是按价格区间覆盖长度加权）：
   $$v_i = \sum_{\tau:\, i\in\mathcal{I}_\tau} \frac{V^{(m)}_\tau}{|\mathcal{I}_\tau|}$$

一字 bar（$H_\tau = L_\tau$）直接累加到对应桶。这是无 tick 数据时的标准近似；有逐笔成交后应按实际成交价分配。

### 4.3 VWAP 与加权矩

$$
\text{VWAP}_t = \mu_v = \frac{\sum_i P_i v_i}{\sum_i v_i}
$$

$$
\sigma_v = \sqrt{\frac{\sum_i v_i (P_i - \mu_v)^2}{\sum_i v_i}}
$$

### 4.4 成交量加权偏度（核心公式）

$$
\boxed{\;\text{Skew}_t = \frac{\sum_i v_i \left(\dfrac{P_i - \mu_v}{\sigma_v}\right)^3}{\sum_i v_i}\;}
$$

这是 Pearson 矩偏度的成交量加权版本。

**无条件几何含义**：
- $\text{Skew} > 0$：成交量集中在低位、高位有长尾；
- $\text{Skew} < 0$：成交量集中在高位、低位有长尾；
- $\text{Skew} \approx 0$：分布对称。

**方向解释依赖 s_pre regime**（不能单独使用）：
- 高 s_pre 上涨趋势中：**负偏 + 放量**最看跌（高位派发，mean $-2.22\%$，13% 上涨）；
- 非高 s_pre 中：**正偏 + 极端放量**偏看涨（低位承接，76% 上涨）。

### 4.5 辅助指标

**POC（Point of Control）**：成交量最大的桶：
$$\text{POC}_t = P_{i^*}, \quad i^* = \arg\max_i v_i$$

**Value Area（70%）**：按 $v_i$ 降序贪心纳入桶，直到累计成交量达到总量的 70%：
$$\sum_{i \in \mathcal{A}_t} v_i \ge 0.7\sum_i v_i$$
其中 $\mathcal{A}_t$ 按 $v_i$ 从大到小选取。注意此算法不保证价格区间连续，与传统 Market Profile 从 POC 向两侧相邻扩展不同。

**Balance**：VWAP 上下成交量之差：
$$\text{Balance}_t = \frac{\sum_{i:P_i>\mu_v} v_i - \sum_{i:P_i<\mu_v} v_i}{\sum_i v_i}$$
正值表示 VWAP 上方成交更多。

**DevClose**：信号 bar 收盘价相对 VWAP 的位置：
$$\text{DevClose}_t = \frac{C_t - \mu_v}{\mu_v}$$

---

## 5. 响应变量

信号触发后 $H$ 根 1h bar 的累计对数收益：

$$
R^{(H)}_t = \sum_{j=1}^{H} r_{t+j}
$$

主规格 $H=100$。同时在 $h \in \{20,40,60,80,100\}$ 测量中间 MADEV 以观察回归路径：

$$
\text{MADEV}^{(L)}_{t+h} = \frac{C_{t+h} - \text{MA}^{(L)}_{t+h}}{\text{MA}^{(L)}_{t+h}}
$$

---

## 6. 复合信号（用于 evidence.md）

### 6.1 高 s_pre 上涨趋势中的向下回归

$$
\mathbb{1}_{\text{sell-exhaustion}} =
\mathbf{1}\{s_{\text{pre}}\ge 0.10\}\cdot
\mathbf{1}\{Z_t\ge 2.5\}\cdot
\mathbf{1}\{\text{MADEV}^{(120)}_t \ge q_{0.67}\}
$$

### 6.2 低 s_pre 下跌趋势中的向上回归（镜像）

$$
\mathbb{1}_{\text{buy-rebound}} =
\mathbf{1}\{s_{\text{pre}}\le -0.10\}\cdot
\mathbf{1}\{Z_t\ge 2.5\}\cdot
\mathbf{1}\{\text{MADEV}^{(120)}_t \le q_{0.33}\}
$$

两个条件用的是同一种机制（放量 + 价格远离均线 → 向均线回归），方向由偏离方向决定。分位数 $q_{0.33}, q_{0.67}$ 在各自 s_pre 层内计算。

---

## 7. 实现参考

| 组件 | 脚本 |
|---|---|
| 同时段 z | `workbench/.../scripts/r2_mean_reversion.py`、`regime_split_1h.py` |
| MADEV / s_pre | 同上 |
| Volume Profile Skew | `workbench/.../scripts/volume_profile_skew.py` |
| 低 s_pre 镜像 | `workbench/.../scripts/low_s_rebound_test.py` |
| 消融实验 | `workbench/.../scripts/ablation_study.py` |

所有脚本归档在 `docs/research/archived-notes/2026/08/2026-08-05-volume-spike-regime-shift/raw-workbench/scripts/`。
