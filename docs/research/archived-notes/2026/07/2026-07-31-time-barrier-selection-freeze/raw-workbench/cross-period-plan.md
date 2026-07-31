# time-barrier-selection · 跨周期 $|s|$ 分布对比 · 实验计划

> 状态：✅ 已完成（2026-07-31）· **新方向**（旧 5m 形态扫描已归档到 `archive:2026-07-31-time-barrier-selection-redirection`）· 结果见 [cross-period-report.md](cross-period-report.md)
>
> 目标：在 1m / 5m / 15m / 1h 四个自然周期上分别测量 $|s| = |\nu|/\sigma$ 的真实水平与分布，**直接验证 KF-14 跨周期不变性**（`archive:2026-07-24-structural-shaping-alpha-freeze`）。
>
> 首个实验对象：**玉米 DCE.c** · 3 个主力合约 (c2601/c2603/c2605) · 4 个周期 (1m/5m/15m/1h)
>
> ⚠️ **本实验不引入塑形容器** $(K_S, K_T, T)$——不做 FPT、不开仓、不扣成本，只统计每个自然周期上 per-bar return 序列的 $|s|$ 分布。

## 1. 核心研究问题

> **KF-14 跨周期不变性**：structural-shaping-alpha 已证 — 5m/15m/1h 三周期上 $|s|$ 量级一致（`shaping-theory.md` §2.10 + §2.14.3）。该结论基于塑形实验，本实验**独立验证**——直接在不同周期上拟合 $|s|$ 分布。

### 1.1 主问题

玉米 1m / 5m / 15m / 1h 四个周期上，per-bar $|s|$ 的**经验分布**是否一致？

### 1.2 从属问题

- **Q1（$\mu_D$ 一致性）**：四个周期上的 FoldedNormal 拟合均值 $\mu_D$ 是否落在同一量级（如 $\mu_D \in [0.15, 0.30]$）？
- **Q2（$\sigma_D$ 一致性）**：四个周期上的 $\sigma_D$ 是否相近？
- **Q3（品种稳健性）**：3 个主力合约 c2601/c2603/c2605 上 $\mu_D$ 是否一致（即"分布参数品种无关"）？
- **Q4（KF-14 数值对照）**：与 `shaping-theory.md` 中 `corn_1h_strength_W20.csv`（玉米 1h `|ν|/σ` mean ≈ 0.198–0.213）的数值是否一致？

## 2. Stage 2 · 玉米跨周期 $|s|$ 分布对比

### 2.1 数据

- **品种**：`DCE.c`（玉米，size=10, tick=1.0, commission=1.21）
- **合约**：3 个主力合约 `c2601 / c2603 / c2605`（1m/15m/1h 三个周期共同覆盖的合约集合）
- **周期**：`1m` / `5m` / `15m` / `1h`
- **数据源**：`project_data/market_data/csv/DCE.c{contract}.tqsdk.{period}.csv`

| 合约 | 1m | 5m | 15m | 1h |
|------|-----|-----|------|-----|
| c2601 | ✓ | ✓ | ✓ | ✓ |
| c2603 | ✓ | ✓ | ✓ | ✓ |
| c2605 | ✓ | ✓ | ✓ | ✓ |

每合约独立处理（KF-22 数据边界），**不跨合约池化**。

### 2.2 测量方法

按 `archive:2026-07-24-structural-shaping-alpha-freeze/raw-scripts/corn_1h_strength_three_views.py` 的成熟口径：

1. **窗口长度**：每个周期取**两个尺度**的滑动窗口：
   - $W = 20$ bar（对应 E[τ] 的典型尺度）
   - $W = 80$ bar（对应 MAX_BARS）
2. **窗口滑动**：stride=4 滑动（避免窗口重叠过高）
3. **per-window 估计**：
   $$\widehat{|s|}_W = \frac{|\bar r_W|}{s_W}$$
   其中 $\bar r_W$ 是 $W$ 个 per-bar log return 的均值，$s_W$ 是样本标准差（ddof=1）
4. **聚合**：把同一 (合约, 周期, W) 下所有窗口的 $\widehat{|s|}_W$ 收集成单变量样本

> **关键点**（与 Stage 1 不同）：这里 $|s|$ 估计量的**窗口 $W$ 是常数**（20 或 80 bar），不随 $T$ 变化。**改变的"周期"是 bar 时长**（1m vs 5m vs 15m vs 1h），不是窗口 bar 数。

### 2.3 采样方法

每个 (合约, 周期, W) 组合独立跑：

- **点估计**：`mean(|s|_W)`、`median(|s|_W)`、分位 p10/p25/p50/p75/p90
- **分布拟合**：把窗口级 $|s|$ 样本喂给 **FoldedNormal($\mu_D, \sigma_D$)** 最大似然拟合，得到 KF-27 标准的 $(\mu_D, \sigma_D)$
- **CI 估计**：cluster bootstrap 按**周**重抽样（沿用 `archive:2026-07-31-time-barrier-selection-redirection/raw-scripts/market_strength_scan.py` 的 KF-2 修正）—— 1m/5m 周期每日 bar 数多，cluster 按日；15m/1h 周期每日 bar 数少，cluster 按周

### 2.4 报告指标

每个 (合约, 周期, W) 组合输出：

| 类别 | 指标 | 用途 |
|------|------|------|
| 经验分布 | `mean, median, p10, p25, p50, p75, p90` | 与 structural-shaping-alpha `corn_1h_strength_W20.csv` 对照 |
| 分布拟合 | `mu_D, sigma_D`（FoldedNormal）| KF-27 标准输入 |
| 分布拟合 CI | `mu_D_ci_lo, mu_D_ci_hi, sigma_D_ci_lo, sigma_D_ci_hi` | cluster bootstrap 给出 |
| 样本量 | `n_windows` | 数据稀疏度 |
| 辅助 | `rho_1` | per-bar return 一阶自相关 |

**主指标汇总表**（合并 3 合约后）：

| 周期 | W | n | $\mu_D$ | $\sigma_D$ | median($|s|_W$) | p10 | p90 | $\rho_1$ |
|------|---|---|---------|-----------|----------------|------|------|---------|
| 1m | 20 | ... | ... | ... | ... | ... | ... | ... |
| 1m | 80 | ... | ... | ... | ... | ... | ... | ... |
| 5m | 20 | ... | ... | ... | ... | ... | ... | ... |
| ... | ... | ... | ... | ... | ... | ... | ... | ... |

### 2.5 KF-14 验证判据

| 判据 | 通过条件 | 意义 |
|------|---------|------|
| **KF-14 一致性**（主判据）| 4 个周期 $\mu_D$ 落在 `[min-25%, max+25%]` 区间 | 跨周期不变性成立 |
| **$\sigma_D$ 稳定性** | 4 个周期 $\sigma_D$ 量级一致（ratio < 2）| 分布形态跨周期一致 |
| **品种稳健性** | 3 合约 $\mu_D$ 互差 < 30% | 结论不依赖单一合约 |
| **对照 sanity check** | 合成 i.i.d. 序列的 $\mu_D$ ≈ $\sqrt{2/\pi} \approx 0.798$ | pipeline 正确性验证 |

### 2.6 形态归类（不预设）

完成数据采集后**事后总结**，不预设形态：

- **A 跨周期一致**：$\mu_D$ 4 周期 ratio < 1.5
- **B 跨周期递增**：$\mu_D$ 随周期变长单调递增
- **C 跨周期递减**：$\mu_D$ 随周期变长单调递减
- **D 不一致**：不符合 A/B/C

### 2.7 输出与工作目录

- 工作目录：`docs/workbench/time-barrier-selection/`
- 脚本：`docs/workbench/time-barrier-selection/scripts/cross_period_strength.py`
- 结果输出：`docs/workbench/time-barrier-selection/outputs/cross_period_*.{csv,json}`
- 主实验报告：`docs/workbench/time-barrier-selection/cross-period-report.md`

### 2.8 判定规则

- **完成**：3 合约 × 4 周期 × 2 窗口 = 24 组数据全部产出，KF-14 验证给出明确判据；
- **降级 A（数据不足）**：1m 数据虽然多但合约覆盖少（仅 3 个）；1h 数据合约多但窗口少；若任一组合 n < 30 窗口，降级标注；
- **降级 B（KF-14 证伪）**：4 周期 $\mu_D$ 跨数量级（如 5m $\mu_D$=0.5 但 1h $\mu_D$=0.05）—— 证伪 KF-14 跨周期不变性，登记为重要发现。

## 3. 后续 Stage（预告）

- **Stage 3**：跨品种（豆粕 / 螺纹 / 豆油）做同样的 4 周期对比，验证 KF-14 的品种无关性
- **Stage 4**：把跨周期 $\mu_D$ 对接到 KF-27 参数优化器，对每个周期算最优塑形参数 $(K_S^*, K_T^*, \tau^*)$，看是否在跨周期上同样稳定

## 4. 已知风险与判定护栏

- **风险 A（数据粒度不一致）**：4 周期样本量差异大（1m 一合约 2 万 bar，1h 一合约 400 bar），需分别报告 n_windows 而非假设等样本
- **风险 B（合约覆盖不一致）**：5m 数据覆盖 9 合约，1m/15m/1h 仅 3 合约——本实验限定在 3 合约交集，避免引入"合约效应"混杂
- **风险 C（窗口尺度选择）**：W=20/80 是 structural-shaping-alpha 的经验值；如发现 4 周期结论对 W 敏感，需补 W=40/160
- **风险 D（cluster bootstrap 粒度）**：1m 上每日 ~330 bar，按周 cluster ~1650 bar，重抽后可能与原结构差异大；需对比按日 vs 按周 cluster 的 CI 差异
- **风险 E（KF-14 数值对照）**：本实验的 $|s|$ 估计量与 `shaping-theory.md` 中的 `|ν|/σ` 在数学上等价（同一公式），但 stage 输出格式可能略不同（如 ddof 选 0 vs 1），需在报告里显式说明
