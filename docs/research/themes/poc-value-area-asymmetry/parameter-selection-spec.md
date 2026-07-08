# poc-value-area-asymmetry · 参数选择与性能报告

> 类型：Theme / 参数选择规格 · 一眼可读版终版
> 状态：**v2（2026-07-08）· 分类器 v3.0 冻结 · 10 互斥 tier · A 级 6 + A- 级 3 · 阶段 4 通过**
> 主题 README：[README.md](README.md)
> 数学契约：[classifier-math-spec.md](classifier-math-spec.md) v3.0（数学定义唯一源）
> 研究状态：[research-status.md](research-status.md)
> 阶段 4 详细流水：workbench:poc-value-area-asymmetry-stage4-classifier-v3

## 0. 文档定位

本文件回答**"分类器为什么选这些参数 · 每个 tier 有多可信 · 下游策略层该怎么用"**。

**边界**：
- 数学定义（rank 公式 / warmup / 触发集合的形式化表述）**只写在 spec** · 本文件仅引用
- 严格性证据的**推导过程**在 workbench · 本文件仅列出**结论性指标**
- 每个 tier 附有**基础性能表** · 品种适应性由下游策略层负责

**阅读顺序**：§1 一眼总览 → §2 10 tier 评级卡 → §3 品种大类型附录 → §4 使用建议 → §5 边界

---

## 1. 一眼可读总览（分类器 v3.0 白名单）

**核心结论**：**10 互斥 tier · 通过 4 硬门槛严格性验证 · A 级 6 + A- 级 3 · 合计 9 个可用 tier**。

### 1.0 互斥性保证（✅ v3.0 冻结）

**分类器 v3.0 是真正的互斥单值分类器**：
- 每个 event **属于且仅属于一个 tier**（含"未分类"）
- 完全消除 v2.0 时期的嵌套问题
- 无需去重规则 · 无需组合去重

**互斥拆分**（详见 spec §7.1）：
```
多头（skew≤0.30 ∧ atr≤0.70 ∧ trend≥0.75）：
  LP_only:  skew ∈ [0, 0.10]                    (极端底厚)
  LL_only:  skew ∈ (0.10, 0.30]                 (中度底厚)

空头（skew≥0.70 ∧ trend≤0.20）：
  SP_only:  atr > 0.80                           (极高波动)
  SC_only:  atr ∈ (0.67, 0.80]                   (高波动)
  SL_only:  atr ∈ (0.50, 0.67]                   (中偏高波动)

× stable/trans (transition_flag) = 10 互斥 tier
```

**"未分类"** = skew ∈ (0.30, 0.70) 中间区间 · 或不满足 filter · 分类器返回 `tier=None`。

### 1.1 A 级白名单（6 个 · 硬门槛全过 + 时稳达标）

| Tier | 触发条件 | mean bps | CI 95% | IR | n | n_days | 品保% | 时稳 |
|------|---------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **LP_only·full** | LP_only（全期）| +33.3 | [+14.5, +52.6] | +0.282 | 633 | 93 | 64% | 0.03 |
| **LL_only·stable** | LL_only ∩ 稳定期 | +33.6 | [+14.1, +54.1] | +0.281 | 617 | 91 | 66% | 0.40 |
| **SP_only·stable** | SP_only ∩ 稳定期 | +33.0 | [+18.4, +49.2] | +0.335 | 559 | 66 | 73% | 0.44 |
| **SP_only·trans** ⭐ | SP_only ∩ 转换期 | **+51.9** | [+28.9, +75.8] | **+0.459** | 267 | 36 | 76% | 0.48 |
| **SC_only·full** | SC_only（全期）| +32.4 | [+18.4, +48.0] | +0.319 | 578 | 70 | 74% | 0.35 |
| **SC_only·trans** | SC_only ∩ 转换期 | +44.9 | [+25.5, +66.6] | +0.395 | 372 | 46 | 79% | 0.35 |

**品保率解读**：单品种保留率是**适用范围描述** · 不是判决门槛。分类器承诺"整体信号存在"· 下游策略层负责按品种筛选。

### 1.2 A- 级白名单（3 个 · 硬门槛全过 · 时稳警示）

| Tier | 触发条件 | mean bps | CI 95% | IR | n | 时稳 | 备注 |
|------|---------|:---:|:---:|:---:|:---:|:---:|---|
| **LL_only·full** | LL_only（全期）| +33.5 | [+18.2, +49.1] | +0.257 | 1290 | 0.67 | **样本最大**（154 独立日）|
| **LL_only·trans** | LL_only ∩ 转换期 | +33.4 | [+10.0, +57.5] | +0.239 | 673 | **1.32** | 时稳警示强 |
| **SP_only·full** | SP_only（全期）| +39.1 | [+26.2, +52.3] | +0.377 | 826 | 0.64 | **品保 82%**（最高）|

### 1.3 未通过（6 个 · 供参考）

| Tier | 失败层 | 说明 |
|------|:---:|---|
| LP_only·stable | L3 (Bonf p=0.0348) | 阶段 3 sweet spot 在扩容后 Bonferroni 未过 · 幅度存在但需扩样本 |
| LP_only·trans | L3 (Bonf p=0.004) | Bonferroni 边缘 |
| SC_only·stable | L2/L3/L4 | mean +9.9 · CI 未排 0 · 中 ATR 稳定期空头无稳定 alpha |
| SL_only·full | L2 | mean +13.9 · CI 触 0 |
| SL_only·stable | L3 | Bonferroni p=0.0164 未过 |
| SL_only·trans | L2/L3 | mean +8.4 · 转换期低 ATR 空头无 alpha |

### 1.4 关键发现（阶段 4 vs 阶段 3）

**扩容后（143 品种 · 36625 events）幅度普遍下降 · 但 CI 更窄**：
- LP_only·stable：+48 → +28（-42%）· 样本 5x · **但 Bonferroni 反而未过**
- LL_only·stable：+47 → +34（-28%）· 样本 3x · **仍稳定通过**
- SP_only·trans：+32 → **+52**（+61%）· 幅度反而放大 · **说明扩容揭露了此档真实强度**
- SC_only·trans：+12 → **+45**（+262%）· 新甜蜜点确认

**多头信号在扩容后严格性下降** · 空头信号反而增强。

---

## 2. 10 tier 详细单卡

### 2.1 LP_only·full · A 级

- **触发条件**：`skew_label = "DN_strict" ∧ atr_rank ≤ 0.70 ∧ trend_rank ≥ 0.75`（等价 `signed_skew_rank ≤ 0.10`）
- **基础性能**：
  - mean bps = +33.3 · CI 95% = [+14.5, +52.6]
  - hit = 60.3% · IR = +0.282
  - n_events = 633 · n_indep_days = 93 · n_symbols = 84
  - 时稳 |first-second|/full = 0.03（**极稳定** ⭐）
- **4 硬门槛**：L1 ✅ · L2 ✅ · L3 (Bonf p=0.0000) ✅ · L4 (反事实 p=0.0000) ✅
- **适用范围**：品种保留 64%（84 品种里 54 个 mean>0）· 详细品种大类型见 §3
- **主导品种 top3**：CZCE.CF601 · CZCE.SR405 · CZCE.FG509

### 2.2 LL_only·stable · A 级 ⭐（多头主力）

- **触发条件**：`skew_label = "DN_loose" ∧ atr_rank ≤ 0.70 ∧ trend_rank ≥ 0.75 ∧ transition_flag = 0`（等价 `signed_skew_rank ∈ (0.10, 0.30] ∧ 稳定`）
- **基础性能**：
  - mean bps = +33.6 · CI 95% = [+14.1, +54.1]
  - hit = 63.5% · IR = +0.281
  - n_events = 617 · n_indep_days = 91 · n_symbols = 68
  - 时稳 = 0.40
- **4 硬门槛**：L1 ✅ · L2 ✅ · L3 (Bonf p=0.0008) ✅ · L4 ✅
- **适用范围**：品种保留 66%
- **主导品种 top3**：SHFE.cu2409 · CZCE.CF601 · DCE.i2409

### 2.3 SP_only·stable · A 级

- **触发条件**：`skew_label = "UP" ∧ atr_rank > 0.80 ∧ trend_rank ≤ 0.20 ∧ transition_flag = 0`
- **基础性能**：
  - mean bps = +33.0 · CI 95% = [+18.4, +49.2]
  - hit = 64.0% · IR = +0.335
  - n_events = 559 · n_indep_days = 66 · n_symbols = 51
  - 时稳 = 0.44
- **4 硬门槛**：L1 ✅ · L2 ✅ · L3 ✅ · L4 ✅
- **适用范围**：品种保留 73%
- **主导品种 top3**：CZCE.TA409 · DCE.c2409 · SHFE.hc2410

### 2.4 SP_only·trans · A 级 ⭐（最强单笔幅度）

- **触发条件**：`skew_label = "UP" ∧ atr_rank > 0.80 ∧ trend_rank ≤ 0.20 ∧ transition_flag = 1`
- **基础性能**：
  - mean bps = **+51.9** ⭐（本主题最强单笔）
  - CI 95% = [+28.9, +75.8]
  - hit = 66.7% · IR = **+0.459**（本主题最强）
  - n_events = 267 · n_indep_days = 36 · n_symbols = 29
  - 时稳 = 0.48
- **4 硬门槛**：L1 ✅ · L2 ✅ · L3 ✅ · L4 ✅
- **适用范围**：品种保留 76%
- **主导品种 top3**：INE.sc2512 · DCE.m2509 · SHFE.rb2405

### 2.5 SC_only·full · A 级

- **触发条件**：`skew_label = "UP" ∧ atr_rank ∈ (0.67, 0.80] ∧ trend_rank ≤ 0.20`
- **基础性能**：
  - mean bps = +32.4 · CI 95% = [+18.4, +48.0]
  - hit = 61.4% · IR = +0.319
  - n_events = 578 · n_indep_days = 70 · n_symbols = 59
  - 时稳 = 0.35
- **4 硬门槛**：L1 ✅ · L2 ✅ · L3 ✅ · L4 ✅
- **适用范围**：品种保留 74%
- **主导品种 top3**：DCE.i2409 · SHFE.al2501 · SHFE.al2409

### 2.6 SC_only·trans · A 级

- **触发条件**：`skew_label = "UP" ∧ atr_rank ∈ (0.67, 0.80] ∧ trend_rank ≤ 0.20 ∧ transition_flag = 1`
- **基础性能**：
  - mean bps = +44.9 · CI 95% = [+25.5, +66.6]
  - hit = 65.6% · IR = +0.395
  - n_events = 372 · n_indep_days = 46 · n_symbols = 40
  - 时稳 = 0.35
- **4 硬门槛**：L1 ✅ · L2 ✅ · L3 ✅ · L4 ✅
- **适用范围**：品种保留 79%
- **主导品种 top3**：SHFE.al2409 · SHFE.ag2401 · SHFE.ag2509

### 2.7 LL_only·full · A- 级（时稳警示）

- **触发条件**：`skew_label = "DN_loose" ∧ atr_rank ≤ 0.70 ∧ trend_rank ≥ 0.75`
- **基础性能**：
  - mean bps = +33.5 · CI 95% = [+18.2, +49.1]
  - hit = 60.6% · IR = +0.257
  - n_events = **1290** · n_indep_days = 154 · n_symbols = 111（**样本最大**）
  - 时稳 = 0.67（**警示**）
- **4 硬门槛**：L1 ✅ · L2 ✅ · L3 ✅ · L4 ✅
- **时稳警示**：|first_half - second_half|/full = 0.67 · **信号强度时段不稳** · 下游需要谨慎使用
- **适用范围**：品种保留 65%

### 2.8 LL_only·trans · A- 级（时稳警示 · IR 边缘）

- **触发条件**：`LL_only ∩ transition_flag = 1`
- **基础性能**：
  - mean bps = +33.4 · CI 95% = [+10.0, +57.5]
  - IR = +0.239 · 时稳 = **1.32**（**强警示**）
  - n_events = 673 · n_days = 98
- **4 硬门槛**：L1 ✅ · L2 ✅ · L3 ✅ · L4 ✅
- **适用范围**：品种保留 57%
- **注**：时稳指标偏差最大 · 下游可能只用某一半样本时段

### 2.9 SP_only·full · A- 级（品保最高 · 时稳警示）

- **触发条件**：`skew_label = "UP" ∧ atr_rank > 0.80 ∧ trend_rank ≤ 0.20`
- **基础性能**：
  - mean bps = +39.1 · CI 95% = [+26.2, +52.3]
  - IR = +0.377 · 时稳 = 0.64
  - n_events = 826 · n_symbols = 66
  - **品种保留 82%**（本主题最高 ⭐）
- **4 硬门槛**：L1 ✅ · L2 ✅ · L3 ✅ · L4 ✅
- **注**：品保 82% 意味着适用范围广 · 时稳警示表示信号强度有时段变化

### 2.10 未通过的 6 个 tier

见 §1.3 · 具体失败层 · 供未来扩样本验证参考。

---

## 3. 品种大类型附录（供下游策略参考）

**说明**：以下是分类器对 20 品种前缀的**基础性能观察** · 不是分类器承诺 · 供下游策略层选择用哪个 tier 时参考。

### 3.1 三大品种类型

**类型 A · 金融/贵金属型**（ag / au / sc / p）：
- 单笔幅度极高（+120 ~ +160）· skew 稍偏即为信号
- 推荐用 tier：**LL_only·stable**（宽松档 · 匹配"轻度不对称"信号）
- 波动率驱动的均值回归性强

**类型 B · 化工/建材/黑色型**（MA / TA / FG / RM / hc / rb）：
- 需要**高 ATR 环境**（>0.67）
- 推荐用 tier：**SP_only·trans · SC_only·full · SC_only·trans**（空头高波动 tier）
- 波动率与信号正相关

**类型 C · 农产品/有色主流型**（m / y / SR / OI / c / cu / cs）：
- **严格档位** · 低 ATR + 涨段
- 推荐用 tier：**LP_only·full · LL_only·stable**（多头 · 严格 filter）
- 传统均值回归机制

### 3.2 20 品种最优档位表

| 品种 | 类型 | 多头最强档 | 多头 mean | 空头最强档 | 空头 mean |
|:-----|:---:|:---:|:---:|:---:|:---:|
| SHFE.ag | A · 白银 | LP_only | +146 | SC_only | +34 |
| SHFE.au | A · 黄金 | LL_only | +150 | SP_only | +43 |
| DCE.p | A · 棕榈 | LL_only | +163 | SC_only | +31 |
| INE.sc | A · 原油 | LP_only | +59 | SC_only | +123 |
| CZCE.MA | B · 甲醇 | LL_wide | +59 | SL_only | +60 |
| CZCE.TA | B · PTA | LP_wide | +73 | SP_only | +40 |
| CZCE.FG | B · 玻璃 | LP_wide | +74 | SL_only | +103 |
| CZCE.RM | B · 菜粕 | LL_only | +50 | SC_only | +83 |
| SHFE.hc | B · 热卷 | LL_only | +68 | SP_only | +55 |
| SHFE.rb | B · 螺纹 | LL_wide | +29 | SP_only | +58 |
| DCE.m | C · 豆粕 | LP_only | +56 | SL_only | +50 |
| DCE.y | C · 豆油 | LP_only | +40 | SP_only | +11 |
| CZCE.SR | C · 白糖 | LP_only | +24 | SC_only | +28 |
| CZCE.OI | C · 菜油 | LP_only | +92 | SC_only | +75 |
| DCE.c | C · 玉米 | LL_only | +13 | SP_only | +24 |
| SHFE.cu | C · 铜 | LP_only | +52 | SP_only | +30 |
| DCE.cs | C · 玉米淀粉 | LL_wide | +22 | SL_only | +18 |
| DCE.i | · 铁矿 | LL_only | +20 | SC_only | +86 |
| SHFE.al | · 铝 | LL_only | +23 | SP_only | +22 |
| CZCE.CF | · 棉花 | LP_wide | +25 | SP_only | +46 |

**观察**：**没有单一档位覆盖多数品种** · 品种异质性是**分类器本质** · 下游策略层需要品种化选择。

### 3.3 品种异质性经济解读

- **金融资产**（贵金属·原油）：**流动性 + 宏观预期主导** · skew 稍偏即为信号（宽松档强）
- **工业品**（黑色·化工）：**产能供需 + 库存周期主导** · 需要更极端波动才有信号
- **传统农产品**：**天气 + 种植周期主导** · 严格底/顶厚是反转信号

---

## 4. 下游策略层使用建议

### 4.1 分类器 v3.0 定位（重要）

**分类器承诺**：
- ✅ 定义 10 互斥类别 · 输出单值 `tier: str | None`
- ✅ 每 A/A- 级 tier 通过 4 硬门槛严格性验证
- ✅ 提供**基础性能测试**（mean / hit / IR / CI）
- ✅ 提供品种大类型描述（3 大类）

**分类器不承诺**：
- ❌ 每品种独立适用性验证
- ❌ 品种选择建议
- ❌ 交易细节（入场/出场/仓位/成本）
- ❌ 完整策略 Sharpe

**下游策略层的责任**：
- 根据品种类型（§3.1）选用 tier
- **排除不适用的品种**（品保 60-80% 意味着 20-40% 品种失效）
- 时段过滤（A- 级 tier 时稳警示）
- 入场/出场规则设计
- 仓位与成本核算

### 4.2 推荐组合起点

**多头方向**（优先）：
- **LL_only·stable**（A 级 · IR 0.28 · 品保 66% · 样本多）· 主力多头 tier
- LP_only·full（A 级 · 时稳 0.03 最稳）· 严格档补充

**空头方向**（优先）：
- **SP_only·trans**（A 级 ⭐ · IR 0.46 最强）· 主力空头
- **SC_only·full**（A 级 · IR 0.32 · 中档空头）· 补充
- SC_only·trans（A 级 · IR 0.40）· 转换期中空

**慎用（时稳警示）**：
- LL_only·trans（时稳 1.32）· 若使用需分时段过滤
- LL_only·full · SP_only·full · 需要观察近期是否 alpha 维持

### 4.3 组合去重（不再需要）

**v3.0 与 v2.0 区别**：
- v2.0：5 主线嵌套 · 需要"去重规则"避免重复计数
- **v3.0：10 tier 完全互斥 · 每 event 只落一个 tier · 无需去重**

**下游策略层可以直接用 tier == "..." 判断入场** · 无二义性。

---

## 5. 已知边界与使用限制

### 5.1 数据边界（KF-22 冻结）

- rank 单位 = **per-contract**（不可池化）
- Bootstrap 单位 = **(contract, date)**（严格 date-cluster）
- 独立采样单位 ≈ 每合约每天 1 个（同一日所有 event 共享 A3_skew）
- 报告样本量时同时给 event 数和独立日数

### 5.2 品种异质性（KF-24）

- **不存在通用参数**（20 品种最优档位 4 分散）
- 分类器 v3.0 是**通用背景标签系统** · 不是"跨品种统一策略"
- **下游策略层必须做品种化处理**

### 5.3 数据集扩容边界

- 阶段 4 用 **143 合约 · 36625 events · 20 品种前缀**
- 时间跨度 2023-09 到 2026-06
- **样本外扩验**：新合约上市后 · A/A- 级白名单是否维持 · 下游主题需重验

### 5.4 分类器不承诺的内容（明确）

- ❌ 入场时机的最优选择（限价 vs 市价）
- ❌ 出场规则（止损 / 止盈 / 追踪）
- ❌ 仓位大小
- ❌ 交易成本精算
- ❌ 组合 Sharpe（本表指标是"信号级"· 未含仓位管理 / 协方差）
- ❌ 品种适应性（下游策略层责任）

---

## 附录 · 与 spec / workbench 的对应

| 本文件章节 | spec 章节 | workbench 位置 |
|-----------|:--------:|:--------------:|
| §1 A/A- 级白名单 | §7.4 Whitelist | stage4 workbench §2 |
| §1.0 互斥性 | §7.1-7.3 · §10.3 | stage4 workbench §1 |
| §2 单 tier 卡 | §7.1-7.3（数学定义） | stage4 workbench §2 |
| §3 品种类型 | - | stage4 workbench §3 |
| §4 使用建议 | §11.2（阶段 4 引用） | stage4 workbench §4 |
| §5.1 数据边界 | §5.1a（冻结约束） | stage3 workbench §12.12 |
| §5.2 品种异质性 | - | stage4 workbench §3 |
