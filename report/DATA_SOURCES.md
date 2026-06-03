# 回测报告数据来源说明

本文档说明报告 web 页面所有可见数据的完整链路，从前端展示，到读取 JSON，到 Python 写入 JSON，到查询数据库，逐层打通。

---

## 完整链路概览

```
用户看到的页面
    ↓
前端 React 组件
    ↓ (useFetchJson)
JSON 数据文件
    ↓ (report.writer.json_writer)
Python 数据处理
    ↓ (data.store.DataStore)
SQLite 数据库
```

---

## 页面结构与板块 - 完整链路说明

### 1. 页面头部 (RUN-PG-HEADER)

**前端组件**：`web/src/pages/RunPage.tsx`  
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

---

## 2. 指标总览 (RUN-MET-CONTAINER)

**前端组件**：`web/src/components/MetricCards.tsx`  
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

**前端组件**：`web/src/components/SymbolTable.tsx`  
**数据来源 JSON**：`data/summary.json` 和 `data/backtests.json`  
**JSON 来源**：`report/writer/json_writer.py` → `export_summary_json()`  
**数据库查询**：`data/store.py` → `DataStore.get_run_summary(run_id)` → SQL 查询 `backtests` 表，按 symbol 分组，每个 symbol 取 total_return 最大的记录

**表格列链路**：
| 列名 | JSON 字段 | 数据库表 | 数据库字段 | 说明 |
|------|-----------|----------|------------|------|
| 品种 | symbol | backtests | symbol |  |
| 收益率 | total_return | backtests | total_return | 已转换为百分比显示；计算公式：`(期末权益-初始资金)/初始资金`（比值，如0.15=15%） |
| 夏普 | sharpe | backtests | sharpe_ratio |  |
| 最大回撤 | max_drawdown | backtests | max_drawdown | 已转换为百分比显示 |
| 交易次数 | total_trades | backtests | total_trades |  |
| 胜率 | win_rate | backtests | win_rate | 数据库存的是比值（如 0.5），前端显示为百分比 |
| K线周期 | kline_interval | backtests | kline_interval |  |

---

## 4. K线图 (RUN-KLINE-CONTAINER)

K线图是最复杂的，包含 K线主图、成交量、MACD、KDJ、交易标记。

### 4.1 K线数据 - 完整链路

**前端组件**：`web/src/components/KlineChart.tsx`  
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

**MACD/ KDJ 基准线**：使用 `createPriceLine()` 方法（在指标 Series 上创建，不是静态画线），自动跟随十字光标联动

### 4.3 交易标记 - 完整链路

**前端组件**：`web/src/components/KlineChart.tsx` → `convertTradeToMarkers()`  
**数据来源 JSON**：`data/trades.json`  
**JSON 来源**：`report/writer/json_writer.py` → `export_trades_json()`  
**数据库查询**：`data/store.py` → `DataStore.query_trades(backtest_id)` → SQL 查询 `backtest_trades` 表

**字段链路**：
| 前端显示 | JSON 字段 | 数据库表 | 数据库字段 | 说明 |
|----------|-----------|----------|------------|------|
| 时间 | datetime | backtest_trades | datetime | 用于匹配 K线时间轴 |
| 方向 | direction | backtest_trades | direction | 可能包含前缀（如 "direction.long"），前端清理 |
| 开平 | offset | backtest_trades | offset | 可能包含前缀（如 "offset.open"），前端清理 |

---

## 5. 权益图 (RUN-EQT-CONTAINER)

**前端组件**：`web/src/components/EquityChart.tsx`  
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

**前端组件**：`web/src/components/BacktestDetail.tsx`  
**数据来源 JSON**：`data/backtests.json`（当前选中品种的记录）  
**JSON 来源**：`report/writer/json_writer.py` → `export_backtests_json()`  
**数据库查询**：`data/store.py` → `DataStore.get_backtests_for_run(run_id)` → SQL 查询 `backtests` 表（主表）和 `backtest_params` 表（参数）

---

## 7. 参数优化 (OPTUNA)

**前端组件**：`web/src/components/OptunaCharts.tsx`  
**数据来源 JSON**：`data/optuna.json`  
**JSON 来源**：`report/writer/json_writer.py` → `export_optuna_json()` 和 `report/optuna_spec.py`  
**数据库查询**：`data/store.py` → `DataStore.get_optuna_data(run_id)` → SQL 查询 `run_studies` 表和 Optuna 自己的表（`studies`、`trials`、`trial_values`、`trial_params`）

---

## 8. 运行日志 (RUN-LOG-CONTAINER)

**前端组件**：`web/src/components/RunLogs.tsx`  
**数据来源 JSON**：`data/logs.json`  
**JSON 来源**：`report/writer/json_writer.py` → `export_logs_json()`  
**数据库查询**：目前日志数据来自 Python 内存记录，暂未存入数据库（TODO）

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
| created_at | DateTimeField | 创建时间 |

### backtests 表（回测记录）
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | Integer | 主键 |
| run_id | Integer | 外键，关联 runs 表 |
| symbol | CharField | 品种代码 |
| strategy | CharField | 策略名称 |
| status | CharField | 回测状态 |
| start_date | CharField | 回测起始日期 |
| end_date | CharField | 回测结束日期 |
| initial_capital | FloatField | 初始资金 |
| end_balance | FloatField | 最终资金 |
| total_return | FloatField | 总收益率 |
| annual_return | FloatField | 年化收益率 |
| sharpe_ratio | FloatField | 夏普比率 |
| max_drawdown | FloatField | 最大回撤 |
| win_rate | FloatField | 胜率 |
| total_trades | IntegerField | 总交易次数 |
| data_src | TextField | 数据源（CSV 路径） |

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
| backtest_id | Integer | 外键，关联 backtests 表 |
| datetime | DateTimeField | 交易时间 |
| symbol | CharField | 品种代码 |
| direction | CharField | 方向（long/short） |
| offset | CharField | 开平（open/close） |
| open_price | FloatField | 开仓价格 |
| close_price | FloatField | 平仓价格 |
| quantity | FloatField | 数量 |
| pnl | FloatField | 盈亏 |
| commission | FloatField | 手续费 |

### backtest_daily 表（回测每日资金曲线）
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | Integer | 主键 |
| backtest_id | Integer | 外键，关联 backtests 表 |
| date | DateField | 日期 |
| equity | FloatField | 资金净值 |
| daily_return | FloatField | 当日收益率 |
| drawdown | FloatField | 当日回撤 |

### run_studies 表（关联 runs 与 Optuna studies）
| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | Integer | 主键 |
| run_id | Integer | 外键，关联 runs 表 |
| study_name | CharField | Optuna study 名称 |

---

## 数据文件结构

所有数据文件都生成在 `{output_dir}/r{run_id}/data/` 目录下：

| 文件名 | 说明 |
|--------|------|
| `run.json` | 本次运行的元信息（来自 runs 表） |
| `summary.json` | 品种汇总数据（每个品种最优回测） |
| `backtests.json` | 所有回测记录完整信息 |
| `equity.json` | 所有品种权益曲线数据（来自 backtest_daily 表） |
| `kline_{symbol}.{interval}.json` | 单个品种 K线数据（来自 CSV 源文件） |
| `trades.json` | 所有品种交易记录（来自 backtest_trades 表） |
| `optuna.json` | Optuna 优化数据（来自 Optuna 表） |
| `logs.json` | 运行日志（可选） |

---

## 数据管理组件 (Python)

### 核心模块职责链
1. **`data/models.py`**：数据库表定义（ORM Model）
2. **`data/store.py`**：数据库操作实现（DataStore 类）
3. **`data/manager.py`**：对外暴露的 DataManager 类（封装 store 的操作）
4. **`report/cache/kline.py`**：K线数据缓存与格式转换
5. **`report/writer/json_writer.py`**：导出 JSON 文件
6. **`report/builder.py`**：完整构建流程控制
7. **前端 React 组件**：读取 JSON 并渲染
