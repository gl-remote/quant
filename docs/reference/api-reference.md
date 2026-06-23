# API 参考

> 版本: 0.2.0-dev | 更新日期: 2026-05-27

---

## 数据层 API

### DataManager

**模块路径**: `data.manager.DataManager`

**功能**: 统一数据访问入口，对外隐藏数据库实现细节。

#### 初始化

```python
from data import DataManager

dm = DataManager(config_manager=None)
```

#### 核心方法

| 方法 | 说明 | 参数 | 返回值 |
|------|------|------|--------|
| `get_all_symbols()` | 获取所有可用品种 | 无 | `list[str]` |
| `search_symbols(pattern)` | 正则搜索品种 | `pattern: str` | `list[str]` |
| `get_symbol_info(symbol)` | 获取品种元数据 | `symbol: str` | `SymbolInfo` |
| `load_kline(symbol, start_date, end_date, interval)` | 加载 K 线数据 | 可选参数 | `DataFrame` |
| `insert_backtest(...)` | 插入回测记录 | 多个参数 | `int` (backtest_id) |
| `query_backtests(...)` | 查询回测列表 | 过滤条件 | `list[BacktestRecord]` |
| `get_backtest(backtest_id)` | 查询单条回测 | `backtest_id: int` | `BacktestRecord | None` |

---

## 策略层 API

### Strategy

**模块路径**: `strategies.core.base.Strategy`

**功能**: 策略抽象基类。

```python
from strategies.core.base import Strategy
from strategies.core.types import Bar, Signal, Fill, StrategyPosition

class MyStrategy(Strategy):
    name: str = "my_strategy"
    VERSION: str = "v1.0.0"
    
    def on_bar(self, bar: Bar) -> Signal:
        """处理一根 K 线，返回交易决策"""
    
    def on_fill(self, fill: Fill) -> None:
        """订单成交回调"""
    
    @property
    def position(self) -> StrategyPosition:
        """当前持仓"""
    
    def reset(self) -> None:
        """重置策略状态"""
```

### 数据类型

| 类型 | 关键字段 |
|------|----------|
| `Bar` | `symbol, datetime, open, high, low, close, volume` |
| `Signal` | `action, volume, reason` |
| `Fill` | `timestamp, action, price, volume, reason`（注意：Fill 是单笔成交回执，不含 pnl/commission，逐笔净盈亏在回测引擎 FIFO 配对层面计算） |
| `StrategyPosition` | `direction, entry_price, volume` |

---

## 回测引擎 API

### VnpyBacktestEngine

**模块路径**: `backtest.vnpy_backtest_engine.VnpyBacktestEngine`

**核心方法**:

```python
class VnpyBacktestEngine:
    def run(self, pairs: list[tuple[str, DataFrame, Strategy]]) -> list[BacktestResult]
    def run_walk_forward(self, data, symbol, strategy, ...) -> WalkForwardResult
```

---

## 核心数据结构

### BacktestResult（回测结果）

**模块路径**: `common.types.BacktestResult`

**功能**: 回测引擎输出的完整结果，包含 vnpy 全量统计 + 自行计算的交易级指标。

**字段分组**:

| 分组 | 关键字段 | 来源 |
|------|---------|------|
| 元数据 | `symbol, strategy, version, git_hash, status, dates` | 引擎入参 |
| **核心绩效** `[vnpy]` | `total_return(%, 如15.5=15.5%), end_balance, sharpe_ratio, max_drawdown(绝对金额), annual_return(%)` | `engine.calculate_statistics()` |
| **盈亏汇总** `[vnpy]` | `total_net_pnl, total_commission, total_slippage, total_turnover` | 同上 |
| **交易日统计** `[vnpy]` | `profit_days, loss_days, daily_trade_count, daily_return_pct(%)` | 同上 |
| 交易级统计 | `win_trades(pnl>0), loss_trades(pnl<0), win_rate, avg_win, avg_loss, win_loss_ratio` | 基于 trades 聚合 |
| 进阶指标 `[vnpy]` | `ewm_sharpe, rgr_ratio, max_ddpercent(%), return_drawdown_ratio` | 同上 |

**格式约定**:
- `total_return`, `annual_return`, `max_ddpercent`: 百分比格式（如 `15.5` = 15.5%）
- `max_drawdown`: 绝对金额（如 `50000.0` = 回撤 5 万元）
- `win_rate`: 比值 (0~1)，store 层输出时乘以 100
- `pnl`（逐笔）: 净盈亏 = 毛利 - commission - slippage

### BacktestRecord（数据库查询模型）

**模块路径**: `common.schemas.BacktestRecord`

**功能**: 从 SQLite 查询回测记录的 Pydantic 验证模型，字段与 backtests 表一一对应。

---

## 报告模块 API

### ReportBuilder

**模块路径**: `report.builder`

**核心方法**:

```python
from report.builder import ReportBuilder

builder = ReportBuilder(db_path, output_dir)
builder.build_all(run_id)                    # 构建完整报告
builder.export_kline_json(symbol)           # 导出 K 线（带缓存）
builder.write_entry_html(output_dir, run_id) # 写入入口 HTML
builder.build_frontend(output_dir)           # 触发前端构建
```

---

## 配置 API

### ProjectConfig

**模块路径**: `config.app_config.ProjectConfig`

```python
from config import ProjectConfig

cfg = ProjectConfig.instance()
bc = cfg.backtest                    # 回测配置
sc = cfg.get_strategy_config("ma")   # 策略配置
```

---

## 通用工具 API

### constants

```python
TRADE_ACTION_BUY = "buy"
TRADE_ACTION_SELL = "sell"
SIGNAL_GOLDEN_CROSS = "golden_cross"
SIGNAL_DEATH_CROSS = "death_cross"
```

### formulas

| 函数 | 说明 |
|------|------|
| `simple_moving_average(data, period)` | 计算 SMA |
| `golden_cross(prev_short, prev_long, cur_short, cur_long)` | 金叉检测 |
| `position_size(capital, ratio, price, contract_size)` | 计算仓位 |

### metrics

| 函数 | 说明 |
|------|------|
| `max_drawdown(curve)` | 最大回撤 |
| `sharpe_ratio(returns, risk_free_rate=0)` | 夏普比率 |