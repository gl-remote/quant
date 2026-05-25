# 常见问题解答

> 版本: 0.0.3 | 更新日期: 2026-05-24

---

## 安装与环境

### Q1: vn.py 和 tqsdk 是必需的吗？

vn.py 和 tqsdk 均为强制依赖，不再支持降级模式。安装方式见 [README](file:///Users/REDACTED_API_KEY/Documents/src/quant/README.md)。

### Q2: vn.py 安装失败怎么办？

vn.py 依赖较多，推荐使用 conda 环境：

1. `conda create -n vnpy_env python=3.10`
2. `conda activate vnpy_env`
3. `pip install vnpy==3.8.0 vnpy_ctastrategy==1.2.0`

### Q3: 支持的 Python 版本？

推荐 Python 3.8 ~ 3.11。核心依赖 `numpy`、`pandas`、`pyyaml` 对此范围兼容良好。

---

## 数据相关

### Q4: CSV 数据文件格式要求？

必须包含以下列：

| 列名 | 类型 | 示例 |
|------|------|------|
| `datetime` | datetime/str | `2024-01-15 09:00:00` |
| `open` | float | `3012.0` |
| `high` | float | `3025.0` |
| `low` | float | `3008.0` |
| `close` | float | `3018.0` |
| `volume` | float/int | `125000` |

使用 `python main.py export` 命令可自动生成标准格式的 CSV 文件。

### Q5: 文件命名规则？

系统按以下优先级搜索数据文件：`{symbol}.csv` → `{symbol}.{interval}.csv` → `{symbol}_*.csv`。推荐使用 `{symbol}.{interval}.csv`（如 `DCE.m2509.1m.csv`），这是导出命令的默认命名。

### Q6: 多次导出同一品种会重复吗？

不会。`export` 命令内置智能合并逻辑：检测已有 CSV → 加载并合并 → 按 `datetime` 去重 → 保留最新数据。导出后自动更新 SQLite 元数据记录。

---

## 回测相关

### Q7: 训练集收益高但测试集很差，是什么原因？

这是典型的**过拟合**现象。策略在历史数据上过度拟合了噪声模式，导致对未知数据的泛化能力不足。系统会在对比分析报告中给出过拟合评分和针对性建议。

常见优化方向：
- 减少策略参数复杂度（如固定均线周期）
- 收紧止损止盈参数
- 增加历史数据覆盖范围
- 使用验证集进行参数选择而非训练集

### Q8: `shuffle: true` 和 `false` 如何选择？

| 模式 | 原理 | 适用场景 | 风险 |
|------|------|---------|------|
| `false` | 按时间顺序划分（前→中→后） | 时间序列金融数据 | 可能受特定时间段特征影响 |
| `true` | 随机采样分配 | 跨品种/跨时段稳健性检验 | 可能引入前视偏差 |

**强烈建议**：对期货/股票等时间序列数据使用 `shuffle: false`。

### Q9: 变异系数 (CV) 的含义？

CV = 标准差 / 均值，衡量指标在训练/验证/测试三阶段上的波动程度。

- CV < 0.5：策略表现稳定，不同时期表现一致
- CV 0.5 ~ 1.0：有一定波动，可接受
- CV > 1.0：波动较大，策略不稳定，需关注

### Q10: 过拟合评分如何计算？

系统从四个维度综合评估（每项触发即加分）：

| 维度 | 严重阈值 | 加分 |
|------|---------|------|
| 训练→测试 收益率下降 >50% | 收益腰斩 | +40 |
| 训练→测试 收益率下降 20-50% | 明显下降 | +20 |
| 测试集回撤比训练集增加 >10% | 风险失控 | +30 |
| 测试集回撤比训练集增加 5-10% | 风险上升 | +15 |
| 夏普比率下降 >50% | 超额收益失效 | +20 |
| 胜率下降 >30% | 信号质量退化 | +10 |

0-9 无风险，10-29 轻微，30-59 中等，60-100 严重。

---

## 报告相关

### Q11: 报告文件保存在哪里？

默认路径 `.quant_shared_data/reports/`。可通过 `config/conf.yaml` 中的 `backtest.report.output_dir` 修改。

每个品种每阶段生成三个文件：`{symbol}_{dataset}_report.json`（结构化报告）、`{symbol}_{dataset}_trades.json`（交易明细）、`{symbol}_{dataset}_equity.json`（资金曲线），外加 `{symbol}_comparison.json`（对比分析）。

### Q12: 交易记录的字段含义？

| 字段 | 说明 |
|------|------|
| `timestamp` | 交易时间 |
| `symbol` | 品种代码 |
| `direction` | buy/sell |
| `price` | 成交价格 |
| `quantity` | 交易数量 |
| `profit` | 盈亏金额（仅卖出时有效） |
| `reason` | 交易原因：金叉买入 / 死叉卖出 / 止损 / 止盈 |

### Q13: 资金曲线数据包含什么？

每条记录包含：`date`（日期）、`equity`（当日权益）、`daily_return`（当日盈亏）、`drawdown`（当日回撤比例）。可用于 matplotlib 可视化或 Excel 分析。

---

## 策略开发

### Q14: 如何添加新策略？

1. 在 `strategies/core/` 下创建新策略核心类（参考 `MaStrategyCore`）
2. 在 `strategies/bridges/` 下创建对应的 vn.py 和天勤桥接器
3. 在 `VnpyBacktestEngine` 中添加策略切换逻辑

架构设计详见 [系统架构设计](architecture.md)。

### Q15: 如何在回测中使用自定义策略参数？

通过 `set_strategy_params()` 动态传入：

```python
engine.set_strategy_params(
    sma_short=10,
    sma_long=30,
    stop_loss_ratio=0.02,
    take_profit_ratio=0.08,
    position_ratio=0.15,
)
```

---

## 运行相关

### Q16: export 命令需要联网吗？

需要。`export` 通过天勤 SDK 从服务器拉取历史 K 线数据，需要有效的网络连接和天勤账号。`test` 和 `backtest`（使用本地 CSV 数据）不需要联网。

### Q17: 实盘交易 (live) 的前提条件？

1. `conf.local.yaml` 中配置有效的天勤账号（开户后获取）
2. 已安装 `tqsdk` 包（`pip install tqsdk`）
3. 网络可连接天勤服务器
4. 交易时段内运行（非交易时段无法执行真实订单）