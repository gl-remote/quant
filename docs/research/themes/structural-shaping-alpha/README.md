# structural-shaping-alpha · 主题

> 类型：Theme / 假设生成期
> 状态：立题（2026-07-05）· 假设待广度扫描 · spec/plan/code 尚未撰写
> 创建时间：2026-07-05
> 上游 Roadmap：[Structural Alpha 长期共识框架](../../../roadmap/strategy-research-framework.md)
> 前置反例：[value-area 家族全部冻结](../../themes-frozen/value-area/README.md)

## 1. 主题问题

**"结构塑形"技巧本身（仓位管理 / 时间退出 / 止盈止损）是否具有独立
alpha？** 即：在**无入场方向 alpha**（随机入场 / 均匀入场 / no_trigger
baseline）的前提下，仅通过精细化的结构塑形，能否产生显著正期望？

这是一个**从"入场找信号"到"结构塑形本身作为信号"的范式反转**。

## 2. 动机

### 2.1 来自 value-area 家族的教训

value-area 家族两个主题（2026-07-03、2026-07-05 先后冻结）证伪了：
- POC / VA reacceptance / rolling POC / 4+ ATR 距离档等所有"入场结构信号"；
- 但 Stage 1.5-A4 意外发现：**结构选择敏感性 >> 距离档选择**（同一距离档
  下最优 vs 最差结构差 2.49 ATR/笔）；
- Stage 4b 也发现：**agri_dce no_trigger baseline 在 15m 下 +0.079 ATR/笔**
  （虽不显著但方向正）。

这两个观察暗示了一个可能性：**alpha 可能主要来自结构塑形，而非入场信号**。
value-area 家族失败于此假设的反面——一直在找入场 alpha，但真正的价值可能
在结构侧。

### 2.2 结构塑形的传统认知与挑战

主流量化教科书把结构塑形（仓位 / 止损 / 止盈 / 时间退出）定位为**风控**
或**放大器**，本身不产生 alpha：

- 仓位管理决定"赚多少 / 亏多少"，不决定"赚不赚"；
- 止损止盈决定 R:R，不决定胜率；
- 时间退出决定持仓周期，不决定方向。

**本主题挑战这个前提**：如果不同结构塑形在 no_trigger baseline 上产生
系统性差异（无论入场是什么），则结构塑形本身就是 alpha。

### 2.3 具体假设候选

以下是本主题拟检验的**结构塑形技巧候选**（每个作为独立子假设）：

| 类别 | 候选技巧 | 假设内容 |
|------|---------|---------|
| 仓位 | 波动率反向仓位（1/ATR）| 高波动品种降仓，低波动升仓，改善夏普比 |
| 仓位 | 波动率正向仓位（ATR × k）| 高波动"顺势加仓"，反直觉但可能有效 |
| 时间退出 | 固定时长退出（N bar 后强平）| 与止损止盈无关，仅时间衰减 |
| 时间退出 | 时间衰减部分退出（40 bar 检查 pnl > 0.3 ATR 平 50%）| 尾部风险剪切 |
| 止损 | 固定 ATR 止损（1.0 / 1.5 / 2.0 ATR）| 止损档位敏感性 |
| 止损 | Trailing stop（走 1 ATR 后 breakeven）| 保护浮盈 |
| 止损 | 分档 stop（按 ATR 距离动态）| 近档紧 stop / 远档宽 stop |
| 止盈 | 单一 POC 目标（value-area 家族用过）| 已证伪 |
| 止盈 | 部分止盈（S2 A4 结构，已在 value-area 家族测过）| 稀释 winner |
| 止盈 | 中位目标（VA 中位 / 半程）| A4 中已测灾难 |
| 止盈 | 无目标（timeout only）| 依赖时间衰减自然回归 |

## 3. 与前主题的差异

本主题**继承前主题的方法论约束**，但**颠倒了研究焦点**：

| 维度 | value-area 家族 | 本主题 |
|------|----------------|--------|
| 入场信号 | 主要变量（reacceptance / 距离档 / POC 距离）| **固定变量**（no_trigger baseline / random 采样）|
| 结构塑形 | 固定变量（S1 baseline 或少数几种 A4 结构）| **主要变量**（仓位 / 时间 / stop / target 逐一扫描）|
| 判据 | 期望净值 vs no_trigger baseline | 期望净值 vs "标准结构"（固定 stop 1.5 ATR + timeout 80 bar + POC 目标）|
| 生效验证 | 需要 no_trigger baseline 对照 | 需要 **"标准结构 baseline" + random 入场 baseline** 双对照 |

## 4. 研究路径

按 methodology skill 的广度优先原则：

### 阶段 1 · 单结构维度扫描（Gatekeeper）

在 no_trigger baseline 事件上（继承自 value-area 家族 Stage 4b 的采样），
逐个改变**一个结构塑形维度**，其他维度固定为"标准结构"：

- 阶段 1a：**仓位维度**（vol-scaled / const / ATR-scaled × 3-4 档）
- 阶段 1b：**时间退出维度**（timeout 20 / 40 / 80 / 160 bar × 是否 partial exit）
- 阶段 1c：**止损维度**（0.5 / 1.0 / 1.5 / 2.0 / 2.5 ATR + trailing on/off + tiered on/off）
- 阶段 1d：**止盈维度**（POC / PrevClose / VA 中位 / 无目标 × partial on/off）

**Gatekeeper 判据**（每个子阶段）：
- 单结构维度在 no_trigger 事件上是否有**显著优于标准结构 baseline** 的组合；
- 显著性用 cluster bootstrap + 配对差值 CI；
- 若某个维度所有档位与标准结构 baseline 无显著差异 → 该维度无独立 alpha，
  记入反例。

### 阶段 2 · 结构维度交互（若阶段 1 至少一个维度有 edge）

对阶段 1 找到的**有 edge 的结构维度**，做两两交互扫描（例如"仓位 × 止损"
矩阵、"时间退出 × 止盈"矩阵），检验：
- 交互效应是否加性（+ 独立价值叠加）；
- 是否存在协同放大（乘性效应）；
- 是否存在互相抵消（负交互）。

### 阶段 3 · 跨周期 + 跨品种稳健性

- 5m 与 15m 双周期一致（继承 Stage 4b 的稳健性硬门槛）；
- 覆盖 5 大板块 × 至少 15 品种；
- 生效边界描述（哪些品种 / 板块生效）。

### 阶段 4 · 与入场 alpha 结合

若阶段 1-3 找到独立结构 alpha，检验：
- 与入场信号（reacceptance / distance filter）叠加是否 alpha 相加；
- 或者只是"入场 alpha × 结构塑形放大器"的错觉。

## 5. 方法论前置约束（继承 value-area 家族教训）

严格适用：

1. **距离/大小/时间统一 ATR 归一化**
2. **判据用期望净值（成本后）**，不用 reach_rate 单一指标
3. **多层对照必须**：标准结构 baseline + random 入场 baseline + no_trigger baseline
4. **配对差异检验**：同一批事件下多结构评估配对；不能只看未配对均值
5. **Cluster bootstrap**：事件按 contract 聚类
6. **跨周期验证**：5m + 15m 一致
7. **样本量透明**：单板块 n < 300 时结论标注"信度不足"

## 6. 关键风险 & 反例检查

### 6.1 与 value-area 家族的独立性

必须避免**变成 value-area 家族的换皮版本**。安全边界：

- 入场固定为 **no_trigger baseline** 或 **random 时点**，不使用 VA / POC / reacceptance；
- 若发现某结构塑形只有在 reacceptance 事件上生效 → **不算独立 alpha**，
  应报回 value-area 家族的 feature-only 出口。

### 6.2 过拟合结构参数

结构塑形维度多，每个 3-5 档，稍不留神就有 100+ 组合。防止过拟合：

- 阶段 1 每子维度独立评估，不做全联合网格搜索；
- 阶段 2 交互只在有 edge 的维度间做，不做全交叉；
- Bonferroni correction 或 FDR 控制多重检验（在样本 n 不大时）。

### 6.3 baseline 选择的伪影

标准结构 baseline 的选择（stop=1.5 ATR / timeout=80 bar / POC 目标）本身
可能刚好落在"最劣化"的组合中，让任何变化都显著更好，制造假 alpha。

防御：**多种 baseline 交叉验证**，例如同时用：
- baseline_A：stop=1.5, timeout=80, target=POC
- baseline_B：stop=1.0, timeout=40, target=PrevClose
- baseline_C：stop=2.0, timeout=160, target=None

若某结构变化仅在某一 baseline 下显著 → 是 baseline 伪影，不是真 alpha。

### 6.4 与市场波动率环境的耦合

结构塑形的效果可能高度依赖市场环境（如波动率制度）。阶段 3 后需要按
**波动率分位**分组验证生效边界。

## 7. 立题决策依据

**为什么值得研究**：

- value-area 家族 Stage 1.5-A4 已有"结构选择敏感性 >> 距离档选择"的
  强证据（同一距离档最优 vs 最差结构差 2.49 ATR/笔）；
- Stage 4b 也有"agri_dce 15m no_trigger baseline +0.079 ATR/笔"的旁证；
- 但两个证据都是 value-area 家族的**副产品**，从未作为主研究方向；
- 立独立主题系统化研究，可以避免副产品的"选择性观察"偏差。

**为什么可能失败（诚实评估）**：

- 主流认知（结构塑形不产生 alpha）有其道理：结构塑形是**从事后结果的函数**，
  不改变事前概率分布；
- 若阶段 1 所有维度都与 baseline 无显著差异 → 主流认知正确，主题失败
  （对应 value-area 家族的四条失败假设之外的第五条独立命题被证伪）。

## 8. 时间线预估

- **阶段 1**（Gatekeeper）：4 个子维度并行，约 1-2 天可跑完；
- **阶段 2**（交互）：只在阶段 1 通过后启动；
- **阶段 3**（稳健性）：仅在阶段 2 通过后启动；
- **阶段 4**（与入场结合）：仅在阶段 3 通过后启动。

**任何阶段不通过即冻结主题**，避免再度陷入 value-area 家族的深度调参陷阱。

## 9. 文档地图

| 目的 | 文档 |
|------|------|
| 主题入口 | 本文件 |
| 当前研究状态 | [research-status.md](research-status.md) |
| 实验计划 | [experiment-plan.md](experiment-plan.md) |
| 数学规格 | 尚未撰写（阶段 1 通过后按 quant-math-spec 补） |
| 参数选择规格 | 尚未撰写（阶段 2 通过后补） |
| 工程实现细节 | 尚未撰写（进入 S0-S6 后补） |
| 家族反例（value-area）| [../../themes-frozen/value-area/README.md](../../themes-frozen/value-area/README.md) |
| 长期框架 | [../../../roadmap/strategy-research-framework.md](../../../roadmap/strategy-research-framework.md) |

## 10. 立题声明（why-not-value-area）

按 [strategy-current.md #5](../../strategy-current.md) 立题前置约束
第 8 条："立题前先说明为什么本次假设不落入 value-area 家族已证伪的四条中"。

value-area 家族已证伪的四条假设：

| 已证伪假设 | 本主题是否触碰 |
|-----------|--------------|
| POC 特殊性（fixed & rolling）| ❌ 不触碰（入场不使用 POC）|
| Reacceptance 触发器特殊性 | ❌ 不触碰（入场用 no_trigger baseline / random）|
| 4+ ATR 距离档 mean-reversion edge | ❌ 不触碰（不做距离档过滤）|
| Rolling POC 独立价值 | ❌ 不触碰（不使用 rolling anchor）|

本主题**完全独立于 value-area 假设链**，检验的是一个正交的命题：**结构
塑形本身是否有独立 alpha**。这个命题在 value-area 家族的研究中从未被直接
验证过，只有副产品级的间接证据。

## 11. 分支管理

- 开发分支：`experiment/structural-shaping-alpha`
- 分支基点：`dev/0.5` @ `7f9c2a9`（2026-07-05 立题时）
- 实现提交 hash：待记录（首次实验后回填）
