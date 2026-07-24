# va-asymmetry-composite · 主题

> 类型：Theme / 完整交易策略（分类器 + 塑形 + 组合层）
> 状态：**阶段 0 · 立题（2026-07-09）**
> 创建时间：2026-07-09
> 最近更新：2026-07-09
> 上游 Roadmap：[Structural Alpha 长期共识框架](../../../roadmap/strategy-research-framework.md)
> 前置 Alpha 源：theme:poc-value-area-asymmetry
> 前置塑形资产：theme:structural-shaping-alpha
> 前置归档起点：archive:2026-07-09-poc-va-shaping

## 1. 主题问题

**如何把已验证的 poc-value-area-asymmetry 分类器（方向 alpha 源）、structural-shaping-alpha 的塑形方法论（First-Passage Designer、真实成本模型、ν_implied 归因）、以及 archive:2026-07-09-poc-va-shaping 已确定的塑形参数与风控口径，组合成一个通过真实交易成本、品种筛选、信号强度加权、多空权重优化四大闸门的、可实盘的完整盈利策略？**

本主题是**第一个跨主题组合的完整交易策略研究**：
- 不做新 alpha 假设的发现工作（alpha 已由 poc-value-area-asymmetry 独立验证）
- 专注于「alpha 源 → 入场/出场/仓位/风控 → 组合层优化 → 实盘口径验证」的完整链路工程化与稳健性检验

## 2. 组合蓝图（三大模块）

### 模块 A · Alpha 源层（继承 poc-value-area-asymmetry v4.0）

**输入**：前一日 5m volume profile + rolling 20 日日线特征
**输出**：6 类互斥分类标签（每小时判定一次）

| 类别 | 方向 | 三维定义 | 评级 | 初始取舍 |
|:---:|:---:|:---|:---|:---|
| L_seg3_lowmid_up | 多 | skew ∈ (0.09, 0.30] · ATR ≤ 0.67 · trend ≥ 0.75 | A- / A / A- | ✅ 保留 |
| L_seg12_high_up | 多 | skew ≤ 0.19 · ATR > 0.67 · trend ≥ 0.75 | A- / fail / A | ✅ 保留（需品种筛选） |
| L_seg2_low_flat | 多 | skew ∈ (0.09, 0.19] · ATR ≤ 0.33 · trend ∈ (0.20, 0.75) | A / fail / A- | ❌ **淘汰**（塑形后 IR < 0，见 archive:2026-07-09-poc-va-shaping） |
| S_seg12_high_dn | 空 | skew ≥ 0.81 · ATR > 0.67 · trend ≤ 0.20 | ⭐ A/A/A | ✅ 保留（核心空头） |
| S_seg34_high_dn | 空 | skew ∈ (0.60, 0.81] · ATR > 0.67 · trend ≤ 0.20 | A / A- / A- | ✅ 保留 |
| S_seg2_mid_dn | 空 | skew ∈ (0.81, 0.91] · ATR ∈ (0.33, 0.67) · trend ≤ 0.20 | A / fail / A | ✅ 保留（需品种筛选） |

**核心约束继承**：
- rank 单位 = per-contract（禁止跨合约池化，见 kf:poc-value-area-asymmetry#KF-22）
- bootstrap 单位 = (contract, date) cluster
- rolling 窗口：signed_skew_rank_rolling100 · daily_atr_rolling20d · trend_rolling20d
- warmup = 20 个交易日

### 模块 B · 交易执行层（塑形 + 风控，继承 archive:2026-07-09-poc-va-shaping + structural-shaping-alpha）

#### B.1 塑形参数（起点口径）

| 参数 | 多头 | 空头 | 来源 |
|:---|:---|:---|:---|
| 止损（SL） | 1.0 ATR | 2.0 ~ 2.5 ATR | archive:2026-07-09-poc-va-shaping §最优塑形参数 |
| 持仓期（时间止盈） | 6 ~ 10 h | 8 ~ 10 h | 同上 |
| Trailing | MFE ≥ 2~3 ATR → breakeven | 不触发（10h 内极少） | 同上 · Trailing 独立验证无效 |
| 止盈（TP） | 不设硬 TP（时间退出为主） | 不设硬 TP（时间退出为主） | 同上 · 硬 TP 劣于时间退出 |

#### B.2 风控口径（起点口径）

| 风控项 | 数值 | 说明 |
|:---|:---|:---|
| 单笔止损上限 | 2% 账户权益 | archive:2026-07-09-poc-va-shaping §风控 v2 |
| 总名义暴露上限 | 100% 账户权益 | 实际瓶颈（日均暴露 653% 名义 → 需压到 ≤100%） |
| 保证金约束 | 80% 保证金率不触发 | 期货 5~12% 保证金 → 约束极松，非瓶颈 |
| 多空自对冲 | 允许同时持有（自然对冲） | 分类器多空完全互斥（event 层面），但跨品种可叠加 |

#### B.3 成本模型（继承 structural-shaping-alpha KF-5）

- **必用 realistic-cost**（`workspace/common/contract_specs.py`）：单边成本 = 佣金 + 滑点(size × tick × slip_tick)，按 entry_atr 换算为 ATR
- **禁止扁平 ATR 成本**（0.05 ATR/单边 低估 4.5 倍，跨品种 9 倍差）
- 仅 debug 时允许 `--flat-cost-debug`

### 模块 C · 组合优化层（本主题新增三大方向）

#### C.1 品种筛选（继承 kf:poc-value-area-asymmetry#KF-24 三大品种类型）

KF-24 发现「不存在通用 tier，品种类型决定最优档位」：

| 类型 | 品种 | 偏好 tier | 组合策略处理 |
|:---|:---|:---|:---|
| A · 金融贵金属 | IF/IH/IC/IM/T/TF/TS/au/ag | LP/SP 精选档 | A 类默认只用 L_seg12_high_up + S_seg12_high_dn |
| B · 化工建材黑色 | rb/hc/i/j/jm/TA/MA/PP/pp/l/v/eb/eg/sc/fu/bu | LL/SC 中档为主 | B 类默认只用 L_seg3_lowmid_up + S_seg34_high_dn |
| C · 农产品有色主流 | cu/al/zn/ni/sn/pb/m/y/p/c/cs/CF/SR/OI/RM/FG | SL 宽档补充 | C 类全部 5 档可用（含 S_seg2_mid_dn） |

**Gatekeeper 问题**：按类型筛选 vs 全品种 5 档，净夏普是否提升 ≥ 0.3？

#### C.2 信号强度加权（用 skew / atr / trend 的 rank 距离做线性加权）

当前分类器用硬阈值（skew≤0.30），导致阈值附近和阈值深处的信号权重相同。
候选加权方案（Gatekeeper 三选一）：

1. **W1 · Skew 距离加权**：`weight = |0.30 - skew_rank| / 0.30`（skew 越远离 0.30 权重越大）
2. **W2 · ATR 匹配度加权**：`weight = 1 - |atr_rank - 0.50|`（ATR 越靠近档位中心权重越大）
3. **W3 · 三维乘积加权**：`weight = w_skew × w_atr × w_trend`（三维独立打分相乘）

**Gatekeeper 问题**：最优加权方案 vs 等权，净夏普是否提升 ≥ 0.2？

#### C.3 多空权重优化（默认 1:1 → 校准到边际 IR 加权）

archive:2026-07-09-poc-va-shaping 中 S_seg12_high_dn 是唯一 A/A/A 三周期全 A，
但多头触发频率约为空头的 2.5 倍。候选方案：

1. **VW1 · 等权 1:1**（baseline）
2. **VW2 · IR 比例加权**：`w_L / w_S = avg_IR_L / avg_IR_S`（按 tier 平均 IR 分配）
3. **VW3 · 触发频率平衡**：`w_L / w_S = sqrt(freq_S / freq_L)`（平衡多空年贡献度）

**Gatekeeper 问题**：最优多空权重方案 vs 等权，净夏普是否提升 ≥ 0.2？

## 3. 与已冻结 / 活跃主题的关系

### 3.1 为什么不触碰 value-area 家族已证伪的四条

| 已证伪假设 | 本主题是否触碰 |
|-----------|--------------|
| POC 特殊性作为均值锚 | ❌ 不触碰（POC 只是 profile 构建的中间量，不作为交易锚） |
| Reacceptance 触发器特殊性 | ❌ 不触碰（分类器按小时定时判定，无 event 触发器） |
| 4+ ATR 距离档 edge | ❌ 不触碰（止损 1~2.5 ATR，目标由时间退出实现） |
| Rolling POC 独立价值 | ❌ 不触碰（rolling 只用于 skew/atr/trend 的 rank 计算，非 POC 追踪） |

### 3.2 与 poc-value-area-asymmetry 的分工

| 维度 | poc-value-area-asymmetry | va-asymmetry-composite |
|:---|:---|:---|
| 定位 | 交易背景**分类器组件** | 完整的**可实盘交易策略** |
| 产出 | tier 标签（6 类） | 订单、仓位、PnL、账户曲线 |
| 涵盖 | 入场信号判定 | 入场 + 出场 + 仓位 + 风控 + 品种筛选 + 加权 |
| 验证 | 7 层严格性（分类器层面） | 实盘口径 8 道闸门（策略层面） |

poc-value-area-asymmetry 主动性研究暂停，分类器 v4.0 契约冻结。
所有「分类器被用起来」的后续工作由本主题承接。

### 3.3 与 structural-shaping-alpha 的分工

| 维度 | structural-shaping-alpha | va-asymmetry-composite |
|:---|:---|:---|
| 假设 | 塑形本身有独立 alpha | 塑形本身无独立 alpha（已证伪），但塑形是 alpha 变现的必要条件 |
| 贡献 | First-Passage Designer + ν_implied + 真实成本模型 + KF 方法论 | 用已验证的塑形参数 + 成本模型把分类器的 alpha 变现 |

structural-shaping-alpha 阶段 1 完成（待冻结候选），其工具资产由本主题直接复用。

## 4. 研究路径（5 个阶段 · 广度优先）

按 methodology skill「最简规则广度扫描 → 品种边界确认 → 深度优化 → 工程化」的顺序：

### 阶段 0 · 立题与复现（Gatekeeper 1）
目标：复现 archive:2026-07-09-poc-va-shaping 的起点口径（5 档保留 + L_seg2_low_flat 淘汰 + 塑形参数 + 风控 v2），确认 baseline 数据链完整。
判据：年化净收益 ≥ 12% · 夏普 ≥ 1.8 · MaxDD ≤ 10%（与 archive 口径一致即通过）

### 阶段 1 · 组合三大方向的 Gatekeeper 扫描
目标：用最小可行实验分别验证 C.1 品种筛选 / C.2 信号强度加权 / C.3 多空权重优化 三个方向是否**各自**有独立增量价值。
方法：每个方向只跑 2-3 个候选（减少组合爆炸）· baseline 对 照 · paired 检验 · realistic-cost
判据：**每个方向独立增量 ≥ 0.2 夏普**（三选二或以上通过则进入阶段 2，否则该方向跳过）

### 阶段 2 · 最优组合搜索
目标：在阶段 1 通过的方向上做联合搜索（若三者都过则 3×3×3=27 组合，若两者过则 9 组合）。
方法：参数平台宽度 ≥ 30%（最优 vs 次优差异 < 30% 判为平台）· 反事实随机对照 · date-cluster bootstrap
判据：夏普 ≥ 2.5 · 年化净收益 ≥ 18% · MaxDD ≤ 8% · 品种保留率 ≥ 70%

### 阶段 3 · 样本外双维度验证
目标：**品种维度**（训练组开发 → 验证组测试）+ **时间维度**（前段训练 → 后段验证）
方法：Walk-Forward 或固定切分 · 20 品种按类型均分训练/验证
判据（两个维度都通过才可实盘）：
- 品种维度：验证组 ≥ 60% 品种正收益
- 时间维度：后段夏普劣化 ≤ 25%

### 阶段 4 · 工程化与模拟盘设计
目标：提取成 `workspace/strategies/va_asymmetry_composite.py` · vnpy BacktestEngine 可跑 · 输出 trade_clearings 与风控报表

## 5. 方法论前置约束（11 条 · 全继承 + 2 条新增）

继承自 value-area 家族（7 条）+ structural-shaping-alpha（2 条）：

1. 距离/大小/时间统一 ATR 归一化
2. 判据用期望净值（成本后），不用 reach_rate 或 win_rate 单指标
3. 多层对照：DirRandom baseline · asymmetry-shuffle baseline · 塑形参数消融对照
4. 配对差异检验：同一批事件下多方案配对
5. Cluster bootstrap：按 (contract, date) 聚类
6. Cross-sampling 护栏：阶段 2 起同物理时长跨周期一致（5m/15m 对比，防 KF-7 伪影）
7. 样本量透明：单品种 n<300 结论标注"信度不足"
8. **ν_implied 归因**：任何"发现正 mean"必须反算 ν = μ − σ²/2 并证明 > 0（KF-9）
9. **真实成本模型**：跨品种判决必用 realistic-cost（KF-5）

**本主题新增 2 条（策略层面特有）**：
10. **组合过拟合防护**：阶段 1 搜索空间 ≤ 9 候选（3 方向 × 3 方案）· Bonferroni family=9
11. **资金曲线过拟合防护**：阶段 3 必须做品种外 + 时间外双维度样本外，任一维度 fail 则回到阶段 2 简化方案

## 6. 关键风险 & 缓解

### 6.1 组合爆炸风险
风险：3 方向 × 3 方案 × 5 tier × 20 品种 = 900 组合 → 过拟合
缓解：阶段 1 先做「每方向独立 Gatekeeper」，无效方向直接排除；有效方向再联合搜索

### 6.2 L_seg2_low_flat 的误删风险
风险：archive 判 L_seg2_low_flat IR<0 是「全品种」结果，但可能在 C 类农产品上仍有价值
缓解：阶段 1 末尾补做「L_seg2_low_flat × C 类品种专项验证」，若 mean>0 则纳入 C 类白名单

### 6.3 名义暴露压缩风险
风险：archive 日均 653% 名义 → 压到 100% 会切掉 85% 的交易 → 夏普可能从 2.23 掉到 <1.5
缓解：阶段 0 就暴露压缩做敏感性曲线（100%/200%/400% 三档）· 选最优平衡点

### 6.4 分类器漂移风险
风险：v4.0 分类器在 2026-01~2026-06 上表现好，但旧数据（2023-2024）可能失效
缓解：阶段 3 时间样本外验证时，前/后段各 18 个月，确保双向稳定

## 7. 立题决策依据

### 为什么值得做
1. **alpha 独立证据链已完整**：poc-value-area-asymmetry 经过 4 个阶段、143 合约、36625 events、20 品种、7 层严格性验证 + FDR 校正，alpha 证据扎实（非 noise）
2. **塑形变现路径已 POC**：archive:2026-07-09-poc-va-shaping 已在同一分类器上证明「正确塑形参数 + 风控 → 年化 15.45% / 夏普 2.23」，说明 alpha 可变现
3. **三大优化方向有理论依据**：品种异质性（KF-24 已证）、信号强度（rank 越远置信度越高，常识）、多空 IR 不对称（S_seg12_high_dn A/A/A 已证）—— 三者都不是"瞎调参"
4. **成本可接受**：阶段 0-1 只需要读已有的 parquet 数据 + 向量化模拟，秒级出结果；不需要 vnpy 完整回测

### 为什么可能失败（诚实评估）
1. **名义暴露压缩过度**：日均 653% → 100% 会切掉很多高置信度交易 → 夏普可能掉半
2. **名义暴露压缩 + 品种筛选叠加**：两者都会减少交易数 → 样本量不足 → CI 变宽 → 结论不稳
3. **三大优化方向实际相互抵消**：品种筛选砍掉的交易恰好是强度加权想保留的 → 净增量为 0 或负
4. **样本外失败**：阶段 2 的最优参数在品种/时间外塌陷 → 回到分类器层面是"有信号但不稳定"

**任一阶段不通过即冻结主题**（或降级为「分类器 + 组合白皮书」，不做实盘），避免陷入深度调参陷阱。

## 8. 时间线预估

| 阶段 | 估计工作量 | 主要成本 |
|:---|:---|:---|
| 阶段 0 · 立题复现 | 几小时（文档 + 脚本 + 跑 baseline） | 低 |
| 阶段 1 · 三大方向 Gatekeeper | 半天 ~ 1 天 | 低（向量化，秒级/分钟级） |
| 阶段 2 · 最优组合搜索 | 1 ~ 2 天 | 中（27 组合 × bootstrap） |
| 阶段 3 · 样本外双维度 | 半天 | 中（数据切分 + rerun） |
| 阶段 4 · 工程化 | 2 ~ 3 天 | 中高（vnpy 集成 + 报表） |

## 9. 文档地图

| 目的 | 文档 |
|:---|:---|
| 主题入口 | 本文件 |
| **当前研究状态 + 关键发现清单** | [research-status.md](research-status.md) |
| **策略数学契约（唯一定义源）** | [strategy-math-spec.md](strategy-math-spec.md) v1.0 |
| 实验计划（阶段 0-4 候选矩阵 + 判定标准） | [experiment-plan.md](experiment-plan.md) v0.1 |
| 参数选择规格（分层 / 判据 / 回填格式） | [parameter-selection-spec.md](parameter-selection-spec.md) v0.1 |
| 工程实现细节（数据结构 / 桥接 / 性能） | [implementation-notes.md](implementation-notes.md)（占位版） |
| Archive 引用清单（继承 / 反例 / 资产复用） | [archive-references.md](archive-references.md) |
| Alpha 源分类器契约（上游） | theme:poc-value-area-asymmetry#classifier-math-spec |
| 塑形工具（上游） | theme:structural-shaping-alpha#first-passage-designer-math-spec |
| 家族反例（value-area） | [../../themes-frozen/value-area/README.md](../../themes-frozen/value-area/README.md) |
| 长期框架 | [../../../roadmap/strategy-research-framework.md](../../../roadmap/strategy-research-framework.md) |

## 10. 分支管理

- 开发分支：`experiment/va-asymmetry-composite`
- 分支基点：`experiment/poc-value-area-asymmetry` 最新 HEAD（或 `dev/0.5`，二选一按实际）
- 实现提交 hash：待记录（首次实验后回填）
