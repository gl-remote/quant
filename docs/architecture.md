# 系统架构设计

> 版本: 0.4.0-dev | 更新日期: 2026-06-27

---

## 架构总览

系统采用 **无状态策略核心 + 运行时上下文 + 桥接器 + 环境化持久化 + 离线报告** 的架构模式。

核心目标：

- 策略业务逻辑不依赖 vn.py / TqSdk；
- 策略运行状态集中在 `State`，便于回测、实盘、测试共用；
- 多周期数据、指标、事件由 `DataFeed` 统一管理；
- 通用趋势/确认/风控逻辑通过 `strategy_aspects` 复用；
- vn.py/TqSdk 差异封装在桥接器中；
- 回测结果按数据环境写入独立 SQLite；
- 报告由 Python 导出 JSON，React 前端通过内联 `window.__DATA__` 离线渲染。

### 核心设计原则

| 原则 | 说明 |
|------|------|
| **策略无状态** | `Strategy[T]` 不持有仓位、成交、资金等运行态，所有状态由 `State[T]` 保存 |
| **上下文驱动** | 每根 K 线由 `BarContext` 提供当前 bar、多周期视图、指标、事件和 aspects advice |
| **框架解耦** | vn.py / TqSdk 只通过 bridge 适配，策略核心代码不直接依赖交易框架 |
| **通用逻辑切面化** | 趋势、确认、止盈止损、冷却等逻辑优先用 `strategy_aspects` 装饰器/DSL 表达 |
| **数据环境隔离** | `backtest`、`test`、`live` 使用独立数据库和命令环境约束 |
| **离线报告** | 报告数据预加载到 HTML，支持 `file://` 直接打开 |

---

## 模块架构图

```text
main.py → cli/
    ├── main.py                         # 参数解析 + 子命令分发
    ├── env.py                          # --env / --config 校验与 DataManager 构建
    ├── commands/                       # export/test/backtest/report/live
    └── workflows/                      # 回测、报告、实时生命周期编排
├── strategies/                         # 策略系统
│   ├── core/
│   │   ├── base.py                     # Strategy[T] 无状态策略接口
│   │   ├── state.py                    # State[T] 运行态容器
│   │   └── types.py                    # Bar / Signal / Fill / StrategyPosition
│   ├── runtime/
│   │   ├── requirements.py             # DataRequirements / BarContext
│   │   ├── data_feed.py                # 多周期数据、指标、事件、forming bar
│   │   ├── aggregate.py                # 周期聚合
│   │   └── cache.py                    # DataFeed 运行时缓存
│   ├── strategy_aspects/               # 装饰器 DSL 与 advice 机制
│   │   ├── direction/                  # trend / confirm
│   │   ├── risk/                       # take-profit / stop-loss / entry-block
│   │   ├── indicators.py               # DSL 指标需求
│   │   └── primitives.py               # Advice / diagnostics 数据结构
│   ├── bridges/
│   │   ├── vnpy_backtest_bridge.py     # vn.py CtaTemplate 适配
│   │   └── tqsdk_bridge.py             # TqSdk 实时/回测式适配
│   ├── utils/loader.py                 # 约定式动态策略加载
│   ├── ma_strategy.py                  # MA 策略
│   └── atr_strategy.py                 # ATR 策略
├── backtest/
│   ├── vnpy_backtest_engine.py         # vn.py 批量回测引擎
│   ├── strategy_factory.py             # 动态创建并注入 bridge class
│   ├── optimizer.py                    # 串行 Grid / Optuna Bayesian 搜索
│   ├── parallel.py                     # 多进程并行 trial
│   ├── walk_forward.py                 # Walk-Forward 窗口切分
│   ├── results.py                      # Walk-Forward 结果模型
│   └── persister.py                    # Search / WalkForward / Backtest 持久化
├── data/
│   ├── manager.py                      # DataManager 统一入口
│   ├── datasource/                     # tqsdk / akshare 数据源
│   ├── models.py                       # peewee ORM 模型
│   ├── schema.py                       # schema version 与迁移
│   ├── store.py                        # SQLite 持久化与查询
│   ├── report_queries.py               # 报告查询
│   ├── optuna_query.py                 # Optuna 查询
│   └── output_paths.py                 # project_data 路径集中定义
├── report/
│   ├── builder/
│   │   ├── data_exports.py             # run/summary/backtests/equity/kline 等导出任务
│   │   ├── frontend.py                 # Vite 前端构建
│   │   └── entry_html.py               # 写 index.html + window.__DATA__
│   ├── writer/json_writer.py           # JSON 写入器
│   ├── cache/                          # 报告构建缓存、K 线 JSON 缓存
│   ├── reporter/                       # 文本报告、Optuna ECharts spec
│   └── web/                            # React + TypeScript 前端
├── common/                             # 通用类型、公式、统计、合约规格、格式化
├── config/                             # Pydantic 配置模型 + TOML 合并
└── project_data/                       # 本地数据、数据库、报告、日志、缓存、profile、coverage
```

---

## CLI 与环境架构

### 子命令

当前 CLI 注册 5 个子命令：

| 命令 | 职责 | 允许环境 |
|------|------|----------|
| `export` | 导出行情 CSV，记录 metadata 和 operation log | `backtest`、`test`、`live` |
| `backtest` | vn.py/TqSdk 回测、优化、Walk-Forward | `backtest` |
| `report` | 文本报告或构建前端报告 | `backtest`、`test`、`live` |
| `test` | TqSdk 实时信号测试，不下单 | `test` |
| `live` | TqSdk 实盘/模拟交易链路 | `live` |

所有业务命令必须显式指定 `--env` 或 `--config`。`cli/env.py` 会根据命令校验 data environment，防止实盘、测试、回测数据混用。

### 配置加载顺序

`--env backtest`：

```text
workspace/config/conf.toml
→ workspace/config/conf.backtest.toml
→ workspace/config/conf.backtest.local.toml
→ TQSDK_API_KEY / TQSDK_API_SECRET
```

`--config path/to/custom.toml`：

```text
workspace/config/conf.toml
→ path/to/custom.toml
→ TQSDK_API_KEY / TQSDK_API_SECRET
```

相对路径会解析到项目根目录。当前不会自动加载通用的 `conf.local.toml`。

---

## 核心架构模式：Strategy + State + BarContext + Bridge

### 当前策略接口

```python
class Strategy(Generic[T]):
    def data_requirements(self, config: T) -> DataRequirements | None: ...
    def on_bar(self, state: State[T], ctx: BarContext) -> Signal: ...
    def on_fill(self, fill: Fill) -> None: ...
```

`Strategy` 是纯决策层，不保存运行态。状态与上下文分离：

| 对象 | 职责 |
|------|------|
| `Strategy[T]` | 生成交易信号，不直接下单，不保存仓位 |
| `State[T]` | 保存 symbol、period、strategy_config、capital、contract_size、margin、position、fills、run_id、backtest_id、extra |
| `BarContext` | 保存当前 `Bar`、多周期视图 `multi`、事件 `events`、切面建议 `aspects` |
| `Bridge` | 将框架数据转为内部对象、调用策略、执行订单、同步成交回状态 |

### vn.py 调用流程

```text
Bridge.on_init()
  ├─ strategy.data_requirements(config)
  └─ 创建 DataFeed，注册周期和指标

Bridge.on_bar(vnpy_bar)
  ├─ vnpy BarData → Bar
  ├─ DataFeed.update_bar()
  ├─ DataFeed.build_context() → BarContext
  ├─ strategy_aspects 执行并写入 ctx.aspects
  ├─ strategy.on_bar(state, ctx) → Signal
  └─ Signal → vn.py buy/sell/short/cover

Bridge.on_trade(vnpy_trade)
  ├─ vnpy TradeData → Fill
  ├─ 更新 state.position 和 state.fills
  └─ strategy.on_fill(fill)
```

### 信号后处理

`Strategy` 基类会自动对 `on_bar()` 返回的 `Signal` 做后处理：

1. 将 `ctx.aspects` 中的方向和风控建议展平为 diagnostics；
2. 复制到 `signal.diagnostics`；
3. 当 `signal.action` 非空时，把 `signal.reason` 序列化为 JSON，便于日志、交易记录和报告解释交易原因。

---

## Runtime：多周期数据与指标上下文

`strategies/runtime/` 是当前策略系统的一等模块。

### DataRequirements

策略通过 `data_requirements(config)` 声明：

- 需要哪些周期；
- 每个周期需要多少历史 K 线；
- 需要哪些指标；
- 是否需要事件。

使用 `strategy_aspects` 的策略无需手动声明全部指标需求；装饰器会把 DSL 中涉及的指标需求合并进去。

### DataFeed

`DataFeed` 管理单品种多周期数据：

| 能力 | 说明 |
|------|------|
| 基础周期 | 自动选择最小周期作为 base period |
| 高周期聚合 | 在 `build_context()` 时由 base period 现场聚合 |
| forming bar | 高周期未完整时，用已到达 base bar 形成中的 K 线提供实时性 |
| 可见性控制 | 预载未来数据不会提前暴露给策略 |
| 指标计算 | 指标在 `build_context → get_data` 时按需惰性计算 |
| 事件 | `EventManager` 管理事件数据 |
| 调试 | `--dump-indicators` 可将指标列回写到基础周期 DataFrame |

---

## Strategy Aspects 架构

`strategy_aspects` 用装饰器和 DSL 把通用策略逻辑从策略主体中抽离出来。

### Advice 机制

切面不会直接交易，只写入 `ctx.aspects`：

```text
ctx.aspects.direction.long.trend
ctx.aspects.direction.long.confirm
ctx.aspects.direction.short.trend
ctx.aspects.direction.short.confirm
ctx.aspects.risk.take_profit.exit
ctx.aspects.risk.stop_loss.exit
ctx.aspects.risk.take_profit.entry_block
ctx.aspects.risk.stop_loss.entry_block
```

策略核心再消费这些 advice，决定是否开仓、平仓或跳过。

### 当前常用装饰器

| 类别 | 装饰器 |
|------|--------|
| 趋势方向 | `@trend_long`、`@trend_short` |
| 入场确认 | `@confirm_long`、`@confirm_short` |
| 止盈止损 | `@exit_for_take_profit`、`@exit_for_stop_loss` |
| 入场阻断 | `@entry_block_after_take_profit`、`@entry_block_after_stop_loss` |

### DSL 能力

当前 DSL 支持指标和函数组合，例如：

```text
macd@5m > 0
kdj@5m < {kdj_pullback_long}
sma({sma_short})@15m > sma({sma_long})@15m
atr@15m * {atr_stop_loss_multiplier}
cooldown() < 10
profit_pct() >= {take_profit_ratio}
loss_abs() >= atr@15m * {atr_stop_loss_multiplier}
peak_profit() >= atr@15m * {trailing_activation_atr} && drawdown_pct() >= {trailing_drawdown_ratio}
```

常见内置指标：`macd`、`kdj`、`sma(period)`、`atr(period=14)`。

常见内置函数：`cooldown`、`profit_abs`、`profit_pct`、`loss_abs`、`loss_pct`、`peak_profit`、`drawdown_pct`。

---

## 策略加载与内置策略

### 约定式动态加载

策略加载位于 `strategies/utils/loader.py`。输入策略名后按约定解析：

| 输入 | 目标文件 |
|------|----------|
| `ma` | `workspace/strategies/ma_strategy.py` |
| `ma_strategy` | `workspace/strategies/ma_strategy.py` |
| `atr` | `workspace/strategies/atr_strategy.py` |
| `xxx` | `workspace/strategies/xxx_strategy.py` |

加载流程：

1. 将 `xxx` 标准化为 `xxx_strategy`；
2. import `strategies.xxx_strategy`；
3. 扫描继承自 `Strategy` 的具体类；
4. 返回策略实例；
5. 回测工厂通过泛型反射识别参数 dataclass 并构建 `State`。

### 当前内置策略

| 策略 | 核心类 | 说明 |
|------|--------|------|
| `ma` | `MaStrategyCore` | MA 趋势 + MACD/KDJ 确认 + ATR/比例止盈止损 + 移动止盈 + 冷却 |
| `atr` | `ATRStrategyCore` | ATR 风控策略，包含趋势、ATR 止盈止损、移动止盈、KDJ 回调和时间退出 |

配置中通过 `[[strategies]] name = "ma"` / `"atr"` 管理策略参数和搜索空间。

---

## 回测与优化架构

### 引擎选择

`backtest` 命令通过 `--engine` 显式选择引擎：

| 引擎 | 用途 |
|------|------|
| `vnpy` | 默认主路径，支持批量回测、参数搜索、并行、Walk-Forward、落库、报告构建 |
| `tqsdk` | 单标的回测/GUI/实时式场景，必须提供 `--symbol`、`--start`、`--end` |

`--symbol` / `--pattern` 只控制标的过滤，不影响引擎选择。`--gui` 只在 `--engine tqsdk` 下生效。

### vn.py search 数据流

```text
CLI backtest
  ↓
build_data_context(args, "backtest")
  ↓
BacktestRunWorkflow.run_vnpy_search()
  ├─ 读取策略配置和 backtest config
  ├─ DataManager.load_kline() 加载本地 CSV
  ├─ 创建 run 记录与 project_data/logs/runs/r{run_id}/run.log
  ├─ 根据 optimizer / no-search / parallel 选择执行路径
  │   ├─ 单次回测: VnpyBacktestEngine.run()
  │   ├─ 串行优化: BacktestOptimizer
  │   └─ 并行优化: ProcessPoolExecutor workers
  ├─ StrategyFactory 动态创建 VnpyBacktestBridge 子类
  ├─ vn.py BacktestingEngine 执行回测
  ├─ bridge 调用 Strategy + DataFeed + aspects
  ├─ VnpyBacktestEngine 汇总 statistics / daily / trades
  ├─ BacktestResultPersister / SearchResultPersister 写入 SQLite
  └─ RunFinalizer 构建报告数据和 index.html
```

### 参数优化

支持：

| 模式 | 说明 |
|------|------|
| `grid` | Optuna GridSampler 枚举搜索空间 |
| `bayesian` | Optuna TPESampler 贝叶斯优化 |
| `--parallel` | 多进程并行执行 trial，主进程统一持久化 |

Study 命名约定：

```text
{strategy}_{engine}_r{run_id}
```

Optuna 存储使用当前环境 SQLite 数据库。

### Walk-Forward

当前 Walk-Forward 主要包括：

- 时间窗口切分；
- 每个窗口 train / validation / test 回测；
- OOS return、Sharpe、drawdown、win rate、positive window ratio、stability score、IS/OOS gap 聚合；
- 聚合结果通过 `WalkForwardPersister` 写入数据库。

当前不应把它描述为“每个窗口内重新 Optuna 优化参数后再 OOS 测试”的完整 WFO。

---

## 数据层架构

### 本地数据目录

统一路径由 `data/output_paths.py` 和 `report/output_paths.py` 管理。

```text
project_data/
├── market_data/csv/              # CSV K 线
├── database/
│   ├── backtest/quant.db
│   ├── test/quant.db
│   └── live/quant.db
├── reports/                      # 前端报告产物
├── logs/                         # run log / worker log
├── cache/
│   ├── report_build/
│   ├── kline_json/
│   └── datafeed/
├── profiles/
└── coverage/
```

### CSV 与导出元数据

CSV 文件名模板：

```text
{symbol}.{provider}.{interval}.csv
```

标准列：

```text
datetime, open, high, low, close, volume, amount
```

导出流程：

```text
export 命令
  ↓
DataExporter
  ├─ 选择 tqsdk / akshare 数据源
  ├─ 拉取 K 线
  ├─ 与已有 CSV 合并去重
  ├─ 写入 project_data/market_data/csv
  ├─ 更新 export_metadata
  └─ 写入 operation_logs
```

### SQLite 主要表

当前 schema version 为 3，主要表：

| 表 | 说明 |
|----|------|
| `runs` | 一次回测/搜索/Walk-Forward 运行 |
| `run_studies` | run 与 Optuna study 关联 |
| `export_metadata` | CSV 导出元数据 |
| `operation_logs` | 数据导出等操作日志 |
| `backtests` | 单条回测结果主表 |
| `backtest_params` | 回测参数，支持数值和非数值参数 |
| `backtest_trades` | 成交记录与 reason |
| `backtest_daily` | 日度结果 |
| `schema_info` | schema version |
| `realtime_sessions` | 实时/实盘会话 |
| `realtime_trades` | 实时/实盘成交 |

---

## 回测结果数据模型

`common/types.py` 中的 `BacktestResult` 是回测引擎、优化器、持久化和报告之间的核心交换模型，包含：

- symbol / strategy / strategy_version；
- status / error_message / success；
- start_date / end_date / total_days；
- total_trades / fills / daily_results；
- end_balance / total_return / annual_return；
- sharpe_ratio / max_drawdown / max_ddpercent；
- total_net_pnl / commission / slippage / turnover；
- win_trades / loss_trades / win_rate / avg_win / avg_loss；
- engine_config / data_src / strategy_params / git_hash。

### vn.py statistics 格式约定

vn.py `calculate_statistics()` 的部分字段已有格式约定：

| 字段 | 格式 | 示例 | 报告处理 |
|------|------|------|----------|
| `total_return` | 百分比，已乘 100 | `15.2` 表示 15.2% | 直接格式化为 `%` |
| `annual_return` | 百分比，已乘 100 | `8.5` 表示 8.5% | 直接格式化为 `%` |
| `max_drawdown` | 绝对金额 | `5200` | 按金额显示 |
| `max_ddpercent` | 百分比，已乘 100 | `12.5` 表示 12.5% | 直接格式化为 `%` |

---

## 报告模块架构

报告模块已拆分为 `builder/`、`writer/`、`cache/`、`reporter/` 和 `web/`，不是单一 `builder.py`。

### 构建流程

```text
ReportWorkflow.build(request)
  ├─ run_data_exports()
  │   ├─ export_run_json()
  │   ├─ export_summary_json()
  │   ├─ export_backtests_json()
  │   ├─ export_equity_json()
  │   ├─ export_kline_json()      # KlineCache: CSV → JSON 缓存
  │   ├─ export_trades_json()
  │   ├─ export_optuna_json()     # ECharts option JSON
  │   └─ write_nav_json()
  ├─ build_frontend()             # npm run build，输出 assets/index.js/css
  ├─ 导出 logs.json hook
  └─ write_entry_html()           # 内联 window.__DATA__
```

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

### 前端加载

- React 18 + TypeScript + Vite；
- UI 使用 Ant Design；
- 图表主要使用 ECharts 和 lightweight-charts；
- Vite `base: "./"`，资源固定输出为 `assets/index.js` 和 `assets/index.css`；
- `index.html` 内联 `window.__DATA__`；
- 前端通过 HashRouter 路由：`/` 导航页，`/run/:id` 单 run 报告页；
- 前端 loader 只读取预加载数据，不依赖 `fetch()`，因此支持 `file://`。

---

## 当前能力边界

| 主题 | 当前边界 |
|------|----------|
| vn.py | 主回测路径，支持批量、优化、并行、Walk-Forward、落库和报告 |
| TqSdk | 主要用于单标的 GUI、实时信号、模拟/实盘式桥接；与 vn.py 报告生命周期不完全等价 |
| Walk-Forward | 当前是窗口切分 + 窗口回测 + OOS 聚合，不是完整窗口内再优化 WFO |
| 并行优化 | 多进程 trial；worker 不直接写库，主进程统一持久化 |
| 报告 | 构建结果离线可看，但数据库变化后需要重新 `report --build` |
