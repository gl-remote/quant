# structural-shaping-alpha · 实验计划

> 类型：Experiment Plan
> 状态：草案（2026-07-05 立题）
> 主题 README：[README.md](README.md)
> 研究状态：[research-status.md](research-status.md)

本计划检验"结构塑形本身是否具有独立 alpha"的命题。按 methodology skill
的广度优先原则，从最简子维度扫描开始，每阶段各自可独立验证。

## 0. 全局设定（所有阶段共用）

### 0.1 事件采样（多策略并行）

采样策略本身可能污染结论（固定 20 bar 步长与日内时段共振 / 事件重叠让
样本非独立 / 方向机制隐含均值回归假设等）。因此采样不是单一方式，而是
**多策略并行 + 交叉验证**。

#### 0.1.1 采样策略 A/B 必做 + C/D 选择性加入

| 采样 ID | 策略 | 必做 / 可选 | 用途 |
|--------|------|-----------|------|
| **SamplingA · uniform_20bar** | 每合约每 20 根 5m bar（或 15m 下 7 根）采样一次 | **必做** | 基线，继承 Stage 4b 口径 |
| **SamplingA · uniform_random** | 每交易日在日盘时段内均匀随机采 3 个时点 | **必做** | 打破 20-bar 固定步长的时段共振 |
| **SamplingA · poisson_stride** | 平均步长 20 bar 的泊松过程采样 | **必做** | 完全消除周期性（随机步长）|
| **SamplingA · event_random_within_far** | Stage 4b no_trigger（含 4+ ATR 距离过滤）| **必做** | 与 value-area 家族口径可比 |
| **SamplingC · overlap_control** | 显式约束"任意时点最多 K 个并发持仓" + block bootstrap | 选择性加入 | 若某变体在 A/B 下显著，用它验证是否被事件重叠人为放大 |
| **SamplingD · env_stratified** | 按波动率分位 / 时段 / 趋势状态分层独立采样 | 选择性加入 | 若某变体在 A/B 下显著，用它验证是否只由某个环境主导 |

**判决规则**：结构变体 alpha **必须在 ≥3 种必做采样策略下都显著**才通过；
仅在 1-2 种下显著记为"采样敏感"，标注保留意见，不进入阶段 2。

#### 0.1.2 方向决定机制（多机制并行）

当前把方向绑到 PrevClose 上意味着方向本身已经包含"均值回归假设"，
仓位变体可能在检验"波动率调整 × 均值回归"的联合，非纯仓位效应。

| 方向 ID | 决定机制 | 必做 / 可选 | 用途 |
|--------|---------|-----------|------|
| **DirRegress** | close > PrevClose → 做空回归；反之做多回归 | **必做** | 现状口径 |
| **DirTrend** | close > PrevClose → 做多顺势；反之做空顺势 | **必做** | 反向对照，暴露"方向假设"的方向性效应 |
| **DirRandom** | 每笔随机 ±1，seed 固定 | **必做** | **真正的 no-signal baseline**，纯结构塑形效应必须在这里也显著 |

**判决规则**：结构变体 alpha **必须在 ≥2 种方向机制下（含 DirRandom）都显著**
才可声称"纯结构 alpha"。若只在 DirRegress 下显著 → 是"结构 × 方向假设"耦合，
不是独立结构 alpha。

#### 0.1.3 采样 × 方向 组合矩阵

阶段 1 每个 L3 变体需要在 **4 采样 × 3 方向 = 12 组合** 下评估。计算成本
上升 4 倍（相对原设计），但过滤能力显著提升。

**避免 value-area 假设污染**：所有采样策略下均不使用 reacceptance / VA 边界 /
距离档过滤（除 SamplingA · event_random_within_far 用于对照，本身不携带方向 alpha）。

#### 0.1.4 事件独立性处理（Sampling C）

**触发条件**：某变体在 A/B 采样 × 方向组合下显著。
**方法**：
- 记录每笔交易的开仓/平仓 bar_idx；
- 按 "任意时点最多 K 个并发持仓（K=2）"约束回测（多余的入场被丢弃）；
- Cluster bootstrap 从 iid 升级为 block bootstrap（block size ≈ timeout 长度）。

若加入 Sampling C 后原显著性消失 → 结论是事件重叠伪影，回退。

#### 0.1.5 环境分层（Sampling D）

**触发条件**：某变体在 A/B/C 都显著，进入阶段 3（稳健性）时启用。
**分层维度**：
- 波动率 4 分位（Q1-Q4，基于 ATR20 相对该品种 6 月均值）；
- 时段分档：开盘 30min / 早盘中段 / 午盘 / 收盘 30min / 夜盘（如有）；
- 趋势/震荡状态：基于 5-day / 20-day MA 距离 + Hurst 指数或简单代理。

**判决**：alpha 应至少在 3 个环境层下方向一致，最强层与最弱层差异 < 3 倍。
超出该范围 → 环境依赖性强，收窄边界。

### 0.2 品种覆盖

**阶段 1（Gatekeeper）**：至少 15 品种，覆盖 5 大板块。默认继承 Stage 4b
的 20 品种 × 70 合约样本：
- black: rb, i, hc, FG
- metals: cu, al, ag, au
- energy_chem: sc, TA, MA, OI
- agri_dce: m, p, y, c, cs
- agri_czce: SR, CF, RM

**阶段 3（稳健性）**：扩至 20+ 品种。

### 0.3 周期

- **主周期**：5m
- **稳健性周期**：15m（阶段 3 强制）

### 0.4 标准结构 baseline

用于判决"结构变化是否显著优于标准"。**三种 baseline 交叉验证**：

| baseline | stop_atr | timeout_bar (5m) | target | position_sizing |
|----------|---------|------------------|--------|----------------|
| **baseline_A** | 1.5 | 80 | PrevClose | const |
| baseline_B | 1.0 | 40 | PrevClose | const |
| baseline_C | 2.0 | 160 | none (仅 timeout) | const |

- **默认对照 baseline**：baseline_A（继承 Stage 4b 的口径）
- **多 baseline 交叉验证**：结构变化必须**在至少 2 个 baseline 下**都显著优于对应 baseline 才算通过。若只在 baseline_A 显著，视为 baseline 伪影，不通过。

### 0.5 交易成本

- **成本**：0.05 ATR/笔（单边），与 value-area 家族一致。
- **判据**：所有期望净值均为成本后。

### 0.6 统计口径

**判据分两类，仓位维度必用类 II，其他维度可选**：

**类 I · 单笔期望**（适用于 stop / target / time-exit 维度）：
- 期望净值（ATR/笔）作为主要判据；
- 配对差值检验（同一批 no_trigger 事件下多结构评估配对）；
- Bootstrap 5000 次 + Cluster bootstrap（按 contract 聚类）；
- 单侧假设 H1: structure_variant > baseline，p<0.05 且 cluster CI 排除 0 为显著；
- 单板块 n<300 时结论标注"信度不足"，不作硬决策依据。

**类 II · 组合风险调整**（仓位维度必用，其他维度可选补充）：
- **组合 Sharpe**（跨品种加权后的年化夏普比）；
- **Sortino**（下行波动率替代 std，捕捉负偏效应）；
- **最大回撤 / MDD**（组合层面）；
- **几何均值收益**（对应 volatility drag 效应）；
- 权重方案：按变体规则实际分配的仓位（如 P1 用 1/ATR × k 分配）；
- 显著性：bootstrap 5000 次组合层面 Sharpe/MDD 分布，比较配对差值 CI。

**为什么仓位维度需要类 II**：仓位变体本质上是**跨品种资金分配规则**的改变，
单笔期望（ATR/笔口径）已经把 ATR 从 pnl 里除掉，看不到仓位分配的效果。
必须回到组合层面（未归一 pnl 或 pnl_currency）才能捕捉波动率归一化、
几何均值 vs 算术均值差异、Sharpe 提升等真实 alpha 来源。

### 0.7 判据分档

| 判决 | 条件 |
|------|------|
| ✅ 有独立 alpha (mean) | 至少 1 个结构变体在 ≥2 baseline 下 mean 差值显著优于对照，跨板块方向一致 |
| ✅ 有独立 alpha (risk-adjusted) | 至少 1 个结构变体在 ≥2 baseline 下 Sharpe/Sortino 显著提升或 MDD 显著降低，mean 不显著变差 |
| ⚠️ 部分有 alpha | 某结构变体在特定板块/周期显著，其他不显著 → 收窄边界继续 |
| ❌ 无独立 alpha | 全部结构变体在所有 baseline 下 mean 和 risk-adjusted 指标都不显著优于对照 → 阶段冻结 |

## 阶段 1 · 单结构维度扫描（Gatekeeper）

**目标**：识别哪个结构维度（如果有）单独就能改善期望净值。

**方法**：固定其他维度为 baseline_A，逐个改变一个维度：

### 术语澄清（三层概念）

本 plan 涉及三层 "baseline / 变体" 概念，避免混淆：

| 层 | 名称 | 数量 | 用途 |
|----|------|------|------|
| L1 | 入场 baseline | 1 (`no_trigger`) | 事件源，所有实验共用（§0.1）|
| L2 | 标准结构 baseline | 3 (`baseline_A/B/C`) | **判决对照物**，变体 vs 它们做配对差值检验（§0.4）|
| L3 | 结构变体候选 | 每子阶段 4-6 个（P0-P4, T0-T5, ...）| 待检验的假设，变化 L2 中的一个维度 |

各子阶段表格里的 `P0 (baseline_A)` / `T0 (baseline_A)` 等行表示
**"该变体等价于 baseline_A"的自检复现点**，不是新 baseline。

每个 L3 变体的判决流程：

```text
1. 在同一批 no_trigger 事件（L1）上跑变体，得到 pnl 序列；
2. 与 baseline_A/B/C（L2）的 pnl 序列配对；
3. 计算配对差值 cluster CI；
4. 至少 2 个 baseline 下差值显著优于对照 → 该变体通过。
```

### 阶段 1a · 仓位维度

**为什么仓位维度可能有独立 alpha**（回应"仓位是纯风控"的主流认知）：

主流认知说仓位是头寸大小的线性变换，不改变 pnl 分布形状，因此不产生
alpha。这个说法对**单品种、算术均值口径**成立，但忽略了三类效应：

1. **Volatility drag（几何均值 vs 算术均值）**：即使算术期望为 0，仓位越大长期几何均值越负。高波动率品种大仓 → 大回撤 → 组合层面几何均值受拖累。1/ATR 反向仓位可通过降低高波品种仓位缓解拖累。

2. **跨品种风险分配**：等 lot 下不同品种的账户金额风险差异极大（如螺纹每 lot 波动 ~300 元/日 vs 玉米 ~30 元/日），组合 pnl 被高波品种主导。波动率反向仓位让每笔金额风险相当，Sharpe / Sortino 可显著改善（即使 mean 不变）。

3. **分布不对称的 Kelly 优化**：不同品种的 no_trigger baseline pnl 分布偏度不同，const 仓位不匹配任何品种的最优 Kelly 分数。按分布特征动态调整可能提升组合几何均值。

**因此本子阶段必须用类 II（组合风险调整）判据**（§0.6），单看 ATR/笔期望
会漏掉真正的仓位 alpha。

**关键提醒**：仓位变体只在 **P0 与 baseline_A 完全等价**（自检点），
其他变体（P1-P4）的期望净值 ATR/笔 可能与 baseline_A 差异不大 —— **这
不是失败信号**，因为仓位 alpha 主要在组合风险调整维度。

| structure_variant_id | position_sizing | 说明 |
|--------|----------------|------|
| P0 (baseline_A) | const 1.0 lot | 固定单位 |
| P1 | 1/ATR × k | 波动率反向：低波动品种大仓 |
| P2 | ATR × k | 波动率正向：高波动品种大仓（反直觉） |
| P3 | 1/vol_20 × k | 20 bar 收益标准差反向 |
| P4 | contract-normalized | 按合约点值归一 |

`k` 缩放系数选择使得所有品种平均仓位与 const 1.0 lot 相当（避免仓位总量差异干扰）。

### 阶段 1b · 时间退出维度

| structure_variant_id | timeout_bar (5m) | partial_exit | 说明 |
|--------|-----------------|--------------|------|
| T0 (baseline_A) | 80 | none | 到时按 close 平仓 |
| T1 | 40 | none | 短时长 |
| T2 | 160 | none | 长时长 |
| T3 | 80 | 40 bar 检查 pnl>0.3 ATR 平 50% | 时间衰减部分退出 |
| T4 | 80 | 40 bar 若浮亏 exit | 提前止损 |
| T5 | 80 | 40 bar 若浮盈 exit | 提前止盈（尾部剪切）|

### 阶段 1c · 止损维度

| structure_variant_id | stop_atr | trailing | tiered | 说明 |
|--------|---------|---------|--------|------|
| S0 (baseline_A) | 1.5 | off | off | 固定 stop |
| S1 | 0.5 | off | off | 紧 stop |
| S2 | 1.0 | off | off | 中 stop |
| S3 | 2.0 | off | off | 宽 stop |
| S4 | 1.5 | 走 1 ATR 后 breakeven | off | Trailing |
| S5 | 分档 (近 0.5 / 中 1.5 / 远 2.5) | off | on | 距离自适应 stop |

**注意**：本阶段"距离"不指入场时的 anchor 距离（那样又变成 value-area 家族的距离档研究），
而是**入场后价格相对入场价的 drift**。tiered on 表示 stop 随浮盈/浮亏程度动态调整。

### 阶段 1d · 止盈维度

| structure_variant_id | target | partial | 说明 |
|--------|-------|---------|------|
| E0 (baseline_A) | PrevClose | none | 固定目标 |
| E1 | none (仅 timeout) | none | 无目标，依赖时间 |
| E2 | PrevClose | 到 50% 距离平 50% | 部分止盈 |
| E3 | PrevClose × 2 | none | 目标 2 倍 |
| E4 | dynamic (走 0.5 ATR 后设 target) | none | 动态目标 |

### 阶段 1 判据

- 每个子阶段独立评估，找到显著优于对应维度基线的变体；
- 使用 3 种 baseline 交叉验证（0.4 节）；
- 至少一个子阶段有变体通过 → 阶段 1 gatekeeper 通过，进入阶段 2；
- 全部不通过 → **主题冻结**，结构塑形本身无独立 alpha 假说被证伪。

## 阶段 2 · 结构维度交互（可选，仅当阶段 1 至少一个维度通过）

**目标**：验证阶段 1 找到的多个"有 edge"的结构变体，两两组合是加性 /
乘性还是抵消。

**方法**：从阶段 1 有 edge 的变体中选择 top-3 组合，做 3×3 = 9 组两两
交互（例如 P1×S4, P1×T3, T3×S4 等），仍在 no_trigger 事件上评估。

**判据**：
- 加性效应：`E(P × S) ≈ E(P) + E(S) - baseline` → 独立 alpha
- 乘性效应：`E(P × S) > E(P) + E(S) - baseline` → 协同放大（更强 alpha）
- 抵消/负交互：`E(P × S) < max(E(P), E(S))` → 结构维度相关，不独立

## 阶段 3 · 跨周期 + 跨品种稳健性

**目标**：确认阶段 1-2 找到的 edge 在时间/品种维度稳健。

**方法**：
- 15m 周期一致性（继承 Stage 4b 的稳健性硬门槛）；
- 扩至 20+ 品种（增加 4-5 个之前未覆盖的品种）；
- 按波动率分位分组（Q1-Q4）观察 edge 是否存在环境依赖。

**判据**：
- 15m 下配对差值方向不反转（允许幅度衰减）；
- 生效品种子集在扩样后仍 ≥60% 保留 edge；
- 生效边界可用宏观特征描述（板块 / 波动率制度）。

## 阶段 4 · 与入场 alpha 结合（可选，最终阶段）

**目标**：结构塑形 edge 与入场信号叠加时是加性还是被"入场 alpha 淹没"。

**方法**：
- 使用 value-area 家族的 reacceptance 事件（虽然 reacceptance 本身无独立 alpha）；
- 在 reacceptance 事件上对比 baseline_A 与阶段 1-3 的最优结构；
- 判断结构 alpha 是否"独立于入场类型"存在。

**判据**：
- 若结构 alpha 在 reacceptance 事件上仍显著 → 结构塑形是**通用 alpha**，可与任何入场结合；
- 若结构 alpha 只在 no_trigger 上显著、reacceptance 上消失 → 结构 alpha 与入场类型耦合，需重新审视。

## 5. 时间线预估

- **阶段 1**：4 个子维度并行，1-2 天；
- **阶段 2**：0.5-1 天；
- **阶段 3**：1-2 天（含 15m 复跑 + 扩品种）；
- **阶段 4**：0.5 天。

**任何阶段 gatekeeper 不通过即冻结主题**，避免深度调参陷阱。

## 6. 输出

- 每阶段独立 workbench 报告（`docs/workbench/structural-shaping-alpha-stageN-<topic>.md`）；
- 阶段稳定后归档到 `docs/archive/strategy-research/`；
- 主题稳定后（若通过）撰写 strategy-math-spec.md。

## 7. 关联主题

- **反例（同家族）**：[value-area 家族](../../themes-frozen/value-area/README.md)
- **方法论继承**：value-area 家族的四大约束（ATR / 期望净值 / 多层对照 / cluster bootstrap）
- **上游 Roadmap**：[Structural Alpha 长期共识框架](../../../roadmap/strategy-research-framework.md)
