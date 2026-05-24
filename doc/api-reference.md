# API 接口文档

> 版本: 0.2.0 | 更新日期: 2026-05-24

---

## 核心回测引擎

### VnpyBacktestEngine

[VnpyBacktestEngine](file:///Users/REDACTED_API_KEY/Documents/src/quant/backtest/backtest_engine.py) 是整个回测子系统的编排器，封装了从数据加载到过拟合评估的完整流水线。

```python
from backtest import VnpyBacktestEngine

engine = VnpyBacktestEngine(config)
engine.set_strategy_params(sma_short=5, sma_long=20)
result = engine.run_full_pipeline(symbol='DCE.m2509')
```

#### 构造函数

```python
VnpyBacktestEngine(config: Dict[str, Any])
```

`config` 字典结构参见 [参数配置说明](configuration.md) 中的 `backtest` 段。

#### set_strategy_params

```python
set_strategy_params(**kwargs)
```

支持的参数：`sma_short`(int), `sma_long`(int), `stop_loss_ratio`(float), `take_profit_ratio`(float), `position_ratio`(float)

#### run_full_pipeline

```python
run_full_pipeline(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]
```

执行完整五阶段流水线，返回结果字典：

```python
{
    'success': bool,
    'symbol': str,
    'datasets': {                     # 数据集信息
        'train': {...},
        'val': {...},
        'test': {...},
    },
    'train': {                        # 训练集回测原始结果
        'dataset_name': str,
        'statistics': {...},
        'daily_results': [...],
    },
    'val': {...},                     # 验证集结果（同上结构）
    'test': {...},                    # 测试集结果（同上结构）
    'train_report': {...},            # 训练集格式化报告
    'val_report': {...},              # 验证集格式化报告
    'test_report': {...},             # 测试集格式化报告
    'comparison': {...},              # 三阶段对比分析
}
```

### 回传统计结构 `statistics`

```python
{
    'start_date': str,           # YYYY-MM-DD
    'end_date': str,             # YYYY-MM-DD
    'total_days': int,           # 总交易日
    'total_trades': int,         # 总交易次数
    'win_trades': int,           # 盈利次数
    'loss_trades': int,          # 亏损次数
    'win_rate': float,           # 胜率
    'total_net_pnl': float,      # 总净盈亏
    'end_balance': float,        # 期末权益
    'max_drawdown': float,       # 最大回撤比例
    'sharpe_ratio': float,       # 年化夏普比率
    'annual_return': float,      # 年化收益率
    'average_win': float,        # 平均盈利
    'average_loss': float,       # 平均亏损
    'win_loss_ratio': float,     # 盈亏比
}
```

### 对比分析结构 `comparison`

```python
{
    'meta': {
        'symbol': str,
        'train': str, 'val': str, 'test': str,
    },
    'metrics_table': {                    # 七项指标的三阶段值
        'total_return':   {'train': float, 'val': float, 'test': float},
        'annual_return':  {...},
        'sharpe_ratio':   {...},
        'max_drawdown':   {...},
        'win_rate':       {...},
        'profit_loss_ratio': {...},
        'total_trades':   {...},
    },
    'return_degradation': {               # 收益递减分析
        'train_to_val': float,            # 百分比差值
        'val_to_test': float,
        'train_to_test': float,
        'risk_level': str,                # high/medium/low/none
        'message': str,                   # 中文解读
    },
    'risk_increase': {                    # 风险递增分析
        'train_to_val': float,
        'val_to_test': float,
        'train_to_test': float,
        'risk_level': str,
        'message': str,
    },
    'stability_analysis': {               # 稳定性分析
        'return_cv': float,               # 收益率变异系数
        'sharpe_cv': float,
        'winrate_cv': float,
        'drawdown_cv': float,
        'avg_cv': float,                  # 平均变异系数
        'stability': str,                 # high/medium/low
        'message': str,
    },
    'overfitting_assessment': {           # 过拟合综合评估
        'score': int,                     # 0-100
        'level': str,                     # high/medium/low/none
        'advice': str,
        'details': {
            'return_degradation': str,    # 收益率下降比例
            'drawdown_increase': str,     # 回撤增加比例
            'sharpe_decline': str,        # 夏普下降比例
            'winrate_decline': str,       # 胜率下降比例
        },
    },
}
```

## 策略桥接器 API

### VnpyStrategyBridge

位于 [strategies/bridges/vnpy_bridge.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/strategies/bridges/vnpy_bridge.py)，继承 `vnpy_ctastrategy.CtaTemplate`，将 vn.py 的 K 线数据转换为标准 Bar 并委托给策略核心。

**生命周期**：

```python
bridge = VnpyStrategyBridge(cta_engine, strategy_name, vt_symbol, setting)
# vn.py 自动调用:
#   bridge.on_init()    → 初始化参数
#   bridge.on_start()   → 启动策略
#   bridge.on_bar(bar)  → 每个 Bar 调用决策
#   bridge.on_stop()    → 停止策略
```

**核心流程**：

```
vnpy BarData → 标准 Bar → Strategy.on_bar() → Signal → self.buy()/sell() → on_fill()
```

| 方法 | 说明 |
|------|------|
| `on_bar(bar: BarData)` | vn.py 回调入口，转换数据后委托给策略核心 |
| `_send_order(signal)` | 将 Signal 翻译为 vn.py 的 buy/sell/short/cover 指令 |
| `_on_trade(trade)` | vn.py 成交回调，构造 Fill 通知策略核心 |

### TqsdkStrategyBridge

位于 [strategies/bridges/tqsdk_bridge.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/strategies/bridges/tqsdk_bridge.py)，纯 Python 类，不继承任何框架类。

**运行模式**：

```python
bridge = TqsdkStrategyBridge(api, symbol, strategy_core)
bridge.run()            # 无 GUI 模式
# 或
bridge.run_with_gui()   # Web 图形界面模式
```

**核心流程**：

```
tqsdk kline_serial (DataFrame) → 标准 Bar → Strategy.on_bar() → Signal → TargetPosTask
```

| 方法 | 说明 |
|------|------|
| `run()` | 主循环，监听 K 线更新并驱动策略决策 |
| `run_with_gui()` | 同上，附加 web 图形界面 |
| `_process_new_bars()` | 处理新增 K 线，逐根调用 `on_bar` |
| `_execute_signal(signal)` | 通过 `TargetPosTask` 调仓 |

---

## 信号优先级 (Signal Priority)

持仓状态下多个出场条件可能同时触发，**`if/elif` 顺序决定实际优先级**：

```
止损 (stop_loss)  >  止盈 (take_profit)  >  死叉 (death_cross)
```

| 优先级 | 信号 | 触发条件 | 说明 |
|--------|------|---------|------|
| 1 (最高) | `stop_loss` | `(entry - current) / entry >= stop_loss_ratio` | 风控止损，优先于一切 |
| 2 | `take_profit` | `(current - entry) / entry >= take_profit_ratio` | 获利了结 |
| 3 (最低) | `death_cross` | 短均线下穿长均线 | 趋势反转信号 |

空仓状态下仅检测 `golden_cross`（金叉）买入信号。

**设计原因**：

- 止损优先级最高确保风险可控，避免死叉信号覆盖止损
- 止盈优先于死叉确保利润锁定，不被趋势信号的滞后性侵蚀
- 如需自定义优先级，修改策略核心中 `on_bar()` 的 `if/elif` 顺序

---

## 数据加载模块

位于 [backtest/data_loader.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/backtest/data_loader.py)。

| 函数 | 说明 |
|------|------|
| `load_csv_data(data_dir, symbol) -> Optional[DataFrame]` | 从 CSV 目录加载品种数据 |
| `split_datasets(df, train_ratio, val_ratio, test_ratio, random_seed, shuffle) -> Tuple[DataFrame, DataFrame, DataFrame]` | 划分三数据集 |
| `df_to_vnpy_datalines(df, symbol) -> list` | DataFrame 转 vnpy BarData 列表 |
| `get_dataset_info(df, name) -> Dict` | 获取数据集统计摘要 |

---

## 报告与对比分析模块

### 报告生成 (report.py)

| 函数 | 说明 |
|------|------|
| `generate_dataset_report(statistics, daily_results, dataset_name, symbol, initial_capital, output_dir, save_trades, save_equity) -> Dict` | 生成单数据集报告并序列化为 JSON |
| `format_console_report(report, dataset_name) -> str` | 格式化控制台输出 |

### 对比分析 (comparison.py)

| 函数 | 说明 |
|------|------|
| `compare_datasets(train_report, val_report, test_report, symbol) -> Dict` | 三阶段对比分析主入口 |
| `format_comparison_report(comparison) -> str` | 格式化对比报告 |

---

## 策略核心

### MaStrategyCore

位于 [strategies/ma_strategy.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/strategies/ma_strategy.py)，纯业务逻辑，无框架依赖。

```python
from strategies.core import MaStrategyCore, TradingConfig

config = TradingConfig(sma_short=5, sma_long=20)
core = MaStrategyCore(config)

signal, reason = core.on_bar_signal(closes=[...], current_price=100.5)
if signal == 'buy':
    core.on_enter(price=100.5, volume=10)
elif signal == 'sell':
    profit = core.on_exit(exit_price=102.0)
```

| 方法 | 说明 |
|------|------|
| `calculate_sma(data, period) -> float` | 计算 SMA |
| `check_crossover(short, long, prev_short, prev_long) -> str` | 检测金叉/死叉 |
| `check_stop_loss(current_price) -> bool` | 止损判断 |
| `check_take_profit(current_price) -> bool` | 止盈判断 |
| `on_bar_signal(closes, current_price) -> Tuple[Optional[str], str]` | 综合信号生成（含风控） |
| `on_enter(price, volume)` | 仓位入场 |
| `on_exit(exit_price) -> float` | 仓位出场，返回盈亏 |

### 策略桥接器

| 类 | 位置 | 用途 |
|----|------|------|
| `VnpyStrategyBridge` | [bridges/vnpy_bridge.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/strategies/bridges/vnpy_bridge.py) | vn.py CtaTemplate 桥接器 |
| `TqsdkStrategyBridge` | [bridges/tqsdk_bridge.py](file:///Users/REDACTED_API_KEY/Documents/src/quant/strategies/bridges/tqsdk_bridge.py) | 天勤 SDK 桥接器 |

两者均委托调用 `MaStrategyCore`，仅负责框架侧的数据转换与订单执行。

---

## 数据结构定义

### TradeRecord

```python
@dataclass
class TradeRecord:
    timestamp: datetime
    symbol: str
    direction: str       # 'buy' | 'sell'
    price: float
    quantity: int
    profit: float = 0.0  # 卖出时有效
    reason: str = ""     # 交易原因：金叉买入/死叉卖出/止损/止盈
```

### BacktestResult

```python
@dataclass
class BacktestResult:
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_profit: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    avg_profit: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    final_equity: float = 0.0
```

### TradingConfig（策略核心）

```python
@dataclass
class TradingConfig:
    sma_short: int = 5
    sma_long: int = 20
    stop_loss_ratio: float = 0.03
    take_profit_ratio: float = 0.05
    position_ratio: float = 0.1
```

---

## 配置管理

### ConfigManager

```python
from config import ConfigManager

cm = ConfigManager()                        # 加载 conf.yaml + conf.local.yaml
cm = ConfigManager(config_file='custom.yaml')  # 加载指定配置文件

tc = cm.get_trading_config()                # 策略 + 风控参数
bc = cm.get_backtest_config()               # 回测引擎参数
dc = cm.get_data_config()                   # 数据存储路径
ac = cm.get_account_info()                  # 天勤账号信息
cm.validate_config()                        # 参数合法性校验
```