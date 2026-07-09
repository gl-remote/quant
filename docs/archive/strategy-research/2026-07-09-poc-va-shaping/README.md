# 2026-07-09-poc-va-shaping

## 归档主题

poc-value-area-asymmetry 分类器 v4.0 的塑形参数优化、成本后收益验证、以及组合层优化（品种筛选 × 信号强度加权 × 多空权重）。

## 核心结论

### 第一层：塑形参数优化（上游 archive）

- 6 类合并版分类器 v4.0 中，L_seg2_low_flat 应淘汰（任何参数下 IR 为负）
- 最优塑形参数：多头 SL1.0 ATR + 8h，空头 SL2.5 ATR + 10h
- Trailing（MFE≥2~3 ATR breakeven）在 10h 内几乎不触发，无效
- 考虑期货保证金制度后（保证金率 5~12%），80% 保证金约束从未触发
- 名义价值 100% 约束是实际瓶颈，日均名义暴露 653%
- 风控口径（2% 单笔止损 + 100% 名义上限）：年化 15.45%，Sharpe 2.23，MaxDD −7.51%
- 胜率 60.3%，盈亏比 1.41，单笔期望 +34.7 bps
- Combo L（SL1.5 + 6.67h + trailing）直接套用严重破坏质量（IR 从 0.23 降到 0.12）

### 第二层：组合层优化（下游 va-asymmetry-composite）

- B0 基线（S1/W0/VW0）：年化 15.10%，Sharpe 2.70，MaxDD −2.40%，298 笔交易，115 合约
- **Stage 1 三大方向 0/6 通过**：品种筛选(S2)、强度加权(W1/W2/W3)、多空权重(VW1/VW2) 全部无增量 alpha
  - S2（品种筛选）：ΔSh −0.27，剔除后反而拖累
  - W1（skew 距离加权）：修正 spec 公式歧义后等价于 B0（ΔSh +0.00），无区分度
  - W2/W3：显著拖累（ΔSh −0.32/−0.31），三维乘积产生过度惩罚
  - VW1/VW2：持平/拖累（ΔSh −0.01/−0.23）
- **结论：B0 = S1 × W0 × VW0 为最优组合方案，组合层 alpha 已被吃满**
- 交易数断层（B0=298 vs archive=1545）因 B0 使用完整合约集合的子集，不影响组合层比较结论

### math-spec 修正记录

本轮检查发现并修复了 9 处规格问题：
- W1 公式方向性歧义（对空头输出负值）→ 改为距离公式 `|rank−thr|`
- W3 clamp 时机未定义 → 显式"先各自 clamp 再乘积"
- §5.3 仓位公式漏 ATR 转换 → 补上 `entry_atr_bps/10000`
- §2 ATR 窗口写 20d 实际 10d → 改为 `daily_atr_10_bps`
- §0 VW3 引用不存在 → 删除
- §1.2 skew 段重叠 tie-break → 补充
- §3.3 时间退出精确定义缺失 → 补充
- §5.2 VW1 tier IR 粒度 → 显式"按 tier 组等权平均"

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
| va_composite_stage0_baseline.py | 组合层 B0 基线回测 |
| va_composite_stage1_gatekeepers.py | 组合层 Stage 1 三方向扫描（含修正后的 W/VW） |

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

### 组合层数据（不搬运，只登记）

| 文件 | 说明 |
|:---|:---|
| `project_data/ai_tmp/va_composite_stage0_baseline.trades.parquet` | B0 基线 298 笔交易 |
| `project_data/ai_tmp/va_composite_stage1_S2.trades.parquet` | S2 配置 232 笔交易 |
| `project_data/ai_tmp/va_composite_stage1_W1.trades.parquet` | W1 配置 298 笔交易 |
| `project_data/ai_tmp/va_composite_stage1_W2.trades.parquet` | W2 配置 298 笔交易 |
| `project_data/ai_tmp/va_composite_stage1_W3.trades.parquet` | W3 配置 298 笔交易 |
| `project_data/ai_tmp/va_composite_stage1_VW1.trades.parquet` | VW1 配置 298 笔交易 |
| `project_data/ai_tmp/va_composite_stage1_VW2.trades.parquet` | VW2 配置 298 笔交易 |

### 上游数据（不搬运，只登记）

- `project_data/logs/poc_va_asymmetry_stage4/classifier_v31_timeline.parquet`
- `project_data/market_data/csv/*.tqsdk.5m.csv`

### Workbench 报告（raw-workbench/）

| 文件 | 用途 |
|:---|:---|
| va-asymmetry-composite-stage0-init.md | Stage 0 立题复现流水 + 差异登记 |
| va-asymmetry-composite-stage0-baseline.md | B0 基线回测结果 + Gatekeeper 判定 |
| va-asymmetry-composite-stage1-gatekeepers.md | 7 配置矩阵 + 0/6 通过判定 + 各方向解读 |

## 复现备注

所有脚本依赖：
- `workspace/common/contract_specs.py`
- `workspace/common/symbol_utils.py`
- `workspace/data/output_paths.py`

运行命令：`unset PYTHONHOME && unset PYTHONPATH && uv run python <script>`

## 关系

- 继承：archive:2026-07-08-poc-va-asymmetry（分类器 v4.0 冻结批次）
- 下游：theme:va-asymmetry-composite（组合优化结论已并回本批次，主题保留为长期规格文档）
