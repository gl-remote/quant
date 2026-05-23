# 常见问题解答 (FAQ)

> 版本: 1.0.0 | 更新日期: 2026-05-23

---

## 安装与环境

### Q1: 我没有安装 vnpy，回测系统还能用吗？

**可以。** 系统内置了降级方案。当检测到 vnpy 未安装时，会自动使用内置的 `BacktestEngine` 执行回测。核心功能完全相同，仅在统计指标的计算精度上可能略有差异。

安装 vnpy 可获得更精确的回测模拟：
```bash
pip install vnpy vnpy_ctastrategy
```

---

### Q2: 安装 vnpy 时报错怎么办？

vnpy 依赖较多，在部分环境下可能安装失败。常见解决方案：

1. **使用 conda 环境**:
```bash
conda create -n vnpy_env python=3.10
conda activate vnpy_env
pip install vnpy vnpy_ctastrategy
```

2. **分步安装**:
```bash
pip install vnpy --no-deps
pip install vnpy_ctastrategy
```

3. **不安装 vnpy**: 系统会自动降级，不影响使用。

---

### Q3: 需要哪些 Python 版本？

推荐 Python 3.8 ~ 3.11。核心依赖 `numpy`、`pandas`、`pyyaml` 对 Python 版本要求较宽松。

---

## 数据相关

### Q4: 数据文件应该是什么格式？

CSV 文件需包含以下列：

| 列名 | 类型 | 示例 |
|------|------|------|
| `datetime` | 时间戳 | `2024-01-15 09:00:00` |
| `open` | 开盘价 | `3012.0` |
| `high` | 最高价 | `3025.0` |
| `low` | 最低价 | `3008.0` |
| `close` | 收盘价 | `3018.0` |
| `volume` | 成交量 | `125000` |

可用内置导出命令自动生成：
```bash
python main.py export --symbol DCE.m2509 --start 2024-01-01 --end 2025-12-31
```

---

### Q5: 文件命名有什么要求？

系统按以下优先级搜索数据文件：

1. `{symbol}.csv` (如 `DCE.m2509.csv`)
2. `{symbol}_qlib.csv` (如 `DCE.m2509_qlib.csv`)
3. `{symbol}_*.csv` (匹配第一个找到的文件)

将文件放入 `.quant_shared_data/csv/` 目录即可。

---

### Q6: 数据量太少怎么办？

数据量不足 10 条时，系统会抛出 `ValueError`。

- 扩大数据时间范围：`--start` 和 `--end` 参数
- 使用更低周期的数据 (如 1 分钟线) 以增加数据点
- 合并多个品种的数据进行测试

---

## 回测相关

### Q7: 为什么训练集收益很高但测试集很差？

这是典型的**过拟合**现象。说明策略在历史数据上过度拟合，对未知数据的泛化能力不足。

系统会通过对比分析报告中的"过拟合综合评估"给出风险评分和建议。常见优化方向：

- 减少策略参数 (如固定均线周期)
- 增加止损止盈风控
- 使用更多历史数据
- 在验证集上进行参数选择，而非训练集

---

### Q8: shuffle: true 和 false 有什么区别？

| 模式 | 工作原理 | 优点 | 风险 |
|------|---------|------|------|
| `false` | 按时间顺序划分 | 避免未来信息泄露 | 可能受时间段特征影响 |
| `true` | 随机采样划分 | 跨时段稳健性验证 | 可能引入前视偏差 |

**强烈建议**: 对时间序列金融数据使用 `shuffle: false`，确保回测结果可靠。

---

### Q9: 报告中的变异系数 (CV) 是什么意思？

变异系数 (Coefficient of Variation) = 标准差 / 均值，用于衡量指标在三阶段 (训练/验证/测试) 上的波动程度。

- **CV < 0.5**: 策略表现稳定
- **CV 0.5 ~ 1.0**: 有一定波动，可接受
- **CV > 1.0**: 波动较大，策略不稳定

---

### Q10: 过拟合评分是如何计算的？

评分范围 0-100，基于以下四个维度：

| 维度 | 触发条件 | 加分 |
|------|---------|------|
| 收益下降 > 50% | 训练→测试收益率腰斩 | +40 |
| 收益下降 20-50% | 明显下降 | +20 |
| 回撤增加 > 10% | 风险显著上升 | +30 |
| 回撤增加 5-10% | 风险有所上升 | +15 |
| 夏普下降 > 50% | 风险调整收益暴跌 | +20 |
| 胜率下降 > 30% | 信号质量下降 | +10 |

- 0-9 分: 无过拟合风险
- 10-29 分: 轻微过拟合
- 30-59 分: 中等风险
- 60-100 分: 严重过拟合

---

### Q11: 如何批量测试不同策略参数？

编写脚本循环调用 API：

```python
from backtest import VnpyBacktestEngine

config = {...}  # 基础配置

for short, long in [(5, 20), (10, 30), (20, 60)]:
    engine = VnpyBacktestEngine(config)
    engine.set_strategy_params(sma_short=short, sma_long=long)
    result = engine.run_full_pipeline(symbol='DCE.m2509')
    
    score = result['comparison']['overfitting_assessment']['score']
    sharpe = result['test']['statistics']['sharpe_ratio']
    print(f"SMA({short},{long}): sharpe={sharpe:.2f}, of_score={score}")
```

---

## 报告相关

### Q12: 报告文件保存在哪里？

默认保存在 `.quant_shared_data/reports/` 目录。

可通过 `conf.yaml` 中的 `backtest.report.output_dir` 修改：
```yaml
backtest:
  report:
    output_dir: "/path/to/custom/reports"
```

---

### Q13: 交易记录中的字段含义？

`{symbol}_*_trades.json` 中的每笔交易记录包含：

| 字段 | 说明 |
|------|------|
| `timestamp` | 交易时间 |
| `symbol` | 品种代码 |
| `direction` | 方向 (buy/sell) |
| `price` | 成交价格 |
| `quantity` | 交易数量 |
| `profit` | 盈亏金额 (卖出时有效) |
| `reason` | 交易原因 (金叉/死叉/止损/止盈) |

---

### Q14: 资金曲线如何解读？

`{symbol}_*_equity.json` 中每条记录包含：

| 字段 | 说明 |
|------|------|
| `date` | 日期 |
| `equity` | 当日收盘后总权益 |
| `daily_return` | 当日盈亏 |
| `drawdown` | 当日回撤比例 |

资金曲线可用于后续可视化 (如 matplotlib 绘图)，也可直接导入 Excel 分析。

---

## 兼容性

### Q15: 旧版 TqSdk 回测还能用吗？

可以。使用 `tq-backtest` 子命令保留旧版兼容：

```bash
python main.py tq-backtest --symbol DCE.m2109 --start 2024-01-01 --end 2024-12-31
```

新版本 `backtest` 子命令使用 vn.py 引擎，功能更丰富。

---

### Q16: 如何贡献新的策略？

1. 在 `backtest/strategies/` 下创建新策略文件
2. 继承 `vnpy_ctastrategy.CtaTemplate` (或 `BacktestEngine` 客户类)
3. 实现 `on_bar()` 方法
4. 在 `VnpyBacktestEngine` 中添加策略切换逻辑

详见 [架构设计文档](architecture.md) 了解模块结构。