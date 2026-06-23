# 回测报告数据来源说明

本文档说明报告 web 页面所有可见数据的完整链路，从前端展示，到读取 JSON，到 Python 写入 JSON，到查询数据库，逐层打通。

---

## 完整链路概览

```
用户看到的页面
    ↓
前端 React 组件
    ↓ (useFetchJson → window.__DATA__)
JSON 数据文件 (output/r{runId}/data/*.json)
    ↓ (report.writer.json_writer)
Python 数据处理
    ↓ (data.store.DataStore)
SQLite 数据库
```

---

## 页面结构与板块 - 完整链路说明

### 1. 页面头部 (RUN-PG-HEADER)

**前端组件**：`report/web/src/pages/RunPage.tsx`  
**数据来源 JSON**：`data/run.json`  
**JSON 来源**：`report/writer/json_writer.py` → `export_run_json()`  
**数据库查询**：`data/store.py` → `DataStore.get_run_info(run_id)` → SQL 查询 `runs` 表

**字段链路**：
| 页面显示 | JSON 字段 | 数据库表 | 数据库字段 |
|----------|-----------|----------|------------|
| 策略名 | strategy | runs | strategy |
| 引擎 | engine | runs | engine |
| 总品种数 | symbols | runs | symbols |
| 创建时间 | created_at | runs | created_at |
| 状态 | status | runs | status |
| 固定种子 | use_fixed_seed | runs | use_fixed_seed |
| 随机种子 | random_seed | runs | random_seed |

---

## 2. 指标总览 (RUN-MET-CONTAINER)

**前端组件**：`report/web/src/components/MetricCards.tsx`  
**数据来源 JSON**：`data/backtests.json` 和 `data/summary.json`  
**JSON 来源**：`report/writer/json_writer.py` → `export_backtests_json()` 和 `export_summary_json()`  
**数据库查询**：`data/store.py` → `DataStore.get_backtests_for_run(run_id)` 和 `get_run_summary(run_id)` → SQL 查询 `backtests` 表

### 2.1 各指标的完整链路

| 指标卡片 | 前端计算来源 | JSON 字段 | 数据库表 | 数据库字段 |
|----------|--------------|-----------|----------|------------|
| 策略 | 直接显示 | strategy | backtests | strategy |
| 引擎 | 直接显示 | engine | runs | engine |
| 总品种数 | 统计最优记录的唯一 symbol 数量 | summary 里的 symbol 列表 | backtests | symbol |
| 平均收益率 | sum(最优记录 total_return) / 总品种数 | total_return | backtests | total_return |
| 总交易次数 | sum(最优记录 total_trades) | total_trades | backtests | total_trades |
| 平均夏普 | avg(最优记录 sharpe_ratio) | sharpe_ratio | backtests | sharpe_ratio |

---

## 3. 品种汇总 (RUN-SUM-TABLE)

**前端组件**：`report/web/src/components/SymbolTable.tsx`  
**数据来源 JSON**：`data/summary.json`  
**JSON 来源**：`report/writer/json_writer.py` → `export_summary_json()`  
**数据库查询**：`data/store.py` → `DataStore.get_run_summary(run_id)` → SQL 查询 `backtests` 表，按 symbol 分组，每个 symbol 取 `total_return` 最大的记录

**表格列链路（当前 10 列）**：
| 列名 | JSON 字段 | 数据库字段 | 说明 |
|------|-----------|------------|------|
| 品种 | symbol | symbol | |
| 收益率 | total_return | total_return | 比值，前端乘 100 显示为百分比 |
| 胜率 | win_rate | win_rate | 后端已乘 100，前端直接显示百分比 |
| 盈亏比 | win_loss_ratio | win_loss_ratio | vnpy 默认不输出此字段，从交易 pnl 自行计算后注入 |
| 交易次数 | total_trades | total_trades | |
| 最大回撤 | max_drawdown | max_drawdown | 前端显示为百分比 |
| 夏普比率 | sharpe | sharpe_ratio | JSON 中重命名为 sharpe |
| 年化收益率 | annual_return | annual_return | 比值，前端乘 100 显示为百分比 |
| 最终权益 | end_balance | end_balance | |
| 回测ID | id | id | 对应 backtests 表的 id 字段 |

---

## 4. K线图 (RUN-KLINE-CONTAINER)

K线图是最复杂的，包含 K线主图、成交量、MACD、KDJ、交易标记。

### 4.1 K线数据 - 完整链路

**前端组件**：`report/web/src/components/KlineChart.tsx`  
**数据来源 JSON**：`data/kline_{symbol}.{interval}.json`  
**JSON 来源**：`report/writer/json_writer.py` → `export_kline_json()` 和 `report/cache/kline.py`  
**数据原始来源**：从 `backtests.data_src` 获取 CSV 文件路径，读取 CSV 原始数据

**链路详细说明**：
1. 从 `summary.json` 获取选中品种的 `data_src`（CSV 路径）
2. 在 `report/cache/kline.py` 中读取 CSV
3. 处理时间（北京时间 → UTC Unix 时间戳）
4. 重采样生成日线数据
5. 保存到 `kline_{symbol}.{interval}.json`

### 4.2 技术指标 - 完整链路

所有指标**在前端实时计算**，使用 `lightweight-charts-indicators` 库（内部封装了 `technicalindicators`）

| 指标 | 数据源 | 计算位置 | 实现库 |
|------|--------|----------|--------|
| SMA (5/60) | K线 close | 前端 | lightweight-charts-indicators (SMA) |
| MACD (12,26,9) | K线 close | 前端 | lightweight-charts-indicators (MACD) |
| KDJ (9,3,3) | K线 high/low/close | 前端 | lightweight-charts-indicators (Stochastic) |

**MACD/KDJ 基准线**：使用 `createPriceLine()` 方法（在指标 Series 上创建，不是静态画线），自动跟随十字光标联动

### 4.3 交易标记 - 完整链路

**前端组件**：`report/web/src/components/KlineChart.tsx` → `convertTradeToMarkers()`  
**数据来源 JSON**：`data/trades.json`  
**JSON 来源**：`report/writer/json_writer.py` → `export_trades_json()`  
**数据库查询**：`data/store.py` → `DataStore.query_trades(backtest_id)` → SQL 查询 `backtest_trades` 表

**字段链路**：
| 前端显示 | JSON 字段 | 数据库表 | 数据库字段 | 说明 |
|----------|-----------|----------|------------|------|
| 时间 | datetime | backtest_trades | datetime | 用于匹配 K线时间轴 |
| 方向 | direction | backtest_trades | direction | long/short |
| 开平 | offset | backtest_trades | offset | open/close/closetoday |

---

## 5. 权益图 (RUN-EQT-CONTAINER)

**前端组件**：`report/web/src/components/EquityChart.tsx`  
**数据来源 JSON**：`data/equity.json`（按品种索引）  
**JSON 来源**：`report/writer/json_writer.py` → `export_equity_json()`  
**数据库查询**：`data/store.py` → `DataStore.query_daily(backtest_id)` → SQL 查询 `backtest_daily` 表

**字段链路**：
| 图表显示 | JSON 字段 | 数据库表 | 数据库字段 |
|----------|-----------|----------|------------|
| 日期 | date | backtest_daily | date |
| 权益 | equity | backtest_daily | equity |
| 回撤 | drawdown | backtest_daily | drawdown |

---

## 6. 回测详情 (RUN-BDT-CONTAINER)

**前端组件**：`report/web/src/components/BacktestDetail.tsx`  
**数据来源 JSON**：`data/backtests.json`（当前选中品种的记录）  
**JSON 来源**：`report/writer/json_writer.py` → `export_backtests_json()`  
**数据库查询**：`data/store.py` → `DataStore.get_backtests_for_run(run_id)` → SQL 查询 `backtests` 表（主表）和 `backtest_params` 表（参数）

---

## 7. 参数优化 (OPTUNA)

**前端组件**：`report/web/src/components/OptunaCharts.tsx`（图表由 `EChartsChart.tsx` 渲染）  
**数据来源 JSON**：`data/optuna.json`  
**JSON 来源**：`report/writer/json_writer.py` → `export_optuna_json()` 调用 `report/reporter/optimizer.py` → `build_optuna_spec()`  
**数据库查询**：`data/store.py` → `DataStore.get_optuna_data(run_id)` → SQL 查询 `run_studies` 表和 Optuna 内部表（`studies`、`trials`、`trial_values`、`trial_params`）

**图表面板**：
| 面板 | 图表类型 | 后端函数 | 说明 |
|------|----------|----------|------|
| 优化历史 | ECharts scatter + line | `_build_history()` | 散点图：X=试验序号, Y=目标值；图例在右上角 |
| 参数重要性 | ECharts bar | `_build_importances()` | 用 optuna.importance.get_param_importances (fANOVA) |
| 平行坐标 | ECharts parallel | `_build_parallel()` | 每 trial 一条线穿过各参数轴和目标值轴 |
| 等高线 | ECharts scatter + visualMap | `_build_contour()` | 取前两个参数，颜色条在右侧竖排 |

**注意**：
- 平行坐标目标值使用 `t.value`（标量）而非 `t.values`（列表），确保 ECharts 正确解析
- vnpy 默认 `calculate_statistics()` 不输出 win_rate/win_loss_ratio/win_trades/loss_trades，这些字段在引擎层从交易 pnl 计算后注入 statistics 字典

---

## 8. 运行日志 (RUN-LOG-CONTAINER)

**前端组件**：`report/web/src/components/RunLogs.tsx`  
**数据来源 JSON**：`data/logs.json`  
**JSON 来源**：`report/writer/json_writer.py` → `export_logs_json()`  
**数据库查询**：目前日志数据来自 Python 内存记录（loguru 的 run.log → 文本提取），暂未存入数据库

---

## 数据库表结构 (SQLite)

使用 Peewee ORM，表定义在 `data/models.py`

### runs 表（批量回测运行记录）
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | Integer | 主键 |
| strategy | CharField | 策略名称 |
| engine | CharField | 回测引擎 |
| symbols | Integer | 回测品种数 |
| status | CharField | 运行状态 |
| use_fixed_seed | IntegerField | 0=随机种子, 1=固定种子 |
| random_seed | IntegerField | 实际使用的随机种子值（为 0 表示随机） |
| created_at | DateTimeField | 创建时间 |

### backtests 表（回测记录，完整字段）
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | Integer | 主键 |
| run_id | Integer | 外键，关联 runs 表 |
| symbol | CharField | 品种代码 |
| strategy | CharField | 策略名称 |
| strategy_version | CharField | 策略版本号 |
| git_hash | CharField | Git 提交哈希 |
| status | CharField | 回测状态（running/success/failed） |
| error_message | TextField | 错误信息 |
| start_date | CharField | 回测起始日期 |
| end_date | CharField | 回测结束日期 |
| total_days | IntegerField | 回测天数 |
| initial_capital | FloatField | 初始资金 |
| commission_rate | FloatField | 手续费率 |
| slippage | FloatField | 滑点 |
| price_tick | FloatField | 最小变动价位 |
| contract_size | IntegerField | 合约乘数 |
| kline_interval | CharField | K线周期 |
| end_balance | FloatField | 最终权益 |
| total_return | FloatField | 总收益率（比值） |
| annual_return | FloatField | 年化收益率（比值） |
| total_trades | IntegerField | 总交易次数 |
| win_trades | IntegerField | 盈利交易数 |
| loss_trades | IntegerField | 亏损交易数 |
| win_rate | FloatField | 胜率（比值） |
| max_consecutive_win | IntegerField | 最大连续盈利次数 |
| max_consecutive_loss | IntegerField | 最大连续亏损次数 |
| avg_win | FloatField | 平均盈利额 |
| avg_loss | FloatField | 平均亏损额 |
| win_loss_ratio | FloatField | 盈亏比 |
| sharpe_ratio | FloatField | 夏普比率 |
| max_drawdown | FloatField | 最大回撤（比值，负值） |
| max_drawdown_duration | IntegerField | 最大回撤持续天数 |
| daily_std | FloatField | 日收益率标准差 |
| return_drawdown_ratio | FloatField | 收益回撤比 |
| engine_config | TextField | JSON：引擎类型、优化器、study名等 |
| data_src | TextField | 数据源文件路径（CSV 等） |
| created_at | DateTimeField | 创建时间 |
| updated_at | DateTimeField | 更新时间 |

**字段来源说明**：
- vnpy `calculate_statistics()` 输出的字段：total_trade_count, total_return, annual_return, sharpe_ratio, max_drawdown, max_drawdown_duration, daily_std, return_drawdown_ratio
- vnpy **不输出**的字段（从交易 pnl 在引擎层计算后注入）：win_trades, loss_trades, win_rate, avg_win, avg_loss, win_loss_ratio, max_consecutive_win, max_consecutive_loss
- 回测引擎创建时预填的基本配置：initial_capital, commission_rate, slippage, price_tick, contract_size, kline_interval
- 插入/更新时补充的元数据：engine_config(JSON), data_src, git_hash, strategy_version

### backtest_params 表（回测参数）
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | Integer | 主键 |
| backtest_id | Integer | 外键，关联 backtests 表 |
| param_name | CharField | 参数名 |
| param_value | FloatField | 参数值 |

### backtest_trades 表（回测交易明细）
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | Integer | 主键 |
| backtest_id | Integer | 外键，关联 backtests 表（CASCADE 删除） |
| datetime | DateTimeField | 交易时间 |
| symbol | CharField | 品种代码 |
| direction | CharField | 方向（long/short） |
| offset | CharField | 开平（open/close/closetoday） |
| open_price | FloatField | 成交价（单笔成交中 open=close） |
| close_price | FloatField | 成交价 |
| quantity | FloatField | 数量（ORM 统一用 quantity 非 volume） |
| pnl | FloatField | 盈亏 |
| commission | FloatField | 手续费 |

### backtest_daily 表（回测每日资金曲线）
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | Integer | 主键 |
| backtest_id | Integer | 外键，关联 backtests 表（CASCADE 删除） |
| date | DateField | 日期 |
| equity | FloatField | 资金净值 |
| daily_return | FloatField | 当日净盈亏（金额，非百分比收益率） |
| drawdown | FloatField | 当日回撤 |

### run_studies 表（关联 runs 与 Optuna studies）
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | Integer | 主键 |
| run_id | Integer | 外键，关联 runs 表 |
| study_name | CharField | Optuna study 名称（唯一） |

---

## 数据文件结构

所有数据文件都生成在 `{output_dir}/r{run_id}/data/` 目录下：

| 文件名 | 说明 |
|--------|------|
| `run.json` | 本次运行的元信息（来自 runs 表） |
| `summary.json` | 品种汇总数据（每个品种最优回测一行，含 id/symbol/total_return/win_rate/win_loss_ratio 等） |
| `backtests.json` | 所有回测记录完整信息（含 params 和 daily 资金曲线） |
| `equity.json` | 所有品种权益曲线数据（来自 backtest_daily 表） |
| `kline_{symbol}.{interval}.json` | 单个品种 K线数据（来自 CSV 源文件） |
| `trades.json` | 所有品种交易记录（来自 backtest_trades 表） |
| `optuna.json` | Optuna 优化图表 ECharts option 配置（含优化历史、参数重要性、平行坐标、等高线） |
| `logs.json` | 运行日志（从 run.log 文本提取） |

---

## 数据管理组件 (Python)

### 核心模块职责链
1. **`data/models.py`**：数据库表定义（Peewee ORM Model）
2. **`data/store.py`**：数据库操作实现（DataStore 类，所有 CRUD）
3. **`data/manager.py`**：对外暴露的 DataManager 类（封装 store）
4. **`config/app_config.py`**：配置管理（回测参数、优化器配置、数据路径）
5. **`backtest/vnpy_backtest_engine.py`**：vnpy 回测引擎封装（含胜率/盈亏比字段补算）
6. **`backtest/optimizer.py`**：Optuna 参数优化器（Grid/Bayesian search）
7. **`report/cache/kline.py`**：K线数据缓存与格式转换
8. **`report/reporter/optimizer.py`**：ECharts 图表配置生成（历史/重要性/平行坐标/等高线）
9. **`report/writer/json_writer.py`**：导出 JSON 文件（各板块独立 export 函数）
10. **`report/builder.py`**：完整构建流程控制（增量导出 + 前端构建 + 数据注入 HTML）
11. **前端 React 组件**：读取 JSON 并渲染（Page 组件 + 图表组件）