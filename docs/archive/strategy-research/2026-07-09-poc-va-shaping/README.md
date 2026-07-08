# 2026-07-09-poc-va-shaping

## 归档主题

poc-value-area-asymmetry 分类器 v4.0 的塑形参数优化与成本后收益验证。

## 核心结论

- 6 类合并版分类器 v4.0 中，L_seg2_low_flat 应淘汰（任何参数下 IR 为负）
- 最优塑形参数：多头 SL1.0 ATR + 6~10h，空头 SL2.0~2.5 ATR + 8~10h
- Trailing（MFE≥2~3 ATR breakeven）在 10h 内几乎不触发，无效
- 考虑期货保证金制度后（保证金率 5~12%），80% 保证金约束从未触发
- 名义价值 100% 约束是实际瓶颈，日均名义暴露 653%
- 风控口径（2% 单笔止损 + 100% 名义上限）：年化 15.45%，Sharpe 2.23，MaxDD −7.51%
- 胜率 60.3%，盈亏比 1.41，单笔期望 +34.7 bps
- Combo L（SL1.5 + 6.67h + trailing）直接套用严重破坏质量（IR 从 0.23 降到 0.12）

## 文件清单

### 原始脚本（raw-scripts/）

| 文件 | 用途 |
|:---|:---|
| poc_va_cost_net_quick.py | 粗算整点开仓成本后收益（无塑形） |
| poc_va_annual_sharpe_quick.py | 无塑形口径的年化/夏普计算 |
| poc_va_combo_l_cost_net.py | Combo L 塑形方案套用验证 |
| poc_va_shaping_scan.py | 塑形参数扫描 v1（逐 bar 迭代，已废弃） |
| poc_va_shaping_scan_v2.py | 塑形参数扫描 v2（向量化，240 组合 × 6 tier） |
| poc_va_shaping_annual_sharpe.py | 扫描最优参数的年化/夏普 |
| poc_va_risk_managed_sharpe.py | 风控口径 v1（错误：未区分保证金） |
| poc_va_risk_managed_v2.py | 风控口径 v2（正确：考虑期货保证金） |
| poc_va_winrate_rr.py | 胜率、盈亏比、凯利分析 |
| poc_va_hold_period_analysis.py | 持仓期 vs IR 趋势分析（有 bug，废弃） |
| poc_va_hold_analysis_v2.py | 持仓期 vs IR 趋势分析 v2（修复版） |

### 原始数据（raw-data/）

| 文件 | 大小 | 说明 |
|:---|:---:|:---|
| poc_va_cost_net_quick.csv | 4K | 无塑形 tier 汇总 |
| poc_va_cost_net_quick.detail.csv | 564K | 无塑形逐笔明细 |
| poc_va_annual_sharpe_quick.csv | 4K | 无塑型年化汇总 |
| poc_va_combo_l_cost_net.csv | 4K | Combo L 套用汇总 |
| poc_va_combo_l_cost_net.detail.csv | 480K | Combo L 套用逐笔明细 |
| poc_va_shaping_scan_results.csv | 284K | 240 参数组合 × 6 tier 扫描结果 |
| poc_va_shaping_annual_sharpe.csv | 4K | 最优塑形年化汇总 |
| poc_va_risk_managed_sharpe.csv | 4K | 风控 v1 汇总 |
| poc_va_risk_managed_v2.csv | 4K | 风控 v2 tier 分档 |

### 上游数据（不搬运，只登记）

- `project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline.parquet`
- `project_data/market_data/csv/*.tqsdk.5m.csv`

## 复现备注

所有脚本依赖：
- `workspace/common/contract_specs.py`
- `workspace/common/symbol_utils.py`
- `workspace/data/output_paths.py`

运行命令：`unset PYTHONHOME && unset PYTHONPATH && uv run python <script>`

## 关系

- 继承：archive:2026-07-08-poc-va-asymmetry（分类器 v4.0 冻结批次）
- 下游：待品种筛选、信号强度加权、多空权重优化
