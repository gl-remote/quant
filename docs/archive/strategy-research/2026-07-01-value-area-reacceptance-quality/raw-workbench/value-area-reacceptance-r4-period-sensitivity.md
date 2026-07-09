# value_area_reacceptance R4：交易周期敏感性实验报告

> 类型：Workbench / 实验报告
> 状态：已完成
> 日期：2026-06-30
> 阶段规划：[value-area-reacceptance-stage-plan.md](./value-area-reacceptance-stage-plan.md)
> 上一轮报告：[value-area-reacceptance-r3-reaccept-depth.md](./value-area-reacceptance-r3-reaccept-depth.md)

## 1. 实验问题

R3 显示 fixed ticks 对 `1~4 ticks` 很敏感：

```text
过浅会增加噪声和成本；
过深会损失 POC 空间或样本质量；
有效区域大致集中在 2~3 ticks，但不同品种偏好不同。
```

因此本轮测试：

```text
把交易周期从 5m 提高到 15m，是否可以降低 1~2 ticks 级别的噪声敏感，
并让 value_area_reacceptance 的重新接受信号更稳定？
```

本轮不是参数优化，只做周期敏感性诊断。

## 2. 实验设置

### 2.1 5m 对照组

复用 R3 / R2 的 5m 主区间：

```text
kline_period = 5m
min_reaccept_ticks ∈ [2, 3]
max_hold_bars = 12
```

### 2.2 15m 实验组

真实 15m 驱动设置：

```text
backtest.interval = 15m
kline_period = 15m
min_reaccept_ticks ∈ [2, 3]
max_hold_bars = 4
```

`max_hold_bars` 从 12 调整为 4，是为了大致保持 5m × 12 bars ≈ 15m × 4 bars 的持仓时长。

基础策略参数保持一致：

```json
{
  "profile_mode": "close",
  "value_area_ratio": 0.7,
  "min_breakout_ticks": 4,
  "failure_buffer_ticks": 1,
  "take_profit_mode": "poc",
  "stop_widen_multiplier": 1.5,
  "strict_close_exit": true,
  "max_trades_per_day": 1,
  "min_target_ticks": 8,
  "min_price_raw_rr": 0.5
}
```

## 3. 口径修正说明

实验中先跑过一批无效口径：

```text
backtest_id = 425~430
```

这些回测虽然 `strategy_params.kline_period = 15m`，但数据库 `backtests.kline_interval = 5m`，说明主回测引擎仍按 5m bar 驱动，只是策略多周期上下文读取了 15m。

因此，`425~430` 不纳入本轮结论。

有效 15m 组使用临时配置覆盖：

```text
[backtest]
interval = "15m"
```

并已确认：

```text
backtests.kline_interval = 15m
strategy_params.kline_period = 15m
```

## 4. 有效 15m 回测 ID

| backtest_id | run_id | symbol | kline_interval | strategy_period | min_reaccept_ticks | max_hold_bars | trades | total_return | net_pnl |
|-------------|--------|--------|----------------|-----------------|--------------------|---------------|--------|--------------|---------|
| 431 | 175 | DCE.m2601 | 15m | 15m | 2 | 4 | 10 | -4.5392% | -4539.2 |
| 432 | 176 | DCE.m2601 | 15m | 15m | 3 | 4 | 10 | -4.5136% | -4513.6 |
| 433 | 177 | CZCE.SR601 | 15m | 15m | 2 | 4 | 7 | -5.7882% | -5788.2 |
| 434 | 178 | CZCE.SR601 | 15m | 15m | 3 | 4 | 7 | -6.0396% | -6039.6 |
| 435 | 179 | SHFE.rb2601 | 15m | 15m | 2 | 4 | 18 | 0.4601% | 460.06 |
| 436 | 180 | SHFE.rb2601 | 15m | 15m | 3 | 4 | 12 | -0.1757% | -175.74 |

## 5. 15m 绩效结果

| id | symbol | ticks | total_return | net_pnl | commission | slippage | trades | win_rate | avg_win | avg_loss | win_loss_ratio | max_consecutive_loss |
|----|--------|-------|--------------|---------|------------|----------|--------|----------|---------|----------|----------------|----------------------|
| 433 | CZCE.SR601 | 2 | -5.7882% | -5788.2 | 318.2 | 370.0 | 7 | 75.00% | 485.47 | 7244.60 | 0.07 | 1 |
| 434 | CZCE.SR601 | 3 | -6.0396% | -6039.6 | 309.6 | 360.0 | 7 | 75.00% | 401.67 | 7244.60 | 0.06 | 1 |
| 431 | DCE.m2601 | 2 | -4.5392% | -4539.2 | 319.2 | 570.0 | 10 | 20.00% | 52.80 | 1148.00 | 0.05 | 3 |
| 432 | DCE.m2601 | 3 | -4.5136% | -4513.6 | 313.6 | 560.0 | 10 | 20.00% | 52.80 | 1141.60 | 0.05 | 3 |
| 435 | SHFE.rb2601 | 2 | 0.4601% | 460.06 | 1439.94 | 960.0 | 18 | 44.44% | 1371.50 | 1005.19 | 1.36 | 4 |
| 436 | SHFE.rb2601 | 3 | -0.1757% | -175.74 | 945.74 | 630.0 | 12 | 33.33% | 1613.80 | 850.84 | 1.90 | 3 |

## 6. 15m 风险结构结果

| id | symbol | ticks | clearings | avg_raw_rr | min_raw_rr | max_stop_risk_pct | worst_net_pct | force_flat | time_exit | take_profit |
|----|--------|-------|-----------|------------|------------|-------------------|---------------|------------|-----------|-------------|
| 433 | CZCE.SR601 | 2 | 4 | 0.844 | 0.563 | 1.920% | -7.245% | 0 | 1 | 2 |
| 434 | CZCE.SR601 | 3 | 4 | 0.763 | 0.563 | 1.920% | -7.245% | 0 | 1 | 2 |
| 431 | DCE.m2601 | 2 | 5 | 1.706 | 0.909 | 1.980% | -3.438% | 0 | 4 | 0 |
| 432 | DCE.m2601 | 3 | 5 | 1.654 | 0.813 | 1.980% | -3.438% | 0 | 4 | 0 |
| 435 | SHFE.rb2601 | 2 | 9 | 1.255 | 0.526 | 1.995% | -1.623% | 1 | 4 | 3 |
| 436 | SHFE.rb2601 | 3 | 6 | 1.440 | 0.667 | 1.980% | -1.150% | 1 | 4 | 1 |

## 7. 15m 成本安全边际

| id | symbol | ticks | total_cost | avg_net_win | cost / avg_net_win |
|----|--------|-------|------------|-------------|--------------------|
| 433 | CZCE.SR601 | 2 | 688.2 | 485.47 | 1.418 |
| 434 | CZCE.SR601 | 3 | 669.6 | 401.67 | 1.667 |
| 431 | DCE.m2601 | 2 | 889.2 | 52.80 | 16.841 |
| 432 | DCE.m2601 | 3 | 873.6 | 52.80 | 16.545 |
| 435 | SHFE.rb2601 | 2 | 2399.94 | 1371.50 | 1.750 |
| 436 | SHFE.rb2601 | 3 | 1575.74 | 1613.80 | 0.976 |

## 8. 与 5m 主区间对照

| symbol | ticks | 5m backtest | 5m return | 5m trades | 15m backtest | 15m return | 15m trades | 变化 |
|--------|-------|-------------|-----------|-----------|--------------|------------|------------|------|
| DCE.m2601 | 2 | 401 | 3.5168% | 12 | 431 | -4.5392% | 10 | 明显恶化 |
| DCE.m2601 | 3 | 402 | 2.3928% | 10 | 432 | -4.5136% | 10 | 明显恶化 |
| CZCE.SR601 | 2 | 403 | 0.2134% | 18 | 433 | -5.7882% | 7 | 明显恶化，左尾扩大 |
| CZCE.SR601 | 3 | 404 | 0.8828% | 12 | 434 | -6.0396% | 7 | 明显恶化，左尾扩大 |
| SHFE.rb2601 | 2 | 409 | -3.3142% | 16 | 435 | 0.4601% | 18 | 有改善，但与主线相反 |
| SHFE.rb2601 | 3 | 410 | -1.8014% | 14 | 436 | -0.1757% | 12 | 有改善，但仍不稳定 |

## 9. 关键发现

### 9.1 15m 没有解决 DCE.m 的 tick 敏感，反而破坏了主线

DCE.m 在 5m 下是当前主线：

```text
5m / 2 ticks: +3.5168%
5m / 3 ticks: +2.3928%
```

但真实 15m 后：

```text
15m / 2 ticks: -4.5392%
15m / 3 ticks: -4.5136%
```

虽然 15m 的 `avg_raw_rr` 看起来更高，但实际 `take_profit = 0`，多数通过 `time_exit` 退出，说明：

```text
15m 收盘确认太慢，重新接受信号已经错过 POC 回归窗口；
价格空间账面上还在，但短期兑现能力消失。
```

### 9.2 SR 在 15m 下出现高胜率但大左尾

SR 的 15m 胜率为 75%，但收益大幅为负：

```text
CZCE.SR601 / 15m / 2 ticks: -5.7882%
CZCE.SR601 / 15m / 3 ticks: -6.0396%
worst_net_pct = -7.245%
```

这说明 15m 把很多小盈利保留下来，但单次左尾远超前期风险预算观察口径。该结果不支持把 SR 升级为主线。

### 9.3 rb 在 15m 下改善，但不是当前主线方向

rb 在 5m 下持续失败，15m 后有所改善：

```text
SHFE.rb2601 / 15m / 2 ticks: +0.4601%
SHFE.rb2601 / 15m / 3 ticks: -0.1757%
```

这说明 rb 的 5m 重新接受可能过噪，15m 对它有一定降噪效果。但该改善不应改变当前主线，因为：

```text
1. DCE.m 主线被 15m 破坏；
2. rb 15m 只有 2 ticks 小幅转正，3 ticks 仍负；
3. 成本压力仍高，且 force_flat 仍存在；
4. 这更像 rb 的独立周期适配问题，不是 value_area_reacceptance 的统一改善。
```

### 9.4 周期比 ticks 更敏感

本轮说明，真正要警惕的不是只差 1~2 ticks，而是：

```text
5m → 15m 会改变信号语义。
```

5m 的重新接受是“短期失败后快速回归价值区”；15m 的重新接受更像“较慢确认后的区间内收盘”。后者可能：

```text
降低噪声；
但也错过 POC 回归最有利的位置；
并放大单根 bar 内部路径风险。
```

## 10. 本轮结论

```text
15m 不适合作为当前 value_area_reacceptance 主线交易周期。
```

具体结论：

```text
DCE.m2601：继续使用 5m，15m 明显破坏原有 edge；
CZCE.SR601：15m 左尾不可接受，继续降级观察；
SHFE.rb2601：15m 有改善迹象，但只能作为独立负面对照后续再看，不影响主线。
```

因此，当前主线不应从 5m 切到 15m。

## 11. 下一轮建议

不要继续直接提高交易周期。更合理的下一轮是：

```text
保留 5m 作为执行周期；
引入 15m / rolling context 作为过滤或质量标签，
而不是直接用 15m bar 触发入场。
```

候选实验：

```text
1. 5m entry + 15m context value area；
2. 5m entry + rolling_context_bars 过滤；
3. 只在 15m context POC 与前日 POC 同向时保留；
4. 比较 DCE.m 的 5m 主线是否能减少 1 tick 噪声，同时不损失 POC 回归窗口。
```

如果后续做归一化，建议先围绕 5m 执行周期做：

```text
reaccept_depth / previous_value_area_width；
reaccept_depth / 最近 5m 波动；
entry 在前日 value area 内部分位。
```
