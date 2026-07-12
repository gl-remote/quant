# value_area_reacceptance R2：品种适配诊断实验报告

> 类型：Workbench / 策略实验报告
> 状态：第二轮完成
> 创建日期：2026-06-30
> 阶段规划：[value-area-reacceptance-stage-plan.md](./value-area-reacceptance-stage-plan.md)
> 上一轮报告：[value-area-reacceptance-r1-risk-budget.md](./value-area-reacceptance-r1-risk-budget.md)
> 关联 issue：[trade-clearing-diagnostics-not-propagated.md](../../../../issues/trade-clearing-diagnostics-not-propagated.md)

## 1. 实验目的

本轮对应阶段规划中的实验线 B：品种适配诊断。

R1 已确认：

```text
当前主线候选在 100000 账户下未被 2%~3% 单次账户风险预算否决；
DCE.m2601 明显优于 CZCE.SR601；
SR 2 ticks 成本安全边际偏薄，3 ticks 左尾更友好。
```

本轮要回答：

```text
DCE.m2601 的优势是否能扩展到相近品种？
CZCE.SR601 的问题是 SR 特有，还是价值区结构普遍成本偏薄？
SHFE.rb2601 作为负面对照是否继续显示不适配？
```

## 2. 实验设置

基础参数沿用 R1：

```json
{
  "kline_period": "5m",
  "profile_mode": "close",
  "value_area_ratio": 0.7,
  "min_breakout_ticks": 4,
  "failure_buffer_ticks": 1,
  "take_profit_mode": "poc",
  "max_hold_bars": 12,
  "stop_widen_multiplier": 1.5,
  "strict_close_exit": true,
  "max_trades_per_day": 1,
  "min_target_ticks": 8,
  "min_price_raw_rr": 0.5
}
```

变量：

```text
symbol ∈ [DCE.m2601, DCE.c2601, DCE.cs2601, CZCE.SR601, SHFE.rb2601]
min_reaccept_ticks ∈ [2, 3]
```

数据可用性：

```text
上述品种均有 2025-09-01 ~ 2026-01-01 的 5m 数据。
```

备注：批量 `--pattern` 没有匹配到数据，本轮改用单品种顺序回测。该问题不影响本轮策略结论，但说明后续若需要批量实验，应单独检查 DataManager 的 pattern 匹配规则。

## 3. 回测 ID

| backtest_id | run_id | symbol | min_reaccept_ticks | 说明 |
|-------------|--------|--------|--------------------|------|
| 401 | 145 | DCE.m2601 | 2 | R1 结果，纳入横向对照 |
| 402 | 146 | DCE.m2601 | 3 | R1 结果，纳入横向对照 |
| 403 | 147 | CZCE.SR601 | 2 | R1 结果，纳入横向对照 |
| 404 | 148 | CZCE.SR601 | 3 | R1 结果，纳入横向对照 |
| 405 | 149 | DCE.c2601 | 2 | 本轮新增 |
| 406 | 150 | DCE.c2601 | 3 | 本轮新增，0 成交 |
| 407 | 151 | DCE.cs2601 | 2 | 本轮新增，0 成交 |
| 408 | 152 | DCE.cs2601 | 3 | 本轮新增，0 成交 |
| 409 | 153 | SHFE.rb2601 | 2 | 本轮新增 |
| 410 | 154 | SHFE.rb2601 | 3 | 本轮新增 |

## 4. 数据口径说明

沿用 R1 临时口径：

```text
风险结构字段：从 backtest_trades.decision_payload_json 的 $.diagnostics.strategy.* 抽取；
退出原因：从 trade_clearings.close_reason 的 `|` 前缀解析；
PnL / commission / slippage / MAE / MFE：使用 trade_clearings 字段。
```

清算层 issue 仍未修复：

```text
trade_clearings.exit_reason 为空；
trade_clearings.diagnostics_json 为空。
```

## 5. 绩效横向结果

| id | symbol | ticks | total_return | net_pnl | commission | slippage | trades | win_rate | avg_win | avg_loss | win_loss_ratio | max_consecutive_loss |
|----|--------|-------|--------------|---------|------------|----------|--------|----------|---------|----------|----------------|----------------------|
| 401 | DCE.m2601 | 2 | 3.5168% | 3516.8 | 403.2 | 720.0 | 12 | 50.00% | 1535.73 | 363.47 | 4.23 | 1 |
| 402 | DCE.m2601 | 3 | 2.3928% | 2392.8 | 347.2 | 620.0 | 10 | 40.00% | 1741.60 | 363.47 | 4.79 | 1 |
| 403 | CZCE.SR601 | 2 | 0.2134% | 213.4 | 696.6 | 810.0 | 18 | 55.56% | 420.60 | 472.40 | 0.89 | 2 |
| 404 | CZCE.SR601 | 3 | 0.8828% | 882.8 | 447.2 | 520.0 | 12 | 50.00% | 603.53 | 309.27 | 1.95 | 1 |
| 405 | DCE.c2601 | 2 | 0.2850% | 285.0 | 95.0 | 190.0 | 2 | 100.00% | 285.0 | 0.0 | 0.0 | 0 |
| 406 | DCE.c2601 | 3 | 0.0000% | 0.0 | 0.0 | 0.0 | 0 | 0.00% | 0.0 | 0.0 | 0.0 | 0 |
| 407 | DCE.cs2601 | 2 | 0.0000% | 0.0 | 0.0 | 0.0 | 0 | 0.00% | 0.0 | 0.0 | 0.0 | 0 |
| 408 | DCE.cs2601 | 3 | 0.0000% | 0.0 | 0.0 | 0.0 | 0 | 0.00% | 0.0 | 0.0 | 0.0 | 0 |
| 409 | SHFE.rb2601 | 2 | -3.3142% | -3314.18 | 1234.18 | 820.0 | 16 | 25.00% | 779.59 | 812.23 | 0.96 | 5 |
| 410 | SHFE.rb2601 | 3 | -1.8014% | -1801.41 | 981.41 | 650.0 | 14 | 42.86% | 561.73 | 871.65 | 0.64 | 2 |

## 6. 风险预算横向结果

| id | symbol | ticks | clearings | avg_raw_rr | min_raw_rr | max_stop_risk_pct | worst_net_pct | force_flat | time_exit | take_profit |
|----|--------|-------|-----------|------------|------------|-------------------|---------------|------------|-----------|-------------|
| 401 | DCE.m2601 | 2 | 6 | 1.368 | 0.692 | 1.950% | -0.514% | 1 | 3 | 2 |
| 402 | DCE.m2601 | 3 | 5 | 1.388 | 0.762 | 1.890% | -0.514% | 0 | 3 | 2 |
| 403 | CZCE.SR601 | 2 | 9 | 0.785 | 0.500 | 1.995% | -0.709% | 2 | 5 | 2 |
| 404 | CZCE.SR601 | 3 | 6 | 0.769 | 0.611 | 1.980% | -0.486% | 1 | 4 | 1 |
| 405 | DCE.c2601 | 2 | 1 | 1.714 | 1.714 | 1.995% | 0.285% | 1 | 0 | 0 |
| 406 | DCE.c2601 | 3 | 0 | - | - | - | - | 0 | 0 | 0 |
| 407 | DCE.cs2601 | 2 | 0 | - | - | - | - | 0 | 0 | 0 |
| 408 | DCE.cs2601 | 3 | 0 | - | - | - | - | 0 | 0 | 0 |
| 409 | SHFE.rb2601 | 2 | 8 | 1.007 | 0.769 | 1.980% | -1.623% | 0 | 4 | 2 |
| 410 | SHFE.rb2601 | 3 | 7 | 0.886 | 0.533 | 1.980% | -1.551% | 0 | 3 | 3 |

## 7. 成本安全边际

| id | symbol | ticks | clearings | total_cost | avg_net_win | cost / avg_net_win |
|----|--------|-------|-----------|------------|-------------|--------------------|
| 401 | DCE.m2601 | 2 | 6 | 1123.2 | 1535.7 | 0.731 |
| 402 | DCE.m2601 | 3 | 5 | 967.2 | 1741.6 | 0.555 |
| 403 | CZCE.SR601 | 2 | 9 | 1506.6 | 420.6 | 3.582 |
| 404 | CZCE.SR601 | 3 | 6 | 967.2 | 603.5 | 1.603 |
| 405 | DCE.c2601 | 2 | 1 | 285.0 | 285.0 | 1.000 |
| 409 | SHFE.rb2601 | 2 | 8 | 2054.2 | 779.6 | 2.635 |
| 410 | SHFE.rb2601 | 3 | 7 | 1631.4 | 561.7 | 2.904 |

该指标不是最终评估公式，只用于粗略观察成本相对平均盈利的压力。

## 8. 关键发现

### 8.1 DCE.m2601 仍是当前唯一主线适配品种

DCE.m2601 同时满足：

```text
正收益明显；
avg_raw_rr > 1.3；
worst_net_pct 仅约 -0.514%；
max_consecutive_loss = 1；
win_loss_ratio > 4；
成本 / 平均盈利显著低于 SR 和 rb。
```

2 ticks 与 3 ticks 的区别：

```text
2 ticks 收益更高、胜率更高；
3 ticks 交易更少、成本更低、盈亏比更高；
二者均未被账户风险预算否决。
```

阶段判断：

```text
DCE.m2601 继续保留为主线样本。
```

### 8.2 DCE.c2601 / DCE.cs2601 交易机会不足，不支持扩展为 DCE 农产品共性

DCE.c2601：

```text
2 ticks 仅 1 次清算；
3 ticks 0 成交；
```

DCE.cs2601：

```text
2 / 3 ticks 均 0 成交。
```

阶段中曾发现 0 成交组合误触发：

```text
检测到爆仓，从 daily_results 重新计算统计指标
```

后续已深入调试确认这是回测统计口径 bug，而不是策略真实爆仓：

```text
0 成交组合的 total_trade_count = 0；
total_net_pnl = 0；
end_balance = initial_capital；
daily_min_balance = initial_capital；
但旧爆仓检测仅检查 sharpe_ratio=0、max_drawdown=0、daily_results 非空，因此误判。
```

已在 `workspace/backtest/vnpy_backtest_engine.py` 中修复：只有当 `daily_results` 累计余额实际 `min_balance <= 0` 时，才触发爆仓统计覆盖。验证回测 `418` 显示：

```text
DCE.c2601 / 3 ticks：0 成交，status=success，end_balance=100000，未再误报爆仓。
```

策略侧结论不变：c / cs 成交少不是初始资本或仓位不足导致。调试期证据显示 `volume_reject = 0`，主要过滤来自：

```text
target_invalid；
min_target_reject。
```

即候选重新接受事件虽存在，但到 POC 空间不足或 POC 已在入场反方向。

阶段判断：

```text
c / cs 暂不证明 DCE 农产品共性；
由于 POC 空间和目标有效性不足，应暂缓，而不是判定为失败主线。
```

### 8.3 CZCE.SR601 仍可观察，但不适合作为当前主线优先品种

SR 2 ticks：

```text
胜率 55.56%，但 win_loss_ratio < 1；
cost / avg_net_win = 3.582；
force_flat 2 次，worst_net_pct -0.709%；
```

SR 3 ticks：

```text
收益和左尾改善；
win_loss_ratio 提升到 1.95；
max_consecutive_loss 降为 1；
但 cost / avg_net_win 仍有 1.603。
```

阶段判断：

```text
SR 不应使用 2 ticks 作为主候选；
若继续研究 SR，应优先测试 3 ticks 或归一化 reaccept 深度，且必须加强成本和 force_flat 压力测试。
```

### 8.4 SHFE.rb2601 继续作为负面对照

rb2601 两组均为负收益：

```text
2 ticks: -3.3142%，max_consecutive_loss = 5；
3 ticks: -1.8014%，win_loss_ratio = 0.64；
```

虽然账户风险预算仍能控制在约 2% 内，但实际收益结构很差：

```text
strict_failure_close 出现；
worst_net_pct 约 -1.55% ~ -1.62%；
cost / avg_net_win > 2.6；
```

阶段判断：

```text
rb2601 不适合作为 value_area_reacceptance 主线品种；
可保留为负面对照，不用它否定 DCE.m 的结构优势。
```

### 8.5 账户风险可执行不等于结构适配

本轮所有有清算的组合，max_stop_risk_pct 都在约 2% 内：

```text
DCE.m / SR / c / rb 均未因账户风险预算被直接否决。
```

但横向表现差异很大：

```text
DCE.m：风险预算可执行 + 原始盈亏比较好 + 成本安全边际较好；
SR：风险预算可执行，但成本安全边际薄；
rb：风险预算可执行，但方向 / 退出 / 成本结构失败；
c/cs：机会不足，无法评价。
```

因此，下一步不能只继续检查账户风险，而应进入 reaccept 深度归一化和品种状态解释。

## 9. 阶段决策

按品种给出当前状态：

| 品种 | 当前状态 | 原因 |
|------|----------|------|
| DCE.m2601 | 保留主线 | 收益、raw_rr、左尾、成本安全边际均最好 |
| CZCE.SR601 | 可观察 / 降低优先级 | 3 ticks 改善，但成本仍偏高，2 ticks 不适合作主候选 |
| DCE.c2601 | 暂缓 | 交易机会极少，无法评价 |
| DCE.cs2601 | 暂缓 | 0 成交，无法评价 |
| SHFE.rb2601 | 排除 / 负面对照 | 负收益、亏损簇和成本压力明显 |

## 10. 下一轮建议

下一轮进入实验线 C：reaccept 深度归一化。

但不建议立即全品种铺开。建议只保留：

```text
主线：DCE.m2601
观察：CZCE.SR601
负面对照：SHFE.rb2601
```

候选归一化方式：

```text
1. fixed ticks: 2 / 3 / 4 ticks；
2. value_area_width fraction: reaccept_depth / previous_value_area_width；
3. ATR fraction: reaccept_depth / ATR；
4. inside percentile: 收盘价进入价值区内侧分位。
```

下一轮重点不是找最优参数，而是回答：

```text
DCE.m 的 2 ticks 优势能否被“价值区宽度 / 波动 / 内侧分位”解释；
SR 的 3 ticks 改善是否只是 fixed tick 偶然，还是更深重新接受质量要求；
rb 失败是否来自 raw_rr、成本、左尾，还是价值区接受机制本身不成立。
```

## 11. 本轮结论

```text
品种适配存在明显分层。
```

更具体地说：

```text
value_area_reacceptance 不是可直接跨品种复用的结构；
当前只有 DCE.m2601 同时通过账户风险、原始盈亏比、左尾和成本安全边际的初筛；
CZCE.SR601 只能作为次级观察品种，且更偏 3 ticks 或归一化深度；
SHFE.rb2601 应排除为主线，只保留负面对照；
DCE.c2601 / DCE.cs2601 交易机会不足，暂不评价。
```
