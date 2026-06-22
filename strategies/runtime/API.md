# runtime 模块对外 API 参考

`strategies.runtime` 负责策略运行时的内存数据编排：管理单品种多周期 K 线、按需聚合高周期、惰性计算指标、筛选事件，最终产出每根 bar 的 `BarContext` 供策略决策。

> 本文档**只收录已被 runtime 之外的代码（桥接层、策略切面、测试等）实际调用的 API**。模块内部使用、当前无人调用的接口不在此列。

## 核心流程

```
1. 策略声明 DataRequirements（周期 + 指标 + 事件）
2. 桥接代码构造 DataFeed 并灌入基础周期数据
3. 每根 bar 调用 DataFeed.build_context(...) 得到 BarContext
4. 策略基于 BarContext.multi[period].indicator(...) 等接口生成信号
```

---

## 1. 数据需求声明

### `IndicatorSpec`（dataclass, frozen）

```python
IndicatorSpec(
    name: str,
    params: dict[str, Any],
    window: int | str = 250,
    func: Callable[..., NDArray[np.float64]] | None = None,
)
```

- 描述「某指标如何计算」。`name` + `params` 决定列名（见下）。
- `window` 为计算所需最少 bar 数；可含模板字符串（如 `"{sma_short}"`），在构建需求时由 strategy_config 解析。
- `func` 接收 `pd.DataFrame` 返回 `NDArray`；为 `None` 时该指标不计算。
- 内置 func：`sma_func`、`ema_func`、`rsi_func`、`macd_func`、`kdj_func`、`atr_func`（均基于 ta-lib）。

### `generate_indicator_column_name(name, params, period="") -> str`

- 生成确定性列名：参数按名排序拼接。例如 `("sma", {"period": 10}, "5m")` → `"5m_sma_10"`。
- 策略读取指标值时必须用此函数生成的列名（含周期前缀）。

### `PeriodRequirements`（dataclass）

```python
PeriodRequirements(lookback_bars: int, min_bars: int | None = None)
```

- `lookback_bars`：每根 bar 构建视图时回看的历史 K 线数。
- `min_bars`：策略要求的最小 K 线数（可选，用于校验）。

### `EventsRequirements`（dataclass）

```python
EventsRequirements.no_events()   # 类方法：不获取任何事件
```

- 实际使用的构造方式只有 `no_events()`。

### `DataRequirements`（dataclass）

```python
DataRequirements(
    periods: dict[str, PeriodRequirements],
    indicators: dict[str, list[IndicatorSpec]],
    events: EventsRequirements = EventsRequirements.no_events(),
)
```

- 策略的完整数据需求（类比数据库查询计划）。key 为周期名。
- **`merge(other: DataRequirements) -> None`**：原地合并另一需求（用于 AOP/切面追加数据）。
  - `periods`：缺失的 key 追加；已存在的取 `lookback_bars` 最大值。
  - `indicators`：按 `(name, params)` 判重后追加。
  - `events`：不合并（各自独立）。

---

## 2. `DataFeed` — 单品种多周期数据管理器

### 构造与初始化

#### `DataFeed(symbol, source=None, requirements=None)`
- `source` 为 `None` 时按合约代码推断交易所。
- 传入 `requirements` 时自动注册周期、选取基础周期、注册指标。

#### `classmethod DataFeed.create(symbol, requirements) -> DataFeed`
- 完整构造：自动加载 native K 线、命中内存/磁盘缓存、增量加载、设置缓存目录。
- 所有声明周期都无数据时回退内存缓存；仍无则抛 `FileNotFoundError`。
- 生产路径（回测桥接器）的推荐入口。

### 数据灌入

#### `load_history_df(period, df, events=None) -> None`
- 幂等加载指定周期历史数据。`df` 索引须为 datetime。
- 行为：
  - 同起点、新数据更短 → 跳过。
  - 同起点、新数据更长 → 只追加新增尾部。
  - 起点变化 → 整体替换（若起点变晚会告警早期数据丢失）。
- 不计算指标（指标在 `build_context` 时惰性计算）。

#### `feed_history_df(df, events=None) -> None`
- 灌入**基础周期**历史 K 线。须先完成需求应用，否则 assert 失败。

#### `feed_bar(bar: Bar, events=None) -> None`
- 追加一根基础周期 K 线，仅追加数据不触发计算。

#### `register_period(period: str) -> PeriodData`
- 注册周期（已存在则返回原对象）。

#### `register_indicator(period_name, indicator: IndicatorSpec) -> None`
- 为指定周期注册指标。周期未注册抛 `KeyError`。

### 上下文构建（核心）

#### `build_context(requirements: DataRequirements, bar: Bar) -> BarContext`
- **唯一计算入口**，三阶段：
  1. **构建视图**：对每个需求周期调 `get_data`。
  2. **计算指标**：对每个视图调 `calculate_indicators`，结果统一写回基础周期 DataFrame。
  3. **筛选事件**：按 `requirements.events` 过滤当前 bar 时间窗内的事件。
- `bar.symbol` 与自身不符时告警并忽略该 bar 内容。
- 返回 `BarContext(symbol, bar, multi, events)`。

#### `get_data(period_name, current_time, lookback_bars=1) -> PeriodDataView | None`
- 构建指定周期截止 `current_time` 的只读视图（**只建视图，不算指标**）。
- 基础周期：直接切片返回。
- 高周期：聚合回填 → 切片 → 补充 forming bar（不完整周期）。基础数据为空返回 `None`。
- 周期未注册抛 `KeyError`。

#### `calculate_indicators(view: PeriodDataView, period_name: str) -> None`
- 基于视图窗口数据计算该周期所有已注册指标，结果写回基础周期 DataFrame 并缓存在视图内。
- 单个指标计算异常仅告警，不中断其他指标。

### 查询

| 方法 | 返回 | 说明 |
|---|---|---|
| `get_period(period_name)` | `PeriodData \| None` | 取周期数据容器 |
| `get_period_names()` | `list[str]` | 所有已注册周期名 |
| `get_indicator_names(period_name)` | `list[str]` | 该周期已有指标列名 |
| `get_registered_indicators(period_name)` | `list[IndicatorSpec]` | 该周期注册的指标规格 |
| `get_date_range(period_name)` | `tuple[str, str] \| None` | 该周期数据日期范围 |

### 属性

- `base_period: str | None`（可读写）—— 基础周期名。

### 序列化

- `save_cache() -> None`：回测结束保存缓存；仅当本次由 native 数据构造（非 `loaded_from_cache`）且有缓存目录时写盘。

---

## 3. `BarContext` — 策略上下文（dataclass）

```python
BarContext(
    symbol: str,
    bar: Bar,
    multi: dict[str, PeriodDataView],   # key = 声明的周期名
    events: list[Event],
    aspects: StrategyAspects = StrategyAspects(),   # 切面产生的临时建议/诊断
)
```

- 策略主要通过 `multi[period]` 取视图，再读 K 线/指标。

---

## 4. `PeriodDataView` — 只读逻辑视图

由 `get_data` 产出，**零拷贝**（通过索引范围引用原始 DataFrame），不受后续数据更新影响（Append-Only 保证）。可含一根 forming bar（高周期不完整周期）作为虚拟最后一行。

索引约定：`idx` 支持负索引（相对视图末尾），`-1` 为最后一根（可能是 forming bar）。

### 消费接口

| 方法 | 返回 | 说明 |
|---|---|---|
| `get_bar(idx=-1)` | `Bar \| None` | 按索引取 K 线，越界返回 `None` |
| `close(idx=-1)` | `float \| None` | 取收盘价 |
| `indicator(name, idx=-1)` | `float \| None` | 取指标值（`name` 须含周期前缀）；不触发计算，不存在返回 `None`。`idx=-1` 优先读缓存 |
| `get_events()` | `list[Event]` | 视图时间范围内的事件 |

### 属性

- `current_time: pd.Timestamp`、`period: str`、`length: int`（含 forming bar 的总数）

---

## 5. `PeriodData` — 单周期数据容器

`get_period(...)` 返回的对象。Append-Only，底层 `pd.DataFrame`。

### 方法

| 方法 | 返回 | 说明 |
|---|---|---|
| `append_bar(bar)` | `None` | 追加单根 K 线；时间已存在则静默忽略 |
| `append_bars(bars)` | `None` | 批量追加 |
| `get_data(current_time, lookback_bars=1, events_df=None, base_df_ref=None)` | `PeriodDataView` | 构建只读视图，返回 index <= current_time 的已有数据（current_time 超出已有数据时 ffill 落到最后一根）；`lookback_bars<=0` 抛 `ValueError` |
| `get_indicator(name, idx)` | `float \| None` | 按绝对索引取指标 |
| `set_indicator_column(name, data)` | `None` | 直接写入整列指标 |

### 属性

- `latest_time: pd.Timestamp | None`、`length: int`

---

## 6. 事件

### `Event`（dataclass, kw_only）

```python
Event(
    timestamp: datetime,
    type: str,                 # 'big_trade' | 'news' | 'custom' ...
    symbol: str,
    reason: str = "",
    period: str | None = None, # None=全局事件（所有周期可见）；否则绑定特定周期
    data: Any = None,
)
```

### `BigTradeEvent`（dataclass, kw_only）

```python
BigTradeEvent(..., price: float, volume: float, direction: str)  # direction: 'buy' | 'sell'
```

继承 `Event` 的全部字段。

---

## 7. 内存缓存工具

进程内缓存 `DataFeed`，避免重复 parquet 反序列化与指标计算。缓存键 = symbol + 源数据日期范围。

| 函数 | 说明 |
|---|---|
| `get_cached_feed(symbol, min_dt, max_dt) -> DataFeed \| None` | symbol 与日期范围完全匹配才命中；不匹配自动失效删除 |
| `set_cached_feed(symbol, feed, min_dt, max_dt) -> None` | 存入缓存 |
| `clear_cache() -> None` | 清空所有缓存 |

---

## 8. `Bar` — 标准化 K 线（框架无关）

```python
Bar(
    symbol: str = "",
    datetime: datetime = datetime.min,
    open: float = 0.0,
    high: float = 0.0,
    low: float = 0.0,
    close: float = 0.0,
    volume: float = 0.0,
)
```

定义于 `strategies.core.types`，是 runtime 与桥接层之间的数据交换格式，作为 `feed_bar` / `build_context` 的入参和 `get_bar` 的返回值。
