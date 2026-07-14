# va-asymmetry-revisit · 三轮验证：因果性铁证 + 扩样证伪

> 类型：Workbench 实验流水
> 状态：**L_seg2 candidate 判死**（2026-07-14）· 因果性无问题，但原候选是选样偏差假阳性

## 一句话结论

用户对 c1-c5 报告的 L_seg2 alpha 提出未来函数质疑。**三轮验证给出决定性答案**：(1) causal tier pipeline **无未来函数**（225 个 event × 3 特征验证 max_abs_diff = 0）；(2) 扩样从 40 → 145 合约（3.6×）后 L_seg2 **Sharpe 从 1.44 塌到 0.08**、年化 3.4%、DD -64.6%；(3) 从 145 合约随机抽 40 组的 Sharpe 分布 mean 0.018 ± 0.572、95% 分位 1.06，**原 40 合约 Sharpe 1.44 落在 98.5% 分位** —— **c1-c5 的"制度依赖 alpha"是选样偏差假阳性**，真信号为零。

## ① 因果性铁证（[e1_v2_causality_ironproof.py](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/scripts/e1_v2_causality_ironproof.py)）

### 实验设计

对 15 品种各抽 15 个随机 event_idx（要求距首/末各 200+ bars），用两种数据算三特征：
- **Full data**：完整 5m 序列（含 event 之后的未来 bars）
- **Truncated data**：`bars_full.iloc[:event_idx + 1]`，event 之后所有 5m bars 全部删除

若两者结果完全相等 → 未来 bars 未参与特征计算 → **严格 causal**。

### 结果

225 个 event × 3 特征 = 675 个特征值比对：

| 特征 | max_abs_diff | 一致率 |
|---|---:|---:|
| A3_skew (W3 rolling 12h profile skew) | **0.0000e+00** | 225/225 = 100.0% |
| atr_intra (前 96 根 5m abs-ret 均值, shift(1)) | **0.0000e+00** | 225/225 = 100.0% |
| trend_intra (前 96 根 5m ret 累积, shift(1)) | **0.0000e+00** | 225/225 = 100.0% |

**证据链完整**：
- 值级一致（本轮验证）→ Rolling rank 一致（单调函数传递）→ tier 分类一致（纯函数）
- **✅ Causal tier pipeline 无未来函数**

## ② 扩样重跑（[e2_expanded_causal_tier.py](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/scripts/e2_expanded_causal_tier.py)）

### 样本变化

| 维度 | c1 (原) | e2 (扩样) | 倍数 |
|---|---:|---:|---:|
| 合约数 | 40 | 145 | 3.6× |
| 品种数 | 15 | 20 (新增 CZCE.FG/MA/OI, DCE.cs, SHFE.au) | 1.3× |
| 时间跨度 | 21 个月 (2024-09 → 2026-05) | 33 个月 (2023-09 → 2026-07) | 1.6× |
| 总 events | 16,406 | ~45,000 | 2.7× |
| L_seg2 events | 302 | 1,100 | 3.6× |

### 全 tier × horizon 全景（扩样版）

| tier | dir | horizon | n | **net mean** | CI | p |
|---|:-:|---|---:|---:|---|---:|
| **L_seg2_low_flat** | +1 | ret_10h | 1075 | **+0.008%** | [-0.10, +0.12] | **0.878** |
| L_seg3_lowmid_up | +1 | ret_10h | 1633 | -0.053% | [-0.14, +0.04] | 0.256 |
| **L_seg12_high_up** | +1 | ret_10h | 983 | **-0.19%** | [-0.37, -0.03] | **0.015** (负) |
| **S_seg12_high_dn** | -1 | ret_10h | 950 | **-0.16%** | [-0.28, -0.03] | **0.011** (负) |
| **S_seg34_high_dn** | -1 | ret_10h | 892 | **-0.15%** | [-0.28, -0.02] | **0.018** (负) |
| S_seg2_mid_dn | -1 | ret_10h | 365 | -0.02% | [-0.18, +0.14] | 0.800 |

**所有 net CI 排 0 的都是负边界**（4/6 tier net 显著为负），仅 L_seg2 与 L_seg3 净收益近似 0 但 CI 也跨 0 → **6 tier 全无正 alpha**。

### L_seg2 · 3-fold walk-forward (扩样版)

| fold | period | train p (10h) | test p (10h) | test mean |
|---:|---|---:|---:|---:|
| 0 | train 0-50%, test 50-70% (2024-11→2025-05) | 0.632 | 0.123 | **-0.16%** (负) |
| 1 | train 0-70%, test 70-85% (2025-05→2025-09) | 0.277 | 0.135 | +0.19% |
| 2 | train 0-85%, test 85-100% (2025-09→2026-07) | 0.657 | 0.066 | +0.20% |

**3 折 test 全部 p > 0.05**，fold 0 甚至反向（原 c4 也是 fold 0 反向）。

### LGO by sector · 10h net

- **0/20 sector 剔除后剩余组 CI 排 0** （原 c3 是 3/5 通过；扩样后归零）

### Per-symbol retention

- **10h net > 0 的 symbols：55/103 = 53.4%** （原 24/39 = 61.5%；扩样后回归到近似 50% = 无信号基准）

### 实用性能（扩样后）

| 版本 | n_trades | 年化 | Sharpe | DD | Hit |
|---|---:|---:|---:|---:|---:|
| c5 报告 (40 合约) | 299 | 36.7% | **1.48** | -21.6% | 53.2% |
| **e2 扩样 (145 合约)** | 1100 | **3.4%** | **0.08** | **-64.6%** | **48.3%** |

### 季度 P&L（扩样版）

| Quarter | n | mean | sum |
|---|---:|---:|---:|
| 2023Q3 | 26 | -0.010 | **-0.27** |
| 2023Q4 | 92 | +0.001 | +0.09 |
| 2024Q1 | 127 | +0.001 | +0.09 |
| 2024Q2 | 84 | -0.003 | **-0.22** |
| 2024Q3 | 82 | -0.001 | -0.11 |
| 2024Q4 | 158 | +0.002 | +0.28 |
| 2025Q1 | 148 | -0.002 | **-0.31** |
| 2025Q2 | 85 | +0.001 | +0.08 |
| 2025Q3 | 120 | +0.001 | +0.18 |
| 2025Q4 | 93 | +0.001 | +0.06 |
| 2026Q1 | 42 | +0.006 | +0.25 |
| 2026Q2 | 18 | -0.002 | -0.03 |

13 个季度 6 正 7 负，最大月盈 +0.28、最大月亏 -0.31 → **零均值 + 结构性季度波动**。

## ③ 选样偏差诊断（[e3_selection_bias_check.py](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/scripts/e3_selection_bias_check.py)）

**从 145 合约随机抽 40 个 × 200 次**，计算 L_seg2 的 Sharpe 分布：

| 统计量 | Sharpe |
|---|---:|
| mean | 0.018 |
| std | 0.572 |
| p05 | -0.911 |
| p50 | 0.009 |
| p95 | 1.062 |
| **原 40 合约** | **1.443** |
| **原 40 合约在此分布的排位** | **98.5% 分位** |

**判决**：c1-c5 报告的 L_seg2 alpha 是**极右尾选样**产物——原 40 合约恰好落在随机抽样能拿到的 top 1.5%。

## ④ 综合判决与去向

**判决**：

1. **因果性无问题**：225 个 event × 3 特征 max_abs_diff = 0，pipeline 严格 causal，无未来函数
2. **L_seg2 alpha 判死（撤销 KF-5）**：扩样后 Sharpe 从 1.44 → 0.08，落在随机 40 合约分布中位；F 系列新增 **F-17 · Causal L_seg2 单信号策略**
3. **原 archive va-asymmetry-composite 6-tier 复合策略在 causal 修复下全线证伪**（4/6 tier net 显著为负、2/6 tier net 近零）→ 印证 KF-6，同时**关闭 hypothesis-inventory H-3 / H-4 / H-5 / H-6 / H-17** —— 原假设的 tier 分类框架在 causal 版下不产生 edge

**给用户的诚实答复**：

- ✅ 你对未来函数的质疑非常关键，逼出了严格铁证——**pipeline 无未来函数**
- ✅ 你给足时间预算也非常关键——扩样从 40 → 145 合约揭示了 c1-c5 的假阳性本质
- ❌ 但**这条主题的核心假设（不管是 signed skew 一维 IC 还是 6-tier 三维联合 tier）在完整数据 + 严格 causal + 无选样偏差下均无 alpha**
- 📋 **本主题应进入冻结候选**——va-asymmetry 系列的策略主线全部证伪；下一步只有两条路：
  - (a) 冻结进 `themes-frozen/va-asymmetry/`，转向完全独立的新主题
  - (b) 探索 hypothesis-inventory H-11 τ_signed / H-12 transition_flag 的 intraday 版（这两条与 signed skew 输入正交，可能仍有 edge），若也证伪则整体冻结

**为什么不写工程化策略**：因为方法论 §7「放弃条件」明确：**广度扫描后多数品种无信号 + 随机对照未通过 → 放弃**。扩样后 145 合约 Sharpe 0.08、随机 40 合约分布 mean 0.018 → 这条主题的策略已经死了，工程化没有意义。

## 文件清单

- 脚本
  - [e1_v2_causality_ironproof.py](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/scripts/e1_v2_causality_ironproof.py) · 因果性铁证（225 events × 3 特征）
  - [e2_expanded_causal_tier.py](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/scripts/e2_expanded_causal_tier.py) · 扩样版完整链路
  - [e3_selection_bias_check.py](file:///Users/gaolei/Documents/src/quant/docs/workbench/va-asymmetry-revisit/scripts/e3_selection_bias_check.py) · 选样偏差诊断
- 数据：`docs/workbench/va-asymmetry-revisit/outputs/{e1_v2,expand,e3}/`
