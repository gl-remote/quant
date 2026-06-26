# 数据字典

> 版本: 0.2.1-dev | 更新日期: 2026-06-06

---

## 概述

本文档定义了回测系统中所有数据库表的字段含义、格式约定、数据来源和计算公式。

### 表清单

| 表名 | 记录数 | 说明 |
|------|--------|------|
| `backtests` | 53 列 | 每次回测的汇总结果（一个品种 × 一个策略 = 一条） |
| `backtest_daily` | 11 列 | 日度权益/盈亏数据（一条回测对应多行日度记录） |
| `backtest_trades` | 12 列 | 逐笔成交记录（含 FIFO 配对后的净盈亏和费用） |

### 字段来源标记

| 标记 | 含义 |
|------|------|
| `[vnpy]` | 来自 vnpy `calculate_statistics()` 或 `DailyResult`，引擎直接输出 |
| `[自算]` | 我们从逐笔 trades 的 pnl 字段聚合计算 |
| `[入参]` | 回测引擎初始化时传入的配置参数 |

### 格式约定速查

| 格式类型 | 示例 | 适用字段 |
|----------|------|---------|
| 百分比（已×100） | `15.5` = 15.5% | total_return, annual_return, max_ddpercent, daily_return_pct |
| 绝对金额（元） | `5200.00` | max_drawdown, total_net_pnl, avg_win, avg_loss |
| 比值（0~1） | `0.6` = 60% | win_rate（数据库存储），前端展示时 ×100 |
| 天数 | `180` | profit_days, loss_days, max_drawdown_duration |

---

## backtests 表（53 列）

每次回测产生一条记录。字段按业务分组排列。

### 元数据

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | INTEGER | PK | 自增主键 |
| `run` | INTEGER | FK | 所属 run_id（关联 runs 表） |
| `symbol` | VARCHAR | ✅ | 品种代码，如 `DCE.m2509` |
| `strategy` | VARCHAR | ✅ | 策略名称，如 `ma` |
| `strategy_version` | VARCHAR | — | 策略版本号 |
| `git_hash` | VARCHAR | — | 回测时的 git commit hash |
| `status` | VARCHAR | ✅ | 状态：`success` / `failed` / `timeout` |
| `error_message` | TEXT | — | 失败时的错误信息 |
| `start_date` | VARCHAR | — | 回测起始日期（YYYY-MM-DD） |
| `end_date` | VARCHAR | — | 回测结束日期（YYYY-MM-DD） |
| `total_days` | INTEGER | — | 总交易日数 |
| `created_at` | DATETIME | ✅ | 记录创建时间 |

### 资金概况 [vnpy]

| 字段 | 类型 | 格式 | 说明 |
|------|------|------|------|
| `initial_capital` | REAL | 金额 | 初始资金（元），如 `100000.0` |
| `end_balance` | REAL | 金额 | 期末账户余额（元）= initial_capital + 累计 net_pnl |
| `total_return` | REAL | **百分比** | **总收益率**，如 `15.5` 表示 **15.5%**（非 0.155） |
| `annual_return` | REAL | **百分比** | **年化收益率**，同上格式 |

### 风险指标 [vnpy]

| 字段 | 类型 | 格式 | 说明 |
|------|------|------|------|
| `sharpe_ratio` | REAL | 比值 | 夏普比率（年化、无风险利率=0）。>1 良好，>2 优秀 |
| `max_drawdown` | REAL | **金额** | **最大回撤金额（元）**，如 `5200.0` 表示回撤了 5200 元 |
| `max_ddpercent` | REAL | **百分比** | **最大回撤百分比**，如 `5.2` 表示 **5.2%** |
| `max_drawdown_duration` | INTEGER | 天数 | 最大回撤持续天数 |
| `daily_std` | REAL | — | 日收益率标准差 |
| `return_drawdown_ratio` | REAL | — | 收益回撤比 = annual_return / max_ddpercent。越高越好 |

### 盈亏汇总 [vnpy]（2026-06-06 新增）

| 字段 | 类型 | 格式 | 说明 |
|------|------|------|------|
| `total_net_pnl` | REAL | 金额 | **总净盈亏（元）** = 所有交易日 net_pnl 之和 = end_balance - initial_capital |
| `daily_net_pnl` | REAL | 金额 | 日均净盈亏 = total_net_pnl / total_days |
| `total_commission` | REAL | 金额 | **总手续费（元）** = Σ(成交价 × 数量 × 合约乘数 × 费率) |
| `daily_commission` | REAL | 金额 | 日均手续费 = total_commission / total_days |
| `total_slippage` | REAL | 金额 | **总滑点成本（元）** = Σ(数量 × 合约乘数 × 单边滑点) |
| `daily_slippage` | REAL | 金额 | 日均滑点成本 |
| `total_turnover` | REAL | 金额 | **总成交金额（元）** = Σ(成交价 × 数量 × 合约乘数) |
| `daily_turnover` | REAL | 金额 | 日均成交金额 |

### 交易日统计 [vnpy]（2026-06-06 新增）

| 字段 | 类型 | 格式 | 说明 |
|------|------|------|------|
| `profit_days` | INTEGER | 天数 | 盈利交易日数（当日 net_pnl > 0 的天数） |
| `loss_days` | INTEGER | 天数 | 亏损交易日数（当日 net_pnl < 0 的天数） |
| `daily_trade_count` | REAL | 笔数 | 日均成交笔数 = total_trade_count / total_days |
| `daily_return_pct` | REAL | **百分比** | 日均收益率%，如 `0.08` 表示日均 0.08% |

### 进阶指标 [vnpy]（2026-06-06 新增）

| 字段 | 类型 | 说明 |
|------|------|------|
| `ewm_sharpe` | REAL | EWM（指数加权移动平均）夏普比率，对近期收益赋予更高权重 |
| `rgr_ratio` | REAL | RGR（Return/Growth/Risk）比率，综合考量收益与风险 |

### 交易级别统计 [自算]

以下字段基于 `backtest_trades` 表中 pnl != 0 的平仓交易聚合：

| 字段 | 类型 | 计算公式 | 统计口径 |
|------|------|----------|----------|
| `total_trades` | INTEGER | 引擎输出的总成交笔数 `[vnpy]` | **含开仓+平仓所有成交** |
| `win_trades` | INTEGER | count(pnl > 0) | 仅 **pnl > 0 的平仓交易**（排除开仓和持平） |
| `loss_trades` | INTEGER | count(pnl < 0) | 仅 **pnl < 0 的平仓交易** |
| `win_rate` | REAL | win_trades / (win_trades + loss_trades) | 比值 0~1；store 层输出时 ×100 |
| `avg_win` | REAL | mean(pnl \| pnl > 0) | 平均盈利金额（元） |
| `avg_loss` | REAL | mean(abs(pnl) \| pnl < 0) | 平均亏损金额（元） |
| `win_loss_ratio` | REAL | avg_win / avg_loss | 盈亏比，>1 表示盈利大于亏损 |
| `max_consecutive_win` | INTEGER | 最长连续 pnl > 0 的次数 | 基于平仓时间顺序 |
| `max_consecutive_loss` | INTEGER | 最长连续 pnl < 0 的次数 | 基于平仓时间顺序 |

> **注意**: `win_trades + loss_trades <= total_trades`。因为 total_trades 包含所有成交（含开仓），而 win/loss 只统计有实际盈亏的平仓交易。

### 引擎配置 [入参]

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `commission_rate` | REAL | 0.0003 | 手续费率，如 0.0003 = 万三 |
| `slippage` | REAL | 0.1 | 单边滑点（价格单位），如 0.1 元/跳 |
| `price_tick` | REAL | 1.0 | 最小变动价位 |
| `contract_size` | INTEGER | 10 | 合约乘数（每手合约的标准单位数） |
| `kline_interval` | VARCHAR | — | K线周期：`1m` / `5m` / `15m` / `30m` / `1h` / `d` |
| `data_src` | VARCHAR | — | 数据来源标识 |

---

## backtest_daily 表（11 列）

每个回测每天一行。来自 vnpy `DailyResult` 对象。

| 字段 | 类型 | 来源 | 说明 |
|------|------|------|------|
| `id` | INTEGER | PK | 自增主键 |
| `backtest_id` | INTEGER | FK | 关联 backtests.id |
| `date` | DATE | [vnpy] | 交易日日期 |
| `equity` | REAL | [vnpy] | 当日收盘权益（元） |
| `drawdown_pct` | REAL | [vnpy] | 当日回撤百分比（相对于历史最高权益） |
| `turnover` | REAL | [vnpy] | **当日成交金额（元）**（2026-06-06 新增） |
| `commission` | REAL | [vnpy] | **当日手续费（元）**（2026-06-06 新增） |
| `slippage` | REAL | [vnpy] | **当日滑点成本（元）**（2026-06-06 新增） |
| `trade_count` | INTEGER | [vnpy] | **当日成交笔数**（2026-06-06 新增） |
| `net_pnl` | REAL | [vnpy] | 当日净盈亏（元）= trading_pnl + holding_pnl - commission - slippage |
| `created_at` | DATETIME | — | 记录创建时间 |

---

## backtest_trades 表（12 列）

每笔成交一行。开仓和平仓都记录，但只有平仓记录有非零 pnl 和 commission。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | PK |
| `backtest_id` | INTEGER | FK → backtests.id |
| `symbol` | VARCHAR | 品种代码 |
| `action` | VARCHAR | 交易方向：`buy` / `sell` |
| `offset` | VARCHAR | 开平标志：`open`（开仓）/ `close`（平仓） |
| `direction` | VARCHAR | 持仓方向：`long`（多头）/ `short`（空头） |
| `price` | REAL | 成交价格 |
| `quantity` | REAL | 成交数量（手） |
| `open_price` | REAL | 配对的开仓均价（仅平仓记录有值） |
| `close_price` | REAL | 平仓均价（仅平仓记录有值） |
| `pnl` | REAL | **净盈亏（元）** = 毛利 - commission - slippage_cost。开仓记录为 0 |
| `commission` | REAL | **该笔平仓周期的总手续费（元）** = 开仓侧 + 平仓侧。开仓记录为 0 |
| `created_at` | DATETIME | 记录创建时间 |

### 逐笔 PnL 计算公式（FIFO 配对）

```
对于每笔 offset='close' 的平仓记录：
  1. 从开仓队列（FIFO）取最旧的同向未配对开仓
  2. matched_vol = min(平仓数量, 开仓剩余数量)
  3. 方向系数: 多头 = +1, 空头 = -1
  4. 毛利 = (close_price - open_price) × matched_vol × contract_size × direction
  5. commission = (open_price × matched_vol + close_price × matched_vol) × contract_size × rate
  6. slippage_cost = 2 × matched_vol × contract_size × slippage  （双边）
  7. pnl = 毛利 - commission - slippage_cost
```

费用参数（来自引擎配置）：
- `rate` = commission_rate（手续费率）
- `slippage` = slippage（单边滑点）
- `size` = contract_size（合约乘数）

---

## 一致性校验规则

`validate_backtest_consistency()` 执行以下检查，用于发现数据异常：

| # | 校验项 | 公式 | 容差 |
|---|--------|------|------|
| 1 | 盈亏笔数 ≤ 总成交 | `win_trades + loss_trades ≤ total_trades` | 精确匹配 |
| 2 | 胜率自洽 | `abs(win_rate - win/(win+loss)) < 0.01` | ±0.01 |
| 3 | 盈利天数匹配 | `profit_days ≈ daily表中 equity > prev_equity 的天数` | 精确匹配 |
| 4 | 手续费对账 | `abs(total_commission - sum(trades.commission)) < 1.0` | ±1.0 元 |

---

## 字段语义变更历史

| 日期 | 字段 | 变更内容 |
|------|------|----------|
| 2026-06-06 | `pnl`（逐笔） | 毛利 → **净盈亏**（扣 commission + slippage） |
| 2026-06-06 | `commission`（逐笔） | 硬编码 0.0 → **真实手续费**（开仓侧 + 平仓侧） |
| 2026-06-06 | `win_trades` | 含开仓 → **仅 pnl > 0 的平仓** |
| 2026-06-06 | `loss_trades` | 含开仓(pnl≤0) → **仅 pnl < 0 的平仓** |
| 2026-06-06 | `win_rate` 分母 | total_trades → **win_trades + loss_trades** |
| 2026-06-06 | `total_return` | 格式约定明确为**百分比**（如 15.5 = 15.5%） |
| 2026-06-06 | `max_drawdown` | 格式约定明确为**绝对金额**（如 50000 元） |
