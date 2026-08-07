# H_only 交易信号探索（已归档）

## 归档说明

本目录包含 Stage 3–9 对 H_only 状态作为交易信号的完整探索，以及两个独立验证（VRP、R_1h_d 熊市验证）。

**最终结论：H_only 不可作为独立交易信号。** 所有在 2024–2026 牛市样本中观察到的正收益，在 2022–2023 熊市数据中均失效或翻转，确认为多头 beta 而非信号 alpha。

## 结论链

| 阶段 | 文档 | 核心发现 |
|---|---|---|
| Stage 3 | [stage3-results.md](./stage3-results.md) | H_only confirmed 后 fwd_ret_20 = +0.47%，但需事后确认 |
| Stage 3 待办 | [stage3-todo.md](./stage3-todo.md) | 早期探索计划 |
| Stage 4 | [stage4-results.md](./stage4-results.md) | confirmed 在超卖位置收益更高，但方向一致性仅 50% |
| Stage 5 | [stage5-results.md](./stage5-results.md) | 成交量/OI/跳空无法预测 confirmed（CV AUC 0.53） |
| Stage 5 待办 | [stage5-todo.md](./stage5-todo.md) | 前瞻指标探索计划 |
| Stage 7 | [stage7-results.md](./stage7-results.md) | 短脉冲（1–2 根）事后 +1.76%，胜率 85% |
| Stage 8 | [stage8-results.md](./stage8-results.md) | 可执行短脉冲策略 +0.07%，跑输随机基准 |
| Stage 9 | [stage9-results.md](./stage9-results.md) | 加 -1% 止损后 +0.21%，但随机入场同样止损 +0.27%，是 beta |
| 机制分析 | [mechanism-oversold-vs-trend.md](./mechanism-oversold-vs-trend.md) | 超卖反弹 vs 趋势启动的机制对比 |
| VRP 验证 | [vrp-validation-report.md](./vrp-validation-report.md) | 随机+止损做多 +0.16%，做空 -1.01%，是多头 beta 非 VRP |
| R_1h_d 熊市验证 | [term-bear-validation-archive.md](./term-bear-validation-archive.md) | F 组 R_1h_d 多空组合在熊市 -0.44%，完全翻转 |

## 方法论教训

1. 事后分组的高收益不等于可交易策略（Stage 7 → Stage 8）；
2. 必须有随机基准（Stage 9）；
3. 必须做空头测试和熊市验证（VRP、R_1h_d）；
4. 前瞻指标 AUC < 0.6 不可用；
5. 非重叠抽样是必须的；
6. 多空组合不等于 market neutral。

## 相关脚本

对应脚本仍在上级 `scripts/` 目录：
- `stage3_state_paths.py` ~ `stage9_stop_loss.py`
- `vrp_validation.py`
- `term_structure.py`, `term_validation.py`, `term_bear_validation.py`
- `fetch_bear_market.py`（下载 2022–2023 熊市数据）
