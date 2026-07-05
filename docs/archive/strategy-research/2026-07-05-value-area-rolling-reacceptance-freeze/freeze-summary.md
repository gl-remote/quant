# value-area-rolling-reacceptance · Freeze Summary

> 类型：Archive · Strategy Research
> 状态：主题冻结（Frozen）
> 归档日期：2026-07-05
> 主题目录：[docs/research/themes-frozen/value-area/value-area-rolling-reacceptance/](../../../research/themes-frozen/value-area/value-area-rolling-reacceptance/README.md)
> 前置主题：[docs/research/themes-frozen/value-area/value-area-reacceptance/](../../../research/themes-frozen/value-area/value-area-reacceptance/README.md)（已冻结）
> 上游 Roadmap：[Structural Alpha 长期共识框架](../../../roadmap/strategy-research-framework.md)

## 1. 主题一句话结论

**Value area rolling reacceptance 策略假设完全失败**。POC 无独特引力
（fixed 与 rolling 双版本证伪），reacceptance 非特殊触发器，4+ ATR 距离
档本身也没有可交易的 mean-reversion edge。5m 与 15m 双周期一致证伪。

## 2. 核心问题

用 rolling volume profile 追踪 POC 跳变，配合 reacceptance 事件在 VA 边界
上做 mean-reversion 交易。前置主题 `value-area-reacceptance` 已用 fixed-
window POC + 离散刷新失败；本主题假设换成 rolling POC 能捕获盘中共识迁移，
从而恢复 edge。

## 3. 实验定义（Stage 1 → Stage 4b）

| Stage | 目的 | 状态 | 结论 |
|-------|------|------|------|
| **Stage 1** | 方向信息 gatekeeper | ✅ 通过（表面）| VA reacceptance 事件相对随机基准 Δ(struct-same) +0.03~+0.09；黑色 / 能化生效，metals / agri 边缘 |
| **Stage 1.5-A** | POC 距离-到达率函数（ticks）| ✅ 完成 | 存在，但 metals vs black 分化明显（波动率异质性）|
| **Stage 1.5-A(ATR)** | ATR 归一化距离-到达率函数 | ✅ 关键 | **跨板块函数完全重合**，波动率归一化后普适规律成立 |
| **Stage 1.5-A2** | Reacceptance 事件 ATR 距离档分布 | ✅ 完成 | Reacceptance edge 在 4+ ATR 档最强（相对 baseline +0.04~+0.10） |
| **Stage 1.5-A3** | 固定 stop 期望净值 | ✅ 完成 | 唯一稳定正期望：energy_chem 4+ +0.483 ATR/笔 (S1) |
| **Stage 1.5-A4** | 多结构敏感性对比 | ✅ 完成 | 结构选择敏感性 >> 距离档选择，agri_czce 4+ 档 S5 tiered stop 从 +0.145 → +0.290 |
| **Stage 1.5-A5** | 多锚点对比（无条件）| ❌ 证伪 POC 特殊性 | 跨 7 种前日锚点（POC/VAH/VAL/RunnerUpPOC/PrevClose/PrevMid/PriceMedian），距离-到达率函数完全重合，差异 ≤ 2 pp |
| **Stage 1.5-A5b** | 多锚点对比（reacceptance 事件下）| ❌ 证伪 POC/reacceptance 耦合 | POC 相对其他锚点差值全部 -0.05~+0.09 抖动，4+ 档 PrevClose 甚至优于 POC |
| **Stage 4** | Rolling POC vs fixed POC vs PrevClose | ⚠️ 表面通过 | 点估计：rolling_60 相对 fixed +0.184 ATR/笔（未做显著性检验）|
| **Stage 4 显著性** | 配对差值 + cluster bootstrap | ❌ 证伪 rolling 独立价值 | 配对差值 -0.137, p=0.646；cluster CI [-1.005, +0.576] 跨 0 |
| **Stage 4b** | Reacceptance vs 5 种其他触发器 vs no_trigger | ❌ 证伪 reacceptance 特殊性 | ALL_ex_metals: reacceptance vs no_trigger diff **+0.019, p=0.438**；no_trigger baseline 期望 +0.007（几乎 0） |
| **Stage 4b (15m)** | 跨周期稳健性 | ❌ 结论一致 | reacceptance vs no_trigger diff **-0.088, p=0.648**；核心结论完全稳健 |

## 4. 固定参数

- **数据周期**：5m（主）/ 15m（跨周期验证）
- **品种**：20 品种、70 合约，覆盖 5 板块（black / metals / energy_chem / agri_dce / agri_czce）
- **时间跨度**：2023-09-04 → 2026-06-30
- **ATR 归一化**：ATR_WINDOW=20 bars
- **距离档**：0-0.5 / 0.5-1.0 / 1.0-1.5 / 1.5-2.5 / 2.5-4.0 / 4.0+ ATR
- **VA 参数**：Volume Area 70% + 前日 fixed-window POC
- **S1 baseline 结构**：stop=1.5 ATR, timeout=80 bar (5m) / 27 bar (15m), cost=0.05 ATR
- **Bootstrap**：n=5000, cluster by contract

## 5. 关键结果

### 5.1 主题假设链完全崩塌

| 假设 | 状态 | 证伪来源 |
|------|------|---------|
| A. POC/VA 反映共识价格 | 部分成立（volume 分布有意义）| — |
| B. 滚动刷新能更好捕获共识 | ❌ 证伪 | Stage 4 显著性检验 |
| C. 价格回到 VA 内部有方向信息 | ⚠️ 均值回归成立，但非 POC 特有 | Stage 1.5-A5/A5b |
| D. 重新接受深度改善风险空间 | ⚠️ A4 有信号但依赖结构 | Stage 4b 证伪触发器 |
| E. POC 目标可兑现 | ❌ 可兑现但任意锚都可 | Stage 1.5-A5b |
| F. 跨品种普遍成立 | ✅ 均值回归普适，但 edge 不存在 | — |

### 5.2 Reacceptance 特殊性证伪（Stage 4b）

**ALL_ex_metals 聚合层，4+ ATR 距离档下**：

| 触发器 | mean pnl (ATR/笔) | vs no_trigger diff | cluster CI | diff p |
|--------|------------------|-------------------|-----------|--------|
| **no_trigger baseline** | +0.007 | — | — | — |
| **reacceptance** | +0.026 | **+0.019** | [-0.208, +0.267] | **0.438 ❌** |
| long_body_reject | -0.016 | -0.024 | [-0.130, +0.084] | 0.659 ❌ |
| volume_spike | -0.020 | -0.028 | [-0.148, +0.122] | 0.671 ❌ |
| random_time | -0.045 | -0.052 | [-0.257, +0.150] | 0.683 ❌ |
| breakout_reversal | -0.030 | -0.037 | [-0.141, +0.066] | 0.755 ❌ |

**Reacceptance 相对 no_trigger baseline 差值仅 +0.019, p=0.438，完全不显著**。

### 5.3 跨周期稳健性

| 结论 | 5m | 15m | 稳健性 |
|------|----|----|-------|
| Reacceptance vs no_trigger 不显著 | ✅ diff +0.019, p=0.44 | ✅ diff -0.088, p=0.65 | 强 |
| 4+ ATR baseline ≈ 0 | ✅ +0.007 | ✅ -0.023 | 强 |
| 主题假设失败 | ✅ | ✅ | 强 |

## 6. 保留的方法论资产

Stage 1.5-4b 得到的**四大跨阶段方法论约束**，可直接沿用到后续主题：

1. **ATR 归一化距离评估**：距离一律用 `|price - anchor| / ATR20`，跨品种可比、跨周期可比、跨板块可比
2. **期望净值判据优先于 reach_rate**：Stage 1.5-A3/A4 已证 reach_rate 差异会误导（8 pp 差可能仅贡献 0.05 ATR 期望）
3. **结构 × 距离档二维联合**：Stage 1.5-A4 证结构选择敏感性 >> 距离档选择（同一距离档最优 vs 最差结构差 2.49 ATR/笔）
4. **多锚点 + 多触发器 + no_trigger baseline 对照**：Stage 1.5-A5/4b 教训——只做单一变量对比会得出假象；必须至少三层对照才可判"独立价值"
5. **配对 vs 未配对区分**：Stage 4 教训——未配对差异 +0.184 → 配对 -0.137 反转
6. **Cluster bootstrap 检验事件非独立性**：Stage 4 教训——同一合约内事件高度相关，t-test 独立性假设失效，cluster CI 揭示真实不确定性

## 7. 保留的技术设施

均可作为后续研究的基础工具：

- **Volume profile 计算**（fixed / rolling）：[stage1_direction.py](raw-scripts/rolling_reacceptance_stage1_direction.py) 中 `compute_daily_anchors` / `rolling_poc`
- **Reacceptance 事件检测**：所有 stage 脚本
- **6 种触发器检测**：[stage4b_trigger_significance.py](raw-scripts/rolling_reacceptance_stage4b_trigger_significance.py) 中 `detect_triggers`
- **Cluster bootstrap 双检验**：[stage4_significance.py](raw-scripts/rolling_reacceptance_stage4_significance.py)
- **多结构 S1-S6 模拟**：[stage1_5_A4_multi_structure.py](raw-scripts/rolling_reacceptance_stage1_5_A4_multi_structure.py)

## 8. 结论 & 对后续研究的建议

### 8.1 不再作为独立策略推进

主题的假设链在每一层都被独立证伪：
- POC 特殊性（fixed）→ Stage 1.5-A5 证伪
- POC 特殊性（rolling）→ Stage 4 显著性检验证伪
- Reacceptance 触发器特殊性 → Stage 4b 证伪
- 4+ ATR 距离档独立 edge → Stage 4b 证伪（no_trigger ≈ 0）

**没有可交易的 alpha**。与前主题 `value-area-reacceptance` 命运一致。

### 8.2 对下一个主题的方法论要求

任何后续 mean-reversion / structural alpha 主题应满足：

1. **必须有 no_trigger baseline 对照**（Stage 4b 教训：距离档过滤不等于 edge）
2. **必须在配对样本上做显著性检验**（Stage 4 教训：未配对易假象）
3. **必须做 cluster bootstrap**（同一合约内事件高度相关）
4. **必须跨周期验证**（Stage 4b 5m/15m 双周期证明稳健性）
5. **距离/大小/时间统一用 ATR 归一化**

### 8.3 潜在再研究方向（非本主题范畴）

以下由 Stage 4b 数据副产品暗示，需另立主题独立验证：

- **15m 下 black 板块 4+ ATR 反向 edge**（no_trigger -0.163, cluster p=0.994 显著负）—— 提示"追高杀低"？
- **Agri_dce 15m 下的正 baseline (+0.079)** —— 品种特异性？
- **60 bar rolling window 优于 240 bar** —— rolling 概念在非 POC 场景下可能有价值？

## 9. 附件

- 原始 workbench 文档：[raw-workbench/](raw-workbench/)
  - [experiment-plan.md](raw-workbench/experiment-plan.md)
  - [stage1-direction-info.md](raw-workbench/stage1-direction-info.md)
  - [stage1_5-poc-attraction.md](raw-workbench/stage1_5-poc-attraction.md)
  - [stage4-rolling-vs-fixed.md](raw-workbench/stage4-rolling-vs-fixed.md)
  - [stage4-significance.md](raw-workbench/stage4-significance.md)
  - [stage4b-trigger-significance.md](raw-workbench/stage4b-trigger-significance.md)
- 分析脚本：[raw-scripts/](raw-scripts/) （12 份）
- 原始数据（未归档，保留在 `project_data/analysis/rolling_reacceptance_*` 下）
