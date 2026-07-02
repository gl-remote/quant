# value_area_reacceptance R28：结构拆解与失效归因（压缩版）

> 类型：Archive / 结构诊断摘要  
> 状态：已完成 / 形成 reentry target 正交化与 continuation 线索  
> 日期：2026-07-01  
> 前置记录：[R27 扩样复验](./value-area-reacceptance-r27-expanded-sample.md)

## 1. 背景与当前定位

R27 扩样后，`value_area_reacceptance` 完整规则未能在外推样本中稳定产生收益。

当前目标不再是证明策略可上线，而是回答：

```text
1. reacceptance entry 是否存在可迁移短期优势；
2. 亏损主要来自 entry 无效，还是 stop / exit / failure 结构不合理；
3. 哪些结构可复用，哪些品种 / 参数组合应排除。
```

阶段判断：

```text
1. 完整策略当前不可作为上线候选；
2. DCE.p 是当前唯一值得继续结构研究的品种窗口；
3. m/SR 旧主线外推失效，暂不作为主线；
4. strong_trend 不能作为充分排除条件；
5. active_label 未显示明显低流动性问题，但主力 / 换月状态仍未验证。
```

## 2. 当前候选

当前最强但仍未确认可上线的结构候选：

```text
symbol family: DCE.p
kline_period: 1m
profile_mode: close
min_reaccept_ticks: 3
stop_widen_multiplier: 1.0
min_price_raw_rr: 0.8
target_distance_ratio: 0.8
max_trades_per_day: 1
strict_close_exit: true
```

对应核心回测：

| backtest_id | symbol | n | net_pnl | 说明 |
| ---: | --- | ---: | ---: | --- |
| 707 | DCE.p2601 | 23 | 6770 | 当前最好样本 |
| 710 | DCE.p2509 | 15 | 610 | 弱正 |
| 713 | DCE.p2605 | 26 | 1925 | 正 |
| 716 | DCE.p2505 | 21 | 540 | 弱正 |
| 合计 | DCE.p | 85 | 9845 | 当前主候选基线 |

限制：

```text
1. 仍是同一品种族、有限月份窗口；
2. 正收益仍可能依赖少数 take_profit 大单；
3. 主力/次主力、换月阶段、持仓排名未验证；
4. 不能直接升级为可上线策略。
```

## 3. 结构诊断核心结论

### 3.1 Entry 不是完全无效，但路径高度二分

第一轮路径拆解显示：

```text
1. take_profit 组路径干净，入场后 MFE 高、MAE 低，forward return 为正；
2. stop_loss / strict_failure_close 组入场后很快转坏；
3. entry 不是完全没有 alpha，但 alpha 不稳定；
4. 当前策略的主要问题不是“完全没有有利路径”，而是失败路径占比和亏损控制。
```

重要经验：

```text
raw_rr 高不等于质量高。
高 raw_rr 可能只是目标远，并不代表胜率高或路径更好。
```

### 3.2 盈利集中度偏高

早期 DCE.p 样本去掉最大盈利后，多数正样本会转负或接近转负。

结论：

```text
DCE.p 的正收益并非稳态小优势累积，仍明显依赖少数 take_profit 大单。
```

这仍是当前候选不能上线的关键原因之一。

## 4. stop_widen 结论

### 4.1 反事实与真实回测一致指向：1.5 偏宽

`stop_widen_multiplier=1.5` 会让失败路径拖累过重。

真实回测对照：

| stop_widen | n | wins | net_pnl | avg_pnl |
| ---: | ---: | ---: | ---: | ---: |
| 1.0 | 85 | 39 | 9845 | 116 |
| 1.2 | 77 | 33 | 3910 | 51 |
| 1.5 | 65 | 30 | 1725 | 27 |

结论：

```text
1. DCE.p + ticks=3 下，stop_widen=1.0 是当前最优；
2. 1.2 优于 1.5，但不如 1.0 稳；
3. 1.0 会改变交易序列，不只是压缩单笔亏损；
4. p2509 对 stop_widen 不敏感，说明部分月份收益来源不是 stop 宽窄。
```

### 4.2 ticks=3 优于 ticks=2

在 `stop_widen=1.0` 下：

| ticks | n | wins | net_pnl | avg_pnl |
| ---: | ---: | ---: | ---: | ---: |
| 2 | 102 | 42 | 1810 | 18 |
| 3 | 85 | 39 | 9845 | 116 |

结论：

```text
1. ticks=2 也受益于 stop=1.0，但新增交易质量差；
2. ticks=3 更严格，失败交易控制更好；
3. 当前候选保留 min_reaccept_ticks=3。
```

## 5. 非 p 与 RR 阈值结论

### 5.1 stop=1.0 没有救回 m/SR

非 p 小批量验证：

| symbol | stop_widen | n | net_pnl |
| --- | ---: | ---: | ---: |
| DCE.m2603 | 1.0 | 3 | -2802 |
| DCE.m2605 | 1.0 | 6 | -5911 |
| CZCE.SR605 | 1.0 | 8 | -5836 |
| CZCE.SR609 | 1.0 | 5 | -1650 |

结论：

```text
1. stop=1.0 是 DCE.p 的有效修正，但不是普遍修复；
2. m/SR 中失败路径太多，take_profit 无法覆盖 stop_loss；
3. 当前不应回到 m/SR 主线。
```

### 5.2 旧 RR 阈值结论需要修正，但 0.8 仍保留

用户提出的机制判断成立：

```text
stop_widen 会影响 raw_rr = target_distance / actual_stop_distance。
旧 stop=1.5 下的 RR 阈值实验不能直接复用。
```

在 `DCE.p + ticks=3 + stop=1.0` 下重测：

| raw_rr | n | wins | net_pnl | avg_pnl |
| ---: | ---: | ---: | ---: | ---: |
| 0.4 | 125 | 61 | 6960 | 56 |
| 0.6 | 99 | 44 | 6610 | 67 |
| 0.8 | 85 | 39 | 9845 | 116 |
| 1.0 | 77 | 33 | 6665 | 87 |

结论：

```text
1. raw_rr=0.8 仍是当前 DCE.p 汇总最优；
2. 0.4 / 0.6 放出更多交易，但新增交易质量不足；
3. 1.0 过于保守，会砍掉有效收益；
4. 当前不修改 min_price_raw_rr=0.8。
```

## 6. ATR / 波动率归一化结论

### 6.1 ATR 下限止损无效

实验参数：

```text
actual_stop_distance = max(structural_stop_distance, ATR20 × multiplier)
multiplier = 0.5 / 1.0 / 1.5 / 2.0
对象：DCE.p2601 / DCE.p2505
```

结果：

```text
ATR 下限完全没有触发。
结构止损距离已经大于 2 × ATR20。
```

结论：

```text
问题不是“结构止损相对波动率太近”。
ATR 更适合作为 ratio 诊断 / 过滤变量，而不是止损下限。
```

### 6.2 stop_distance / ATR20 分桶有信息量，但非单调

当前候选 `707/710/713/716` 的分桶：

| stop/ATR20 | n | wins | net_pnl | avg_pnl | 结论 |
| --- | ---: | ---: | ---: | ---: | --- |
| <1.0 | 3 | 0 | -2010 | -670 | 过紧，全部亏损 |
| 1.0-1.5 | 15 | 6 | 915 | 61 | 弱正 |
| 1.5-2.0 | 13 | 8 | 3810 | 293 | 较好 |
| 2.0-3.0 | 22 | 9 | -1305 | -59 | 较差 |
| >=3.0 | 32 | 16 | 8435 | 264 | 最赚钱，但有大单贡献，且受每天一单约束影响 |

结论：

```text
1. 不能简单说止损越小越好；
2. <1 ATR 很差，直接压小止损大概率误杀；
3. 2-3 ATR 区间也差；
4. >=3 ATR 反而保留大收益路径；
5. 但该结论受 max_trades_per_day=1 约束影响：如果不限制每天一单，大单盈利后的再次落回 VA 可能继续触发新交易；
6. 新交易会增加成本和路径风险，因此不能直接推断 >=3 ATR 区间在无限制交易下仍最优；
7. stop/ATR 关系是非单调结构。
```

### 6.3 ATR ratio 过滤反事实很好，但真实回测只小幅改善

反事实最优过滤：

```text
过滤 stop/ATR20 < 1.0
过滤 2.0 <= stop/ATR20 < 3.0
```

反事实结果：

| group | n | wins | net_pnl | avg_pnl |
| --- | ---: | ---: | ---: | ---: |
| baseline | 85 | 39 | 9845 | 116 |
| filter counterfactual | 60 | 30 | 13160 | 219 |

真实回测有效结果：

| group | n | wins | net_pnl | avg_pnl |
| --- | ---: | ---: | ---: | ---: |
| baseline | 85 | 39 | 9845 | 116 |
| real_filter | 77 | 35 | 10645 | 138 |

分合约真实结果：

| symbol | baseline | real_filter | delta |
| --- | ---: | ---: | ---: |
| DCE.p2505 | 540 | 1260 | 720 |
| DCE.p2509 | 610 | -610 | -1220 |
| DCE.p2601 | 6770 | 7605 | 835 |
| DCE.p2605 | 1925 | 2390 | 465 |

结论：

```text
1. ATR ratio 过滤真实回测方向为正，但幅度远小于反事实；
2. p2509 转负，说明该过滤不是跨合约稳定增强；
3. 过滤器会改变交易序列：过滤掉当天第一笔后，后续信号可能被释放出来；
4. 反事实不能直接等同真实回测；
5. 暂不把 stop/ATR 过滤升级为当前候选主规则。
```

### 6.4 保留假设：ATR 可能有助于泛化

尽管当前 ATR ratio 过滤没有稳定提升样本内收益，但保留一个研究假设：

```text
ATR / 波动率归一化可能不一定提升当前小样本收益，
但可能在解决过拟合、跨月份/跨品种泛化时发挥作用。
```

因此当前处理方式是：

```text
1. 不把 ATR ratio 过滤并入当前主候选；
2. 保留 ATR ratio 作为诊断字段和未来泛化测试变量；
3. 后续扩样或跨品种验证时，观察 ATR ratio 是否能降低参数对个别月份的依赖；
4. 避免因为当前样本内收益不稳定就完全否定波动率归一化方向。
```

## 7. 工程与口径备注

### 7.1 有效代码改动

当前策略中新增了默认关闭参数：

```text
stop_atr_bars
stop_atr_multiplier
stop_atr_ratio_bars
min_stop_atr_ratio
max_stop_atr_ratio
exclude_stop_atr_ratio_low
exclude_stop_atr_ratio_high
```

位置：

- [value_area_reacceptance_baseline_strategy.py](file:///Users/gaolei/Documents/src/quant/workspace/strategies/value_area_reacceptance_baseline_strategy.py)

辅助诊断脚本：

- [value_area_reacceptance_structure_diagnosis.py](file:///Users/gaolei/Documents/src/quant/scripts/analysis/value_area_reacceptance_structure_diagnosis.py)

### 7.2 作废回测

`753-756` 作废：

```text
原因：第一次实现 stop_atr_ratio 过滤时，data_requirements 未把 stop_atr_ratio_bars 纳入 lookback，导致 stop_atr_ratio 全部为 NULL，过滤未生效。
修复：data_requirements 已将 stop_atr_bars / stop_atr_ratio_bars 纳入 lookback_bars。
有效真实过滤回测为 757-760。
```

### 7.3 交易序列问题

由于：

```text
max_trades_per_day = 1
```

过滤器不只是删除交易，还可能释放当天后续交易。

这解释了：

```text
反事实：85 -> 60 笔，net 9845 -> 13160
真实回测：85 -> 77 笔，net 9845 -> 10645
```

后续所有过滤器实验都必须区分：

```text
静态删除反事实
真实策略交易序列重排
```

## 8. 当前结论

```text
1. 完整 value_area_reacceptance 仍不能上线；
2. DCE.p 是当前唯一值得继续拆解的窗口；
3. 当前候选保持：DCE.p + 1m + close-profile + ticks=3 + stop_widen=1.0 + raw_rr=0.8；
4. stop_widen=1.5 已基本判定偏宽；
5. ticks=2 交易更多但质量差，不作为优先候选；
6. m/SR 暂不作为主线；
7. ATR ratio 有信息量，但真实过滤不够稳定，暂不并入候选；
8. 盈利集中度、交易序列重排、主力/换月验证仍未解决。
```

## 9. 下一步

优先级最高的是交易序列差异分析：

```text
1. 找出 baseline 中被 stop/ATR 过滤掉的交易；
2. 找出真实过滤后同一天释放出来的新交易；
3. 按 symbol 汇总：被过滤交易净盈亏、新释放交易净盈亏、最终 delta；
4. 特别检查 p2509 为什么从 +610 变成 -610；
5. 判断是否需要“过滤后当天不再交易”的 day-level gating。
```

在完成该分析前，不建议继续扩样或把 ATR ratio 过滤并入主候选。

## 10. max_trades_per_day=3 初测

为了验证“每天一单”对交易序列的影响，本轮把当前 DCE.p 候选从：

```text
max_trades_per_day = 1
```

改为：

```text
max_trades_per_day = 3
```

并分别测试：

```text
1. baseline：DCE.p + ticks=3 + stop=1.0 + raw_rr=0.8
2. ATR filter：baseline + stop/ATR20 过滤 <1.0 和 2.0-3.0
```

对应回测：

```text
max3 baseline: 761 / 762 / 763 / 764
max3 ATR filter: 765 / 766 / 767 / 768
```

### 10.1 汇总结果

| group | n | wins | losses | win_pct | net_pnl | avg_pnl | cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| max1_base | 85 | 39 | 46 | 45.9 | 9845 | 116 | 4635 |
| max1_atr_filter | 77 | 35 | 42 | 45.5 | 10645 | 138 | 4155 |
| max3_base | 132 | 60 | 72 | 45.5 | 14645 | 111 | 7335 |
| max3_atr_filter | 116 | 52 | 64 | 44.8 | 13425 | 116 | 6375 |

结论：

```text
1. 放开到每天 3 单后，baseline 总收益从 9845 提升到 14645；
2. 交易数从 85 增加到 132，成本从 4635 增加到 7335；
3. 虽然成本明显增加，但新增交易整体仍贡献正收益；
4. ATR filter 在 max1 下小幅改善，但在 max3 下反而低于 baseline；
5. 这说明 ATR filter 的价值依赖 max_trades_per_day，不是稳定主规则。
```

### 10.2 分合约结果

| group | symbol | backtest_id | n | wins | win_pct | net_pnl | avg_pnl |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| max1_base | DCE.p2505 | 716 | 21 | 8 | 38.1 | 540 | 26 |
| max3_base | DCE.p2505 | 764 | 37 | 17 | 45.9 | 7875 | 213 |
| max3_atr_filter | DCE.p2505 | 768 | 29 | 11 | 37.9 | 3635 | 125 |
| max1_base | DCE.p2509 | 710 | 15 | 7 | 46.7 | 610 | 41 |
| max3_base | DCE.p2509 | 762 | 20 | 10 | 50.0 | 3590 | 180 |
| max3_atr_filter | DCE.p2509 | 766 | 19 | 9 | 47.4 | 2210 | 116 |
| max1_base | DCE.p2601 | 707 | 23 | 12 | 52.2 | 6770 | 294 |
| max3_base | DCE.p2601 | 761 | 34 | 15 | 44.1 | 2580 | 76 |
| max3_atr_filter | DCE.p2601 | 765 | 30 | 14 | 46.7 | 5435 | 181 |
| max1_base | DCE.p2605 | 713 | 26 | 12 | 46.2 | 1925 | 74 |
| max3_base | DCE.p2605 | 763 | 41 | 18 | 43.9 | 600 | 15 |
| max3_atr_filter | DCE.p2605 | 767 | 38 | 18 | 47.4 | 2145 | 56 |

分合约观察：

```text
1. p2505 / p2509 明显受益于每天 3 单，说明每天一单压掉了部分有效后续机会；
2. p2601 / p2605 在 max3 baseline 下反而变差，说明后续交易不总是好；
3. ATR filter 在 p2601 / p2605 上改善 max3 baseline，但在 p2505 / p2509 上砍掉了大量有效收益；
4. 因此不能简单把 max_trades_per_day=3 或 ATR filter 作为统一规则。
```

### 10.3 exit_reason 与成本

| group | exit_reason | n | net_pnl | avg_pnl |
| --- | --- | ---: | ---: | ---: |
| max3_base | stop_loss | 56 | -44615 | -797 |
| max3_base | take_profit | 42 | 53945 | 1284 |
| max3_base | time_exit | 27 | 6825 | 253 |
| max3_atr_filter | stop_loss | 49 | -39015 | -796 |
| max3_atr_filter | take_profit | 34 | 46265 | 1361 |
| max3_atr_filter | time_exit | 27 | 7225 | 268 |

成本观察：

```text
max1_base: 85 笔，成本 4635，净利 9845
max3_base: 132 笔，成本 7335，净利 14645
```

说明：

```text
1. 放开每天 3 单确实显著增加交易成本；
2. 但在这批 DCE.p 样本中，新增交易收益仍覆盖了额外成本；
3. ATR filter 降低了 stop_loss，也降低了 take_profit，最终在 max3 下净收益低于 baseline。
```

### 10.4 阶段结论

```text
1. 用户关于“每天一单限制会影响大单后再次落回 VA 的交易序列”的判断成立；
2. max_trades_per_day=3 在当前四个 DCE.p 样本上提高了总收益；
3. 但改善主要来自 p2505 / p2509，p2601 / p2605 反而被后续交易拖累；
4. ATR ratio 过滤不应并入主候选，在 max3 下它降低了总收益；
5. 当前更像是存在“哪些日内后续交易值得做”的问题，而不是简单改每天交易次数。
```

### 10.5 下一步

```text
1. 不直接把 max_trades_per_day=3 升级为候选；
2. 先做同日第 1 / 2 / 3 笔交易的序号分层；
3. 分析第二、第三笔交易在不同合约中的收益、成本、exit_reason；
4. 如果第 2/3 笔只在 p2505/p2509 有效，则考虑日内再入场条件，而不是全局放开；
5. 当前候选仍暂记为 max_trades_per_day=1，max3 作为重要后续方向。
```

## 11. 同日第 1 / 2 / 3 笔交易序号分层

本轮对 `max_trades_per_day=3` 的回测做日内交易序号分层：

```text
trade_seq = 同一 backtest_id + 同一交易日内，按 open_time 排序后的第几笔清算交易。
```

分析对象：

```text
max3_base: 761 / 762 / 763 / 764
max3_atr_filter: 765 / 766 / 767 / 768
```

### 11.1 汇总结果

| group | trade_seq | n | wins | losses | win_pct | net_pnl | avg_pnl | cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| max3_base | 1 | 85 | 39 | 46 | 45.9 | 9845 | 116 | 4635 |
| max3_base | 2 | 36 | 14 | 22 | 38.9 | -2315 | -64 | 2055 |
| max3_base | 3 | 11 | 7 | 4 | 63.6 | 7115 | 647 | 645 |
| max3_atr_filter | 1 | 77 | 35 | 42 | 45.5 | 10645 | 138 | 4155 |
| max3_atr_filter | 2 | 31 | 12 | 19 | 38.7 | -2675 | -86 | 1755 |
| max3_atr_filter | 3 | 8 | 5 | 3 | 62.5 | 5455 | 682 | 465 |

关键结论：

```text
1. 第 1 笔交易正好对应 max1 结果；
2. 第 2 笔交易整体为负，baseline 为 -2315，ATR filter 为 -2675；
3. 第 3 笔交易样本少，但收益很强，baseline 为 +7115，ATR filter 为 +5455；
4. max3 的总收益提升不是来自第 2 笔，而主要来自少数第 3 笔大收益；
5. 这说明“放开到 3 单”不是线性增加好交易，而是引入了一个负的第 2 笔层和一个小样本高收益第 3 笔层。
```

### 11.2 分合约结果

| group | symbol | seq1_net | seq2_net | seq3_net |
| --- | --- | ---: | ---: | ---: |
| max3_base | DCE.p2505 | 540 | 335 | 7000 |
| max3_base | DCE.p2509 | 610 | 2980 | - |
| max3_base | DCE.p2601 | 6770 | -4470 | 280 |
| max3_base | DCE.p2605 | 1925 | -1160 | -165 |
| max3_atr_filter | DCE.p2505 | 1260 | -2345 | 4720 |
| max3_atr_filter | DCE.p2509 | -610 | 2820 | - |
| max3_atr_filter | DCE.p2601 | 7605 | -3070 | 900 |
| max3_atr_filter | DCE.p2605 | 2390 | -80 | -165 |

分合约观察：

```text
1. p2505 的第 3 笔贡献极大，是 max3_base 大幅改善的主要来源；
2. p2509 的第 2 笔为正，是每天一单压掉的有效后续机会；
3. p2601 的第 2 笔明显拖累，说明该合约不适合简单放开日内再入场；
4. p2605 的第 2/3 笔也没有明显价值；
5. ATR filter 能缓解 p2601/p2605 的第 2 笔拖累，但会砍掉 p2505 的有效第 2/3 笔收益。
```

### 11.3 exit_reason 分层

| group | trade_seq | exit_reason | n | net_pnl | avg_pnl |
| --- | ---: | --- | ---: | ---: | ---: |
| max3_base | 2 | stop_loss | 18 | -14635 | -813 |
| max3_base | 2 | take_profit | 6 | 8955 | 1493 |
| max3_base | 2 | time_exit | 8 | 4270 | 534 |
| max3_base | 3 | stop_loss | 2 | -1080 | -540 |
| max3_base | 3 | take_profit | 6 | 8120 | 1353 |
| max3_base | 3 | time_exit | 2 | 295 | 148 |
| max3_atr_filter | 2 | stop_loss | 16 | -12855 | -803 |
| max3_atr_filter | 2 | take_profit | 4 | 6195 | 1549 |
| max3_atr_filter | 2 | time_exit | 7 | 4890 | 699 |
| max3_atr_filter | 3 | stop_loss | 1 | -460 | -460 |
| max3_atr_filter | 3 | take_profit | 4 | 5840 | 1460 |
| max3_atr_filter | 3 | time_exit | 2 | 295 | 148 |

结构观察：

```text
1. 第 2 笔的问题是 stop_loss 数量太多，take_profit / time_exit 虽有贡献但覆盖不足；
2. 第 3 笔的收益主要来自 take_profit，且 stop_loss 数量很少；
3. 但第 3 笔样本只有 8-11 笔，不能直接作为规则依据；
4. 第 1 / 2 / 3 笔很可能不是同一种策略的钱，而是不同日内上下文下的不同收益来源；
5. 当前最值得研究的是分别定义第 2/3 笔的独立触发条件，而不是简单 max_trades_per_day=3。
```

### 11.4 阶段结论

```text
1. max_trades_per_day=3 的收益提升不是均匀来自第 2、3 笔；
2. 第 2 笔整体为负，不宜无条件开放；
3. 第 3 笔表现强，但样本太少，且高度集中在 p2505；
4. ATR filter 不是统一解决方案，它减少部分亏损，也砍掉部分有效后续交易；
5. 第 1 / 2 / 3 笔应视为可能不同的策略子结构，不能用同一套条件强行优化；
6. 下一步若继续研究日内再入场，应构造“再入场资格”或独立子策略条件，而不是简单提高 max_trades_per_day。
```

### 11.5 下一步

```text
1. 暂不把 max_trades_per_day=3 升级为候选；
2. 继续把 max1 候选作为主线；
3. 日内再入场作为独立结构方向：研究第 2/3 笔出现前的上下文；
4. 不把第 1/2/3 笔强行视为同一种策略信号，而是分别拆成可能不同的子策略条件；
5. 优先看 p2505 第 3 笔与 p2509 第 2 笔为什么有效；
6. 对比 p2601/p2605 的第 2 笔为什么明显失败。
```

## 12. 第 2/3 笔上下文拆解：再入场资格初步假设

分析对象仍然是 `max3_base`：`761 / 762 / 763 / 764`。

本轮不直接改策略，只做交易序列上下文拆解，目标是判断第 2/3 笔是否存在独立的再入场资格。

### 12.1 有效组与失败组对比

分组定义：

```text
有效组 A：p2505 第 3 笔
有效组 B：p2509 第 2 笔
失败组：p2601 / p2605 第 2 笔
```

| group | n | wins | losses | net_pnl | avg_pnl | avg_pnl_before | prev_win_n | prev_loss_n | same_dir_n | avg_gap_min | avg_raw_rr |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| effective_p2505_seq3 | 6 | 5 | 1 | 7000 | 1167 | 449 | 2 | 4 | 6 | 46.3 | 1.69 |
| effective_p2509_seq2 | 5 | 3 | 2 | 2980 | 596 | -748 | 0 | 5 | 5 | 26.4 | 1.27 |
| failed_p2601_p2605_seq2 | 21 | 7 | 14 | -5630 | -268 | -78 | 8 | 13 | 18 | 53.0 | 2.40 |

关键观察：

```text
1. 两个有效组几乎都不是“前一笔盈利后继续追打”：
   - p2509 第 2 笔全部发生在前一笔亏损之后；
   - p2505 第 3 笔多数也发生在前序亏损之后。
2. 有效组全部是同方向再入场；失败组多数也是同方向，但失败组里高 RR 并没有带来正收益。
3. 失败组平均 raw_rr 更高，说明第 2/3 笔不是简单用 RR 能筛出来。
4. 再入场更像是“第一次同方向尝试被止损后，市场重新给出同方向 reaccept 信号”，而不是普通多交易次数。
```

### 12.2 前一笔 exit_reason 的影响

| trade_seq | prev_exit | n | wins | losses | net_pnl | avg_pnl |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 2 | stop_loss | 16 | 9 | 7 | 4120 | 258 |
| 2 | take_profit | 11 | 2 | 9 | -4545 | -413 |
| 2 | time_exit | 9 | 3 | 6 | -1890 | -210 |
| 3 | stop_loss | 7 | 5 | 2 | 6315 | 902 |
| 3 | take_profit | 3 | 2 | 1 | 1260 | 420 |
| 3 | time_exit | 1 | 0 | 1 | -460 | -460 |

按前一笔盈亏看：

| trade_seq | prev_pnl_bucket | n | wins | losses | net_pnl | avg_pnl |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 2 | after_loss | 23 | 11 | 12 | 1835 | 80 |
| 2 | after_win | 13 | 3 | 10 | -4150 | -319 |
| 3 | after_loss | 7 | 5 | 2 | 6315 | 902 |
| 3 | after_win | 4 | 2 | 2 | 800 | 200 |

方向关系：

| trade_seq | dir_relation | n | net_pnl | avg_pnl |
| ---: | --- | ---: | ---: | ---: |
| 2 | opposite_dir | 5 | -2185 | -437 |
| 2 | same_dir | 31 | -130 | -4 |
| 3 | same_dir | 11 | 7115 | 647 |

结论：

```text
1. 前一笔 stop_loss 后的第 2/3 笔整体为正；
2. 前一笔 take_profit 或 time_exit 后继续交易整体偏差；
3. 第 2 笔反向交易明显偏负；
4. “前一笔止损 + 同方向再入场”是目前最强的第 2/3 笔资格候选。
```

### 12.3 反事实静态过滤

如果保留：

```text
1. 所有第 1 笔交易；
2. 第 2/3 笔中，前一笔 exit_reason=stop_loss 且方向相同的交易。
```

静态结果为：

| group | n | wins | losses | win_pct | net_pnl | avg_pnl | cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| max1_plus_prev_stop_same_dir | 108 | 53 | 55 | 49.1 | 20280 | 188 | 5940 |
| added_reentries_only | 23 | 14 | 9 | 60.9 | 10435 | 454 | 1305 |

与已知基准对比：

```text
max1_base: n=85, net_pnl=9845
max3_base: n=132, net_pnl=14645
静态过滤后: n=108, net_pnl=20280
```

限制：

```text
1. 这是静态反事实，不等于真实策略回测；
2. 一旦真实过滤掉某笔交易，后续第 2/3 笔序列可能重排；
3. 样本仍然小，不能直接升级为主规则；
4. 但该结果足够支持下一轮真实回测：只允许“前一笔 stop_loss 后同方向再入场”。
```

### 12.4 阶段假设

```text
第 1 笔：仍按当前主候选理解，是标准 VA reacceptance 信号；
第 2/3 笔：更像是同方向结构未失效时的 retry / continuation 信号；
不应该把第 2/3 笔理解为简单重复第 1 笔。
```

下一步：

```text
1. 先不直接放开 max_trades_per_day=3；
2. 增加一个再入场资格参数做真实回测：
   - 只有前一笔 exit_reason=stop_loss；
   - 且本次方向与前一笔相同；
   - 才允许日内第 2/3 笔；
3. 用 DCE.p 四个样本先跑一轮；
4. 如果有效，再扩到非 p 样本检验是否只是 p 小样本拟合。
```

## 13. 再入场资格真实回测

### 13.1 实现

新增策略参数：

```text
reentry_requires_prev_stop_same_direction: bool = False
```

默认关闭，不影响旧实验。

开启后：

```text
第 1 笔不受影响；
第 2/3 笔只有在上一笔 exit_reason=stop_loss，且本次方向与上一笔方向相同时才允许入场。
```

测试参数：

```text
DCE.p + 1m + close-profile + min_reaccept_ticks=3
stop_widen_multiplier=1.0
min_price_raw_rr=0.8
target_distance_ratio=0.8
max_trades_per_day=3
reentry_requires_prev_stop_same_direction=true
```

回测 ID：

```text
769 DCE.p2601
770 DCE.p2509
771 DCE.p2605
772 DCE.p2505
```

### 13.2 与 max1 / max3 对比

| group | n | wins | losses | win_pct | net_pnl | avg_pnl | worst | best | cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| max1_base | 85 | 39 | 46 | 45.9 | 9845 | 116 | -2205 | 4335 | 4635 |
| max3_base | 132 | 60 | 72 | 45.5 | 14645 | 111 | -2205 | 4335 | 7335 |
| reentry_stop_same | 102 | 49 | 53 | 48.0 | 15745 | 154 | -2205 | 4335 | 5595 |

结论：

```text
1. 真实回测没有复现静态反事实的 20280；
2. 但它高于 max1_base 和 max3_base；
3. 交易数从 max3 的 132 降到 102，成本从 7335 降到 5595；
4. 胜率和单笔均值均高于 max1 / max3；
5. 说明“前一笔 stop_loss + 同方向再入场”不是纯噪声，有真实过滤价值。
```

### 13.3 分合约结果

| id | symbol | n | wins | losses | net_pnl | avg_pnl | cost |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 772 | DCE.p2505 | 24 | 10 | 14 | 2600 | 108 | 1320 |
| 770 | DCE.p2509 | 20 | 10 | 10 | 3590 | 180 | 1170 |
| 769 | DCE.p2601 | 27 | 14 | 13 | 6280 | 233 | 1440 |
| 771 | DCE.p2605 | 31 | 15 | 16 | 3275 | 106 | 1665 |

分交易序号：

| trade_seq | n | wins | losses | net_pnl | avg_pnl | cost |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 85 | 39 | 46 | 9845 | 116 | 4635 |
| 2 | 16 | 9 | 7 | 4120 | 258 | 900 |
| 3 | 1 | 1 | 0 | 1780 | 1780 | 60 |

分合约 / 交易序号：

| symbol | seq1_net | seq2_net | seq3_net |
| --- | ---: | ---: | ---: |
| DCE.p2505 | 540 | 280 | 1780 |
| DCE.p2509 | 610 | 2980 | - |
| DCE.p2601 | 6770 | -490 | - |
| DCE.p2605 | 1925 | 1350 | - |

### 13.4 不符合预期现象

```text
1. 静态反事实里第 2/3 笔新增 23 笔，净利 10435；
2. 真实回测中新增第 2/3 笔只有 17 笔，净利 5900；
3. 其中第 3 笔从静态反事实中的 7 笔左右，真实回测只剩 1 笔；
4. 这说明过滤机制确实改变了交易序列，不能用静态删除结果直接推断真实策略表现。
```

具体解释：

```text
当某些第 2 笔被过滤后，原本 max3 序列中的第 3 笔不一定还会出现；
即使出现，它的“上一笔交易”也可能已经变了，导致再入场资格变化。
```

### 13.5 阶段结论

```text
1. 用户提出的“两套策略雏形”判断得到进一步支持：
   - 第 1 笔偏标准 VA reacceptance，吃价值回归；
   - 第 2/3 笔偏失败试探后的 retry / continuation，等待方向确认。
2. 当前这个最小再入场规则能提升 max1，并优于无条件 max3；
3. 但它仍使用第 1 笔的 POC 目标和退出逻辑，可能没有真正发挥 continuation 结构；
4. 下一步如果继续，不应继续优化同一套 POC 止盈，而应单独测试 continuation 版本：
   - 更远目标；
   - 不同止盈模式；
   - 更严格的方向确认；
   - 或只允许失败后第二次同方向 reaccept。
```

当前处理：

```text
1. reentry_stop_same 暂不升级为主候选；
2. 它是一个通过真实回测验证的结构分支；
3. 主候选仍保留 max1；
4. 后续若继续，应把 continuation/retry 作为独立子策略研究，而不是继续混在 VA 回归规则里。
```

## 14. 平仓后冷却时间实验

### 14.1 实现

新增策略参数：

```text
reentry_cooldown_minutes: int = 0
```

默认 `0`，不影响旧实验。

开启后：

```text
第 1 笔不受影响；
第 2/3 笔必须等待上一笔平仓后达到指定分钟数，才允许再次开仓；
不限制上一笔 exit_reason；
不限制本次方向是否与上一笔相同。
```

测试参数保持与 max3_base 一致，仅加入冷却时间：

```text
DCE.p + 1m + close-profile + min_reaccept_ticks=3
stop_widen_multiplier=1.0
min_price_raw_rr=0.8
target_distance_ratio=0.8
max_trades_per_day=3
```

回测 ID：

```text
cooldown_15m:
773 DCE.p2601
774 DCE.p2509
775 DCE.p2605
776 DCE.p2505

cooldown_30m:
777 DCE.p2601
778 DCE.p2509
779 DCE.p2605
780 DCE.p2505
```

### 14.2 汇总对比

| group | n | wins | losses | win_pct | net_pnl | avg_pnl | cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| max1_base | 85 | 39 | 46 | 45.9 | 9845 | 116 | 4635 |
| max3_base | 132 | 60 | 72 | 45.5 | 14645 | 111 | 7335 |
| reentry_stop_same | 102 | 49 | 53 | 48.0 | 15745 | 154 | 5595 |
| cooldown_15m | 128 | 60 | 68 | 46.9 | 17890 | 140 | 7110 |
| cooldown_30m | 118 | 54 | 64 | 45.8 | 15495 | 131 | 6525 |

结论：

```text
1. cooldown_15m 当前最高，超过 max3_base 和 reentry_stop_same；
2. cooldown_30m 收益回落，略低于 reentry_stop_same；
3. 冷却时间确实能过滤掉一部分过密重复开仓，但冷却过长会错过有效再入场；
4. 15m 更像是在“避免立刻反复打脸”和“保留后续机会”之间取得了较好平衡。
```

### 14.3 分合约结果

| group | symbol | n | net_pnl | avg_pnl | cost |
| --- | --- | ---: | ---: | ---: | ---: |
| cooldown_15m | DCE.p2505 | 36 | 8415 | 234 | 2025 |
| cooldown_15m | DCE.p2509 | 19 | 4290 | 226 | 1110 |
| cooldown_15m | DCE.p2601 | 33 | 3900 | 118 | 1800 |
| cooldown_15m | DCE.p2605 | 40 | 1285 | 32 | 2175 |
| cooldown_30m | DCE.p2505 | 32 | 3375 | 105 | 1785 |
| cooldown_30m | DCE.p2509 | 18 | 5390 | 299 | 1050 |
| cooldown_30m | DCE.p2601 | 29 | 7925 | 273 | 1575 |
| cooldown_30m | DCE.p2605 | 39 | -1195 | -31 | 2115 |

不符合预期现象：

```text
1. 30m 在 p2601 / p2509 上更好，但在 p2505 / p2605 上明显变差；
2. 15m 的优势主要来自 p2505，且 p2605 仍然很弱；
3. 因此冷却时间不是稳定跨合约最优规则，仍有样本依赖。
```

### 14.4 分交易序号

| group | trade_seq | n | wins | losses | net_pnl | avg_pnl | cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| cooldown_15m | 1 | 85 | 39 | 46 | 9845 | 116 | 4635 |
| cooldown_15m | 2 | 33 | 15 | 18 | 3590 | 109 | 1890 |
| cooldown_15m | 3 | 10 | 6 | 4 | 4455 | 446 | 585 |
| cooldown_30m | 1 | 85 | 39 | 46 | 9845 | 116 | 4635 |
| cooldown_30m | 2 | 27 | 13 | 14 | 5335 | 198 | 1545 |
| cooldown_30m | 3 | 6 | 2 | 4 | 315 | 53 | 345 |

结构观察：

```text
1. cooldown_15m 保留了第 3 笔收益，seq3 净利 4455；
2. cooldown_30m 的第 2 笔质量更高，但几乎牺牲了第 3 笔收益；
3. 这进一步支持：第 2 笔和第 3 笔不是同一种钱；
4. 冷却时间主要是在控制“过密再入场”，但不能解决 continuation 目标与 VA 回归目标混用的问题。
```

### 14.5 阶段结论

```text
1. 冷却时间方向值得保留；
2. 当前 DCE.p 小样本上，15m 冷却是本组里最好的 max3 约束；
3. 但 15m 不应直接升级为主候选，因为收益仍集中且 p2605 很弱；
4. 它更适合作为 continuation/retry 子策略的一个入场节奏约束；
5. 下一步若继续，应把“冷却时间 + continuation 更远目标”合并测试，而不是只在 POC 目标下继续调冷却分钟数。
```

## 15. 统一 continuation/retry 实验

### 15.1 实验设计

本轮目标是验证用户提出的“两套策略雏形”：

```text
第 1 笔：标准 VA reacceptance，吃价值回归；
第 2/3 笔：失败/试探后的 retry 或 continuation，等待方向确认后吃更大波段。
```

因此不再只测试单独的 `cooldown` 或 `stop_same`，而是测试统一结构：

```text
max_trades_per_day=3
reentry_cooldown_minutes=15
reentry_requires_prev_stop_same_direction=true
```

两组对照：

```text
A 组：第 2/3 笔仍使用 POC 目标；
B 组：第 1 笔仍使用 POC 目标，第 2/3 笔改用 1.5R 目标。
```

工程备注：

```text
1. 初版 B 组直接设置 take_profit_mode=r, take_profit_r=1.5；
2. 这会把第 1 笔也改成 R 目标，导致第 1 笔交易数从 85 变成 160；
3. 因此初版 B 组 785-788 作废；
4. 后续新增 reentry_take_profit_r，只对日内第 2/3 笔生效；
5. 修正版 B 组使用 789-792。
```

新增参数：

```text
reentry_take_profit_r: float = 0.0
```

默认 `0`，不影响旧实验。只有当 `trade_count > 0` 且 `reentry_take_profit_r > 0` 时，才覆盖第 2/3 笔的目标为 R 目标。

回测 ID：

```text
A_cooldown_stop_same_poc:
781 DCE.p2601
782 DCE.p2509
783 DCE.p2605
784 DCE.p2505

B_reentry_1_5R 修正版：
789 DCE.p2601
790 DCE.p2509
791 DCE.p2605
792 DCE.p2505

作废：
785-788，因为错误地把第 1 笔也改成 R 目标。
```

### 15.2 总体对比

| group | n | wins | losses | win_pct | net_pnl | avg_pnl | worst | best | cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| max1_base | 85 | 39 | 46 | 45.9 | 9845 | 116 | -2205 | 4335 | 4635 |
| max3_base | 132 | 60 | 72 | 45.5 | 14645 | 111 | -2205 | 4335 | 7335 |
| cooldown_15m | 128 | 60 | 68 | 46.9 | 17890 | 140 | -2205 | 4335 | 7110 |
| A_cooldown_stop_same_poc | 101 | 48 | 53 | 47.5 | 15930 | 158 | -2205 | 4335 | 5550 |
| B_reentry_1_5R | 111 | 55 | 56 | 49.5 | 23905 | 215 | -2205 | 4335 | 6015 |

关键结论：

```text
1. B_reentry_1_5R 明显优于 A 组、cooldown_15m、max3_base 和 max1_base；
2. B 组交易数 111，成本 6015，显著低于 cooldown_15m 的 128 笔 / 成本 7110；
3. B 组 win_pct=49.5，avg_pnl=215，都是本轮最高；
4. 这说明“第 2/3 笔使用更远目标”有真实改善，不只是增加交易次数。
```

### 15.3 分交易序号

| group | trade_seq | n | wins | losses | net_pnl | avg_pnl | best | cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A | 1 | 85 | 39 | 46 | 9845 | 116 | 4335 | 4635 |
| A | 2 | 14 | 8 | 6 | 4925 | 352 | 2535 | 795 |
| A | 3 | 2 | 1 | 1 | 1160 | 580 | 1780 | 120 |
| B | 1 | 85 | 39 | 46 | 9845 | 116 | 4335 | 4635 |
| B | 2 | 24 | 15 | 9 | 12900 | 538 | 2175 | 1260 |
| B | 3 | 2 | 1 | 1 | 1160 | 580 | 1780 | 120 |

观察：

```text
1. 第 1 笔在 A/B 中完全一致，说明修正版 B 只改变了第 2/3 笔；
2. B 的主要改善来自第 2 笔：
   - A seq2: n=14, net_pnl=4925, avg_pnl=352
   - B seq2: n=24, net_pnl=12900, avg_pnl=538
3. 第 3 笔没有明显变化，说明本轮真正验证的是“第 2 笔 continuation 目标”；
4. 更远目标不仅提高单笔均值，还改变了后续交易序列，使第 2 笔数量增加。
```

### 15.4 分合约结果

| group | symbol | n | wins | losses | net_pnl | avg_pnl | best | cost |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A | DCE.p2505 | 24 | 10 | 14 | 2680 | 112 | 1860 | 1320 |
| A | DCE.p2509 | 19 | 10 | 9 | 4290 | 226 | 2260 | 1110 |
| A | DCE.p2601 | 28 | 13 | 15 | 4920 | 176 | 4335 | 1500 |
| A | DCE.p2605 | 30 | 15 | 15 | 4040 | 135 | 2535 | 1620 |
| B | DCE.p2505 | 27 | 12 | 15 | 5810 | 215 | 1860 | 1470 |
| B | DCE.p2509 | 22 | 11 | 11 | 2665 | 121 | 1935 | 1275 |
| B | DCE.p2601 | 29 | 14 | 15 | 5900 | 203 | 4335 | 1560 |
| B | DCE.p2605 | 33 | 18 | 15 | 9530 | 289 | 2175 | 1710 |

不符合预期现象：

```text
1. B 组并不是所有合约都改善：p2509 从 4290 降到 2665；
2. B 组最大改善来自 p2605，从 4040 提升到 9530；
3. p2605 此前在 cooldown_15m 中很弱，本轮反而成为主要贡献之一；
4. 这说明更远目标可能不是简单放大利润，而是在某些月份改变了原本 POC 目标下的错误退出结构。
```

### 15.5 exit_reason

| group | exit_reason | n | net_pnl | avg_pnl |
| --- | --- | ---: | ---: | ---: |
| A | force_flat | 3 | -900 | -300 |
| A | forced_close | 1 | 75 | 75 |
| A | stop_loss | 41 | -32185 | -785 |
| A | take_profit | 34 | 44185 | 1300 |
| A | time_exit | 22 | 4755 | 216 |
| B | force_flat | 2 | -120 | -60 |
| B | forced_close | 1 | 75 | 75 |
| B | stop_loss | 42 | -34245 | -815 |
| B | take_profit | 40 | 54565 | 1364 |
| B | time_exit | 26 | 3630 | 140 |

观察：

```text
1. B 组 stop_loss 数量只比 A 多 1 笔，但 take_profit 多 6 笔；
2. take_profit 净收益从 44185 提升到 54565；
3. 更远目标并没有显著增加止损灾难，反而增加了有效止盈；
4. 这支持 continuation/retry 子结构真实存在。
```

### 15.6 阶段结论

```text
1. 本轮最重要结论：第 2/3 笔不应该继续沿用第 1 笔的 POC 回归目标；
2. “15m 冷却 + 前一笔 stop_loss + 同方向 + 第 2/3 笔 1.5R 目标”是目前最强结构候选；
3. 用户关于“两套策略雏形”的判断得到目前最强支持：
   - 第 1 笔：VA reacceptance / 价值回归；
   - 第 2/3 笔：failed-probe continuation / 方向确认。
4. 但该结论仍只在 DCE.p 四个样本上成立，不能直接升级为最终策略；
5. 下一步需要做两个方向：
   - 扩到非 p 样本，验证是否是 DCE.p 拟合；
   - 在 DCE.p 内做更小范围目标对照，例如 reentry_take_profit_r=1.2 / 2.0，验证 1.5R 不是偶然点。
```

当前候选记录：

```text
主线 A：max1 VA reacceptance，POC 目标；
结构分支 B：reentry continuation，15m cooldown + prev_stop_same_direction + reentry_take_profit_r=1.5。
```

暂不把 B 直接合并为主候选，先做扩样和目标稳健性检查。

### 15.7 目标口径正交复测

后续代码重构后，确认一个重要口径问题：

```text
789-792 中的 reentry_take_profit_r=1.5 是 raw target；
旧代码仍会对 reentry R target 应用 target_distance_ratio=0.8；
因此 789-792 的真实执行目标约为 1.2R，而不是真正 1.5R。
```

本轮将目标约束正交化：

```text
target_distance_ratio / target_band_ticks 只作用于 POC 目标；
reentry_take_profit_r 直接决定第 2/3 笔 R 目标，不再被 POC 目标缩放参数影响。
```

回测 ID：

```text
old_raw_1_5R_effective_1_2R: 789 / 790 / 791 / 792
true_1_5R: 799 / 800 / 801 / 802
true_1_2R: 803 / 804 / 805 / 806
```

总体对比：

| group | n | wins | losses | win_pct | net_pnl | avg_pnl | worst | best | cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| old_raw_1_5R_effective_1_2R | 111 | 55 | 56 | 49.5 | 23905 | 215 | -2205 | 4335 | 6015 |
| true_1_2R | 111 | 55 | 56 | 49.5 | 23905 | 215 | -2205 | 4335 | 6015 |
| true_1_5R | 111 | 54 | 57 | 48.6 | 20025 | 180 | -2205 | 4335 | 6015 |

分交易序号：

| group | trade_seq | n | wins | losses | net_pnl | avg_pnl | best | cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| true_1_2R | 1 | 85 | 39 | 46 | 9845 | 116 | 4335 | 4635 |
| true_1_2R | 2 | 24 | 15 | 9 | 12900 | 538 | 2175 | 1260 |
| true_1_2R | 3 | 2 | 1 | 1 | 1160 | 580 | 1780 | 120 |
| true_1_5R | 1 | 85 | 39 | 46 | 9845 | 116 | 4335 | 4635 |
| true_1_5R | 2 | 24 | 14 | 10 | 8540 | 356 | 2180 | 1260 |
| true_1_5R | 3 | 2 | 1 | 1 | 1640 | 820 | 2260 | 120 |

分合约：

| group | symbol | n | net_pnl | avg_pnl | cost |
| --- | --- | ---: | ---: | ---: | ---: |
| true_1_2R | DCE.p2505 | 27 | 5810 | 215 | 1470 |
| true_1_5R | DCE.p2505 | 27 | 5850 | 217 | 1470 |
| true_1_2R | DCE.p2509 | 22 | 2665 | 121 | 1275 |
| true_1_5R | DCE.p2509 | 22 | 2385 | 108 | 1275 |
| true_1_2R | DCE.p2601 | 29 | 5900 | 203 | 1560 |
| true_1_5R | DCE.p2601 | 29 | 5900 | 203 | 1560 |
| true_1_2R | DCE.p2605 | 33 | 9530 | 289 | 1710 |
| true_1_5R | DCE.p2605 | 33 | 5890 | 178 | 1710 |

结论：

```text
1. 789-792 不能再称为“真 1.5R”，应称为 raw 1.5R / effective 1.2R；
2. 正交 true_1_2R 完全复现旧 789-792，说明旧优势来自实际 1.2R 目标；
3. true_1_5R 仍盈利，但总收益从 23905 降到 20025；
4. 差异主要来自第 2 笔：seq2 从 12900 降到 8540；
5. 因此当前 continuation/retry 的较优目标不是 1.5R，而更接近 1.2R；
6. 下一步不应急着扩样，应先在 DCE.p 内做 1.0R / 1.2R / 1.35R / 1.5R 小范围目标稳健性测试。
```

### 15.8 reentry R 目标稳健性测试

本轮继续固定结构：

```text
max_trades_per_day=3
reentry_cooldown_minutes=15
reentry_requires_prev_stop_same_direction=true
第 1 笔仍使用 POC 目标；
第 2/3 笔使用正交后的 reentry_take_profit_r。
```

回测 ID：

```text
true_1_0R: 807 / 809 / 810 / 811
true_1_2R: 803 / 804 / 805 / 806
true_1_35R: 812 / 813 / 814 / 815
true_1_5R: 799 / 800 / 801 / 802

备注：808 是一次异常空结果，不纳入统计。
```

总体对比：

| group | n | wins | losses | win_pct | net_pnl | avg_pnl | worst | best | cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| true_1_0R | 111 | 56 | 55 | 50.5 | 23165 | 209 | -2205 | 4335 | 6015 |
| true_1_2R | 111 | 55 | 56 | 49.5 | 23905 | 215 | -2205 | 4335 | 6015 |
| true_1_35R | 111 | 55 | 56 | 49.5 | 24925 | 225 | -2205 | 4335 | 6015 |
| true_1_5R | 111 | 54 | 57 | 48.6 | 20025 | 180 | -2205 | 4335 | 6015 |

分交易序号：

| group | trade_seq | n | wins | losses | net_pnl | avg_pnl | best | cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| true_1_0R | 1 | 85 | 39 | 46 | 9845 | 116 | 4335 | 4635 |
| true_1_0R | 2 | 24 | 16 | 8 | 12560 | 523 | 1935 | 1260 |
| true_1_0R | 3 | 2 | 1 | 1 | 760 | 380 | 1380 | 120 |
| true_1_2R | 1 | 85 | 39 | 46 | 9845 | 116 | 4335 | 4635 |
| true_1_2R | 2 | 24 | 15 | 9 | 12900 | 538 | 2175 | 1260 |
| true_1_2R | 3 | 2 | 1 | 1 | 1160 | 580 | 1780 | 120 |
| true_1_35R | 1 | 85 | 39 | 46 | 9845 | 116 | 4335 | 4635 |
| true_1_35R | 2 | 24 | 15 | 9 | 13440 | 560 | 2180 | 1260 |
| true_1_35R | 3 | 2 | 1 | 1 | 1640 | 820 | 2260 | 120 |
| true_1_5R | 1 | 85 | 39 | 46 | 9845 | 116 | 4335 | 4635 |
| true_1_5R | 2 | 24 | 14 | 10 | 8540 | 356 | 2180 | 1260 |
| true_1_5R | 3 | 2 | 1 | 1 | 1640 | 820 | 2260 | 120 |

分合约：

| group | symbol | n | net_pnl | avg_pnl | cost |
| --- | --- | ---: | ---: | ---: | ---: |
| true_1_0R | DCE.p2505 | 27 | 5330 | 197 | 1470 |
| true_1_2R | DCE.p2505 | 27 | 5810 | 215 | 1470 |
| true_1_35R | DCE.p2505 | 27 | 6090 | 226 | 1470 |
| true_1_5R | DCE.p2505 | 27 | 5850 | 217 | 1470 |
| true_1_0R | DCE.p2509 | 22 | 2905 | 132 | 1275 |
| true_1_2R | DCE.p2509 | 22 | 2665 | 121 | 1275 |
| true_1_35R | DCE.p2509 | 22 | 3165 | 144 | 1275 |
| true_1_5R | DCE.p2509 | 22 | 2385 | 108 | 1275 |
| true_1_0R | DCE.p2601 | 29 | 7700 | 266 | 1560 |
| true_1_2R | DCE.p2601 | 29 | 5900 | 203 | 1560 |
| true_1_35R | DCE.p2601 | 29 | 5900 | 203 | 1560 |
| true_1_5R | DCE.p2601 | 29 | 5900 | 203 | 1560 |
| true_1_0R | DCE.p2605 | 33 | 7230 | 219 | 1710 |
| true_1_2R | DCE.p2605 | 33 | 9530 | 289 | 1710 |
| true_1_35R | DCE.p2605 | 33 | 9770 | 296 | 1710 |
| true_1_5R | DCE.p2605 | 33 | 5890 | 178 | 1710 |

结论：

```text
1. 1.0R / 1.2R / 1.35R 都明显优于 max1_base，说明 continuation/retry 目标不是单点偶然；
2. 当前四样本最高是 1.35R，net_pnl=24925；
3. 1.2R 与 1.35R 差距不大，构成较稳定平台；
4. 1.5R 明显回落，说明目标过远会牺牲第 2 笔胜率与收益；
5. 主要收益来源仍是第 2 笔，seq3 只有 2 笔，不能作为主判断；
6. 下一步可以选择：
   - 先用 1.2R/1.35R 做扩样；
   - 或在 DCE.p 内补 1.3R / 1.4R 精细化确认峰值，但要警惕过拟合。
```

## 16. 上一笔盈利后再入场对照

### 16.1 实验问题

用户提出把再入场条件从：

```text
上一笔必须 stop_loss 且同方向
```

改成：

```text
上一笔必须盈利
```

本轮用可在策略内部稳定判断的口径实现：

```text
上一笔 exit_reason = take_profit
且本次方向与上一笔相同。
```

说明：这里没有直接用清算后的 `net_pnl > 0`，因为策略入场时拿不到未来清算表里的净利；使用 `take_profit` 作为“上一笔盈利”的实时近似。

新增参数：

```text
reentry_requires_prev_take_profit_same_direction: bool = False
```

测试参数保持与当前最强结构一致：

```text
max_trades_per_day=3
reentry_cooldown_minutes=15
reentry_take_profit_r=1.5
```

对照组：

```text
prev_stop_same_r: 789 / 790 / 791 / 792
prev_tp_same_r: 793 / 794 / 795 / 796
```

### 16.2 总体对比

| group | n | wins | losses | win_pct | net_pnl | avg_pnl | worst | best | cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| max1_base | 85 | 39 | 46 | 45.9 | 9845 | 116 | -2205 | 4335 | 4635 |
| prev_stop_same_r | 111 | 55 | 56 | 49.5 | 23905 | 215 | -2205 | 4335 | 6015 |
| prev_tp_same_r | 95 | 43 | 52 | 45.3 | 9875 | 104 | -2205 | 4335 | 5205 |

结论：

```text
1. 上一笔 take_profit 后同方向再入场几乎没有带来新增收益；
2. prev_tp_same_r 的总收益 9875，几乎等同 max1_base 的 9845；
3. 它远弱于 prev_stop_same_r 的 23905；
4. 因此当前第 2/3 笔的有效来源不是“盈利后顺势加仓”，而是“失败试探后的同方向 retry”。
```

### 16.3 分交易序号

| group | trade_seq | n | wins | losses | net_pnl | avg_pnl | best | cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| prev_stop_same_r | 1 | 85 | 39 | 46 | 9845 | 116 | 4335 | 4635 |
| prev_stop_same_r | 2 | 24 | 15 | 9 | 12900 | 538 | 2175 | 1260 |
| prev_stop_same_r | 3 | 2 | 1 | 1 | 1160 | 580 | 1780 | 120 |
| prev_tp_same_r | 1 | 85 | 39 | 46 | 9845 | 116 | 4335 | 4635 |
| prev_tp_same_r | 2 | 8 | 2 | 6 | -1530 | -191 | 1140 | 450 |
| prev_tp_same_r | 3 | 2 | 2 | 0 | 1560 | 780 | 820 | 120 |

关键观察：

```text
1. 两组第 1 笔完全一致；
2. 差异集中在第 2 笔：
   - stop 后同方向 retry：seq2 净利 12900；
   - take_profit 后同方向再入场：seq2 净利 -1530；
3. 第 3 笔样本都只有 2 笔，不能作为主要判断；
4. 这基本否定了“盈利后继续加仓”作为当前结构主线。
```

### 16.4 分合约结果

| group | symbol | n | wins | losses | net_pnl | avg_pnl | best | cost |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| prev_stop_same_r | DCE.p2505 | 27 | 12 | 15 | 5810 | 215 | 1860 | 1470 |
| prev_stop_same_r | DCE.p2509 | 22 | 11 | 11 | 2665 | 121 | 1935 | 1275 |
| prev_stop_same_r | DCE.p2601 | 29 | 14 | 15 | 5900 | 203 | 4335 | 1560 |
| prev_stop_same_r | DCE.p2605 | 33 | 18 | 15 | 9530 | 289 | 2175 | 1710 |
| prev_tp_same_r | DCE.p2505 | 26 | 10 | 16 | 790 | 30 | 1860 | 1410 |
| prev_tp_same_r | DCE.p2509 | 15 | 7 | 8 | 610 | 41 | 1540 | 870 |
| prev_tp_same_r | DCE.p2601 | 24 | 12 | 12 | 6390 | 266 | 4335 | 1290 |
| prev_tp_same_r | DCE.p2605 | 30 | 14 | 16 | 2085 | 70 | 2020 | 1635 |

不符合预期现象：

```text
1. prev_tp_same_r 在 p2601 上仍然不错，但 p2505 / p2509 / p2605 都明显弱；
2. 尤其 p2505 从 stop_retry 的 5810 降到 790；
3. 说明“盈利后继续做”不是稳定收益来源，甚至可能是在收益已经释放后继续暴露风险。
```

### 16.5 阶段结论

```text
1. 当前 continuation/retry 的核心条件应保留“上一笔 stop_loss 后同方向”；
2. 不应改成“上一笔 take_profit 后同方向”；
3. 这进一步支持：有效第 2 笔不是顺势加仓，而是第一次试探失败后的再确认；
4. 下一步继续沿 prev_stop_same_r 方向做扩样或目标稳健性测试。
```
