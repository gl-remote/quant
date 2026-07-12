# structural-alpha-r7：日内高周期价值区持续性

> 类型：Workbench / 策略研究记录  
> 状态：进行中  
> 分支：`experiment/structural-alpha-r3-value-area-edge`  
> 上游计划：[策略短期研究计划](../roadmap/strategy-short-term-plan.md)  
> 长期框架：[策略长期共识：共识价格区间下的账户风险结构塑形框架](../roadmap/strategy-research-framework.md)  
> 前序研究：[r6 持续价值区与 POC 共识锚点](./structural-alpha-r6-persistent-value-area.md)

## 1. 研究问题

r6 用“日”为单位验证持续价值区，结果不支持：

```text
价值区持续越久，POC 越强
```

但日级样本太少，且持续价值区可能发生在日内 1h / 2h / 4h 这种窗口级别。

因此 r7 把持续价值区研究从日级切换到日内高周期窗口，验证：

```text
在 1h / 2h / 4h 级别，
价格围绕某个窗口价值区反复接受、POC 稳定，
是否更能解释 VAH / VAL 重新接受后的 POC 回归？
```

本轮仍不把高周期窗口作为过滤，只作为诊断标签。

## 2. 固定基准

入口仍使用原 5m 价值区重新接受，不改交易逻辑：

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
  "min_price_raw_rr": 0.5,
  "context_lookback_bars": 24
}
```

逐一加入诊断周期：

```text
context_period = 1h / 2h / 4h
```

## 3. 新增高周期窗口标签

| 标签 | 含义 |
| --- | --- |
| `ctx` | 高周期上下文：`1h` / `2h` / `4h` |
| `ctxloc` | 入场价相对高周期窗口价值区的位置：`above` / `inside` / `below` |
| `ctd` | 入场价到高周期窗口 POC 的方向有效距离桶 |
| `crr` | 高周期窗口 POC 对应的原始价格盈亏比桶 |
| `cpb` | 高周期窗口连续重叠 bar 数：`1b` / `2b` / `3b_plus` |
| `cov` | 高周期窗口 VA 重叠程度 |
| `cps` | 高周期窗口 POC 稳定性 |

注意：本轮高周期窗口只用于诊断，实际止盈目标仍是原先前日 POC。

## 4. 基准结果

由于只是增加标签，不改变入场和退出，收益结果与 r5/r6 基准一致。

| context | symbol | trades | net pnl | max drawdown |
| --- | --- | ---: | ---: | ---: |
| `1h` | `DCE.m2601` | 20 | +1,148.22 | -1,850.74 |
| `1h` | `CZCE.SR601` | 22 | +726.75 | -1,103.46 |
| `1h` | `SHFE.rb2601` | 22 | -4,946.94 | -6,781.51 |
| `2h` | `DCE.m2601` | 20 | +1,148.22 | -1,850.74 |
| `2h` | `CZCE.SR601` | 22 | +726.75 | -1,103.46 |
| `2h` | `SHFE.rb2601` | 22 | -4,946.94 | -6,781.51 |
| `4h` | `DCE.m2601` | 20 | +1,148.22 | -1,850.74 |
| `4h` | `CZCE.SR601` | 22 | +726.75 | -1,103.46 |
| `4h` | `SHFE.rb2601` | 22 | -4,946.94 | -6,781.51 |

## 5. 高周期持续性结果

### 5.1 连续重叠 bar 数

| context | symbol | cpb | samples | net after commission | wins | losses |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `1h` | `DCE.m2601` | `1b` | 10 | +2,784.17 | 4 | 5 |
| `1h` | `CZCE.SR601` | `1b` | 11 | +2,198.42 | 6 | 5 |
| `1h` | `SHFE.rb2601` | `1b` | 11 | -2,758.24 | 5 | 6 |
| `2h` | `DCE.m2601` | `1b` | 10 | +2,784.17 | 4 | 5 |
| `2h` | `CZCE.SR601` | `1b` | 11 | +2,198.42 | 6 | 5 |
| `2h` | `SHFE.rb2601` | `1b` | 11 | -2,758.24 | 5 | 6 |
| `4h` | `DCE.m2601` | `1b` | 10 | +2,784.17 | 4 | 5 |
| `4h` | `CZCE.SR601` | `1b` | 11 | +2,198.42 | 6 | 5 |
| `4h` | `SHFE.rb2601` | `1b` | 11 | -2,758.24 | 5 | 6 |

观察：

```text
1h / 2h / 4h 的高周期窗口没有形成 2b / 3b+ 的有效分层。
```

这说明在当前实现和样本里，高周期单 bar 价值区之间并没有连续重叠到足以形成持续性标签。原因可能是：

1. 单根 1h / 2h / 4h bar 构造出的 VA 太窄；
2. 当前用单 bar 的高低 / close profile 近似窗口价值区，表达力不足；
3. 5m 入口发生时，高周期视图里的已完成 bars 太少或太离散；
4. 真正的日内价值区应使用滚动多根 5m bar 聚合，而不是高周期单根 bar 对比。

### 5.2 POC 稳定性

| context | symbol | cps | samples | net after commission | wins | losses |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `1h` | `DCE.m2601` | `stable` | 10 | +2,784.17 | 4 | 5 |
| `1h` | `CZCE.SR601` | `stable` | 11 | +2,198.42 | 6 | 5 |
| `1h` | `SHFE.rb2601` | `stable` | 11 | -2,758.24 | 5 | 6 |
| `2h` | `DCE.m2601` | `stable` | 10 | +2,784.17 | 4 | 5 |
| `2h` | `CZCE.SR601` | `stable` | 11 | +2,198.42 | 6 | 5 |
| `2h` | `SHFE.rb2601` | `stable` | 11 | -2,758.24 | 5 | 6 |
| `4h` | `DCE.m2601` | `stable` | 10 | +2,784.17 | 4 | 5 |
| `4h` | `CZCE.SR601` | `stable` | 11 | +2,198.42 | 6 | 5 |
| `4h` | `SHFE.rb2601` | `stable` | 11 | -2,758.24 | 5 | 6 |

观察：

```text
高周期 POC stable 没有区分力。
```

所有样本几乎都被标为 stable，这个标签当前不可用。

## 6. 高周期位置关系

高周期持续性没有形成分层，但 `ctxloc` 有少量信息。

### 6.1 1h / 2h

`1h` 与 `2h` 结果完全一致：

| context | symbol | ctxloc | samples | net after commission | wins | losses |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `1h/2h` | `DCE.m2601` | `above` | 6 | +1,420.28 | 2 | 3 |
| `1h/2h` | `DCE.m2601` | `below` | 4 | +1,363.89 | 2 | 2 |
| `1h/2h` | `CZCE.SR601` | `above` | 4 | +1,741.07 | 3 | 1 |
| `1h/2h` | `CZCE.SR601` | `below` | 7 | +457.34 | 3 | 4 |
| `1h/2h` | `SHFE.rb2601` | `above` | 8 | -770.43 | 4 | 4 |
| `1h/2h` | `SHFE.rb2601` | `below` | 2 | -2,020.71 | 0 | 2 |
| `1h/2h` | `SHFE.rb2601` | `inside` | 1 | +32.91 | 1 | 0 |

### 6.2 4h

| context | symbol | ctxloc | samples | net after commission | wins | losses |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `4h` | `DCE.m2601` | `above` | 8 | +3,472.50 | 4 | 3 |
| `4h` | `DCE.m2601` | `below` | 2 | -688.33 | 0 | 2 |
| `4h` | `CZCE.SR601` | `above` | 6 | +1,359.80 | 3 | 3 |
| `4h` | `CZCE.SR601` | `below` | 5 | +838.61 | 3 | 2 |
| `4h` | `SHFE.rb2601` | `above` | 6 | -1,095.11 | 3 | 3 |
| `4h` | `SHFE.rb2601` | `below` | 4 | -1,696.03 | 1 | 3 |
| `4h` | `SHFE.rb2601` | `inside` | 1 | +32.91 | 1 | 0 |

观察：

```text
DCE.m 在 4h 窗口中，入场价位于 4h 价值区上方时表现最好；
SR 两侧都可接受；
rb 仍然失败。
```

但这还不能解释为持续价值区，只能说明高周期位置关系可能有背景信息。

## 7. 高周期 POC 距离 / RR

### 7.1 目标距离 `ctd`

大部分交易的高周期 POC 有效方向距离都很近：

| context | symbol | ctd | samples | net after commission |
| --- | --- | --- | ---: | ---: |
| `1h` | `DCE.m2601` | `lt6` | 9 | +2,963.67 |
| `1h` | `CZCE.SR601` | `lt6` | 10 | +1,585.45 |
| `1h` | `SHFE.rb2601` | `lt6` | 9 | -2,323.48 |
| `4h` | `DCE.m2601` | `lt6` | 9 | +2,963.67 |
| `4h` | `CZCE.SR601` | `lt6` | 9 | +1,828.60 |
| `4h` | `SHFE.rb2601` | `lt6` | 9 | -908.16 |

说明：

```text
高周期窗口 POC 当前不是可用的盈利上界。
```

它更多像背景位置，而不是目标价。

### 7.2 高周期 RR `crr`

多数高周期 POC 对应 `crr < 0.5`，但在 `DCE.m` 和 `SR` 上仍为正：

| context | symbol | crr | samples | net after commission |
| --- | --- | --- | ---: | ---: |
| `1h` | `DCE.m2601` | `lt0_5` | 7 | +4,441.95 |
| `1h` | `CZCE.SR601` | `lt0_5` | 9 | +862.59 |
| `1h` | `SHFE.rb2601` | `lt0_5` | 9 | -2,323.48 |
| `4h` | `DCE.m2601` | `lt0_5` | 8 | +3,982.64 |
| `4h` | `CZCE.SR601` | `lt0_5` | 8 | +1,105.74 |
| `4h` | `SHFE.rb2601` | `lt0_5` | 9 | -908.16 |

这进一步说明：

```text
高周期 POC 不是本轮交易的主要盈利目标；
收益仍来自原前日 POC 结构。
```

## 8. 阶段结论

r7 结论：

```text
把持续价值区从日级换成 1h / 2h / 4h 后，
仍没有直接证明“持续越久，POC 越强”。
```

更具体：

1. 高周期 `cpb` 全部落在 `1b`，没有形成持续性分层；
2. 高周期 `cps` 几乎全是 stable，没有区分力；
3. 高周期 POC 距离多数太近，不适合作为盈利上界；
4. `4h ctxloc` 对 `DCE.m` 有一定背景解释力，但不是持续价值区证据；
5. `SHFE.rb2601` 仍失败，说明高周期价值区标签不能修复失败边界质量问题。

因此，当前实现下：

```text
日内高周期单 bar 价值区 ≠ 有效的持续价值区研究对象。
```

## 9. 重要方法问题

这轮暴露出一个方法问题：

```text
直接用 1h / 2h / 4h 单根聚合 bar 的 VAH / VAL / POC，
不能很好表达“筹码堆积 / 价值区持续”。
```

更合理的研究对象应该是：

```text
滚动窗口 volume profile：
最近 12 根 5m = 1h
最近 24 根 5m = 2h
最近 48 根 5m = 4h
```

而不是：

```text
高周期单根 bar profile。
```

因为“持续价值区”本质上是多根 bar 的成交分布稳定性，不是单根高周期 K 的高低收统计。

## 10. 下一步建议

不建议继续在 `context_period=1h/2h/4h` 这套单 bar 高周期标签上调。

如果继续验证你的直觉，应改成：

```text
structural-alpha-r8-rolling-intraday-value-area
```

核心改动：

```text
用 5m 滚动窗口构造 1h / 2h / 4h volume profile，
比较相邻滚动窗口的 VA 重叠、POC 漂移、价格离开 / 回归质量。
```

这才更接近长期框架里的：

```text
特殊价格区域
→ 筹码堆积
→ 共识拥挤
→ 压力释放 / 回归
```

当前 r7 阶段判断：

```text
想法仍值得保留；
当前 1h/2h/4h 单 bar 实现不适合作为证据；
下一轮若继续，应改为滚动日内成交分布，而不是高周期 K 线价值区。
```
