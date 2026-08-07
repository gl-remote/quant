# 因子定义：ATR 跨周期波动比

> 因子库条目 · atr-cross-timeframe-ratio
> 日期：2026-08-07
> 状态：已归档（描述性/风险因子，不是独立 alpha）
> 适用：商品期货 1h/15m；可扩展到 5m/1h、1h/日线
> 原始研究：[workbench/atr-timeframe-ratio/](../../../../docs/research/workbench/atr-timeframe-ratio/)
>   - [quadrant-profile.md](../../../../docs/research/workbench/atr-timeframe-ratio/quadrant-profile.md)
>   - [transition-paths.md](../../../../docs/research/workbench/atr-timeframe-ratio/transition-paths.md)
>   - [archive/h_only_signal_research/](../../../../docs/research/workbench/atr-timeframe-ratio/archive/h_only_signal_research/)（证伪记录）
>
> 本文件只承载可直接编码的数学定义。证据数字见 `evidence.md`，失效条件见 `boundary.md`。

---

## 0. 符号约定

| 符号 | 含义 |
|---|---|
| $H_t$ | 1h K 线在 $t$ 时刻的 Wilder ATR(14) |
| $L_t$ | 15m K 线在 $t$ 时刻的 Wilder ATR(56)（时钟对齐到 14 小时） |
| $H^{\text{long}}_t$ | 1h Wilder ATR(50)（约 1 周） |
| $L^{\text{long}}_t$ | 15m Wilder ATR(200)（约 50 小时） |
| $C_t$ | 1h 收盘价 |
| $S_H = H/H^{\text{long}}$ | 1h 短长 ATR 比 |
| $S_L = L/L^{\text{long}}$ | 15m 短长 ATR 比 |

时钟对齐：15m ATR 使用 56 根（56 × 15 分钟 = 14 小时 = 14 根 1h），不是 bar 对齐的 14 根。bar 对齐口径噪声大、对未来波动预测力差一个量级，不建议使用。

---

## 1. 核心因子

### 1.1 跨周期 ATR 比值（R_bar）

$$
\boxed{\;R_t = \frac{H_t}{L_t}\;}
$$

- 理论随机游走值 $\sqrt{4}=2.0$（1h 含 4 个 15m）；
- 实证中位数 **1.82**，系统性低于理论值（波动聚集导致长周期 ATR 相对偏大）；
- 半衰期约 **3.2 根 1h**（强均值回归）；
- 对未来波动率幅度预测力弱（corr 0.05），主要价值在状态分类。

### 1.2 同周期短长比（S_H, S_L）

$$
S_{H,t} = \frac{H_t}{H^{\text{long}}_t}, \qquad S_{L,t} = \frac{L_t}{L^{\text{long}}_t}
$$

用于判断每个周期是在扩张还是收缩。

---

## 2. 四象限状态分类

$$
\text{state}_t =
\begin{cases}
\text{co\_compress} & S_H < 1 \wedge S_L < 1 \\
\text{H\_only} & S_H \ge 1 \wedge S_L < 1 \\
\text{L\_only} & S_H < 1 \wedge S_L \ge 1 \\
\text{co\_expand} & S_H \ge 1 \wedge S_L \ge 1
\end{cases}
$$

| 状态 | 含义 | 全周期占比 |
|---|---|---:|
| co_compress | 双周期压缩（平静期） | 51.6% |
| H_only | 高周期独扩（宏观信息先动） | 8.1% |
| L_only | 低周期独扩（短周期脉冲） | 6.7% |
| co_expand | 共振扩张（趋势/事件） | 33.6% |

---

## 3. 辅助因子

### 3.1 归一化波动率（H_norm）

$$
H^{\text{norm}}_t = H_t / C_t
$$

这是预测未来波动率的**主要因子**，重要性远高于 R_bar：

- corr(H_norm, \|fwd_ret_20\|) = **0.43**（全周期）
- corr(R_bar, \|fwd_ret_20\|) = 0.05

### 3.2 已实现波动率（rv_20）

$$
\text{rv20}_t = \text{std}\left(\left\{\frac{C_{t-j}}{C_{t-j-1}} - 1\right\}_{j=0}^{19}\right)
$$

20 根 1h 收益率滚动标准差，对未来波动率 corr ≈ 0.38。

### 3.3 日级跨期限比值（R_1h_d，F 组）

$$
R^{1h,d}_t = \frac{D_t}{H^{\text{clock}}_t}
$$

其中 $D_t$ 是日线 Wilder ATR(14)（由 1h 聚合），$H^{\text{clock}}_t$ 是 1h ATR(168)（约 7 天，时钟对齐）。

- 理论值 $\sqrt{6}\approx 2.45$（1 天约 6 根 1h）；
- 实证中位数 2.56，略高于理论值；
- 方向信号已被证伪（在熊市翻转），但作为长周期波动状态标签可用。

### 3.4 路径标签（path_type）

对每段 co_compress，追踪其后 60 根：

| path_type | 定义 |
|---|---|
| H_path | co_compress → H_only → co_expand |
| L_path | co_compress → L_only → co_expand |
| direct | co_compress → co_expand（无独扩过渡） |
| no_expand | 60 根内未到共振 |

这是事件型标签，不是每根 bar 的连续因子。

---

## 4. 响应变量

### 4.1 前向波动率

$$
|r^{(h)}_t| = \left|\frac{C_{t+h}}{C_t} - 1\right|, \qquad h \in \{5, 20, 60\}
$$

### 4.2 前向方向收益（仅用于检验，不用于信号）

$$
r^{(h)}_t = \frac{C_{t+h}}{C_t} - 1
$$

所有方向收益的"显著性"在 2022–2023 熊市数据上均失效，详见 boundary.md。

---

## 5. 实现参考

| 组件 | 脚本 |
|---|---|
| 因子计算（15m/1h） | `workbench/atr-timeframe-ratio/scripts/profile_quadrants_full.py` |
| 5m/15m/1h 多周期对比 | `workbench/atr-timeframe-ratio/scripts/compare_5m_15m.py` |
| F 组跨期限结构 | `workbench/atr-timeframe-ratio/scripts/term_structure.py` |
| 路径识别 | `workbench/atr-timeframe-ratio/scripts/transition_paths.py` |
| 熊市数据下载 | `workbench/atr-timeframe-ratio/scripts/fetch_bear_market.py` |

输入数据：TQSDK 商品期货 1h/15m K 线 CSV，列 `datetime, open, high, low, close, volume, open_oi`。
