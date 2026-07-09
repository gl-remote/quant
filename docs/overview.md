# 项目概览

> 版本: 0.4.0-dev | 最后更新: 2026-06-27

---

## 项目简介

Quantsmith 是一个基于 **Python + React** 的量化策略研发工具链，覆盖行情导出、策略开发、批量回测、参数优化、Walk-Forward 验证、报告生成和实时/实盘桥接。

系统当前以 **vn.py 批量回测** 为主路径，以 **TqSdk** 支持实时信号、模拟/实盘和单标的 GUI 场景。报告模块采用 Python 导出数据、React 前端离线渲染的方式，生成后可直接通过 `file://` 打开。

### 核心特性

| 特性 | 说明 |
|------|------|
| **无状态策略核心** | `Strategy[T]` 只负责决策，运行态由 `State` 保存，行情上下文由 `BarContext` 提供 |
| **多周期运行时** | `DataFeed` 根据 `DataRequirements` 管理多周期数据、指标、事件和形成中 K 线 |
| **Strategy Aspects** | 用装饰器/DSL 声明趋势、确认、止盈止损、冷却等通用策略逻辑 |
| **多策略支持** | 当前内置 `ma` 与 `atr` 策略，策略文件按约定动态加载 |
| **回测与优化** | vn.py 支持单品种/批量回测、Grid/Optuna Bayesian 搜索、并行 trial 和 Walk-Forward |
| **环境化数据隔离** | `backtest`、`test`、`live` 使用独立 SQLite 数据库，避免数据串扰 |
| **离线报告** | React + Vite 前端，ECharts/lightweight-charts 图表，数据内联到 `window.__DATA__` |

### 技术栈

| 分类 | 技术 |
|------|------|
| 后端 | Python 3.12、vn.py、TqSdk、Optuna、TA-Lib、Pandera |
| 前端 | React 18、TypeScript、Vite、Ant Design、ECharts、lightweight-charts |
| 数据库 | SQLite + peewee ORM，按数据环境隔离 |
| 配置 | Pydantic、TOML、环境变量覆盖 |
| 环境 | uv、npm |

---

## 快速开始

### 1. 安装依赖

```bash
uv sync --all-groups

# 报告前端依赖
cd workspace/report/web
npm install
```

### 2. 配置账户与环境

所有业务命令都必须显式指定 `--env` 或 `--config`。

常用环境：

| 环境 | 用途 | 数据库 |
|------|------|--------|
| `backtest` | 回测、优化、报告 | `project_data/database/backtest/quant.db` |
| `test` | 实时信号测试 | `project_data/database/test/quant.db` |
| `live` | 实盘交易 | `project_data/database/live/quant.db` |

本地密钥不要写入通用配置文件。按环境创建本地覆盖文件，例如：

```bash
cp workspace/config/conf.example.toml workspace/config/conf.backtest.local.toml
```

也可以用环境变量覆盖天勤凭证：

```bash
export TQSDK_API_KEY="your_api_key"
export TQSDK_API_SECRET="your_api_secret"
```

配置加载顺序：

- `--env backtest`：`conf.toml` → `conf.backtest.toml` → `conf.backtest.local.toml` → `TQSDK_*` 环境变量
- `--config path/to/file.toml`：`conf.toml` → 指定配置文件 → `TQSDK_*` 环境变量

### 3. 导出行情数据

```bash
./run.sh export \
  --env backtest \
  --symbol DCE.m2509 \
  --source tqsdk \
  --interval 5m \
  --start 2025-01-01 \
  --end 2025-06-01
```

CSV 默认写入：

```text
project_data/market_data/csv/{symbol}.{provider}.{interval}.csv
```

### 4. 运行回测

vn.py 单品种回测：

```bash
./run.sh backtest \
  --env backtest \
  --engine vnpy \
  --strategy ma \
  --symbol DCE.m2509 \
  --start 2025-01-01 \
  --end 2025-06-01 \
  --no-search
```

vn.py 参数搜索：

```bash
./run.sh backtest \
  --env backtest \
  --engine vnpy \
  --strategy atr \
  --symbol DCE.m2509 \
  --optimizer bayesian \
  --trials 20
```

TqSdk GUI 回测需要显式选择 `--engine tqsdk`：

```bash
./run.sh backtest \
  --env backtest \
  --engine tqsdk \
  --strategy ma \
  --symbol DCE.m2509 \
  --start 2025-01-01 \
  --end 2025-06-01 \
  --gui
```

### 5. 构建与查看报告

```bash
./run.sh report --env backtest --build
open project_data/reports/index.html
```

指定 run 构建：

```bash
./run.sh report --env backtest --build --run 12
```

---

## 项目结构

```text
quant/
├── main.py                         # CLI 入口转发器
├── run.sh                          # 常用命令包装脚本
├── workspace/
│   ├── cli/                        # 命令行注册、环境校验、workflow 编排
│   ├── strategies/                 # 策略核心、运行时、切面、桥接器
│   │   ├── core/                   # Strategy / State / Bar / Signal / Fill
│   │   ├── runtime/                # DataFeed / BarContext / 多周期聚合
│   │   ├── strategy_aspects/       # 趋势、确认、风控 DSL 与 advice
│   │   ├── bridges/                # vn.py / TqSdk 桥接器
│   │   ├── ma_strategy.py          # MA 策略
│   │   └── atr_strategy.py         # ATR 策略
│   ├── backtest/                   # vn.py 回测、策略工厂、优化、并行、Walk-Forward
│   ├── data/                       # 数据源、DataManager、ORM、报告查询、路径管理
│   ├── report/                     # 报告数据导出、前端构建、缓存、文本报告
│   │   └── web/                    # React 前端工程
│   ├── common/                     # 通用类型、公式、指标、合约规格、格式化
│   ├── config/                     # TOML + Pydantic 配置
│   ├── packages/python-contracts/  # 报告 JSON 契约校验包
│   └── tests/                      # 测试
├── docs/                           # 项目文档
└── project_data/                   # 本地数据、数据库、报告、日志、缓存、profile、coverage
```

---

## 主要命令

| 命令 | 用途 | 示例 |
|------|------|------|
| `export` | 导出 K 线 CSV | `./run.sh export --env backtest --symbol DCE.m2509 --source tqsdk` |
| `backtest` | 回测、搜索、Walk-Forward | `./run.sh backtest --env backtest --engine vnpy --strategy ma --symbol DCE.m2509` |
| `report` | 文本报告或构建可视化报告 | `./run.sh report --env backtest --build --run 12` |
| `test` | TqSdk 实时信号测试，不下单 | `./run.sh test --env test --strategy ma --symbol DCE.m2509` |
| `live` | TqSdk 实盘/模拟交易链路 | `./run.sh live --env live --strategy ma --symbol DCE.m2509` |

---

## 核心模块

| 模块 | 职责 |
|------|------|
| `cli/` | 子命令注册、`--env/--config` 校验、workflow 路由 |
| `strategies/core/` | 框架无关策略接口、运行状态与标准交易类型 |
| `strategies/runtime/` | 多周期数据、指标惰性计算、事件、`BarContext` 构建 |
| `strategies/strategy_aspects/` | 用 DSL 声明方向确认与风控 advice，策略再消费 advice 生成信号 |
| `strategies/bridges/` | 将 vn.py/TqSdk 数据和订单协议适配为内部 `State`/`Signal`/`Fill` |
| `backtest/` | vn.py 回测引擎、动态策略工厂、参数优化、并行、Walk-Forward |
| `data/` | 数据导出、CSV/SQLite 管理、ORM 模型、报告查询、环境化路径 |
| `report/` | JSON 导出、K 线缓存、前端构建、离线入口 HTML、文本报告 |
| `common/` | 纯工具、类型、统计、指标公式、合约规格 |
| `config/` | TOML 合并、Pydantic 校验、环境变量凭证覆盖 |

---

## 当前能力边界

- 推荐主回测路径是 `--engine vnpy`。
- `--engine tqsdk` 主要用于单标的、GUI、实时/模拟/实盘式桥接场景；与 vn.py 批量回测/报告生命周期并不完全等价。
- Walk-Forward 当前主要做窗口切分、窗口回测和 OOS 聚合，不等同于每个窗口独立 Optuna 重新优化后再测试的完整 WFO。
- 并行优化通过多进程执行 trial，worker 不直接写数据库，由主进程统一持久化结果。
