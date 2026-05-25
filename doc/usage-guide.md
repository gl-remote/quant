# 使用指南

> 版本: 0.2.0-dev | 更新日期: 2026-05-25

---

## 环境准备

### 安装依赖

```bash
cd /path/to/quant
pip install -r requirements.txt
```

vn.py 和 tqsdk 为强制依赖，安装后即可使用全部功能。

### 配置天勤账号

复制配置模板并填入凭证：

```bash
cp config/conf.example.yaml config/conf.local.yaml
```

编辑 `config/conf.local.yaml` 中的 `api_key` 和 `api_secret`。实盘交易和无 GUI 数据导出依赖此配置。

### 准备行情数据

使用内置导出命令从天勤获取历史 K 线：

```bash
python main.py export --symbol DCE.m2509 --start 2025-01-01 --end 2026-01-01
```

数据保存至 `.quant_shared_data/csv/DCE.m2509.1m.csv`。该命令支持断点续传，重复执行会自动合并去重，不会产生重复数据。

也可以手动将 CSV 文件放入 `.quant_shared_data/csv/` 目录。CSV 必须包含以下列：`datetime`, `open`, `high`, `low`, `close`, `volume`。系统按 `{symbol}.csv` → `{symbol}.{interval}.csv` → `{symbol}_*.csv` 优先级匹配文件。

## 命令行参考

```
python main.py <子命令> [参数]
```

### `export` — 数据导出

```bash
python main.py export --symbol DCE.m2509 --start 2025-01-01 --end 2026-01-01
```

| 参数 | 必需 | 说明 |
|------|------|------|
| `--symbol` | 是 | 品种代码，如 `DCE.m2509` |
| `--start` | 是 | 起始日期 `YYYY-MM-DD` |
| `--end` | 是 | 结束日期 `YYYY-MM-DD` |
| `--output` | 否 | 自定义输出路径 |

导出逻辑：拉取天勤数据 → 检测已有 CSV → 合并去重 → 写入 → 更新 SQLite 元数据。

### `test` — 策略逻辑测试

```bash
python main.py test
```

离线运行，验证策略核心算法的 SMA 计算、交叉检测、止盈止损逻辑是否正确。不需要网络连接和天勤账号。

### `backtest` — vn.py 三阶段回测

```bash
python main.py backtest --symbol DCE.m2509 --start 2025-01-01 --end 2026-01-01
```

| 参数 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| `--symbol` | 否 | `DCE.m2509` | 品种代码 |
| `--start` | 否 | 全部数据 | 数据过滤起始日期 |
| `--end` | 否 | 全部数据 | 数据过滤结束日期 |

执行完整流水线：加载 CSV → 划分三数据集 → 独立回测 → 生成报告 → 对比分析。结果同时输出到控制台和 `.quant_shared_data/reports/` 目录。

### `tq-backtest` — 天勤回测（旧版兼容）

```bash
python main.py tq-backtest --symbol DCE.m2109 --start 2024-01-01 --end 2024-12-31 --gui
```

| 参数 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| `--symbol` | 否 | `DCE.m2109` | 品种代码 |
| `--start` | 否 | `2024-01-01` | 起始日期 |
| `--end` | 否 | `2024-12-31` | 结束日期 |
| `--capital` | 否 | `100000.0` | 初始资金 |
| `--gui` | 否 | 关闭 | 启用天勤 Web 图形界面 |

使用天勤 SDK 的 Backtest 模式执行回测，通过 `--gui` 可查看 K 线图与交易信号标注。

### `live` — 实盘/模拟交易

```bash
python main.py live --symbol DCE.m2509 --gui
```

需要 `config/conf.local.yaml` 中配置有效的天勤账号。`--gui` 启用实时 K 线图和资金曲线监控。

## 输出解读

### 控制台输出

回测完成后，控制台依次输出：

1. 数据加载与划分信息
2. 三个数据集各自的回测报告（收盘权益、收益率、夏普比率等）
3. **三阶段对比分析报告**，包含：
   - 指标对比总览（训练/验证/测试的七项指标）
   - 收益递减分析
   - 风险递增分析
   - 策略稳定性（变异系数）
   - 过拟合综合评估（0-100 评分 + 建议）

### JSON 文件输出

所有文件保存于 `.quant_shared_data/reports/`：

| 文件 | 内容 |
|------|------|
| `{symbol}_train_report.json` | 训练集结构化报告 |
| `{symbol}_val_report.json` | 验证集结构化报告 |
| `{symbol}_test_report.json` | 测试集结构化报告 |
| `{symbol}_comparison.json` | 三阶段对比分析（含过拟合评估） |
| `{symbol}_*_trades.json` | 逐笔交易明细 |
| `{symbol}_*_equity.json` | 每日资金曲线 |

### 过拟合评分解读

| 评分 | 等级 | 含义 |
|------|------|------|
| 0-9 | 无风险 | 策略泛化能力良好，可考虑投入实盘 |
| 10-29 | 轻微 | 存在轻微过拟合迹象，可通过参数微调优化 |
| 30-59 | 中等 | 中等风险，建议简化策略或增加数据量 |
| 60-100 | 严重 | 严重过拟合，策略在未知数据上不可靠 |

## 编程调用

除命令行外，可在 Python 脚本中直接使用 API：

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

# 获取过拟合评估
assessment = result['comparison']['overfitting_assessment']
print(f"风险评分: {assessment['score']}/100 ({assessment['level']})")
print(f"建议: {assessment['advice']}")

# 获取各阶段夏普比率
metrics = result['comparison']['metrics_table']
for k in ['train', 'val', 'test']:
    print(f"{k}: Sharpe={metrics['sharpe_ratio'][k]:.2f}")
```

## 批量参数测试

遍历不同策略参数组合进行批量回测：

```python
from backtest import VnpyBacktestEngine

config = {...}  # 基础配置（不变）

for short, long in [(5, 20), (10, 30), (20, 60)]:
    engine = VnpyBacktestEngine(config)
    engine.set_strategy_params(sma_short=short, sma_long=long)
    result = engine.run_full_pipeline(symbol='DCE.m2509')

    score = result['comparison']['overfitting_assessment']['score']
    test_sharpe = result['test_report']['performance']['sharpe_ratio']
    print(f"SMA({short},{long}): Test Sharpe={test_sharpe:.2f}, Overfit={score}")
```

完整 API 参见 [API 接口文档](api-reference.md)。