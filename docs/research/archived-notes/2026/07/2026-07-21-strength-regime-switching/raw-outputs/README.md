# raw-outputs · strength-regime-switching

> 类型：Archive / 原始实验输出
> 状态：已归档（2026-07-21 批次）
> 原位置：`project_data/research/strength_regime_switching/`
> 补归档：2026-08-02（原数据遗留在 project_data，本次补入归档）

保存 strength-regime-switching 主题 P0–P4 各脚本输出的 CSV/JSON（均 <100KB，全量入库）：

- P0 强度基线：`p0_strength_profile.csv`、`p0_kf27_optimal_threshold.csv`
- P1 自相关/互相关：`p1_autocorrelation.csv`、`p1_cross_correlation.csv`、`p1_decision_inputs.json`、`p1_xhat_ts_{corn,corn_starch,soybean_meal}.csv`
- P2 CUSUM/小波断点：`p2_breakpoints_*.csv`（多品种多方法）、`p2_cusum_summary.{csv,json}`
- P3 状态机：`p3_regime_segments_{corn,corn_starch,soybean_meal}.csv`
- P4 固定 vs 分层对比：`p4_comparison_fixed_vs_layered.csv`、`p4_kf27_layered_parameters.csv`

对应脚本见 `../raw-scripts/`（`p0_*`、`p1_*`、`p2_*`、`p3_*`、`p4_*`）。
