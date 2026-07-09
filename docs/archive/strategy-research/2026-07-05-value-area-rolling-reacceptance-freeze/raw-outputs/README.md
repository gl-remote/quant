# raw-outputs：value-area rolling reacceptance freeze 阶段原始报告

> 类型：Archive / 原始实验输出（MD 报告 + JSON 明细）  
> 状态：已归档 · 主题冻结  
> 所属阶段：value-area-rolling-reacceptance 冻结批次（2026-07-05）  
> 批次入口：[../README.md](../README.md) · [../raw-workbench/](../raw-workbench/)

## 1. 目录用途

本目录保存 rolling_reacceptance 冻结阶段各脚本直接输出的原始 Markdown 报告与 JSON 明细。

对应 `raw-workbench/` 中每篇 workbench 的「原始输出」字段所指向的位置（原位置 `project_data/analysis/rolling_reacceptance_stage*/`，现已搬入归档）。

## 2. 子目录说明

| 子目录 | 对应阶段 | 文件数 | 代表报告文件 |
|:---|:---|:---:|:---|
| `rolling_reacceptance_stage1/` | Stage 1 · 方向层筛选 | 2 | `stage1_direction_report.md` / `.json` |
| `rolling_reacceptance_stage1_5/` | Stage 1.5 · POC 引力 & 距离到达率 + A2~A5 子实验 | 14 | `stage1_5_A_distance_reach_atr.md`（ATR 修正主结论）· `A2_reacceptance_distance_dist.md` · `A3_expected_value.md` · `A4_multi_structure.md` · `A5_multi_anchor.md` · `A5b_reacc_multi_anchor.md`（均 .md + .json 配对）|
| `rolling_reacceptance_stage4/` | Stage 4 · 显著性 & 多锚点 EV | 3 | `stage4_significance_test.md` · `stage4_multi_anchor_expected_value.md` + 1 json |
| `rolling_reacceptance_stage4b/` | Stage 4b · 触发信号显著性 | 2 | `stage4b_trigger_significance.md` + 1 json |
| `rolling_reacceptance_stage4b_15m/` | Stage 4b · 15m 跨周期复核 | 2 | `stage4b_15m_trigger_significance.md` + 1 json |

## 3. 命名与对应脚本

| 报告名 | 对应 `raw-scripts/` 脚本 |
|:---|:---|
| stage1_direction_report | `rolling_reacceptance_stage1_direction.py` |
| stage1_5_A_distance_reach{_atr} | `rolling_reacceptance_stage1_5_A_distance_reach.py` · `_atr.py` |
| stage1_5_A2_reacceptance_distance_dist | `rolling_reacceptance_stage1_5_A2_reacceptance_distance.py` |
| stage1_5_A3_expected_value | `rolling_reacceptance_stage1_5_A3_expected_value.py` |
| stage1_5_A4_multi_structure | `rolling_reacceptance_stage1_5_A4_multi_structure.py` |
| stage1_5_A5_multi_anchor · A5b | `rolling_reacceptance_stage1_5_A5_multi_anchor.py` · `A5b.py` |
| stage4_significance_test | `rolling_reacceptance_stage4_significance.py` |
| stage4_multi_anchor_expected_value | `rolling_reacceptance_stage4_multi_anchor_expected_value.py` |
| stage4b_trigger_significance | `rolling_reacceptance_stage4b_trigger_significance.py` |
| stage4b_15m_trigger_significance | `rolling_reacceptance_stage4b_15m.py` |

## 4. raw-workbench 相对路径说明

`raw-workbench/*.md` 中存在大量相对路径链接 `../../project_data/analysis/rolling_reacceptance_stage*/...`，这是归档时的实际历史路径记录，**保留不作批量替换**。如需从 workbench 跳转本目录报告，可按上表映射手动定位。
