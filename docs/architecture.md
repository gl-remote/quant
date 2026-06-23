# 系统架构设计

> 版本: 0.2.0-dev | 更新日期: 2026-05-27

---

## 架构总览

系统采用**策略核心 + 桥接器**的架构模式，实现业务逻辑与执行框架的完全分离。报告模块采用 **Python 数据导出 + React 前端渲染** 的方式，支持 `file://` 协议直接打开。

### 核心设计原则

| 原则 | 说明 |
|------|------|
| **策略一致性** | 回测和实盘使用同一份算法代码，消除实现差异 |
| **框架可替换** | 更换交易框架只需新增桥接器，核心代码零改动 |
| **单一职责** | 每个模块职责明确，避免职责重叠 |
| **零依赖层** | `common/` 纯函数库，无 I/O、无副作用 |
| **数据预加载** | 报告数据嵌入 HTML，支持 `file://` 协议 |

### 模块架构图

```
main.py → cli/
    ├── cli/main.py          参数解析 + 命令分发
    └── commands/            5个子命令 (export/test/backtest/report/live)
├── strategies/              策略核心
│   ├── core/base.py         Strategy ABC
│   ├── core/types.py        Bar/Signal/Fill/StrategyPosition
│   ├── ma_strategy.py       MaStrategyCore (纯业务逻辑)
│   └── bridges/             框架桥接器
│       ├── vnpy_bridge.py   vn.py 桥接
│       └── tqsdk_bridge.py  天勤桥接
├── backtest/                回测与优化引擎
│   ├── vnpy_backtest_engine.py  批量回测
│   ├── walk_forward.py          Walk-Forward 时间窗口切分
│   ├── runners.py               批量回测编排
│   └── optimizer.py             Optuna 参数优化器
├── data/                    数据层
│   ├── manager.py           DataManager 统一入口
│   ├── models.py            Pydantic + peewee ORM 模型
│   ├── store.py             SQLite 持久化
│   └── exporter.py          天勤→CSV 导出
├── report/                  报告生成
│   ├── builder.py           JSON 导出 + 前端构建触发
│   ├── charts.py            Plotly JSON spec 生成
│   ├── optimizer_report.py  Optuna 优化报告
│   ├── kline_cache.py       K线缓存机制
│   └── web/                 React 前端工程
│       ├── src/components/  KlineChart/EquityChart/SymbolTable
│       ├── src/pages/       NavPage/RunPage/OptunaPage
│       └── src/data/loader.ts 数据预加载读取
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

策略核心算法完全独立于任何交易框架，桥接器负责协议转换。

### 调用流程

```
Bridge 调用流程:
  bar = Bar(...)                     # 1. Bridge 将框架数据转为标准 Bar
  signal = strategy.on_bar(bar)      # 2. Strategy 产生决策
  bridge.execute(signal)             # 3. Bridge 翻译为框架指令
  strategy.on_fill(fill)             # 4. 成交回执 → 更新状态
```

### 桥接器对比

| 特性 | VnpyBacktestBridge | TqsdkStrategyBridge |
|------|-------------------|---------------------|
| 用途 | vn.py 批量回测 | 天勤实盘/模拟/回测 |
| 订单执行 | `self.buy/sell` | 手动交易记录 |
| 行情格式 | vnpy BarData | tqsdk kline_serial |

---

## 报告模块架构

报告模块采用前后端分离设计，Python 负责数据导出，React 负责可视化渲染。

### 数据流

```
finish_run(run_id)
    ↓
build_all(db_path, output_dir, run_id)
    ├─ export_run_json()
    ├─ export_summary_json()
    ├─ export_backtests_json()
    ├─ export_equity_json()
    ├─ export_kline_json()          # 带缓存机制
    ├─ export_optuna_json()
    └─ write_entry_html()           # 数据预加载嵌入
```

### 输出结构

```
output/
├── index.html                      # 单页应用入口
├── data/
│   └── nav.json                    # 全局导航数据
├── rN/
│   └── data/
│       ├── run.json                # run 元信息
│       ├── summary.json            # 品种汇总
│       ├── backtests.json          # 回测列表
│       ├── kline_*.json            # K线数据
│       └── optuna.json             # 优化数据（如有）
└── assets/
    ├── index-[hash].js             # React bundle
    └── vendor/plotly.min.js        # Plotly 库
```

### 数据预加载机制

为支持 `file://` 协议，所有数据通过 `window.__DATA__` 预加载：

```python
# builder.py - write_entry_html()
# 遍历所有 JSON 文件，嵌入到 HTML 中
<script>
window.__DATA__ = {
    "data/nav.json": [...],
    "r1/data/run.json": {...},
    "r1/data/kline_DCE.m2509.json": [...]
}
</script>
```

---

## K线缓存机制

`report/kline_cache.py` 实现 K线数据的增量缓存：

| 场景 | 行为 |
|------|------|
| 首次构建 | CSV → JSON，写入 `output/.kline_cache/{md5}.json` |
| 二次构建同品种 | 缓存命中，O(1) 复制 |
| CSV 文件更新 | 基于文件 mtime 自动失效 |

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

---

### 2. Backtest 层

#### `backtest/vnpy_backtest_engine.py` — vn.py 回测引擎

**核心接口**：

```python
class VnpyBacktestEngine:
    def __init__(self, backtest_config: BacktestConfig, dm: DataManager)
    def run(self, pairs: list[tuple[str, DataFrame, Strategy]]) -> list[dict]
    def run_walk_forward(self, data, symbol, strategy, ...) -> WalkForwardResult
```

---

### 3. Data 层

#### `data/manager.py` — DataManager 统一入口

**核心接口**：

| 方法 | 功能 | 返回值 |
|------|------|--------|
| `get_all_symbols()` | 获取所有可用品种 | `list[str]` |
| `search_symbols(pattern)` | 正则搜索品种 | `list[str]` |
| `load_kline(symbol, start, end, interval)` | 加载 K 线数据 | `DataFrame[KlineSchema]` |
| `insert_backtest(...)` | 插入回测记录 | `int` (backtest_id) |
| `query_backtests(...)` | 查询回测记录 | `list[BacktestRecord]` |

---

### 4. Report 层

#### `report/builder.py` — 报告构建器

**核心接口**：

```python
class ReportBuilder:
    def build_all(db_path, output_dir, run_id) -> None
    def export_run_json() -> dict
    def export_kline_json(symbol) -> dict          # 带缓存
    def write_entry_html(output_dir, run_id) -> None  # 预加载嵌入
    def build_frontend(output_dir) -> None           # 触发 npm build
```

---

### 5. Common 层（零依赖）

| 模块 | 职责 | 关键函数 |
|------|------|----------|
| `constants.py` | 全局常量 | 交易方向、信号原因、默认参数 |
| `formulas.py` | 量化计算公式 | `simple_moving_average`, `golden_cross` |
| `schemas.py` | Pandera Schema | `KlineSchema`, `DailyReturnSchema` |
| `metrics.py` | 绩效指标 | `max_drawdown`, `sharpe_ratio` |
| `stats.py` | 统计聚合 | `rank_by_key`, `summary_stats` |
| `formatting.py` | 安全格式化 | `format_pct`, `ensure_float` |

---

## 配置系统

### 配置加载流程

1. 读取 `config/conf.toml`（基础配置）
2. 读取 `config/conf.local.toml`（本地覆盖）
3. 解析环境变量（API 密钥优先）
4. 路径解析（相对路径 → 绝对路径）
5. Pydantic 模型校验

---

## 回测数据模型（2026-06-06 更新）

### vnpy 数据来源与格式约定

vnpy 4.4.0 的 `calculate_statistics()` 返回的统计数据有明确的**格式约定**：

| 字段 | 格式 | 示例 | 前端处理 |
|------|------|------|---------|
| `total_return` | **百分比**（已乘 100） | `15.2` 表示 15.2% | `.toFixed(2) + '%'` |
| `annual_return` | **百分比**（已乘 100） | `8.5` 表示 8.5% | 同上 |
| `max_drawdown` | **绝对金额**（元） | `5200` 表示亏了 5200 元 | `.toLocaleString('zh-CN')` + `'元'` |
| `max_ddpercent` | **百分比**（已乘 100） | `12.5` 表示 12.5% | `.toFixed(2) + '%'` |
| `win_rate` | **比值** (0~1) | `0.6` 表示 60% | store 层 `* 100` 后传前端 |

> ⚠️ **重要**: 前端/报告层不得对上述字段再做 `* 100` 或百分比转换。store 层负责统一格式化。

### 逐笔交易 PnL 计算方式

vnpy 的 `TradeData` 不提供逐笔 PnL 和 commission，这些由我们通过 FIFO 配对计算：

```
开仓队列: [(方向, 价格, 数量), ...]   # FIFO 先进先出
平仓时:
  1. 取最旧的开仓记录配对
  2. 毛利 = (平仓价 - 开仓价) × 配对数量 × 合约乘数 × 方向系数
  3. commission = 开仓侧(价格×数量×size×rate) + 平仓侧(价格×数量×size×rate)
  4. slippage = 开仓侧(数量×size×slip) + 平仓侧(数量×size×slip)
  5. 净盈亏(pnl) = 毛利 - commission - slippage
```

费用参数来源：引擎初始化时的 `rate`、`slippage`、`size`（与 vnpy 内部 `DailyResult.calculate_pnl()` 公式一致）。

### win_trades / loss_trades 统计范围

只统计 **pnl != 0 的平仓交易**（排除开仓记录 pnl=0 和持平交易）：

```python
closed_trades = [t for t in trades if t['pnl'] != 0]  # 排除开仓
win_trades = len([t for t in closed_trades if t['pnl'] > 0])
loss_trades = len([t for t in closed_trades if t['pnl'] < 0])
# 注意: win_trades + loss_trades <= total_trades（后者含所有成交）
```

### 数据库表结构

#### backtests 表（53 列）

字段按来源分为四组：

| 分组 | 来源 | 关键字段 |
|------|------|----------|
| 元数据 | 我们自己 | symbol, strategy, version, git_hash, status, dates, config params |
| **vnpy 直接提供** `[vnpy]` | `engine.calculate_statistics()` | total_return, end_balance, sharpe_ratio, max_drawdown, annual_return, daily_std, return_drawdown_ratio, **新增15个** |
| **自行计算** | 基于 trades 的 pnl 字段聚合 | win_trades, loss_trades, win_rate, avg_win, avg_loss, win_loss_ratio, max_consecutive_win/loss |
| 日度汇总 | 基于 backtest_daily 聚合 | profit_days, loss_days 等 |

#### backtest_daily 表（11 列）

每条记录对应一个交易日，来自 vnpy `DailyResult`：

| 字段 | 来源 |
|------|------|
| date, equity, drawdown_pct | vnpy DailyResult |
| **turnover, commission, slippage, trade_count** | vnpy DailyResult（2026-06-06 新增） |

### 一致性校验规则

`validate_backtest_consistency()` 执行以下检查：

| # | 校验项 | 规则 |
|---|--------|------|
| 1 | 盈亏笔数 ≤ 总成交数 | `win_trades + loss_trades <= total_trades` |
| 2 | 胜率匹配 | `abs(win_rate - win/(win+loss)) < 0.01` |
| 3 | profit_days 匹配 | `profit_days ≈ daily 表中 equity > prev_equity 的天数` |
| 4 | commission 对账 | `abs(total_commission - sum(trade.commission)) < 1.0` |

### 数据流全景

```
vnpy 引擎
  ├─ engine.trades (TradeData) → FIFO 配对 → 净盈亏 + 真实费用 → backtest_trades 表
  ├─ engine.daily_results (DailyResult) → turnover/commission/slippage → backtest_daily 表
  └─ engine.calculate_statistics() → 30+ 统计指标 → backtests 表
       ↓
BacktestResult dataclass (common/types.py) — 全量字段 + 默认值(TqSdk兼容)
       ↓
data/store.py — 写入 ORM + JSON 导出(get_run_summary / get_backtests_for_run)
       ↓
SQLite (自动迁移: ALTER TABLE 补列)
       ↓
前端 (types/index.ts → BacktestDetail/SymbolTable/MetricCards)
文字报告 (report/reporter/text.py — 详情+汇总表)
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