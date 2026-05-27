# API 参考

> 版本: 0.2.0-dev | 更新日期: 2026-05-26

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

#### 元数据查询

| 方法 | 说明 | 参数 | 返回值 |
|------|------|------|--------|
| `get_all_symbols()` | 获取所有可用品种 | 无 | `list[str]` |
| `search_symbols(pattern)` | 正则搜索品种 | `pattern: str` | `list[str]` |
| `get_symbol_info(symbol)` | 获取品种元数据 | `symbol: str` | `SymbolInfo` |
| `get_data_summary()` | 获取数据汇总 | 无 | `DataSummary` |

#### 数据加载

```python
# 加载 K 线数据（带 Pandera 验证）
df = dm.load_kline(
    symbol="DCE.m2509",
    start_date="2024-01-01",  # 可选
    end_date="2024-12-31",    # 可选
    interval="1m"              # 可选，默认从配置读取
)

# 失败返回 None
df = dm.load_kline("DCE.m2509")
```

#### 回测记录

| 方法 | 说明 | 返回值 |
|------|------|--------|
| `insert_backtest(...)` | 插入回测记录 | `int` (backtest_id) |
| `query_backtests(...)` | 查询回测列表 | `list[BacktestRecord]` |
| `get_backtest(backtest_id)` | 查询单条回测 | `BacktestRecord | None` |
| `insert_backtest_trades(backtest_id, trades)` | 批量插入交易明细 | `int` |
| `query_trades(backtest_id)` | 查询交易明细 | `list[TradeRecord]` |
| `insert_backtest_daily(backtest_id, daily)` | 批量插入每日资金曲线 | `int` |
| `query_daily(backtest_id)` | 查询每日资金曲线 | `list[dict]` |
| `delete_backtest(backtest_id)` | 删除回测记录 | `bool` |

#### 资源管理

| 方法 | 说明 |
|------|------|
| `clear_cache()` | 清除数据缓存 |
| `close()` | 关闭数据库连接 |

---

### DataStore

**模块路径**: `data.store.DataStore`

**功能**: 数据库操作层，被 DataManager 调用，外部模块不应直接使用。

#### 核心方法

| 方法 | 说明 |
|------|------|
| `log(command, message, symbol=None, status="INFO")` | 写入操作日志 |
| `get_metadata(symbol)` | 查询品种元数据 |
| `upsert_metadata(symbol, filepath, ...)` | 插入或更新元数据 |
| `insert_backtest_detailed(...)` | 插入完整回测记录 |
| `insert_backtest_trades(backtest_id, trades)` | 批量插入交易 |
| `query_backtests(symbol, strategy, status, limit)` | 查询回测记录 |
| `get_backtest(backtest_id)` | 查询单条回测 |
| `insert_backtest_daily(backtest_id, daily)` | 批量插入每日数据 |
| `delete_backtest(backtest_id)` | 删除回测及关联数据 |

---

## 策略层 API

### Strategy

**模块路径**: `strategies.core.base.Strategy`

**功能**: 策略抽象基类，所有策略实现必须继承此类。

#### 核心接口

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

#### Bar

```python
@dataclass
class Bar:
    symbol: str
    datetime: str
    open: float
    high: float
    low: float
    close: float
    volume: float
```

#### Signal

```python
@dataclass
class Signal:
    action: str = ""          # "buy" / "sell" / ""
    volume: int = 0           # 预计算的手数
    reason: str = ""          # 信号原因（如 SIGNAL_GOLDEN_CROSS）
```

#### Fill

```python
@dataclass
class Fill:
    timestamp: str
    symbol: str
    action: str               # "buy" / "sell"
    price: float
    volume: int
    reason: str
    pnl: float = 0.0          # 盈亏
    commission: float = 0.0   # 手续费
```

#### StrategyPosition

```python
@dataclass
class StrategyPosition:
    direction: str = ""       # "long" / ""
    entry_price: float = 0.0
    volume: int = 0
```

---

## 回测引擎 API

### VnpyBacktestEngine

**模块路径**: `backtest.vnpy_backtest_engine.VnpyBacktestEngine`

**功能**: vn.py 回测引擎，纯执行器，不负责数据加载和策略创建。

#### 初始化

```python
from backtest import VnpyBacktestEngine
from config.app_config import BacktestConfig
from data import DataManager

engine = VnpyBacktestEngine(backtest_config, data_manager)
```

#### 核心方法

**run()** — 执行多策略 × 多品种回测

```python
pairs = [
    ("DCE.m2509", df1, strategy1),
    ("DCE.m2511", df1, strategy2),
]
results = engine.run(pairs)
```

**run_walk_forward()** — 执行滚动时间窗口验证

```python
result = engine.run_walk_forward(
    data=df,
    symbol="DCE.m2509",
    strategy=strategy,
    train_size=None,    # None 时按比例计算
    val_size=None,
    test_size=None,
    step=None,
)
```

---

## 优化器 API

### OptunaOptimizer

**模块路径**: `optimizer.optuna_search.OptunaOptimizer`

**功能**: 统一参数优化器，支持网格搜索和贝叶斯优化两种模式。

```python
from optimizer import OptunaOptimizer

# 网格搜索模式
opt = OptunaOptimizer(
    engine=engine,
    datasets=datasets,
    strategy_name="ma",
    search_space={
        "sma_short": {"type": "int", "low": 5, "high": 30, "step": 5},
        "sma_long": {"type": "int", "low": 30, "high": 200, "step": 10},
    },
    strategy_params={},
    capital=100000.0,
    contract_size=10,
    n_trials=50,
    search_type="grid",  # "grid" 或 "bayesian"
)
result = opt.optimize()
```

---

## 配置 API

### ProjectConfig

**模块路径**: `config.app_config.ProjectConfig`

**功能**: 全局配置单例，统一配置访问入口。

#### 获取配置

```python
from config import ProjectConfig

cfg = ProjectConfig.instance()

# 访问回测配置
bc = cfg.backtest
print(bc.initial_capital)
print(bc.commission_rate)

# 访问策略配置
sc = cfg.get_strategy_config("ma")
print(sc.sma_short)
print(sc.sma_long)

# 访问账户信息
account = cfg.get_account_info()
if account:
    print(account.api_key)
```

#### 配置模型结构

| 模型 | 说明 |
|------|------|
| `AppConfig` | 应用配置 |
| `EnvironmentConfig` | 环境配置 |
| `StrategyItemConfig` | 策略配置项 |
| `BacktestConfig` | 回测配置 |
| `SplitConfig` | 数据集划分配置 |
| `OptimizerConfig` | 优化器配置 |
| `DataConfig` | 数据配置 |
| `ExportConfig` | 导出配置 |
| `SystemConfig` | 系统配置 |
| `AccountInfo` | 账户信息 |

---

## 通用工具 API

### constants

**模块路径**: `common.constants`

**功能**: 全局常量字典。

#### 交易方向

```python
TRADE_ACTION_BUY = "buy"
TRADE_ACTION_SELL = "sell"
TRADE_DIRECTION_LONG = "long"
TRADE_DIRECTION_SHORT = "short"
```

#### 信号原因

```python
SIGNAL_GOLDEN_CROSS = "golden_cross"
SIGNAL_DEATH_CROSS = "death_cross"
SIGNAL_STOP_LOSS = "stop_loss"
SIGNAL_TAKE_PROFIT = "take_profit"
```

#### 默认参数

```python
DEFAULT_INITIAL_CAPITAL = 100000.0
DEFAULT_COMMISSION_RATE = 0.0003
DEFAULT_SMA_SHORT = 5
DEFAULT_SMA_LONG = 60
DEFAULT_STOP_LOSS_RATIO = 0.02
DEFAULT_TAKE_PROFIT_RATIO = 0.05
```

### formulas

**模块路径**: `common.formulas`

**功能**: 量化计算公式库。

| 函数 | 说明 | 参数 | 返回值 |
|------|------|------|--------|
| `simple_moving_average(data, period)` | 计算 SMA | `data: list[float], period: int` | `float` |
| `golden_cross(prev_short, prev_long, cur_short, cur_long)` | 金叉检测 | 四个 float | `bool` |
| `death_cross(prev_short, prev_long, cur_short, cur_long)` | 死叉检测 | 四个 float | `bool` |
| `stop_loss_triggered(entry_price, current_price, ratio)` | 止损检查 | `float, float, float` | `bool` |
| `take_profit_triggered(entry_price, current_price, ratio)` | 止盈检查 | `float, float, float` | `bool` |
| `position_size(capital, position_ratio, price, contract_size)` | 计算仓位 | 四个参数 | `int` |
| `calculate_fifo_profit(fills)` | 计算 FIFO 盈亏 | `list[Fill]` | `float` |
| `total_return(initial, final, total_trades)` | 计算总收益率 | 三个参数 | `float` |
| `win_rate(win_trades, total_trades)` | 计算胜率 | 两个 int | `float` |

### metrics

**模块路径**: `common.metrics`

**功能**: 绩效指标计算。

| 函数 | 说明 |
|------|------|
| `max_drawdown(curve)` | 计算最大回撤 |
| `sharpe_ratio(returns, risk_free_rate=0)` | 计算夏普比率 |

### formatting

**模块路径**: `common.formatting`

**功能**: 安全格式化工具。

| 函数 | 说明 |
|------|------|
| `format_pct(value, decimals=2)` | 格式化百分比 |
| `format_float(value, decimals=2)` | 格式化浮点数 |
| `ensure_float(value, default=0.0)` | 安全转换为 float |
| `parse_percentage(value)` | 解析百分比字符串 |

---

## 报告 API

### build_report

**模块路径**: `report.__init__.py`

**功能**: 生成回测报告。

```python
from report import build_report

html = build_report(
    backtest_id=42,
    data_manager=dm,
    output_path="report.html",
)
```

### build_optimizer_report

**模块路径**: `report.optimizer_report`

**功能**: 生成优化器报告。

```python
from report import build_optimizer_report

html = build_optimizer_report(
    study_db_url="sqlite:///optuna_studies.db",
    study_name="my_study",
    best_params={},
    best_value=0.5,
    backtest_ids=[42, 43, 44],
)
```

---

## CLI API

### 命令入口

**模块路径**: `cli.main.main`

**功能**: 命令行入口函数。

```python
from cli.main import main

if __name__ == "__main__":
    main()
```

### 命令实现

| 命令 | 模块 | 说明 |
|------|------|------|
| `export` | `cli.commands.export` | 导出 K 线数据 |
| `test` | `cli.commands.test` | 策略测试 |
| `backtest` | `cli.commands.backtest` | 统一回测 |
| `report` | `cli.commands.report` | 报告管理 |
| `live` | `cli.commands.live` | 实盘交易 |

---

## 示例代码

### 示例 1: 简单回测

```python
from data import DataManager
from strategies.core import load_strategy
from backtest import VnpyBacktestEngine
from config import ProjectConfig

# 加载配置和数据
cfg = ProjectConfig.instance()
dm = DataManager()
df = dm.load_kline("DCE.m2509", "2024-01-01", "2024-12-31")

# 创建策略
strategy = load_strategy(
    "ma",
    strategy_params={"sma_short": 5, "sma_long": 60},
    capital=100000.0,
    contract_size=10,
)

# 执行回测
engine = VnpyBacktestEngine(cfg.backtest, dm)
results = engine.run([("DCE.m2509", df, strategy)])

# 输出结果
for r in results:
    if r['success']:
        stats = r['statistics']
        print(f"收益率: {stats.get('total_return', 0):.2%}")
        print(f"夏普比率: {stats.get('sharpe_ratio', 0):.2f}")
        print(f"最大回撤: {stats.get('max_drawdown', 0):.2%}")
```

### 示例 2: Walk-Forward 验证

```python
from data import DataManager
from strategies.core import load_strategy
from backtest import VnpyBacktestEngine
from config import ProjectConfig

cfg = ProjectConfig.instance()
dm = DataManager()
df = dm.load_kline("DCE.m2509", "2024-01-01", "2024-12-31")

strategy = load_strategy("ma", capital=100000.0)

engine = VnpyBacktestEngine(cfg.backtest, dm)
wf_result = engine.run_walk_forward(df, "DCE.m2509", strategy)

if wf_result['success']:
    agg = wf_result['aggregate']
    print(f"窗口数: {wf_result['windows']}")
    print(f"OOS平均收益: {agg['return_mean']:.2%}")
    print(f"稳定性评分: {agg['stability_score']:.2f}")
```

### 示例 3: 参数优化

```python
from data import DataManager
from backtest import VnpyBacktestEngine
from optimizer import GridOptimizer
from config import ProjectConfig

cfg = ProjectConfig.instance()
dm = DataManager()

# 加载数据
datasets = [("DCE.m2509", dm.load_kline("DCE.m2509"))]

# 配置优化器
engine = VnpyBacktestEngine(cfg.backtest, dm)
opt = GridOptimizer(
    engine=engine,
    datasets=datasets,
    strategy_name="ma",
    param_grid={
        "sma_short": [5, 10, 15],
        "sma_long": [30, 60, 90],
    },
    strategy_params={},
    capital=100000.0,
    contract_size=10,
)

# 执行优化
result = opt.run()
print(f"最优夏普: {result.best_value:.4f}")
print(f"最优参数: {result.best_params}")
```
