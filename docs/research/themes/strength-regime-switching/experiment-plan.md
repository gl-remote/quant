# Experiment Plan

## P1: $|\nu|/\sigma$ 时间序列自相关分析（Gatekeeper）

验证 $|\nu|/\sigma$ 是否存在可预测的 temporal structure。

- 计算玉米 1h $\hat{x}_{W=80}(t)$ 序列的 ACF/PACF
- Ljung-Box 检验：$H_0: \text{白噪声}$
- 计算 regime 切换的持续性（半衰期、平均停留时间）
- **Gate**：若 Ljung-Box p > 0.05 且平均停留时间 < 20h，放弃研究

## P2: 多分辨率 CUSUM 断点检测

复现层叠检测算法：

1. 对 W ∈ {20, 40, 80, 160} 运行 CUSUM
2. 跨分辨率共识确认（≥ 3 分辨率在 ±20h 内同时检出）
3. 输出断点时间戳序列

**验证**：在仿真 GBM（常数 $\nu/\sigma$）上的误检率

## P3: 状态机 RLL（Run-Length Limiting）

三态状态机 + 最小停留约束 + 滞后确认窗口。

- LOW: $|\nu|/\sigma < 0.10$
- MID: $0.10 \leq |\nu|/\sigma \leq 0.25$
- HIGH: $|\nu|/\sigma > 0.25$

## P4: 分层参数适配回测

三 regime 分别装入 KF-27 最优参数：

| Regime | K_S | K_T | τ | 行为 |
|---|---|---|---|---|
| LOW | N/A | N/A | N/A | 不开仓 |
| MID | 2.0 | 6.0 | 前 65% | 年化最优 |
| HIGH | 3.0 | 9.0 | 前 65% | Sharpe 最优 |

## P5: MCS 误检率验证

1000 次 GBM 仿真，验证误检率 ≤ 4 次/年。

## P6: OOS 样本外验证

留出 2025H2 数据做 OOS 验证。
