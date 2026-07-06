# structural-shaping-alpha · 实验计划

> 类型：Experiment Plan
> 状态：v2.3（2026-07-06 追加 Combo L 作为跨周期候选）
> 主题 README：[README.md](README.md)
> 研究状态：[research-status.md](README.md)
> 变更记录：
>
> - v1 → v2 阶段 1 从单维度扫描改为行业共识组合 gatekeeper
> - v2 → v2.1（2026-07-06）追加 Combo D2 参数补丁，用于区分 D 的参数病 vs 命题病
> - v2.1 → v2.2（2026-07-06）阶段 1 完成后阶段 2/3/4 全面重构：从"验证塑形独立 alpha"改为"扫描塑形受益条件"
> - v2.2 → v2.3（2026-07-06）追加 Combo L 到 §1.1 作为跨周期候选主 combo（workbench §8.8 / §8.11 实证支持）；M/N/G-K 探索性 combo 保留在 workbench 不入主计划

本计划检验"结构塑形本身是否具有独立 alpha"的命题。v2 按对话讨论结果，
将阶段 1 从"逐维度扫描"改为"行业共识最优组合直接对比"，大幅降低计算量
的同时回答同一个 gatekeeper 问题。

## 0. 全局设定（所有阶段共用）

### 0.1 事件采样

v2 gatekeeper 使用**最简采样 + 纯随机方向**，避免采样矩阵膨胀。
若 gatekeeper 通过后进入阶段 2，再逐步加严。

#### v2 gatekeeper 采样配置

| 维度     | 策略                | 说明                                     |
| ------ | ----------------- | -------------------------------------- |
| **采样** | uniform\_20bar    | 每 20 根 5m bar 采样一次（继承 Stage 4b 口径）     |
| **方向** | DirRandom（纯随机 ±1） | 真正的 no-signal baseline，纯结构塑形效应必须在这里也显著 |

**选择 DirRandom 的理由**：如果纯随机方向下结构塑形都没效果，那在其他方向
下即使"有效"也只是方向耦合，不是独立结构 alpha。gatekeeper 只需要回答
"有没有"，不需要回答"在什么条件下有"。

**DirRandom gatekeeper 的隐含偏好（必须写清）**：

- DirRandom 会**过滤掉所有方向依赖的结构效应**，因此该 gatekeeper 对
  "方向无关的风控组合"（如 Combo D 波动率目标）天然占优，对
  "方向依赖的盈亏组合"（如 Combo A/C 教科书 R:R、宽止损波段）天然不利；
- **通过 = 方向无关的结构 alpha 存在**（这是本主题的核心命题）；
- **未通过 ≠ 结构塑形完全无用**——只能说明纯随机方向下无独立 alpha，
  阶段 2 才回答"什么条件下塑形能从无害升级为正贡献"（v2.2 重构后：
  方向 alpha × 塑形 / 跨周期 × 塑形 / 波动率制度 × 塑形三条并行）。

#### 阶段 3 加严采样（阶段 2 任一子条件通过后启用）

| 维度   | 策略                     | 用途                       |
| ---- | ---------------------- | ------------------------ |
| 采样 + | uniform\_random        | 打破 20-bar 固定步长时段共振       |
| 采样 + | poisson\_stride        | 完全消除周期性                  |
| 方向 + | DirRegress             | 均值回归方向对照                 |
| 方向 + | DirTrend               | 顺势方向对照                   |
| 采样 + | overlap\_control (K=2) | 若某组合在基础采样下显著，验证是否被事件重叠放大 |
| 采样 + | env\_stratified        | 按波动率分位分层，验证是否只由某个环境主导    |

**判决规则**（阶段 3）：阶段 2 通过的组合 + baseline 必须在 ≥3 种采样
策略下都显著，且在 ≥2 种方向机制下（含 DirRandom）都显著，才可声称
"跨周期 / 跨制度稳健"。

### 0.2 品种覆盖

**gatekeeper**：10 品种 × 2 合约 = 20 合约（每板块取 2 主力合约）：

| 板块           | 品种     | 合约示例           |
| ------------ | ------ | -------------- |
| black        | rb, i  | rb2601, i2601  |
| metals       | cu, al | cu2601, al2601 |
| energy\_chem | sc, TA | sc2601, TA2601 |
| agri\_dce    | m, p   | m2601, p2601   |
| agri\_czce   | SR, CF | SR601, CF601   |

**阶段 3（稳健性）**：扩至 20 品种 × 70 合约，继承 Stage 4b 口径。

### 0.3 周期

- **gatekeeper / 阶段 2**：5m
- **阶段 3（稳健性）**：5m + 15m 双周期

### 0.4 交易成本

- **成本口径**：按 `workspace/common/contract_specs.py` 每合约实际
  规格计算——单边成本 = 佣金（按 entry 价格估）+ 滑点（`size × tick
  × slip_tick(0.5)`），按每笔 entry\_atr 换算为 ATR 归一化，随事件 /
  合约 / 波动率变化。Runner 默认启用（`structural_shaping_gatekeeper.py`
  在 §8.7 修正后已切换 `--realistic-cost` 为默认）。
- **扁平备用模型（仅 debug）**：`0.05 ATR/笔（单边）`，与 value-area
  家族历史口径一致，但**已知会跨品种低估 4.5 倍**（详见 workbench
  §8.7），仅供快速原型或跨主题历史对比使用，**不得用于 gatekeeper
  最终判决**。
- **判据**：所有期望净值均为成本后。跨成本模型的 mean\_net\_atr 系统
  下移，但 paired diff vs baseline 因同 event 双向抵消不受影响。

### 0.5 统计口径

**类 I · 单笔期望**（主要判据）：

- 期望净值（ATR/笔）作为主要判据；
- 配对差值检验（同一批 no\_trigger 事件下多组合评估配对）；
- Bootstrap 5000 次 + Cluster bootstrap（按 contract 聚类）；
- 单侧假设 H1: combo > baseline\_E，p<0.05 且 cluster CI 排除 0 为显著；
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

| 判决                          | 条件                                             |
| --------------------------- | ---------------------------------------------- |
| ✅ 有独立 alpha (mean)          | 至少 1 个组合 mean 净值显著 > 0（成本后），且显著优于 E 基准         |
| ✅ 有独立 alpha (risk-adjusted) | 某组合 mean 不显著但 Sharpe/MDD 显著优于 E（阈值见 §0.5 类 II） |
| ⚠️ 部分有 alpha                | 特定板块显著，其他不显著 → 收窄边界继续                          |
| ❌ 无独立 alpha                 | 全部组合 ≈ 0 且无显著差异 → 主题冻结                         |

> **阶段 3 判决升级**（v2.2 重构后）：阶段 2 任一子条件通过后，进入阶段 3
> 稳健性验证时，"显著"的定义按 §0.1 加严采样规则收紧为 "≥3 种采样策略
> × ≥2 种方向机制（含 DirRandom）同时显著"，阶段 1 gatekeeper 与阶段 2
> 单采样 × 单方向判决**不足以**支撑最终结论。阶段 2 内部判决使用
> §2.0/2a/2b/2c 各自的判据表，不受此加严规则约束。

***

## 阶段 1 · 行业共识组合 Gatekeeper

**目标**：直接测试行业公认的"最优概率"结构塑形组合，在随机入场
（no\_trigger baseline）下是否有独立 alpha。不再逐维度拆开，而是测
"整机"效果。

### 设计理念

原 v1 计划拆成仓位 / 时间 / 止损 / 止盈四个子维度逐个扫描。
v2 改为：直接测试行业内广泛认可的 6 种完整组合。理由：

1. 实际交易中仓位/止损/止盈/时间退出是联合使用的，拆开测可能遗漏
   维度间的交互效应
2. 行业共识组合本身就是一个"已有无数人验证过的最优配置"，
   如果这个都不行，那更冷门的变体大概率也不行
3. 计算量从 v1 的 \~18,000 次（仅 gatekeeper）降到 **120 次**

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

**已知机制陷阱（2026-07-06 首次运行后发现）**：D 的原参数把三样"急性"
设置叠加在一起——armed 阈值太低（MFE ≥ 1 ATR）+ armed 后无缓冲（stop 直接
贴 entry）+ 无止盈。这三条一起会把 win\_rate 机械锁死在 5% 附近。因此若 D
判为 ❌ 证伪，必须用 D2（见下）复核区分 **参数病 vs 命题病**，否则不能
把结论一般化到"波动率目标学派"。

#### Combo D2 · 波动率目标 v2（D 参数病对照）

```
仓位：1/ATR 归一化（同 D）
止损：1.0 ATR（同 D）
      MFE ≥ 2 ATR 后 → 止损移至入场价 + 0.5 ATR 缓冲（trailing 放宽）
止盈：3.0 ATR（新增）
时间：80 bar（同 D）
```

逻辑：把 D 的三条陷阱按"合理"波动率目标风格逐一放宽（armed 阈值抬到
2 ATR / armed 后留 0.5 ATR 缓冲 / 加固定止盈）。D2 vs D 差值测参数病，
D2 vs E 差值测命题病。若 D2 仍显著劣于 E → 波动率目标学派整体命题病；
若 D2 通过 → D 只是参数病，学派值得阶段 2 深挖。

**触发规则**：D2 是**条件补跑**——只在 D 判为 ❌ 证伪且 win\_rate < 15%
时补跑（win\_rate 上限过低说明有机械陷阱嫌疑）。若 D 直接通过或 win\_rate
正常，无需 D2。

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

#### Combo L · A + take→trail（无止盈的延迟 breakeven trailing）· v2.3 新增

```
仓位：risk 1% per trade（同 A）
止损：1.5 ATR（固定初始止损）
      持仓期间 MFE ≥ 3.0 ATR → 止损移至入场价（breakeven，无缓冲）
      armed 后 stop 不再移动（无 chandelier trailing）
止盈：无（不主动落袋）
时间：80 bar
```

逻辑：把 A 的 fixed take profit (3 ATR) 替换为"MFE≥3 armed → stop=entry"，
armed 前用 1.5 ATR 初始止损兜底，armed 后不再干预，让 tail 完全靠"是否
回踩 entry 或时间到期"自然结束。设计目标是**保留完整的远距趋势 tail**，
避免固定止盈提前砍单（对比 A）也避免急性 breakeven 剪掉半赢样本（对比 F）。

**三条出场路径**：

- **stop**：armed 前反向撞初始 1.5 ATR 止损 → net ≈ -1.5 - 2c
- **breakeven**：armed 后回踩 entry → net ≈ -2c
- **time\_exit**：armed 后未回踩 entry，走完 80 bar 按 close 出 → 平均 net ≈ +5 ATR（唯一 winner 路径）

**实证状态（截至 2026-07-06）**：

- 5m × SCALE=1: mean=-0.420, p(vs E)=0.175（不显著）
- 5m × SCALE=5: **mean=+0.312, p(vs E)=0.004 ✓**（显著正）
- 15m × SCALE=1: **mean=+0.041, p(vs E)=0.060**（接近显著，唯一跨周期正 mean 的 combo）
- 唯一 Sharpe/Sortino 跨周期为正的 combo
- 详见 workbench §8.8（5m 首发）/ §8.10（跨 SCALE）/ §8.11（15m 复核）

**与 M/N 的关键差别**（M/N 在跨周期上被证伪为 SCALE 重采样伪影）：

- L: armed 后 stop=entry **固定不动**，winner 靠时间到期
- M/N: armed 后 stop **一路跟随** max\_mfe - 1.5 ATR（chandelier）
- 结论：**"给 tail 完全空间"（L）跨周期稳健；"跟随浮盈动态锁利"（M/N）依赖 5m 短周期时序 pattern，跨周期消散**

### 1.2 组合参数矩阵

| 维度       | A 教科书        | B 短线         | C 波段         | D 机构        | D2 机构 v2       | E 基准    | F 盈亏保护          | L 延迟 trail      |
| -------- | ------------ | ------------ | ------------ | ----------- | -------------- | ------- | --------------- | --------------- |
| 单笔风险     | 1%           | 0.5%         | 2%           | 1/ATR       | 1/ATR          | 固定 lot  | 1%              | 1%              |
| 止损       | 1.5 ATR      | 0.5 ATR      | 2.5 ATR      | 1.0 ATR     | 1.0 ATR        | 1.5 ATR | 1.5 → breakeven | 1.5 → breakeven |
| 止盈       | 3.0 ATR (2R) | 1.0 ATR (2R) | 7.5 ATR (3R) | 无           | 3.0 ATR        | 2.0 ATR | 3.0 ATR (2R)    | 无               |
| 时间       | EOD          | 40 bar       | 160 bar      | 80 bar      | 80 bar         | 80 bar  | 80 bar          | 80 bar          |
| trailing | 无            | 无            | 无            | MFE≥1 / 无缓冲 | MFE≥2 / 缓冲 0.5 | 无       | MFE≥1 / 无缓冲     | **MFE≥3 / 无缓冲** |

### 1.3 诊断对比关系

| 对比      | 检验的问题                                                       |
| ------- | ----------------------------------------------------------- |
| A vs E  | "经典 R:R=2:1 + 风控仓位" vs "朴素固定 lot"是否改善期望？                    |
| B vs E  | "紧止损高周转"是否改善期望？                                             |
| C vs E  | "宽止损大波段"是否改善期望？                                             |
| D vs E  | "波动率目标 + 无目标退出"是否改善期望或风险调整指标？                               |
| D2 vs D | trailing 参数放宽 + 加止盈是否救得回 D？（参数病 vs 命题病）                     |
| D2 vs E | 波动率目标学派本身（去掉 D 的参数陷阱）是否有独立 alpha？                           |
| F vs A  | "盈亏保护 trailing"是否在教科书配置基础上进一步改善期望？                          |
| D vs F  | "机构风控" vs "教科书 + 保护"哪种更优？                                   |
| L vs A  | "无止盈 + 延迟 breakeven trailing" vs "固定 R:R=2:1 止盈" 谁更能吃 tail？ |
| L vs F  | 把 armed 阈值从 1 ATR 抬到 3 ATR + 去掉止盈是否改善 trailing 的 edge？      |
| L vs E  | Combo L 作为独立候选，跨周期（5m / 15m）是否稳健优于基准 E？                     |

### 1.4 计算量

```
主实验：6 组合 × 1 采样 × 1 方向 × 20 合约 = 120 次回测
条件补跑（D 触发时）：+1 组合 × 20 合约 = 20 次回测
合计上限：140 次回测
轻量 Python 模拟口径：约 5 秒（实测 4 秒完成 7 组合 34,454 笔）
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
- **D 判 ❌ 且 win\_rate < 15%** → 触发 D2 补跑
  - D2 vs E 显著负 → D 是**参数病 + 命题病**（学派整体证伪）
  - D2 vs E 不显著 → D 是**纯参数病**，波动率目标学派留存值得阶段 2
  - D2 vs D 显著正 → 参数修正确实吃回一部分 edge（用于校准 KF-3 的诊断准则）

***

## 阶段 2 · 塑形受益条件扫描（v2.2 重构）

**阶段 1 已完成 · 结论**：❌ 无独立 alpha（KF-1..5）。阶段 1 gatekeeper
在 no-signal (DirRandom) baseline 下证伪了"塑形独立 alpha"命题，且揭示
了首达定理数学恒等式 E\[net] = -2 × 成本。

**阶段 2 命题反转**：从"塑形有独立 alpha 吗？"转为\*\*"什么条件下塑形能从
'无害' 升级为 '正贡献'？"\*\*

**为什么不冻结**：阶段 1 只证伪了"独立 alpha"（塑形作为唯一 edge 源），
未证伪"依附型贡献"（塑形作为 alpha 放大器 / 制度过滤器 / 长周期 tail
捕获器）。这类"依附型贡献"是主流 CTA / 机构风控实际使用塑形的方式，
值得独立扫描。

**为什么不进原设计的阶段 2**：原设计的"加严采样"（uniform\_random /
DirRegress / overlap\_control 等）目的是**验证阶段 1 通过的组合是否
稳健**——但阶段 1 无组合通过，加严只会把不存在的信号验证到不存在，
路径逻辑死了。

### 2.0 触发条件与前置资源

阶段 2 是**开放式扫描**，三个子条件相互独立、按前置资源可用性优先级
调度，不强制全部执行。**任一子条件通过即产出 KF，不必等全套完成**。

**前置资源需求**：

| 子条件              | 前置资源                                  | 当前状态                                  |
| ---------------- | ------------------------------------- | ------------------------------------- |
| 2a 方向 alpha × 塑形 | 需要"已通过 DirRandom 方向 gatekeeper"的入场事件源 | ⏸ 无（value-area 家族已冻结证伪，暂无可用 baseline） |
| 2b 跨周期 × 塑形      | 15m / 1h / 日线数据落库（每周期 20 合约）          | ✅ 5m 全部到位，长周期需要 fetch                 |
| 2c 波动率制度 × 塑形    | 阶段 1 主 CSV（已有） + 制度分位分层脚本             | ✅ 就绪                                  |

**优先级建议**：**2c > 2b > 2a**。2c 用现成数据几秒可跑；2b 需要
数据 fetch 但仍独立；2a 必须等到未来某个方向 alpha 主题通过 gatekeeper
后再挂载（预计跨主题，中长期）。

### 2a · 入场方向 alpha × 塑形交互

**假设**：塑形规则的正贡献必须依附于真实入场方向 alpha——塑形不创造
gross 期望，只塑造 gross 期望的分布。

**方法**：以未来某个通过 DirRandom 方向 gatekeeper 的入场事件源作为
non-random baseline，对每个事件同时评估 7 combo 的 net，测：

- **加性贡献**：某 combo net > baseline gross（塑形放大了 alpha）
- **抵消性贡献**：baseline gross > combo net > 0（塑形吃掉一部分 alpha 但仍正）
- **中性贡献**：combo net ≈ baseline gross（塑形无影响）
- **破坏性贡献**：combo net < 0 < baseline gross（塑形抹掉了 alpha，对应 KF-2 trailing 负 edge 的推广）

**判据**：至少 1 个 (combo, baseline) 组合达到"加性贡献"，配对差值
CI 排除 0，且跨采样策略 ≥3 种稳健。

**输出**：workbench `structural-shaping-alpha-stage2a-<baseline_theme>.md`

**触发**：等待未来方向 alpha 主题产出可用事件源；本阶段挂起。

### 2b · 跨周期 × 塑形交互（远距 tail 探索）

**假设**：阶段 1 SCALE=5 已初见"远距趋势 tail 让 C/D mean 微正"的方向
证据（realistic-cost 下 +0.01\~+0.04 ATR/笔，工业意义低）。在 5m 上远距
\= 400 bar ≈ 6 天，物理时间尺度小；如果切换到 15m / 1h / 日线，"远距"
对应的物理时间成倍拉长，趋势 tail 幅度理论上会显著放大。

**方法**：15m 复跑阶段 1 相同 7 combo × 三档 SCALE（无 D2 触发时可
去掉，视 D 表现）× realistic-cost，看：

- **7 combo mean 是否随周期上升而系统性抬高**（tail 放大假设）
- **是否有 combo mean 在 15m 或更长周期上显著 > 0**（跨周期 alpha）
- **F vs A、D vs E 的负 edge 是否随周期消散**（trailing 破坏性是否只在 5m）

**周期梯度**：`5m → 15m → 1h`（后两个视前一个结果推进）。**日线暂不进入**
（5m 数据总长 1.5\~2 年，日线样本数不够）。

**判据**：

- **跨周期正 mean**：某 combo 在 15m 或 1h 下 mean > 0 且 CI 下界 > 0
  → 塑形在长周期上有独立价值
- **跨周期恶化消散**：F vs A / D vs E 的负 diff 随周期缩窄到不显著
  → trailing 破坏性只是 5m 短距回归带产物
- **两者都不通过**：塑形跨周期 tail 假设证伪 → 强化 KF-1 结论

**计算量**：15m 每合约 bar 数 ≈ 5m 的 1/3，SCALE=1 单档约 2 秒；三档 SCALE

- 7 combo + 20 合约 ≈ 6 秒。1h 更快。

**优先级**：**建议作为阶段 2 的第一步**——成本低、独立、结论清晰。

**输出**：workbench `structural-shaping-alpha-stage2b-crossperiod.md`

### 2c · 波动率制度 × 塑形交互

**假设**：塑形规则可能只在特定波动率制度下有效——大 K\_T 组合在高波
动率下更容易命中止盈，紧止损组合在低波动率下更少被噪声打飞。塑形
可能不是"通用规则"，而是**制度过滤器**。

**方法**：读阶段 1 SCALE=1 realistic-cost CSV（现成），按每笔 event 的
`entry_atr` 分位分三档：

- 低波动（0-33%）：typical 震荡 / 低成交量段
- 中波动（33-67%）：正常段
- 高波动（67-100%）：typical 事件 / 突发段

对每档独立统计 7 combo 的 mean\_net\_atr / paired vs E / win\_rate。

**判据**：

- 某 combo 在某波动档上 mean 显著 > 0 且 CI 排除 0 → 塑形是制度过滤器
- 某 combo 在某波动档上 paired vs E 显著正 → 塑形有制度依赖的少输效应
  （注意排除 §8.6 KF-4 "少输 ≠ alpha" 陷阱，必须同时看 mean）
- 所有档都无正 mean → 波动率制度不改变结论，冻结 2c 分支

**注意**：ER 分层（§8.5）已经做了"震荡 / 混合 / 趋势"三分，2c 换成
**波动率分层**是正交维度——ER 是"动量方向性"，波动率是"每 bar 幅度"。
两者可能揭示不同信息。

**计算量**：读现成 CSV + 分组统计，秒级。

**优先级**：**最先做**——成本最低，即时结论。

**输出**：workbench `structural-shaping-alpha-stage2c-volregime.md`

### 阶段 2 联合判决

三个子条件独立判决，任一通过即产出 KF：

| 通过条件  | 意义                | 后续动作                                  |
| ----- | ----------------- | ------------------------------------- |
| 2a 通过 | 塑形是 alpha 放大器     | 挂到源 alpha 主题作为增强模块                    |
| 2b 通过 | 塑形在长周期有独立价值       | 独立主题 `structural-shaping-crossperiod` |
| 2c 通过 | 塑形是制度过滤器          | 独立主题 `structural-shaping-regime`      |
| 全部不通过 | KF-1..5 加固 · 主题冻结 | 归档到 `docs/archive/strategy-research/` |

**关键**：阶段 2 不再是"阶段 1 通过后的自动延续"，而是**阶段 1 证伪
基础上的正向探索**。三个子条件都不通过是可接受结局——那时冻结主题会
比阶段 1 单独冻结更严谨，因为已经排除了三种主要的塑形受益路径。

***

## 阶段 3 · 跨周期 + 跨品种稳健性（可选，仅当阶段 2 任一子条件通过后启动）

**方法**：

- 通过的 combo + baseline 组合在**更多周期**上复跑
- 扩至 20 品种 × 70 合约
- 按波动率分位、板块、时段分组稳健性
- 加严采样（uniform\_random / poisson / overlap\_control）——**这里才是原
  §2.1 加严采样的正确位置**

**判据**：

- 跨周期方向不反转
- 扩品种后 ≥60% 保留 edge
- 生效边界可用板块 / 波动率制度 / 周期描述

**注意**：阶段 3 只对阶段 2 已通过的**具体组合**做加严验证，不再对
"塑形整体"做扫描——扫描已在阶段 1 完成并证伪。

***

## 时间线预估

| 阶段              | 状态                | 计算量                        | 预估时间              |
| --------------- | ----------------- | -------------------------- | ----------------- |
| 阶段 1 gatekeeper | ✅ 完成（KF-1..5）     | 140 次回测 × 3 SCALE × 2 成本模型 | 已完成               |
| 阶段 2c 波动率制度     | 就绪待启动             | 读现成 CSV                    | **约 10 秒**        |
| 阶段 2b 跨周期       | 待 fetch 15m/1h 数据 | 15m/1h 各 140 次 × 3 SCALE   | 数据 fetch + 约 30 秒 |
| 阶段 2a 方向 × 塑形   | ⏸ 挂起（等 alpha 主题）  | 视 baseline 事件数             | 中长期               |
| 阶段 3 稳健性        | 仅在 2a/b/c 任一通过后启动 | \~2,000 次回测                | 2-4 小时            |

**任一阶段判决完成后，若无通过条件，冻结主题并归档 KF**。

***

## 6. 输出

- 阶段 1：archive:2026-07-06-structural-shaping-alpha-stage1#stage1-gatekeeper-report（原 `docs/workbench/structural-shaping-alpha-gatekeeper.md` · 已归档）
- 阶段 2+：workbench 报告 `docs/workbench/structural-shaping-alpha-stageN-<topic>.md`
- 主题稳定后归档到 `docs/archive/strategy-research/`
- 通过后撰写 strategy-math-spec.md

***

## 7. 关联主题

- **反例（同家族）**：[value-area 家族](../../themes-frozen/value-area/README.md)
- **方法论继承**：value-area 家族的四大约束（ATR / 期望净值 / 多层对照 / cluster bootstrap）
- **上游 Roadmap**：[Structural Alpha 长期共识框架](../../../roadmap/strategy-research-framework.md)

