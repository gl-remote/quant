# Strength Regime Switching · 研究状态

| 阶段 | 状态 | 开始 | 完成 | 产出 |
|---|---|---|---|---|
| P0: 前期准备 — 多品种 $|\nu|/\sigma$ 分布测绘 | ✅ 完成 | 2026-07-18 | 2026-07-20 | `p0_strength_profile.csv`, `p0_kf27_optimal_threshold.csv` |
| P1: $|\nu|/\sigma$ 时间序列自相关分析（Gatekeeper） | ✅ 完成 | 2026-07-20 | 2026-07-20 | `p1_autocorrelation.csv`, `p1_*_xhat_ts.csv` → 决策走路线 A |
| P2: 多分辨率 CUSUM 断点检测（路线 A） | ✅ 完成 | 2026-07-21 | 2026-07-21 | `p2_breakpoints_*.csv`, `p2_cusum_summary.csv` |
| P3: 状态机 RLL 分段与滞后确认 | ✅ 完成 | 2026-07-21 | 2026-07-21 | `p3_regime_segments_*.csv` → 三品种分段完成 |
| Phase-Summary: P0~P3 全阶段实验报告 | ✅ 完成 | 2026-07-21 | 2026-07-21 | `Phase-Summary-P0-P3.md` → 汇总各阶段结果与结论 |
| P4: 分层参数适配回测 + 对比实验 | ✅ 完成 | 2026-07-21 | 2026-07-21 | `p4_kf27_layered_parameters.csv`, `p4_comparison_fixed_vs_layered.csv` → 对比完成 |
| P5: MCS 仿真误检率验证 | ⏸ 归档暂停 | — | — | — |
| P6: OOS 样本外验证 | ⏸ 归档暂停 | — | — | — |

## 整体状态

**归档暂停**（2026-07-21）：
- 核心假设全部验证通过 → 高强度 regime → 更高预期 Sharpe
- 工程实现问题识别：当前"CUSUM 断点 + 区间整体分配"方式不够贴合 K线 直观，容易合并多个阶段
- 改进方向明确：逐点分位数分类 + 最小停留确认，不增加参数，不过拟合
- 结论：核心假设成立，实现需要改进，暂存归档，未来重启直接试改进方案

## 参考

- 完整复盘：[review-2026-07-21.md](./review-2026-07-21.md)

