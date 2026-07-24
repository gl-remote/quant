# archive · 2026-07-08 · poc-value-area-asymmetry（全阶段 · Stage 1~4）

> 批次：阶段归档（非冻结 · workbench + 专属脚本 + 数据登记）
> 主题：theme:poc-value-area-asymmetry
> 归档范围：`experiment/poc-value-area-asymmetry` 分支从首次提交到当前 HEAD 的**所有主题相关文件**（不仅 workbench，含 70 个专属临时脚本）
> 归档日期：2026-07-08
> 结论标签：✅ 全阶段通过 · v4.0 分类器冻结 · 🔁 转下游主线

## 批次内容

| 文件 / 子目录 | 内容 |
|:---|:---|
| [stage1-measurement.md](stage1-measurement.md) | 阶段 1 完整流水（v7 · A3_skew 独立方向信号 · DN 侧测量 · 严格无未来函数）|
| [stage2-guardrails.md](stage2-guardrails.md) | 阶段 2 完整流水（v4 · 跨周期护栏 + ν_implied + 样本外 · 4 主线 Bonferroni 通过）|
| [stage3-robustness.md](stage3-robustness.md) | 阶段 3 完整流水（v11 · 稳健性深度检验 · 5/5 任务全过 · 12 格经济机制 · 洞察 P~U）|
| [stage-summary.md](stage-summary.md) | 阶段 4 总结（KF-25~29 · 6 类合并白名单 · FDR 方法论）|
| [stage4-classifier-v4.md](stage4-classifier-v4.md) | 阶段 4 完整流水（三维 144 tier + FDR + 合并降级 · 15~20 通过 · 分类器 v4.0）|
| `raw-scripts/` | 70 个本主题专属临时分析脚本 · §脚本归档清单分 5 组登记 |

## 一句话结论

**全阶段 1→2→3→4 均通过**：从 A3_skew 是一个独立方向信号（阶段 1 · 19 合约）→ 跨周期 + ν_implied + 样本外硬门槛通过（阶段 2 · 4 主线）→ 背景划分器 7 层严格性证据链完整（阶段 3 · 5/5）→ 三维信号地图 144 tier 扫完收敛到 6 类合并版白名单 · 分类器 v4.0 冻结（阶段 4 · 143 合约 · 36625 events）。**主题主动性研究暂停 · 分类器 v4.0 可作为下游策略稳定组件引用。下游主题可立：poc-va-shaping-composite / poc-va-symbol-refinement / poc-va-tail-asymmetry。**

**关键方法论收获（跨主题可复用）**：
- **KF-25 FDR 优于 Bonferroni**：结构性切片族相邻高度相关时用 BH FDR（α=0.05），比 Bonferroni 合理
- **KF-26 平稳期 alpha 仅存在于转换期**：独立平稳期不产生方向 alpha
- **KF-27 顺 trend 硬规则**：交叉 trend（跌段做多 / 涨段做空）全部负值，无例外
- **KF-28 转换期是空头最密集区**：稳定期空头 alpha 弱
- **KF-29 合并降级优于精细切分**：144 tier → 6 类合并，通过率 20% → 83%

## 与主题目录的关系

主题 theme:poc-value-area-asymmetry 仍**保留在活跃 themes/** · 因为：
- 分类器组件 `workspace/strategies/classifiers/poc_va.py` 作为长期可引用资产
- 下游主题可立
- 主动性研究暂停 · 但主题不冻结（未来可因下游需求或新合约恢复验证）

## 数据文件（不搬运 · 只登记路径与元信息）

**归档范围 Step 0 判定**：数据文件不搬（二进制/大文件）· 只登记路径 + 元信息。

### 阶段 1 · `project_data/logs/poc_va_asymmetry_stage1/`（7.2M · 31 文件）

| 类别 | 代表文件 | 大小 | 行数 |
|:---|:---|:---:|:---:|
| 事件表（long / extended / daily_atr / atr_vs_skew 等） | long_events.csv · extended_long_events.csv | 2.5M / 560K | 11749 / 7176 |
| 条件 alpha 矩阵（contract / segment × DN/UP） | conditional_alpha_by_contract.csv 等 | 4-12K | 11~26 |
| 信息量扫描（分位/五分位/阈值 σ / prof_space） | quantile_sweep.csv · quintile_stats.csv · threshold_by_sigma.csv · profit_space.csv | 8-48K | 41-241 |
| 严格验证（cluster bootstrap · monotonic · gatekeeper · IC 等） | cluster_bootstrap_significance.csv · per_symbol_ic.csv · pooled_ic.csv · cross_symbol_consistency.csv | 4-28K | 5-481 |

### 阶段 2 · `project_data/logs/poc_va_asymmetry_stage2/`（6.3M · 11 文件）

| 类别 | 代表文件 | 大小 | 行数 |
|:---|:---|:---:|:---:|
| 事件表（OOS × 2） | oos_events.csv · short_scan_events.csv | 2.2M / 4.0M | 10519 / 10519 |
| 参数网格（long / short） | param_grid_long.csv · param_grid_short.csv | 12K | 97 / 97 |
| ν_implied / 时间衰减 / 跨周期 | final_signal_nu_implied.csv · short_e_time_decay.csv · final_signal_timeframes.csv | 4K | 5 / 9 / 17 |
| OOS 结果（prefix / short E 等） | oos_by_prefix.csv · short_e_by_prefix.csv · short_e_horizon.csv · short_scan_8h.csv | 4K | 6~15 |

### 阶段 3 · `project_data/logs/poc_va_asymmetry_stage3/`（128K · 26 文件）

| 类别 | 代表文件 | 大小 | 行数 |
|:---|:---|:---:|:---:|
| 分类器性能矩阵 | classifier_stat_2_perf.csv · classifier_stat_2_symbol_matrix.csv · classifier_strict_bootstrap.csv · classifier_perf_corrected.csv | 4-8K | 16~134 |
| 三层严格验证 (stat 1/2/3) | classifier_stat_1_ci_diff.csv · classifier_stat_3_counterfactual.csv · classifier_stat_3_independence.csv · classifier_stat_3_time_in_market.csv | 4-8K | 6~106 |
| 5 个任务 | task1_prefix_deep.csv / task1_summary · task2_atr_regime · task3_exp_a_regime_filter / task3_regime_transition · task4_short_mechanism · task5_overlap | 4-8K | 4-43 |
| 诊断 + 连续性 + 阈值 + 三档 | twelve_cells_diagnosis · three_bands_lopo.csv / three_bands_per_prefix · classifier_threshold_scan · classifier_prefix_rank_comparison · skew_ks_pairwise · skew_dist_per_prefix / skew_dist_per_contract · edge_sensitivity · atr_vs_trend_independence | 4-8K | 5~106 |
| 稳定/转换期深潜 | deep_stable_vs_transition_dist / _horizon / _attribution | 4K | 5~29 |

### 阶段 4 · `project_data/logs/poc_va_asymmetry_stage4/`（约 2M · 5 文件）

| 文件名 | 大小 | 行数 |
|:---|:---:|:---:|
| dataset_full.parquet | 1.8M | parquet |
| stage4_step2_144tier_descriptive.csv | 52K | 217 |
| stage4_step3_144tier_verification.csv | 28K | 100 |
| stage4_6class_merged_verification.csv | 4.0K | 19 |
| stage4_step2_seven_layer_verification.csv | 4.0K | 16 |

## 脚本归档清单（已搬入 `raw-scripts/` · 70 个 · 按阶段分组）

### Stage 0 · 早期探索与测量辅助（19 个 · 阶段 1 前后测量/验证用）

| # | 脚本 | 用途 |
|:---:|:---|:---|
| 1 | poc_va_asymmetry_atr_check.py | ATR 制度检查 |
| 2 | poc_va_asymmetry_bad_contracts.py | 坏合约/异常合约剔除诊断 |
| 3 | poc_va_asymmetry_bayesian.py | 贝叶斯分层 alpha 估计（阶段 1 bayesian_events.csv 生成）|
| 4 | poc_va_asymmetry_cluster_bootstrap.py | 早期 cluster bootstrap 显著性实现 |
| 5 | poc_va_asymmetry_conditional_alpha.py | 条件 alpha 矩阵（DN 侧 × segment/contract）|
| 6 | poc_va_asymmetry_conditional_alpha_up.py | 条件 alpha 矩阵（UP 侧）|
| 7 | poc_va_asymmetry_daily_atr.py | 日线 ATR 事件表生成 |
| 8 | poc_va_asymmetry_diag_cu.py | cu2601 假象专项诊断（阶段 1 后期校正）|
| 9 | poc_va_asymmetry_distribution.py | A3_skew 分布拟合（阶段 1 distribution_fit.csv 生成）|
| 10 | poc_va_asymmetry_event_vs_nonevent.py | Event vs Non-event 对照分析（event_vs_nonevent.csv 生成）|
| 11 | poc_va_asymmetry_extended_symbols.py | 扩展合约集加载（从 ~19 合约扩至更大池）|
| 12 | poc_va_asymmetry_multilayer_ci.py | 多层组合 CI 验证（阶段 1 末尾）|
| 13 | poc_va_asymmetry_multilayer_no_lookahead.py | 严格无未来函数版本的多层 CI |
| 14 | poc_va_asymmetry_no_lookahead.py | 严格无未来函数版主测量流程 |
| 15 | poc_va_asymmetry_prev_ndays.py | 前 N 天 profile 窗口对比 |
| 16 | poc_va_asymmetry_return_shape.py | 收益分布形状拟合（偏度/厚尾）|
| 17 | poc_va_asymmetry_rolling_compare.py | Rolling 窗口 vs W1 对比（rolling 证伪）|
| 18 | poc_va_asymmetry_sigma_no_lookahead.py | σ 无未来函数版测量（阶段 1 v7 核心）|
| 19 | poc_va_asymmetry_threshold_dedup.py | 阈值去重扫描（threshold_by_sigma + threshold_dedup_scan）|

### Stage 1 · 测量与信息量（5 个）

| # | 脚本 | 用途 |
|:---:|:---|:---|
| 1 | poc_va_asymmetry_stage1.py | 主入口：阶段 1 基础测量与 alpha 矩阵 |
| 2 | poc_va_asymmetry_stage1_profit_space.py | prof_space 探索（段 × 合约 alpha）|
| 3 | poc_va_asymmetry_stage1_quantile_sweep.py | 分位 sweep（阈值网格）|
| 4 | poc_va_asymmetry_stage1_quintile.py | 五分位统计 |
| 5 | poc_va_asymmetry_stage1_significant.py | cluster bootstrap 显著性 |

### Stage 2 · 跨周期护栏 + ν_implied（8 个）

| # | 脚本 | 用途 |
|:---:|:---|:---|
| 6 | poc_va_asymmetry_stage2_final_verify.py | 4 主线最终验证（Bonferroni · ν_implied · 跨周期一致）|
| 7 | poc_va_asymmetry_stage2_grid_search.py | 参数网格（long/short 2×97）|
| 8 | poc_va_asymmetry_stage2_nu_implied.py | ν_implied 反算（σ_imp vs σ_real 一致性）|
| 9 | poc_va_asymmetry_stage2_oos.py | OOS 合约全量扫描 |
| 10 | poc_va_asymmetry_stage2_short_e_deep.py | 空头 E_h(t) 深入（按 prefix × 持有期）|
| 11 | poc_va_asymmetry_stage2_short_scan.py | 空头扫描 8h 持有期 |
| 12 | poc_va_asymmetry_stage2_time_decay.py | 信号时间衰减（horizon 扫描）|
| 13 | poc_va_asymmetry_stage2_timeframe.py | 跨周期（1h vs 4h vs 1d）一致性 |

### Stage 3 · 稳健性深度检验（23 个）

| # | 脚本 | 用途 |
|:---:|:---|:---|
| 14 | poc_va_asymmetry_stage3_atr_vs_trend_independence.py | ATR × trend 独立性检验（KF-23 证据）|
| 15 | poc_va_asymmetry_stage3_cell_continuity.py | §13.12 相邻格连续性验证 |
| 16 | poc_va_asymmetry_stage3_classifier_perf_fix.py | 分类器性能修正（统计偏误校正）|
| 17 | poc_va_asymmetry_stage3_classifier_stat_1.py | L1 样本量 + L2 CI 排 0（bootstrap）|
| 18 | poc_va_asymmetry_stage3_classifier_stat_2.py | L2 按 prefix 矩阵 + 品保指标 |
| 19 | poc_va_asymmetry_stage3_classifier_stat_3.py | L3 反事实 + L4 时间占用市场 |
| 20 | poc_va_asymmetry_stage3_classifier_strict_bootstrap.py | 七层严格性（L1-L7 汇总）· family=8 Bonferroni |
| 21 | poc_va_asymmetry_stage3_deep_stable_vs_transition.py | 稳定 vs 转换期归因（KF-R/T/U 证据）|
| 22 | poc_va_asymmetry_stage3_edge_sensitivity.py | 阈值边界敏感性（段划分边缘稳定性）|
| 23 | poc_va_asymmetry_stage3_prefix_rank_experiment.py | 品种 rank 对比实验 |
| 24 | poc_va_asymmetry_stage3_skew_dist_diagnosis.py | skew 分布 per-contract 诊断（KS pairwise）|
| 25 | poc_va_asymmetry_stage3_task1_prefix_deep.py | 任务 1 · 品种异质性深潜 |
| 26 | poc_va_asymmetry_stage3_task2_atr_regime.py | 任务 2 · ATR 制度稳定性 |
| 27 | poc_va_asymmetry_stage3_task2_deep_dive.py | 任务 2 · ATR 档深入 |
| 28 | poc_va_asymmetry_stage3_task3_exp_a_regime_filter.py | 任务 3 · 实验 A · 制度过滤器 |
| 29 | poc_va_asymmetry_stage3_task3_regime_transition.py | 任务 3 · 制度转换识别 |
| 30 | poc_va_asymmetry_stage3_task4_short_mechanism.py | 任务 4 · 空头机制（崩盘前奏 vs 均值回归）|
| 31 | poc_va_asymmetry_stage3_task5_overlap.py | 任务 5 · 重叠相关性修正 |
| 32 | poc_va_asymmetry_stage3_three_bands_oos.py | 三档分类 · LOPO 留一品种 OOS |
| 33 | poc_va_asymmetry_stage3_three_bands_verify.py | 三档分类 · per prefix 验证 |
| 34 | poc_va_asymmetry_stage3_threshold_fine_scan.py | 阈值精细扫描（段边界附近）|
| 35 | poc_va_asymmetry_stage3_twelve_cells_supplement.py | §13.13 12 格补充证据 |
| 36 | poc_va_asymmetry_stage3_twelve_cells.py | 12 格主分析（KF-23 主体）|

### Stage 4 · 分类器三维深化 + 合并降级（15 个）

| # | 脚本 | 用途 |
|:---:|:---|:---|
| 37 | poc_va_asymmetry_stage4_data_full.py | 143 合约扩容数据集加载 |
| 38 | poc_va_asymmetry_stage4_step1_exclusive_classes.py | v3.0 · 10 互斥 tier 描述性（冻结基线 0eccf72）|
| 39 | poc_va_asymmetry_stage4_step2_seven_layer.py | v3.0 · family=15 七层严格验证 |
| 40 | poc_va_asymmetry_stage4_symbol_diagnosis.py | 品种异质性诊断（KF-24 证据）|
| 41 | poc_va_asymmetry_stage4_export_data.py | 数据导出（下游策略层用）|
| 42 | poc_va_asymmetry_stage4_step2_144tier_descriptive.py | v9.1 Step 2 · 144 tier 描述性扫描 |
| 43 | poc_va_asymmetry_stage4_step3_144tier_verification.py | v9.1 Step 3 · 144 tier 严格验证 + BH FDR + Bonferroni sanity |
| 44 | poc_va_classifier_tier_grading.py | 分类器 tier 分级辅助 |
| 45 | poc_va_classifier_verify.py | 分类器验证辅助 |
| 46 | poc_va_stage4_6class_merged.py | KF-29 · 6 类合并降级验证（通过率 20%→83%）|
| 47 | poc_va_stage4_build_3tables.py | 方案 B · 3 表聚合（按 trend 拆 · 稳健度计数）|
| 48 | poc_va_stage4_build_6tables.py | 方案 A · 6 表聚合（stable/trans × Tup/Tflat/Tdn）|
| 49 | poc_va_stage4_check_l2_amid.py | L2_Amid_Tup 未通过原因诊断（方差过大）|
| 50 | poc_va_stage4_dump_detail.py | 详细导出 |
| 51 | poc_va_stage4_fail_analysis.py | 失败 tier 原因分析（Bonferroni 是主瓶颈）|

**复现链路（按阶段）**：
- stage1：stage1.py → quantile_sweep → quintile → profit_space → significant
- stage2：grid_search → oos → nu_implied → timeframe → short_scan → short_e_deep → time_decay → final_verify
- stage3：task1~5 + twelve_cells + three_bands + classifier_stat_{1,2,3} → classifier_strict_bootstrap → deep_stable_vs_transition → cell_continuity / threshold_fine_scan
- stage4：data_full → step1_exclusive_classes → step2_seven_layer → symbol_diagnosis → step2_144tier → step3_144tier(FDR) → 6class_merged → build_tables → fail_analysis

## 未归档（保留在长期路径）

**判断为"非专属 / 长期资产"**：
- `workspace/strategies/classifiers/poc_va.py` + `__init__.py` — **长期分类器组件**（不是临时策略），留作下游主题引用
- `docs/research/themes/poc-value-area-asymmetry/` 六份长期文档 — theme 活跃保留
- `docs/research/archived-notes/README.md` — 顶层索引，不归入子批次
