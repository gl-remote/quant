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
| `Fill` | `timestamp, action, price, volume, pnl` |
| `StrategyPosition` | `direction, entry_price, volume` |

---

## 回测引擎 API

### VnpyBacktestEngine

**模块路径**: `backtest.vnpy_backtest_engine.VnpyBacktestEngine`

**核心方法**:

```python
class VnpyBacktestEngine:
    def run(self, pairs: list[tuple[str, DataFrame, Strategy]]) -> list[dict]
    def run_walk_forward(self, data, symbol, strategy, ...) -> dict
```

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