# Hurst 形状假设检验 · 实验设计与数据筛选方案

> **文档定位**：为 [hurst-shape-assumptions-testability.md](hurst-shape-assumptions-testability.md) 的假设检验提供**具体的数据处理与实验执行方案**。
>
> **关键约束**：本研究检验"高跨期波动率比值蕴含市场强度"，应**聚焦在高比值子样本**上，而非全样本。
>
> **数据基础**：复用 [ATR 跨周期比值研究](../archived-notes/2026/08/2026-08-07-atr-cross-timeframe-ratio/) 的已验证数据管道。
>
> **状态**：workbench 草稿 · 待执行。

---

## 目录

1. [研究目标回顾](#1-研究目标回顾)
2. [已有数据资产盘点](#2-已有数据资产盘点)
3. [核心筛选问题](#3-核心筛选问题)
4. [筛选策略设计](#4-筛选策略设计)
5. [样本独立性处理](#5-样本独立性处理)
6. [多尺度 H(τ) 估计方案](#6-多尺度-hτ-估计方案)
7. [成本参数校准](#7-成本参数校准)
8. [对照组设计](#8-对照组设计)
9. [实验执行计划](#9-实验执行计划)
10. [风险与陷阱](#10-风险与陷阱)
11. [输出清单](#11-输出清单)

---

## 1. 研究目标回顾

### 1.1 核心命题

[主定理](cross-timeframe-vol-ratio-implies-market-strength.md#4-主定理跨周期比值蕴含市场强度存在性)：

$$R(a, b) > \sqrt{b/a} \;\Longrightarrow\; \exists\, c \in (a, b): H(c) > \tfrac{1}{2}$$

### 1.2 检验目标

[hurst-shape-assumptions-testability.md](hurst-shape-assumptions-testability.md) 的 P0-P4 假设谱系，核心是回答：

> **在高 R 子样本中，H(τ) 的形状符合哪个假设？该假设下可盈利门槛 r* 是否有实测覆盖率？**

### 1.3 与之前研究的区别

| 维度 | ATR 跨周期比值研究（已归档） | 本研究 |
|------|--------------------------|--------|
| 关注点 | R_bar 的描述性统计、四象限画像 | H(τ) 曲线形状、可盈利门槛 |
| 样本 | 全样本（含低 R） | **聚焦高 R 子样本** |
| 周期 | 主要 15m/1h | 多尺度（1m-1d） |
| 输出 | 状态因子定位 | 假设可用性判定 |

---

## 2. 已有数据资产盘点

### 2.1 数据源

来自 [profile_quadrants_full.py](../archived-notes/2026/08/2026-08-07-atr-cross-timeframe-ratio/atr-timeframe-ratio/scripts/profile_quadrants_full.py)：

| 项目 | 值 |
|------|---|
| 数据目录 | `project_data/market_data/csv/` |
| 合约数 | 52 个（1h 口径） |
| 时间范围 | 2022-05-12 ~ 2026-04-01 |
| 总行数 | 33,996（1h 面板） |
| 周期 | 1h, 15m 已确认可用 |

### 2.2 R_bar 实测分布

来自 [full_profile_summary.json](../archived-notes/2026/08/2026-08-07-atr-cross-timeframe-ratio/atr-timeframe-ratio/outputs/profile_full/full_profile_summary.json) 和 [compare_summary.json](../archived-notes/2026/08/2026-08-07-atr-cross-timeframe-ratio/atr-timeframe-ratio/outputs/compare_5m_15m/compare_summary.json)：

| 指标 | R_15 (1h/15m) | R_5 (1h/5m) | GBM 基线 |
|------|--------------|------------|---------|
| 中位数 | 1.84 | 3.16 | 2.0 / 3.46 |
| 均值 | 1.85 | 3.25 | — |
| p05 | 1.56 | 2.43 | — |
| p95 | 2.19 | 4.39 | — |
| min | 1.22 | 1.49 | — |
| max | 2.77 | 11.26 | — |
| std | 0.19 | 0.65 | — |

**关键观察**：
- R_15 中位数 1.84 < 2.0 → 主流市场子扩散
- R_15 p95 = 2.19 > 2.0 → 约 5% 样本满足 $R > R_{\text{GBM}}$
- R_5 中位数 3.16 < 3.46 → 也子扩散，但 p95 = 4.39 远超基线

### 2.3 R_bar 时序特性

来自 [full_profile_summary.json](../archived-notes/2026/08/2026-08-07-atr-cross-timeframe-ratio/atr-timeframe-ratio/outputs/profile_full/full_profile_summary.json)：

| 指标 | 值 |
|------|---|
| ACF(1) 中位数 | 0.81 |
| 半衰期中位数 | 3.24 小时 |

**关键约束**：R_bar 高自相关 → 连续 bar 高度相关，**必须做非重叠抽样**（参见 §5）。

### 2.4 四象限分布

| 象限 | 占比 | R_bar 倾向 |
|------|------|-----------|
| co_compress | 51.6% | 低（双压缩） |
| H_only | 8.1% | 中高 |
| L_only | 6.7% | 中低 |
| co_expand | 33.6% | **高（双扩张）** |

**关键约束**：co_expand 占 33.6% 但不一定都满足 $R > R_{\text{GBM}}$——需用 R_bar 阈值精确筛选，不能简单按象限。

### 2.5 可用周期数据确认

| 周期 | 数据可用性 | 来源 |
|------|-----------|------|
| 1m | 部分（33 合约，2025-05~09） | volume-spike 研究 |
| 5m | 是（32 合约，2024-01~2026-04） | compare_5m_15m |
| 15m | 是（52 合约，2022-05~2026-04） | profile_quadrants_full |
| 30m | 待确认 | 需 glob 检查 |
| 1h | 是（52 合约） | profile_quadrants_full |
| 2h | 待确认 | 需 glob 检查 |
| 4h | 待确认 | 需 glob 检查 |
| 1d | 是（推断） | 通常有 |

**第一步执行**：用 glob 确认 30m, 2h, 4h, 1d 数据可用性。

---

## 3. 核心筛选问题

### 3.1 为什么要筛选高 R 子样本？

本研究检验"**高 R 蕴含市场强度**"。若用全样本（含大量低 R 子样本），会：

1. **稀释信号**：低 R 子样本的 $H(\tau) < 1/2$，与高 R 子样本混合后形状假设检验失效；
2. **扭曲 Lipschitz 常数**：低 R 时段 $H(\tau)$ 可能更不稳定，拉高 $\hat{L}$；
3. **门槛无意义**：在低 R 子样本上算 $r^\ast$ 覆盖率，结论无价值。

### 3.2 筛选的两难

| 策略 | 优点 | 缺点 |
|------|------|------|
| 严格阈值（R > 2.0） | 信号纯净 | 样本少（~5%） |
| 宽松阈值（R > 1.8） | 样本多 | 含大量非高 R |
| 分位数（R > p75） | 自适应 | 阈值不固定，难跨研究比较 |
| 象限筛选（co_expand） | 与已有研究衔接 | 不精确（co_expand 内 R 分布宽） |

### 3.3 推荐策略：分层筛选

**主分析**：R_15 > 2.0（严格 GBM 基线）
- 物理含义清晰：$R > R_{\text{GBM}}$ 触发主定理
- 预期样本量：约 5% × 33996 ≈ 1700 行（1h 口径）
- 非重叠后：约 1700 / 4 ≈ 425 独立样本（按 4h 间隔）

**敏感性分析**：R_15 > 1.9, 1.95, 2.05, 2.10
- 检验结论对阈值的稳健性

**对照组**：R_15 < 1.6（明确低 R）
- 预期样本量：约 5%
- 用于对比 H(τ) 形状差异

---

## 4. 筛选策略设计

### 4.1 筛选维度

筛选应同时考虑：

1. **R_bar 水平**：主筛选维度
2. **时间独立性**：非重叠抽样（§5）
3. **数据完整性**：多尺度数据齐全
4. **品种代表性**：避免单一品种主导

### 4.2 主筛选方案

```python
# 伪代码
R_GBM_15 = 2.0  # 1h/15m 的 GBM 基线

# 主分析组
high_R = panel[panel["R_bar"] > R_GBM_15]

# 对照组
low_R = panel[panel["R_bar"] < 1.6]

# 敏感性分析组
for threshold in [1.9, 1.95, 2.05, 2.10]:
    subset = panel[panel["R_bar"] > threshold]
```

### 4.3 筛选后的样本量预估

基于 R_15 分布（中位 1.84, p95 2.19）：

| 阈值 | 预期占比 | 预期样本（1h） | 非重叠后（4h 间隔） |
|------|---------|---------------|-------------------|
| R > 1.6 | ~5% | 1,700 | 425 |
| R > 1.8 | ~50% | 17,000 | 4,250 |
| R > 1.9 | ~25% | 8,500 | 2,125 |
| R > 2.0 | ~5% | 1,700 | 425 |
| R > 2.1 | ~2% | 680 | 170 |
| R > 2.2 | ~1% | 340 | 85 |

**推荐**：主分析用 R > 2.0（425 独立样本，足够统计检验），敏感性分析扩展到 1.9-2.1。

### 4.4 品种均衡

检查 high_R 子样本的品种分布，避免单一品种主导：

```python
# 检查每个品种在 high_R 中的占比
symbol_dist = high_R["symbol"].value_counts(normalize=True)
# 若某品种占比 > 30%，考虑分品种分析或加权
```

### 4.5 时间均衡

检查 high_R 的时间分布，避免集中在某段时间：

```python
# 检查 high_R 的月份分布
month_dist = high_R.groupby("year_month").size()
# 若集中在某几个月，需在结论中说明
```

---

## 5. 样本独立性处理

### 5.1 问题

R_bar 的 ACF(1) = 0.81，半衰期 3.24 小时。连续 1h bar 的高度相关会导致：

1. 有效样本量虚高（1700 行实际可能只等价于 400 独立样本）
2. 假设检验的 p 值偏小（过度拒绝）
3. Lipschitz 常数估计偏差

### 5.2 非重叠抽样方案

**方案 A：固定间隔抽样**

```python
# 每 4 小时取一个样本（约等于半衰期 + 1h）
# 52 合约 × 4 年 × 250 交易日 × 6 样本/日 ≈ 312,000 → 太多
# 实际 high_R 子样本约 1700 行，4h 间隔后约 425 独立样本
```

**方案 B：状态触发抽样**

只在 R_bar **穿越阈值**时取样（首次进入 high_R 状态）：

```python
# 伪代码
high_R_events = []
for symbol in symbols:
    sym_panel = panel[panel["symbol"] == symbol].sort_values("datetime")
    sym_panel["is_high"] = sym_panel["R_bar"] > R_GBM
    # 找穿越点：前一根不满足，当前根满足
    crossings = sym_panel[(~sym_panel["is_high"].shift(1, fill_value=False)) & sym_panel["is_high"]]
    high_R_events.append(crossings)
```

**推荐方案 B**：状态触发抽样更符合事件研究范式，且天然非重叠。

### 5.3 最小间隔约束

即使状态触发抽样，仍需约束两次事件间的最小间隔（避免快速来回穿越）：

```python
MIN_GAP = 8  # 8 小时，约 2 个半衰期
# 两次事件间至少间隔 8 小时
```

### 5.4 预期独立样本量

基于状态转换矩阵（[full_profile_summary.json](../archived-notes/2026/08/2026-08-07-atr-cross-timeframe-ratio/atr-timeframe-ratio/outputs/profile_full/full_profile_summary.json)）：

- co_compress → co_expand 直接转换概率 1.1%（很低）
- 但通过 H_only / L_only 中转的路径更多
- 估算：52 合约 × 4 年 × 250 交易日 × 0.5% 转换率 ≈ 260 事件

**风险**：严格 R > 2.0 的事件可能不足 200 个。需在敏感性分析中放宽到 R > 1.9。

---

## 6. 多尺度 H(τ) 估计方案

### 6.1 尺度网格

为覆盖 $c = 5\text{m}, 15\text{m}$ 的定位需求，尺度网格应包含：

| 尺度 | $\tau$（分钟） | $\ln \tau$ | 数据可用性 |
|------|---------------|-----------|-----------|
| 1m | 1 | 0 | 部分 |
| 5m | 5 | 1.61 | 是 |
| 15m | 15 | 2.71 | 是 |
| 30m | 30 | 3.40 | 待确认 |
| 1h | 60 | 4.09 | 是 |
| 2h | 120 | 4.79 | 待确认 |
| 4h | 240 | 5.48 | 待确认 |
| 1d | 1440 | 7.27 | 是 |

### 6.2 σ_τ 估计

对每个尺度 $\tau$，用滚动窗口估计 $\sigma_\tau$：

$$\sigma_\tau(t) = \text{std}\left(\left\{\ln\frac{C_{t-j\tau}}{C_{t-(j+1)\tau}}\right\}_{j=0}^{N-1}\right)$$

- $N = 50$（50 个 $\tau$-bar 的滚动窗口）
- 对齐到 1h 时间戳（用 `merge_asof` backward）

### 6.3 H(τ) 估计

**区间平均法**（推荐，与 R_bar 同源）：

$$\overline{H}(\tau_i, \tau_{i+1}) = \frac{\ln(\sigma_{\tau_{i+1}} / \sigma_{\tau_i})}{\ln(\tau_{i+1} / \tau_i)}$$

**中心差分法**（更平滑，但需 3 个点）：

$$H(\tau_i) \approx \frac{\ln \sigma_{\tau_{i+1}} - \ln \sigma_{\tau_{i-1}}}{\ln \tau_{i+1} - \ln \tau_{i-1}}$$

### 6.4 数据对齐

所有尺度的 $\sigma_\tau$ 对齐到 1h 时间戳：

```python
# 伪代码
base = df_1h[["datetime", "close"]]
for tau in [5, 15, 30, 60, 120, 240, 1440]:
    df_tau = load(tau)
    df_tau["sigma_tau"] = df_tau["log_ret"].rolling(50).std()
    base = pd.merge_asof(base, df_tau[["datetime", "sigma_tau"]], 
                         on="datetime", direction="backward",
                         suffixes=("", f"_{tau}"))
```

### 6.5 尺度范围选择

**主分析**：5m - 1h（$\tau_1 = 5, \tau_2 = 60$）
- GBM 基线：$\sqrt{60/5} = \sqrt{12} \approx 3.46$
- 几何中点：$\sqrt{5 \times 60} \approx 17.3\text{m}$（接近 15m）
- 与已有 R_5 数据衔接

**扩展分析**：5m - 4h
- GBM 基线：$\sqrt{240/5} = \sqrt{48} \approx 6.93$
- 几何中点：$\sqrt{5 \times 240} \approx 34.6\text{m}$
- 覆盖更宽尺度，但需 4h 数据

---

## 7. 成本参数校准

### 7.1 需要校准的参数

可盈利门槛 $r^\ast = (b/a)^{H^\ast(c)}$ 依赖：

$$H^\ast(c) = \tfrac{1}{2} + \tfrac{1}{2} \log_2\!\left(1 + \sin\!\left(\pi \, \delta^\ast(c)\right)\right)$$

$$\delta^\ast(c) = \frac{x_{\min} \sqrt{c}}{\sqrt{2\pi}}$$

$$x_{\min} = \sqrt{\frac{6 c_{\text{cost}}}{K_S^3 R(R-1)}}$$

需校准：$c_{\text{cost}}, K_S, R = K_T / K_S$。

### 7.2 校准来源

| 参数 | 校准方法 | 数据源 |
|------|---------|--------|
| $c_{\text{cost}}$ | 单边手续费 + 滑点，以 ATR 计 | 各品种合约规格 |
| $K_S$ | 止损距离，以 ATR 计 | 历史回测或经验值（如 1.5 ATR） |
| $R$ | 盈亏比 | 策略假设（如 R=2） |

### 7.3 基准参数集

参考 [when-barrier §2.4](../theorems/structural-shaping-alpha/when-barrier-shaping-yields-alpha.md) 的 ATR 归一化约定：

| 参数 | 基准值 | 来源 |
|------|--------|------|
| $c_{\text{cost}}$ | 0.1 ATR（单边） | 商品期货经验值 |
| $K_S$ | 1.5 ATR | 保守止损 |
| $R$ | 2.0 | 2:1 盈亏比 |

代入：

$$x_{\min} = \sqrt{\frac{6 \times 0.1}{1.5^3 \times 2 \times 1}} = \sqrt{\frac{0.6}{6.75}} \approx 0.298$$

$$\delta^\ast(15\text{m}) = \frac{0.298 \times \sqrt{15}}{\sqrt{2\pi}} \approx \frac{0.298 \times 3.87}{2.51} \approx 0.46$$

注意：$\delta^\ast = 0.46$ 已接近 $\delta$ 的理论上界 0.5（对应 $H \to \infty$），说明基准参数下可盈利门槛很高。

### 7.4 敏感性分析

需对 $c_{\text{cost}}, K_S, R$ 做敏感性分析：

```python
param_grid = {
    "c_cost": [0.05, 0.1, 0.2],  # ATR
    "K_S": [1.0, 1.5, 2.0],       # ATR
    "R": [1.5, 2.0, 3.0],         # 盈亏比
}
```

---

## 8. 对照组设计

### 8.1 对照组的必要性

单一高 R 组无法验证"高 R 蕴含高 H"——需要对比证明因果关系。

### 8.2 对照组方案

| 组别 | 筛选条件 | 预期 H(τ) | 作用 |
|------|---------|----------|------|
| 高 R 组 | R_15 > 2.0 | $H > 1/2$（主定理预测） | 验证主定理 |
| 低 R 组 | R_15 < 1.6 | $H < 1/2$ | 反向验证 |
| 中 R 组 | 1.8 < R_15 < 2.0 | $H \approx 1/2$ | 过渡带 |

### 8.3 配对设计

为控制品种和时间效应，做**品种内配对**：

```python
# 伪代码
for symbol in symbols:
    sym_panel = panel[panel["symbol"] == symbol]
    high_events = sym_panel[sym_panel["R_bar"] > 2.0]
    # 为每个 high_event 找最近的 low_event（同品种，时间相近）
    for event in high_events:
        matched = sym_panel[
            (sym_panel["R_bar"] < 1.6) &
            (abs(sym_panel["datetime"] - event["datetime"]) < timedelta(days=30))
        ]
```

---

## 9. 实验执行计划

### 9.1 Step 0：数据可用性确认（前置）

```bash
# 确认 30m, 2h, 4h, 1d 数据
ls project_data/market_data/csv/*.30m.csv | wc -l
ls project_data/market_data/csv/*.2h.csv | wc -l
ls project_data/market_data/csv/*.4h.csv | wc -l
ls project_data/market_data/csv/*.1d.csv | wc -l
```

### 9.2 Step 1：构建多尺度面板

脚本：`step1_multiscale_panel.py`

1. 加载所有可用周期数据
2. 每个周期计算 $\sigma_\tau$（50 bar 滚动窗口）
3. 对齐到 1h 时间戳
4. 计算区间平均 $\overline{H}(\tau_i, \tau_{i+1})$ 和中心差分 $H(\tau_i)$
5. 输出：`multiscale_panel.parquet`

### 9.3 Step 2：R_bar 筛选与事件提取

脚本：`step2_filter_and_events.py`

1. 加载多尺度面板
2. 计算 R_15（1h/15m）
3. 按阈值筛选（R > 2.0, 1.9, 1.8, < 1.6）
4. 状态触发抽样（首次穿越阈值）
5. 最小间隔约束（8h）
6. 输出：`high_R_events.parquet`, `low_R_events.parquet`

### 9.4 Step 3：P0 恒定 H 检验

脚本：`step3_test_P0.py`

1. 对 high_R_events 的每个事件，提取多尺度 $H(\tau_i)$
2. 检验子区间 $\overline{H}$ 是否为常数
3. Friedman 检验（多相关样本）
4. 输出：`P0_results.json`

### 9.5 Step 4：P1 Lipschitz 检验

脚本：`step4_test_P1.py`

1. 对每个事件，计算 Lipschitz 比 $\lambda_{ij}$
2. 取 $\hat{L} = \max \lambda_{ij}$
3. 检验 $\hat{L}$ 的分布
4. 检验 $\hat{L}$ 的跨品种稳定性
5. 计算可盈利门槛 $r^\ast = (b/a)^{H^\ast + \hat{L} d(c)}$
6. 检验实测 $r$ 覆盖 $r^\ast$ 的比例
7. 输出：`P1_results.json`

### 9.6 Step 5：P2 单调性检验

脚本：`step5_test_P2.py`

1. 对每个事件，提取 $H(\tau_i)$ 序列
2. 计算 Spearman $\rho$
3. 检验单调性和方向一致性
4. 输出：`P2_results.json`

### 9.7 Step 6：综合决策

脚本：`step6_decision.py`

1. 汇总 P0-P2 结果
2. 按 [hurst-shape-assumptions-testability.md §11](hurst-shape-assumptions-testability.md#11-决策流程) 决策流程判定
3. 输出：`decision_summary.json`, `decision_report.md`

---

## 10. 风险与陷阱

### 10.1 样本量风险

**风险**：严格 R > 2.0 的事件可能不足 200 个，统计功效不足。

**缓解**：
- 主分析用 R > 1.9（预期样本量翻倍）
- 报告效应大小（effect size）而非仅 p 值
- 用 bootstrap 估计置信区间

### 10.2 选择偏差

**风险**：只选高 R 子样本可能引入选择偏差——高 R 时段可能有特殊的市场微结构。

**缓解**：
- 对照组设计（§8）
- 报告高 R 子样本的品种/时间分布
- 在结论中说明选择偏差的潜在影响

### 10.3 多重检验

**风险**：对 P0, P1, P2 同时检验，增加第一类错误。

**缓解**：
- Bonferroni 校正
- 或按层级检验（先 P0，拒后 P1，再 P2）

### 10.4 尺度范围选择偏差

**风险**：H(τ) 的形状依赖尺度范围选择。窄范围（5m-1h）可能单调，宽范围（1m-1d）可能不单调。

**缓解**：
- 主分析用 5m-1h（与 c=15m 定位需求一致）
- 扩展分析用 1m-1d（检验形状稳健性）
- 报告不同尺度范围的结果

### 10.5 R_bar 估计噪声

**风险**：R_bar 用 Wilder ATR(14) 估计，有估计噪声。R = 2.0 附近的样本可能因噪声误分类。

**缓解**：
- 用更长的 ATR 窗口（如 50）做稳健性检验
- 报告 R_bar 的估计标准误
- 在 R = 2.0 ± 0.05 的边界带做敏感性分析

### 10.6 时变性

**风险**：H(τ) 时变，单次估计可能不代表整个高 R 时段。

**缓解**：
- 在事件后多时点估计 H(τ)（如 0h, 4h, 8h, 12h）
- 报告 H(τ) 的时变路径

---

## 11. 输出清单

### 11.1 数据文件

| 文件 | 内容 |
|------|------|
| `multiscale_panel.parquet` | 多尺度面板（所有品种，所有尺度） |
| `high_R_events.parquet` | 高 R 事件（状态触发抽样） |
| `low_R_events.parquet` | 低 R 事件（对照组） |

### 11.2 结果文件

| 文件 | 内容 |
|------|------|
| `P0_results.json` | P0 检验结果 |
| `P1_results.json` | P1 检验结果（含 $\hat{L}$ 分布） |
| `P2_results.json` | P2 检验结果 |
| `decision_summary.json` | 综合决策 |
| `decision_report.md` | 可读报告 |

### 11.3 图表

| 图 | 内容 |
|----|------|
| `fig1_H_curve_high_vs_low.png` | 高 R vs 低 R 的 H(τ) 曲线对比 |
| `fig2_Lipschitz_dist.png` | $\hat{L}$ 的分布 |
| `fig3_rstar_coverage.png` | $r^\ast$ 门槛与实测 $r$ 的覆盖关系 |
| `fig4_H_by_quadrant.png` | 四象限内的 H(τ) 分布 |
| `fig5_timeseries_H.png` | H(τ) 的事件后时变路径 |

---

## 附录 · 与已有脚本的关系

| 已有脚本 | 复用内容 | 本研究新脚本 |
|---------|---------|------------|
| [profile_quadrants_full.py](../archived-notes/2026/08/2026-08-07-atr-cross-timeframe-ratio/atr-timeframe-ratio/scripts/profile_quadrants_full.py) | Wilder ATR、面板构建、象限分类 | step1, step2 |
| [compare_5m_15m.py](../archived-notes/2026/08/2026-08-07-atr-cross-timeframe-ratio/atr-timeframe-ratio/scripts/compare_5m_15m.py) | 5m 数据加载、R_5 计算 | step1 |
| [stage6_nonoverlap.py](../archived-notes/2026/08/2026-08-07-atr-cross-timeframe-ratio/atr-timeframe-ratio/scripts/stage6_nonoverlap.py) | 非重叠抽样逻辑 | step2 |

---

## 版本历史

| 日期 | 版本 | 变更 |
|------|-----|------|
| 2026-08-08 | v0.1 | workbench 草稿；建立数据筛选与实验执行方案 |
