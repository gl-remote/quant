# value_area_reacceptance_baseline R29：扩样与随机基准复验

> 类型：Archive / 策略实验摘要
> 状态：已完成 / 固定规则扩样未通过 / 结构优于随机基准
> 最近更新：2026-07-02
> 前置研究：[R28 结构诊断](./value-area-reacceptance-r28-structure-diagnosis.md)
> 当前研究入口：[strategy-current.md](../../../research/strategy-current.md)

## 1. 实验问题

R28 在 `DCE.p2505/p2509/p2601/p2605` 四个样本中发现：

```text
首笔 VA reacceptance 是弱正期望；
首笔失败后，同方向、冷却后的第 2 笔 continuation/retry 是主要收益来源。
```

R29 目标：固定 R28 后的保守候选，不继续调参，验证该结构是否能扩样。

## 2. 固定候选参数

```text
strategy = value_area_reacceptance_baseline
execution period = 1m
profile_mode = close
value_area_ratio = 0.7
min_breakout_ticks = 4
failure_buffer_ticks = 1
strict_close_exit = true
take_profit_mode = poc
target_distance_ratio = 0.8
target_band_ticks = 0
min_reaccept_ticks = 3
min_reaccept_va_width_ratio = 0
max_hold_bars = 60
stop_widen_multiplier = 1.0
min_target_ticks = 8
min_price_raw_rr = 0.8
max_trades_per_day = 3
reentry_cooldown_minutes = 15
reentry_requires_prev_stop_same_direction = true
reentry_take_profit_r = 1.3
```

目标口径：

```text
第 1 笔：POC 目标，执行目标 = entry → POC 距离的 80%；
第 2/3 笔：固定 R 目标，reentry_take_profit_r 直接决定目标；
target_distance_ratio 不缩放 reentry R target。
```

## 3. 扩样前基准

扩样前最强参考是 R28 的 `true_1.35R`，本轮实测扩样使用更保守的 `1.3R`。

| group | ids | n | win_pct | net_pnl | avg_pnl | PF | trade_sharpe | daily_sharpe | maxDD | worst | best |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| max1_base | 707/710/713/716 | 85 | 45.9 | 9845 | 115.8 | 1.30 | 1.00 | 1.72 | 3570 | -2205 | 4335 |
| true_1.35R | 812/813/814/815 | 111 | 49.5 | 24925 | 224.5 | 1.61 | 2.10 | 3.99 | 5200 | -2205 | 4335 |

R28 `true_1.35R` 分交易序号：

| trade_seq | n | wins | net_pnl | avg_pnl | worst | best |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 85 | 39 | 9845 | 115.8 | -2205 | 4335 |
| 2 | 24 | 15 | 13440 | 560.0 | -1660 | 2180 |
| 3 | 2 | 1 | 1640 | 820.0 | -620 | 2260 |

扩样前判断：

```text
R28 样本内不依赖单笔暴利，但依赖一批头部盈利交易；
主要收益来自第 2 笔 continuation；
最大单亏 -2205，maxDD=5200，样本内风险可接受。
```

## 4. R29 扩样总览

R29 共新增测试 15 个合约窗口，不含 R28 基准样本。

| 批次 | 品种/窗口 | ids | 样本数 | 清算数 | net_pnl | 结构观察 | 结论 |
| --- | --- | --- | ---: | ---: | ---: | --- | --- |
| Batch 1 | DCE.m2505/m2509/m2601/m2605 | 816-819 | 4 | 19 | -20044 | stop_loss 主导亏损，seq2 失败 | 明显失败 |
| Batch 2 | DCE.y2509/y2601 | 820-821 | 2 | 51 | -1025 | seq2 为正，seq1 为负 | 接近但未通过 |
| Batch 3 | DCE.c2601/c2603/c2605 | 822-824 | 3 | 1 | -186 | 几乎无信号 | 无法泛化 |
| Batch 4 | DCE.cs2601/cs2603/cs2605 | 825-827 | 3 | 6 | -1865 | 信号少且为负 | 未通过 |
| Batch 5 | DCE.p2405/p2409/p2501 | 828-830 | 3 | 106 | -14460 | seq1 强负，seq2 打平 | DCE.p 历史外推失败 |

## 5. 分批核心结果

### 5.1 Batch 1：DCE.m 回归验证

| group | n | wins | losses | win_pct | net_pnl | avg | worst | best | PF | maxDD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DCE.m_batch1 | 19 | 3 | 16 | 15.8 | -20044 | -1055 | -4548 | 1965 | 0.16 | 20044 |

分合约：

| symbol | id | n | net_pnl | worst | best | 趋势 | 活跃度 |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| DCE.m2505 | 816 | 11 | -15281 | -4548 | 1965 | non_strong_trend | active |
| DCE.m2509 | 817 | 1 | -266 | -266 | -266 | non_strong_trend | active |
| DCE.m2601 | 818 | 1 | 1414 | 1414 | 1414 | non_strong_trend | active |
| DCE.m2605 | 819 | 6 | -5911 | -2385 | 427 | non_strong_trend | active |

结论：

```text
DCE.m 明显失败；
亏损不是来自不活跃或强趋势样本；
当前适配 DCE.p 后的 continuation 参数不能直接回到 DCE.m。
```

### 5.2 Batch 2：DCE.y 相近油脂油料扩样

| group | n | wins | losses | win_pct | net_pnl | avg | worst | best | PF | maxDD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DCE.y_batch2 | 51 | 25 | 26 | 49.0 | -1025 | -20 | -1175 | 1625 | 0.94 | 4300 |

分交易序号：

| trade_seq | n | wins | net_pnl | avg | worst | best |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 37 | 17 | -4175 | -113 | -1175 | 1525 |
| 2 | 12 | 7 | 3600 | 300 | -775 | 1625 |
| 3 | 2 | 1 | -450 | -225 | -1075 | 625 |

结论：

```text
DCE.y 接近打平但未通过；
第 2 笔 continuation 仍有正贡献；
第 1 笔为负，吞掉了第 2 笔优势。
```

### 5.3 Batch 3：DCE.c 泛化检查

| symbol | id | n | net_pnl | 趋势 | 活跃度 | 备注 |
| --- | ---: | ---: | ---: | --- | --- | --- |
| DCE.c2601 | 822 | 0 | 0 | non_strong_trend | active | 无交易 |
| DCE.c2603 | 823 | 1 | -186 | trend_bias | active | 仅 1 笔 |
| DCE.c2605 | 824 | 0 | 0 | non_strong_trend | active | 无交易 |

结论：

```text
DCE.c 几乎无信号；
不是流动性不足导致；
当前规则在 DCE.c 上没有可评估收益能力。
```

### 5.4 Batch 4：DCE.cs 泛化检查

| group | n | wins | losses | win_pct | net_pnl | avg | worst | best | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DCE.cs_batch4 | 6 | 2 | 4 | 33.3 | -1865 | -311 | -1150 | 550 | 0.26 |

结论：

```text
DCE.cs 交易数少且为负；
与 DCE.c 类似，玉米链品种没有形成可用信号。
```

### 5.5 Batch 5：DCE.p 历史完整窗口扩样

| group | n | wins | losses | win_pct | net_pnl | avg | median | worst | best | PF | trade_sharpe | daily_sharpe | maxDD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DCE.p_old_full_windows | 106 | 46 | 60 | 43.4 | -14460 | -136 | -380 | -2540 | 3300 | 0.76 | -1.20 | -2.25 | 16525 |

分合约：

| symbol | id | n | wins | net_pnl | avg | worst | best | 趋势 | 活跃度 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| DCE.p2405 | 828 | 30 | 12 | -6865 | -229 | -1575 | 2625 | strong_trend | active |
| DCE.p2409 | 829 | 35 | 17 | -5675 | -162 | -2380 | 1620 | trend_bias | active |
| DCE.p2501 | 830 | 41 | 17 | -1920 | -47 | -2540 | 3300 | strong_trend | active |

分交易序号：

| trade_seq | n | wins | net_pnl | avg | worst | best |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 76 | 31 | -17265 | -227 | -2540 | 3300 |
| 2 | 26 | 12 | -430 | -17 | -2380 | 2900 |
| 3 | 4 | 3 | 3235 | 809 | -630 | 2625 |

exit_reason：

| exit_reason | n | net_pnl | avg |
| --- | ---: | ---: | ---: |
| stop_loss | 51 | -54920 | -1077 |
| take_profit | 27 | 31580 | 1170 |
| time_exit | 24 | 9660 | 403 |
| force_flat | 4 | -780 | -195 |

结论：

```text
DCE.p 历史完整窗口扩样明显失败；
三个新增 p 样本全部为负；
seq1 强负，seq2 接近打平但不赚钱；
stop_loss 是核心亏损来源；
p2405 / p2501 是 strong_trend，p2409 是 trend_bias，强上涨趋势可能是关键失败环境。
```

### 5.6 随机入场基准复验

为确认“亏损是否等同随机”，新增长期基准策略：

```text
strategy = value_area_random_baseline
base = value_area_reacceptance_baseline
random_baseline_mode = direction_matched
random_direction_mode = same / random
seeds = 1..10
symbols = DCE.p2405 / DCE.p2409 / DCE.p2501
```

复验输出：

```text
CSV: project_data/research/random_baseline/value_area_random_baseline_compare_20260702_205803.csv
JSON: project_data/research/random_baseline/value_area_random_baseline_compare_20260702_205803.json
```

说明：本节只做同一 runner 下的相对比较；`total_net_pnl` 使用 vnpy 返回值，和上文清算口径不完全一致，因此不与 Batch 5 的清算 `net_pnl=-14460` 混算。

| symbol | structure pnl | same-dir random mean | same-dir percentile | random-dir mean | random-dir percentile | 观察 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| DCE.p2405 | -6170 | -17203 | 100% | -8228 | 60% | 结构亏损，但显著好于同方向随机 |
| DCE.p2409 | -5010 | -14206 | 100% | -8258 | 90% | 结构亏损，但仍优于随机 |
| DCE.p2501 | -1260 | -4530 | 100% | -7692 | 100% | 结构亏损，但明显好于随机 |

组合视角：

| group | count | total pnl | mean pnl | median pnl | trade_count |
| --- | ---: | ---: | ---: | ---: | ---: |
| structure | 3 | -12440 | -4147 | -5010 | 212 |
| same-direction random | 30 | -359390 | -11980 | -14110 | 4542 |
| random-direction random | 30 | -241780 | -8059 | -8325 | 4416 |

结论：

```text
DCE.p 旧窗口上的固定规则不赚钱，仍然成立；
但结构入口没有退化成随机入场；
尤其相对 same-direction random，结构在三个样本均位于随机分布顶部；
这说明 VA reacceptance 的事件 / 入场过滤仍有信息量，问题更可能在市场环境、风险空间、交易序列或退出兑现层。
```

## 6. 核心结论

```text
1. 当前固定规则没有通过扩样；
2. R28 的 DCE.p 四样本优势不能直接外推到更早 DCE.p 历史；
3. DCE.p 不能再视为已验证主线，只能视为特定阶段局部结构；
4. DCE.m 明显失败，说明当前 p continuation 参数不能直接回到最初 m 类样本；
5. DCE.y 有局部线索：seq2 continuation 为正，但 seq1 为负导致整体不过关；
6. DCE.c / DCE.cs 主要问题是信号不足或弱负；
7. 扩样失败主要来自 stop_loss 频率升高和 seq1 首笔负贡献；
8. strong_trend / trend_bias 可能是重要失败环境，但还不能直接作为最终过滤条件；
9. 随机入场复验显示，旧 DCE.p 失败样本上结构仍优于 same-direction/random-direction 随机基准，不能简单判定为无信息随机噪声。
```

## 7. 结构性结论：将策略重构为多次 VA 回归测试

R29 扩样失败后，不应直接把 `value_area_reacceptance` 判定为无效随机噪声。随机入场复验显示，旧 `DCE.p` 失败样本上，结构入口仍优于 same-direction/random-direction 随机基准，说明 VA reacceptance 事件仍有信息量。

当前问题更像是：

```text
策略把不同性质的交易序列混在一起：
1. 首次 VA reacceptance：尝试吃 VA 边界 → POC 的价值回归；
2. 首次失败后的第 2/3 笔：可能既包含继续 VA 回归，也包含趋势 continuation；
3. 当前 reentry 条件依赖“上一笔是否止损/亏损”，这是交易结果约束，不是市场结构约束。
```

因此，下一版 VA 回归主线应尝试把三次交易统一解释为：

```text
市场多次尝试离开上一日 VA 区域，但外部价格接受失败；
只要 POC 价格共识尚未被充分测试，或离开 VA 的突破力度正在衰减，
后续 reacceptance 仍可视为同一个 VA → POC 回归过程的延续。
```

这个改造的目的不是继续调参，而是把不可解释的交易序列条件替换成可解释的 auction/profile 条件。

### 7.1 主规则框架

基础结构保持不变：

```text
使用上一交易日 VAH / VAL / POC；
当价格打破 VA 边界后重新回到 VA 内，才允许考虑开仓；
交易目标仍围绕 POC 价格共识测试。
```

候选方向分为两类：

| setup | 结构 | 回归方向 |
| --- | --- | --- |
| VAL reacceptance long | 跌破 VAL 后重新收回 VAL | 从 VA 下边界回归 POC |
| VAH reacceptance short | 突破 VAH 后重新收回 VAH | 从 VA 上边界回归 POC |

核心变化是：不再用 `trade_seq=1/2/3` 或 `上一笔必须亏损` 来解释开仓，而是用同侧 VA 边界的多次测试状态来解释。

同侧状态应至少记录：

```text
last_breakout_ticks：上一次同侧打破 VA 边界的突破距离；
last_reached_poc：上一次同侧回归是否充分测试 POC；
attempt_count：当日/当前 session 内同侧回归尝试次数；
last_side：当前记录属于 VAL-long 还是 VAH-short。
```

long/short 两侧状态不能混用。VAL 下破后的 long 回归，只能和前一次 VAL 下破比较；VAH 上破后的 short 回归，只能和前一次 VAH 上破比较。

### 7.2 关键可选分支 A：做更接近 POC 的方向，还是更远离 POC 的方向

这是新规则的第一组核心分支，必须单独验证。

#### A1：只做 VA 边界 → POC 更近方向

定义：

```text
VAL reacceptance long：entry 在 POC 下方，做多回归 POC；
VAH reacceptance short：entry 在 POC 上方，做空回归 POC。
```

约束：

```text
long: POC > entry_price
short: POC < entry_price
abs(POC - entry_price) >= min_target_ticks * price_tick
```

解释：

```text
这是真正的 VA 回归线：
价格从 VA 边界重新进入 VA，预期回到 POC 价格共识区。
```

优点：

```text
结构最清晰；
收益来源可解释；
可以直接观察 POC touch rate、entry_to_poc_distance、回归完成率。
```

风险：

```text
在强趋势中，重新进入 VA 可能只是短暂停顿，POC 不一定被测试；
如果 POC 距离太近，交易成本会吞噬优势。
```

#### A2：做远离 POC 的方向

定义：

```text
VAL reacceptance 后不做 long 回归 POC，而是寻找继续向下/失败再离开的机会；
VAH reacceptance 后不做 short 回归 POC，而是寻找继续向上/失败再离开的机会。
```

解释：

```text
这不再是纯 VA 回归，而更接近 continuation / failed reacceptance 方向。
```

优点：

```text
可能适配 strong_trend / trend_bias 环境；
与 R28 中第 2 笔 continuation 收益线索有关。
```

风险：

```text
它和 VA 回归不是同一类钱；
如果混在一个策略里优化，会继续造成 seq1/seq2 解释混乱。
```

结论：

```text
A1 应作为 VA 回归主线优先验证；
A2 可以作为 continuation 分支候选，但不应和 A1 混在同一组结论里评估。
```

### 7.3 关键可选分支 B：打破 VA 边界后，哪些 reacceptance 允许开仓

在主规则下，打破 VA 边界后重新回到 VA 内，并不必然开仓。以下三个候选条件值得逐一验证。

#### B1：首次测试 POC

规则：

```text
当日/当前 session 内，同侧第一次 VA reacceptance 可以开仓；
目标是测试 POC。
```

解释：

```text
第一次从 VA 边界回归 POC，是最干净的价值回归样本。
```

验证重点：

```text
首次回归的 POC touch rate；
首次回归的 avg_pnl / PF / stop_loss 占比；
R29 中 seq1 强负是否来自所有首次回归，还是来自某些环境或空间条件。
```

#### B2：当前突破 VA 区域比上一次更弱

规则：

```text
current_breakout_ticks < last_breakout_ticks
```

long 侧：

```text
current_breakout_ticks = VAL - current_breakout_low
```

short 侧：

```text
current_breakout_ticks = current_breakout_high - VAH
```

解释：

```text
如果本次离开 VA 的距离小于上次，说明外部价格接受能力减弱；
重新回到 VA 后，更可能继续向 POC 回归。
```

验证重点：

```text
突破距离收缩后的 POC touch rate 是否高于普通 reacceptance；
stop_loss 是否下降；
是否能改善 R29 中 seq1/seq2 混合后的亏损结构。
```

#### B3：上次 POC 没有被充分测试

规则：

```text
last_reached_poc is False
```

POC 充分测试建议定义为：

```text
long: bar.high >= POC - target_band_ticks * price_tick
short: bar.low <= POC + target_band_ticks * price_tick
```

解释：

```text
上一次虽然重新回到 VA 内，但没有完成 POC 价格共识测试；
因此下一次同侧 reacceptance 仍可视为同一个 VA 回归过程的延续。
```

验证重点：

```text
未触达 POC 后的再次回归是否有更高完成率；
这种再次交易是否只是增加交易成本，还是确实提高整体期望；
与当前“上一笔亏损后才允许 reentry”的效果相比，是否更稳定、更可解释。
```

### 7.4 候选组合

建议下一轮不要直接搜索大量参数，而是先按结构分支做小矩阵验证：

| 组合 | 方向分支 | 开仓条件 | 目的 |
| --- | --- | --- | --- |
| R30-A | 更接近 POC | 首次测试 POC | 验证最纯 VA 回归是否仍有边际 |
| R30-B | 更接近 POC | 突破距离弱于上次 | 验证外部接受衰减是否提高胜率 |
| R30-C | 更接近 POC | 上次 POC 未充分测试 | 验证多次回归是否有结构价值 |
| R30-D | 更接近 POC | B2 或 B3 | 验证完整多次 VA 回归规则 |
| R30-E | 更远离 POC | 单独记录，不与 VA 回归混评 | 作为 continuation 候选对照 |

主规则可以表达为：

```text
can_enter_va_reversion =
    is_reaccepted_into_va
    and is_poc_reversion_direction
    and (
        is_first_poc_test
        or current_breakout_ticks < last_breakout_ticks
        or previous_poc_not_fully_tested
    )
```

其中 `is_poc_reversion_direction` 是独立分支：

```text
true：做 VA 边界 → POC 更近方向；
false：做远离 POC 的 continuation 候选方向。
```

### 7.5 这一路线需要观察的指标

下一轮验证不只看总收益，必须拆以下指标：

```text
1. POC touch rate：入场后是否充分测试 POC；
2. entry_to_poc_ticks：入场到 POC 的空间是否足够覆盖成本；
3. breakout_ticks：打破 VA 边界的距离分布；
4. breakout_ticks_delta：当前突破距离相对上次是否收缩；
5. by_condition pnl：B1/B2/B3 各条件独立收益；
6. overlap pnl：B2 和 B3 同时满足时的收益；
7. stop_loss 占比：是否解决 R29 的 stop_loss 主导亏损；
8. by_environment：strong_trend / trend_bias / non_strong_trend 下是否表现不同。
```

判断标准：

```text
如果 A1 + B2/B3 能提高 POC touch rate，并降低 stop_loss 占比，
说明 VA 回归线仍值得独立推进；

如果 A1 仍失败，但 A2 在 strong_trend 样本中表现更好，
说明 R28 的第 2 笔收益更可能属于 continuation，而不是 VA 回归；

如果 B1/B2/B3 都无法改善随机基准，
则 VA reacceptance 应降级为状态特征，而不是直接交易策略。
```

## 8. 下一步

暂停继续扩样和无约束调参，进入 R30 结构分支验证：

```text
1. 固定 R29 基础参数和样本，不先调 stop/target；
2. 实现 VA 多次回归状态：记录同侧突破距离、POC 是否充分测试；
3. 分别验证 A1/A2 与 B1/B2/B3 条件组合；
4. 输出 POC touch rate、breakout_ticks_delta、stop_loss 占比和 by_condition pnl；
5. 用随机入场基准确认新规则是否仍显著优于随机。
```
