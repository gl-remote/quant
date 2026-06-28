# structural-alpha-r5：价值区上下文对照

> 类型：Workbench / 策略研究记录  
> 状态：进行中  
> 分支：`experiment/structural-alpha-r3-value-area-edge`  
> 上游计划：[策略短期研究计划](../roadmap/strategy-short-term-plan.md)  
> 前序研究：[r3 价值区边缘重新接受](./structural-alpha-r3-value-area-edge-reacceptance.md)、[r4 POC 路径质量](./structural-alpha-r4-value-area-poc-path.md)

## 1. 研究动机

r3 / r4 已经发现：

```text
VAH / VAL 重新接受本身不是 alpha；
POC 空间 + price_raw_rr 是有效前置过滤；
继续围绕 min_target_ticks / rr / path_check_bars 调参，已经接近过拟合风险。
```

因此 r5 不继续优化入口参数，而是回到 roadmap 的结构型 alpha 问题：

```text
哪些价值区上下文里，回 POC 这件事本身更成立？
```

本轮把现有 VAH / VAL 重新接受样本加上价值上下文标签，重点观察：

1. 今日开盘相对前日价值区的位置；
2. 前日收盘相对前日价值区的位置；
3. 今日开盘到前日 POC 的距离；
4. 前日收盘到前日 POC 的距离；
5. 今日开盘与前日收盘相对 POC 的关系；
6. 上述关系是否存在明显品种差异。

## 2. 固定基准

本轮不做路径早退，不继续调参，固定使用 r3 / r4 中较有结构含义的前置条件：

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

## 3. 新增上下文标签

在 exit reason 中追加以下标签：

| 标签 | 含义 |
| --- | --- |
| `ol` | 今日开盘相对前日价值区：`above` / `inside` / `below` |
| `cl` | 前日收盘相对前日价值区：`above` / `inside` / `below` |
| `op` | 今日开盘到前日 POC 的距离桶 |
| `cp` | 前日收盘到前日 POC 的距离桶 |
| `ocr` | 前日收盘到今日开盘相对 POC 的方向关系 |

距离桶沿用 r3：

| bucket | 含义 |
| --- | --- |
| `lt6` | 小于 6 ticks |
| `6_8` | 6~8 ticks |
| `8_12` | 8~12 ticks |
| `ge12` | 大于等于 12 ticks |

`ocr` 示例：

| 标签 | 含义 |
| --- | --- |
| `same_above` | 昨收和今开都在 POC 上方 |
| `same_below` | 昨收和今开都在 POC 下方 |
| `above_to_below` | 昨收在 POC 上方，今开在 POC 下方 |
| `at_to_below` | 昨收在 POC，今开在 POC 下方 |

## 4. 基准回测结果

| id | symbol | trades | net pnl | win rate | max drawdown |
| ---: | --- | ---: | ---: | ---: | ---: |
| 341 | `DCE.m2601` | 20 | +1,148.22 | 44.44% | -1,850.74 |
| 342 | `CZCE.SR601` | 22 | +726.75 | 54.55% | -1,103.46 |
| 343 | `SHFE.rb2601` | 22 | -4,946.94 | 45.45% | -6,781.51 |
| 344 | `DCE.c2601` | 4 | +187.99 | 100.00% | -93.63 |
| 345 | `DCE.cs2601` | 0 | 0.00 | - | 0.00 |

`DCE.c2601` 和 `DCE.cs2601` 样本过少，只作弱参考。本轮主要观察 `DCE.m2601`、`CZCE.SR601`、`SHFE.rb2601`。

## 5. 开盘位置分桶

| symbol | open location | samples | net after commission | wins | losses | 观察 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `DCE.m2601` | `inside` | 6 | +5,958.51 | 4 | 1 | 最强结构 |
| `DCE.m2601` | `above` | 2 | -1,247.99 | 0 | 2 | 失败 |
| `DCE.m2601` | `below` | 2 | -1,926.35 | 0 | 2 | 失败 |
| `CZCE.SR601` | `above` | 3 | +823.31 | 2 | 1 | 可接受 |
| `CZCE.SR601` | `below` | 1 | +765.56 | 1 | 0 | 样本少但为正 |
| `CZCE.SR601` | `inside` | 7 | +609.54 | 3 | 4 | 可接受但不如 DCE.m 强 |
| `SHFE.rb2601` | `below` | 3 | +95.80 | 2 | 1 | 近似持平 |
| `SHFE.rb2601` | `inside` | 8 | -2,854.04 | 3 | 5 | 明显失败 |

关键观察：

```text
DCE.m2601 的有效性高度集中在“今日开在前日价值区内”；
SR 不只依赖开在价值区内，开在价值区外也可以；
rb 开在价值区内反而明显失败。
```

这说明 r4 看到的品种差异，不只是路径窗口问题，而是价值上下文本身不同。

## 6. 前日收盘位置分桶

| symbol | prev close location | samples | net after commission | wins | losses | 观察 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `DCE.m2601` | `inside` | 9 | +3,013.19 | 4 | 4 | 主要正收益来源 |
| `DCE.m2601` | `above` | 1 | -229.02 | 0 | 1 | 弱参考 |
| `CZCE.SR601` | `inside` | 8 | +1,566.39 | 4 | 4 | 最强 |
| `CZCE.SR601` | `below` | 1 | +765.56 | 1 | 0 | 弱参考 |
| `CZCE.SR601` | `above` | 2 | -133.54 | 1 | 1 | 接近持平 |
| `SHFE.rb2601` | `inside` | 9 | -2,455.27 | 4 | 5 | 仍失败 |
| `SHFE.rb2601` | `below` | 1 | +1,072.28 | 1 | 0 | 弱参考 |
| `SHFE.rb2601` | `above` | 1 | -1,375.25 | 0 | 1 | 弱参考 |

前日收盘在价值区内，对 `DCE.m2601` 和 `CZCE.SR601` 有正面解释；但对 `SHFE.rb2601` 不成立。

## 7. 开盘到 POC 距离

| symbol | open-POC distance | samples | net after commission | wins | losses |
| --- | --- | ---: | ---: | ---: | ---: |
| `DCE.m2601` | `6_8` | 2 | +2,052.22 | 2 | 0 |
| `DCE.m2601` | `lt6` | 3 | +1,143.91 | 1 | 1 |
| `DCE.m2601` | `ge12` | 3 | +1,066.32 | 1 | 2 |
| `DCE.m2601` | `8_12` | 2 | -1,478.28 | 0 | 2 |
| `CZCE.SR601` | `ge12` | 4 | +1,717.53 | 3 | 1 |
| `CZCE.SR601` | `lt6` | 4 | +433.27 | 2 | 2 |
| `CZCE.SR601` | `8_12` | 2 | +314.39 | 1 | 1 |
| `CZCE.SR601` | `6_8` | 1 | -266.77 | 0 | 1 |
| `SHFE.rb2601` | `ge12` | 8 | -800.09 | 4 | 4 |
| `SHFE.rb2601` | `lt6` | 2 | -1,991.05 | 0 | 2 |
| `SHFE.rb2601` | `8_12` | 1 | +32.91 | 1 | 0 |

开盘到 POC 距离并不是单调越大越好：

```text
DCE.m 偏中等距离最好；
SR 偏远距离更好；
rb 远距离也不能解决失败边界问题。
```

## 8. 开盘位置 + 入场波动率组合

| symbol | open location | volatility bucket | samples | net after commission | wins | losses |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `DCE.m2601` | `inside` | `0_5_1` | 5 | +4,986.95 | 3 | 1 |
| `DCE.m2601` | `inside` | `lt0_5` | 1 | +971.56 | 1 | 0 |
| `DCE.m2601` | `above` | `1_1_5` | 1 | -1,018.97 | 0 | 1 |
| `DCE.m2601` | `below` | `0_5_1` | 1 | -1,467.04 | 0 | 1 |
| `CZCE.SR601` | `inside` | `lt0_5` | 5 | +480.99 | 2 | 3 |
| `CZCE.SR601` | `inside` | `0_5_1` | 2 | +128.55 | 1 | 1 |
| `CZCE.SR601` | `above` | `ge1_5` | 1 | +956.85 | 1 | 0 |
| `CZCE.SR601` | `below` | `lt0_5` | 1 | +765.56 | 1 | 0 |
| `SHFE.rb2601` | `inside` | `0_5_1` | 4 | -1,525.40 | 1 | 3 |
| `SHFE.rb2601` | `inside` | `lt0_5` | 4 | -1,328.64 | 2 | 2 |
| `SHFE.rb2601` | `below` | `0_5_1` | 2 | -323.65 | 1 | 1 |
| `SHFE.rb2601` | `below` | `lt0_5` | 1 | +419.46 | 1 | 0 |

组合观察进一步支持：

```text
DCE.m 的强结构 = 今日开在前日价值区内 + 入场 bar 中低波动；
SR 的结构更慢，低波动更重要，开盘位置不是唯一解释；
rb 的问题不是通过开盘位置或入场波动率能解决。
```

## 9. exit reason 诊断

`DCE.m2601` 的 `inside + 0_5_1`：

| exit reason | samples | net after commission |
| --- | ---: | ---: |
| `take_profit` | 3 | +5,204.72 |
| `time_exit` | 2 | -217.77 |

说明 DCE.m 在该上下文中，POC 命中收益足以覆盖少量时间退出。

`CZCE.SR601` 的 `inside + lt0_5`：

| exit reason | samples | net after commission |
| --- | ---: | ---: |
| `take_profit` | 1 | +557.54 |
| `time_exit` | 4 | -76.55 |

说明 SR 的慢路径可以被接受，时间退出并不致命。

`SHFE.rb2601` 的 `inside + 0_5_1`：

| exit reason | samples | net after commission |
| --- | ---: | ---: |
| `take_profit` | 1 | +940.48 |
| `strict_failure_close` | 1 | -1,375.25 |
| `force_flat` | 1 | -615.80 |
| `time_exit` | 1 | -474.83 |

说明 rb 即使能命中 POC，也会被 strict failure / force flat / time exit 吞噬。

## 10. 阶段结论

r5 初步证明，继续调路径参数不如切换到价值上下文研究。

当前最有解释力的结构不是：

```text
VAH / VAL 重新接受后，几根 bar 内是否推进 N ticks
```

而是：

```text
今日开盘是否仍在昨日价值区语境内；
前日收盘是否仍在昨日价值区语境内；
该品种对“回 POC”的路径容忍度和失败边界质量如何。
```

阶段性判断：

| 品种 | 判断 |
| --- | --- |
| `DCE.m2601` | 值得继续：优先研究 `open inside previous VA + 中低入场波动 + 回 POC` |
| `CZCE.SR601` | 值得继续：优先研究 `低入场波动 + 慢路径回 POC`，不强制早退 |
| `SHFE.rb2601` | 暂停回 POC 结构：先研究 strict failure 为什么吞噬收益 |
| `DCE.c2601` / `DCE.cs2601` | 样本不足，暂不作为判断依据 |

r5 不是把上下文直接当成新参数过滤，而是把研究对象从“入口调参”推进到：

```text
哪些价值上下文中，POC 作为短期盈利上界更可信？
```

## 11. 下一步

不建议继续扩大参数搜索。下一步应做最小结构对照：

1. `DCE.m2601`：固定 `open inside previous VA`，验证 POC 命中是否稳定覆盖 time exit；
2. `CZCE.SR601`：固定低入场波动，允许慢路径，验证 time exit 是否长期可控；
3. `SHFE.rb2601`：单独拆 strict failure 样本，判断是失败边界过近、价值区不适用，还是品种日内结构不同；
4. 增加“开盘区间边界 + VAH/VAL”共振诊断，避免只围绕前日价值区内部继续过拟合。
