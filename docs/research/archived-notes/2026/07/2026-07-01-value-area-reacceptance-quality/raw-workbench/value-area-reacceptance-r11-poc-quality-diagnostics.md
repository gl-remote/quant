# value_area_reacceptance R11：POC 质量标签诊断 payload 最小实现

> 类型：Workbench / 实验报告
> 状态：已完成
> 日期：2026-06-30
> 阶段规划：[value-area-reacceptance-stage-plan.md](./value-area-reacceptance-stage-plan.md)
> 上一轮报告：[value-area-reacceptance-r10-reaccept-normalization.md](./value-area-reacceptance-r10-reaccept-normalization.md)

## 1. 实验问题

R9 显示，当前最有解释力的 POC 质量标签是：

```text
POC edge distance
current-day acceptance migration
```

R10 又确认，VA width 归一化不能直接替代 fixed ticks。

因此本轮不继续调参，而是做最小工程实现：

```text
把 POC 质量标签写入 strategy decision_payload / clearing diagnostics，
暂不改变交易信号，
为后续更大样本分桶验证准备数据字段。
```

## 2. 实现范围

本轮改动策略文件：

```text
workspace/strategies/value_area_reacceptance_strategy.py
```

新增诊断字段进入 `decision_payload.diagnostics.alpha`：

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
```

新增诊断字段进入 `decision_payload.diagnostics.risk`：

```text
va_width
reaccept_depth
reaccept_depth_va_ratio
min_reaccept_ticks
min_reaccept_va_width_ratio
strict_failure_distance
expected_profit_distance
raw_price_r_multiple
raw_account_r_multiple
```

同时 exit signal 写入真实 `execution.exit_reason`，使 `trade_clearings.exit_reason` 能从 payload 中解析。

## 3. 计算口径

### 3.1 POC edge distance

```text
poc_pct = (POC - VAL) / (VAH - VAL)
poc_edge_distance = min(poc_pct, 1 - poc_pct)
```

分桶：

```text
edge: < 0.20
mid_edge: < 0.35
central: >= 0.35
```

### 3.2 current acceptance migration

当前实现使用最近 6 根执行周期 K 线 close 的中位数表示当前短期接受位置：

```text
current_acceptance = median(recent 6 closes)
current_acceptance_migration = abs(current_acceptance - previous_POC) / VA_width
```

分桶：

```text
near_poc: <= 0.30
mid: <= 0.70
away: > 0.70
```

### 3.3 local band

基于 previous session close-profile：

```text
从 POC 向左右连续扩展，直到相邻 price bucket volume < POC_volume * 50%。
local_band_width_ratio = local_band_width / VA_width
```

分桶：

```text
tight: <= 0.10
medium: <= 0.25
wide: > 0.25
```

### 3.4 multi-modal profile

基于 previous session close-profile：

```text
volume >= top_volume * 70% 的高成交价格，
若形成两个或以上不连续组件，则 multi_modal_profile = true。
```

### 3.5 close-vs-range POC divergence

同一 previous session 同时计算 close-profile POC 与 range-profile POC：

```text
close_range_poc_divergence = abs(range_profile_POC - close_profile_POC) / VA_width
```

分桶：

```text
low: <= 0.10
medium: <= 0.35
high: > 0.35
```

## 4. 验证回测

使用 DCE.m2601 主线参数做最小验证：

```text
backtest_id = 443
symbol = DCE.m2601
profile_mode = close
min_reaccept_ticks = 2
min_reaccept_va_width_ratio = 0
```

结果：

```text
total_trades = 12
total_net_pnl = 3516.8
status = success
clearings = 6
```

该结果与原 fixed 2 ticks 组一致，说明本轮诊断字段实现没有改变交易信号。

## 5. 落库验证

### 5.1 backtest_trades.decision_payload_json

验证 SQL 返回：

```text
id,symbol,total_trades,total_net_pnl,status,trade_poc_edge,trade_migration,trade_local_band,trade_multi_modal,trade_reaccept_va_ratio
443,DCE.m2601,12,3516.8,success,mid_edge,mid,tight,0,0.16
```

说明新字段已进入交易开仓 payload。

### 5.2 trade_clearings.diagnostics_json

验证 SQL 返回：

```text
backtest_id,exit_reason,clearing_poc_edge,clearing_migration,clearing_divergence,clearing_reaccept_va_ratio,execution_exit
443,time_exit,mid_edge,mid,low,0.16,time_exit
443,take_profit,mid_edge,mid,low,0.111111111111111,take_profit
443,time_exit,mid_edge,mid,low,0.125,time_exit
```

说明开仓 alpha / risk 诊断字段已由 clearing 服务透传到清算记录，exit reason 也能从 execution 层解析。

## 6. 阶段结论

本轮完成的是诊断能力，不是策略优化。

关键结论：

```text
POC 质量标签已经可以进入 backtest_trades 与 trade_clearings，
后续可以按标签直接做更大样本分桶，
不再依赖临时脚本从 CSV / DB 重算全部标签。
```

这使后续研究从“事后临时诊断”推进到“策略运行时保留结构快照”。

但当前仍不应把标签作为硬过滤条件：

```text
POC edge distance 与 current acceptance migration 已有解释力，
但还需要更大样本验证稳定性；
local band、multi-modal、close-vs-range divergence 仍先作为警示/诊断标签。
```

## 7. 下一步

建议下一轮做：

```text
R12：基于新 diagnostics_json 的批量分桶验证。
```

具体做法：

```text
1. 用当前交易规则重新跑 DCE.m、CZCE.SR、SHFE.rb 的主线对照；
2. 不额外写临时 profile 计算脚本；
3. 直接从 trade_clearings.diagnostics_json 提取标签；
4. 验证 R9 的 POC edge distance / migration 结论是否复现；
5. 再决定是否把这些字段接入 report 层固定分桶视图。
```
