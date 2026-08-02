# raw-outputs · structural-shaping-alpha freeze

> 类型：Archive / 原始实验输出
> 状态：已归档 · 主题冻结（2026-07-24）
> 原位置：`project_data/research/first_passage_boundary/`
> 补归档：2026-08-02（原数据遗留在 project_data，本次补入归档）

## 1. 已入库文件（31 个 JSON）

`first_passage_boundary/` 子目录保存首达边界探索器及各 KF 验证脚本输出的 **JSON 汇总**（均 <120KB，git 跟踪），覆盖：

> 注：同目录磁盘上另有 39 个同名 `.csv`（合计约 460KB，与 JSON 内容重复，是脚本的扁平表输出）。仓库 `.gitignore` 全局忽略 `*.csv`，故这些 CSV 不入库但保留在归档目录磁盘上，与既有归档批次惯例一致。

- `boundary_explorer_realcost_*.json`：5m/15m/1h/全周期 × 多个时间戳的 65-combo 网格结果
- `cost_sensitivity_*`、`cross_period_stratified_*`、`extreme_rr_stratified_*`
- `drift_detector_full_scan_*`、`hf_trend_leakage_*`、`hurst_stratified_*`
- `fourier_finite_time_*`、`fpt_nu_nonzero_validation_*`、`fpt_bootstrap_ci_*`、`fpt_conditional_expect_*`
- `fpt_kf23_jump_correction_*`、`fpt_kf24_sigma_timevary_*`、`fpt_kf25_trailing_barrier_mc_*`
- `kf15_gbm_fit_*`、`kf15_significance_*`、`recheck_kf11_fourier_*`
- `symbol_sector_stratified_*`、`vol_regime_stratified_*`
- `corn_1h_*`（dirrand_grid / realized_strength / strength_dirrand_yield / strength_W{20,80} / top_slice_W{20,80}）

这些文件即 `shaping-theory.md` 中各 KF 数据文件字段（`project_data/research/first_passage_boundary/<name>.{json,csv}`）所指对象。

## 2. 逐笔大 CSV（已删除，仅留指纹）

`boundary_explorer_trades_realcost_*.csv` 是逐笔成交明细，单文件 0.8–26MB（合计约 75MB），超过仓库跟踪文件体量上限，原位于 `project_data/research/first_passage_boundary/`，已于 2026-08-02 清理（该目录为无主历史数据）。这些文件由 `raw-scripts/first_passage_boundary_explorer.py` 可再生；下表保留 md5 + 行数作为历史指纹，复现后可按 hash 校验：

| 文件 | md5 | 行数 |
|---|---|---|
| boundary_explorer_trades_realcost_15m_20260714_211025.csv | aa866125393fac2167b16ff53b99ccef | 104391 |
| boundary_explorer_trades_realcost_15m_20260714_214524.csv | e47a05644a69c5e144e330b4b6a0b279 | 57817 |
| boundary_explorer_trades_realcost_15m_20260714_232251.csv | 85448ec0a787815f40f464fbc82c47b8 | 32121 |
| boundary_explorer_trades_realcost_1h_20260714_211513.csv | 8c0ec7fd0bb6d5a38d8ad0d9537cd1d5 | 31201 |
| boundary_explorer_trades_realcost_1h_20260714_214722.csv | 5fbb0010522f8e24820bfcba2a978b8b | 17281 |
| boundary_explorer_trades_realcost_1h_20260714_232335.csv | a5a3d0ace424db5b487a1256ee20c5cb | 9601 |
| boundary_explorer_trades_realcost_20260714_151956.csv | 46b188a1426ace17419fd7d8d0161670 | 88597 |
| boundary_explorer_trades_realcost_20260714_153121.csv | 1b050587e3fe9e21c545f6b2ef6aad3a | 319931 |
| boundary_explorer_trades_realcost_5m_20260714_213917.csv | c6d2f922113be115a8339dd2998bbdf1 | 177193 |
| boundary_explorer_trades_realcost_5m_20260714_232055.csv | d47622eb181ceea889fe235f871f8429 | 98441 |

对应生成脚本：`raw-scripts/first_passage_boundary_explorer.py`（`--flat-cost-debug` 等档位）。
