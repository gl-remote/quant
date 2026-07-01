# value_area_reacceptance 主题研究现状

> 类型：Research / 主题状态
> 状态：活跃 / R28 结构诊断形成 continuation/retry 候选，准备扩样复验
> 最近更新：2026-07-02
> 当前工作台：[R28 value_area_reacceptance 结构诊断](../../workbench/value-area-reacceptance-r28-structure-diagnosis.md)
> 前置扩样：[R27 扩样复验](../../workbench/value-area-reacceptance-r27-expanded-sample.md)
> 返回总入口：[strategy-current.md](../strategy-current.md)

## 1. 主题一句话结论

```text
value_area_reacceptance 仍是当前主线，但研究重心已经从旧 m/SR 单笔 POC 回归，
转向 DCE.p 上更清晰的 continuation/retry 结构。

当前准备扩样验证的候选是：
首笔吃 VA reacceptance 的 POC 回归；
首笔失败后，等待 15m 冷却，同方向再入场，吃 failed-probe continuation；
reentry 目标先用保守 1.3R，不继续在 DCE.p 小样本内细调。
```

边界：

```text
1. 当前最强证据主要来自 DCE.p 四个样本；
2. 这不是最终上线规则；
3. 旧 m/SR 结论已经降级为历史对照；
4. 需要先扩样确认 continuation/retry 是否能外推。
```

## 2. 当前候选结构

准备扩样的候选版本：

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
+ reentry trade: conservative fixed R target, reentry_take_profit_r = 1.3
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
```

目标口径：

```text
target_distance_ratio / target_band_ticks 只作用于首笔 POC 目标；
reentry_take_profit_r 直接决定第 2/3 笔 R 目标；
两类目标约束已经正交，不能再把 reentry 目标理解为会被 0.8 缩放的 raw target。
```

## 3. 当前交易结构理解

### 3.1 首笔：VA reacceptance / 价值回归

```text
前日 VAL 下破失败后重新接受回价值区内 → 做多；
前日 VAH 上破失败后重新接受回价值区内 → 做空；
等待 1m 收盘价进入价值区内侧至少 3 ticks；
首笔目标仍使用 POC 附近目标，即 entry → POC 距离的 80%。
```

### 3.2 第 2/3 笔：failed-probe continuation / 方向确认

```text
如果上一笔 stop_loss 且方向相同，
说明市场在同一侧反复试探并拒绝原 VA 边界；
等待 15m 冷却后允许再次入场；
第 2/3 笔不再使用 POC 回归目标，而使用固定 R 目标。
```

当前解释：

```text
第 1 笔和第 2/3 笔可能不是同一种钱：
- 第 1 笔是价值区重新接受后的回归收益；
- 第 2/3 笔是多次失败试探后的方向确认收益。
```

## 4. 最近关键结果

### 4.1 R27 扩样后的降级

```text
旧候选：1m + m/SR + A4_ratio_80 + actual RR=0.8 + min_reaccept_ticks=2/3。

R27 外推后，旧候选没有形成足够稳定收益；
因此不能继续围绕 m/SR 单笔 POC 回归硬调。
```

当前保留判断：

```text
旧候选仍说明 VA reacceptance 有结构 alpha 雏形，
但它不是当前最值得扩样的主候选。
```

### 4.2 R28 结构诊断

核心发现：

```text
max_trades_per_day=1 只看首笔，收益有限；
max_trades_per_day=3 后，主要增量来自第 2 笔；
无条件放开重复入场会增加成本和噪音；
“上一笔 stop_loss + 同方向 + 15m 冷却”能更好隔离 continuation/retry 结构。
```

### 4.3 reentry R 目标稳健性

固定结构：

```text
max_trades_per_day = 3
reentry_cooldown_minutes = 15
reentry_requires_prev_stop_same_direction = true
```

DCE.p 四样本对照：

| reentry target | n | wins | losses | win_pct | net_pnl | avg_pnl | worst | best | cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1.0R | 111 | 56 | 55 | 50.5 | 23165 | 209 | -2205 | 4335 | 6015 |
| 1.2R | 111 | 55 | 56 | 49.5 | 23905 | 215 | -2205 | 4335 | 6015 |
| 1.35R | 111 | 55 | 56 | 49.5 | 24925 | 225 | -2205 | 4335 | 6015 |
| 1.5R | 111 | 54 | 57 | 48.6 | 20025 | 180 | -2205 | 4335 | 6015 |

分交易序号：

| target | seq1 net_pnl | seq2 net_pnl | seq3 net_pnl |
| --- | ---: | ---: | ---: |
| 1.0R | 9845 | 12560 | 760 |
| 1.2R | 9845 | 12900 | 1160 |
| 1.35R | 9845 | 13440 | 1640 |
| 1.5R | 9845 | 8540 | 1640 |

当前判断：

```text
1.0R / 1.2R / 1.35R 构成较稳定平台；
1.35R 当前最高，但不应继续在当前四样本精调；
1.5R 明显回落，说明目标过远会牺牲第 2 笔；
seq3 只有 2 笔，不作为主判断。
```

因此下一轮扩样使用：

```text
reentry_take_profit_r = 1.3
```

## 5. POC / VA 定义

当前仍使用前一交易日 close-profile：

```text
profile: price -> accumulated volume
```

POC：

```text
成交量最大的 price bucket；
并列时选择离 session close 更近的价格。
```

VAH / VAL：

```text
从 POC 开始，按相邻 bucket 成交量贪婪扩展，
直到覆盖 value_area_ratio=70% 的成交量。
```

当前判断：

```text
close-profile POC 并非完全错误；
但 continuation/retry 分支中，第 2/3 笔不应该继续使用 POC 作为目标。
```

## 6. ATR / volatility normalization 状态

```text
ATR 可能在解决过拟合、提升泛化时发挥作用；
尤其可用于 stop boundary normalization 或 ATR-ratio entry filter。
```

当前处理：

```text
保留为后续泛化变量；
暂不并入当前扩样主规则；
先验证 continuation/retry 结构本身是否外推。
```

## 7. 当前不建议继续的方向

| 方向 | 当前处理 | 原因 |
| --- | --- | --- |
| DCE.p 内继续细调 1.3 / 1.35 / 1.4 | 暂停 | 当前差异已足够，继续调参易过拟合 |
| 直接采用 1.35R 为最终最优 | 暂停 | 只在四样本最高，需要扩样验证 |
| 回到旧 m/SR 单笔 POC 候选硬调 | 暂停 | R27 外推表现不足 |
| 无条件 max3 重复入场 | 暂停 | 成本和噪音增加，结构不够纯 |
| 上一笔 take_profit 后同方向再入场 | 暂停 | 对照结果接近退回 max1，未支持 continuation 假设 |
| ATR 过滤直接入主规则 | 暂缓 | 更适合后续泛化验证，不应现在混入主效应 |
| edge_or_away 真实过滤 | 暂缓 | 旧口径强，当前结构下未重新证明 |
| range-profile 替换 close-profile | 暂缓 | 当前主问题不是 profile 替换 |

## 8. 下一阶段待验证

下一步应扩样验证当前 continuation/retry 候选，而不是继续当前小样本调参。

固定候选：

```text
period = 1m
profile_mode = close
min_reaccept_ticks = 3
stop_widen_multiplier = 1.0
min_price_raw_rr = 0.8
max_trades_per_day = 3
reentry_cooldown_minutes = 15
reentry_requires_prev_stop_same_direction = true
reentry_take_profit_r = 1.3
```

扩样顺序：

```text
1. 先扩 DCE.p 更多合约 / 月份；
2. 如果仍稳定，再扩到相近油脂油料或其他候选品种；
3. 每批结束后记录总体、分合约、分 trade_seq；
4. 同步标注强趋势、活跃度、异常数据；
5. 不强求所有时期赚钱，重点看赚钱时期是否稳定、亏损时期是否可解释。
```

观察指标：

```text
n
win_pct
net_pnl
avg_pnl
worst / best
cost
trade_seq=1/2/3 拆解
分合约稳定性
第 2 笔 continuation 是否继续贡献主要收益
强趋势 / 非强趋势差异
活跃 / thin / suspicious 样本标签
```

通过标准：

```text
1. 扩样后总收益仍为正；
2. 第 2 笔 continuation 仍是主要增量来源；
3. 收益不是完全来自单个合约或极少数大单；
4. 成本增加后仍有净优势；
5. 失败样本能被行情状态、活跃度或结构条件解释。
```

如果扩样失败：

```text
将 continuation/retry 降级为 DCE.p 局部线索或过拟合；
回到结构归因，而不是继续调 reentry_take_profit_r。
```

## 9. 关联文档

| 目的 | 文档 |
| --- | --- |
| 总入口 | [strategy-current.md](../strategy-current.md) |
| R28 当前结构诊断 | [value-area-reacceptance-r28-structure-diagnosis.md](../../workbench/value-area-reacceptance-r28-structure-diagnosis.md) |
| R27 扩样复验 | [value-area-reacceptance-r27-expanded-sample.md](../../workbench/value-area-reacceptance-r27-expanded-sample.md) |
| POC / VA 质量诊断阶段归档 | [value_area_reacceptance POC / VA 质量诊断阶段归档](../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/value-area-reacceptance-quality-summary.md) |
| R16-R24 actual RR 重整 | [value-area-reacceptance-r16-r24-1m-actual-rr-summary.md](../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r16-r24-1m-actual-rr-summary.md) |
| R25 1m vs 5m | [value-area-reacceptance-r25-1m-vs-5m-actual-rr.md](../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r25-1m-vs-5m-actual-rr.md) |
| R26 稳定性检查 | [value-area-reacceptance-r26-1m-stability-check.md](../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r26-1m-stability-check.md) |
