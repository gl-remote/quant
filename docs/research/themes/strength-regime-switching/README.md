# Strength Regime Switching

基于 `structural-shaping-alpha` KF-27 框架的**市场强度 regime 切换检测与自适应交易策略**研究主题。

## 问题定义

上游主题证明：品种的 $|\nu|/\sigma$ 服从 FoldedNormal($\mu_D, \sigma_D$) 分布，KF-27 给出了**全时段静态最优**塑形容器。但实盘中 $|\nu|/\sigma$ 存在显著的时间序列自相关与 regime 切换行为——如果能在**强趋势阶段多用仓位、弱趋势阶段少做或不做**，应能进一步提升 Sharpe 与年化。

## 核心假设

$$H_0: \text{Regime 切换检测无法提升 KF-27 静态最优的绩效}$$

$$H_1: \text{分层参数适配 + 时间择时可在同等破产风险下提升 Sharpe ≥ 0.3}$$

## 上游依赖

- `../structural-shaping-alpha/shaping-theory.md` — KF-27 闭式接口、$|\nu|/\sigma$ 分布参数
- `../structural-shaping-alpha/raw-scripts/corn_1h_strength_three_views.py` — 强度探测标准脚本
- `../structural-shaping-alpha/raw-scripts/kf26_parameter_optimizer.py` — 参数优化器

## 关键 KPI

| 指标 | 目标 | 测量方式 |
|---|---|---|
| 识别器 se | ≤ 0.05 | 估计值与 W=160h 滑动窗口的校准误差 |
| Regime 切换延迟 | 中位数 ≤ 40h | 从 true breakpoint 到检测的滞后 |
| Sharpe/年 提升 | ≥ +0.3 | 分层参数 vs KF-27 静态最优 OOS |
| regime 误检率 | ≤ 4 次/年 | 在 Monte Carlo GBM 仿真上的误触发次数 |
