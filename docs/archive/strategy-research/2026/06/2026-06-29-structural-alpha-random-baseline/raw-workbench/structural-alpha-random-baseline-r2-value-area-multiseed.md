# structural-alpha-random-baseline-r2-value-area-multiseed

> 类型：Workbench / 随机对照实验  
> 状态：初步完成，需复核 random-direction 成交配对警告  
> 日期：2026-06-28  
> 对应补充计划：[结构入口随机基准对照计划](../roadmap/strategy-random-entry-baseline-plan.md)  
> 前序实验：[r1 value area random baseline pilot](./structural-alpha-random-baseline-r1-value-area.md)

## 1. 本轮问题

r1 单 seed 只能说明价值区重新接受结构没有被随机对照立即证伪，但不能判断结果是否稳定。

本轮问题：

```text
在 DCE.m2601 上，前日 VAH / VAL 重新接受结构，
相对 50 seeds 的匹配随机基准，
是否表现出稳定的方向信息、收益分布优势或风险分布优势？
```

重点不是判断是否已经可交易，而是判断：

```text
结构入口是否比随机开仓更稳定、更收敛？
```

## 2. 实验对象

### 2.1 原结构

策略：`value_area_reacceptance`

固定参数：

```text
symbol = DCE.m2601
kline_period = 5m
profile_mode = close
value_area_ratio = 0.7
min_breakout_ticks = 4
failure_buffer_ticks = 1
take_profit_mode = poc
max_hold_bars = 12
stop_widen_multiplier = 1.5
strict_close_exit = true
max_trades_per_day = 1
min_target_ticks = 8
min_price_raw_rr = 0.5
```

结构含义：

```text
昨日 VAL 下破后重新接受 → 做多回 POC
昨日 VAH 上破后重新拒绝 → 做空回 POC
```

### 2.2 随机基准

策略：`value_area_random_baseline`

本轮使用两类随机基准：

| 口径 | 含义 | 检验问题 |
|------|------|----------|
| `direction_matched / same` | 保留重新接受事件和原方向，只随机化失败边界 / 风险空间 | 原结构入场与 strict failure 是否优于同事件同方向随机风险空间 |
| `direction_matched / random` | 保留重新接受事件，但随机方向 | 原结构方向假设是否优于随机方向 |

每类基准跑 50 seeds，`workers=4` 并发执行。

输出文件：

```text
project_data/research/random_baseline/value_area_random_baseline_r2_20260628_220756.csv
project_data/research/random_baseline/value_area_random_baseline_r2_20260628_220756.json
```

## 3. 实现备注

本轮新增并发 runner：

```text
scripts/tools/run_value_area_random_baseline.py
```

实现方式：

```text
ProcessPoolExecutor
→ 每个 seed 独立调用 VnpyBacktestEngine.run(..., batch_mode=True)
→ batch_mode 跳过数据库写入
→ 汇总 CSV / JSON 写入 project_data/research/random_baseline
```

这样避免 100 次随机回测直接写 SQLite 造成锁竞争，也避免污染回测报告库。

本轮试跑时发现 `same direction` 初版随机风险空间没有随 seed 变化，随后修正为随机扩展 `breakout_extreme` 距离；本报告只采用修正后的 50 seeds 结果。

## 4. 结果汇总

### 4.1 原结构

| 指标 | 数值 |
|------|------:|
| total_return | `+1.1482%` |
| total_net_pnl | `+1,148.22` |
| max_drawdown | `-1,850.74` |
| sharpe_ratio | `0.5925` |
| win_rate | `44.44%` |
| win_trades / loss_trades | `4 / 5` |
| total_trades | `20` |
| avg_win | `1,580.00` |
| avg_loss | `636.00` |
| win_loss_ratio | `2.4843` |
| total_commission | `711.78` |
| total_slippage | `1,280.00` |

### 4.2 同事件同方向随机风险空间：50 seeds

| 指标 | 随机分布 | 原结构相对位置 |
|------|----------:|----------------:|
| return_mean | `+0.8632%` | - |
| return_median | `+1.0072%` | - |
| return_p25 | `+0.2900%` | - |
| return_p75 | `+1.5615%` | - |
| net_pnl_mean | `+863.16` | - |
| net_pnl_median | `+1,007.15` | - |
| structure_net_pnl_percentile | - | `56.00%` |
| max_drawdown_mean | `-1,844.48` | - |
| max_drawdown_median | `-1,805.41` | - |
| structure_drawdown_percentile | - | `48.00%` |
| win_rate_mean | `42.91%` | - |
| win_rate_median | `45.45%` | - |
| structure_win_rate_edge_mean | - | `+1.54` 个百分点 |
| structure_win_rate_edge_median | - | `-1.01` 个百分点 |
| trade_count_mean | `24.00` | - |

解读：

```text
原结构相对同事件同方向随机风险空间，
净收益只在 56% 分位附近，
回撤在 48% 分位附近，
胜率优势不稳定。
```

这说明：

```text
当前 strict failure / 入场风险空间，
没有显著优于同事件同方向随机风险空间。
```

### 4.3 同事件随机方向：50 seeds

| 指标 | 随机分布 | 原结构相对位置 |
|------|----------:|----------------:|
| return_mean | `-2.6645%` | - |
| return_median | `-3.1088%` | - |
| return_p25 | `-4.0920%` | - |
| return_p75 | `-1.0434%` | - |
| net_pnl_mean | `-2,664.52` | - |
| net_pnl_median | `-3,108.83` | - |
| structure_net_pnl_percentile | - | `100.00%` |
| max_drawdown_mean | `-3,987.71` | - |
| max_drawdown_median | `-4,026.24` | - |
| structure_drawdown_percentile | - | `98.00%` |
| win_rate_mean | `34.14%` | - |
| win_rate_median | `35.71%` | - |
| structure_win_rate_edge_mean | - | `+10.30` 个百分点 |
| structure_win_rate_edge_median | - | `+8.73` 个百分点 |
| trade_count_mean | `29.72` | - |

解读：

```text
随机方向自然胜率约 34%~36%，
符合“涨 / 跌 / 中间波动扫描止损”三状态下随机方向胜率低于 50% 的判断。
```

原结构相对随机方向基准：

```text
胜率高出约 8.7~10.3 个百分点，
净收益与回撤均显著优于随机方向分布。
```

这说明：

```text
VAH 上破失败做空、VAL 下破失败做多，
这个方向假设存在明显信息量。
```

## 5. 口径风险

本轮 `random-direction` 中出现多次：

```text
平仓有余量未配对
```

该警告主要出现在随机方向样本中，原因可能是随机方向导致部分事件下 `target_price` 与交易方向组合异常，触发了 vnpy 成交方向与 FIFO 配对口径不一致。

因此本轮对 `random-direction` 的结论采用保守表述：

```text
方向信息优势很强，但 random-direction 基准的成交配对口径需要单独复核。
```

不过该警告不影响 `same-direction` 主要结论，因为 `same-direction` 的方向与原结构一致，且没有观察到同类大规模配对异常。

## 6. 本轮结论

### 6.1 结构没有失去意义

如果结构入口完全没有信息量，应看到：

```text
原结构 ≈ 同事件随机方向
```

但本轮看到：

```text
原结构胜率 44.44%
随机方向胜率均值 34.14%
随机方向胜率中位数 35.71%
```

方向胜率优势明显超过 `4` 个百分点阈值。

因此：

```text
价值区重新接受结构没有失去意义；
其方向假设有继续研究价值。
```

### 6.2 但当前入场 / 失败边界没有显著优势

同事件同方向随机风险空间结果显示：

```text
原结构净收益只在 56% 分位；
回撤只在 48% 分位；
胜率相对同方向随机没有稳定优势。
```

因此：

```text
当前“重新接受 K 收盘 + 假突破极值 strict failure”的具体风险空间塑形，
还没有被证明优于同事件同方向随机。
```

### 6.3 阶段判断

本轮应把价值区线索拆成两层：

| 层级 | 判断 |
|------|------|
| 方向假设 | 有明显信息量，继续保留 |
| 入场 / strict failure 风险空间 | 尚未证明有效，需要重新塑形 |

更准确的结论不是：

```text
价值区入口有效
```

而是：

```text
价值区重新接受的方向选择有效；
但当前失败边界、入场价格和账户风险结构仍未完成塑形。
```

## 7. 下一轮建议

不要继续扩大 seed，而是先处理两个问题：

1. 复核 `random-direction` 成交配对警告，确认随机方向基准统计口径可靠；
2. 在同事件同方向前提下，重新设计失败边界 / 入场风险空间，例如：
   - 不用假突破极值，改用重新接受 K 的高低点；
   - strict failure 距离按 ATR / entry bar range 分桶；
   - 只保留 strict distance 与 target distance 同时落入稳定区间的样本；
   - 输出 MAE / MFE 和 strict failure 快速再触及率。

只有当新的风险空间定义显著优于同事件同方向随机分布时，才进入账户风险预算和尾部风险补证。
