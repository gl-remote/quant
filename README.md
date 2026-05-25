# 天勤量化交易系统

![version](https://img.shields.io/badge/version-0.2.0--dev-blue) ![python](https://img.shields.io/badge/python-3.10%2B-green) ![tests](https://img.shields.io/badge/tests-162%20passed-brightgreen) ![coverage](https://img.shields.io/badge/coverage-51%25-yellow)

基于双均线交叉（SMA Crossover）策略的自动化量化交易系统，支持数据获取、三阶段回测、过拟合评估及实盘交易。

## 核心功能

- **金叉买入 / 死叉卖出** — SMA 双均线交叉信号
- **风控管理** — 止损、止盈、仓位比例控制
- **三阶段回测** — 训练集 / 验证集 / 测试集独立回测，过拟合综合评估
- **多品种并发回测** — 正则匹配 + 多线程并行 + 合并报告
- **数据导出** — 从天勤拉取历史 K 线，增量合并 / 强制覆盖为 CSV
- **实盘交易** — 天勤实盘/模拟 + Web GUI
- **操作日志** — 所有操作持久化至 SQLite，支持审计追溯
- **统一回测引擎** — 根据标的数量自动选择 TqSdk（单标的）或 vn.py（批量）

## 项目结构

```
quant/
├── main.py                 # 命令行入口（转发器）
├── run.sh                  # 快捷运行脚本
├── config/                 # YAML 分层配置管理
│   ├── conf.yaml           #   基础配置（提交版本控制）
│   ├── conf.local.yaml     #   本地密钥覆盖（不提交）
│   ├── conf.example.yaml   #   配置模板
│   └── config_manager.py   #   配置加载与合并
├── strategies/             # 策略模块（核心算法 + 桥接器）
│   ├── core/base.py        #   策略抽象接口 (Strategy ABC)
│   ├── core/context.py     #   交易上下文 (TradingContext)
│   ├── ma_strategy.py      #   均线交叉策略 (继承 Strategy)
│   └── bridges/            #   vn.py / 天勤 桥接器
├── backtest/               # 回测引擎、数据加载、报告对比
├── report/                 # 报告生成 (单数据集/多品种对比/DB 报告)
├── data/                   # 数据管理 (models/store/manager/exporter)
├── common/                 # 公共工具（零依赖）
│   ├── constants.py        #   全局常量字典 (60+)
│   ├── formulas.py         #   量化计算公式库 (15+)
│   ├── schemas.py          #   Pandera Schema 定义
│   ├── metrics.py          #   绩效指标计算
│   ├── stats.py            #   统计聚合
│   └── formatting.py       #   安全格式化
├── cli/                    # 命令行接口（重构后）
│   ├── main.py             #   参数解析与命令分发
│   └── commands/           #   命令实现
│       ├── export.py       #     数据导出命令
│       ├── test.py         #     策略测试命令
│       ├── backtest.py     #     统一回测命令
│       ├── report.py       #     报告生成命令
│       └── live.py         #     实盘交易命令
├── common/                 # 公共工具（零依赖）
│   ├── constants.py        #   全局常量字典
│   ├── formulas.py         #   量化计算公式库
│   └── metrics.py          #   绩效指标计算
└── docs/                   # 文档
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

### 4. 运行回测

#### 单标的回测（TqSdk，支持 GUI）

```bash
python main.py backtest --symbol DCE.m2509 --start 2024-01-01 --end 2024-12-31 --gui
```

#### 批量回测（vn.py，生成文字报告）

```bash
python main.py backtest --pattern "DCE\.m"
python main.py backtest  # 扫描全部品种
```

执行完整流水线：加载数据 → 划分训练/验证/测试集 → 独立回测 → 生成报告 → 过拟合对比分析。结果同时输出到控制台和数据库。

## 命令行参考

| 命令 | 说明 | 示例 |
|------|------|------|
| `export` | 从天勤导出 K 线 CSV | `python main.py export --symbol DCE.m2509 --start 2025-01-01 --end 2026-01-01` |
| `test` | 离线策略逻辑验证 | `python main.py test` |
| `backtest` | 统一回测（自动选择引擎） | 单标的: `python main.py backtest --symbol DCE.m2509 --gui`<br>批量: `python main.py backtest --pattern "DCE\.m"` |
| `report` | 从数据库生成回测报告 | `python main.py report --id 42`<br>`python main.py report --compare 1,2,3` |
| `live` | 实盘/模拟交易 | `python main.py live --symbol DCE.m2509 --gui` |

### 快捷脚本

使用 `run.sh` 脚本简化命令：

```bash
./run.sh backtest --symbol DCE.m2509 --gui
./run.sh report --compare 1,2,3
```

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

> 完整参数说明见 [配置文档](docs/configuration.md)。

## 文档

| 文档 | 说明 |
|------|------|
| [系统概览](docs/overview.md) | 项目定位与核心能力 |
| [架构设计](docs/architecture.md) | 模块划分、数据流、设计决策 |
| [配置说明](docs/configuration.md) | 参数详解与配置示例 |
| [使用指南](docs/usage-guide.md) | 环境准备、CLI 操作、编程调用 |
| [API 文档](docs/api-reference.md) | 核心接口与数据结构 |
| [常见问题](docs/faq.md) | 安装、数据、回测 FAQ |
| [AI_BEHAVIOR_RULES.md](AI_BEHAVIOR_RULES.md) | AI 开发行为规范 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 项目贡献指南 |

## 环境要求

- Python 3.8 ~ 3.11
- 依赖：`numpy`, `pandas`, `pyyaml`, `tqsdk`
- vn.py ≥ 3.8.0（可选，未安装时自动降级）

## 开发规范

项目遵循以下开发规范：

1. **常量字典**：所有硬编码字符、数值统一定义在 `common/constants.py`
2. **计算公式**：所有量化计算统一在 `common/formulas.py` 实现
3. **单一职责**：每个模块职责清晰，避免功能混杂
4. **类型提示**：提供完整的类型标注
5. **测试覆盖**：核心功能需有单元测试覆盖