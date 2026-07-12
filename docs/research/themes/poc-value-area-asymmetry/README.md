# poc-value-area-asymmetry · 主题

> 类型：Theme / 交易背景分类器
> 状态：**阶段 1+2+3 完成 · 分类器契约 v2.0 冻结（数学契约与参数选择分离）· 23 条 KF · 阶段 4 待启动**
> 创建时间：2026-07-07
> 最近更新：2026-07-08
> 上游 Roadmap：[Structural Alpha 长期共识框架](../../../roadmap/strategy-research-framework.md)
> 前置反例：[value-area 家族全部冻结](../../themes-frozen/value-area/README.md)
> 前置铺垫：theme:structural-shaping-alpha · archive:2026/07/2026-07-06-structural-shaping-alpha-stage1

## 1. 主题问题

**POC 两侧的 value area 不对称是否携带信息量？**

即：在同一个 volume profile 构建里，从 POC 到 VAH 与从 POC 到 VAL 的分布
特征（volume 比例 / 距离比例 / skewness / 成交量重心距离）不是恒等对称的；
本主题检验这种不对称是否对未来收益（方向 / 幅度 / 命中率）有可复现的
统计关联。

## 2. 动机

### 2.1 与已冻结的 value-area 家族的关系

value-area 家族已证伪的四条假设：

| 已证伪假设 | 本主题是否触碰 |
|-----------|--------------|
| POC 特殊性（fixed & rolling）作为均值锚 | ❌ 不触碰（不用 POC 作为回归目标 / 价格锚） |
| Reacceptance 触发器特殊性 | ❌ 不触碰（不用 reacceptance 事件采样） |
| 4+ ATR 距离档 mean-reversion edge | ❌ 不触碰（不做距离档过滤） |
| Rolling POC 独立价值（作为回归锚） | ❌ 不触碰（rolling 只是 profile 构建方式之一，不作为锚） |

本主题检验的是**正交命题**：POC 两侧 value area 的**形状不对称**（而非
POC 位置或 VA 边界本身）对未来收益的信息量。前主题一直把 POC / VA 当作
"价格锚点"来验证均值回归，本主题把 POC / VA 当作**当下市场结构的描述量**，
只用它的**形状**做特征。

### 2.2 来自 structural-shaping-alpha 的教训

- **KF-1**：结构塑形本身在 DirRandom 下无独立 alpha → 若要有 alpha，
  必须找到入场方向层面的信号；本主题在入场信号层做假设生成；
- **KF-7**：5m × SCALE=5 tail alpha 是重采样伪影 → 5m 上"发现"的信号
  多半是采样噪声。**已知 5m ≈ 全随机游走**（跨主题共识），本主题直接
  跳过 5m 交易时间尺度；
- **KF-9**：归因必须用 ν = μ − σ²/2，不能用 μ → 未来任何"发现方向 alpha"
  的主题必须证明 ν_implied > 0 显著。本主题遵守。

### 2.3 具体假设候选（假设生成期，尚未收敛）

四种候选度量（阶段 1 全部尝试测量，收敛到最有信息量的度量）：

| 编号 | 度量 | 语义 |
|------|------|------|
| A1 | Volume 比例：`vol_upper / vol_lower`（VAH-POC 与 POC-VAL 内） | volume 分布的上下侧对比 |
| A2 | 距离比例：`(VAH-POC) / (POC-VAL)` | 上下侧 VA 空间不对称 |
| A3 | Volume skewness（整个 profile） | 综合分布偏度 |
| A4 | 两侧 volume 重心到 POC 的距离比 | 成交量重心视角 |

**方向映射不做预设**（用户明确要求"分阶段、最小假设"）。阶段 1 只测量
不对称的存在性 + 显著性 + 变化规律 + 与未来收益的**双向**关联（回归斜率
的方向由数据决定）。

## 3. 数据 / 周期 / 构建口径（立题时预约定）

- **交易时间尺度**：**1h**（bar）。原因：已知 5m ≈ 全随机游走，避免掉进
  KF-7 的重采样伪影陷阱；直接从 1h 起测。
- **profile 构建原始数据**：**5m bar**（volume 分布分辨率保留）。
- **profile 构建窗口**（阶段 1 三选一并行比较）：
  - W1：**前一天**（daily fixed profile · 与 value-area-reacceptance 前主题同口径）
  - W2：**前一周**（weekly fixed profile）
  - W3：**rolling 窗口**（rolling profile · 长度分档扫描，例如 4h / 12h / 24h / 72h）
- **profile 定义**：沿用前主题的 VA 定义（POC + 70% volume window），三种
  窗口的具体参数在 experiment-plan.md 里细化。
- **不使用**前主题证伪的成分：POC 作为回归锚、reacceptance 触发、距离档
  过滤——本主题只用 POC/VA 的**形状统计量**。

## 4. 研究路径

按 methodology skill 的广度优先 + 最小假设原则：

### 阶段 1 · 测量与信息量（Gatekeeper）

1a · **测量层**：三种窗口（W1/W2/W3）× 四种度量（A1-A4）在 20 品种上
的分布 · 显著性（远离 0 / 远离 1） · 稳定性（时间序列）。
1b · **信息量层**：以 asymmetry_t 为自变量、未来 N 小时收益为因变量的
预测性回归（Pearson / Spearman / IC / rank-IC），跨品种池化 + 分品种
两种口径。方向由数据决定，不预设。
1c · **结论**：
- 若至少一个 (窗口, 度量, N) 组合在 pooled 与 ≥60% 品种上 IC 显著且
  同号 → 进入阶段 2；
- 否则冻结主题。

### 阶段 2 · 事件驱动确认 + 跨周期护栏

在阶段 1 收敛出的 top-K 组合上：
- 事件采样（分位数触发 · 例如上尾/下尾 20%）+ structural-shaping-alpha
  的 7 combo 结构对比，检验回归斜率能否转化为可交易 net edge；
- **跨周期护栏**：30m + 1h 或 1h + 2h 一致（同物理时长跨采样护栏，
  防 KF-7 伪影）。

### 阶段 3 · 跨品种稳健性 · 波动率制度 · 成本敏感度

仅在阶段 2 通过后启动，扩至 20 品种 × 70 合约，realistic-cost 判决。

### 阶段 4 · 与其他方向 alpha 组合

仅在阶段 3 通过后考虑。

## 5. 方法论前置约束（继承 value-area 家族 + structural-shaping-alpha）

1. 距离/大小/时间统一 **ATR 归一化**
2. 判据用**期望净值（成本后）** + IC，不用 reach_rate 或 win_rate 单指标
3. **多层对照**：DirRandom baseline · asymmetry-shuffle baseline · 跨窗口对照
4. **配对差异检验**：同一批事件下多度量 / 多窗口配对
5. **Cluster bootstrap**：事件按 contract 聚类
6. **Cross-sampling 护栏**：阶段 2 起同物理时长跨周期一致（防 KF-7）
7. **样本量透明**：单品种事件 n<300 时结论标注"信度不足"
8. **归因**：任何"发现正 mean"必须反算 ν_implied 并证明其 > 0 显著（KF-9）

## 6. 关键风险 & 反例检查

### 6.1 与 value-area 家族的独立性

必须避免变成 value-area 家族的换皮版本。安全边界：
- 不做"POC 是否是引力锚"的验证（前主题已证伪）；
- 不做"reacceptance 是否特殊"的验证（前主题已证伪）；
- 不做"距离档 mean-reversion"的验证（前主题已证伪）；
- 只测**形状不对称 → 未来收益方向 / 幅度**的信息量。

若阶段 1 发现"asymmetry 唯一有效方式是接入 POC 回归" → 立即降级并
指回 value-area 家族反例。

### 6.2 KF-7（重采样伪影）

已知 5m ≈ 随机游走，直接从 1h 起测。阶段 2 起加同物理时长跨周期护栏。

### 6.3 KF-4（"少输"型 paired 显著性 ≠ alpha）

任何"显著"必须同时看 mean 与配对 CI，避免只是方差缩小的机械副作用。

### 6.4 多重检验

窗口 3 × 度量 4 × 未来窗口 N（例如 1h/2h/4h/8h）= 48 组合。阶段 1
必须做 Bonferroni 或 FDR 校正。

### 6.5 数据 leakage

profile 构建的窗口必须严格在 t 之前（前一天 / 前一周 / rolling
截止 t 之前 1 bar），不使用 t 时刻之后信息。

## 7. 立题决策依据

**为什么值得研究**：
- value-area 家族证伪了 POC / VA 作为**回归锚**，但**没有**证伪 POC / VA
  作为**形状特征**的信息量；两者是不同命题；
- 主流市场轮廓文献（Steidlmayer、Dalton 等）本身就把 VA 的形状不对称
  （p-shape / b-shape / D-shape）作为市场结构的定性描述，只是从未在
  中国期货 1h 尺度上做过定量 IC 验证；
- 本主题成本极低：阶段 1 仅需读现有 5m 数据 + 计算 profile 特征 +
  IC 回归，无需完整回测框架，秒级出结论。

**为什么可能失败（诚实评估）**：
- 若形状不对称只是"POC 位置本身"的映射（POC 靠近 VAH ⇔ 上侧窄）→
  已被前主题证伪；
- 若 IC 显著但不可交易（成本后消散）→ 与 KF-8 "数学正 edge ≠ 工业
  可用 alpha" 一致，本主题止步于阶段 1；
- 若不同窗口 IC 结论矛盾 → 是 profile 构建方法的自由度陷阱，冻结。

## 8. 时间线预估

- **阶段 1**（测量 + IC）：几秒到几十秒计算，主要工作在文档 + 分析；
- **阶段 2**（事件驱动 + 跨周期）：仅在阶段 1 通过后启动；
- **阶段 3+**：递进。

**任何阶段不通过即冻结主题**，避免陷入深度调参陷阱。

## 9. 文档地图

| 目的 | 文档 |
|------|------|
| 主题入口 | 本文件 |
| 当前研究状态（23 KF）| [research-status.md](research-status.md) |
| 实验计划（阶段 1-3 总结 + 阶段 4 起点）| [experiment-plan.md](experiment-plan.md) |
| **分类器数学契约**（唯一定义源）| [classifier-math-spec.md](classifier-math-spec.md) v2.0 |
| **参数选择与性能报告**（一眼可读终版）| [parameter-selection-spec.md](parameter-selection-spec.md) v1 ⭐ |
| Archive 引用清单 | [archive-references.md](archive-references.md) |
| 工程实现细节 | 尚未撰写（阶段 4 起写 `workspace/common/poc_va_classifier.py` 时补）|
| 家族反例（value-area）| [../../themes-frozen/value-area/README.md](../../themes-frozen/value-area/README.md) |
| 前置铺垫（structural-shaping-alpha）| [../structural-shaping-alpha/README.md](../structural-shaping-alpha/README.md) |
| 长期框架 | [../../../roadmap/strategy-research-framework.md](../../../roadmap/strategy-research-framework.md) |

## 10. 立题声明（why-not-value-area）

按 [strategy-current.md #5](../../strategy-current.md) 立题前置约束
第 8 条："立题前先说明为什么本次假设不落入 value-area 家族已证伪的四条中"。

见 §2.1。核心区别：value-area 家族一直把 POC/VA 当作**价格锚点**验证
均值回归，本主题把 POC/VA 当作**当下市场结构的描述量**只用其**形状**
做特征。二者是不同命题，前主题的证伪链不适用本命题。

## 11. 分支管理

- 开发分支：`experiment/poc-value-area-asymmetry`
- 分支基点：`dev/0.5` @ `2f14290b99a47da640ab188fb298036d9e201bc1`（2026-07-07 立题时）
- 实现提交 hash：待记录（首次实验后回填）
