# Stage 4b · Reacceptance 触发器特殊性检验

> 类型：Stage Report
> 状态：完成
> 创建时间：2026-07-05
> 关联计划：[experiment-plan.md](value-area-rolling-reacceptance-experiment-plan.md)

## 1. 背景

Stage 1.5 证伪 POC 特殊性，Stage 4 显著性检验证伪 rolling POC 独立价值。
但用户提出一个关键盲点：**reacceptance 触发器本身是否特殊？还是只是
"4+ ATR 距离档 + 任意 bar" 的伪装？**

若 reacceptance 与 no_trigger baseline 无显著差异，则主题剩余的所有资产都
被证伪。

## 2. 方法

**触发器候选**（6 种，都在 4+ ATR 距离档下评估）：

1. **reacceptance**：现有定义（bar close 从 VA 外穿回内）
2. **no_trigger**（baseline）：每 20 bar 采样一次
3. **long_body_reject**：长实体 + 反向长影线
4. **volume_spike**：成交量突破前 20 bar 90 分位
5. **random_time**：按 reacceptance 相同数量随机采样 far bars
6. **breakout_reversal**：close 突破前 5 bar 极值后反向

**统一目标锚**：PrevClose（Stage 4 显著性检验显示 PrevClose 与 rolling POC/
fixed POC 无显著差异，用最简）

**结构**：S1 baseline（stop=1.5 ATR, timeout=80 bar, cost=0.05）

**统计方法**：
- 单触发器 vs 0：bootstrap + one-sample t-test + cluster bootstrap
- 触发器 vs no_trigger baseline：cluster bootstrap 差值 CI + 单侧 p

**脚本**：[rolling_reacceptance_stage4b_trigger_significance.py](../../scripts/analysis/rolling_reacceptance_stage4b_trigger_significance.py)
**原始输出**：[stage4b_trigger_significance.md](../../project_data/analysis/rolling_reacceptance_stage4b/stage4b_trigger_significance.md)

## 3. 结果

### 3.1 ALL_ex_metals 聚合层：所有触发器无优势

| 触发器 | n | mean | vs no_trigger diff | cluster 95% CI | diff p |
|--------|---|------|-------------------|----------------|--------|
| **reacceptance** | 643 | +0.026 | **+0.019** | [-0.208, +0.267] | **0.438 ❌** |
| long_body_reject | 10330 | -0.016 | -0.024 | [-0.130, +0.084] | 0.659 ❌ |
| volume_spike | 16193 | -0.020 | -0.028 | [-0.148, +0.122] | 0.671 ❌ |
| random_time | 660 | -0.045 | -0.052 | [-0.257, +0.150] | 0.683 ❌ |
| breakout_reversal | 12795 | -0.030 | -0.037 | [-0.141, +0.066] | 0.755 ❌ |
| **no_trigger baseline** | 5355 | **+0.007** | — | — | — |

**Reacceptance 相对 no_trigger 差值 +0.019 ATR/笔，p=0.438**。完全不显著。

### 3.2 每板块单锚点 vs 0：全部不显著

包括之前看好的 energy_chem：

| 板块 | 触发器 | mean | 95% CI | cluster p |
|------|-------|------|--------|-----------|
| energy_chem | reacceptance | +0.253 | [-0.091, +0.624] | 0.241 ❌ |
| energy_chem | no_trigger | -0.049 | [-0.204, +0.115] | 0.808 ❌ |
| black | reacceptance | +0.068 | [-0.233, +0.382] | 0.371 ❌ |
| agri_czce | reacceptance | -0.179 | [-0.470, +0.135] | 0.850 ❌ |

**没有任何板块 × 触发器组合在 cluster bootstrap 下显著**。

### 3.3 与 Stage 4 表面结论的对比

Stage 4 表面 energy_chem 4+ ATR + reacceptance + PrevClose 是 +0.941 ATR/笔
（p=0.005 显著）；Stage 4b 相同配置下只有 +0.253（不显著）。差异原因：

- Stage 4 距离阈值：≥ 2.5 ATR（混入 2.5-4 ATR 段）
- Stage 4b 距离阈值：≥ 4.0 ATR（严格 4+ 段）
- **Stage 4 表面 edge 主要来自 2.5-4 ATR 混合贡献，纯 4+ ATR 无 edge**

## 4. 判决

### 4.1 主题假设链完全崩塌

| 假设 | 状态 | 证伪来源 |
|------|------|---------|
| POC 特殊性（fixed）| ❌ | Stage 1.5 A5/A5b |
| POC 特殊性（rolling）| ❌ | Stage 4 显著性检验 |
| **reacceptance 触发器特殊性** | ❌ | **Stage 4b** |
| 4+ ATR 距离档本身有 edge | ❌ | Stage 4b（no_trigger 期望 ≈ 0）|
| 距离-到达率函数存在 | ✅ | Stage 1.5 A（无争议）|
| ATR 归一化跨品种普适 | ✅ | Stage 1.5 A ATR 版本 |

### 4.2 主题的真实资产（重估）

**几乎没有独立可交易资产**：

- ~~rolling POC~~：无显著独立价值
- ~~reacceptance edge~~：无显著独立价值
- ~~4+ ATR 距离档 edge~~：baseline 期望 ≈ 0
- ~~POC 目标可兑现~~：任何均值锚都可，但配合任何触发器都不显著

**保留的价值**：

1. **方法论资产**：
   - ATR 归一化距离评估
   - 期望净值判据 vs reach_rate 判据
   - 多锚点/多触发器对照
   - Cluster bootstrap 检验事件非独立性
   - 配对 vs 未配对区分（Stage 4 教训）
   
2. **反例经验**：告诉后续研究"看起来显著的 edge 需要通过多层对照才算真"

3. **技术基础设施**：volume profile、reacceptance 检测、事件研究框架代码

### 4.3 主题命运

**主题完全失败**。建议：

1. **Freeze 主题**：写 Freeze Note 归档到 [`docs/research/themes-frozen/value-area/value-area-rolling-reacceptance/`](../research/themes-frozen/value-area/value-area-rolling-reacceptance/)
2. **不作为独立策略推进**：与前主题 value-area-reacceptance 相同命运
3. **方法论提炼到 workspace-level**：把 Stage 1.5-4b 得到的四大方法论约束加入
   [`docs/research/quant-research-methodology.md`](../../docs/research/quant-research-methodology.md) 或等价位置
4. **技术设施保留可复用**：volume profile / reacceptance detection / cluster
   bootstrap 脚本可作为后续主题的基础工具

### 4.4 教训清单（写入方法论库）

1. **未配对对比会产生假象**：Stage 4 表面 +0.184 → 配对 -0.137（反向）
2. **距离档过滤本身可能不是 edge**：no_trigger baseline 期望 ≈ 0
3. **触发器需要 no_trigger baseline 对照**：不能仅比较不同触发器
4. **Cluster bootstrap 揭示事件非独立性**：同一合约内相关性大幅缩小有效样本量
5. **样本量 n<300 时任何"显著性"都值得怀疑**：需要 cluster CI 双确认

## 5. 下一步

**推荐**：
1. 完善 Stage 4b 判决 → 更新 Stage 4 主报告、Stage 4 显著性报告、experiment-plan
2. 撰写主题 Freeze Note 到主题目录
3. 更新方法论库

**不推荐**：
- 尝试补救主题（例如换目标锚 / 换距离档 / 换 stop）—— 已经足够彻底
- 直接 pivot 为其他主题 —— 需要独立立题
