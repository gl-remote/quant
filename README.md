# 天勤量化交易系统

基于双均线交叉（SMA Crossover）策略的自动化量化交易系统，支持数据获取、三阶段回测、过拟合评估及实盘交易。

## 核心功能

- **金叉买入 / 死叉卖出** — SMA 双均线交叉信号
- **风控管理** — 止损、止盈、仓位比例控制
- **三阶段回测** — 训练集 / 验证集 / 测试集独立回测，过拟合综合评估
- **数据导出** — 从天勤拉取历史 K 线，智能去重合并为 CSV
- **双引擎降级** — vn.py 优先，不可用时自动切换内置引擎
- **操作日志** — 所有操作持久化至 SQLite，支持审计追溯

## 项目结构

```
quant/
├── main.py                 # 命令行入口
├── config/                 # YAML 分层配置管理
│   ├── conf.yaml           #   基础配置（提交版本控制）
│   ├── conf.local.yaml     #   本地密钥覆盖（不提交）
│   ├── conf.example.yaml   #   配置模板
│   └── config_manager.py   #   配置加载与合并
├── strategies/             # 策略模块（核心算法 + 网关适配器）
│   ├── core/               #   纯业务逻辑（无框架依赖）
│   └── gateways/           #   vn.py / 天勤 网关
├── backtest/               # 回测引擎、数据加载、报告对比
├── data/                   # 数据导出、SQLite 管理
└── doc/                    # 文档
```

## 快速开始

### 1. 安装依赖

```bash
pip install -e ".[dev]"
```

推荐安装 vn.py 以获得更好的回测精度（可选）：

```bash
pip install vnpy vnpy_ctastrategy
```

### 2. 配置天勤账号

```bash
cp config/conf.example.yaml config/conf.local.yaml
```

编辑 `config/conf.local.yaml`，填入天勤 API Key 和 Secret。仅数据导出和实盘交易需要此配置，离线测试和本地 CSV 回测不需要。

### 3. 导出历史数据

```bash
python main.py export --symbol DCE.m2509 --start 2025-01-01 --end 2026-01-01
```

数据保存至 `.quant_shared_data/csv/`，重复执行自动去重合并。

### 4. 运行三阶段回测

```bash
python main.py backtest --symbol DCE.m2509
```

执行完整流水线：加载数据 → 划分训练/验证/测试集 → 独立回测 → 生成报告 → 过拟合对比分析。结果同时输出到控制台和 `.quant_shared_data/reports/` 目录。

## 命令行参考

| 命令 | 说明 | 示例 |
|------|------|------|
| `export` | 从天勤导出 K 线 CSV | `python main.py export --symbol DCE.m2509 --start 2025-01-01 --end 2026-01-01` |
| `test` | 离线策略逻辑验证 | `python main.py test` |
| `backtest` | vn.py 三阶段回测 | `python main.py backtest --symbol DCE.m2509` |
| `tq-backtest` | 天勤 SDK 回测（旧版兼容） | `python main.py tq-backtest --symbol DCE.m2109 --gui` |
| `live` | 实盘/模拟交易 | `python main.py live --symbol DCE.m2509 --gui` |

## 关键配置

回测参数通过 `config/conf.yaml` 中的 `backtest` 段管理：

```yaml
backtest:
  initial_capital: 100000.0      # 初始资金
  commission_rate: 0.0003        # 手续费率
  slippage: 1                    # 滑点（跳）
  interval: "1m"                 # K线周期: 1m/5m/15m/30m/1h/d
  split:
    train_ratio: 0.6             # 训练集 60%
    val_ratio: 0.2               # 验证集 20%
    test_ratio: 0.2              # 测试集 20%
    shuffle: false               # 时间序列建议 false
```

策略参数：

```yaml
strategy_params:
  sma_short: 5                   # 短期均线周期
  sma_long: 20                   # 长期均线周期

risk:
  stop_loss_ratio: 0.03          # 止损 3%
  take_profit_ratio: 0.05        # 止盈 5%
  position_ratio: 0.1            # 仓位 10%
```

> 完整参数说明见 [配置文档](doc/configuration.md)。

## 文档

| 文档 | 说明 |
|------|------|
| [系统概览](doc/overview.md) | 项目定位与核心能力 |
| [架构设计](doc/architecture.md) | 模块划分、数据流、设计决策 |
| [配置说明](doc/configuration.md) | 参数详解与配置示例 |
| [使用指南](doc/usage-guide.md) | 环境准备、CLI 操作、编程调用 |
| [API 文档](doc/api-reference.md) | 核心接口与数据结构 |
| [常见问题](doc/faq.md) | 安装、数据、回测 FAQ |

## 环境要求

- Python 3.8 ~ 3.11
- 依赖：`numpy`, `pandas`, `pyyaml`, `tqsdk`
- vn.py ≥ 3.8.0（可选，未安装时自动降级）