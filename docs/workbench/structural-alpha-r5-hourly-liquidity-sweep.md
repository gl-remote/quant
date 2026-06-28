# structural-alpha-r5：多小时等高 / 等低流动性池扫单重新接受

类型：Workbench / 策略实验记录  
状态：执行中  
创建日期：2026-06-28  
最后更新：2026-06-28

## 来源规划

- 来源规划：[strategy-short-term-plan.md](../roadmap/strategy-short-term-plan.md)
- 研究框架：[strategy-research-framework.md](../roadmap/strategy-research-framework.md)

## 开发信息

- 开发分支：experiment/structural-alpha-r5-hourly-liquidity-sweep
- 开分支 hash：04b8573
- 实现提交 hash：待回填

## 核心问题

用 1h 结构定义共识流动性边界、5m 执行扫破后重新接受，是否比 IB/前日边界更好平衡样本、失败距离、盈利上界、成本安全边际。

## 明确排除

- IB 已做未通过。
- POC/VAH/VAL 由其他分支研究。
- 成交量不做主边界/硬过滤。

## 固定参数第一轮计划

- 品种：DCE.m2601
- 执行周期：5m
- 结构周期：1h
- lookback_hours：24 / 48
- touch_tolerance_ticks：4
- min_touches：2
- min_breakout_ticks：2 / 4
- target：r / band_mid / opposite_band
- 日内约束：last_entry 14:00，force_flat 14:50

## 工程实现

| 项目 | 状态 | 说明 |
| --- | --- | --- |
| 策略 | 已完成 | `workspace/strategies/hourly_liquidity_sweep_strategy.py` |
| 测试 | 已完成 | `workspace/tests/strategies/test_hourly_liquidity_sweep_strategy.py` |
| 数据需求 | 已完成 | `5m` 执行周期 + `1h` 结构周期 |
| 结构边界 | 已完成 | 过去 N 小时 1h high / low 贪心聚类，生成等高 / 等低 band |
| 入场 | 已完成 | 5m 扫破 band 后重新回到 band_inner / band_mid |
| 退出 | 已完成 | stop loss、strict failure close、take profit、force flat、time exit |

验证：

```text
ruff check workspace/strategies/hourly_liquidity_sweep_strategy.py workspace/tests/strategies/test_hourly_liquidity_sweep_strategy.py
ruff format workspace/strategies/hourly_liquidity_sweep_strategy.py workspace/tests/strategies/test_hourly_liquidity_sweep_strategy.py
ruff format --check workspace/strategies/hourly_liquidity_sweep_strategy.py workspace/tests/strategies/test_hourly_liquidity_sweep_strategy.py
uv run mypy workspace/strategies/hourly_liquidity_sweep_strategy.py workspace/tests/strategies/test_hourly_liquidity_sweep_strategy.py
uv run pytest workspace/tests/strategies/test_hourly_liquidity_sweep_strategy.py --tb=short
```

结果：`8 passed`。

## 第一轮固定参数结果

### DCE.m2601 参数对照

统一约束：

```text
kline_period = 5m
structure_period = 1h
touch_tolerance_ticks = 4
min_touches = 2
last_entry_time = 14:00
force_flat_time = 14:50
max_trades_per_day = 1
```

| id | 参数摘要 | trades | win rate | net pnl | max drawdown | 观察 |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| `364` | 24h / breakout 2 / band_inner / 1R | 78 | 34.29% | -14,699 | -14,699 | 基础组明显失败 |
| `365` | 24h / breakout 4 / band_inner / 1R | 64 | 38.71% | -12,810 左右 | -13,738 | 减少交易但仍明显亏损 |
| `366` | 24h / breakout 2 / band_mid target | 60 | 54.17% | -10,220 左右 | -10,284 | 胜率提高，但盈利空间太小 |
| `367` | 48h / breakout 2 / band_inner / 1R | 52 | 36.00% | -15,110 | -15,110 | 更长 lookback 没有改善 |
| `368` | 24h / breakout 4 / band_mid reaccept / 2R | 56 | 37.04% | -8,840 左右 | -9,858 | DCE.m2601 最佳，但仍远差于通过线 |
| `369` | 48h / breakout 4 / band_mid reaccept / 2R | 34 | 20.00% | -11,940 左右 | -11,938 | 更长 lookback + 严格重接受恶化 |
| `370` | 24h / breakout 4 / band_mid reaccept / opposite_band | 54 | 29.63% | -10,210 左右 | -11,234 | 对侧 band 目标未改善 |
| `371` | 48h / min_touches 3 / breakout 4 / band_mid / 2R | 34 | 20.00% | -11,940 左右 | -11,938 | 增加触碰次数导致样本减少但质量未提升 |

DCE.m2601 判断：

```text
小时级等高 / 等低边界可以生成足够交易，
但扫单后重新接受质量明显不足。
严格化边界、提高 R、要求 band_mid 重接受都只能减少交易，不能改善期望。
```

### 跨品种验证

采用 DCE.m2601 中相对最好的结构：

```text
lookback_hours = 24
min_breakout_ticks = 4
reaccept_mode = band_mid
take_profit_mode = r
take_profit_r = 2.0
max_hold_bars = 12
```

| id | symbol | trades | win rate | net pnl | max drawdown | 观察 |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| `372` | CZCE.SR601 | 70 | 41.94% | -5,920 左右 | -8,397 | 仍明显成本后为负 |
| `373` | DCE.c2601 | 38 | 66.67% | -241.50 | -1,890 | 接近打平，但仍负，且回撤/成本不小 |
| `374` | SHFE.rb2601 | 68 | 42.42% | -14,140 左右 | -15,224 | 明显失败 |

`DCE.c2601` 明细显示：

```text
总净盈亏 -241.50
总手续费 1,691.50
总滑点成本 3,380.00
开平 8 组交易，胜率 66.67%
最大回撤 -1,890.39
```

这说明该结构在 c 上有一定毛收益，但仍主要被成本和回撤吞噬，不构成跨品种通过证据。

## 波动率归一化补充诊断

用户追问是否结合波动率后，补充实现了小时 ATR 归一化诊断和可选过滤。新增诊断字段：

```text
hourly_atr
sweep_depth_atr
strict_distance_atr
target_distance_atr
```

新增过滤参数：

```text
volatility_filter_enabled
atr_lookback
min_sweep_atr
max_strict_distance_atr
min_target_atr
```

语义：

```text
sweep_depth / hourly_atr >= min_sweep_atr
strict_distance / hourly_atr <= max_strict_distance_atr
target_distance / hourly_atr >= min_target_atr
```

### DCE.m2601 ATR 过滤对照

基础结构沿用 DCE.m2601 相对最佳组：

```text
lookback_hours = 24
min_breakout_ticks = 4
reaccept_mode = band_mid
take_profit_mode = r
take_profit_r = 2.0
max_hold_bars = 12
atr_lookback = 14
```

| id | ATR 过滤摘要 | trades | win rate | net pnl | max drawdown | 观察 |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| `368` | 无 ATR 过滤 | 56 | 37.04% | -8,840 左右 | -9,858 | 原相对最佳组 |
| `375` | min_sweep 0.2 / max_strict 1.0 / min_target 0.4 | 44 | 36.36% | -7,100 左右 | -8,187 | 减亏但仍明显失败 |
| `376` | min_sweep 0.3 / max_strict 1.0 / min_target 0.4 | 42 | 38.10% | -6,750 左右 | -7,830 | 略改善，仍不达标 |
| `377` | min_sweep 0.2 / max_strict 0.8 / min_target 0.4 | 38 | 31.58% | -5,810 左右 | -7,035 | 本轮 DCE 最好，但仍显著为负 |
| `378` | min_sweep 0.2 / max_strict 1.0 / min_target 0.6 | 44 | 36.36% | -7,240 左右 | -8,327 | 提高目标 ATR 要求无明显改善 |

判断：

```text
ATR 归一化过滤能减少一部分亏损和交易数，
但没有改变结构方向：DCE.m2601 最佳仍约 -5.81%，回撤仍约 -7.04%。
```

### ATR 过滤跨品种验证

采用 DCE.m2601 最佳 ATR 过滤：

```text
min_sweep_atr = 0.2
max_strict_distance_atr = 0.8
min_target_atr = 0.4
```

| id | symbol | trades | win rate | net pnl | max drawdown | 观察 |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| `379` | DCE.c2601 | 10 | 20.00% | -2,070 左右 | -2,068 | 原接近打平品种被 ATR 过滤明显劣化 |
| `380` | CZCE.SR601 | 32 | 35.71% | -5,880 左右 | -6,341 | 与未过滤相比交易减少，但仍明显为负 |
| `381` | SHFE.rb2601 | 38 | 31.58% | -11,920 左右 | -12,110 | 仍明显失败 |

波动率补充结论：

```text
波动率归一化能解释一部分“固定 tick 扫破太廉价”的问题，
但不能把小时级等高/等低扫单重新接受变成可交易结构。
```

失败层级更新：

1. 固定 tick 口径确实偏粗，ATR 过滤后 DCE.m2601 有减亏；
2. 但减亏来自减少交易和控制过大验证成本，不是接受/拒绝质量显著提升；
3. 跨品种不稳定，尤其 DCE.c2601 从接近打平变为明显亏损；
4. 因此本方向不建议继续做 ATR 阈值微调。

## 临时结论

当前判断：

```text
多小时等高 / 等低流动性池扫单后的重新接受，
作为独立结构未通过第一轮固定参数诊断。
```

失败层级：

1. **边界可定义，但质量不足**：1h 等高/等低 band 能客观生成，也能产生交易；问题不是没有信号。
2. **扫单重新接受后的胜率不足**：DCE.m2601 多数组胜率低于 40%，严格重接受后也没有稳定改善。
3. **盈利上界没有有效扩大**：2R 和 opposite_band 都未能带来足够毛收益安全边际。
4. **更长小时 lookback 没改善**：48h 比 24h 更容易样本下降和胜率恶化。
5. **跨品种不稳定**：只有 DCE.c2601 接近打平，但 SR / rb 明显失败。

后续不建议继续围绕当前“1h 等高/等低 + 5m 重新接受”做 tick 阈值或 ATR 阈值微调。

若保留这个方向的信息，建议只作为后续研究的诊断字段：

```text
价格是否在小时级重复触碰带附近发生扫单
→ 用于解释其他主边界附近的事件质量
→ 不作为独立入场结构
```
