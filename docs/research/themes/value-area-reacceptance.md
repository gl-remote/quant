# value_area_reacceptance 主题研究现状

> 类型：Research / 主题状态\
> 状态：活跃 / 阶段收束，等待扩大样本复验\
> 最近更新：2026-07-01\
> 最新阶段归档：[value_area_reacceptance POC / VA 质量诊断阶段归档](../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/value-area-reacceptance-quality-summary.md)\
> 原始记录：[R1~R15 raw-workbench](../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/)\
> 返回总入口：[strategy-current.md](../strategy-current.md)

## 1. 主题一句话结论

```text
value_area_reacceptance 在当前样本中显示出结构 alpha 雏形：
有效交易依赖旧 VA 边界被快速拒绝后，
价格仍能回到一个位置合理、未失效、可兑现的前日 POC / POC band。

当前最强坏结构标签是 edge_or_away，
已进入运行时 would_filter 影子评估，
但还没有完成跨合约、跨月份、更长历史验证。
```

## 2. 当前策略结构

主线版本：

```text
value_area_reacceptance
+ 5m close-profile previous-day POC / VA
+ min_reaccept_ticks 2~3
+ POC target
+ min_target / price_raw_rr 预筛
+ POC 质量诊断标签
+ edge_or_away 影子过滤评估
```

交易结构：

```text
前日 VAL 下破失败后重新接受回价值区内 → 做多，目标 POC；
前日 VAH 上破失败后重新接受回价值区内 → 做空，目标 POC；
入场等待 5m 收盘价进入价值区内侧 2~3 ticks；
只保留到 POC 有足够空间且价格原始盈亏比不太差的样本；
运行时记录 POC 质量标签和 would_filter_edge_or_away。
```

当前不要把 `would_filter_edge_or_away` 当作真实过滤条件。它目前只是影子标签。

## 3. 当前固定参数

主线回测参数：

```text
strategy = value_area_reacceptance
engine = vnpy
execution period = 5m
profile_mode = close
value_area_ratio = 0.7
min_breakout_ticks = 4
failure_buffer_ticks = 1
take_profit_mode = poc
max_hold_bars = 12
stop_widen_multiplier = 1.5
strict_close_exit = true
max_trades_per_day = 1
min_reaccept_ticks = 2 / 3
min_reaccept_va_width_ratio = 0
min_target_ticks = 8
min_price_raw_rr = 0.5
```

这些参数不是最终优化结果，只是当前用于诊断和复验的固定主线配置。

### 3.1 min_target / price_raw_rr 预筛含义

这两个参数只做入场前的空间预筛，不决定方向。

```text
min_target_ticks = 8
```

含义：

```text
entry 到 POC target 的距离至少要有 8 ticks。
如果 POC 离 entry 太近，即使方向正确，也容易被手续费、滑点和噪声吃掉。
```

```text
min_price_raw_rr = 0.5
```

含义：

```text
price_raw_rr = abs(POC - entry) / abs(entry - strict_failure)
```

也就是：

```text
目标价格空间 / 结构失败距离 >= 0.5。
```

它防止的是：

```text
POC 看起来有空间，但为了捕捉这段回归，需要承担过大的结构失败距离。
```

当前这两个参数会把样本自然裁剪到：

```text
entry 到 POC 至少 8 ticks；
风险不能超过目标距离的 2 倍；
保留的是有一定 POC 回归空间、但路径不能过差的样本。
```

### 3.2 failure boundary 当前定义

当前结构失败边界在代码里叫 `strict_failure`。

它不是 VAH / VAL 本身，而是：

```text
假突破过程中的突破极值 ± failure_buffer_ticks。
```

多头：

```text
前日 VAL 下破失败后重新接受做多；
long_breakout_low = 下破期间最低 low；
strict_failure = long_breakout_low - failure_buffer_ticks * price_tick。
```

空头：

```text
前日 VAH 上破失败后重新接受做空；
short_breakout_high = 上破期间最高 high；
strict_failure = short_breakout_high + failure_buffer_ticks * price_tick。
```

当前：

```text
failure_buffer_ticks = 1
```

所以结构失败边界是：

```text
多头：跌破下破极值再多 1 tick；
空头：涨破上破极值再多 1 tick。
```

需要区分两个距离：

```text
strict_distance = abs(entry - strict_failure)
stop_distance = strict_distance * stop_widen_multiplier
```

当前：

```text
stop_widen_multiplier = 1.5
strict_close_exit = true
```

因此：

```text
真实 stop_price 比 strict_failure 更远；
但 price_raw_rr 使用 strict_distance，而不是放宽后的 stop_distance；
如果收盘价重新越过 strict_failure，会触发 strict_failure_close。
```

这意味着 `strict_failure` 是结构失效线，`stop_price` 是更宽的保护性硬止损线。

## 4. POC / VA 当前定义

当前主线使用前一交易日的 5m close-profile：

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

range-profile 同时作为诊断字段保留，但没有替代主线 close-profile。

当前判断：

```text
close-profile POC 并非完全错误，
关键盈利样本中它往往比 range-profile 更贴近短期可兑现目标；
range-profile 可能过度平滑并推远目标。
```

证据：

- [R8 profile definition contrast](../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r8-profile-definition-contrast.md)

## 5. 当前最重要理解

### 5.1 有效性不来自目标更远

当前最准确理解：

```text
value_area_reacceptance 的有效性不来自“POC 更远、raw_rr 更高”，
而来自旧 VA 边界被快速拒绝后，
价格仍能回到一个位置合理、未失效、可兑现的 POC / POC band。
```

POC / VA 真正有效时，提供的是：

```text
较近失败边界 + 适中可兑现目标 + 足够原始盈亏比
```

而不是：

```text
更远目标；
更高账面 raw_rr；
更深 reaccept；
更长交易周期。
```

### 5.2 5m 暂时保留，15m 不作为主交易周期

15m 真实回测没有改善主线：

```text
15m 能过滤部分噪声，
但也会让“失败后快速重新接受并回归 POC”的信号变慢、变模糊，
并错过 POC 回归窗口。
```

因此当前仍保留 5m 作为执行周期。

证据：

- [R4 交易周期敏感性](../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r4-period-sensitivity.md)

### 5.3 2~3 ticks 是经验折中，不是最终优化参数

当前 R15 主线样本里，3 ticks 相比 2 ticks 机会数减少：

| 品种 | 2 ticks | 3 ticks | 减少 | 减少比例 |
| --- | ---: | ---: | ---: | ---: |
| DCE.m2601 | 6 | 5 | -1 | -16.7% |
| CZCE.SR601 | 9 | 6 | -3 | -33.3% |
| SHFE.rb2601 | 8 | 7 | -1 | -12.5% |
| 合计 | 23 | 18 | -5 | -21.7% |

当前观察到的 tick 结构：

```text
前日 VA 宽度通常约 23~24 ticks；
盈利样本的 entry → POC 可兑现空间通常约 12~13 ticks；
2~3 ticks reaccept 是在约 24 ticks 宽 VA 内，等待价格重新进入价值区的一小段确认。
```

但这组 tick 数不能直接解释为市场固有属性。

更准确的判断是：

```text
固定 tick 数更像当前定义和筛选方法下形成的结构尺度；
VA 内部相对位置、POC 是否靠边、当前接受区是否远离旧 POC，更可能具有市场结构含义。
```

原因：

```text
当前 VA / POC 来自前日 5m close-profile；
value_area_ratio=0.7 的扩展算法会塑造 VA width；
min_target_ticks=8 和 min_price_raw_rr=0.5 会过滤掉 POC 太近或风险收益太差的样本；
因此 20~25 ticks VA width 和 10~15 ticks POC 路径，是“当前定义 + 当前筛选”下的观察结果。
```

当前更稳的市场结构表达不是：

```text
VA 必然约等于 24 ticks；
盈利目标必然约等于 12 ticks。
```

而是：

```text
有效回归通常不是极短或极远路径；
它更像从旧 VA 边界附近，回到一个未失效、位置合理、仍被当前短期价格接受的 POC；
这个路径在当前样本中大致落在 VA width 的中等比例区间。
```

VA width 归一化尝试没有替代 fixed ticks：

```text
DCE.m2601 收益被压缩；
CZCE.SR601 转负；
SHFE.rb2601 仍为负。
```

当前理解：

```text
2~3 ticks 更像是在“足够进入价值区”和“不能错过 POC 回归窗口”之间形成的经验折中，
不是单纯尺度归一化问题。
```

证据：

- [R3 reaccept depth](../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r3-reaccept-depth.md)
- [R10 reaccept normalization](../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r10-reaccept-normalization.md)

## 6. POC 质量标签

当前最有解释力的 POC 质量标签：

```text
POC edge distance
current-day acceptance migration
```

### 6.1 POC edge distance

定义：

```text
poc_pct = (POC - VAL) / (VAH - VAL)
poc_edge_distance = min(poc_pct, 1 - poc_pct)
```

分桶：

```text
edge: poc_edge_distance < 0.20
mid_edge: 0.20 <= poc_edge_distance < 0.35
central: poc_edge_distance >= 0.35
```

含义：

```text
如果 POC 太靠近 VAH / VAL 边缘，
它不像价值区内部的稳定共识中心，
更像贴在边界附近的历史成交峰。
```

### 6.2 current-day acceptance migration

定义：

```text
current_acceptance = 最近 6 根执行周期 close 的中位数
migration = abs(current_acceptance - previous_POC) / VA_width
```

分桶：

```text
near_poc: migration <= 0.30
mid: migration <= 0.70
away: migration > 0.70
```

含义：

```text
如果当前短期接受区已经远离旧 POC，
旧 POC 可能只是历史锚点，
不再是短期容易回归的目标。
```

### 6.3 edge_or_away

组合标签：

```text
edge_or_away = poc_edge_bucket == edge
            or current_acceptance_migration_bucket == away
```

结构含义：

```text
旧 POC 太靠近前日 VA 边缘，
或当前短期接受区已经明显远离旧 POC，
因此旧 POC 作为短期可兑现共识锚的质量不足。
```

运行时字段：

```text
would_filter_edge_or_away
would_filter_reason
```

当前状态：

```text
只写 diagnostics，不改变 entry signal。
```

证据：

- [R9 POC quality tags](../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r9-poc-quality-tags.md)
- [R12 diagnostics bucket recheck](../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r12-diagnostics-bucket-recheck.md)
- [R15 shadow filter](../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r15-shadow-filter.md)

## 7. 当前统计结果

R15 重新跑主线 6 组：

```text
DCE.m2601: 456 / 457
CZCE.SR601: 458 / 459
SHFE.rb2601: 460 / 461
```

### 7.1 原始策略 raw

清算口径：

```text
n=41
win_pct=43.9%
tp_pct=29.3%
net_pnl=1890.206
median_pnl=-171.600
worst_pnl=-1622.608
left_tail_1000=4
```

日级去重、同结构平均 PnL：

```text
n=23
win_pct=43.5%
tp_pct=30.4%
net_pnl=130.399
median_pnl=-105.658
left_tail_1000=2
```

判断：

```text
原始策略略正但不稳定；
收益主要来自少数高质量样本；
中位数仍为负，左尾仍明显。
```

### 7.2 edge_or_away 影子过滤

清算口径：

```text
raw:
n=41, win_pct=43.9%, net_pnl=1890.206, left_tail_1000=4

shadow_kept:
n=25, win_pct=64.0%, net_pnl=10754.990, left_tail_1000=1

shadow_filtered:
n=16, win_pct=12.5%, net_pnl=-8864.784, left_tail_1000=3
```

日级去重、同结构平均 PnL：

```text
raw:
n=23, win_pct=43.5%, net_pnl=130.399, left_tail_1000=2

shadow_kept:
n=14, win_pct=64.3%, net_pnl=4633.791, left_tail_1000=1

shadow_filtered:
n=9, win_pct=11.1%, net_pnl=-4503.392, left_tail_1000=1
```

判断：

```text
edge_or_away 不是 2/3 ticks 重复样本造成的假象；
它已经是强候选过滤器，
但当前仍只作为 would_filter 影子标签。
```

## 8. 分品种结论

当前分品种判断：

```text
DCE.m2601：当前主线收益来源，最值得作为后续候选策略样本；
CZCE.SR601：有结构解释力，但 POC 兑现率和成本压力仍需观察；
SHFE.rb2601：当前更接近负面对照，edge_or_away 可过滤坏样本，但不能修复品种左尾。
```

R15 清算口径 raw：

```text
DCE.m2601   net_pnl=5909.600
CZCE.SR601  net_pnl=1096.200
SHFE.rb2601 net_pnl=-5115.594
```

R15 日级去重、优先 2 ticks 的 shadow_kept：

```text
DCE.m2601   net_pnl=3875.200
CZCE.SR601  net_pnl=1101.800
SHFE.rb2601 net_pnl=-363.336
```

重点：

```text
SHFE.rb2601 即使过滤 edge_or_away 后，日级 shadow_kept 仍为负；
这说明 POC 质量标签能过滤坏结构，
但不能单独修复品种级左尾。
```

## 9. 当前不建议继续的方向

| 方向 | 当前处理 | 原因 |
| --- | --- | --- |
| 广撒新结构入口 | 暂停 | 价值区主线仍是最强结构线，当前问题是质量诊断和样本扩展 |
| 继续优化 fixed ticks | 暂停 | 2~3 ticks 是经验折中，不是当前最该优化的自由参数 |
| 用 VA width ratio 替代 fixed ticks | 暂停 | R10 显示归一化不能替代 fixed ticks |
| 直接切换 15m 交易周期 | 暂停 | R4 显示 15m 会让信号变慢和模糊 |
| 直接切换 range-profile | 暂停 | R8 显示 close-profile 仍有解释力 |
| 直接启用 edge_or_away 真实过滤 | 暂缓 | 当前只是同一阶段样本内影子验证，还未跨样本验证 |
| 继续在当前样本切小桶 | 暂停 | 当前样本可支持的结论已基本榨干，继续切桶易过拟合 |
| 主动止盈 / 分段目标 / MFE 回撤退出 | 暂缓 | 退出层有价值，但当前主任务是验证结构质量和过滤稳定性 |

## 10. 下一阶段待验证

### 10.1 扩大样本的影子过滤复验

目标：

```text
验证 edge_or_away 的 shadow filter 是否跨合约、跨月份、更长历史仍稳定。
```

最小方案：

```text
1. 保留当前交易信号和参数；
2. 选择更多合约或更长历史区间；
3. 继续写入 would_filter=edge_or_away；
4. 报告 raw / shadow_kept / shadow_filtered；
5. 分品种判断 DCE.m 是否适合进入候选策略；
6. 判断 SR / rb 是否应降级、排除或需要额外左尾过滤。
```

### 10.2 报告层固定 shadow filter 视图

可以做低风险基础设施：

```text
在 report / clearing diagnostics 层固定展示：
raw strategy vs shadow_kept strategy vs shadow_filtered trades
```

这不改变交易信号，只提升后续复验效率。

### 10.3 账户风险预算与品种左尾

即便 `edge_or_away` 有效，也不能替代：

```text
最小手数风险；
合约乘数；
滑点压力；
force_flat；
品种级左尾。
```

尤其 SHFE.rb2601 说明：

```text
POC 质量标签能过滤坏结构，
但不能单独修复品种级左尾。
```

### 10.4 是否启用真实过滤

只有在扩大样本后仍稳定，才考虑：

```text
if would_filter_edge_or_away:
    skip entry
```

当前不建议启用。

### 10.5 区分方法产物和市场属性

后续若要判断 VA / POC tick 结构是否是市场固有属性，不能只看已触发交易的样本。

建议对照：

```text
1. 不带交易筛选，统计所有交易日的前日 VA width；
2. 比较 5m close-profile、5m range-profile、1m profile、真实成交量 profile；
3. 换合约月份和更长历史；
4. 优先观察比例结构，而不是固定 tick 数。
```

重点比例：

```text
poc_pct = (POC - VAL) / VA_width；
poc_edge_distance = min(poc_pct, 1 - poc_pct)；
target_to_va = abs(entry - POC) / VA_width；
current_acceptance_migration = abs(current_acceptance - previous_POC) / VA_width。
```

当前判断：

```text
20~25 ticks VA width 和 10~15 ticks POC 路径，更像当前定义和筛选下的观察尺度；
POC 靠边质量差、当前接受区远离旧 POC 后质量差，更像可能跨样本复验的市场结构假设。
```

## 11. 关联文档

| 目的 | 文档 |
| --- | --- |
| 总入口 | [strategy-current.md](../strategy-current.md) |
| 最新阶段归档 | [value_area_reacceptance POC / VA 质量诊断阶段归档](../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/value-area-reacceptance-quality-summary.md) |
| 最新阶段原始记录 | [raw-workbench](../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/) |
| R7 关键路径复盘 | [value-area-reacceptance-r7-key-sample-review.md](../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r7-key-sample-review.md) |
| R8 profile 定义对照 | [value-area-reacceptance-r8-profile-definition-contrast.md](../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r8-profile-definition-contrast.md) |
| R15 shadow filter | [value-area-reacceptance-r15-shadow-filter.md](../../archive/strategy-research/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r15-shadow-filter.md) |
