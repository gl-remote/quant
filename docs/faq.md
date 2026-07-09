# 常见问题

> 版本: 0.4.0-dev | 更新日期: 2026-06-27

---

## 安装与配置

### Q: 如何安装依赖？

A:

```bash
uv sync --all-groups

# 报告前端依赖
cd workspace/report/web
npm install
```

### Q: 为什么命令提示“必须显式指定 --env 或 --config”？

A: 当前 CLI 要求所有业务命令显式声明数据环境，避免回测、测试、实盘数据混写。

示例：

```bash
./run.sh backtest --env backtest --strategy ma --symbol DCE.m2509
./run.sh report --env backtest --build
./run.sh test --env test --strategy ma --symbol DCE.m2509
./run.sh live --env live --strategy ma --symbol DCE.m2509
```

### Q: 支持哪些环境？

A:

| 环境 | 说明 | 数据库 |
|------|------|--------|
| `backtest` | 回测、参数搜索、报告 | `project_data/database/backtest/quant.db` |
| `test` | 实时信号测试 | `project_data/database/test/quant.db` |
| `live` | 实盘/模拟交易 | `project_data/database/live/quant.db` |

CLI 层可用环境是 `backtest`、`test`、`live`。`unit_test` 是测试代码内部使用的配置环境。

### Q: 如何配置天勤 API 密钥？

A: 推荐使用环境变量：

```bash
export TQSDK_API_KEY="your_api_key"
export TQSDK_API_SECRET="your_api_secret"
```

也可以创建环境本地覆盖文件：

```bash
cp workspace/config/conf.example.toml workspace/config/conf.backtest.local.toml
```

在 `conf.backtest.local.toml` 中填写：

```toml
[[third_party.services]]
name = "tqsdk"
provider = "tianqin"
api_key = "your_api_key"
api_secret = "your_api_secret"
account_type = "tqsim"
enabled = true
```

### Q: `conf.local.toml` 还会被加载吗？

A: 不会。当前按环境加载：

```text
conf.toml -> conf.<env>.toml -> conf.<env>.local.toml -> TQSDK_* 环境变量
```

例如 `--env backtest` 会加载：

```text
workspace/config/conf.toml
workspace/config/conf.backtest.toml
workspace/config/conf.backtest.local.toml
```

使用 `--config path/to/custom.toml` 时，加载顺序是：

```text
conf.toml -> custom.toml -> TQSDK_* 环境变量
```

---

## 数据管理

### Q: 数据文件存储在哪里？

A: 本地数据统一在 `project_data/` 下：

| 类型 | 路径 |
|------|------|
| CSV 行情 | `project_data/market_data/csv/` |
| SQLite 数据库 | `project_data/database/<env>/quant.db` |
| 报告 | `project_data/reports/` |
| 日志 | `project_data/logs/` |
| 缓存 | `project_data/cache/` |
| profile | `project_data/profiles/` |
| coverage | `project_data/coverage/` |

### Q: 数据库还是 `project_data/database/quant_shared.db` 吗？

A: 不是。当前数据库按环境隔离：

```text
project_data/database/backtest/quant.db
project_data/database/test/quant.db
project_data/database/live/quant.db
```

### Q: 如何导出新的 K 线数据？

A:

```bash
./run.sh export \
  --env backtest \
  --symbol DCE.m2509 \
  --source tqsdk \
  --interval 5m \
  --start 2025-01-01 \
  --end 2025-06-01
```

### Q: 支持哪些数据源和周期？

A:

| 项目 | 可选值 |
|------|--------|
| 数据源 | `tqsdk`、`akshare` |
| 周期 | `1m`、`5m`、`15m`、`30m`、`1h`、`1d` |

CSV 文件名模板：

```text
{symbol}.{provider}.{interval}.csv
```

例如：

```text
DCE.m2509.tqsdk.5m.csv
DCE.m2509.akshare.1d.csv
```

### Q: 如何清理缓存？

A:

```bash
make clean-cache
# 如需清理报告产物：
make clean-reports
```

缓存主要包括：

| 缓存 | 路径 |
|------|------|
| 报告增量构建 | `project_data/cache/report_build/` |
| K 线 JSON | `project_data/cache/kline_json/` |
| DataFeed 磁盘缓存 | `project_data/cache/datafeed/` |

---

## 回测相关

### Q: 如何运行单品种回测？

A: 推荐使用 vn.py：

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

### Q: 如何运行批量回测？

A:

```bash
./run.sh backtest \
  --env backtest \
  --engine vnpy \
  --strategy ma \
  --pattern "DCE.m*" \
  --start 2025-01-01 \
  --end 2025-06-01
```

### Q: 回测引擎会自动选择吗？

A: 不会。当前通过 `--engine` 显式选择：

| 引擎 | 说明 |
|------|------|
| `vnpy` | 默认主路径，支持批量、优化、并行、Walk-Forward、报告落库 |
| `tqsdk` | 单标的回测/GUI/实时式桥接场景 |

`--gui` 只在 `--engine tqsdk` 下生效。

### Q: 如何打开 TqSdk GUI 回测？

A:

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

TqSdk 路径目前主要用于单标的/GUI/实时式场景，和 vn.py 批量回测的持久化、报告生命周期不完全等价。

### Q: 如何启用参数优化？

A: 可以通过 CLI 覆盖：

```bash
./run.sh backtest \
  --env backtest \
  --engine vnpy \
  --strategy atr \
  --symbol DCE.m2509 \
  --optimizer bayesian \
  --trials 20
```

也可以在配置中设置：

```toml
[optimizer]
enabled = true
engine = "bayesian"  # grid 或 bayesian
n_trials = 20
```

### Q: 如何启用并行优化？

A:

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

并行优化使用多进程隔离。worker 不直接写 SQLite，由主进程统一持久化结果。

### Q: Walk-Forward 和普通回测有什么区别？

A: 普通回测在一个时间段内评估策略。Walk-Forward 会把时间序列切成多个窗口，分别跑 train / validation / test 并聚合 OOS 表现。

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

当前实现主要是窗口切分、窗口回测和 OOS 聚合，不等同于每个窗口独立 Optuna 重新优化后再测试的完整 WFO。

---

## 报告相关

### Q: 如何查看回测报告？

A: 先构建报告，再打开入口文件：

```bash
./run.sh report --env backtest --build
open project_data/reports/index.html
```

指定 run 构建：

```bash
./run.sh report --env backtest --build --run 12
```

查看文本报告：

```bash
./run.sh report --env backtest --id 123
```

### Q: 报告为什么可以离线打开？

A: 报告构建时会把 JSON 数据内联到 `index.html` 的 `window.__DATA__`，前端通过 HashRouter 和内联数据渲染，不依赖 HTTP 服务。

### Q: 报告 JSON 输出在哪里？

A:

```text
project_data/reports/
├── index.html
├── data/nav.json
└── runs/r{run_id}/data/
    ├── run.json
    ├── summary.json
    ├── backtests.json
    ├── equity.json
    ├── trades.json
    ├── optuna.json
    ├── logs.json
    └── kline_{symbol}.{interval}.json
```

### Q: 报告前端使用 Plotly 吗？

A: 当前前端主要使用 ECharts 和 lightweight-charts。Optuna 图表也导出为 ECharts option JSON。

### Q: 报告无法加载怎么办？

A:

1. 确认前端依赖已安装：

```bash
cd workspace/report/web
npm install
```

2. 重新构建报告：

```bash
./run.sh report --env backtest --build
```

3. 确认数据库环境正确，例如回测写入的是 `backtest` 环境，就要用 `--env backtest` 构建报告。

---

## 策略开发

### Q: 当前内置哪些策略？

A:

| 策略 | 文件 | 说明 |
|------|------|------|
| `ma` | `workspace/strategies/ma_strategy.py` | MA 策略，结合多周期趋势、MACD/KDJ 确认、ATR/比例风控 |
| `atr` | `workspace/strategies/atr_strategy.py` | ATR 风控策略，包含 ATR 止盈止损、移动止盈、时间退出等逻辑 |

### Q: 如何添加新策略？

A:

1. 新建 `workspace/strategies/xxx_strategy.py`。
2. 定义策略参数 dataclass，例如 `XxxParams`。
3. 定义 `class XxxStrategyCore(Strategy[XxxParams])`。
4. 实现 `data_requirements(config)`、`on_bar(state, ctx)`、`on_fill(fill)`。
5. 在配置中添加 `[[strategies]] name = "xxx"`。
6. 使用 `--strategy xxx` 运行。

策略加载按文件名约定：`xxx` 会映射到 `workspace/strategies/xxx_strategy.py`。

### Q: 策略核心现在需要关注哪些对象？

A:

| 对象 | 用途 |
|------|------|
| `Strategy[T]` | 无状态决策核心 |
| `State[T]` | 策略配置、资金、持仓、成交、扩展运行态 |
| `BarContext` | 当前 K 线、多周期数据、指标、事件、aspects advice |
| `Signal` | 策略输出的买卖动作、手数、原因和诊断信息 |
| `Fill` | 成交通知 |

当前核心接口是：

```python
def on_bar(self, state: State[T], ctx: BarContext) -> Signal:
    ...
```

不是旧版的 `on_bar(self, bar)`。

### Q: Strategy Aspects 是什么？

A: `strategy_aspects` 用装饰器和 DSL 表达通用策略逻辑，例如趋势、确认、止盈、止损、冷却。

常用装饰器：

| 类别 | 装饰器 |
|------|--------|
| 方向趋势 | `@trend_long`、`@trend_short` |
| 入场确认 | `@confirm_long`、`@confirm_short` |
| 出场风控 | `@exit_for_take_profit`、`@exit_for_stop_loss` |
| 入场阻断 | `@entry_block_after_take_profit`、`@entry_block_after_stop_loss` |

切面只写入 `ctx.aspects`，不会直接下单；策略 `on_bar()` 读取 advice 后决定是否返回交易 `Signal`。

### Q: 为什么交易 reason 是 JSON？

A: 策略基类会把 `ctx.aspects` 中的诊断信息展平写入 `Signal.diagnostics`，当存在交易信号时再把 reason 和 diagnostics 序列化为 JSON，便于后续落库、报告和交易原因分析。

---

## 实时与实盘

### Q: 如何运行实时信号测试？

A:

```bash
./run.sh test \
  --env test \
  --strategy ma \
  --symbol DCE.m2509
```

`test` 命令使用 TqSdk 实时链路，不下单。

### Q: 如何运行实盘链路？

A:

```bash
./run.sh live \
  --env live \
  --strategy ma \
  --symbol DCE.m2509
```

`live` 命令会进入交易链路，运行前务必确认 `conf.live.local.toml` 或环境变量中的账户配置。

---

## 技术问题

### Q: 如何选择回测引擎？

A:

| 场景 | 推荐 |
|------|------|
| 批量回测 | `--engine vnpy` |
| 参数搜索 | `--engine vnpy` |
| 并行 trial | `--engine vnpy --parallel` |
| Walk-Forward | `--engine vnpy --mode walk-forward` |
| 单标的 GUI | `--engine tqsdk --gui` |
| 实时信号/实盘 | `test` / `live` 命令 |

### Q: 如何运行测试？

A:

```bash
uv run pytest workspace/tests/ workspace/packages/python-contracts/tests/ --tb=short
```

常用完整检查：

```bash
ruff check workspace/ scripts/ main.py
uv run mypy workspace/cli workspace/common workspace/config workspace/data workspace/backtest workspace/strategies workspace/report
uv run pytest workspace/tests/ workspace/packages/python-contracts/tests/ --tb=short
```

### Q: 回测速度慢怎么办？

A:

1. 优先使用 vn.py 批量回测。
2. 先用 `--no-search` 验证单次逻辑，再扩大搜索。
3. 用 `--parallel --workers N` 并行参数 trial。
4. 缩小参数搜索空间，避免无意义组合。
5. 确认 K 线 JSON、DataFeed 和报告缓存没有被频繁无效化。

### Q: 如何贡献代码？

A: 保持最小必要改动，提交前运行：

```bash
ruff check workspace/ scripts/ main.py
uv run mypy workspace/cli workspace/common workspace/config workspace/data workspace/backtest workspace/strategies workspace/report
uv run pytest workspace/tests/ workspace/packages/python-contracts/tests/ --tb=short
```
