# value_area_reacceptance R1：账户风险预算预筛实验报告

> 类型：Workbench / 策略实验报告
> 状态：第一轮完成
> 创建日期：2026-06-30
> 阶段规划：[value-area-reacceptance-stage-plan.md](./value-area-reacceptance-stage-plan.md)
> 长期框架：[strategy-research-framework.md](../../../../roadmap/strategy-research-framework.md)
> 当前研究入口：[strategy-current.md](../../../../research/strategy-current.md)
> 关联 issue：[trade-clearing-diagnostics-not-propagated.md](../../../../issues/trade-clearing-diagnostics-not-propagated.md)

## 1. 实验目的

本轮对应阶段规划中的实验线 A：账户风险预算预筛。

要回答的问题：

```text
value_area_reacceptance 在当前主线参数下，
strict failure 和 actual stop 经过合约乘数、最小手数、滑点、手续费、force_flat 后，
是否仍能把单次账户风险控制在 2%~3%？
```

本轮不是寻找最优参数，也不评价是否可实盘，只做第一层风险预算筛查。

## 2. 实验环境

实验分支：

```text
experiment/value-area-reacceptance-risk-budget
```

开分支 hash：

```text
6b672e4c298159f202d9c6a648c5557a4577b0e7
```

回测环境：

```text
env = backtest
engine = vnpy
mode = single
initial_capital = 100000
commission_rate = 0.0300%
slippage = 1.0
```

本轮回测 ID：

| backtest_id | run_id | symbol | min_reaccept_ticks | max_hold_bars |
|-------------|--------|--------|--------------------|---------------|
| 401 | 145 | DCE.m2601 | 2 | 12 |
| 402 | 146 | DCE.m2601 | 3 | 12 |
| 403 | 147 | CZCE.SR601 | 2 | 12 |
| 404 | 148 | CZCE.SR601 | 3 | 12 |

## 3. 参数设置

固定参数：

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
symbol ∈ [DCE.m2601, CZCE.SR601]
min_reaccept_ticks ∈ [2, 3]
```

注意：本轮沿用上一阶段主线候选，不测试 `min_reaccept_ticks=1`，因为本轮目标是风险预算预筛，而不是重复完整参数邻域。

## 4. 数据口径说明

本轮发现清算层诊断字段存在透传问题：

```text
trade_clearings.exit_reason 为空；
trade_clearings.diagnostics_json 为空；
```

已记录为 issue：

```text
docs/issues/trade-clearing-diagnostics-not-propagated.md
```

因此，本轮临时口径为：

```text
风险结构字段：从 backtest_trades.decision_payload_json 的 $.diagnostics.strategy.* 抽取；
退出原因：从 trade_clearings.close_reason 的 `|` 前缀解析；
PnL / commission / slippage / MAE / MFE：使用 trade_clearings 字段。
```

本轮结论可用于风险预算预筛，但在清算层诊断透传修复前，不应把自动报告中的 clearing diagnostics 作为唯一依据。

## 5. 汇总结果

### 5.1 回测绩效摘要

| backtest_id | symbol | min_reaccept_ticks | total_return | net_pnl | total_commission | total_slippage | trades | win_rate | avg_win | avg_loss | win_loss_ratio | max_consecutive_loss |
|-------------|--------|--------------------|--------------|---------|------------------|----------------|--------|----------|---------|----------|----------------|----------------------|
| 401 | DCE.m2601 | 2 | 3.5168% | 3516.8 | 403.2 | 720.0 | 12 | 50.00% | 1535.73 | 363.47 | 4.23 | 1 |
| 402 | DCE.m2601 | 3 | 2.3928% | 2392.8 | 347.2 | 620.0 | 10 | 40.00% | 1741.60 | 363.47 | 4.79 | 1 |
| 403 | CZCE.SR601 | 2 | 0.2134% | 213.4 | 696.6 | 810.0 | 18 | 55.56% | 420.60 | 472.40 | 0.89 | 2 |
| 404 | CZCE.SR601 | 3 | 0.8828% | 882.8 | 447.2 | 520.0 | 12 | 50.00% | 603.53 | 309.27 | 1.95 | 1 |

初步观察：

```text
DCE.m2601 的 2 / 3 ticks 均保持正收益，且盈亏比很高；
CZCE.SR601 的 2 ticks 胜率较高但盈亏比不足，3 ticks 明显改善盈亏比和左尾；
该结果延续上一阶段“DCE.m 更适合 2 ticks，SR 可能更适合 3 ticks”的机制差异。
```

### 5.2 账户风险预算摘要

| backtest_id | symbol | min_reaccept_ticks | clearings | avg_price_raw_rr | min_price_raw_rr | max_strict_risk | max_actual_stop_risk | max_stop_risk_costed | max_stop_risk_pct | worst_net_pnl | worst_net_pct | force_flat_n | time_exit_n | take_profit_n |
|-------------|--------|--------------------|-----------|------------------|------------------|-----------------|----------------------|----------------------|-------------------|---------------|---------------|--------------|-------------|---------------|
| 401 | DCE.m2601 | 2 | 6 | 1.368 | 0.692 | 1300.0 | 1950.0 | 2108.4 | 1.950% | -513.6 | -0.514% | 1 | 3 | 2 |
| 402 | DCE.m2601 | 3 | 5 | 1.388 | 0.762 | 1260.0 | 1890.0 | 2108.4 | 1.890% | -513.6 | -0.514% | 0 | 3 | 2 |
| 403 | CZCE.SR601 | 2 | 9 | 0.785 | 0.500 | 1330.0 | 1995.0 | 2184.6 | 1.995% | -708.8 | -0.709% | 2 | 5 | 2 |
| 404 | CZCE.SR601 | 3 | 6 | 0.769 | 0.611 | 1320.0 | 1980.0 | 2184.6 | 1.980% | -486.0 | -0.486% | 1 | 4 | 1 |

字段说明：

```text
max_strict_risk = strict_distance × volume × contract_multiplier；
max_actual_stop_risk = actual_stop_distance × volume × contract_multiplier；
max_stop_risk_costed = actual_stop_risk + commission + slippage_cost；
max_stop_risk_pct = max_actual_stop_risk / 100000；
worst_net_pct = worst_net_pnl / 100000。
```

## 6. 关键发现

### 6.1 单次账户风险预算初步可执行

四个组合的最大 actual stop 风险均低于 2%：

```text
DCE.m2601 / 2 ticks: 1.950%
DCE.m2601 / 3 ticks: 1.890%
CZCE.SR601 / 2 ticks: 1.995%
CZCE.SR601 / 3 ticks: 1.980%
```

若把手续费和滑点加入 worst-case stop 风险，最大值约为：

```text
DCE.m2601: 2108.4，约 2.1084%
CZCE.SR601: 2184.6，约 2.1846%
```

这说明：

```text
在当前 100000 资金、合约乘数 10、滑点 1.0、stop_widen_multiplier=1.5 下，
value_area_reacceptance 的实际止损风险大体贴近 2% 风险预算，
但计入费用和滑点后已经略高于 2%，仍低于 3%。
```

因此，本轮不构成“风险预算不可执行”的否决。

### 6.2 最小手数不是当前主问题

本轮实际持仓量为 6~14 手，说明策略在风险预算和保证金约束下可以按风险距离缩放仓位。

从最小手数角度看，单手 tick value 约为：

```text
合约乘数 10 × tick 1 = 10 元 / tick / 手
```

即使 strict_distance / actual_stop_distance 达到十几到三十 ticks，单手风险也远低于 2% 账户风险。因此当前不是“最小手数导致无法控制风险”的场景。

### 6.3 DCE.m2601 的账户风险结构明显优于 SR

DCE.m2601 两组：

```text
avg_price_raw_rr ≈ 1.37~1.39；
min_price_raw_rr > 0.69；
worst_net_pct = -0.514%；
max_consecutive_loss = 1；
win_loss_ratio > 4。
```

SR 两组：

```text
avg_price_raw_rr ≈ 0.77~0.79；
2 ticks 的 min_price_raw_rr 触及 0.5 下限；
2 ticks worst_net_pct = -0.709%，max_consecutive_loss = 2；
3 ticks 后 worst_net_pct 改善到 -0.486%，win_loss_ratio 提升到 1.95。
```

这说明当前差异不是单纯胜率差异，而是：

```text
DCE.m 的 POC 空间 / strict failure 距离更容易形成较高原始盈亏比；
SR 的方向可能有效，但 POC 空间和成本后盈亏比更紧，2 ticks 更像高胜率低赔率结构。
```

### 6.4 force_flat 没有造成超预算亏损，但仍需继续观察

本轮 force_flat：

```text
DCE.m2601 / 2 ticks: 1 次，且为盈利退出；
DCE.m2601 / 3 ticks: 0 次；
CZCE.SR601 / 2 ticks: 2 次，其中 1 次亏损 -708.8；
CZCE.SR601 / 3 ticks: 1 次，且为盈利退出。
```

本轮未观察到 force_flat 导致超出 2%~3% 的账户风险，但 SR 2 ticks 的最大净亏损来自 force_flat，说明后续仍需把 force_flat 作为左尾来源继续分桶。

### 6.5 费用和滑点对 SR 更敏感

SR 2 ticks：

```text
total_net_pnl = 213.4；
total_commission = 696.6；
total_slippage = 810.0；
```

这意味着 SR 2 ticks 的毛收益被成本显著侵蚀，成本安全边际很薄。

SR 3 ticks 成本压力有所下降：

```text
total_net_pnl = 882.8；
total_commission = 447.2；
total_slippage = 520.0；
```

但仍不如 DCE.m 稳定。

## 7. 阶段判断

本轮对实验线 A 的回答：

```text
value_area_reacceptance 在 DCE.m2601 与 CZCE.SR601、min_reaccept_ticks=2~3、max_hold_bars=12 下，
单次账户风险预算初步可执行；
actual stop 风险基本低于 2%，计入成本后约 2.1%~2.18%，仍处于 2%~3% 预算区间；
因此可以进入下一轮品种适配与机制差异诊断。
```

但必须附加约束：

```text
DCE.m2601 优先级高于 CZCE.SR601；
CZCE.SR601 不宜继续用 2 ticks 作为主候选，应优先看 3 ticks 或归一化 reaccept 深度；
SR 的成本 / 平均盈利和 force_flat 左尾需要单独压力测试；
清算层 diagnostics_json / exit_reason 问题修复前，自动化诊断报告不能直接作为唯一依据。
```

## 8. 下一轮建议

下一轮进入实验线 B：品种适配诊断。

建议不要大范围铺开，而是先做小范围扩展：

```text
DCE.m2601
DCE.c2601
DCE.cs2601
CZCE.SR601
SHFE.rb2601
```

目的：

```text
验证 DCE.m 的优势是否来自豆粕自身，还是 DCE 农产品价值区机制；
验证 SR 的问题是否是 CZCE/SR 特有，还是高成本低空间结构；
保留 rb2601 作为上一阶段质量差的负面对照，不用它否定主线。
```

第二轮核心观察字段：

```text
event_count；
avg_price_raw_rr；
min_price_raw_rr；
max_actual_stop_risk_pct；
worst_net_pct；
cost / avg_win；
exit reason 分布；
force_flat 亏损占比；
POC take_profit 兑现次数。
```

## 9. 本轮结论

```text
通过账户风险预算预筛，但不是全面通过。
```

更准确表述：

```text
当前主线候选在 100000 账户下具备风险预算可执行性，
没有因为合约乘数、最小手数、滑点或实际止损距离被第一层否决；
但 SR 成本安全边际偏薄，清算诊断字段存在 issue，
下一轮应优先做品种适配与机制差异诊断，而不是直接进入参数优化。
```
