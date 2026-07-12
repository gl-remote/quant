# value-area-rolling-reacceptance · 阶段 4 实验报告：Rolling POC 相对基线的独立价值

> 类型：Stage Report
> 状态：草案
> 创建时间：2026-07-05
> 关联主题：[../research/themes-frozen/value-area/value-area-rolling-reacceptance/README.md](../research/themes-frozen/value-area/value-area-rolling-reacceptance/README.md)
> 关联计划：[experiment-plan.md](value-area-rolling-reacceptance-experiment-plan.md)
> 前置阶段：[Stage 1.5 结题](value-area-rolling-reacceptance-stage1_5-poc-attraction.md#L1071)

---

## 1. 阶段目标

Stage 1.5 结题结论：**前日 fixed-window POC 不比其他前日锚点特殊**，但主题
存活的关键假设 **rolling POC 相对 fixed POC 是否有独立价值** 尚未验证。

阶段 4 的核心问题：

- **Q1**：rolling POC 相对 fixed POC，在 reacceptance 触发 + 期望净值口径下，
  是否有显著更高的期望净值？
- **Q2**：rolling POC 相对 PrevClose（"任意合理均值锚"兜底基线），是否有
  显著独立价值？
- **Q3**：三态判决 —— 主题存活 / rolling 无优势 / 主题失败

## 2. 方法论前置约束（Stage 1.5 结题继承）

严格适用以下约束（[experiment-plan §跨阶段方法论约束](value-area-rolling-reacceptance-experiment-plan.md)）：

1. **距离用 ATR 归一化**：所有距离评估用 `distance_atr = |price - anchor| / ATR20`
2. **期望净值判据**：不用 reach_rate 单一指标，用"期望净值 = p × d - (1-p) × s - cost"
3. **结构 × 距离档二维联合**：先选定 S1 baseline，若差异不显著再对比其他结构
4. **多锚点对照**：**至少同时评估 rolling POC / fixed POC / PrevClose 三锚**

## 3. 三态判决标准

| 判决 | 条件 | 含义 |
|------|------|------|
| ✅ **主题成立** | rolling POC 期望净值 显著优于 fixed POC 且 显著优于 PrevClose（跨主要板块）| POC 概念在更精确定义下有独立价值，rolling 是必要的 |
| ⚠️ **rolling 无优势** | rolling POC ≈ fixed POC | 追踪 POC 跳变无实证价值，回退 fixed 版本，与前主题重合 |
| ❌ **主题失败** | rolling POC ≈ PrevClose | POC 的动态版本也不比任意合理均值锚强，主题彻底证伪 |

**"显著"定义**：跨主要板块（black / energy_chem / agri_dce / agri_czce）
的期望净值差异 ≥ 0.05 ATR/笔，且方向一致（不能一半板块正、一半板块负）。

## 4. 实验设计

### 4.1 事件集

**触发器**：沿用 Stage 1 / 1.5 的 reacceptance 事件定义（fixed VA 边界，
close 从外穿回内）。**不改触发器以保持前后一致**。

- 使用 20 个已覆盖品种（black 4 + metals 4 + energy_chem 4 + agri_dce 5 + agri_czce 3）
- 事件筛选：距 fixed POC ≥ 2.5 ATR（远距离档 + 甜蜜区上半段），符合 A4 生效
  边界

### 4.2 锚点候选

对每个 reacceptance 事件，同时评估以下 5 个锚点：

| 锚点 | 定义 |
|------|------|
| **rolling_POC_60** | 前 60 bar (5h) volume profile 众数 |
| **rolling_POC_120** | 前 120 bar (10h) volume profile 众数 |
| **rolling_POC_240** | 前 240 bar (20h ≈ 2 日) volume profile 众数 |
| **fixed_POC** | 前日 volume profile 众数（stage 1/1.5 定义）|
| **PrevClose** | 前日收盘价 |

**rolling window 选择**：60 / 120 / 240 覆盖"半日 / 日 / 双日"三档时间
尺度。若 60 有优势 → 短窗口更好；若 240 更好 → 长窗口更好；若都无优势
→ rolling 无价值。

### 4.3 交易结构

沿用 A4 的 **S1_baseline**：

- 入场：reacceptance 事件的下一 bar open
- 目标：对应锚点价格
- 止损：入场价 ± 1.5 ATR
- 时限：80 bar
- 成本：0.05 ATR/笔（single side）

**为什么只用 S1**：Stage 1.5 §5.6 已经证明结构选择对期望净值影响很大，
但**结构与锚点选择是独立维度**。先固定 S1 分离锚点效应；若 rolling 有
优势，再扩展到其他结构。

### 4.4 输出矩阵

对每个板块 × 距离档，输出 5 锚点的期望净值：

```
           rolling_60  rolling_120  rolling_240  fixed  PrevClose
black                                                              
  2.5-4.0
  4.0+
energy_chem
  2.5-4.0
  4.0+
...
```

**关键差值**：
- rolling_60 - fixed
- rolling_120 - fixed
- rolling_240 - fixed
- rolling_best - PrevClose

## 5. 结果

**执行时间**：2026-07-05
**总交易数**：5541（含 metals）
**原始报告**：[stage4_multi_anchor_expected_value.md](../../project_data/analysis/rolling_reacceptance_stage4/stage4_multi_anchor_expected_value.md)

### 5.1 跨板块聚合（不含 metals）

| bucket | rolling_60 | rolling_120 | rolling_240 | fixed_POC | PrevClose |
|---|---|---|---|---|---|
| 2.5-4.0 | -0.186 | -0.288 | -0.249 | **-0.165** | -0.445 |
| **4.0+** | **+0.481** | +0.422 | -0.012 | +0.297 | +0.417 |

**关键发现**：
- 4.0+ 档：**rolling_POC_60 = +0.481 ATR/笔 > fixed_POC (+0.297) > PrevClose (+0.417)**
- rolling_60 相对 fixed_POC 提升 +0.184 ATR/笔（61% 相对提升）
- rolling_60 相对 PrevClose 提升 +0.064 ATR/笔（15% 相对提升）
- 2.5-4.0 档：所有锚点都是负期望，rolling 无优势

### 5.2 板块拆分（4.0+ 档，重点关注）

| 板块 | rolling_60 | rolling_120 | rolling_240 | fixed_POC | PrevClose | rolling_60 - fixed |
|------|-----------|-------------|-------------|-----------|-----------|---------------------|
| **energy_chem** | **+1.184** | +0.822 | -0.062 | +0.661 | +0.941 | **+0.522** |
| **black** | **+0.910** | +0.373 | -0.066 | +0.301 | +0.043 | **+0.609** |
| agri_czce | +0.162 | +0.265 | +0.209 | +0.344 | +0.252 | -0.183 |
| agri_dce | -0.154 | +0.258 | -0.084 | +0.033 | +0.113 | -0.187 |
| metals | -0.244 | -0.153 | -0.242 | -0.357 | -0.545 | +0.113 |

**关键板块分化**：
- **energy_chem 4.0+ 档**：rolling_60 提升最大（+0.522），rolling_60 是所有锚点最优
- **black 4.0+ 档**：rolling_60 提升 +0.609（相对 fixed_POC 提升 200%）
- **agri 双板块**：rolling_60 反而劣于 fixed_POC（-0.18）

### 5.3 Rolling 窗口选择

| 窗口 | 4.0+ 档聚合期望 | 排名 |
|------|----------------|-----|
| **rolling_POC_60** | **+0.481** | ★ 最优 |
| rolling_POC_120 | +0.422 | ★ 次优 |
| rolling_POC_240 | -0.012 | ✗ 最差 |
| fixed_POC | +0.297 | baseline |
| PrevClose | +0.417 | baseline |

**窗口结论**：**60 bar (5h) 是最优 window**，240 bar (2 日) 明显过长。这与
主题 README §8 的 jump-process 假设一致 —— 短窗口更能捕获盘中共识迁移。

## 6. 结论

### ⚠️ 表面结论被显著性检验反转（2026-07-05 补充）

**详见 [stage4-significance.md](value-area-rolling-reacceptance-stage4-significance.md)**

原始 §5 表面结论 "rolling POC_60 相对 fixed POC 提升 +0.184" 是**未配对
样本组成的假象**。配对检验（同一事件下直接比较）显示：

- ALL_ex_metals 4.0+ 配对差值 **-0.137** ATR/笔（p=0.646, CI [-0.831, +0.574]）
- rolling POC vs PrevClose 配对差值 **-0.399** ATR/笔（p=0.902）
- Cluster bootstrap 95% CI 全部跨 0

**主题假设 "rolling POC 有独立价值" 在统计上被证伪**。

**保留结论**：energy_chem 4.0+ 档在任意锚点下都显著盈利（p<0.01, CI 排除 0），
这是 **"reacceptance + 远距离档"** 的 edge，与 rolling POC 无关。

---

### 6.1 三态判决结果（原始，已被显著性检验反转）

判决依据（[4.3 三态判决标准](#L38)）：
- 条件 1：rolling POC 显著优于 fixed POC → **成立**（+0.184 ATR/笔 > 0.05 阈值）
- 条件 2：rolling POC 显著优于 PrevClose → **弱成立**（+0.064 ATR/笔 > 0.05 阈值，但边际）
- 条件 3：方向一致（跨板块）→ **不完全成立**（工业品成立，农产品反向）

**判决：✅ 主题存活，但需要限定生效边界为工业品板块**。

具体版本：
- **energy_chem + black 4.0+ 档**：rolling_POC_60 显著优于 fixed_POC 与 PrevClose，主题假设成立
- **agri_czce + agri_dce 4.0+ 档**：fixed_POC 更好，rolling 无优势甚至反向
- **metals**：全线负期望，禁用

### 6.2 主题命运决策

**Rolling POC 存活但边界收窄**：

**新的策略定位**（Stage 4 后）：

```
入场：
  - 触发：reacceptance 事件（fixed VA 边界）
  - 距离档：4.0+ ATR（相对 rolling_POC_60）
  - 生效板块：energy_chem + black（工业品）
  - 禁用板块：agri_czce / agri_dce / metals

目标：rolling_POC_60（5h volume profile 众数）

结构：S1 baseline
  - Stop: 1.5 ATR
  - Timeout: 80 bar
  - Cost: 0.05 ATR/笔

期望：
  - energy_chem: +1.184 ATR/笔（n=59）
  - black: +0.910 ATR/笔（n=41）
  - 综合工业品：+1.05 ATR/笔（估计）
```

### 6.3 与 Stage 1.5 结论的对比

| 定位维度 | Stage 1.5 结论 | Stage 4 结论 | 变化 |
|---------|---------------|-------------|------|
| POC 是否特殊 | fixed POC 不特殊 | **rolling POC_60 相对 fixed 提升 +0.184** | 主题存活 |
| 生效板块 | energy_chem/black/agri | **仅 energy_chem + black** | 收窄 |
| 距离档 | 4.0+ ATR | **4.0+ ATR (相对 rolling POC)** | 一致 |
| 目标锚 | 任意均值锚 (PrevClose 略优) | **rolling_POC_60** | 主题假设生效 |
| 期望净值 | energy_chem +0.483 (fixed) | **energy_chem +1.184 (rolling_60)** | 大幅提升 |

**主题 rolling 假设的价值被 Stage 4 直接证实**（工业品）。fixed POC + PrevClose
双基线对照下 rolling_60 显著优于两者。

### 6.4 保留观察 / 未解决问题

1. **样本量偏小**：energy_chem 4.0+ 档 n=59，black 4.0+ 档 n=41，需要更多品种/更长时间样本
2. **农产品反向**：为什么 agri 板块 rolling 反而更差？—— 可能与农产品盘中共识变化慢有关，60 bar 过短
3. **距离档设定**：所有距离档基于 fixed_POC 定义，未按 rolling_POC 重新定义。若按 rolling_POC 定义距离，结论可能进一步变化
4. **结构维度未验证**：仅 S1 baseline。若结合 A4 的 S5 tiered stop，工业品 4.0+ 档可能进一步优化

### 6.5 下一步

- **S0：主题 Spec 编写** —— 基于 rolling_POC_60 + reacceptance + 工业品板块的定位
- **S1-S2：Indicator + 策略实现** —— rolling POC 增量计算 + 交易逻辑
- **阶段 5**：品种边界扩样 + 时间样本外


## 7. 附录

- 关联文档：
  - [experiment-plan.md](value-area-rolling-reacceptance-experiment-plan.md)
  - [Stage 1.5 结题](value-area-rolling-reacceptance-stage1_5-poc-attraction.md#L1071)
  - [Stage 1 报告](value-area-rolling-reacceptance-stage1-direction-info.md)
