# Stage 4 显著性检验补充报告

> 类型：Stage 4 Supplement
> 状态：完成
> 创建时间：2026-07-05

## 1. 背景

Stage 4 主报告 §5-§6 得出结论"rolling POC_60 相对 fixed POC 提升 +0.184 ATR/笔，
主题存活"。但该结论基于点估计，未做显著性检验。用户提出：**统计学上 rolling
的优势显著吗？**

## 2. 方法

对 Stage 4 输出的 5541 笔交易做四类检验：

1. **单锚点 vs 0**：one-sample t-test + bootstrap 95% CI + Cohen's d
2. **配对差值检验**：同一事件下 rolling_60 vs fixed_POC / PrevClose，paired t + Wilcoxon
3. **Cluster Bootstrap**：按合约聚类，检验事件非独立性影响
4. **效应量**：Cohen's d 判断实际差异强度

排除 metals 板块（Stage 4 已判定禁用）。

**脚本**：[rolling_reacceptance_stage4_significance.py](../../scripts/analysis/rolling_reacceptance_stage4_significance.py)
**原始输出**：[stage4_significance_test.md](../../project_data/analysis/rolling_reacceptance_stage4/stage4_significance_test.md)

## 3. 关键结论

### 3.1 盈利本身显著（保留）

energy_chem 4.0+ 档在任意锚点下都显著盈利：

| 锚点 | mean | 95% CI | p |
|------|------|--------|---|
| rolling_POC_60 | +1.184 | [+0.348, +2.002] | 0.0038 ✓ |
| fixed_POC | +0.661 | [+0.151, +1.183] | 0.0072 ✓ |
| PrevClose | +0.941 | [+0.263, +1.648] | 0.0054 ✓ |

**"reacceptance + 远距离档"的策略在 energy_chem 上真实盈利**。

### 3.2 Rolling 相对 Fixed 无显著优势（证伪）

配对差值检验（同一事件下的直接比较）：

| 板块 | mean_diff | 95% CI | paired_p | Cohen's d |
|------|----------|--------|----------|----------|
| energy_chem 4.0+ | +0.634 | [-0.603, +1.922] | **0.168 ❌** | +0.142 |
| black 2.5-4.0 | +0.098 | [-0.681, +0.860] | 0.404 ❌ | +0.032 |
| **ALL_ex_metals 4.0+** | **-0.137** | [-0.831, +0.574] | **0.646 ❌** | -0.032 |

**跨板块聚合层，配对差值反转为负**。Stage 4 表面看到的 +0.184 差值是
**不同事件组成的假象**（未配对时 fixed_POC 有 640 笔而 rolling_60 只有 219 笔）。

### 3.3 Rolling 相对 PrevClose 也无显著优势

| 板块 | mean_diff | paired_p |
|------|----------|----------|
| ALL_ex_metals 4.0+ | **-0.399** | **0.902 ❌** |

**"PrevClose 作为兜底基线"在配对检验中甚至优于 rolling_60**。

### 3.4 Cluster Bootstrap 进一步削弱信心

按合约聚类的 95% CI 全部跨 0（rolling_60 vs fixed_POC）：

| 板块 × bucket | 观察差值 | cluster 95% CI |
|--------------|---------|---------------|
| energy_chem 4.0+ | +0.634 | [-0.580, +1.219] |
| ALL_ex_metals 4.0+ | -0.137 | [-1.005, +0.576] |

**同一合约内事件高度相关**，让 t-test 的独立性假设失效。cluster CI 显示
"真实 rolling 优势"可能是从 -1.0 到 +1.2 的任何数字。

## 4. 判决反转

| 判决维度 | Stage 4 表面结论 | 显著性检验后 |
|---------|----------------|-------------|
| rolling POC > fixed POC | ✓ +0.184 | ❌ 配对 -0.137, p=0.646 |
| rolling POC > PrevClose | ✓ +0.064 | ❌ 配对 -0.399, p=0.902 |
| 策略盈利（energy_chem 4.0+）| ✓ +1.184 | ✓ CI 排除 0 |
| 生效板块 | energy_chem/black | energy_chem 唯一显著 |

**主题假设 "rolling POC 相对 fixed POC 有独立价值" 在统计上被证伪**。

## 5. 主题命运重新决策

**Stage 1.5 + Stage 4 显著性检验综合判决**：

- ❌ POC 特殊性（fixed 定义）：证伪（Stage 1.5）
- ❌ POC 特殊性（rolling 定义）：证伪（Stage 4 显著性检验）
- ✅ reacceptance edge：真实存在，独立于锚点选择
- ✅ 距离档 × 结构地图：真实存在，独立于 POC 定义

**主题真正的资产是**：**"reacceptance + 远距离档"的均值回归策略**，
**不是"rolling POC"**。

### 5.1 主题命运的三种可能（更新）

1. **接受主题失败 + Pivot 为均值回归策略**（推荐）
   - 抛弃 rolling POC 假设
   - 保留 reacceptance + 远距离档 + energy_chem 板块
   - 目标锚用 **PrevClose**（最简、显著盈利、无 rolling POC 优势）
   - 主题需要**重写 README + 改名**（"value-area-rolling-reacceptance"名字已不准确）

2. **补跑更大样本再判**
   - 目前 energy_chem 4.0+ 配对样本仅 n=47，power 不足
   - 扩至 30+ energy_chem 品种或纳入更长历史
   - 但**方向已明**：配对 CI 跨 0，扩大样本可能只是让 CI 更窄，不改方向

3. **主题冻结 + Feature-only 出口**
   - reacceptance edge 作为 feature 交给下游策略
   - 主题不再作为独立研究

## 6. 保留观察

1. **energy_chem 显著盈利的机制**：为什么单锚点显著、配对差不显著？
   - 可能 = 各锚点都在捕获同一"均值回归"信号，锚点选择是二阶变量
2. **rolling_POC_240 明显最差**：+0.481 vs -0.012 ATR/笔
   - 说明"追踪时效性"确实有价值，但 60 vs 120 vs fixed 之间的差异不显著
3. **样本量瓶颈**：所有配对 n < 300，检验 power 有限

## 7. 下一步建议

- **立即**：更新 Stage 4 主报告，标注 §6 结论"表面看到的 rolling 优势不显著"
- **立即**：更新 experiment-plan 的阶段 4 判决 → **主题失败或需 pivot**
- **决策依赖**：用户在"pivot 均值回归 / 扩样再判 / 冻结" 之间选一个
