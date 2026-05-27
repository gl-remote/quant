# 常见问题

> 版本: 0.2.0-dev | 更新日期: 2026-05-26

---

## 安装与配置

### Q: 如何安装依赖？

A: 在项目根目录执行：
```bash
cd /Users/REDACTED_API_KEY/Documents/src/quant
pip install -e .
```

### Q: 如何配置天勤 API 密钥？

A: 有两种方式：

1. **配置文件方式**（推荐）：
```bash
cp config/conf.example.toml config/conf.local.toml
```
编辑 `config/conf.local.toml`，填入 API 密钥。

2. **环境变量方式**：
```bash
export TQSDK_API_KEY=your_api_key
export TQSDK_API_SECRET=your_api_secret
```

### Q: 配置文件在哪里？

A: 
- `config/conf.toml` - 基础配置（提交版本控制）
- `config/conf.local.toml` - 本地覆盖（不提交）
- `config/conf.example.toml` - 配置模板

---

## 数据相关

### Q: 数据文件存储在哪里？

A: 默认存储在 `.quant_shared_data/csv/` 目录，文件格式为 `{symbol}.{interval}.csv`，例如 `DCE.m2509.1m.csv`。

### Q: 如何导出数据？

A: 使用 `export` 命令：
```bash
python main.py export --symbol DCE.m2509 --start 2024-01-01 --end 2024-12-31
```

### Q: 数据文件命名规范是什么？

A: `{symbol}.{interval}.csv`，例如：
- `DCE.m2509.1m.csv` - 豆粕2509合约 1分钟K线
- `SHFE.au2512.1h.csv` - 黄金2512合约 1小时K线

### Q: 如何查看有哪些可用的数据？

A: 使用 DataManager API：
```python
from data import DataManager
dm = DataManager()
print(dm.get_all_symbols())
```

---

## 回测相关

### Q: 如何运行回测？

A: 使用 `backtest` 命令：
```bash
# 单品种（带 GUI）
python main.py backtest --symbol DCE.m2509 --strategy ma --start 2024-01-01 --end 2024-12-31 --gui

# 批量回测
python main.py backtest --pattern "DCE\.m" --strategy ma
```

### Q: 回测结果存储在哪里？

A: 存储在 SQLite 数据库 `.quant_shared_data/quant_shared.db` 中，可通过 `report` 命令查看。

### Q: 如何查看回测报告？

A: 使用 `report` 命令：
```bash
# 查看列表
python main.py report

# 查看详细报告
python main.py report --id 42
```

### Q: Walk-Forward 是什么？

A: Walk-Forward（滚动窗口验证）是一种评估策略稳健性的方法。它将数据划分为多个时间窗口，每个窗口在训练集训练、测试集验证，最后汇总所有窗口的表现。这能更真实地评估策略在未来数据上的表现。

### Q: 如何选择回测引擎？

A: 系统会自动选择：
- 单品种 + `--gui` → TqSdk 图形化回测
- 批量模式（`--pattern`）或无 GUI → vn.py 批量回测

### Q: 过拟合评估是如何工作的？

A: 系统通过四个维度评估过拟合风险：
1. 收益递减：训练集到测试集收益率下降超过 50%
2. 回撤增加：测试集回撤比训练集大 10% 以上
3. 夏普下降：夏普比率下降超过 50%
4. 胜率下降：胜率下降超过 30%

评分范围 0-100，分数越高风险越大。

---

## 策略开发

### Q: 如何创建新策略？

A: 步骤：
1. 在 `strategies/` 目录下创建新文件
2. 实现 `Strategy` 接口
3. 在配置文件中添加策略配置

示例：
```python
from strategies.core.base import Strategy
from strategies.core.types import Bar, Signal, Fill, StrategyPosition

class MyStrategy(Strategy):
    name: str = "my_strategy"
    VERSION: str = "v1.0.0"
    
    def on_bar(self, bar: Bar) -> Signal:
        # 实现策略逻辑
        return Signal()
    
    def on_fill(self, fill: Fill) -> None:
        # 更新状态
        pass
```

### Q: 策略配置参数有哪些？

A: 均线策略的默认参数：
- `sma_short`: 短期均线周期（默认 5）
- `sma_long`: 长期均线周期（默认 60）
- `stop_loss_ratio`: 止损比例（默认 0.02）
- `take_profit_ratio`: 止盈比例（默认 0.05）
- `position_ratio`: 仓位比例（默认 0.5）

### Q: 如何调试策略？

A: 
1. 使用 `test` 命令运行单元测试：
```bash
python main.py test --strategy ma
```

2. 在策略代码中添加日志：
```python
import logging
logger = logging.getLogger(__name__)

def on_bar(self, bar: Bar) -> Signal:
    logger.debug(f"Processing bar: {bar.datetime}, close={bar.close}")
    # ...
```

---

## 参数优化

### Q: 如何启用参数优化？

A: 在配置文件中设置：
```toml
[optimizer]
enabled = true
engine = "grid"  # 或 "optuna"

[optimizer.search_space]
sma_short = { type = "int", low = 5, high = 15, step = 5 }
sma_long = { type = "int", low = 30, high = 120, step = 30 }
```

然后运行：
```bash
python main.py backtest --symbol DCE.m2509 --strategy ma --mode search
```

### Q: 网格搜索和 Optuna 有什么区别？

A: 
- **网格搜索**：穷举所有参数组合，适合参数空间较小的情况
- **Optuna**：贝叶斯优化，智能搜索最优参数，适合参数空间较大的情况

### Q: 优化结果存储在哪里？

A: 
- 回测结果存储在主数据库
- Optuna study 存储在 `optuna_studies.db`
- 优化报告生成在 `output/` 目录

---

## 实盘交易

### Q: 如何启动实盘交易？

A: 
```bash
python main.py live --symbol DCE.m2509 --strategy ma --gui
```

### Q: 实盘交易需要注意什么？

A: 
1. 确保 API 密钥配置正确
2. 设置合理的止损比例
3. 监控交易日志
4. 从模拟交易开始测试

---

## 常见错误

### Q: 遇到 "API Key not found" 错误怎么办？

A: 检查配置文件或环境变量是否正确设置了 API 密钥。

### Q: 数据文件不存在怎么办？

A: 使用 `export` 命令先导出数据：
```bash
python main.py export --symbol DCE.m2509 --start 2024-01-01 --end 2024-12-31
```

### Q: 回测结果异常怎么办？

A: 
1. 检查数据完整性
2. 检查策略参数配置
3. 查看日志输出
4. 使用 Walk-Forward 验证策略稳健性

### Q: 测试失败怎么办？

A: 
```bash
# 运行单个测试文件
python -m pytest tests/test_models.py -v

# 运行单个测试用例
python -m pytest tests/test_config.py::test_config_load -v
```

### Q: vnpy 导入错误怎么办？

A: 确保已安装 vnpy：
```bash
pip install vnpy
```

---

## 性能优化

### Q: 回测速度慢怎么办？

A: 
1. 减少回测时间范围
2. 使用更粗的 K 线周期（如 1h 代替 1m）
3. 关闭不必要的日志
4. 使用批量回测模式

### Q: 内存占用高怎么办？

A: 
1. 分批加载数据
2. 使用 `load_kline()` 加载（失败返回 None）
3. 定期清理缓存：`dm.clear_cache()`

---

## 最佳实践

### Q: 如何避免过拟合？

A: 
1. 使用 Walk-Forward 验证
2. 限制参数搜索范围
3. 跨品种测试策略
4. 保持测试集表现与训练集接近

### Q: 如何选择策略参数？

A: 
1. 使用参数优化工具
2. 参考行业标准参数
3. 验证参数的稳定性
4. 避免过度优化

### Q: 如何管理多个策略？

A: 
1. 在配置文件中添加多个策略配置
2. 使用 `--strategy` 参数选择策略
3. 定期对比不同策略的表现

### Q: 如何备份数据？

A: 
1. 定期备份 `.quant_shared_data/` 目录
2. 备份数据库文件 `quant_shared.db`
3. 使用版本控制管理配置文件

---

## 其他

### Q: 项目的代码结构是怎样的？

A: 
```
quant/
├── cli/          # 命令行接口
├── strategies/   # 策略核心
├── backtest/     # 回测引擎
├── optimizer/    # 参数优化
├── data/         # 数据管理
├── report/       # 报告生成
├── common/       # 通用工具
├── config/       # 配置管理
└── tests/        # 测试用例
```

### Q: 如何贡献代码？

A: 参考 `CONTRIBUTING.md` 文件，遵循项目代码规范。

### Q: 如何更新项目？

A: 
```bash
git pull origin main
pip install -e .
```

### Q: 有问题反馈渠道吗？

A: 可以通过项目的 Issue 系统提交问题和建议。
