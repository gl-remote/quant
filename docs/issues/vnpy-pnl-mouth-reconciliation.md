# vnpy 回测 PnL 口径：daily_results 与 backtest_trades 对账

> 状态：已验证  
> 发现来源：`low-validation-cost-r1-breakout-retest` 实验  
> 关联归档：[low-validation-cost-r1-breakout-retest](../archive/strategy-research/low-validation-cost-r1-breakout-retest.md)

## 问题

实验中发现：`backtests.total_net_pnl` / `backtest_daily.net_pnl` 与直接聚合 `backtest_trades.pnl` 的结果差异很大。

这不是回测引擎计算错误，而是口径不同。

## 对账证据

DCE.m2601 run 30：

```text
逐笔毛盈亏合计        720.00
- 总手续费         10,193.11
- 总滑点           18,280.00
+ 期末未平仓浮盈        80.00
= 日度净盈亏合计    -27,673.11
```

可完全对上 `backtest_daily.net_pnl`。

## 口径定义

| 数据 | 口径 | 用途 |
|---|---|---|
| `backtest_trades.pnl` | 逐笔毛盈亏，不扣手续费和滑点 | 分析价格运动、胜负结构、单笔空间 |
| `backtest_trades.commission` | 该成交本侧手续费，open/close 各自记录 | 成本拆解 |
| `backtest_daily.net_pnl` | 日度净盈亏，包含手续费、滑点和期末持仓重估 | 真实权益变化 |
| `backtests.total_net_pnl` | `backtest_daily.net_pnl` 汇总 | 策略收益主口径 |

## 研究规则

```text
真实收益、成本后期望、盈亏平衡胜率、安全边际：
以 backtest_daily.net_pnl / backtests.total_net_pnl 为准。

单笔价格结构、严格失败距离、MFE/MAE：
可以使用 backtest_trades.pnl，但必须标注为毛盈亏口径。
```

## 代码处理

本次未修改 `_parse_trades` 业务逻辑，只修正注释和 Schema 说明，避免误把 `backtest_trades.pnl` 当净收益。

已更新：

- `workspace/common/schemas.py`
- `workspace/data/models.py`
- `workspace/common/types.py`
- `workspace/data/store.py`

## 查询模板

```sql
WITH bt AS (
  SELECT id FROM backtests WHERE run_id = :run_id AND symbol = :symbol
), trade_summary AS (
  SELECT
    SUM(pnl) AS gross_trade_pnl,
    SUM(commission) AS trade_commission,
    SUM(CASE WHEN offset = 'close' THEN pnl ELSE 0 END) AS close_gross_pnl,
    SUM(CASE WHEN offset = 'open' THEN commission ELSE 0 END) AS open_commission,
    SUM(CASE WHEN offset = 'close' THEN commission ELSE 0 END) AS close_commission
  FROM backtest_trades
  WHERE backtest_id IN bt
), daily_summary AS (
  SELECT
    SUM(daily_return) AS net_pnl,
    SUM(commission) AS daily_commission,
    SUM(slippage) AS daily_slippage
  FROM backtest_daily
  WHERE backtest_id IN bt
)
SELECT * FROM trade_summary CROSS JOIN daily_summary;
```
