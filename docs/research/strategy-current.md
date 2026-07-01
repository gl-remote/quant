# 策略当前研究进度

> 类型：Research / 当前策略研究状态
> 状态：活跃 / R28 结构诊断后形成 DCE.p continuation 候选，准备扩样复验
> 最近更新：2026-07-02
> 当前工作台：[R28 value_area_reacceptance 结构诊断](../workbench/value-area-reacceptance-r28-structure-diagnosis.md)
> 前置扩样：[R27 扩样复验](../workbench/value-area-reacceptance-r27-expanded-sample.md)
> 长期框架：[策略长期共识：共识价格区间下的账户风险结构塑形框架](../roadmap/strategy-research-framework.md)

## 1. 当前一句话结论

```text
主线仍是 value_area_reacceptance，但旧 m/SR 单笔 POC 回归候选已降级。

R27 外推后，当前更值得继续验证的是：
DCE.p + 1m + VA reacceptance 首笔 POC 目标 + 失败后同方向 continuation/retry。

保守扩样参数先固定 reentry_take_profit_r=1.3，
不继续在 DCE.p 小样本内细调 1.3 / 1.35 / 1.4，避免过拟合。
```

边界：

```text
1. 当前结论主要来自 DCE.p 四个样本，不是最终上线规则；
2. continuation/retry 是否能外推到其他 p 合约、其他品种、其他月份仍未验证；
3. m/SR 旧候选保留为历史对照，不再作为当前最强主候选；
4. ATR / volatility normalization 保留为泛化候选变量，暂不并入主规则。
```

## 2. 当前主题

| 主题 | 状态 | 文档 |
| --- | --- | --- |
| value_area_reacceptance | 主线 / R28 结构诊断形成 continuation 候选 / 准备扩样 | [value-area-reacceptance.md](./themes/value-area-reacceptance.md) |

## 3. 当前候选结构

当前准备扩样的候选：

```text
value_area_reacceptance
+ 1m execution
+ previous-day close-profile VA / POC
+ min_reaccept_ticks = 3
+ stop_widen_multiplier = 1.0
+ min_price_raw_rr = 0.8
+ strict_close_exit = true
+ max_trades_per_day = 3
+ reentry_cooldown_minutes = 15
+ reentry_requires_prev_stop_same_direction = true
+ first trade: POC target with target_distance_ratio = 0.8
+ reentry trade: fixed R target, conservative reentry_take_profit_r = 1.3
```

候选参数：

```text
strategy = value_area_reacceptance
engine = vnpy
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
primary expansion symbols = DCE.p contracts first
```

目标口径说明：

```text
target_distance_ratio / target_band_ticks 只作用于第 1 笔 POC 目标；
reentry_take_profit_r 直接决定第 2/3 笔 R 目标，不再被 POC 目标缩放参数影响。
```

## 4. 最近关键结论

### 4.1 R27 扩样后的降级

```text
旧候选 m/SR + 1m + A4_ratio_80 在外推样本中没有形成足够稳定收益；
不能继续把它当作主候选硬推。

DCE.p 是目前更清晰的正向结构来源，但仍可能是品种 / 月份拟合，必须扩样验证。
```

### 4.2 R28 结构诊断

```text
单笔 VA reacceptance 的收益有限；
放开每日最多 3 笔后，收益主要来自第 2 笔；
第 1 笔和第 2/3 笔更像两套不同结构：
- 第 1 笔：VA reacceptance / 价值回归；
- 第 2/3 笔：failed-probe continuation / 方向确认。
```

### 4.3 reentry R 目标稳健性

在 DCE.p 四样本、固定：

```text
max_trades_per_day = 3
reentry_cooldown_minutes = 15
reentry_requires_prev_stop_same_direction = true
```

目标对照：

| reentry target | n | win_pct | net_pnl | avg_pnl | cost |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1.0R | 111 | 50.5 | 23165 | 209 | 6015 |
| 1.2R | 111 | 49.5 | 23905 | 215 | 6015 |
| 1.35R | 111 | 49.5 | 24925 | 225 | 6015 |
| 1.5R | 111 | 48.6 | 20025 | 180 | 6015 |

当前判断：

```text
1.0R / 1.2R / 1.35R 都明显优于 max1_base，说明不是单点偶然；
1.35R 当前最高，但继续细调 1.3 / 1.4 会增加过拟合风险；
因此扩样先用更保守的 1.3R。
```

## 5. 当前不建议继续的方向

```text
1. 不在 DCE.p 四样本里继续细调 reentry_take_profit_r；
2. 不把 1.35R 当前最高值直接当成最终最优参数；
3. 不回到旧 m/SR 单笔 POC 候选继续硬调；
4. 不直接启用 ATR 过滤或 ATR stop 作为主规则；
5. 不把第 3 笔作为主要判断依据，目前 seq3 样本太少；
6. 不继续切更细标签桶。
```

## 6. 下一步优先级

优先做小批量扩样：

```text
1. 固定当前保守候选：reentry_take_profit_r = 1.3；
2. 先扩 DCE.p 的更多合约 / 月份，验证是否仍是稳定平台；
3. 每批结束后记录总体、分合约、分 trade_seq 结果；
4. 重点观察第 2 笔是否继续贡献主要收益；
5. 同时记录强趋势、活跃度、异常样本，不强行要求所有时期赚钱。
```

扩样观察指标：

```text
n
win_pct
net_pnl
avg_pnl
worst / best
cost
trade_seq=1/2/3 拆解
分合约稳定性
强趋势 / 非强趋势表现差异
活跃 / thin / suspicious 样本标签
```

阶段判断标准：

```text
如果扩样后第 2 笔 continuation 仍稳定贡献收益，进入跨品种验证；
如果只在当前四个 DCE.p 样本有效，则降级为 DCE.p 局部结构或过拟合线索；
如果收益来自极少数大单，必须继续拆分行情状态，不能直接上线。
```

## 7. 文档地图

| 目的 | 文档 |
| --- | --- |
| 当前状态入口 | 本文件 |
| value_area_reacceptance 主题状态 | [themes/value-area-reacceptance.md](./themes/value-area-reacceptance.md) |
| R28 当前结构诊断 | [value-area-reacceptance-r28-structure-diagnosis.md](../workbench/value-area-reacceptance-r28-structure-diagnosis.md) |
| R27 扩样复验 | [value-area-reacceptance-r27-expanded-sample.md](../workbench/value-area-reacceptance-r27-expanded-sample.md) |
| POC / VA 质量诊断阶段归档 | [value_area_reacceptance POC / VA 质量诊断阶段归档](../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/value-area-reacceptance-quality-summary.md) |
| 长期框架 | [strategy-research-framework.md](../roadmap/strategy-research-framework.md) |

## 8. 给 AI 的工作规则

后续 AI 接手时：

```text
1. 先读本文件；
2. 再读 themes/value-area-reacceptance.md；
3. 需要实验细节时读 R28 workbench；
4. 不要继续小样本调 reentry_take_profit_r；
5. 下一步围绕 reentry_take_profit_r=1.3 做分批扩样；
6. 每批实验写入 docs/workbench；
7. 若发现数据周期、成交配对、成本口径问题，先写 docs/issues 并暂停受影响实验。
```
