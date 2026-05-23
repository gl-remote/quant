# 回测系统使用指南

> 版本: 1.0.0 | 更新日期: 2026-05-23

---

## 1. 环境准备

### 1.1 安装依赖

```bash
cd /path/to/quant
pip install -r requirements.txt
```

推荐安装 vn.py 以获得最佳回测体验：

```bash
pip install vnpy vnpy_ctastrategy
```

如果无法安装 vnpy，系统会自动使用内置降级引擎，核心功能不受影响。

### 1.2 准备数据

使用内置的数据导出功能从天勤获取 K 线数据：

```bash
python main.py export --symbol DCE.m2509 --start 2024-01-01 --end 2025-12-31
```

数据将保存至 `.quant_shared_data/csv/DCE.m2509_qlib.csv`。

也可以手动将 CSV 文件放入该目录，要求包含以下列：

| 列名 | 类型 | 说明 |
|------|------|------|
| datetime | datetime/str | 时间戳，格式 YYYY-MM-DD HH:MM:SS |
| open | float | 开盘价 |
| high | float | 最高价 |
| low | float | 最低价 |
| close | float | 收盘价 |
| volume | float/int | 成交量 |

### 1.3 配置文件

确保 `conf.yaml` 中的 `backtest` 段已正确配置 (见 [参数配置说明](configuration.md))。

## 2. 快速开始

### 2.1 基础回测

```bash
python main.py backtest --symbol DCE.m2509
```

执行完整的三阶段回测流水线，使用 `conf.yaml` 中的默认配置。

### 2.2 指定时间范围

```bash
python main.py backtest --symbol DCE.m2509 --start 2024-01-01 --end 2024-06-30
```

仅使用指定日期范围内的数据进行回测。

### 2.3 旧版 TqSdk 回测 (兼容)

```bash
python main.py tq-backtest --symbol DCE.m2109 --start 2024-01-01 --end 2024-12-31 --capital 100000 --gui
```

使用天勤 SDK 执行实时回测，`--gui` 启用图形界面。

## 3. 输出说明

### 3.1 控制台输出

回测执行后，控制台会依次输出：

1. 数据加载日志 (文件路径、数据量、时间范围)
2. 数据集划分信息 (各集数据量)
3. 训练集回测报告
4. 验证集回测报告
5. 测试集回测报告
6. 三阶段对比分析报告

### 3.2 文件输出

所有文件保存在 `.quant_shared_data/reports/` 目录：

| 文件 | 内容 |
|------|------|
| `{symbol}_train_report.json` | 训练集结构化报告 |
| `{symbol}_val_report.json` | 验证集结构化报告 |
| `{symbol}_test_report.json` | 测试集结构化报告 |
| `{symbol}_train_trades.json` | 训练集详细交易记录 |
| `{symbol}_val_trades.json` | 验证集详细交易记录 |
| `{symbol}_test_trades.json` | 测试集详细交易记录 |
| `{symbol}_train_equity.json` | 训练集资金曲线 |
| `{symbol}_val_equity.json` | 验证集资金曲线 |
| `{symbol}_test_equity.json` | 测试集资金曲线 |
| `{symbol}_comparison.json` | 三阶段对比分析 |

## 4. 使用场景

### 4.1 策略开发阶段

在开发新策略时，建议使用**时间顺序划分**模式 (`shuffle: false`)，确保不引入未来信息泄露：

```yaml
backtest:
  split:
    shuffle: false
```

1. 在训练集上优化策略参数 (SMA 周期、止损止盈比例)
2. 在验证集上选择最优参数组合
3. 在测试集上评估最终泛化性能

### 4.2 稳健性检验

验证策略在不同市场环境下的表现：

```yaml
backtest:
  split:
    shuffle: true          # 随机采样
    random_seed: 42        # 固定种子，可复现
```

多次运行，每次使用不同种子，观察对比报告中过拟合评分的变化。

### 4.3 策略对比

对不同策略参数组合分别运行回测，比较对比报告中的核心指标：

```bash
# 参数组 A: SMA(5, 20)
python main.py backtest --symbol DCE.m2509

# 修改 conf.yaml 参数后 → 参数组 B: SMA(10, 30)
python main.py backtest --symbol DCE.m2509
```

## 5. 命令行参数

### `backtest` 子命令

```
python main.py backtest [--symbol SYMBOL] [--start DATE] [--end DATE]
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--symbol` | `DCE.m2509` | 品种代码 |
| `--start` | (全部) | 数据起始日期，格式 YYYY-MM-DD |
| `--end` | (全部) | 数据结束日期，格式 YYYY-MM-DD |

### `tq-backtest` 子命令 (旧版)

```
python main.py tq-backtest [--symbol SYMBOL] [--start DATE] [--end DATE] [--capital CAPITAL] [--gui]
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--symbol` | `DCE.m2109` | 品种代码 |
| `--start` | `2024-01-01` | 开始日期 |
| `--end` | `2024-12-31` | 结束日期 |
| `--capital` | `100000.0` | 初始资金 |
| `--gui` | (关闭) | 启用天勤图形界面 |

## 6. 编程调用

除了命令行，也可以在 Python 脚本中直接使用 API：

```python
from backtest import VnpyBacktestEngine

config = {
    'data_dir': '.quant_shared_data/csv',
    'initial_capital': 100000,
    'commission_rate': 0.0003,
    'slippage': 1,
    'price_tick': 1,
    'contract_size': 10,
    'interval': 'd',
    'split': {
        'train_ratio': 0.6,
        'val_ratio': 0.2,
        'test_ratio': 0.2,
        'random_seed': 42,
        'shuffle': False,
    },
    'report': {
        'output_dir': '.quant_shared_data/reports',
        'save_trade_records': True,
        'save_equity_curve': True,
    },
}

engine = VnpyBacktestEngine(config)
engine.set_strategy_params(
    sma_short=5,
    sma_long=20,
    stop_loss_ratio=0.03,
    take_profit_ratio=0.05,
    position_ratio=0.1,
)

result = engine.run_full_pipeline(symbol='DCE.m2509')
print(result['comparison']['overfitting_assessment']['level'])
```

详见 [API 接口文档](api-reference.md)。