# 价值区 VAH / VAL 重新接受深耕摘要

> 类型：Archive / 实验摘要  
> 阶段主题：structural-alpha-random-baseline  
> 状态：已归档  
> 结题报告：[结构型 Alpha 随机对照阶段结题报告](./structural-alpha-stage-final-report.md)

## 1. 深耕背景

随机对照显示：

```text
价值区 VAH / VAL 重新接受方向假设有明显信息；
但原始入场 / strict failure 风险空间没有显著优于同方向随机。
```

因此深耕目标不是寻找新入口，而是验证：

```text
能否通过接受质量、风险空间和时间退出诊断，
把方向 edge 转化为更稳定的结构优势。
```

## 2. 固定基础结构

基础结构：

```text
前日 VAH 上破失败后重新跌回价值区内 → 做空，目标 POC；
前日 VAL 下破失败后重新收回价值区内 → 做多，目标 POC。
```

基础参数：

```text
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

## 3. 深度重新接受

最重要发现：

```text
不要在刚刚收回 VAH / VAL 时立刻进；
等待 5m K 线收盘价重新收回价值区内侧 2~3 ticks，
能显著改善风险空间质量。
```

注意：这里不是逐笔 tick 确认，而是：

```text
5m 收盘价重新接受到边界内侧 2~3 个最小变动价位。
```

DCE.m2601 上 `min_reaccept_ticks = 2` 改善最明确：

```text
收益提高；
胜率提高；
MAE 下降；
MFE 上升；
最大单亏下降；
亏损簇变浅；
成本 / 平均盈利下降。
```

SR601 上 `2~3 ticks` 同样有价值，但机制不同：

```text
2 ticks 更偏胜率优势；
3 ticks 对尾部风险更友好。
```

因此不能把 `2 ticks` 当作最终参数，应理解为：

```text
重新接受需要最小确认深度。
```

后续应测试更鲁棒表达：

```text
reaccept_depth >= x * ATR；
reaccept_depth >= y% * previous_value_area_width；
reaccept_close_position 位于价值区内侧某个分位。
```

## 4. 机制诊断

DCE.m2601 上，`min_reaccept_ticks = 2` 相比 `1 tick`：

```text
平均 MAE: 5.30 → 4.00 ticks；
平均 MFE: 7.90 → 9.83 ticks；
最大单亏: -1430 → -420；
最大连亏: 2 → 1；
最差亏损簇: -1430 → -420；
成本/平均盈利: 1.26 → 0.64；
strict failure: 1 → 0。
```

这说明改善不是简单减少交易，而是边界接受质量和风险空间同时改善。

SR601 上 `3 ticks` 对尾部风险改善更明显，但样本偏少，需要后续品种适配研究。

## 5. time_exit 与 POC 兑现

time_exit 诊断结论：

```text
time_exit 不是大量“接近 POC 后没卖导致回吐”；
多数 time_exit 的 MFE 不足以接近 POC；
简单延长 max_hold_bars 到 18/24 会放大左尾风险；
12 bars 附近是当前较合理持仓窗口。
```

因此当前不应简单延长时间退出。

退出策略本身有价值，但本阶段不继续深耕。后续可研究：

```text
partial_target_ratio = 0.3 / 0.5 / 0.7 of POC distance；
take_profit_r = 0.5 / 0.75 / 1.0；
MFE 回撤退出；
time_exit 前小 MFE 主动兑现。
```

## 6. 当前主线版本

阶段结束时，价值区主线保留为：

```text
value_area_reacceptance
+ POC 空间
+ price_raw_rr 预筛
+ min_reaccept_ticks 2~3
+ max_hold_bars ≈ 12
```

但它仍不是可上线策略，下一阶段必须补证：

```text
2%~3% 单次账户风险预算；
合约乘数、最小手数和实际仓位；
滑点、跳空和 force_flat 左尾；
DCE.m 与 SR 的品种适配；
min_reaccept_ticks 的波动归一表达；
最大单亏和亏损簇；
成本 / 平均盈利安全边际。
```

## 7. 深耕阶段结论

价值区方向不是随机噪声。

更准确地说：

```text
方向层有效；
原始风险空间一般；
重新接受深度可以显著改善风险空间；
退出层影响兑现质量，但本阶段暂缓继续优化；
下一阶段应围绕账户风险、品种适配和尾部风险做正式补证。
```
