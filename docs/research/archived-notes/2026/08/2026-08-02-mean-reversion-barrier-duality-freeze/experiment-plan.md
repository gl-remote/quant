# 实验计划 · mean-reversion-barrier-duality

> 类型：Theme / experiment-plan
> 状态：初稿（2026-08-02）
> 本文定义"怎么验证"，不改变 strategy-math-spec.md 的策略语义。

---

## 1. 验证目标

用真实数据回答三层问题：

1. **存在性**：可交易尺度上，价格是否存在足够强的均值回归漂移（OU 的 $\kappa$），使 $R<1$ 容器在**真实成本后** $E_{\text{net}}>0$？
2. **对偶性**：$R^\ast$ 是否随回归强度 $\kappa$ 单调下降、在强回归段跌破 1（命题 7.1）？同一事件在趋势段（$H>1/2$）是否反过来 $R^\ast>1$？
3. **充分条件**：定理 7.2 的四条（强回归 / 时间成本 / 下行敏感 / 紧止损）哪些在真实市场成立？

---

## 2. 方法论硬约束（继承）

遵守 `quant-research-methodology`：

- **广度优先**：先多品种 / 多周期最简规则扫描，再深度调参；
- **随机对照必选**：同方向随机入场 + 随机方向随机入场双 baseline，结构胜率 / 期望必须显著高于随机；
- **真实成本**：跨品种判决用每合约真实成本（佣金 + 滑点，查表 `workspace/common/contract_specs.py`），扁平 ATR 成本仅 debug；
- **数据边界**：独立样本按 $(contract,date)$ 聚类，cluster bootstrap 报 CI；不跨合约池化尾部阈值；
- **显著性护栏**：警惕"少输型"paired 显著性（方差缩小伪影），做二维拆分（单独变 $K_T$ 或 $K_S$）；
- **制度拆分**：下"过拟合"判决前先拆波动率 / 趋势 / 时段制度；
- **高胜率防伪（KF-6）**：固定时间上限 $T$、报时间退出比例、禁扛单。

---

## 3. 候选矩阵

### 3.1 过程 / 制度维度

| 维度 | 档位 | 说明 |
|---|---|---|
| 品种 | 股指 / 国债 / 商品（农产品 / 黑色 / 能化）/ 加密 / 汇率 | 广度扫描 ≥15 品种 |
| 周期 | 1m / 5m / 15m / 1h / 日线 | 检验 $\kappa$ 的尺度依赖 |
| 制度 | ATR 三分位（低 / 中 / 高）、趋势三分位、时段 | 拆分均值回归 vs 趋势制度 |
| 过程对照 | OU 估计段 / fBm $H<1/2$ 段 / $H>1/2$ 段 / 随机段 | 验证对偶 |

### 3.2 入场与塑形参数

| 参数 | 扫描档 | 说明 |
|---|---|---|
| 入场偏离 $d=K_T$ | 0.3 / 0.5 / 0.8 / 1.2 / 2.0 ATR | 距均衡的偏离 |
| 均衡估计 | 滚动 VWAP / 滚动均值 / POC / 开盘价 | 多锚点对照 |
| $R=K_T/K_S$ | 0.2 / 0.3 / 0.5 / 0.8 / 1.0 / 1.5 / 2.0 / 3.0 | 跨 $R<1$ 与 $R>1$ |
| 时间上限 $T$ | 固定（如 20 / 80 bar） | 防伪高胜率 |
| 方向 | 多 / 空 / 多空混合 | 检验对称性 |

固定容器宽度扫描（固定 $L=K_T+K_S$）用于复现命题 7.1 的 $R^\ast(\kappa)$ 曲线。

### 3.3 OU 参数估计

- 用离散观测极大似然（OU 的 AR(1) 闭式）估计 $(\kappa,\sigma,\theta)$，窗口滚动；
- 同时报告 fBm Hurst $H$（R/S 或增量自相关），区分"反持续（$H<1/2$）"与"均值回归漂移（$\kappa>0$）"——KF-4 表明前者单独不够；
- 入场事件按估计的 $\kappa$ 分箱，观察 $E_{\text{net}}$ 与 $R^\ast$ 是否随 $\kappa$ 单调。

---

## 4. 验证顺序

### 阶段 0（已完成，合成数据）

- OU 首达 ODE 数值 + 小 κ 闭式，验证 KF-1..6；
- 产出：archive:2026-08-02-mean-reversion-barrier-duality-freeze（`raw-scripts/` 9 个脚本 + stage0-summary）。

### 阶段 1 · 广度扫描（存在性）

1. 多品种 × 多周期估计 OU 参数与 $H$；
2. 最简规则：价格偏离均衡 $d$ 入场，固定 $T$，扫 $R$ 网格；
3. 真实成本后算 $E_{\text{net}}$、单笔 / 年化 Sharpe、$P_{\text{win}}$、时间退出比例；
4. 同事件跑双随机 baseline（随机方向 + 随机持有期）；
5. **通过门槛**：强回归分箱（$\kappa$ 上三分位）中，多数品种 $R<1$ 档 $E_{\text{net}}>0$ 且显著优于随机，且 $R^\ast$ 随 $\kappa$ 下降方向一致。

### 阶段 2 · 对偶性验证

1. 把事件按 $H$ / 趋势制度分箱；
2. 对比回归段（$H<1/2,\kappa>0$）与趋势段（$H>1/2$）的 $R^\ast$；
3. 预期：回归段 $R^\ast<1$，趋势段 $R^\ast>1$，交叉点可定位；
4. 二维拆分（单独变 $K_T$ 或 $K_S$）排除"少输型"伪影。

### 阶段 3 · 充分条件与稳健性

1. 加按时间计成本（$c_t$）扫 $R^\ast$ 下移量（定理 7.2 条件 2）；
2. 下行偏差 / Sortino 目标下复算（条件 3）；
3. 参数敏感度：$d$、$T$、均衡锚点、$\kappa$ 窗口；
4. cluster bootstrap（按 contract×date）报 CI；
5. 样本外：品种 LOPO + 时间前 / 后半切分。

### 阶段 4 · 工程化决策

- 阶段 1–3 通过 → 写完整 math-spec 修订 + parameter-selection-spec + implementation-notes；
- 稳定后考虑提炼 `theorem:mean-reversion-barrier-duality#...`；
- 未通过：记录是哪条前提失败（无 κ / 成本吞噬 / 过拟合），降级或放弃。

---

## 5. 判据与门槛

| 判据 | 通过标准 |
|---|---|
| 正净期望 | 强回归分箱 $E_{\text{net}}>0$，cluster CI 下限 > 0 |
| 随机对照 | 结构 $E_{\text{net}}$ / 胜率显著优于同事件随机（配对检验） |
| 对偶方向 | 回归段 $R^\ast<$ 趋势段 $R^\ast$，且强回归段 $R^\ast<1$ |
| 成本稳健 | 真实成本后结论不翻转（与扁平 cost debug 双向对照） |
| 参数稳健 | $d,T,R$ 合理邻域内结论不剧烈变化 |
| 样本外 | LOPO 多数保留 + 时间后半不塌陷 |
| 高胜率防伪 | 时间退出比例可控，随机持有期 baseline 不复制高胜率 |

---

## 6. 风险与已知陷阱

- **过拟合高胜率**：紧止盈 + 不止损 / 长等待可伪造胜率（KF-6）——固定 $T$ + 随机持有期对照；
- **容量与成本**：$R<1$ 高频、单笔毛利小，真实成本可能吞噬全部 edge；
- **OU 误设**：真实回归可能非线性 / regime-switching，需非线性对照；
- **制度依赖被误判过拟合**：拆 $\kappa$ / 波动率 / 时段后再判；
- **幸存者与合约寿命**：每合约独立样本，不跨合约池化阈值。

---

## 7. 复现资产

- 合成数据验证脚本：archive:2026-08-02-mean-reversion-barrier-duality-freeze（`raw-scripts/`，9 个脚本）
  - `explore_ou_duality.py`：OU vs BM、长空头混合、R 扫描
  - `verify_ou_analytic.py`：ODE 数值 vs 小 κ 闭式
  - `r_optimality_regimes.py`：固定止损 / 时间成本 / fBm 代理三大约束
  - `objectives_study.py`：多目标（Sharpe / Kelly / 下行惩罚）
  - `kappa_threshold_study.py`：$R^\ast(\kappa)$ 交叉点定位
  - `regime_realism_check.py` / `equilibrium_error_check.py` / `timescale_competition.py` / `r_optimality_study.py`：成本、regime 破裂、均衡误差、Péclet 数压力测试
- 真实数据阶段脚本阶段 1 启动后写入 `docs/workbench/<theme-slug>/scripts/`。
