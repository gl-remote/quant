# 系统架构设计

> 版本: 0.2.0-dev | 更新日期: 2026-05-26

---

## 架构总览

系统采用**策略核心 + 桥接器**的架构模式，实现业务逻辑与执行框架的完全分离。

### 核心设计原则

| 原则 | 说明 |
|------|------|
| **策略一致性** | 回测和实盘使用同一份算法代码，消除实现差异 |
| **框架可替换** | 更换交易框架只需新增桥接器，核心代码零改动 |
| **单一职责** | 每个模块职责明确，避免职责重叠 |
| **零依赖层** | `common/` 纯函数库，无 I/O、无副作用 |

### 模块架构图

```
main.py (19行转发器) → cli/
    ├── cli/main.py          参数解析 + 命令分发
    └── commands/            5个子命令 (export/test/backtest/report/live)
├── strategies/              策略核心
│   ├── core/base.py         Strategy ABC
│   ├── core/types.py        Bar/Signal/Fill/StrategyPosition
│   ├── ma_strategy.py       MaStrategyCore (纯业务逻辑)
│   └── bridges/             框架桥接器
│       ├── vnpy_bridge.py   vn.py 桥接
│       └── tqsdk_bridge.py  天勤桥接
├── backtest/                回测引擎
│   ├── vnpy_backtest_engine.py  批量回测 + Walk-Forward
│   └── walk_forward.py          数据加载与时间窗口切分
├── optimizer/               参数优化
│   ├── grid_search.py       网格搜索
│   └── optuna_search.py     Optuna 贝叶斯优化
├── data/                    数据层
│   ├── manager.py           DataManager 统一入口
│   ├── models.py            Pydantic + peewee ORM 模型
│   ├── store.py             SQLite 持久化
│   └── exporter.py          天勤→CSV 导出
├── report/                  报告生成
│   ├── reports.py           文字报告
│   ├── charts.py            Plotly 可视化
│   ├── optimizer_report.py  Optuna 优化报告
│   └── _html.py             HTML 模板
├── common/                  通用工具 (零依赖)
│   ├── constants.py         全局常量字典
│   ├── formulas.py          量化计算公式库
│   ├── schemas.py           Pandera Schema 定义
│   ├── metrics.py           绩效指标
│   ├── stats.py             统计聚合
│   └── formatting.py        安全格式化
└── config/                  配置管理
    └── app_config.py        Pydantic 配置模型 + 单例
```

---

## 核心架构模式：核心 + 桥接器

这是系统最重要的设计决策。策略核心算法完全独立于任何交易框架，桥接器负责协议转换。

### 调用流程

```
Bridge 调用流程:
  bar = Bar(...)                     # 1. Bridge 将框架数据转为标准 Bar
  signal = strategy.on_bar(bar)      # 2. Strategy 产生决策
  bridge.execute(signal)             # 3. Bridge 翻译为框架指令
  strategy.on_fill(fill)             # 4. 成交回执 → 更新状态
```

### 桥接器对比

| 特性 | VnpyStrategyBridge | TqsdkStrategyBridge |
|------|-------------------|---------------------|
| 用途 | vn.py 批量回测 | 天勤实盘/模拟/回测 |
| 订单执行 | `self.buy/sell` | 手动交易记录 |
| 行情格式 | vnpy BarData | tqsdk kline_serial |

---

## 模块职责详解

### 1. Strategy 层

#### `strategies/core/base.py` — 策略抽象基类

```python
class Strategy(ABC):
    @abstractmethod
    def on_bar(self, bar: Bar) -> Signal:        # 处理 K 线，返回交易信号
    @abstractmethod
    def on_fill(self, fill: Fill) -> None:       # 成交回调，更新状态
    @property
    def position(self) -> StrategyPosition:      # 当前持仓
    @abstractmethod
    def reset(self) -> None:                     # 重置状态（新回测）
```

#### `strategies/core/types.py` — 数据类型定义

| 类型 | 用途 | 关键字段 |
|------|------|----------|
| `Bar` | 标准化 K 线数据 | `datetime, open, high, low, close, volume` |
| `Signal` | 交易决策信号 | `action, volume, reason` |
| `Fill` | 成交回执 | `timestamp, action, price, volume, pnl` |
| `StrategyPosition` | 持仓状态 | `direction, entry_price, volume` |

#### `strategies/ma_strategy.py` — 均线交叉策略核心

**决策逻辑流程**：
1. 更新收盘价缓存
2. 计算双均线（SMA短/长周期）
3. 交叉检测（金叉买入/死叉卖出）
4. 风控检查（止损/止盈）

**关键方法**：
| 方法 | 功能 |
|------|------|
| `on_bar()` | 策略决策中枢，返回 Signal |
| `on_fill()` | 成交回调，更新持仓和交易记录 |
| `_is_golden_cross()` | 金叉检测 |
| `_is_death_cross()` | 死叉检测 |
| `_check_stop_loss()` | 止损检查 |
| `_check_take_profit()` | 止盈检查 |
| `_calc_position_size()` | 计算仓位大小 |

---

### 2. Backtest 层

#### `backtest/vnpy_backtest_engine.py` — vn.py 回测引擎

**设计原则**：纯执行器，不负责数据加载和策略创建。

**核心接口**：

```python
class VnpyBacktestEngine:
    def __init__(self, backtest_config: BacktestConfig, dm: DataManager)
    def run(self, pairs: list[tuple[str, DataFrame, Strategy]]) -> list[dict]
    def run_walk_forward(self, data, symbol, strategy, ...) -> dict
```

**run() 方法**：
- 接收 `(symbol, DataFrame, Strategy)` 配对列表
- 同一份 DataFrame 共用一个 vnpy engine，一次回放跑多个策略
- 返回结构化结果：`statistics`, `daily_results`, `strategy_name` 等

**run_walk_forward() 方法**：
- 滚动时间窗口验证
- 自动切分 train/val/test 窗口
- 返回窗口结果列表和聚合指标

#### `backtest/walk_forward.py` — 时间窗口切分

| 函数 | 功能 |
|------|------|
| `walk_forward_split()` | 按固定行数切分窗口 |
| `walk_forward_split_by_ratio()` | 按比例切分窗口（60%/20%/20%） |
| `df_to_vnpy_datalines()` | DataFrame → vnpy BarData 转换 |

---

### 3. Data 层

#### `data/manager.py` — DataManager 统一入口

**设计原则**：对外隐藏数据库概念，仅暴露数据类型约定。

**核心接口**：

| 方法 | 功能 | 返回值 |
|------|------|--------|
| `get_all_symbols()` | 获取所有可用品种 | `list[str]` |
| `search_symbols(pattern)` | 正则搜索品种 | `list[str]` |
| `get_symbol_info(symbol)` | 获取品种元数据 | `SymbolInfo` |
| `load_kline(symbol, start, end, interval)` | 加载 K 线数据 | `DataFrame[KlineSchema]` |
| `insert_backtest(...)` | 插入回测记录 | `int` (backtest_id) |
| `query_backtests(...)` | 查询回测记录 | `list[BacktestRecord]` |
| `insert_backtest_trades()` | 批量插入交易明细 | `int` |
| `insert_backtest_daily()` | 批量插入每日资金曲线 | `int` |

**数据验证**：所有 DataFrame 通过 Pandera `KlineSchema` 验证。

#### `data/store.py` — SQLite 持久化层

**数据库表结构**：

| 表名 | 用途 |
|------|------|
| `backtest` | 回测主记录 |
| `backtest_trade` | 交易明细 |
| `backtest_daily` | 每日资金曲线 |
| `export_metadata` | 数据导出元数据 |
| `operation_log` | 操作日志 |

#### `data/models.py` — 数据模型

| 模型类型 | 用途 |
|----------|------|
| `BacktestRecord` | Pydantic 模型，回测记录 |
| `TradeRecord` | Pydantic 模型，交易记录 |
| `Backtest` | peewee ORM 模型 |
| `BacktestTrade` | peewee ORM 模型 |
| `BacktestDaily` | peewee ORM 模型 |
| `KlineSchema` | Pandera Schema，K 线验证 |

---

### 4. Optimizer 层

#### `optimizer/grid_search.py` — 网格搜索

```python
class GridOptimizer:
    def __init__(self, engine, datasets, strategy_name, param_grid, ...)
    def run(self) -> OptimizationResult
```

**工作流程**：
1. 根据 `param_grid` 生成所有参数组合
2. 为每个组合创建策略实例
3. 调用 `engine.run()` 执行回测
4. 返回最优参数和所有结果

#### `optimizer/optuna_search.py` — Optuna 贝叶斯优化

```python
class OptunaOptimizer:
    def __init__(self, engine, datasets, search_space, n_trials, ...)
    def optimize(self) -> OptimizationResult
```

**工作流程**：
1. 创建 Optuna Study
2. 定义目标函数（最大化夏普比率或自定义指标）
3. 执行贝叶斯优化搜索
4. 持久化所有 trial 结果到 SQLite

---

### 5. CLI 层

#### `cli/main.py` — 命令分发

```python
def main():
    parser = argparse.ArgumentParser(...)
    sub = parser.add_subparsers(dest='command', required=True)
    # 添加子命令: export, test, backtest, report, live
    args = parser.parse_args()
    command_handlers[args.command](args)
```

#### `cli/commands/backtest.py` — 回测命令

**核心职责**：编排 `data` → `optimizer` → `backtest` 三层。

**模式切换**：
- `--symbol` 指定单品种 → TqSdk 图形化回测
- `--pattern` 或省略 → vn.py 批量回测

**回测模式**：
- `mode=search`：参数搜索（默认）
- `mode=walk-forward`：Walk-Forward 滚动验证

---

### 6. Common 层（零依赖）

| 模块 | 职责 | 关键函数 |
|------|------|----------|
| `constants.py` | 全局常量 | 交易方向、信号原因、默认参数 |
| `formulas.py` | 量化计算公式 | `simple_moving_average`, `golden_cross`, `position_size` |
| `schemas.py` | Pandera Schema | `KlineSchema`, `DailyReturnSchema` |
| `metrics.py` | 绩效指标 | `max_drawdown`, `sharpe_ratio` |
| `stats.py` | 统计聚合 | `rank_by_key`, `summary_stats` |
| `formatting.py` | 安全格式化 | `format_pct`, `ensure_float`, `parse_percentage` |

---

## 数据流

### 回测数据流

```
DataManager.load_kline() → DataFrame
    │
    ├──▶ split_datasets() → train_df, val_df, test_df
    │
    └──▶ VnpyBacktestEngine.run(pairs)
            │
            ├──▶ vnpy BacktestingEngine
            │       ├──▶ VnpyStrategyBridge.on_bar()
            │       │       └──▶ Strategy.on_bar(bar) → Signal
            │       └──▶ calculate_statistics()
            │
            └──▶ 返回: statistics, daily_results
                    │
                    └──▶ DataManager.insert_backtest() → SQLite
```

### 数据导出流

```
天勤 API → exporter._fetch_from_tqsdk() → DataFrame
    │
    ├──▶ 已有 CSV? → pd.concat + drop_duplicates
    │
    └──▶ 保存: {symbol}.{interval}.csv
            │
            └──▶ DataStore.upsert_metadata() → SQLite
```

---

## 配置系统

### 配置层级

```
ProjectConfig (单例)
    ├── app: AppConfig
    ├── environment: EnvironmentConfig
    ├── strategies: list[StrategyItemConfig]
    ├── backtest: BacktestConfig
    │   └── split: SplitConfig
    ├── data: DataConfig
    ├── export: ExportConfig
    ├── optimizer: OptimizerConfig
    ├── system: SystemConfig
    └── third_party: ThirdPartyConfig
```

### 配置加载流程

1. 读取 `config/conf.toml`（基础配置）
2. 读取 `config/conf.local.toml`（本地覆盖，不提交版本控制）
3. 解析环境变量（API 密钥优先）
4. 路径解析（相对路径 → 绝对路径）
5. Pydantic 模型校验

### 配置访问方式

```python
from config import ProjectConfig

cfg = ProjectConfig.instance()
bc = cfg.backtest                    # BacktestConfig
sc = cfg.get_strategy_config("ma")   # StrategyItemConfig
```

---

## 过拟合评估体系

系统通过四个维度评估策略过拟合风险：

| 维度 | 检测内容 | 风险阈值 |
|------|---------|---------|
| 收益递减 | 训练→测试收益率下降 | >50% |
| 回撤增加 | 测试集回撤 vs 训练集 | 差异 >10% |
| 夏普下降 | 风险调整收益衰退 | >50% |
| 胜率下降 | 交易信号质量退化 | >30% |

**评分范围**：0-100，分数越高风险越大。
