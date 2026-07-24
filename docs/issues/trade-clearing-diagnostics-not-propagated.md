# Issue: trade_clearings 未透传 exit_reason 与 diagnostics_json

> 类型：Issue / 回测清算诊断口径\
> 状态：已验证\
> 创建日期：2026-06-30\
> 发现阶段：[value-area-reacceptance-stage-plan.md](../research/archived-notes/2026/07/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-stage-plan.md)\
> 关联实验：[value-area-reacceptance-r1-risk-budget.md](../research/archived-notes/2026/07/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r1-risk-budget.md)

## 1. 问题摘要

在 `value_area_reacceptance` 第一轮账户风险预算预筛中，回测和清算均能完成，但 `trade_clearings` 表中的结构诊断字段没有按预期透传：

```text
trade_clearings.exit_reason 为空；
trade_clearings.diagnostics_json 为空；
清算日志提示缺 alpha / risk 诊断。
```

实际开仓和平仓原始成交的 `backtest_trades.decision_payload_json` 中存在策略层字段，例如：

```text
entry_price；
strict_failure；
strict_distance；
stop_price；
target_price；
price_raw_rr；
holding_bars；
path_progress。
```

因此，实验可以暂时通过 `backtest_trades.decision_payload_json` 手工抽取风险字段继续分析，但清算层诊断口径不完整，会影响后续自动化报告、分桶统计和阶段归档的可信度。

## 2. 复现信息

实验分支：

```text
experiment/value-area-reacceptance-risk-budget
```

开分支 hash：

```text
6b672e4c298159f202d9c6a648c5557a4577b0e7
```

涉及回测 ID：

```text
401, 402, 403, 404
```

对应组合：

| backtest_id | symbol | min_reaccept_ticks | max_hold_bars |
|-------------|--------|--------------------|---------------|
| 401 | DCE.m2601 | 2 | 12 |
| 402 | DCE.m2601 | 3 | 12 |
| 403 | CZCE.SR601 | 2 | 12 |
| 404 | CZCE.SR601 | 3 | 12 |

清算日志出现：

```text
清算成交缺 alpha 诊断（开仓未填结构候选）
清算成交缺 risk 诊断（开仓未填风险预算）
```

## 3. 影响范围

影响：

1. `trade_clearings.exit_reason` 不能直接用于 exit reason 分布；
2. `trade_clearings.diagnostics_json` 不能直接用于结构分桶；
3. 自动报告中的 clearing diagnostics 会缺少策略结构字段；
4. 后续实验若依赖清算层字段做账户风险预算、MAE/MFE、胜率 / 盈亏比转化诊断，会出现口径不完整。

不影响：

1. 原始成交记录写入；
2. FIFO 清算生成；
3. `net_pnl`、`commission`、`slippage_cost`、`mae`、`mfe` 等基础字段；
4. 本轮通过 `backtest_trades.decision_payload_json` 手工抽取 strict failure / stop / target 的临时分析。

## 4. 当前临时处理

本轮实验暂时使用：

```sql
trade_clearings.open_trade_id
→ backtest_trades.id
→ backtest_trades.decision_payload_json
→ $.diagnostics.strategy.*
```

手工抽取：

```text
entry_price；
strict_failure；
strict_distance；
stop_price；
target_price；
price_raw_rr。
```

退出原因暂时从：

```text
trade_clearings.close_reason
```

按 `|` 前缀解析，例如：

```text
time_exit|... → time_exit
take_profit|... → take_profit
force_flat|... → force_flat
```

## 5. 修复建议

后续应检查清算服务：

```text
workspace/clearing/service.py
```

重点确认：

1. 是否从开仓成交 `decision_payload_json` 正确读取 `diagnostics`；
2. 是否把策略层诊断按约定映射到 `TradeClearing.diagnostics_json`；
3. 是否从平仓原因中规约出 `exit_reason`；
4. 当前诊断 schema 是否要求 alpha / risk / execution 三层，但策略只写了 strategy 层；
5. 若策略暂未提供 alpha / risk / execution，应避免误判为缺失，或在策略侧补齐结构化诊断。

## 6. 修复与验证

本问题已经通过策略侧补齐结构化诊断解决：

```text
entry signal 写入 alpha / risk / execution diagnostics；
exit signal 写入 alpha / risk / execution diagnostics；
trade_clearings.diagnostics_json 可直接读取策略结构字段；
trade_clearings.exit_reason 可从 execution diagnostics 和 close_reason 口径复核。
```

修复涉及：

```text
workspace/strategies/value_area_reacceptance_strategy.py
```

验证回测：

```text
R11: backtest_id = 443，验证 diagnostics_json 可落库；
R12: backtest_id = 450~455，基于 trade_clearings.diagnostics_json 复验 R9 分桶；
R15: backtest_id = 456~461，验证 would_filter_edge_or_away 影子过滤字段。
```

验证结论：

```text
trade_clearings.diagnostics_json 已可用于 POC 质量标签分桶、edge_or_away 影子过滤评估，
不再需要依赖 backtest_trades.decision_payload_json 做手工抽取。
```

关联记录：

- [R11 POC quality diagnostics](../research/archived-notes/2026/07/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r11-poc-quality-diagnostics.md)
- [R12 diagnostics bucket recheck](../research/archived-notes/2026/07/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r12-diagnostics-bucket-recheck.md)
- [R15 shadow filter](../research/archived-notes/2026/07/2026-07-01-value-area-reacceptance-quality/raw-workbench/value-area-reacceptance-r15-shadow-filter.md)
