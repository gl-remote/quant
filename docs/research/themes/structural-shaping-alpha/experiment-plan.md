# structural-shaping-alpha · 实验计划

> 类型：Experiment Plan
> 状态：草案 v2（2026-07-06 gatekeeper 精简改造）
> 主题 README：[README.md](README.md)
> 研究状态：[research-status.md](README.md)
> 变更记录：v1 → v2 阶段 1 从单维度扫描改为行业共识组合 gatekeeper

本计划检验"结构塑形本身是否具有独立 alpha"的命题。v2 按对话讨论结果，
将阶段 1 从"逐维度扫描"改为"行业共识最优组合直接对比"，大幅降低计算量
的同时回答同一个 gatekeeper 问题。

## 0. 全局设定（所有阶段共用）

### 0.1 事件采样

v2 gatekeeper 使用**最简采样 + 纯随机方向**，避免采样矩阵膨胀。
若 gatekeeper 通过后进入阶段 2，再逐步加严。

#### v2 gatekeeper 采样配置

| 维度 | 策略 | 说明 |
|------|------|------|
| **采样** | uniform_20bar | 每 20 根 5m bar 采样一次（继承 Stage 4b 口径） |
| **方向** | DirRandom（纯随机 ±1）| 真正的 no-signal baseline，纯结构塑形效应必须在这里也显著 |

**选择 DirRandom 的理由**：如果纯随机方向下结构塑形都没效果，那在其他方向
下即使"有效"也只是方向耦合，不是独立结构 alpha。gatekeeper 只需要回答
"有没有"，不需要回答"在什么条件下有"。

**DirRandom gatekeeper 的隐含偏好（必须写清）**：
- DirRandom 会**过滤掉所有方向依赖的结构效应**，因此该 gatekeeper 对
  "方向无关的风控组合"（如 Combo D 波动率目标）天然占优，对
  "方向依赖的盈亏组合"（如 Combo A/C 教科书 R:R、宽止损波段）天然不利；
- **通过 = 方向无关的结构 alpha 存在**（这是本主题的核心命题）；
- **未通过 ≠ 结构塑形完全无用**——只能说明纯随机方向下无独立 alpha，
  阶段 2 才回答"叠加方向信号后是否有加性 alpha"。

#### 阶段 2 加严采样（gatekeeper 通过后启用）

| 维度 | 策略 | 用途 |
|------|------|------|
| 采样 + | uniform_random | 打破 20-bar 固定步长时段共振 |
| 采样 + | poisson_stride | 完全消除周期性 |
| 方向 + | DirRegress | 均值回归方向对照 |
| 方向 + | DirTrend | 顺势方向对照 |
| 采样 + | overlap_control (K=2) | 若某组合在基础采样下显著，验证是否被事件重叠放大 |
| 采样 + | env_stratified | 按波动率分位分层，验证是否只由某个环境主导 |

**判决规则**（阶段 2）：结构组合 alpha 必须在 ≥3 种采样策略下都显著，
且在 ≥2 种方向机制下（含 DirRandom）都显著，才可声称"独立结构 alpha"。

### 0.2 品种覆盖

**gatekeeper**：10 品种 × 2 合约 = 20 合约（每板块取 2 主力合约）：

| 板块 | 品种 | 合约示例 |
|------|------|---------|
| black | rb, i | rb2601, i2601 |
| metals | cu, al | cu2601, al2601 |
| energy_chem | sc, TA | sc2601, TA2601 |
| agri_dce | m, p | m2601, p2601 |
| agri_czce | SR, CF | SR601, CF601 |

**阶段 3（稳健性）**：扩至 20 品种 × 70 合约，继承 Stage 4b 口径。

### 0.3 周期

- **gatekeeper / 阶段 2**：5m
- **阶段 3（稳健性）**：5m + 15m 双周期

### 0.4 交易成本

- **成本**：0.05 ATR/笔（单边），与 value-area 家族一致。
- **判据**：所有期望净值均为成本后。

### 0.5 统计口径

**类 I · 单笔期望**（主要判据）：
- 期望净值（ATR/笔）作为主要判据；
- 配对差值检验（同一批 no_trigger 事件下多组合评估配对）；
- Bootstrap 5000 次 + Cluster bootstrap（按 contract 聚类）；
- 单侧假设 H1: combo > baseline_E，p<0.05 且 cluster CI 排除 0 为显著；
- 单板块 n<300 时结论标注"信度不足"。

**类 II · 组合风险调整**（Combo D 必用，其他可选补充）：
- 组合 Sharpe / Sortino / MDD / 几何均值收益；
- 权重方案：按变体规则实际分配的仓位；
- 显著性：bootstrap 5000 次组合层面 Sharpe/MDD 分布。

**Combo D（及所有无止盈/mean 不敏感组合）的量化阈值**：
- **Sharpe 显著**：Combo Sharpe > E Sharpe + 0.3，且 bootstrap 95% CI 下界 > E Sharpe；
- **Sortino 显著**：Combo Sortino > E Sortino + 0.3，且 bootstrap 95% CI 下界 > E Sortino；
- **MDD 显著降低**：Combo MDD < E MDD × 0.8（相对降低 ≥ 20%），
  且 bootstrap 95% CI 上界 < E MDD；
- **几何均值**：Combo geo-mean > E geo-mean，且 bootstrap 95% CI 下界 > 0；
- 任一条件满足即视为"risk-adjusted 显著优于 E"。

### 0.6 判据分档

| 判决 | 条件 |
|------|------|
| ✅ 有独立 alpha (mean) | 至少 1 个组合 mean 净值显著 > 0（成本后），且显著优于 E 基准 |
| ✅ 有独立 alpha (risk-adjusted) | 某组合 mean 不显著但 Sharpe/MDD 显著优于 E（阈值见 §0.5 类 II） |
| ⚠️ 部分有 alpha | 特定板块显著，其他不显著 → 收窄边界继续 |
| ❌ 无独立 alpha | 全部组合 ≈ 0 且无显著差异 → 主题冻结 |

> **阶段 2 判决升级**：进入阶段 2 后，"显著"的定义按 §0.1 加严采样规则收紧
> 为 "≥3 种采样策略 × ≥2 种方向机制（含 DirRandom）同时显著"，
> 阶段 1 gatekeeper 使用的单采样 × 单方向判决**不足以**支撑最终结论。

---

## 阶段 1 · 行业共识组合 Gatekeeper

**目标**：直接测试行业公认的"最优概率"结构塑形组合，在随机入场
（no_trigger baseline）下是否有独立 alpha。不再逐维度拆开，而是测
"整机"效果。

### 设计理念

原 v1 计划拆成仓位 / 时间 / 止损 / 止盈四个子维度逐个扫描。
v2 改为：直接测试行业内广泛认可的 6 种完整组合。理由：

1. 实际交易中仓位/止损/止盈/时间退出是联合使用的，拆开测可能遗漏
   维度间的交互效应
2. 行业共识组合本身就是一个"已有无数人验证过的最优配置"，
   如果这个都不行，那更冷门的变体大概率也不行
3. 计算量从 v1 的 ~18,000 次（仅 gatekeeper）降到 **120 次**

### 1.1 六种行业共识组合

#### Combo A · 教科书风控（经典 R:R=2:1）

```
仓位：risk 1% account per trade
      size = account_value × 0.01 / (stop_atr × tick_value)
止损：1.5 ATR（固定）
止盈：2R = 3.0 ATR（固定）
时间：日盘结束强平（EOD）
trailing：无
```

逻辑：几乎所有期货教科书的标准配置。单笔风险可控，
R:R = 2:1，胜率只需 >34% 即正期望。

#### Combo B · 紧止损短线（高周转）

```
仓位：risk 0.5% per trade
      size = account_value × 0.005 / (stop_atr × tick_value)
止损：0.5 ATR（紧）
止盈：2R = 1.0 ATR（固定）
时间：40 bar（≈3.3 小时）
trailing：无
```

逻辑：缩小每笔空间提高周转率，依赖大量样本统计优势。
日内炒单常见配置。**R:R 保持 2:1 与 A 一致**——若采用对称目标
（R:R=1:1），DirRandom 下期望净值必然 ≤ -成本，
gatekeeper 会变成 sanity check 而非有效检验。

#### Combo C · 宽止损波段（拿大波动）

```
仓位：risk 2% per trade
      size = account_value × 0.02 / (stop_atr × tick_value)
止损：2.5 ATR（宽）
止盈：3R = 7.5 ATR（固定）
时间：160 bar（≈13 小时，可跨日盘）
trailing：无
```

逻辑：给足空间避免噪声止损，赚大波段。
CTA 趋势策略常见参数范围。

#### Combo D · 波动率目标（机构风控）

```
仓位：1/ATR 归一化
      k 使得所有品种平均仓位 ≈ 1 lot
止损：1.0 ATR
      走 1 ATR 浮盈后 → breakeven（trailing）
止盈：无（仅时间退出）
时间：80 bar（≈6.7 小时）
```

逻辑：不预测方向，只控制每笔波动率敞口，让时间退出自然平仓。
AHL/Man Group 风格。学术支持：Harvey et al. (2018) volatility targeting
提升风险资产 Sharpe ratio，降低左尾。

#### Combo E · 基准对照（最朴素）

```
仓位：固定 1 lot（不调整）
止损：1.5 ATR（固定）
止盈：2.0 ATR（固定，纯 ATR，不含价格锚点）
时间：80 bar
trailing：无
```

用途：判决对照基准。E 与 A 的唯一差别是仓位（固定 lot vs risk-based），
其余维度（止损/止盈/时间）都用 ATR 固定倍数、不含任何价格锚点，
避免 PrevClose 等价格锚点在 DirRandom 下引入不对称样本，
使 A vs E 差值成为**纯"风控仓位"贡献**的估计。
A-D/F 所有组合都与 E 做配对差值检验。

#### Combo F · 盈亏保护（教科书 + trailing 止损）

```
仓位：risk 1% per trade（同 A）
止损：1.5 ATR（固定初始止损）
      持仓期间 MFE ≥ 1 ATR → 止损移至入场价（breakeven）
止盈：2R = 3.0 ATR（同 A）
时间：80 bar
```

逻辑：以教科书配置为底座，加入"保护已有利润"这一行为金融学层面
最被广泛认可的规则。F 与 A 的唯一区别是止损是否动态化，
配对差值直接测"盈亏保护"行为在随机入场下的独立效果。

### 1.2 组合参数矩阵

| 维度 | A 教科书 | B 短线 | C 波段 | D 机构 | E 基准 | F 盈亏保护 |
|------|---------|--------|--------|--------|--------|-----------|
| 单笔风险 | 1% | 0.5% | 2% | 1/ATR | 固定 lot | 1% |
| 止损 | 1.5 ATR | 0.5 ATR | 2.5 ATR | 1.0 ATR | 1.5 ATR | 1.5 → breakeven |
| 止盈 | 3.0 ATR (2R) | 1.0 ATR (2R) | 7.5 ATR (3R) | 无 | 2.0 ATR | 3.0 ATR (2R) |
| 时间 | EOD | 40 bar | 160 bar | 80 bar | 80 bar | 80 bar |
| trailing | 无 | 无 | 无 | breakeven | 无 | breakeven |

### 1.3 诊断对比关系

| 对比 | 检验的问题 |
|------|-----------|
| A vs E | "经典 R:R=2:1 + 风控仓位" vs "朴素固定 lot"是否改善期望？ |
| B vs E | "紧止损高周转"是否改善期望？ |
| C vs E | "宽止损大波段"是否改善期望？ |
| D vs E | "波动率目标 + 无目标退出"是否改善期望或风险调整指标？ |
| F vs A | "盈亏保护 trailing"是否在教科书配置基础上进一步改善期望？ |
| D vs F | "机构风控" vs "教科书 + 保护"哪种更优？ |

### 1.4 计算量

```
6 组合 × 1 采样(uniform_20bar) × 1 方向(DirRandom) × 20 合约 = 120 次回测
vnpy BacktestEngine 口径：约 10 分钟
轻量 Python 模拟口径：约 1 分钟
```

### 1.5 判据

**gatekeeper 通过条件（满足任一即可进入阶段 2）**：

- **条件 1 (mean)**：至少 1 个组合 (A-F) 的 mean 净值显著 > 0（成本后），
  且配对差值显著优于 E
- **条件 2 (risk-adjusted)**：至少 1 个组合的 Sharpe/Sortino 显著优于 E
  或 MDD 显著降低，mean 不显著变差

**gatekeeper 冻结条件**：

- 全部组合 mean ≈ 0，且无显著差异 → 主流认知正确，主题冻结

**特别诊断**：

- F vs A 显著 → "盈亏保护 trailing"有独立效果，值得阶段 2 深挖
- D 显著 → "波动率目标"有独立效果，与 Harvey (2018) 一致
- 仅 F > A 但 A ≈ E → trailing 改善来自入场结构耦合，不是独立结构 alpha

---

## 阶段 2 · 组合深挖（可选，仅当阶段 1 通过）

**目标**：对阶段 1 通过的组合做加严验证 + 交互诊断。

### 2.1 加严采样（逐步）

1. 加入 uniform_random + poisson 采样，确认 uniform_20bar 下显著不是时段共振
2. 加入 DirRegress / DirTrend 方向，确认纯随机方向下也显著（或明确边界）
3. 若仍显著，加入 overlap_control (K=2) 验证事件重叠非伪影
4. 若仍显著，加入 env_stratified 验证非单环境主导

### 2.2 组合交互诊断

对阶段 1 top-2 组合，拆解其相对 E 的优势来源：

- 单独改变仓位维度（保持其他维度不变），测仓位贡献
- 单独改变止损维度，测止损贡献
- 单独改变止盈/时间维度，测止盈/时间贡献
- 两两交互：仓位 × 止损、止损 × 止盈 等

**耦合矩阵（独立性问题的显式落地）**：

| 耦合对 | 检验的问题 |
|--------|-----------|
| 仓位 × 止损 | 风控仓位的价值是否依赖止损宽度？（宽止损下 risk% 是否失效） |
| 止损 × 止盈 | 止损宽度决定 R:R 后，止盈倍数是否还有独立效应？ |
| 止损 × 时间 | 时间退出是否替代了远距离止损？（短时间退出下 2.5 ATR 止损是否浪费） |
| 仓位 × 时间 | 波动率目标仓位是否只在长时间持仓下体现优势？ |
| 止盈 × 时间 | 时间退出与固定止盈哪个先触发？两者是否互斥？ |

**判决**：耦合对差值显著 → 该组维度不独立，阶段 3 必须联合调参；
耦合对差值不显著 → 两维度可近似独立处理，可分别做敏感性扫描。

### 2.3 判据

阶段 2 通过 → 进入阶段 3（跨周期 + 跨品种稳健性）。
阶段 2 失败（加严采样后消失）→ 收窄边界或冻结。

---

## 阶段 3 · 跨周期 + 跨品种稳健性（可选）

**方法**：
- 15m 周期复跑阶段 1 的所有通过组合
- 扩至 20 品种 × 70 合约
- 按波动率分位分组

**判据**：
- 15m 下配对差值方向不反转
- 扩品种后 ≥60% 保留 edge
- 生效边界可用板块/波动率制度描述

---

## 阶段 4 · 与入场 alpha 结合（可选，最终阶段）

（与 v1 相同，保留。）

**目标**：结构塑形 edge 与入场信号叠加时是加性还是被"入场 alpha 淹没"。

---

## 5. 时间线预估

| 阶段 | 计算量 | 预估时间 |
|------|-------|---------|
| 阶段 1 gatekeeper | 120 次回测 | **10-20 分钟** |
| 阶段 2 加严 | ~500 次回测 | 1-2 小时 |
| 阶段 3 稳健性 | ~2,000 次回测 | 2-4 小时 |
| 阶段 4 结合 | ~500 次回测 | 1 小时 |

**任何阶段 gatekeeper 不通过即冻结主题**。

---

## 6. 输出

- 阶段 1：workbench 报告 `docs/workbench/structural-shaping-alpha-gatekeeper.md`
- 阶段 2+：workbench 报告 `docs/workbench/structural-shaping-alpha-stageN-<topic>.md`
- 主题稳定后归档到 `docs/archive/strategy-research/`
- 通过后撰写 strategy-math-spec.md

---

## 7. 关联主题

- **反例（同家族）**：[value-area 家族](../../themes-frozen/value-area/README.md)
- **方法论继承**：value-area 家族的四大约束（ATR / 期望净值 / 多层对照 / cluster bootstrap）
- **上游 Roadmap**：[Structural Alpha 长期共识框架](../../../roadmap/strategy-research-framework.md)
