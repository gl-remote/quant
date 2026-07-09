# 使用指南

> 版本: 0.4.0-dev | 更新日期: 2026-06-27

---

## 快速入门

### 1. 安装依赖

```bash
uv sync --all-groups

# 报告前端依赖
cd workspace/report/web
npm install
```

### 2. 配置运行环境

所有业务 CLI 命令都必须显式指定 `--env` 或 `--config`。

常用环境：

| 环境 | 适用命令 | 数据库 |
|------|----------|--------|
| `backtest` | `export`、`backtest`、`report` | `project_data/database/backtest/quant.db` |
| `test` | `export`、`test`、`report` | `project_data/database/test/quant.db` |
| `live` | `export`、`live`、`report` | `project_data/database/live/quant.db` |

本地覆盖配置按环境命名：

```bash
cp workspace/config/conf.example.toml workspace/config/conf.backtest.local.toml
```

`--env backtest` 的加载顺序：

```text
workspace/config/conf.toml
→ workspace/config/conf.backtest.toml
→ workspace/config/conf.backtest.local.toml
→ TQSDK_API_KEY / TQSDK_API_SECRET
```

> 当前不会自动加载 `workspace/config/conf.local.toml`。

### 3. 导出数据

```bash
./run.sh export \
  --env backtest \
  --symbol DCE.m2509 \
  --source tqsdk \
  --interval 5m \
  --start 2025-01-01 \
  --end 2025-06-01
```

可用数据源：

| 数据源 | 说明 |
|--------|------|
| `tqsdk` | 天勤数据，适合期货分钟线 |
| `akshare` | AkShare 数据，常用于日线或补充数据 |

CSV 默认写入：

```text
project_data/market_data/csv/{symbol}.{provider}.{interval}.csv
```

### 4. 运行回测

单品种 vn.py 回测，不做参数搜索：

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

参数搜索：

```bash
./run.sh backtest \
  --env backtest \
  --engine vnpy \
  --strategy atr \
  --symbol DCE.m2509 \
  --optimizer bayesian \
  --trials 20
```

多标的批量搜索：

```bash
./run.sh backtest \
  --env backtest \
  --engine vnpy \
  --strategy ma \
  --pattern "DCE.m*" \
  --optimizer grid
```

并行优化：

```bash
./run.sh backtest \
  --env backtest \
  --engine vnpy \
  --strategy atr \
  --pattern "DCE.m*" \
  --optimizer bayesian \
  --trials 50 \
  --parallel \
  --workers 4
```

### 5. 查看报告

构建所有 run 的可视化报告：

```bash
./run.sh report --env backtest --build
```

构建指定 run：

```bash
./run.sh report --env backtest --build --run 12
```

查看单个 backtest 的文本报告：

```bash
./run.sh report --env backtest --id 123
```

打开前端报告：

```bash
open project_data/reports/index.html
```

---

## CLI 命令详解

### 通用规则

- `--env` 和 `--config` 必须二选一。
- `backtest` 命令只能使用 `--env backtest`。
- `test` 命令只能使用 `--env test`。
- `live` 命令只能使用 `--env live`。
- `export` 和 `report` 可用于 `backtest`、`test`、`live`。

### `export`

```bash
./run.sh export \
  --env backtest \
  --symbol DCE.m2509 \
  --source tqsdk \
  --interval 5m \
  --start 2025-01-01 \
  --end 2025-06-01 \
  --force
```

常用参数：

| 参数 | 说明 |
|------|------|
| `--symbol` | 标的，项目内统一使用 `EXCHANGE.SYMBOL`，如 `DCE.m2509` |
| `--source` | `tqsdk` 或 `akshare` |
| `--interval` | `1m`、`5m`、`15m`、`30m`、`1h`、`1d` |
| `--start` / `--end` | 日期范围 |
| `--output` | 自定义 CSV 输出路径 |
| `--force` | 强制覆盖或重新合并 |

### `backtest`

`backtest` 通过 `--engine` 显式选择引擎，不再根据 `--symbol`/`--pattern` 自动推断。

| 引擎 | 适用场景 |
|------|----------|
| `vnpy` | 默认主路径，支持批量、搜索、并行、Walk-Forward、报告落库 |
| `tqsdk` | 单标的回测和 GUI 场景，必须提供 `--symbol`、`--start`、`--end` |

常用参数：

| 参数 | 说明 |
|------|------|
| `--strategy` | 策略名，当前内置 `ma`、`atr` |
| `--symbol` | 单标的过滤 |
| `--pattern` | 批量匹配本地 CSV |
| `--engine` | `vnpy` 或 `tqsdk`，默认 `vnpy` |
| `--mode` | `search` 或 `walk-forward`，仅 vn.py 路径有效 |
| `--optimizer` | `grid` 或 `bayesian` |
| `--trials` | 最大试验次数 |
| `--parallel` / `--workers` | 多进程并行 trial |
| `--no-search` | 跳过参数搜索，单次回测 |
| `--gui` | 仅 `--engine tqsdk` 生效 |

TqSdk GUI 示例：

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

### `report`

```bash
./run.sh report --env backtest --build
./run.sh report --env backtest --build --run 12
./run.sh report --env backtest --id 123
./run.sh report --env backtest --symbol DCE.m2509 --strategy ma --limit 10
```

报告构建后，入口文件为：

```text
project_data/reports/index.html
```

### `test`

实时信号测试链路，不下单。

```bash
./run.sh test \
  --env test \
  --strategy ma \
  --symbol DCE.m2509
```

### `live`

实时交易链路，会根据配置账户下单。

```bash
./run.sh live \
  --env live \
  --strategy ma \
  --symbol DCE.m2509
```

---

## 回测模式

### Search 模式

默认模式是 `search`：

```bash
./run.sh backtest --env backtest --engine vnpy --mode search --strategy ma --symbol DCE.m2509
```

行为：

1. 读取本地 CSV 与导出元数据。
2. 创建 run 记录与 run log。
3. 按配置或 CLI 参数决定是否执行参数搜索。
4. 通过 vn.py 引擎运行回测。
5. 将回测、参数、成交、日度结果写入 SQLite。
6. 构建报告 JSON 与前端入口。

### Walk-Forward 模式

```bash
./run.sh backtest \
  --env backtest \
  --engine vnpy \
  --mode walk-forward \
  --strategy ma \
  --symbol DCE.m2509 \
  --start 2024-01-01 \
  --end 2025-06-01
```

当前 Walk-Forward 主要做：

- 时间窗口切分；
- 每个窗口的 train / validation / test 回测；
- OOS 收益、夏普、回撤、胜率、稳定性等聚合。

当前它不等同于“每个窗口内重新 Optuna 优化参数后再 OOS 测试”的完整 WFO。

---

## 报告查看

### 输出结构

```text
project_data/reports/
├── index.html
├── assets/
│   ├── index.js
│   └── index.css
├── data/
│   └── nav.json
└── runs/
    └── r{run_id}/
        └── data/
            ├── run.json
            ├── summary.json
            ├── backtests.json
            ├── equity.json
            ├── trades.json
            ├── optuna.json
            ├── logs.json
            └── kline_{symbol}.{interval}.json
```

报告前端不依赖 HTTP 服务。构建入口 HTML 时会把 JSON 数据内联到 `window.__DATA__`，前端通过 HashRouter 离线读取。

### 清理报告

```bash
./run.sh report --env backtest --clean
```

---

## 策略开发指南

### 当前策略接口

策略核心是无状态对象，主要接口是：

```python
class Strategy(Generic[T]):
    def data_requirements(self, config: T) -> DataRequirements | None: ...
    def on_bar(self, state: State[T], ctx: BarContext) -> Signal: ...
    def on_fill(self, fill: Fill) -> None: ...
```

职责边界：

| 对象 | 职责 |
|------|------|
| `Strategy` | 纯决策逻辑，不持有运行态 |
| `State` | 策略配置、资金、合约乘数、持仓、成交、扩展状态 |
| `BarContext` | 当前 K 线、多周期数据、指标、事件、aspects advice |
| `Bridge` | 框架数据转换、下单执行、成交同步、状态更新 |

### 新增策略步骤

1. 新建 `workspace/strategies/xxx_strategy.py`。
2. 定义参数 dataclass，例如 `XxxParams`。
3. 定义 `class XxxStrategyCore(Strategy[XxxParams])`。
4. 实现 `data_requirements()`、`on_bar(state, ctx)`、`on_fill(fill)`。
5. 如需通用趋势、确认、止盈止损、冷却逻辑，优先使用 `strategy_aspects` 装饰器/DSL。
6. 在 `workspace/config/conf.toml` 或 `conf.<env>.local.toml` 增加 `[[strategies]] name = "xxx"`。
7. 通过 `--strategy xxx` 运行。

策略加载是约定式动态加载：

| 输入 | 解析结果 |
|------|----------|
| `ma` | `workspace/strategies/ma_strategy.py` |
| `atr` | `workspace/strategies/atr_strategy.py` |
| `xxx` | `workspace/strategies/xxx_strategy.py` |

### Strategy Aspects

优先用现有切面表达通用逻辑：

| 类别 | 装饰器 |
|------|--------|
| 方向趋势 | `@trend_long`、`@trend_short` |
| 入场确认 | `@confirm_long`、`@confirm_short` |
| 出场风控 | `@exit_for_take_profit`、`@exit_for_stop_loss` |
| 入场阻断 | `@entry_block_after_take_profit`、`@entry_block_after_stop_loss` |

切面只写入 `ctx.aspects`，不会直接交易；最终是否开平仓仍由策略 `on_bar()` 消费 advice 后决定。

---

## 关键指标解读

### 格式约定

| 字段类型 | 格式 | 示例 |
|----------|------|------|
| 收益率类 (`total_return`, `annual_return`) | 百分比，已乘 100 | `15.5` 表示 15.5% |
| 回撤金额 (`max_drawdown`) | 绝对金额 | `5200` 表示亏损 5200 元 |
| 回撤百分比 (`max_ddpercent`) | 百分比，已乘 100 | `12.5` 表示 12.5% |
| 胜率 (`win_rate`) | 比值或报告层格式化结果 | 数据库存储和前端展示需看具体字段来源 |

### 核心绩效指标

| 指标 | 说明 | 来源 |
|------|------|------|
| `total_return` | 总收益率 | vn.py statistics |
| `end_balance` | 最终权益余额 | vn.py statistics |
| `sharpe_ratio` | 夏普比率 | vn.py statistics |
| `max_drawdown` / `max_ddpercent` | 最大回撤金额 / 百分比 | vn.py statistics |
| `annual_return` | 年化收益率 | vn.py statistics |
| `total_net_pnl` | 总净盈亏 | vn.py daily results 汇总 |
| `total_commission` | 总手续费 | vn.py daily/trade 汇总 |
| `total_slippage` | 总滑点成本 | vn.py daily results 汇总 |
| `total_turnover` | 总成交金额 | vn.py daily results 汇总 |

### 交易级别统计

| 指标 | 说明 |
|------|------|
| `win_trades` / `loss_trades` | 盈利/亏损平仓交易数 |
| `win_rate` | 基于盈亏平仓交易统计 |
| `avg_win` / `avg_loss` | 平均盈利/亏损金额 |
| `win_loss_ratio` | 盈亏比 |
| `max_consecutive_win/loss` | 最大连续盈利/亏损次数 |

---

## 常用验证命令

```bash
ruff check workspace/ scripts/ main.py
uv run mypy workspace/cli workspace/common workspace/config workspace/data workspace/backtest workspace/strategies workspace/report
uv run pytest workspace/tests/ workspace/packages/python-contracts/tests/ --tb=short
```

---

## 最佳实践

1. 先明确目标交易频率、持仓周期、样本范围和停止条件，再做参数搜索。
2. 优先使用 vn.py 跑批量回测和优化，TqSdk 用于 GUI、实时信号和实盘链路。
3. 使用 `--env` 隔离回测、测试、实盘数据库。
4. 新策略优先使用 `Strategy + State + BarContext + aspects` 架构，不在策略对象上保存运行态。
5. 交易次数过低时，不要直接比较收益率；应先判断样本是否可用。
6. 报告构建结果可离线查看，但数据来自最近一次构建，需要修改数据库后重新 `report --build`。
