# poc-value-area-asymmetry · 实验计划

> 类型：Experiment Plan
> 状态：**v7（2026-07-08）· 阶段 1+2+3 完成 · 阶段 4 目标重新校准：从"三大方向落地"改为"互斥分类器 v3.0 验证"**
> 主题 README：[README.md](README.md)
> 研究状态：[research-status.md](research-status.md)
> 阶段 1 详细流水：[docs/workbench/poc-value-area-asymmetry-stage1-measurement.md](../../../workbench/poc-value-area-asymmetry-stage1-measurement.md)（v7）
> 阶段 2 详细流水：[docs/workbench/poc-value-area-asymmetry-stage2-guardrails.md](../../../workbench/poc-value-area-asymmetry-stage2-guardrails.md)（v4）
> 阶段 3 详细流水:[docs/workbench/poc-value-area-asymmetry-stage3-robustness.md](../../../workbench/poc-value-area-asymmetry-stage3-robustness.md)（v11）

本计划检验"POC 两侧 value area 不对称是否携带信息量"的命题。阶段 1+2+3
已完成 · **主题定位为"交易背景分类器"** · 阶段 3 产出 10 tier 体系但**存在
嵌套（LP ⊆ LL · SP ⊆ SC ⊆ SL）· 不满足"分类器每个 event 属于且仅属于一个
类"的基本定义**。**阶段 4 唯一目标：把 10 tier 拆成互斥类别 · 独立验证 ·
冻结分类器 v3.0**。完整策略（入场 / 出场 / 仓位 / cost）**不属于本主题** ·
留给下游"跨主题组合策略"主题。

## 0. 全局设定（所有阶段共用）

### 0.1 时间尺度

| 用途 | 周期 | 说明 |
|------|------|------|
| **交易 / 事件时钟 / 未来收益窗口** | **1h** | 5m ≈ 全随机游走，跳过；从 1h 起测 |
| **profile 构建原始数据** | **5m** | 保留 volume 分布分辨率 |
| **阶段 2 跨周期护栏** | 30m + 1h · 1h + 2h | 同物理时长跨采样一致性（防 KF-7 伪影） |

### 0.2 Profile 构建窗口（阶段 1 已锁定 W1）

阶段 1 扫描过 W1（前一天） / W2（前一周） / W3（rolling K=48/144/288/864）+
前 N 天（N=2/3/5），**结论**：**W1（前一天）唯一最强**，其他窗口一律弱化
或反向。阶段 2 起**仅用 W1**。

Value Area 定义：POC = volume 最大的 tick bin；VA = 从 POC 双向贪心扩展到
累计 70% volume 的最小连续区间；VAH / VAL = 上下边界。

**Leakage 硬约束**：profile 严格用 t-1 结束的 5m bar 构建，t 时刻信号使用
t-1 结束的 profile。

### 0.3 不对称度量（阶段 1 已锁定 A3）

四档度量 A1（volume 比）/ A2（距离比）/ A3（profile skew）/ A4（重心距离比）
中，**A3_skew 唯一在 A/B/C 三层证据链上一致通过**：
- 独立方向信号（洞察 E · cluster CI 排 0）
- 与 ATR 正交（洞察 I · Spearman |ρ| < 0.05）
- 段内配对下 DN 事件有独立增量（洞察 H · shuffle p=0.004）

**A3 定义**：volume 加权分布的三阶中心矩标准化偏度

```
mean = Σ p·v(p) / Σ v(p)
std  = sqrt( Σ (p-mean)²·v(p) / Σ v(p) )
A3   = Σ ((p-mean)/std)³ · v(p) / Σ v(p)
```

**阈值参数化**（洞察 C）：`|A3_skew| ≥ k×σ`，σ 为 per-contract std
（无未来函数版本用 rolling K=100 事件），k=1.5 通过 cluster CI 排 0。

**注**：A1/A2/A4 仅用 VA 内数据，A3 用整个 profile；这可能是 A3 强于
其他度量的原因（洞察 A · VA 外 tail 携带独立信息 · 独立主题候选）。

### 0.4 未来收益（阶段 1 已锁定 8h horizon）

阶段 1 扫描 N ∈ {1, 2, 4, 8} 小时，信号强度随 horizon 单调放大，
**8h 为峰值**。阶段 2 起以 **8h 为主 horizon**，阶段 2 补测 4h / 12h
作为 horizon 敏感度。

```
r_{t,N} = log(close_{t+N} / close_t)
单位：bps（= 1e4 × r_{t,N}）
```

### 0.5 品种覆盖

**阶段 1**：实际用 19 合约（原 10 品种 × 主力 + 9 个诊断扩充）
- 原 10：rb2601, i2601, cu2601, al2601, sc2512, TA601, m2601, p2601, SR601, CF601
- 扩 9：c2601, y2601, cs2601, ag2601, hc2510, MA601, OI601, RM601, FG601

**阶段 2**：**扩合约月份**至 20 品种 × 60-70 合约（继承 Stage 4b 口径），
用于样本外验证与 CI 稳健性提升。

**阶段 3**：扩至全部合约月份 + 更长历史 · 波动率制度分层。

### 0.6 交易成本

- 阶段 1 不涉及交易，无成本；已用 realistic-cost 估计"净利润空间"（洞察 B）
- 阶段 2 起使用 realistic-cost（`workspace/common/contract_specs.py`），
  继承 KF-5 教训（成本单位统一为合约面额归一化 bps）

### 0.7 统计口径

**阶段 1 · 信息量层**（已完成）：
- Spearman IC（pooled + per-symbol）· cluster bootstrap（按 contract 聚类）5000 次
- 段内配对 t 检验 + Shuffle 检验（洞察 H）
- Bonferroni 校正（family=48/240）
- k×σ 阈值下 cluster CI 判据（洞察 E/K）

**阶段 2 起 · 交易层**：
- 沿用 structural-shaping-alpha experiment-plan §0.5 类 I / II 判据
- 期望净值 + paired 检验 + cluster bootstrap + realistic-cost
- 反算 ν_implied 必须显著 > 0（KF-9 硬约束）
- 跨周期护栏（KF-7 硬约束）

### 0.8 主题定位（阶段 2 收尾后明确 · 阶段 3/4 遵循）

**本主题不是完整的交易策略 · 而是"交易背景分类器"**：

- 使用数据：**只用前一交易日 5m volume profile + rolling 20 日日线特征**
- 触发时刻：每小时整点（当天 · 无当天数据）
- 判定结果：**当前时段是否属于某种"高胜率/高幅度"环境**
- 未指定：**当天入场时机 · 具体订单类型 · 止盈止损 · 仓位管理**

**因此 4 大主线的正确解读是**：

> "如果当前时段满足（skew + atr + trend）某个组合 · 那么未来 4-8h **平均**
> 上有显著方向偏差（多头 +45 bps · 空头 +40 bps）· 100% 品种保留度 ·
> Bonferroni 严格显著。**这是一个可作为其他策略的 quality filter 或
> 与入场/出场规则组合使用的背景标签**。"

**这个定位决定了阶段 3/4 的正确目标**：

1. **不追求快速上线**：因为不含入场/出场规则 · 不能独立运行
2. **不做 realistic-cost 净收益上线判决**：因为没有具体订单
3. **追求"背景分类器"的稳健性**：跨品种 · 跨周期 · 跨波动率制度 · 跨时段
4. **阶段 4 是"如何被使用"**：作为 quality filter 组合 · 或与入场规则合并

**KF-8 账户闸门的适用性**：需在阶段 4 具体入场规则出现后才能真正评估
（阶段 3 只做"背景分类器"层面的初步频率与幅度分布估算）。

---

## 阶段 1 · 测量 + 信息量（✅ 已完成 · 2026-07-07）

**目标**：回答"不对称是否存在、是否稳定、是否对未来收益有可复现的
统计关联"，暂不做交易。

**结论**：**通过。找到独立方向信号 · 严格无未来函数下多层组合 CI 排 0**。

### 1.1 核心发现摘要

**主线**（严格无未来函数版本 · cluster bootstrap 5000 次）：

| 触发条件 | n | mean bps | hit | 95% CI | p_two |
|---------|---|---------|-----|--------|-------|
| **DN 单层**（A3_skew ≤ -1.5×σ_roll · dedup_8h）| 464 | +29.4 | 55.8% | [+8.7, +52.3] | 0.005 |
| **DN + 低日线 ATR_10** | 283 | +39.8 | 61.1% | [+9.3, +70.8] | 0.007 |
| **DN + 涨段 + 低日线 ATR_10** ⭐ | 133 | **+56.9** | **64%** | [+14.0, +121.2] | **0.002** |

**信号叠加**：每加一层 filter 增益 8-17 bps · 每层都独立 CI 排 0。

### 1.2 关键洞察（升级为主题 KF 候选）

- **B** · 成本口径基准差异（方法论级）
- **C** · k×σ 参数化阈值（方法论级）
- **E** · cluster bootstrap CI 排 0（显著性级）
- **F** · DN 分布正偏尖峰厚尾 · UP 无独立信号
- **G** · 信号顺势随大行情走
- **H** · ⭐⭐ 段内配对独立信息量 · shuffle p=0.004
- **I** · ⭐⭐ 与 ATR 正交 · ATR 意外作 filter
- **J** · σ 无未来函数版本 mean 稳定
- **K** · ⭐⭐⭐ 严格无未来函数下 3 档位 CI 排 0（主线 +57 bps · p=0.002）

### 1.3 已排除的假设

- ❌ UP（顶厚）侧独立空头信号：扩至 19 合约后仍无
- ❌ "顶厚→跌"对称假设：跌段 UP mean = -4 bps · 无加速下跌
- ❌ profile 窗口 rolling / 前 N 天版本：全部弱化或反向
- ❌ 反转空头（DN + 平 + 高 ATR）：严格 rank 版本 n 掉 74% · 降级弱线索

### 1.4 输出

- workbench：[poc-value-area-asymmetry-stage1-measurement.md](../../../workbench/poc-value-area-asymmetry-stage1-measurement.md)（v7）
- 数据文件：`project_data/logs/poc_va_asymmetry_stage1/`（14 个 CSV）
- 复现脚本：`scripts/ai_tmp/poc_va_asymmetry_*.py`（12+ 脚本）

---

## 阶段 2 · 跨周期护栏 + ν_implied · 样本外扩展 · 网格搜索（✅ 已完成 · 2026-07-07）

**触发条件**：阶段 1 已通过（✅）· 主线信号锁定为 **DN + 涨段 + 低日线 ATR_10**。

**结论**：**严格闭环 · 4 主线全数通过 Bonferroni + ν_implied + 跨周期护栏 · 100% 品种保留度**。

### 2.1 阶段 2 起点（基于阶段 1 严格无未来函数三档位）

| 档位 | 触发 | 阶段 1 结果 |
|------|------|------------|
| 主线 | DN + 涨段（trend rank ≥ 67% · rolling 20 日）+ 低 ATR（rank ≤ 50%）| +57 bps · p=0.002 |
| 单层 filter | DN + 低 ATR | +40 bps · p=0.007 |
| 单层 base | DN 单独（A3_skew ≤ -1.5×σ_roll100）| +29 bps · p=0.005 |

### 2.2 三大硬门槛（全过）· 三大补充洞察

**门槛 1 · 跨周期护栏（KF-7）**：✅
- 15m/30m/1h/2h 四时钟 · 相邻周期 CI 全排 0

**门槛 2 · ν_implied 反算（KF-9）**：✅
- ν = μ - σ²/2 = +56.1 bps · CI [+13.5, +120] · p=0.002

**门槛 3 · 样本外扩展（44 合约多年历史）**：✅
- 主线 CI 排 0（+25 bps · hit 68.5%）· 但 DN 单层塌陷 · 品种保留 57.1%

**补充洞察 L · 触发时段衰减**：无显著衰减 · 全天可挂单
**补充洞察 M · 空头方向探索**：找到候选 E · UP+跌+高ATR · 4h horizon 有效
**补充洞察 N · 参数网格搜索**：96 组合双向扫描 · 找到多空 sweet spot（幅度双双翻倍）
**补充洞察 O · 严格收尾**：Bonferroni + ν + 跨周期三重验证 · 4/4 主线全过

### 2.3 阶段 2 最终定型四大主线（阶段 3 起冻结）

**多头首选（精选事件）**：
```
IF signed_skew_rank_rolling100 ≤ 0.10
   AND daily_atr_10_bps_rolling20d_rank ≤ 0.70
   AND trend_ret_10d_rolling20d_rank ≥ 0.75
THEN 做多 · 持仓 8h
预期：mean +44.8 bps · hit 78.9% · 每合约 3-5 天 1 次
Bonferroni p < 0.00052 ✅ · ν_implied +44.5 · 100% 品种保留度
```

**多头宽松（放宽 skew · 高触发率）**：
```
IF signed_skew_rank_rolling100 ≤ 0.30
   AND daily_atr_10_bps_rolling20d_rank ≤ 0.70
   AND trend_ret_10d_rolling20d_rank ≥ 0.75
THEN 做多 · 持仓 8h
预期：mean +39.6 bps · hit 64.2% · 每合约 1-2 天 1 次（触发率 3x）
Bonferroni p < 0.00052 ✅ · ν_implied +39.1
```

**空头首选（崩盘前奏）**：
```
IF signed_skew_rank_rolling100 ≥ 0.70
   AND daily_atr_10_bps_rolling20d_rank > 0.80
   AND trend_ret_10d_rolling20d_rank ≤ 0.20
THEN 做空 · 持仓 4h
预期：mean +40.0 bps · hit 63.0% · 每合约 3-5 天 1 次
Bonferroni p < 0.00052 ✅ · ν_implied +39.4 · 100% 品种保留度
```

**空头宽松（放宽 atr · 高触发率）**：
```
IF signed_skew_rank_rolling100 ≥ 0.70
   AND daily_atr_10_bps_rolling20d_rank > 0.50
   AND trend_ret_10d_rolling20d_rank ≤ 0.20
THEN 做空 · 持仓 4h
预期：mean +27.4 bps · hit 60.6% · 每合约 1-2 天 1 次（触发率 2x）
Bonferroni p < 0.00052 ✅ · ν_implied +27.0
```

### 2.4 输出

- workbench：[poc-value-area-asymmetry-stage2-guardrails.md](../../../workbench/poc-value-area-asymmetry-stage2-guardrails.md)（v4）✅
- 数据文件：`project_data/logs/poc_va_asymmetry_stage2/`（15+ CSV）
- KF 定型：15 条（`KF-poc-va-01` ~ `KF-poc-va-15`）· 见 research-status.md

---

## 阶段 3 · 背景分类器稳健性深度检验（✅ 已完成 · 2026-07-07）

**触发**：阶段 2 通过（✅）· 4 大主线已定型。

**目标**：**把"背景分类器"打到能被其他策略/主题信赖的稳健水平**。不追求上线 ·
不做入场出场规则设计 · 只回答"这个背景标签的可靠性边界在哪里"。

**结论**：**5/5 任务全过 · 6 大洞察（P/Q/R/S/T/U）· 7 层严格证据链完整 ·
输出 A 级白名单 5 档 + B 级 3 档**。

### 3.1 阶段 3 五大任务完成情况

| 任务 | 判据 | 结果 |
|------|------|------|
| 1 · 分品种深挖 | ≥80% 品种保留 edge | ✅ 4/4 主线（平均 95.4%）|
| 2 · 3-way ATR 制度 | ≥2 主线依赖性成立 | ✅ 3/4（多头宽松除外）+ 深挖发现洞察 P |
| 3 · Regime transition 衰减 | <20% 或明确使用边界 | ✅ 1/4 全过 · 3/4 明确使用边界 + 后置实验发现洞察 T |
| 4 · 收益分布刻画 | 输出使用说明书 | ✅ workbench §3（多头 3 机制）+ §5（洞察 Q · 空头单机制）|
| 5 · 触发互斥性 | 嵌套 + 互斥明确 | ✅ 首选⊂宽松嵌套 · 多空完全互斥 |

### 3.2 阶段 3 六大核心洞察（KF-16 ~ KF-21）

**洞察 P · 3 种多头反弹机制**（⭐⭐⭐）
- 低 ATR：日常均值回归（8h · payoff 1.46）
- 中 ATR：震荡后秩序恢复（8h · 尖峰厚尾 kurt=12）
- 高 ATR：恐慌 V 反弹（4h 完成 118% · 后期回吐）
- **阶段 4 可拆成 3 个多头子策略 · 持仓期自适应**

**洞察 Q · 空头单机制 vs 多头多机制**（⭐⭐⭐）
- 空头只有"崩盘前奏"1 种机制 · **必须高 ATR**
- 低 ATR 空头 8h 反转 -152% · 中 ATR 弱信号
- **建议空头收敛为 atr≥0.67 单一档位**

**洞察 R · Regime transition 信号衰减**（⭐⭐⭐）
- 46% 事件在过渡期 · 多头首选衰减仅 11%
- **通用规律**：filter 严格度和 regime 稳定 filter 的价值反向

**洞察 S · ATR × Trend 正交**（⭐⭐⭐）
- atr_rank 与 trend_rank r=+0.003（完全独立）
- ATR = 强度 · Trend = 方向 · **联合筛选是核心 filter 架构**
- 否定"高 ATR = 跌段"直觉（高 ATR 涨跌对称）

**洞察 T · 空头宽松的救赎 · Regime 稳定 filter**（⭐⭐⭐）
- 空头宽松 + regime 稳定 → +36 bps · 增益 31.6%
- 多头首选加 regime filter 增益仅 7.5% · 不值得
- **阶段 4 分主线定制 regime 处理**

**洞察 U · 稳定 vs 转换 · 空头 horizon 曲线差异**（⭐⭐⭐）
- 空头首选：稳定日 8-12h 峰 +67 → +70 · 转换日 4h 峰 +32 · 12h 归零
- **严格 t-test 修正**：mean 层面差异仅空头宽松显著
- **阶段 4 空头出场策略必须分**：稳定日追踪止损 · 转换日目标止盈 4h

**KF-22 · 采样精度边界 · "数据边界不可造假"**（⭐⭐⭐ 跨主题方法论）
- 严格 date-cluster bootstrap · A 级 5 主线全部保留 · 多头首选·稳定升级 B→A
- prefix 池化反证：空头 4/5 档 Bonferroni 降级 · **不能通过池化补精度**
- 冻结：rank 单位 = per-contract · bootstrap 单位 = (contract, date)
- 详见 workbench §12.12

**KF-23 · 分位 × ATR 制度信号地图**（⭐⭐⭐ 分类器细化 · 阶段 4 起点）
- 12 格深度诊断 · **多头 5 稳定甜蜜点 + 空头 3 反常甜蜜点**
- **段3·ATR低**（skew∈(0.19,0.25] · atr≤0.33）：mean **+85 · hit 83%** · 100% 品种保留
- **段4·ATR高**（skew∈(0.25,0.30] · atr>0.67）：新机制 · 高 ATR 波动率反弹
- 相邻格子方向一致（多头 100% · 空头 86%）· 阶段 4 分档策略安全
- 教训：**"过拟合" vs "制度依赖" 辨析** · 必须拆分制度维度再判决
- 详见 workbench §13

### 3.3 阶段 3 分类器 7 层严格性验证（workbench §12 · A~G）

**A · Bonferroni**（family=8 · p<0.00625）：稳定期 4/5 · 转换期 2/5 通过
**B · 稳定 vs 转换差异**：仅空头宽松 p=0.024 显著（其余 mean 层面不显著）
**C · 分类器性能**（v8 修正后）：年化 Sharpe gross +1.06 ~ +1.48 · net-15bps +0.77 ~ +1.10 · 单笔 IR +0.35 ~ +0.60（旧 +8~+15 是错误口径 · 已作废）
**D · 品种保留率**：稳定期 90-100% · 转换期 82-100%
**E · 反事实基准**：5 组合 p=0.0000（**明确不是随机噪声**）
**F · 组合独立性**：空头 3 主线 Jaccard 0.65-0.86（本质同一信号）
**G · Time-in-market**：占用天数比 <0.4%（极稀疏 · 不冲突其他策略）

### 3.4 阶段 3 分类器"评级白名单"（阶段 4 起点）

**A 级 · 可直接用于阶段 4 或其他策略**（5 档 · Sharpe/IR 数据 v8 修正版）：
1. **多头宽松·稳定**（性价比之王 · gross Sharpe +1.48 · net +1.10 · 触发 60/合约/年）⭐
2. **多头首选·全**（最强单笔 · IR 0.577 · gross Sharpe +1.59 · net +1.18）
3. **多头首选·转换**（Bonferroni ✅ · Sharpe +1.22 · IR 0.56）
4. **空头首选·稳定** or **空头收敛·稳定**（二选一 · 高度重叠 · 推荐收敛 · Sharpe +1.20-1.24）
5. **空头宽松·稳定**（gross Sharpe +1.40 · net +0.89 · 触发 77/合约/年 · 高频空头）

**B 级 · 可用但需谨慎**（3 档）：
- 多头首选·稳定（n=52 少 · Bonferroni fail · 待扩样本外）
- 多头宽松·转换（Bonferroni p=0.0056 · 边缘）
- 空头宽松·转换（Bonferroni fail · 但洞察 T 有 mean 差异证据）

**C 级 · 暂不用**（2 档）：
- 空头首选·转换（Bonferroni fail · p=0.032）
- 空头收敛·转换（Bonferroni fail · p=0.014）

### 3.5 输出

- workbench：[poc-value-area-asymmetry-stage3-robustness.md](../../../workbench/poc-value-area-asymmetry-stage3-robustness.md)（v7）✅
- 数据文件：`project_data/logs/poc_va_asymmetry_stage3/`（15+ CSV）
- KF 定型：新增 6 条（`KF-poc-va-16` ~ `KF-poc-va-21`）· 累计 21 条 · 见 research-status.md
- 分类器代码规范化：待阶段 4 起做（提取 `workspace/common/poc_va_classifier.py`）

---

## 阶段 4 · 互斥分类器 v3.0 验证与冻结

**触发**：阶段 3 通过（✅）· 10 tier 严格证据链完整 · **但 tier 之间存在嵌套 · 不满足分类器互斥性定义**。

**目标**：**把 10 tier 拆成互斥类别 · 每类独立通过完整严格性验证 · 冻结分类器 v3.0 契约**。

### 4.1 阶段 4 唯一目标 · 互斥分类器构造

**分类器基本定义**（阶段 4 起遵循）：
- 一个分类器 = 从事件空间到类别空间的**单值函数**
- **每个 event 属于且仅属于一个类别**（含"未分类"）
- 类别之间**严格互斥** · 触发次数无重复计数

**当前问题**（阶段 3 遗留）：
- 10 tier 存在嵌套：`LP ⊆ LL` · `SP ⊆ SC ⊆ SL`
- 一个 skew=0.08 事件同时命中 `LP_all + LP_stable + LL_all + LL_stable` · **是"多标签系统" · 不是分类器**

**阶段 4 处理路径**：**从 5 主线嵌套拆成 5 主线互斥（方案 γ）**：

```
多头（skew ≤ 0.30 ∧ atr ≤ 0.70 ∧ trend ≥ 0.75）:
  LP_only:  skew ∈ [0, 0.10]                (原 LP)
  LL_only:  skew ∈ (0.10, 0.30]             (原 LL \ LP)

空头（skew ≥ 0.70 ∧ trend ≤ 0.20）:
  SP_only:  atr > 0.80                       (原 SP)
  SC_only:  atr ∈ (0.67, 0.80]               (原 SC \ SP)
  SL_only:  atr ∈ (0.50, 0.67]               (原 SL \ SC)

× 稳定/转换 = 10 互斥类别 + "未分类"
```

**总类别数**：10 互斥 tier + 1 未分类 = **11 类**（family size = 10 用于 Bonferroni）

### 4.2 阶段 4 执行步骤

#### Step 1 · 定义互斥类别 · 描述性统计（30-45 分钟）

- 用现有阶段 3 数据 · 应用互斥定义重新分组
- 对每个互斥类别输出：
  - n_events / n_indep_days
  - 主导品种 top3
  - 品种分布（几个品种触发过）
  - mean bps / hit / payoff（描述性）
- **验证互斥性**：∑ 各类 n 应等于总触发数（无重叠）

**判据**：若某类 n < 15 · 该类**不进入 Step 2**（样本不足以判决）。

#### Step 2 · 每类独立完整 7 层严格性验证（45-60 分钟）

对**通过 Step 1 门槛**的每个类别 · 独立跑：

| 层 | 判据 | 阈值 |
|----|------|------|
| 1 · 样本量 | n_events / n_indep_days | ≥ 15 / ≥ 5 |
| 2 · CI（严格 date-cluster）| 95% CI 排 0 | 是 |
| 3 · Bonferroni | family size = 10 · p < 0.005 | 是 |
| 4 · 反事实 | vs 随机触发 · p < 0.001 | 是 |
| 5 · 品种保留率 | 单品种 mean > 0 比例 | ≥ 80% |
| 6 · 单笔 IR | mean / std | ≥ 0.30 |
| 7 · 时间稳定性 | 前后半分 mean 差 / 全 mean | ≤ 50% |

#### Step 3 · 判决 + 分档（15 分钟）

- **A 级**：7/7 通过 → 分类器契约 v3.0 白名单主类
- **B 级**：6/7 通过 · 或 5/7 通过但样本 n<30 → 备用类别（阶段 4+ 扩样本再验）
- **未分类**：≤ 4/7 通过 → **不进入分类器输出** · tier = None

#### Step 4 · 更新分类器契约 v3.0（30 分钟）

**改造 `classifier-math-spec.md`**：
- `ClassifierOutput.tier: str | None`（唯一输出 · 不再 `tiers_hit: List[str]`）
- §7 触发条件改为互斥集合定义
- 加入互斥性数学证明（§10.3 更新）
- 版本号 v2.0 → v3.0

**改造 `parameter-selection-spec.md`**：
- §1 只留互斥类别的评级表
- 删除"关系 A/B/C"和"去重规则"章节（§1.0 · §1.5）
- 每类独立单卡（§2）

**更新 `research-status.md`**：
- 加 KF-24（分类器互斥化 · v3.0 冻结）
- 更新 A 级白名单

**更新 workbench**：
- 新增 workbench：`docs/workbench/poc-value-area-asymmetry-stage4-classifier-v3.md`
- 记录 Step 1-3 完整证据链

### 4.3 阶段 4 判决

**通过条件**（进阶段 5 · 或结题）：
- ✅ **至少 3 个互斥类别通过 A 级判据**
- ✅ 至少覆盖多头 + 空头两个方向
- ✅ 分类器契约 v3.0 冻结 · workbench 归档

**边缘条件**（分类器可用但稀疏）：
- ⚠️ 只有 1-2 类通过 A 级 · 但方向明确
- 分类器可实现 · 只暴露少数类别 · 主题**"活跃 · 稀疏可用"**状态

**失败条件**（主题冻结）：
- ❌ 0 类通过 Bonferroni
- 说明"互斥后 alpha 全消失" · 分类器无严格证据支撑
- 主题降级为"探索性发现" · 迁到 `themes-frozen`

### 4.4 阶段 4 后置动作（若通过）

**Step 5 · 代码规范化**（阶段 4 通过后 · 1-2 天）：
- 提取 `workspace/common/poc_va_classifier.py`
- 契约映射为可复用组件
- 单元测试对齐阶段 3 CSV 输出
- 供下游主题（跨主题组合策略）引用

**Step 6 · 主题状态更新**：
- **主动性研究暂停 · 但不进 themes-frozen**（分类器持续可用 · 供其他主题引用）
- 归档：`docs/archive/strategy-research/2026-XX-XX-poc-value-area-asymmetry-classifier-v3`
- 12 格候选（KF-23）作为**"未来细化候选" · 留给下游主题深挖**

### 4.5 明确排除的内容（不属于本主题）

**阶段 4 明确不做**：
- ❌ 入场时机（限价 vs 市价 · 追高 vs 回踩）
- ❌ 出场规则（止损 / 止盈 / 追踪 / 时间衰减）
- ❌ 仓位管理（Kelly / 定额 / ATR 归一化）
- ❌ 交易成本精算（realistic-cost）
- ❌ Sharpe / MDD / Calmar / 覆盖率
- ❌ 与其他主题的组合验证（如 quality filter）
- ❌ 12 格分位×制度深化验证

**理由**：以上都属于**"完整策略"层面** · 需要跨主题组合才能有意义。本主题的产出是**分类器组件** · 不是策略。

### 4.6 下游主题（阶段 4 通过后）

**若分类器 v3.0 成立** · 后续可立**新主题**（不属于本主题）：

1. **`poc-va-shaping-composite`** — 分类器 + 结构塑形组合策略
   - 引用本分类器 + `structural-shaping-alpha` combo
   - 有独立的 `strategy-math-spec.md`
   - 承担入场/出场/仓位/cost 责任

2. **`poc-va-quantile-refinement`** — 分位×制度细化研究
   - 深挖 KF-23 的 12 格候选甜蜜点
   - 若通过 · 反向升级本主题分类器 tier

3. **`poc-va-tail-asymmetry`** — VA 外 tail 独立信息假设（KF-01 遗留）

---

**任一阶段判决完成后，若无通过条件，冻结主题并归档 KF**。

## 时间线

| 阶段 | 状态 | 计算量 | 备注 |
|------|------|-------|------|
| 阶段 1 · 测量 + IC | **✅ 已完成 2026-07-07** | 数十分钟脚本 + 数小时文档 | 主线锁定 · 12+ 洞察 · KF 8 条 |
| 阶段 2 · 跨周期护栏 + ν_implied + 样本外 + 网格搜索 | **✅ 已完成 2026-07-07** | 分钟级到数十分钟 | 4 大主线定型 · Bonferroni 全过 · KF 15 条 |
| 阶段 3 · 背景分类器稳健性深度检验 | **✅ 已完成 2026-07-07** | 数小时 | 5 大任务 · 6 大洞察 · 7 层严格证据链 · KF 23 条 · 10 tier 体系（含嵌套）|
| 阶段 4 · 互斥分类器 v3.0 验证与冻结 | **待启动** | 2-3 小时 | 拆分互斥 + 独立完整验证 · 冻结契约 v3.0 · **不做完整策略** |

---

## 输出

- 阶段 1：[docs/workbench/poc-value-area-asymmetry-stage1-measurement.md](../../../workbench/poc-value-area-asymmetry-stage1-measurement.md)（v7）✅
- 阶段 2：[docs/workbench/poc-value-area-asymmetry-stage2-guardrails.md](../../../workbench/poc-value-area-asymmetry-stage2-guardrails.md)（v4）✅
- 阶段 3：[docs/workbench/poc-value-area-asymmetry-stage3-robustness.md](../../../workbench/poc-value-area-asymmetry-stage3-robustness.md)（v11）✅
- 阶段 4：`docs/workbench/poc-value-area-asymmetry-stage4-classifier-v3.md`（待建）
- 主题稳定后归档到 `docs/archive/strategy-research/`
- 分类器契约 v3.0 冻结后不再撰写 strategy-math-spec.md（本主题不承担完整策略）

---

## 关联主题

- **反例（同大方向）**：[value-area 家族](../../themes-frozen/value-area/README.md)
- **方法论前置**：[structural-shaping-alpha](../structural-shaping-alpha/README.md)
  （KF-1 / KF-4 / KF-5 / KF-7 / KF-8 / KF-9 全部适用）
- **上游 Roadmap**：[Structural Alpha 长期共识框架](../../../roadmap/strategy-research-framework.md)
- **衍生候选主题**（阶段 1 洞察 A）：`poc-va-tail-asymmetry` · VA 外 tail 携带信息假设
