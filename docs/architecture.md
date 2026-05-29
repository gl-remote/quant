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

| 特性 | VnpyStrategyBridge | TqsdkStrategyBridge |
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
    def run_walk_forward(self, data, symbol, strategy, ...) -> dict
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

## 过拟合评估体系

系统通过四个维度评估策略过拟合风险：

| 维度 | 检测内容 | 风险阈值 |
|------|---------|---------|
| 收益递减 | 训练→测试收益率下降 | >50% |
| 回撤增加 | 测试集回撤 vs 训练集 | 差异 >10% |
| 夏普下降 | 风险调整收益衰退 | >50% |
| 胜率下降 | 交易信号质量退化 | >30% |