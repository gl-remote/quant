# structural-alpha-r8：滚动日内价值区持续性

> 类型：Workbench / 策略研究记录  
> 状态：进行中  
> 分支：`experiment/structural-alpha-r3-value-area-edge`  
> 上游计划：[策略短期研究计划](../roadmap/strategy-short-term-plan.md)  
> 长期框架：[策略长期共识：共识价格区间下的账户风险结构塑形框架](../roadmap/strategy-research-framework.md)  
> 前序研究：[r7 日内高周期价值区持续性](./structural-alpha-r7-intraday-window-value-area.md)

## 1. 研究问题

r7 直接使用 `1h / 2h / 4h` 单根高周期 K 构造 VAH / VAL / POC，结果没有形成有效持续性分层。

本轮修正研究对象：

```text
不用高周期单根 K，
改用最近 N 根 5m K 线构造滚动 volume profile。
```

窗口：

| rolling_context_bars | 含义 |
| ---: | --- |
| 12 | 最近约 1h |
| 24 | 最近约 2h |
| 48 | 最近约 4h |

核心问题：

```text
滚动日内成交分布是否能更好表达筹码堆积 / 共识拥挤？
滚动窗口 VA 重叠、POC 漂移、入场相对窗口位置，
是否能解释前日 VAH / VAL 重新接受后的 POC 回归质量？
```

本轮仍只加诊断标签，不改变入场和退出。

## 2. 固定基准

入口仍使用前日价值区边缘重新接受：

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

逐一加入：

```text
rolling_context_bars = 12 / 24 / 48
```

## 3. 新增滚动窗口标签

| 标签 | 含义 |
| --- | --- |
| `ctx` | `roll12` / `roll24` / `roll48` |
| `ctxloc` | 入场价相对滚动窗口价值区的位置 |
| `ctd` | 入场到滚动窗口 POC 的方向距离 |
| `crr` | 滚动窗口 POC 对应原始 RR |
| `cpb` | 当前滚动窗口与前一个同长度滚动窗口是否重叠：`1b` / `2b` |
| `cov` | 两个滚动窗口 VA overlap |
| `cps` | 滚动窗口 POC stability |

`cpb=2b` 表示：

```text
当前 N 根 5m 的 VA
与前 N 根 5m 的 VA
overlap_ratio >= 0.5
```

## 4. 基准结果

因为只打标签，不过滤，收益结果与原基准一致。

| rolling window | symbol | trades | net pnl | max drawdown |
| --- | --- | ---: | ---: | ---: |
| `roll12` | `DCE.m2601` | 20 | +1,148.22 | -1,850.74 |
| `roll12` | `CZCE.SR601` | 22 | +726.75 | -1,103.46 |
| `roll12` | `SHFE.rb2601` | 22 | -4,946.94 | -6,781.51 |
| `roll24` | `DCE.m2601` | 20 | +1,148.22 | -1,850.74 |
| `roll24` | `CZCE.SR601` | 22 | +726.75 | -1,103.46 |
| `roll24` | `SHFE.rb2601` | 22 | -4,946.94 | -6,781.51 |
| `roll48` | `DCE.m2601` | 20 | +1,148.22 | -1,850.74 |
| `roll48` | `CZCE.SR601` | 22 | +726.75 | -1,103.46 |
| `roll48` | `SHFE.rb2601` | 22 | -4,946.94 | -6,781.51 |

## 5. 滚动窗口持续性 `cpb`

| ctx | symbol | cpb | samples | net after commission | wins | losses |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `roll12` | `DCE.m2601` | `1b` | 7 | +3,181.79 | 3 | 3 |
| `roll12` | `DCE.m2601` | `2b` | 3 | -397.62 | 1 | 2 |
| `roll12` | `CZCE.SR601` | `1b` | 9 | +1,699.63 | 5 | 4 |
| `roll12` | `CZCE.SR601` | `2b` | 2 | +498.79 | 1 | 1 |
| `roll12` | `SHFE.rb2601` | `1b` | 8 | -4,148.97 | 2 | 6 |
| `roll12` | `SHFE.rb2601` | `2b` | 3 | +1,390.74 | 3 | 0 |
| `roll24` | `DCE.m2601` | `1b` | 7 | +2,391.84 | 3 | 3 |
| `roll24` | `DCE.m2601` | `2b` | 3 | +392.33 | 1 | 2 |
| `roll24` | `CZCE.SR601` | `1b` | 7 | +717.35 | 3 | 4 |
| `roll24` | `CZCE.SR601` | `2b` | 4 | +1,481.07 | 3 | 1 |
| `roll24` | `SHFE.rb2601` | `1b` | 7 | -3,650.70 | 3 | 4 |
| `roll24` | `SHFE.rb2601` | `2b` | 4 | +892.46 | 2 | 2 |
| `roll48` | `DCE.m2601` | `1b` | 5 | +2,975.20 | 2 | 3 |
| `roll48` | `DCE.m2601` | `2b` | 5 | -191.03 | 2 | 2 |
| `roll48` | `CZCE.SR601` | `1b` | 5 | +886.76 | 3 | 2 |
| `roll48` | `CZCE.SR601` | `2b` | 6 | +1,311.65 | 3 | 3 |
| `roll48` | `SHFE.rb2601` | `1b` | 8 | -1,186.64 | 4 | 4 |
| `roll48` | `SHFE.rb2601` | `2b` | 3 | -1,571.59 | 1 | 2 |

观察：

```text
滚动窗口终于产生了持续性分层，
但不支持“持续越久越好”的统一结论。
```

分品种看：

- `DCE.m2601`：`cpb=1b` 明显强于 `2b`，更像“新鲜价值 / 新近分布”；
- `CZCE.SR601`：`roll24/roll48` 的 `2b` 更好，支持慢速持续价值；
- `SHFE.rb2601`：`roll12/roll24` 的 `2b` 能减亏甚至转正，但 `roll48` 仍失败。

## 6. POC 稳定性 `cps`

| ctx | symbol | cps | samples | net after commission | wins | losses |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `roll12` | `DCE.m2601` | `drift` | 6 | +3,220.05 | 3 | 3 |
| `roll12` | `DCE.m2601` | `stable` | 3 | -397.62 | 1 | 2 |
| `roll12` | `CZCE.SR601` | `stable` | 4 | +1,123.24 | 3 | 1 |
| `roll12` | `CZCE.SR601` | `mild_drift` | 3 | +1,414.16 | 2 | 1 |
| `roll12` | `CZCE.SR601` | `drift` | 4 | -338.98 | 1 | 3 |
| `roll12` | `SHFE.rb2601` | `stable` | 4 | +490.51 | 3 | 1 |
| `roll12` | `SHFE.rb2601` | `drift` | 5 | -2,272.28 | 1 | 4 |
| `roll24` | `DCE.m2601` | `drift` | 7 | +1,970.79 | 3 | 4 |
| `roll24` | `DCE.m2601` | `stable` | 2 | +851.64 | 1 | 1 |
| `roll24` | `CZCE.SR601` | `stable` | 5 | +1,237.92 | 3 | 2 |
| `roll24` | `CZCE.SR601` | `drift` | 6 | +960.50 | 3 | 3 |
| `roll24` | `SHFE.rb2601` | `stable` | 1 | +1,072.28 | 1 | 0 |
| `roll24` | `SHFE.rb2601` | `drift` | 8 | -3,217.95 | 3 | 5 |
| `roll48` | `DCE.m2601` | `drift` | 4 | +3,434.51 | 2 | 2 |
| `roll48` | `DCE.m2601` | `stable` | 5 | +816.69 | 2 | 2 |
| `roll48` | `CZCE.SR601` | `drift` | 9 | +2,203.30 | 5 | 4 |
| `roll48` | `SHFE.rb2601` | `drift` | 11 | -2,758.24 | 5 | 6 |

观察：

```text
POC stable 不是统一优势。
```

更像：

- `DCE.m2601`：POC 漂移反而更好，说明它可能吃的是新鲜分布变化后的回归；
- `CZCE.SR601`：`roll12 stable/mild_drift`、`roll24 stable` 都可接受，更符合慢速价值接受；
- `SHFE.rb2601`：短窗口 stable 能改善，但样本少，不能修复整体结构。

## 7. 入场相对滚动价值区位置 `ctxloc`

| ctx | symbol | ctxloc | samples | net after commission | wins | losses |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `roll12` | `DCE.m2601` | `above` | 1 | +2,762.37 | 1 | 0 |
| `roll12` | `DCE.m2601` | `inside` | 7 | -720.74 | 2 | 4 |
| `roll12` | `CZCE.SR601` | `inside` | 8 | +989.81 | 4 | 4 |
| `roll12` | `SHFE.rb2601` | `above` | 6 | -2,275.45 | 3 | 3 |
| `roll24` | `DCE.m2601` | `inside` | 8 | +1,932.53 | 3 | 4 |
| `roll24` | `CZCE.SR601` | `below` | 5 | +1,032.36 | 3 | 2 |
| `roll24` | `CZCE.SR601` | `inside` | 5 | +400.49 | 2 | 3 |
| `roll24` | `SHFE.rb2601` | `inside` | 11 | -2,758.24 | 5 | 6 |
| `roll48` | `DCE.m2601` | `above` | 4 | +2,115.47 | 2 | 1 |
| `roll48` | `DCE.m2601` | `inside` | 5 | -411.96 | 1 | 4 |
| `roll48` | `CZCE.SR601` | `inside` | 9 | +1,365.95 | 4 | 5 |
| `roll48` | `SHFE.rb2601` | `inside` | 11 | -2,758.24 | 5 | 6 |

观察：

```text
滚动价值区位置关系有信息，但品种差异很强。
```

`DCE.m2601` 更像在滚动价值区外侧产生回归 / 压力释放；`CZCE.SR601` 更能接受在滚动价值区内部慢回归；`SHFE.rb2601` 即使 inside 也失败。

## 8. 滚动 POC 距离 / RR

多数交易对滚动 POC 的方向距离仍很近：

```text
ctd = lt6
crr = lt0_5
```

代表：

```text
滚动 POC 不适合直接替代前日 POC 作为盈利目标。
```

但它作为背景状态有一定解释力，尤其是：

```text
窗口是否重叠、POC 是稳定还是漂移、入场在窗口内还是外侧。
```

## 9. 阶段结论

r8 结论：

```text
滚动日内价值区比 r7 的高周期单 bar 方法更有效，
它确实产生了可观察的持续性 / 稳定性 / 位置分层。
```

但它没有支持一个简单命题：

```text
价值区越持续、POC 越稳定，回 POC 越强。
```

更准确的结构解释是：

```text
DCE.m2601：新鲜滚动价值 / POC 漂移更有利，可能代表新近压力释放；
CZCE.SR601：2h/4h 滚动价值持续更有利，符合慢速价值接受；
SHFE.rb2601：短窗口持续 / stable 可减亏，但整体失败边界质量仍差。
```

因此，滚动价值区方向有研究价值，但不能作为统一过滤器。

## 10. 下一步建议

不建议继续简单调：

```text
rolling_context_bars = 12 / 18 / 24 / 36 / 48
poc_drift threshold
VA overlap threshold
```

更合理的下一步是把品种性格拆开：

1. `DCE.m2601`：研究“新鲜价值区 / POC 漂移后的压力释放”；
2. `CZCE.SR601`：研究“持续滚动价值区内的慢速 POC 回归”；
3. `SHFE.rb2601`：暂停回 POC 主线，单独诊断 strict failure / time exit。

当前阶段判断：

```text
滚动日内价值区通过“作为结构诊断变量”的初筛；
未通过“统一 POC 磁吸过滤器”的标准。
```
