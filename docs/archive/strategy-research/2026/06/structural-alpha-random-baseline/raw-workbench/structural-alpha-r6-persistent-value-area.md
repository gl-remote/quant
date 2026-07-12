# structural-alpha-r6：持续价值区与 POC 共识锚点

> 类型：Workbench / 策略研究记录  
> 状态：进行中  
> 分支：`experiment/structural-alpha-r3-value-area-edge`  
> 上游计划：[策略短期研究计划](../roadmap/strategy-short-term-plan.md)  
> 长期框架：[策略长期共识：共识价格区间下的账户风险结构塑形框架](../roadmap/strategy-research-framework.md)  
> 前序研究：[r5 价值区上下文对照](./structural-alpha-r5-value-context-comparison.md)

## 1. 研究问题

r5 发现，单日 VAH / VAL 重新接受的收益更像来自价值上下文，而不是入口参数本身。

本轮进一步验证一个更贴合长期框架的结构命题：

```text
价值区持续时间越长、POC 越稳定，
是否说明该区域形成更强市场共识 / 筹码堆积，
从而让 POC 作为短期盈利上界更可靠？
```

这对应长期框架中的市场行为假说：

```text
特殊价格区间
→ 共识拥挤
→ 试探性交易、止损单和突破追单堆积
→ 假突破、反复穿越、快速回撤
→ 压力释放后形成短期动能或回归
```

r6 不继续调入口参数，只给现有样本增加持续价值区标签，观察收益是否集中在多日价值共识中。

## 2. 固定基准

沿用 r5 固定基准，不加路径早退，不加新过滤：

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

## 3. 新增持续价值区标签

### 3.1 持续天数 `pd`

根据连续价值区重叠判断：

```text
当前前日 VA 与更早一日 VA 的 overlap_ratio >= 0.5
```

若连续满足，则持续天数增加。

| bucket | 含义 |
| --- | --- |
| `1d` | 只确认单日前日价值区 |
| `2d` | 连续 2 天价值区明显重叠 |
| `3d_plus` | 连续 3 天以上明显重叠 |

### 3.2 重叠程度 `ov`

```text
overlap_ratio = 两个 VA 重叠长度 / 当前 VA 宽度
```

| bucket | 含义 |
| --- | --- |
| `low` | < 0.5 |
| `mid` | 0.5~0.8 |
| `high` | >= 0.8 |

### 3.3 POC 稳定性 `ps`

```text
poc_drift = 连续价值区内 POC 最大漂移 ticks
```

| bucket | 含义 |
| --- | --- |
| `stable` | 最大漂移 <= 4 ticks |
| `mild_drift` | 非 stable 但漂移 < 8 ticks |
| `drift` | 漂移 >= 8 ticks |

## 4. 基准回测结果

| id | symbol | trades | net pnl | win rate | max drawdown |
| ---: | --- | ---: | ---: | ---: | ---: |
| 346 | `DCE.m2601` | 20 | +1,148.22 | 44.44% | -1,850.74 |
| 347 | `CZCE.SR601` | 22 | +726.75 | 54.55% | -1,103.46 |
| 348 | `SHFE.rb2601` | 22 | -4,946.94 | 45.45% | -6,781.51 |
| 349 | `DCE.c2601` | 4 | +187.99 | 100.00% | -93.63 |
| 350 | `DCE.cs2601` | 0 | 0.00 | - | 0.00 |

`DCE.c2601` 与 `DCE.cs2601` 样本过少，仅弱参考。

## 5. 持续天数分桶

| symbol | pd | samples | net after commission | wins | losses | 观察 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `DCE.m2601` | `1d` | 7 | +4,189.51 | 3 | 3 | 主要正收益来源 |
| `DCE.m2601` | `2d` | 2 | -2,486.01 | 0 | 2 | 明显失败 |
| `DCE.m2601` | `3d_plus` | 1 | +1,080.66 | 1 | 0 | 样本太少 |
| `CZCE.SR601` | `1d` | 9 | +3,059.50 | 6 | 3 | 主要正收益来源 |
| `CZCE.SR601` | `2d` | 2 | -861.08 | 0 | 2 | 失败 |
| `SHFE.rb2601` | `1d` | 10 | -2,789.04 | 4 | 6 | 仍失败 |
| `SHFE.rb2601` | `2d` | 1 | +30.80 | 1 | 0 | 样本太少 |

关键观察：

```text
本轮不支持“价值区持续越久，POC 效果越强”的简单单调假设。
```

相反，`DCE.m2601` 和 `CZCE.SR601` 的正收益都主要来自 `1d`，`2d` 样本反而为负。`3d_plus` 只有 `DCE.m2601` 1 笔，不能作为证据。

## 6. 重叠程度与 POC 稳定性

### 6.1 VA 重叠程度

| symbol | ov | samples | net after commission | wins | losses |
| --- | --- | ---: | ---: | ---: | ---: |
| `DCE.m2601` | `high` | 7 | +4,189.51 | 3 | 3 |
| `DCE.m2601` | `mid` | 3 | -1,405.34 | 1 | 2 |
| `CZCE.SR601` | `high` | 11 | +2,198.42 | 6 | 5 |
| `SHFE.rb2601` | `high` | 11 | -2,758.24 | 5 | 6 |

VA 高重叠在 `DCE.m2601` 和 `CZCE.SR601` 上为正，但在 `SHFE.rb2601` 上仍为负，说明重叠本身不是充分条件。

### 6.2 POC 稳定性

| symbol | ps | samples | net after commission | wins | losses |
| --- | --- | ---: | ---: | ---: | ---: |
| `DCE.m2601` | `stable` | 9 | +1,703.50 | 3 | 5 |
| `DCE.m2601` | `drift` | 1 | +1,080.66 | 1 | 0 |
| `CZCE.SR601` | `stable` | 10 | +2,792.72 | 6 | 4 |
| `CZCE.SR601` | `drift` | 1 | -594.31 | 0 | 1 |
| `SHFE.rb2601` | `stable` | 10 | -2,789.04 | 4 | 6 |
| `SHFE.rb2601` | `mild_drift` | 1 | +30.80 | 1 | 0 |

`CZCE.SR601` 对 POC 稳定性更敏感；`DCE.m2601` 的收益仍更像来自开盘上下文；`SHFE.rb2601` 即使 POC stable 也不成立。

## 7. 持续天数 + 开盘位置

| symbol | open location | pd | samples | net after commission | wins | losses |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `DCE.m2601` | `inside` | `1d` | 5 | +4,877.84 | 3 | 1 |
| `DCE.m2601` | `inside` | `3d_plus` | 1 | +1,080.66 | 1 | 0 |
| `DCE.m2601` | `above` | `1d` | 1 | -229.02 | 0 | 1 |
| `DCE.m2601` | `above` | `2d` | 1 | -1,018.97 | 0 | 1 |
| `DCE.m2601` | `below` | `1d` | 1 | -459.31 | 0 | 1 |
| `DCE.m2601` | `below` | `2d` | 1 | -1,467.04 | 0 | 1 |
| `CZCE.SR601` | `inside` | `1d` | 5 | +1,470.62 | 3 | 2 |
| `CZCE.SR601` | `inside` | `2d` | 2 | -861.08 | 0 | 2 |
| `CZCE.SR601` | `above` | `1d` | 3 | +823.31 | 2 | 1 |
| `CZCE.SR601` | `below` | `1d` | 1 | +765.56 | 1 | 0 |
| `SHFE.rb2601` | `inside` | `1d` | 7 | -2,884.84 | 2 | 5 |
| `SHFE.rb2601` | `inside` | `2d` | 1 | +30.80 | 1 | 0 |
| `SHFE.rb2601` | `below` | `1d` | 3 | +95.80 | 2 | 1 |

关键结论：

```text
open inside previous VA 的解释力仍强于 persistent days。
```

`DCE.m2601` 的最佳桶仍是：

```text
open inside previous VA + pd=1d
```

而不是多日持续价值区。

## 8. exit reason 诊断

| symbol | pd | exit reason | samples | net after commission |
| --- | --- | --- | ---: | ---: |
| `DCE.m2601` | `1d` | `take_profit` | 2 | +4,124.06 |
| `DCE.m2601` | `1d` | `time_exit` | 4 | -906.10 |
| `DCE.m2601` | `2d` | `strict_failure_close` | 1 | -1,467.04 |
| `DCE.m2601` | `2d` | `time_exit` | 1 | -1,018.97 |
| `DCE.m2601` | `3d_plus` | `take_profit` | 1 | +1,080.66 |
| `CZCE.SR601` | `1d` | `take_profit` | 3 | +2,237.25 |
| `CZCE.SR601` | `1d` | `time_exit` | 5 | +56.69 |
| `CZCE.SR601` | `2d` | `force_flat` | 1 | -594.31 |
| `CZCE.SR601` | `2d` | `time_exit` | 1 | -266.77 |
| `SHFE.rb2601` | `1d` | `take_profit` | 2 | +2,012.76 |
| `SHFE.rb2601` | `1d` | `strict_failure_close` | 2 | -2,771.18 |
| `SHFE.rb2601` | `1d` | `time_exit` | 5 | -1,414.81 |

`DCE.m2601` 和 `CZCE.SR601` 的 `1d` 正收益来自 POC take_profit 足够强，且 time_exit 可承受；`2d` 反而被 strict failure / time_exit 拖累。

## 9. 阶段结论

r6 初步结论：

```text
“持续价值区越久，POC 越强”这个直觉，本轮没有得到直接支持。
```

更准确的解释是：

```text
POC 回归有效，不一定来自多日价值区持续；
更可能来自“昨日价值仍被今日开盘接受，但尚未形成钝化的多日横盘”。
```

也就是说，当前样本更支持：

```text
新近形成的前日价值区
+ 今日开盘仍在该价值区内
+ 边缘假突破后重新接受
→ 回 POC 有效
```

而不是：

```text
价值区持续越久
→ 筹码堆积越强
→ POC 磁吸越强
```

可能原因：

1. 多日价值区持续后，区间可能已经钝化，POC 不再提供足够短期动能；
2. 当前数据中 `2d / 3d+` 样本太少，无法充分验证；
3. 单日 VA 的“昨日价值仍被今天接受”可能比“多日横盘”更适合短持仓回 POC；
4. `SHFE.rb2601` 的失败说明，持续价值区不能修复失败边界质量问题。

## 10. 下一步建议

不建议继续围绕 `persistent_days` 调阈值。

若继续本路线，应转向两个更具体的结构对照：

1. **新鲜价值接受**

```text
前日价值区新近形成
+ 今日开盘仍接受该价值区
+ VAH / VAL 假突破重新接受
```

验证是否优于多日钝化价值区。

2. **价值迁移 vs 价值回归**

```text
如果价值区持续多日后突破，
也许更应该研究“接受新价值区”的迁移，
而不是继续期待回 POC。
```

当前 r6 的阶段判断：

```text
持续价值区不是本轮直接通过的结构变量；
open inside previous VA 仍是更强解释变量；
下一步不应继续调 persistent 阈值，
而应比较“新鲜价值接受”与“多日价值钝化后的迁移”。
```
