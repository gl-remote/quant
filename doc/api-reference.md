# API 接口文档

> 版本: 1.0.0 | 更新日期: 2026-05-23

---

## 1. 核心类

### 1.1 VnpyBacktestEngine

```python
class VnpyBacktestEngine:
    """vn.py 框架回测引擎 — 封装完整回测流水线"""
```

位于 `backtest/backtest_engine.py`，通过 `backtest/__init__.py` 导出：

```python
from backtest import VnpyBacktestEngine
```

#### 构造方法

```python
def __init__(self, config: Dict[str, Any])
```

**参数:**
| 参数 | 类型 | 说明 |
|------|------|------|
| `config` | `Dict` | 回测配置字典，结构同 `conf.yaml` 中的 `backtest` 段 |

支持的配置键:

| 键 | 类型 | 默认值 | 说明 |
|---|------|--------|------|
| `data_dir` | `str` | `.quant_shared_data/csv` | CSV 数据目录 |
| `initial_capital` | `float` | `100000.0` | 初始资金 |
| `commission_rate` | `float` | `0.0003` | 手续费率 |
| `slippage` | `float` | `1.0` | 滑点 (跳) |
| `price_tick` | `float` | `1.0` | 最小价格变动 |
| `contract_size` | `int` | `10` | 合约乘数 |
| `interval` | `str` | `1m` | K线周期 |
| `split` | `Dict` | (见下) | 数据划分参数 |
| `report` | `Dict` | (见下) | 报告输出参数 |

`split` 子配置:

| 键 | 类型 | 默认值 | 说明 |
|---|------|--------|------|
| `train_ratio` | `float` | `0.6` | 训练集比例 |
| `val_ratio` | `float` | `0.2` | 验证集比例 |
| `test_ratio` | `float` | `0.2` | 测试集比例 |
| `random_seed` | `int` | `42` | 随机种子 |
| `shuffle` | `bool` | `False` | 是否随机打乱 |

`report` 子配置:

| 键 | 类型 | 默认值 | 说明 |
|---|------|--------|------|
| `output_dir` | `str` | `.quant_shared_data/reports` | 报告输出目录 |
| `save_trade_records` | `bool` | `True` | 是否保存交易记录 |
| `save_equity_curve` | `bool` | `True` | 是否保存资金曲线 |

#### 方法

##### set_strategy_params

```python
def set_strategy_params(self, **kwargs)
```

设置传递给回测策略的参数。

**支持的参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `sma_short` | `int` | `5` | 短期均线周期 |
| `sma_long` | `int` | `20` | 长期均线周期 |
| `stop_loss_ratio` | `float` | `0.03` | 止损比例 (3%) |
| `take_profit_ratio` | `float` | `0.05` | 止盈比例 (5%) |
| `position_ratio` | `float` | `0.1` | 仓位比例 (10%) |

##### run_full_pipeline

```python
def run_full_pipeline(
    self,
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]
```

执行完整的回测流水线：加载 → 划分 → 回测 ×3 → 报告 → 对比。

**参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| `symbol` | `str` | 合约代码，如 `DCE.m2509` |
| `start_date` | `Optional[str]` | 数据起始日期，`YYYY-MM-DD` 格式 |
| `end_date` | `Optional[str]` | 数据结束日期，`YYYY-MM-DD` 格式 |

**返回值:**

```python
{
    'success': bool,           # 是否成功
    'symbol': str,             # 合约代码
    'datasets': {              # 数据集信息
        'train': {...},
        'val': {...},
        'test': {...},
    },
    'train': {                 # 训练集回测结果
        'dataset_name': str,
        'statistics': {...},   # 回传统计
        'daily_results': [...],
    },
    'val': {...},              # 验证集回测结果 (结构同上)
    'test': {...},             # 测试集回测结果 (结构同上)
    'train_report': {...},     # 训练集格式化报告
    'val_report': {...},       # 验证集格式化报告
    'test_report': {...},      # 测试集格式化报告
    'comparison': {...},       # 三阶段对比分析
}
```

**statistics 结构:**

```python
{
    'start_date': str,
    'end_date': str,
    'total_days': int,
    'total_trades': int,
    'win_trades': int,
    'loss_trades': int,
    'win_rate': float,
    'total_net_pnl': float,
    'end_balance': float,
    'max_drawdown': float,
    'sharpe_ratio': float,
    'annual_return': float,
    'average_win': float,
    'average_loss': float,
    'win_loss_ratio': float,
}
```

**comparison 结构:**

```python
{
    'meta': {
        'symbol': str,
        'train': str,
        'val': str,
        'test': str,
    },
    'metrics_table': {
        'total_return': {'train': float, 'val': float, 'test': float},
        'annual_return': {...},
        'sharpe_ratio': {...},
        'max_drawdown': {...},
        'win_rate': {...},
        'profit_loss_ratio': {...},
        'total_trades': {...},
    },
    'return_degradation': {
        'train_to_val': float,
        'val_to_test': float,
        'train_to_test': float,
        'risk_level': str,        # 'high' / 'medium' / 'low' / 'none'
        'message': str,
    },
    'risk_increase': {...},
    'stability_analysis': {
        'return_cv': float,
        'sharpe_cv': float,
        'winrate_cv': float,
        'drawdown_cv': float,
        'avg_cv': float,
        'stability': str,         # 'high' / 'medium' / 'low'
        'message': str,
    },
    'overfitting_assessment': {
        'score': int,             # 0-100
        'level': str,             # 'high' / 'medium' / 'low' / 'none'
        'advice': str,
        'details': {
            'return_degradation': str,
            'drawdown_increase': str,
            'sharpe_decline': str,
            'winrate_decline': str,
        },
    },
}
```

---

### 1.2 BacktestEngine (降级引擎)

```python
class BacktestEngine:
    """原始回测引擎 — vnpy 不可用时的降级方案"""
```

位于同一文件中，当 `vnpy` 未安装时自动启用。

```python
from backtest import BacktestEngine
```

#### 构造方法

```python
def __init__(self, initial_capital: float = 100000.0)
```

#### 方法

| 方法 | 说明 |
|------|------|
| `add_trade(trade: TradeRecord)` | 添加一笔交易记录，更新资金和持仓 |
| `calculate_metrics() -> BacktestResult` | 计算绩效指标 |
| `generate_report() -> str` | 生成格式化报告字符串 |

---

### 1.3 数据类

#### TradeRecord

```python
@dataclass
class TradeRecord:
    timestamp: datetime
    symbol: str
    direction: str              # 'buy' or 'sell'
    price: float
    quantity: int
    profit: float = 0.0
    reason: str = ""
```

#### BacktestResult

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

---

## 2. 数据加载模块

位于 `backtest/data_loader.py`。

### load_csv_data

```python
def load_csv_data(data_dir: str, symbol: str) -> Optional[pd.DataFrame]
```

从指定目录加载品种的历史 CSV 数据。

### split_datasets

```python
def split_datasets(
    df: pd.DataFrame,
    train_ratio: float = 0.6,
    val_ratio: float = 0.2,
    test_ratio: float = 0.2,
    random_seed: int = 42,
    shuffle: bool = False,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]
```

将 DataFrame 按比例划分为训练/验证/测试集。

### df_to_vnpy_datalines

```python
def df_to_vnpy_datalines(df: pd.DataFrame, symbol: str) -> list
```

将 DataFrame 转换为 vnpy BarData 对象列表。

### get_dataset_info

```python
def get_dataset_info(df: pd.DataFrame, name: str = "") -> Dict
```

获取数据集基本统计信息。

---

## 3. 报告模块

位于 `backtest/report.py`。

### generate_dataset_report

```python
def generate_dataset_report(
    statistics: Dict[str, Any],
    daily_results: Optional[List[Dict]] = None,
    dataset_name: str = "unknown",
    symbol: str = "",
    initial_capital: float = 100000.0,
    output_dir: str = ".quant_shared_data/reports",
    save_trades: bool = True,
    save_equity: bool = True,
) -> Dict[str, Any]
```

### format_console_report

```python
def format_console_report(report: Dict, dataset_name: str) -> str
```

---

## 4. 对比分析模块

位于 `backtest/comparison.py`。

### compare_datasets

```python
def compare_datasets(
    train_report: Dict,
    val_report: Dict,
    test_report: Dict,
    symbol: str = "",
) -> Dict[str, Any]
```

### format_comparison_report

```python
def format_comparison_report(comparison: Dict) -> str
```