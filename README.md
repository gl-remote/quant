# 策略工具箱

![version](https://img.shields.io/badge/version-0.4.0--dev-blue) ![python](https://img.shields.io/badge/python-3.12%2B-green) ![tests](https://img.shields.io/badge/tests-333%20passed-brightgreen) ![coverage](https://img.shields.io/badge/coverage-55%25-yellow)

多品种量化策略研发工具链。集成回测引擎、参数优化、报告可视化、Walk-Forward 验证，覆盖从数据到策略评估的完整流程。

## 核心功能

- **策略研发** — 策略框架 + vnpy 回测引擎，支持多品种批量回测
- **参数优化** — Optuna 贝叶斯搜索 + Walk-Forward 滚动验证，对抗过拟合
- **报告系统** — React SPA 离线可浏览报告，权益曲线 / 交易明细 / Optuna 优化过程
- **数据管理** — 多数据源导出（天勤 / AKShare），SQLite 持久化，增量合并
- **实盘交易** — 可选接入天勤 SDK 实盘/模拟（独立模块，不依赖回测链路）

## 项目结构

```
quant/
├── main.py                     # CLI 入口
├── scripts/                    # 仓库级脚本
│   ├── test.sh                 #   统一验证（lint/type/unit）
│   └── tools/                  #   操作脚本（拉数据/回测/清数据）
└── workspace/                  # 项目主体（按业务域组织）
    ├── config/                 # TOML + Pydantic 配置管理
    │   ├── app_config.py
    │   ├── conf.toml           # 基础配置
    │   └── conf.local.toml     # 本地密钥覆盖
    ├── strategies/             # 策略模块（框架无关）
    │   ├── core/               #   策略抽象 + 类型定义
    │   ├── bridges/            #   vnpy / 天勤 桥接
    │   └── ma_strategy.py      #   均线交叉策略
    ├── backtest/               # 回测引擎、参数优化、Walk-Forward
    │   ├── vnpy_backtest_engine.py   # 批量回测引擎
    │   ├── optimizer.py              # Optuna 参数优化
    │   └── walk_forward.py           # Walk-Forward 验证
    ├── data/                   # 数据管理（多数据源 + SQLite）
    ├── report/                 # 报告系统（Python 包 + React SPA 前端 web/）
    ├── common/                 # 公共工具层
    ├── cli/                    # 命令行接口（commands/ + workflows/）
    ├── packages/               # 跨域共享契约（contracts + python-contracts）
    ├── tests/                  # 横切验证层（按域子目录对齐源码）
    └── docs/                   # 项目文档
```

## 快速开始

### 安装

```bash
pip install -e ".[dev]"
```

可选安装 vnpy 以获得更高回测精度：

```bash
pip install vnpy vnpy_ctastrategy
```

### 导出数据

```bash
python main.py export --symbol DCE.m2509 --start 2025-01-01 --end 2026-01-01
```

### 运行回测

```bash
# 批量回测 + 参数搜索
python main.py backtest --pattern "DCE\.m" --strategy ma --mode search

# Walk-Forward 验证
python main.py backtest --pattern "DCE\.m" --strategy ma --mode walk-forward
```

## 命令行参考

| 命令 | 说明 | 示例 |
|------|------|------|
| `export` | 导出 K 线 CSV | `python main.py export --symbol DCE.m2509 --start 2025-01-01` |
| `backtest` | 回测 + 参数搜索 + 报告 | `python main.py backtest --pattern "DCE\.m" --strategy ma --mode search` |
| `report` | 从数据库生成报告 | `python main.py report --id 42` |
| `live` | 实盘/模拟交易 | `python main.py live --symbol DCE.m2509 --gui` |

常见用法见 `scripts/tools/backtest-ma.sh`。

### 快捷脚本

```bash
./run.sh backtest --symbol DCE.m2509 --gui
```

## 关键配置

```toml
[backtest]
initial_capital = 100000.0      # 初始资金
commission_rate = 0.0003        # 手续费率
slippage = 1                    # 滑点（跳）
interval = "1m"                  # K线周期: 1m/5m/15m/30m/1h/d

[optimizer]
engine = "bayesian"              # grid / bayesian
n_trials = 5                     # 最大试验次数
```

## 文档

| 文档 | 说明 |
|------|------|
| [系统概览](docs/overview.md) | 项目定位与核心能力 |
| [架构设计](docs/architecture.md) | 模块划分、数据流、设计决策 |
| [数据字典](docs/reference/data-dictionary.md) | 全部字段含义、格式约定、计算公式 |
| [配置说明](docs/reference/configuration.md) | 参数详解与配置示例 |
| [文档目录](docs/README.md) | 当前说明、参考资料、规划和设计记录入口 |

## 环境要求

- Python 3.10 ~ 3.12
- 核心依赖：`numpy`, `pandas`, `peewee`, `pydantic`, `loguru`
- 可选：`tqsdk`（数据导出 + 实盘）、`vnpy`（批量回测）