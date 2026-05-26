# 使用指南

> 版本: 0.2.0-dev | 更新日期: 2026-05-26

---

## 快速入门

### 1. 安装依赖

```bash
cd /Users/REDACTED_API_KEY/Documents/src/quant
pip install -e .
```

### 2. 配置账户

复制配置模板并填写天勤 API 密钥：

```bash
cp config/conf.example.toml config/conf.local.toml
```

编辑 `config/conf.local.toml`：

```toml
[[third_party.services]]
name = "tqsdk"
provider = "tqsdk"
api_key = "your_actual_api_key"
api_secret = "your_actual_api_secret"
enabled = true
```

### 3. 导出数据

```bash
# 导出单个品种
python main.py export --symbol DCE.m2509 --start 2024-01-01 --end 2024-12-31

# 强制覆盖已有数据
python main.py export --symbol DCE.m2509 --start 2024-01-01 --end 2024-12-31 --force
```

---

## 回测命令详解

### 单品种回测（TqSdk 图形化）

```bash
python main.py backtest --symbol DCE.m2509 --strategy ma --start 2024-01-01 --end 2024-12-31 --gui
```

**参数说明**：
| 参数 | 说明 | 必填 |
|------|------|------|
| `--symbol` | 品种代码 | ✅ |
| `--strategy` | 策略名称 | ✅ |
| `--start` | 开始日期 | ✅ |
| `--end` | 结束日期 | ✅ |
| `--gui` | 启用图形界面 | ❌ |
| `--capital` | 初始资金（默认读配置） | ❌ |

### 批量回测（vn.py）

```bash
# 正则匹配多个品种
python main.py backtest --pattern "DCE\.m" --strategy ma

# 扫描所有可用品种
python main.py backtest --strategy ma

# 指定单个品种（无 GUI）
python main.py backtest --symbol DCE.m2509 --strategy ma
```

### 参数优化

```bash
# 网格搜索
python main.py backtest --symbol DCE.m2509 --strategy ma --optimizer grid --mode search

# Optuna 贝叶斯优化
python main.py backtest --symbol DCE.m2509 --strategy ma --optimizer optuna --mode search
```

### Walk-Forward 滚动验证

```bash
python main.py backtest --symbol DCE.m2509 --strategy ma --mode walk-forward
```

---

## 策略开发指南

### 创建新策略

1. 在 `strategies/` 目录下创建新文件，如 `my_strategy.py`

2. 实现 `Strategy` 接口：

```python
from strategies.core.base import Strategy
from strategies.core.types import Bar, Signal, Fill, StrategyPosition
from typing_extensions import override

class MyStrategy(Strategy):
    name: str = "my_strategy"
    VERSION: str = "v1.0.0"
    
    def __init__(self, strategy_params=None, capital=None, contract_size=None):
        self._config = MyParams(**(strategy_params or {}))
        self._capital = capital or 100000.0
        self._contract_size = contract_size or 10
        self._position = StrategyPosition()
        self._fills = []
    
    @property
    def config(self):
        return self._config
    
    @property
    def position(self):
        return self._position
    
    @override
    def on_bar(self, bar: Bar) -> Signal:
        # 实现策略逻辑
        return Signal()
    
    @override
    def on_fill(self, fill: Fill) -> None:
        # 更新持仓和交易记录
        pass
    
    @override
    def reset(self) -> None:
        # 重置状态
        pass
```

3. 在配置文件中添加策略配置：

```toml
[[strategies]]
name = "my_strategy"
enabled = true
# 添加自定义参数
```

### 策略配置参数

```toml
[[strategies]]
name = "ma"
enabled = true

# 均线参数
sma_short = 5          # 短期均线周期
sma_long = 60         # 长期均线周期

# 风控参数
stop_loss_ratio = 0.02    # 止损比例
take_profit_ratio = 0.05  # 止盈比例

# 资金管理
position_ratio = 0.5      # 仓位比例
```

---

## 报告命令详解

### 查看回测列表

```bash
# 默认显示最近 20 条
python main.py report

# 按品种过滤
python main.py report --symbol DCE.m2509

# 按策略过滤
python main.py report --strategy MaStrategyCore

# 指定显示条数
python main.py report --limit 50
```

### 查看详细报告

```bash
python main.py report --id 42
```

### 删除回测记录

```bash
python main.py report --clean 42
```

---

## 实盘交易

```bash
# 启动实盘交易
python main.py live --symbol DCE.m2509 --strategy ma

# 启用图形界面
python main.py live --symbol DCE.m2509 --strategy ma --gui
```

---

## 测试命令

```bash
# 运行策略单元测试
python main.py test --strategy ma

# 运行所有测试
python -m pytest tests/ -v
```

---

## 数据管理

### DataManager 接口

```python
from data import DataManager

dm = DataManager()

# 获取所有可用品种
symbols = dm.get_all_symbols()

# 搜索品种
matched = dm.search_symbols("DCE\\.m")

# 获取品种信息
info = dm.get_symbol_info("DCE.m2509")

# 加载 K 线数据
df = dm.load_kline("DCE.m2509", start_date="2024-01-01", end_date="2024-12-31")

# 查询回测记录
backtests = dm.query_backtests(symbol="DCE.m2509", strategy="MaStrategyCore")

# 获取单个回测详情
bt = dm.get_backtest(42)

# 获取交易明细
trades = dm.query_trades(42)

# 获取每日资金曲线
daily = dm.query_daily(42)
```

---

## 参数优化配置

### 网格搜索配置

```toml
[optimizer]
enabled = true
engine = "grid"

[optimizer.search_space]
sma_short = { type = "int", low = 5, high = 20, step = 5 }
sma_long = { type = "int", low = 30, high = 120, step = 30 }
stop_loss_ratio = { type = "float", low = 0.01, high = 0.03, step = 0.01 }
take_profit_ratio = { type = "float", low = 0.03, high = 0.08, step = 0.02 }
```

### Optuna 配置

```toml
[optimizer]
enabled = true
engine = "optuna"
n_trials = 100

[optimizer.search_space]
sma_short = { type = "int", low = 5, high = 30, step = 5 }
sma_long = { type = "int", low = 30, high = 200, step = 10 }
stop_loss_ratio = { type = "float", low = 0.01, high = 0.05 }
take_profit_ratio = { type = "float", low = 0.02, high = 0.1 }
```

---

## 回测结果解读

### 关键指标

| 指标 | 说明 | 计算公式 |
|------|------|----------|
| `total_return` | 总收益率 | (最终权益 - 初始资金) / 初始资金 |
| `annual_return` | 年化收益率 | 按年复利计算 |
| `sharpe_ratio` | 夏普比率 | 超额收益 / 收益标准差 |
| `max_drawdown` | 最大回撤 | 权益曲线从峰值下跌的最大幅度 |
| `win_rate` | 胜率 | 盈利交易次数 / 总交易次数 |
| `total_trades` | 总交易次数 | 卖出次数（每次完整交易） |
| `win_loss_ratio` | 盈亏比 | 平均盈利 / 平均亏损 |

### 过拟合评估

系统自动评估策略的过拟合风险：

| 维度 | 风险阈值 | 说明 |
|------|---------|------|
| 收益递减 | >50% | 训练集到测试集收益率下降超过 50% |
| 回撤增加 | >10% | 测试集回撤比训练集大 10% 以上 |
| 夏普下降 | >50% | 夏普比率下降超过 50% |
| 胜率下降 | >30% | 胜率下降超过 30% |

**评分范围**：0-100，分数越高表示过拟合风险越大。

---

## Walk-Forward 结果解读

```python
wf_result = engine.run_walk_forward(data, symbol, strategy)

# 窗口数量
print(wf_result['windows'])

# 各窗口结果
for window in wf_result['window_results']:
    print(f"窗口 {window['window']}:")
    print(f"  训练期: {window['train_start']} ~ {window['train_end']}")
    print(f"  测试期: {window['test_start']} ~ {window['test_end']}")
    print(f"  收益率: {window['statistics'].get('total_return', 0):.2%}")

# 聚合指标
aggregate = wf_result['aggregate']
print(f"OOS平均收益: {aggregate['return_mean']:.2%}")
print(f"OOS平均夏普: {aggregate['sharpe_mean']:.2f}")
print(f"稳定性评分: {aggregate['stability_score']:.2f}")
print(f"IS-OOS差距: {aggregate['is_oos_return_gap']:.2%}")
```

---

## 最佳实践

### 1. 数据准备

- 确保数据完整，无缺失或异常值
- 使用 `export` 命令定期更新数据
- 数据文件命名规范：`{symbol}.{interval}.csv`

### 2. 策略测试

- 使用 Walk-Forward 验证策略稳健性
- 避免过拟合：测试集表现不应显著差于训练集
- 跨品种验证：在多个品种上测试策略

### 3. 参数优化

- 使用网格搜索进行初步探索
- 使用 Optuna 进行精细优化
- 设置合理的搜索范围，避免极端值

### 4. 风险控制

- 设置合理的止损比例
- 限制单一品种持仓比例
- 定期监控策略表现

### 5. 日志与监控

- 定期查看回测报告
- 监控实盘交易日志
- 设置异常通知机制

---

## 常见问题

### Q: 如何添加新策略？

A: 在 `strategies/` 目录下创建新文件，实现 `Strategy` 接口，并在配置文件中添加策略配置。

### Q: 数据文件在哪里？

A: 默认存储在 `.quant_shared_data/csv/` 目录，文件格式为 `{symbol}.{interval}.csv`。

### Q: 回测结果存储在哪里？

A: 存储在 SQLite 数据库 `.quant_shared_data/quant_shared.db` 中，可通过 `report` 命令查看。

### Q: 如何启用参数优化？

A: 在配置文件中设置 `[optimizer].enabled = true`，并配置 `search_space`。通过 `engine` 字段选择搜索模式：`grid`（穷举搜索）或 `optuna`（贝叶斯优化）。

### Q: Walk-Forward 和普通回测有什么区别？

A: Walk-Forward 将数据划分为多个时间窗口，每个窗口在训练集训练、测试集验证，能更真实评估策略未来表现。

### Q: 如何选择回测引擎？

A: 单品种带 GUI 使用 TqSdk，批量回测或参数优化使用 vn.py。系统会根据参数自动选择。
