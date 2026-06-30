# value_area_reacceptance POC / VA 质量诊断阶段归档

> 类型：Archive / 策略实验摘要
> 状态：已完成 / 当前样本通过诊断，未完成跨样本验证
> 日期：2026-07-01
> 原始记录：[`raw-workbench/`](./raw-workbench/)
> 关联路线：[`strategy-research-framework.md`](../../../roadmap/strategy-research-framework.md)

## 1. 阶段问题

本阶段研究对象是 `value_area_reacceptance`：

```text
前日价值区边界被突破失败后，价格重新接受回价值区，
以旧 POC 或 POC 附近共识区作为短期可兑现目标。
```

阶段核心问题：

```text
当前 POC / VA 定义是否足以代表“短期可兑现共识锚”？
如果不是，哪些质量标签能解释好坏交易？
```

本阶段不是参数优化阶段，也没有把候选过滤器直接固化为真实交易规则。

## 2. 固定主线设置

主线回测使用：

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

主要样本：

```text
DCE.m2601
CZCE.SR601
SHFE.rb2601
```

其中 DCE.m2601 是当前主线候选，CZCE.SR601 是观察样本，SHFE.rb2601 更接近负面对照。

## 3. 关键实现与基础问题

### 3.1 0-trade 误判爆仓修复

早期发现 DCE.c2601 / DCE.cs2601 低成交不是因为初始资本不足，而是策略目标/POC 约束导致。

同时修复 vn.py 回测统计误判：

```text
0-trade flat-equity backtest 不应被视为 blown-up。
```

修复后爆仓判断改为基于：

```text
daily_results["net_pnl"].cumsum() + initial_capital
```

只有累计余额 `<= 0` 才视为爆仓。

### 3.2 POC 质量诊断字段落库

策略运行时新增诊断字段：

```text
poc_edge_distance
poc_edge_bucket
current_acceptance_migration
current_acceptance_migration_bucket
local_band_width_ratio
local_band_bucket
multi_modal_profile
close_range_poc_divergence
close_range_poc_divergence_bucket
would_filter_edge_or_away
would_filter_reason
```

这些字段写入：

```text
backtest_trades.decision_payload_json
trade_clearings.diagnostics_json
```

`would_filter_edge_or_away` 目前只是影子过滤标签，不改变 entry signal。

## 4. POC / VA 定义诊断

当前主线使用前一交易日的 5m close-profile：

```text
profile: price -> accumulated volume
```

POC：

```text
成交量最大的 price bucket；
并列时选择离 session close 更近的价格。
```

VA：

```text
从 POC 开始，按相邻 bucket 成交量贪婪扩展，
直到覆盖 value_area_ratio=70% 的成交量。
```

range-profile 也被计算为诊断字段，但没有替代主线 close-profile。

R8 的关键结论：

```text
close-profile POC 并非完全错误，
关键盈利样本中它往往比 range-profile 更贴近短期可兑现目标。
range-profile 可能过度平滑并推远目标。
```

因此本阶段没有切换到 range-profile，也没有使用 naive 全局 POC band。

## 5. 主要实验结论

### 5.1 交易周期

真实 15m 回测没有改善主线：

```text
15m 能过滤部分噪声，
但也让失败后快速重新接受并回归 POC 的信号变慢、变模糊。
```

当前保留 5m 作为执行周期。

### 5.2 reaccept 深度

fixed 2~3 ticks 对结果敏感，但这不是简单参数优化问题。

VA width 归一化尝试：

```text
min_reaccept_va_width_ratio = 0.10 / 0.15
```

没有替代 fixed ticks：

```text
DCE.m2601 收益被压缩；
CZCE.SR601 转负；
SHFE.rb2601 仍为负。
```

阶段解释：

```text
2~3 ticks 更像是在“足够进入价值区”和“不能错过 POC 回归窗口”之间形成的经验折中，
不是单纯尺度归一化问题。
```

### 5.3 POC 质量标签

最有解释力的标签：

```text
POC edge distance
current-day acceptance migration
```

定义：

```text
poc_pct = (POC - VAL) / (VAH - VAL)
poc_edge_distance = min(poc_pct, 1 - poc_pct)

edge: poc_edge_distance < 0.20
mid_edge: 0.20 <= poc_edge_distance < 0.35
central: poc_edge_distance >= 0.35
```

```text
current_acceptance = 最近 6 根执行周期 close 的中位数
migration = abs(current_acceptance - previous_POC) / VA_width

near_poc: migration <= 0.30
mid: migration <= 0.70
away: migration > 0.70
```

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

## 6. 关键统计结果

### 6.1 原始主线结果

R15 重新跑主线 6 组：

```text
DCE.m2601: 456 / 457
CZCE.SR601: 458 / 459
SHFE.rb2601: 460 / 461
```

清算口径 raw：

```text
n=41
win_pct=43.9%
tp_pct=29.3%
net_pnl=1890.206
median_pnl=-171.600
worst_pnl=-1622.608
left_tail_1000=4
```

分品种 raw：

```text
DCE.m2601   net_pnl=5909.600
CZCE.SR601  net_pnl=1096.200
SHFE.rb2601 net_pnl=-5115.594
```

结论：原始策略略正但不稳定，收益主要来自 DCE.m，rb 明显拖累。

### 6.2 edge_or_away 影子过滤结果

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

结论：

```text
edge_or_away 不是 2/3 ticks 重复样本造成的假象；
它在 raw、日级去重、同结构平均 PnL 三种口径下都能稳定识别坏结构。
```

但：

```text
SHFE.rb2601 的日级 shadow_kept 仍为负，
说明该品种左尾不能靠 POC 标签单独修复。
```

## 7. 当前阶段判断

本阶段最重要结论：

```text
value_area_reacceptance 的结构 alpha 雏形来自：
旧 VA 边界被快速拒绝后，
价格仍能回到一个位置合理、未失效、可兑现的 POC / POC band。
```

POC / VA 有效时提供的是：

```text
较近失败边界 + 适中可兑现目标 + 足够原始盈亏比
```

而不是：

```text
更远目标；
更高账面 raw_rr；
更深 reaccept；
更长周期。
```

`edge_or_away` 是当前最强的坏结构候选过滤器。

但当前状态仍是：

```text
候选过滤器 / 影子评估通过当前样本；
未完成跨合约、跨月份、更长区间验证；
不应直接视为最终交易规则。
```

## 8. 保留与不保留

### 8.1 保留

策略代码保留：

```text
workspace/strategies/value_area_reacceptance_strategy.py
```

原因：

```text
该策略仍处于活跃研究线，且已经具备运行时诊断字段。
```

保留诊断字段：

```text
would_filter_edge_or_away
would_filter_reason
```

原因：

```text
后续扩大样本时，可继续观察 raw / shadow_kept / shadow_filtered。
```

### 8.2 暂不启用

暂不把 `edge_or_away` 固化为真实 entry filter。

原因：

```text
样本仍小；
DCE.m 的 bad 日级结构只有 1 个；
rb 的 not_bad 仍保留左尾；
还没有跨合约、跨月份、更长窗口验证。
```

### 8.3 暂不继续

若不扩大样本，不建议继续在当前样本上做更多参数或标签挖掘。

原因：

```text
当前样本可支持的结论已经基本榨干；
继续切小桶容易过拟合。
```

## 9. 后续最小方案

下一阶段建议：

```text
扩大样本的影子过滤复验。
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

只有当更大样本仍稳定时，才考虑：

```text
if would_filter_edge_or_away:
    skip entry
```

作为真实交易规则。

## 10. 原始记录

原始阶段记录保存在：

```text
raw-workbench/
```

其中：

```text
value-area-reacceptance-stage-plan.md
value-area-reacceptance-r1-risk-budget.md
...
value-area-reacceptance-r15-shadow-filter.md
```
