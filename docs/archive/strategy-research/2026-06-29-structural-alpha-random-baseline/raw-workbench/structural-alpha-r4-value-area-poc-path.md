# structural-alpha-r4：价值区 POC 空间后的路径质量验证

> 类型：Workbench / 策略实验记录  
> 状态：执行中  
> 创建日期：2026-06-28  
> 最后更新：2026-06-28  
> 来源规划：[策略短期研究计划：结构型 Alpha 验证](../roadmap/strategy-short-term-plan.md)  
> 前序实验：[structural-alpha-r3：前日价值区边缘接受 / 拒绝](./structural-alpha-r3-value-area-edge-reacceptance.md)  
> 开发分支：`experiment/structural-alpha-r3-value-area-edge`  
> 开分支 hash：`9c619c4`  
> 实现提交 hash：待补

## 1. 核心问题

r3 已经把有效线索从“VAH / VAL 重新接受”收敛到：

```text
target_distance >= 8 ticks
且 price_raw_rr >= 0.5
```

该子样本在 `DCE.m2601` 和 `CZCE.SR601` 上明显改善，但 `SHFE.rb2601` 仍然失败。

r4 的问题是：

```text
在 POC 空间和价格原始盈亏比足够的样本里，
入场后的早期路径质量是否能进一步过滤 time_exit 和 strict_failure？
```

## 2. 最小结构定义

沿用 r3 策略 `value_area_reacceptance`，固定基础结构：

```text
5m
close profile
value_area_ratio = 0.7
min_breakout_ticks = 4
failure_buffer_ticks = 1
take_profit_mode = poc
max_hold_bars = 12
stop_widen_multiplier = 1.5
min_target_ticks = 8
min_price_raw_rr = 0.5
max_trades_per_day = 1
```

新增路径质量参数：

| 参数 | 含义 |
| --- | --- |
| `path_check_bars` | 入场后第 N 根 K 开始检查是否已有足够向 POC 推进 |
| `min_path_progress_ticks` | 入场后向 POC 方向的最大有利推进必须至少达到 N ticks |

路径推进定义：

```text
多头：max(high - entry_price)
空头：max(entry_price - low)
```

如果到检查窗口仍未达到要求，则以 `path_failure` 早退。

## 3. 验证

```text
ruff check workspace/strategies/value_area_reacceptance_strategy.py workspace/tests/strategies/test_value_area_reacceptance_strategy.py
ruff format --check workspace/strategies/value_area_reacceptance_strategy.py workspace/tests/strategies/test_value_area_reacceptance_strategy.py
uv run mypy workspace/strategies/value_area_reacceptance_strategy.py
uv run pytest workspace/tests/strategies/test_value_area_reacceptance_strategy.py --tb=short
```

结果：14 条局部单元测试通过。

## 4. 固定对照结果

### 4.1 无路径早退基准

| id | symbol | trades | win rate | avg win | avg loss | net pnl | max drawdown | exit reason 观察 |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `320` | `DCE.m2601` | 20 | 44.44% | 1,580.00 | 636.00 | +1,148.22 | -1,850.74 | POC 命中 3 次贡献 +5,320；time_exit 5 次拖累 -1,750；strict failure 1 次 -1,430 |
| `321` | `CZCE.SR601` | 22 | 54.55% | 661.67 | 266.00 | +726.75 | -1,103.46 | POC 命中 3 次贡献 +2,370；time_exit 6 次接近持平 |
| `322` | `SHFE.rb2601` | 22 | 45.45% | 590.00 | 795.00 | -4,946.94 | -6,781.51 | POC 命中也有效，但 strict failure 2 次 -2,600，time_exit 6 次 -910 |

### 4.2 路径早退对照

| id | 参数 | symbol | trades | win rate | avg win | avg loss | net pnl | max drawdown | 观察 |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `308` | `path_check_bars=1,min_path_progress_ticks=1` | `DCE.m2601` | 20 | 44.44% | 1,580.00 | 496.00 | +1,848.29 | -1,850.74 | 主品种改善，替换部分 time_exit 为小亏 path_failure |
| `309` | 同上 | `CZCE.SR601` | 22 | 50.00% | 594.00 | 354.00 | -713.36 | -1,543.50 | SR 由正转负，路径早退伤害样本 |
| `310` | 同上 | `SHFE.rb2601` | 22 | 36.36% | 705.00 | 532.86 | -4,037.16 | -5,871.73 | rb 减亏但仍明显失败 |
| `311` | `path_check_bars=1,min_path_progress_ticks=2` | `DCE.m2601` | 20 | 44.44% | 1,580.00 | 496.00 | +1,848.29 | -1,850.74 | 与 1 tick 推进等价 |
| `312` | 同上 | `CZCE.SR601` | 22 | 50.00% | 594.00 | 322.00 | -553.37 | -1,383.51 | 仍由正转负 |
| `313` | 同上 | `SHFE.rb2601` | 22 | 36.36% | 705.00 | 532.86 | -4,037.16 | -5,871.73 | 仍负 |
| `314` | `path_check_bars=2,min_path_progress_ticks=1` | `DCE.m2601` | 20 | 44.44% | 1,580.00 | 636.00 | +1,148.22 | -1,850.74 | 与无路径早退接近 |
| `315` | 同上 | `CZCE.SR601` | 22 | 45.45% | 594.00 | 308.33 | -793.37 | -1,583.06 | 失败 |
| `316` | 同上 | `SHFE.rb2601` | 22 | 40.00% | 705.00 | 643.33 | -4,167.13 | -6,001.70 | 仍负 |
| `317` | `path_check_bars=2,min_path_progress_ticks=2` | `DCE.m2601` | 20 | 40.00% | 1,580.00 | 576.67 | +868.20 | -1,990.75 | 主品种变差 |
| `318` | 同上 | `CZCE.SR601` | 22 | 45.45% | 594.00 | 268.33 | -553.38 | -1,343.08 | 仍负 |
| `319` | 同上 | `SHFE.rb2601` | 22 | 40.00% | 705.00 | 643.33 | -4,167.13 | -6,001.70 | 仍负 |

### 4.3 exit reason 观察

最好的主品种路径早退组 `308`：

| reason | 次数 | gross pnl | commission | 观察 |
| --- | ---: | ---: | ---: | --- |
| `take_profit` | 3 | +5,320 | 115.28 | POC 命中仍是主要收益来源 |
| `time_exit` | 4 | -770 | 136.10 | 较基准少 1 笔、亏损减小 |
| `path_failure` | 1 | -280 | 38.91 | 能把一部分差路径转成小亏 |
| `strict_failure_close` | 1 | -1,430 | 37.04 | 严格失败仍未解决 |

但同一参数在 `CZCE.SR601` 上：

| reason | 次数 | gross pnl | commission | 观察 |
| --- | ---: | ---: | ---: | --- |
| `take_profit` | 2 | +1,370 | 89.60 | POC 命中少于基准 |
| `path_failure` | 2 | -660 | 90.04 | 早退直接制造亏损 |
| `time_exit` | 5 | +250 | 193.31 | SR 的 time_exit 并不坏，早退反而伤害结构 |

## 5. 结论

### 5.1 第一阶段结论

r4 当前最小路径早退 **未通过**。

原因：

```text
早期向 POC 推进不足，并不是通用品种上的坏样本判据。
```

它在 `DCE.m2601` 上能把部分 `time_exit` 变成小亏，净值从 `+1,148.22` 提升到 `+1,848.29`；但在 `CZCE.SR601` 上会把原本可接受甚至接近持平的路径提前砍掉，使净值从 `+726.75` 变成负值。`SHFE.rb2601` 虽然减亏，但仍无法转正。

因此当前结构判断为：

```text
POC 空间 + price_raw_rr 是有效前置过滤；
简单的“入场后 1~2 根 K 必须推进 N ticks”不是有效路径质量过滤。
```

后续若继续 r4，不应再调 `path_check_bars` / `min_path_progress_ticks`，而应转向：

```text
按品种拆分路径形态；
比较 POC 命中前的 MAE / MFE 比例；
分析 time_exit 为正的样本是否需要保留，而不是一刀切早退；
单独解释 rb 的 strict failure 质量问题。
```

### 5.2 第二阶段：5m 下拉长路径窗口 + 波动率 / 品种分组

根据第一阶段结果，路径检查不升到更高周期，仍固定 `5m`，但把检查窗口从 1~2 根 bar 拉长到：

```text
path_check_bars = 3 / 4 / 6
```

对应：

```text
15 分钟 / 20 分钟 / 30 分钟
```

同时加入入场 bar 波动率分桶：

```text
volatility_ratio = entry_bar_range / strict_distance
```

分桶：

| bucket | 含义 |
| --- | --- |
| `lt0_5` | 入场 bar 波动小于严格失败距离 0.5 倍 |
| `0_5_1` | 0.5~1.0 倍 |
| `1_1_5` | 1.0~1.5 倍 |
| `ge1_5` | 大于等于 1.5 倍 |

#### 5.2.1 路径窗口对照

| path window | progress | `DCE.m2601` net | `CZCE.SR601` net | `SHFE.rb2601` net | 观察 |
| --- | ---: | ---: | ---: | ---: | --- |
| 3 bars / 15m | 1 tick | +1,148.22 | -563.35 | -4,297.10 | DCE.m 与基准接近，SR 仍被伤害 |
| 3 bars / 15m | 2 ticks | +1,288.23 | -323.37 | -4,297.10 | DCE.m 小幅改善，SR 仍负 |
| 4 bars / 20m | 1 tick | +1,148.22 | -263.32 | -4,687.00 | SR 接近但仍负 |
| 4 bars / 20m | 2 ticks | +1,148.22 | -23.34 | -4,687.00 | SR 基本接近 0，但仍不如无早退基准 |
| 6 bars / 30m | 1 tick | +1,148.22 | -573.35 | -4,946.94 | 接近无早退，但 SR 仍负 |
| 6 bars / 30m | 2 ticks | +1,148.22 | -253.37 | -4,427.06 | 没有形成跨品种改善 |

无路径早退基准：

| symbol | net pnl |
| --- | ---: |
| `DCE.m2601` | +1,148.22 |
| `CZCE.SR601` | +726.75 |
| `SHFE.rb2601` | -4,946.94 |

结论：

```text
把路径检查窗口从 5~10 分钟放宽到 15~30 分钟，仍没有让路径早退成为稳定改进。
```

对 `DCE.m2601`，路径窗口放宽后基本回到基准，仅 3 bars / 2 ticks 有轻微改善。对 `CZCE.SR601`，所有路径早退版本仍弱于无早退基准，说明 SR 的有效路径确实允许更长时间的横向消化。对 `SHFE.rb2601`，路径早退只能减亏，不能转正。

#### 5.2.2 波动率分桶观察

本轮以所有 3/4/6 bar 路径窗口结果合并观察波动率分桶。

| symbol | volatility bucket | samples | net after commission | wins | losses | 观察 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `DCE.m2601` | `0_5_1` | 36 | +21,259.49 | 18 | 11 | 最强正收益区间 |
| `DCE.m2601` | `1_1_5` | 6 | -6,113.82 | 0 | 6 | 入场 bar 过大时明显失败 |
| `DCE.m2601` | `lt0_5` | 18 | +1,699.36 | 6 | 12 | 低波动也能正，但质量较弱 |
| `CZCE.SR601` | `lt0_5` | 48 | +7,118.15 | 24 | 24 | SR 最适合低入场波动 |
| `CZCE.SR601` | `0_5_1` | 12 | +1,571.23 | 6 | 6 | 中等波动也可接受 |
| `CZCE.SR601` | `ge1_5` | 6 | -1,859.50 | 0 | 6 | 入场 bar 极大时失败 |
| `SHFE.rb2601` | `lt0_5` | 30 | -4,415.35 | 16 | 14 | 低波动仍负 |
| `SHFE.rb2601` | `0_5_1` | 36 | -9,794.65 | 12 | 24 | 中等波动明显负 |

exit reason 进一步显示：

| symbol | bucket | 主要问题 |
| --- | --- | --- |
| `DCE.m2601` | `0_5_1` | POC 命中收益很强，但仍有 strict failure；整体可覆盖 |
| `DCE.m2601` | `1_1_5` | 全部 time_exit 亏损，说明入场 bar 太大后追随 POC 失败 |
| `CZCE.SR601` | `lt0_5` | force_flat / take_profit 贡献正收益，time_exit 接近小亏，可接受 |
| `CZCE.SR601` | `ge1_5` | 全部 path_failure 亏损，入场波动过大不适合早退结构 |
| `SHFE.rb2601` | `0_5_1` | take_profit 有效，但 strict failure 和 force_flat 大幅吞噬 |
| `SHFE.rb2601` | `lt0_5` | 仍被 path_failure / time_exit 拖累，低波动也不能解决 |

#### 5.2.3 第二阶段判断

这一轮回答了两个问题。

第一，路径检查窗口是否只是太短？

```text
不是主要问题。
```

窗口拉长到 15~30 分钟后，路径早退仍没有稳定优于无早退基准。尤其 `CZCE.SR601`，最好的路径窗口也只是接近 0，仍明显弱于无早退的 +726.75。

第二，波动率和品种有没有关系？

```text
有，而且关系很强。
```

当前最清晰的结构是：

```text
DCE.m2601：中等入场波动最好，过大波动失败；
CZCE.SR601：低波动 / 中低波动最好，适合慢路径；
SHFE.rb2601：POC 命中有效，但失败边界质量差，波动率过滤不能单独修复。
```

因此，下一步不应继续做统一路径早退，而应改成：

```text
按品种使用不同的路径/波动率解释：
DCE.m：偏快确认 + 避免过大入场 bar；
SR：允许慢路径 + 避免过大入场 bar；
rb：暂停，单独研究 strict failure 为什么吞噬收益。
```

当前 r4 的阶段结论：

```text
POC 空间 + price_raw_rr 仍是有效前置过滤；
路径早退不是通用改进；
入场 bar 波动率与品种适配是下一层更重要的结构变量。
```

