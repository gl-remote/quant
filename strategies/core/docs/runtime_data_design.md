# 量化策略运行时数据管理方案设计

**文档版本**: 3.0  
**编制日期**: 2026-05-31  
**文档状态**: 定稿（合并 v1 + v2，同步当前实现）  
**修订说明**: 合并前两个版本的设计决策、审计发现与修复记录，更新架构为当前实现路径

---

## 一、概述

### 1.1 核心需求

1. K线数据管理：维护策略运行过程中接收到的K线数据历史
2. 多周期支持：同时管理多个不同周期的K线表格（如1分钟、3分钟、5分钟等）
3. 逐根更新：模拟实盘场景，支持一根一根追加K线（更新对应周期）
4. 指标计算：使用成熟第三方库或内置函数计算指标
5. 事件数据管理：支持事件数据（大单成交、新闻等），与K线、指标一起管理
6. 多策略共享：不同策略可以使用不同周期组合，共享的周期数据和指标只存一份
7. 并发安全：基于条件变量的快照等待，只锁正在更新的周期，之前的数据可以安全读
8. 截止周期镜像：策略只能看到指定周期及之前的数据，不受后面数据干扰
9. 简易实现：优先考虑代码简洁、易理解
10. 回测场景：只考虑几千个周期的回测

### 1.2 现有问题

1. 每个策略自己维护数据缓存（如 `_close_history`）
2. 多个策略回测相同数据时，指标重复计算
3. 没有统一的数据管理接口，每个策略重复实现类似逻辑
4. 不支持多周期数据统一管理
5. 没有事件数据管理

---

## 二、当前架构

### 2.1 目录结构

```
strategies/
├── core/                     # 策略核心（Strategy ABC + 数据类型 + 内置指标）
│   ├── __init__.py           # 导出 CORE_VERSION, Strategy, Bar, Signal, Fill, StrategyPosition
│   ├── base.py               # Strategy ABC + UninitializedStrategy
│   ├── types.py              # Bar, Signal, Fill, StrategyPosition
│   └── indicators.py         # 内置指标计算函数（sma_func, ema_func, rsi_func）
├── runtime/                  # 运行时数据管理（与 core/ 平级）
│   ├── __init__.py           # 统一导出所有运行时类
│   ├── events.py             # Event / BigTradeEvent / NewsEvent + 注册体系（Indicator/Converter）
│   ├── period.py             # PeriodData + PeriodDataView 数据容器
│   ├── requirements.py       # PeriodRequirements, IndicatorRequirements, EventsRequirements, DataRequirements, BarContext
│   ├── data_feed.py          # DataFeed + build_context + 默认指标注册
│   └── cache.py              # DataFeedCache 单例（含 setup 工厂方法）
├── bridges/                  # 框架桥接器
├── utils/                    # 工具函数
└── ma_strategy.py            # 策略实现
```

### 2.2 模块职责

| 模块 | 职责 | 关键导出 |
|------|------|----------|
| `core/__init__.py` | 核心版本号、基类、类型统一导出 | `CORE_VERSION`, `Strategy`, `Bar`, `Signal` |
| `core/base.py` | Strategy 抽象基类 | `Strategy`, `UninitializedStrategy` |
| `core/types.py` | 标准化数据类型 | `Bar`, `Signal`, `Fill`, `StrategyPosition` |
| `core/indicators.py` | 内置指标函数（仅依赖 pandas） | `sma_func`, `ema_func`, `rsi_func` |
| `runtime/events.py` | 事件类型 + 指标/周期转换注册体系 | `Event`, `BigTradeEvent`, `NewsEvent`, `IndicatorCalcMode`, `register_indicator_func` |
| `runtime/period.py` | 单周期数据容器 + 只读逻辑视图 | `PeriodData`, `PeriodDataView` |
| `runtime/requirements.py` | 数据需求声明类型 | `PeriodRequirements`, `IndicatorRequirements`, `EventsRequirements`, `DataRequirements`, `BarContext` |
| `runtime/data_feed.py` | 多周期数据调度 + build_context + 默认指标注册 | `DataFeed`, `build_context` |
| `runtime/cache.py` | DataFeed 全局单例缓存（含 setup 工厂方法） | `DataFeedCache` |

### 2.3 依赖关系

```
core/ （Strategy ABC + 标准化类型 + 内置指标函数）
  └── 无内部依赖，可独立导入

runtime/ （运行时数据管理）
  ├── 依赖 core/types.py（Bar）
  ├── 依赖 core/indicators.py（sma_func, ema_func, rsi_func）
  └── 不依赖 core/base.py（无循环依赖）

策略层（如 ma_strategy.py）
  ├── 依赖 core/base.py（Strategy ABC）
  ├── 依赖 core/types.py（Bar, Signal）
  └── 通过 build_context() 间接使用 runtime/，不直接引用 DataFeedCache
```

**核心原则**：`core/` 不依赖 `runtime/`，`runtime/` 单向依赖 `core/`。这保证了核心模块的最小化和独立性。

---

## 三、核心类设计

### 3.1 Event / BigTradeEvent / NewsEvent

**位置**: `strategies/runtime/events.py`

```python
@dataclass(kw_only=True)
class Event:
    """事件基类

    【设计原则】
    - 与 Bar.datetime 保持一致，使用 datetime 对象
    - 策略层无需关注底层存储细节
    - 内部实现可以自由转换为 pd.Timestamp

    【事件时间作用范围说明】
    - 事件时间戳表示事件发生的具体时间
    - 事件归属：根据时间戳，归属于时间区间包含该时间的 K 线
    - period 字段作用：
      - None：全局事件，所有周期的 K 线都可以看到该事件
      - "1m"：周期特定事件，只在 1m 周期的 K 线中可见
    """
    timestamp: dt  # 事件发生的时间
    type: str  # 'big_trade' | 'news' | 'orderbook_imbalance' | 'custom'
    symbol: str  # 交易品种
    reason: str = ""  # 事件原因/描述，类似 Signal.reason
    period: Optional[str] = None  # None 表示全局事件，否则绑定到特定周期
    data: Any = None

@dataclass(kw_only=True)
class BigTradeEvent(Event):
    """大单成交事件"""
    price: float
    volume: float
    direction: str  # 'buy' | 'sell'

@dataclass(kw_only=True)
class NewsEvent(Event):
    """新闻事件"""
    title: str
    content: Optional[str] = None
    importance: int = 1  # 1-5
```

### 3.2 IndicatorCalcMode / IndicatorFuncInfo / 注册体系

**位置**: `strategies/runtime/events.py`

```python
class IndicatorCalcMode(Enum):
    BATCH = "batch"        # 一次性计算所有数据（默认）
    INCREMENTAL = "incremental"  # 逐行/增量式计算，适合 update_bar 时触发

@dataclass
class IndicatorFuncInfo:
    func: Callable[..., pd.Series]
    calc_mode: IndicatorCalcMode
    name: str
    description: Optional[str] = None

REGISTERED_INDICATOR_FUNCS: Dict[str, IndicatorFuncInfo] = {}

def register_indicator_func(name: str, func: Callable[..., pd.Series],
                            calc_mode: IndicatorCalcMode = IndicatorCalcMode.BATCH,
                            description: Optional[str] = None) -> None:
    """全局注册指标计算函数，所有 DataFeed 共享

    指标计算函数签名要求：
    def indicator_func(df: pd.DataFrame, **params) -> pd.Series

    【指标列名生成规则】
    - 列名格式：{indicator_name}_{param1_value}_{param2_value}_...
    - 参数按参数名称排序，确保参数顺序不影响列名生成
    - 示例：
      - sma(period=10) -> sma_10
      - bbands(period=20, std=2) -> bbands_20_2
      - bbands(std=2, period=20) -> bbands_20_2
    """

def generate_indicator_column_name(name: str, params: Dict[str, Any]) -> str:
    """生成指标列名（按参数名称排序）"""
```

周期转换函数注册体系（同模块）：

```python
REGISTERED_CONVERTERS: Dict[Tuple[str, str], Callable[..., List[Bar]]] = {}

def register_period_converter(source_period: str, target_period: str,
                               func: Callable[..., List[Bar]]) -> None:
    """全局注册周期转换函数"""
```

### 3.3 PeriodData

**位置**: `strategies/runtime/period.py`

#### 设计目标
- 统一管理该周期的 **K线、指标** 两类数据（事件由 `DataFeed` 统一管理）
- 提供逻辑视图，策略只能看到指定时间点之前的数据
- 支持数据追加（Append-Only，历史数据不修改）
- 底层存储使用 Pandas DataFrame
- **两种使用场景**：
  - 场景1：由 `DataFeed` 统一管理（多策略共享）
  - 场景2：策略自己持有（策略私有数据，不共享）

#### 数据结构
```python
class PeriodData:
    # K线数据（OHLCV）+ 指标数据（合并在一起，索引统一为datetime）
    _df: pd.DataFrame
    _latest_time: Optional[pd.Timestamp]  # 最新数据时间
    _period: str  # 周期名称

    # 数据追踪字段（类似数据库表）
    _created_at: pd.Timestamp       # PeriodData 创建时间
    _last_updated_at: pd.Timestamp  # 最后一次更新时间
    _update_count: int              # 更新次数

    # 指标计算状态跟踪
    _calculated_indicators: Set[str]           # 已计算的指标列名
    _indicator_last_calc_idx: Dict[str, int]   # 指标最后计算到的行索引
```

#### 核心方法
```python
def __init__(self, period: str): ...
def append_bars(self, bars: List[Bar]) -> None: ...
def append_bar(self, bar: Bar) -> None: ...
def append_indicators(self, indicators: pd.DataFrame) -> None: ...

# --- 视图方法 ---
def get_data(self, current_time: Union[pd.Timestamp, dt], lookback_bars: int = 1,
             events_df: Optional[pd.DataFrame] = None) -> PeriodDataView: ...

# --- 数据访问方法 ---
def get_bar(self, idx: int) -> Optional[Bar]: ...
def get_bar_by_time(self, time: Union[pd.Timestamp, dt]) -> Optional[Bar]: ...
def get_indicator(self, name: str, idx: int) -> Optional[float]: ...
def get_indicator_series(self, name: str) -> pd.Series: ...

# --- 指标计算状态管理 ---
def is_indicator_calculated(self, name: str) -> bool: ...
def get_indicator_last_calc_idx(self, name: str) -> Optional[int]: ...
def mark_indicator_calculated(self, name: str, last_idx: Optional[int] = None) -> None: ...
def clear_indicator_calculation(self, name: Optional[str] = None) -> None: ...

# --- 封装对 _df 的访问 ---
def apply_indicator(self, func: Callable[..., pd.Series], **params: Any) -> pd.Series: ...
def set_indicator_column(self, name: str, series: pd.Series) -> None: ...

# --- 属性 ---
@property
def latest_time(self) -> Optional[pd.Timestamp]: ...
@property
def length(self) -> int: ...
@property
def period(self) -> str: ...
```

### 3.4 PeriodDataView

**位置**: `strategies/runtime/period.py`

#### 设计目标
- 只读逻辑视图，防止策略修改数据
- 只包含截止指定时间点和指定历史K线范围的数据
- 不受后续数据更新影响（Append-Only 保证）
- 高效实现：通过索引范围访问原始数据，**不复制数据**
- **纯只读，不触发任何计算**，指标不存在返回 None

#### 数据结构
```python
class PeriodDataView:
    _df_ref: pd.DataFrame          # 对原始 DataFrame 的引用（不复制数据）
    _events_ref: pd.DataFrame      # 对原始事件数据的引用（不复制数据）
    _start_idx: int                # 视图的起始索引（包含）
    _end_idx: int                  # 视图的结束索引（包含）
    _current_time: pd.Timestamp    # 视图的截止时间
    _period: str                   # 周期名称
```

#### 核心方法
```python
def __init__(self, df_ref: pd.DataFrame, events_ref: Optional[pd.DataFrame],
             start_idx: int, end_idx: int, current_time: pd.Timestamp, period: str): ...

# --- 数据访问 ---
def get_bar(self, idx: int = -1) -> Optional[Bar]: ...
def get_indicator(self, name: str, idx: int = -1) -> Optional[float]: ...
def get_events(self) -> List[Event]: ...
def get_all_bars(self) -> pd.DataFrame: ...

# --- 便捷访问器 ---
def bar(self, idx: int = -1) -> Bar | None: ...
def close(self, idx: int = -1) -> float | None: ...
def indicator(self, name: str, idx: int = -1) -> float | None: ...
def indicator_series(self, name: str) -> pd.Series: ...
def events(self) -> List[Event]: ...

# --- 属性 ---
@property
def current_time(self) -> pd.Timestamp: ...
@property
def length(self) -> int: ...
@property
def period(self) -> str: ...
```

### 3.5 DataFeed

**位置**: `strategies/runtime/data_feed.py`

#### 设计目标
- 管理单个品种（symbol）的所有周期数据
- 提供统一的 `update_bar` 入口，调度所有相关计算
- 基于条件变量的快照等待机制（只在 `DataFeed` 级别加锁）
- 统一管理 K线、指标、事件 三类数据
- 支持周期转换（从1m数据衍生出5m数据，基础设施就绪，当前实现为 no-op）
- 回测前统一注册所有指标，避免实时计算的不同步问题

#### 数据结构
```python
class DataFeed:
    symbol: str  # 交易品种，如 "btc_usdt" 或 "CZCE.sr509"
    source: Optional[str] = None  # 数据源标识（从symbol解析或传入）

    _periods: Dict[str, PeriodData]  # key: 周期名，value: PeriodData

    _events: pd.DataFrame  # 事件数据，包含可选的 period 字段

    # 并发控制
    _lock: threading.RLock
    _updating_time: pd.Timestamp | NaTType  # 正在更新的时间，用于视图安全检查
    _condition: threading.Condition

    # 指标注册配置
    _registered_indicators: Dict[str, List[Tuple[str, Dict[str, Any]]]]

    # 周期转换配置
    _period_conversions: Dict[Tuple[str, str], Callable]
    _derived_periods: Dict[str, str]

    # 数据追踪字段
    _created_at: pd.Timestamp
    _last_updated_at: pd.Timestamp
    _update_count: int
    _event_count: int
```

#### 核心方法
```python
def __init__(self, symbol: str, source: Optional[str] = None): ...
def register_period(self, period: str) -> PeriodData: ...
def register_indicator(self, period_name: str, indicator_name: str, **params: Any) -> None: ...
def load_history_data(self, period: str, bars: List[Bar], events: Optional[List[Event]] = None) -> None: ...
def append_event(self, event: Event) -> None: ...
def append_events(self, events: List[Event]) -> None: ...
def get_events(self, start_time=None, end_time=None, event_type=None, period=None) -> List[Event]: ...
def get_events_at_bar(self, bar_time, period) -> List[Event]: ...

def update_bar(self, bar: Bar, period: str, events: Optional[List[Event]] = None) -> None:
    """核心方法，线程安全
    执行流程：
    1. 锁定并记录当前正在更新的时间
    2. 更新对应周期的 PeriodData（追加K线 + 可选事件）
    3. 检查是否触发周期转换
    4. 清除正在更新的时间标记，通知等待线程
    """

def _check_period_conversion(self, source_period: str) -> None:
    """周期转换检查（当前为简化实现，基础设施就绪但未启用）"""

def _calculate_indicators_for_period(self, period_name: str) -> None: ...
def calculate_all(self) -> None: ...
def get_period(self, period_name: str) -> Optional[PeriodData]: ...

def get_data(self, period_name: str, current_time, lookback_bars: int = 1,
             timeout: Optional[float] = None) -> Optional[PeriodDataView]:
    """策略主要访问入口
    并发安全 + 懒加载指标计算 + 构造视图
    """
```

### 3.6 DataFeedCache（单例 + setup 工厂方法）

**位置**: `strategies/runtime/cache.py`

#### 设计目标
- 单例模式，全局唯一入口
- 管理多个 `DataFeed` 实例，按 symbol 区分
- 支持策略测试时注入 mock 的 cache
- 有自己的锁，保护 `get_or_create` 操作
- 只做路由，实际数据操作委托给 `DataFeed`

#### 核心签名
```python
class DataFeedCache:
    _instance: Optional['DataFeedCache'] = None

    def __init__(self): ...
    @classmethod
    def get_instance(cls) -> 'DataFeedCache': ...
    @classmethod
    def set_instance(cls, instance: Optional['DataFeedCache']) -> None: ...
    def get_or_create(self, symbol: str, source: Optional[str] = None) -> DataFeed: ...
    def update_bar(self, symbol: str, bar: Bar, period_name: str, events=None) -> None: ...
    def get_data(self, symbol: str, period_name: str, current_time, lookback_bars=1, timeout=None) -> Optional[PeriodDataView]: ...

    def setup(self, symbol: str, requirements: DataRequirements) -> DataFeed:
        """按策略的数据需求声明配置 DataFeed

        回测引擎只需调用一次此方法，即可完成周期注册和指标注册。
        """
```

### 3.7 Requirements 类

**位置**: `strategies/runtime/requirements.py`

```python
@dataclass
class PeriodRequirements:
    """单个周期的数据需求（类比表的查询需求）"""
    lookback_bars: int           # 查询的历史K线数量（最近N个周期）
    min_bars: Optional[int] = None  # 策略需要的最小K线数（可选，用于校验）

@dataclass
class IndicatorRequirements:
    """单个指标的计算需求"""
    name: str                    # 指标名
    params: Dict[str, Any]       # 指标参数

@dataclass
class EventsRequirements:
    """事件数据需求"""
    include_global_events: bool = False    # 是否需要全局事件（period=None）
    include_period_events: List[str] = field(default_factory=list)  # 周期名列表，"*"表示所有
    event_types: List[str] = field(default_factory=list)  # 事件类型白名单

    @classmethod
    def all_events(cls) -> 'EventsRequirements': ...
    @classmethod
    def no_events(cls) -> 'EventsRequirements': ...

@dataclass
class DataRequirements:
    """策略的数据需求（类比数据库查询计划）
    - DataFeed ≈ 数据库（Database），用 symbol + source 作为唯一标识
    - PeriodData ≈ 数据表（Table），用 period 作为唯一标识
    """
    periods: Dict[str, PeriodRequirements]                          # key=周期名
    indicators: Dict[str, List[IndicatorRequirements]]              # key=周期名
    events: EventsRequirements = field(default_factory=EventsRequirements.no_events)
```

### 3.8 BarContext

**位置**: `strategies/runtime/requirements.py`

```python
@dataclass
class BarContext:
    """当前 bar 的策略上下文——引擎按 data_requirements 声明构造"""
    symbol: str
    bar: Bar
    multi: Dict[str, PeriodDataView]   # key=周期名，集合=data_requirements中声明的周期
    events: List[Event]                # 当前 bar 时间范围内的事件
```

### 3.9 build_context 辅助函数

**位置**: `strategies/runtime/data_feed.py`

```python
def build_context(
    data_feed: DataFeed,
    requirements: DataRequirements,
    current_time: Union[pd.Timestamp, dt],
    timeout: Optional[float] = None
) -> BarContext:
    """构造 BarContext 上下文对象

    行为：
    1. 解析 requirements 中的 periods 配置
    2. 对每个周期调用 data_feed.get_data(period, current_time, lookback_bars, timeout)
    3. 从 DataFeed 获取当前时间范围内的事件（按 requirements.events 配置筛选）
    4. 构造并返回 BarContext 对象
    """
```

---

## 四、设计决策

### 4.1 为什么 runtime/ 与 core/ 平级而不是子模块

**背景**：v1 设计为单文件 `strategies/core/data_feed.py`，v2 重构为独立子包。

**决策过程**：
- `runtime/` 只负责运行时内存数据编排（DataFeed/PeriodData/Event）
- `core/` 保持最小化，只包含 Strategy ABC 和标准化类型
- 避免与根目录 `data/`（离线存储层）混淆
- 无循环依赖：`runtime/` -> `core/types.py`（单向）

**最终方案**：`runtime/` 作为 `core/` 的**平级兄弟模块**，两者都位于 `strategies/` 下。策略通过 `strategies.__init__` 的统一导出访问，不关心内部目录结构。

### 4.2 为什么单文件被拆分为5个模块

| 模块 | 拆分原因 |
|------|----------|
| `events.py` | Event 类型+注册体系是纯数据定义，独立变化，方便在 PeriodData 和 DataFeed 之间共享 |
| `period.py` | PeriodData+PeriodDataView 是核心数据容器，约 500 行，单独文件清晰 |
| `requirements.py` | 策略需求声明类型是独立的 API 契约，与数据容器无依赖 |
| `data_feed.py` | DataFeed 是多周期调度逻辑，包含 update_bar 核心流程和 build_context 编排 |
| `cache.py` | DataFeedCache 是全局单例，负责生命周期管理，独立于 DataFeed 的业务逻辑 |

### 4.3 Append-Only 数据模型

**决策**：所有数据采用 Append-Only（只追加不修改）模式。

**理由**：
- 历史数据一旦写入就不会被修改，保证了快照的一致性
- 多个策略并发读历史数据时无需加锁
- 简化了并发安全模型：只需要保护正在写入的尾部数据
- Pandas concat 在几千周期量级下性能可接受

### 4.4 Lazy 指标计算

**决策**：指标在 `DataFeed.get_data()` 调用时触发计算，而不是在 `update_bar()` 时立即计算。

**理由**：
- 避免无用计算：如果某个指标从未被访问，就不需要计算
- 多策略共享：第一个策略访问时计算，后续策略直接复用
- 回测前可通过 `calculate_all()` 预计算，兼顾性能
- 计算粒度：BATCH 模式全量计算，INCREMENTAL 模式增量计算

**触发点明确**：指标计算的触发点是 `DataFeed.get_data()`（或 `build_context()`），而非 `PeriodDataView.get_indicator()`。`PeriodDataView` 是纯只读，不触发任何计算。

### 4.5 Condition Variable 线程安全

**决策**：基于条件变量的时间检查机制（只在 `DataFeed` 级别加锁）。

**设计细节**：
- `DataFeed._lock: threading.RLock` 保护所有写操作（`update_bar`）
- `DataFeed._updating_time` 标记正在更新的时间戳
- `DataFeed._condition: threading.Condition` 用于等待/通知
- `get_data()` 检查 `current_time` 是否小于 `_updating_time`
  - 如果安全（无更新或 current_time 在更新时间之前）：直接返回视图
  - 如果不安全且 `timeout=None`（回测模式）：抛出 ValueError
  - 如果不安全且 `timeout>0`（实盘模式）：等待更新完成
  - 如果不安全且 `timeout=0`（非阻塞）：立即抛出异常

### 4.6 `_updating_time` NaTType + epoch sentinel 修复

**决策**：使用 `pd.Timestamp(0)`（epoch 起始时间）作为"没有正在进行的更新"的哨兵值。

**背景**：初始设计使用 `Optional[pd.Timestamp]`，`None` 表示无更新。但在时间比较时，`None` 与 `pd.Timestamp` 的比较行为不可预测，导致条件判断异常。

**修复**：
```python
# 当前实现
self._updating_time: pd.Timestamp | NaTType = pd.Timestamp(0)
# 无更新时设置为 pd.Timestamp(0)，更新时设置为 bar 的时间戳
# update_bar 结束时重置为 pd.Timestamp(0)
self._updating_time = pd.Timestamp(0)
```

**比较逻辑**：
```python
if self._updating_time != pd.Timestamp(0):
    if current_time_ts >= self._updating_time:
        # 冲突处理
        ...
```

### 4.7 周期转换（intentionally no-op，基础设施就绪）

**决策**：周期转换的**基础设施已经完成**（`_period_conversions`、`_derived_periods`、`REGISTERED_CONVERTERS` 都已定义），但转换逻辑本身 `_check_period_conversion()` 当前为 `pass`（no-op）。

**理由**：
- 当前第一期实现只处理显式注册的周期（如 1m 和 5m 都从外部数据源加载）
- 周期转换需要明确的时间对齐规则（见 7.4 节时间对齐规则）
- 基础设施预留了扩展点，后续可以按需实现
- 当前 `_period_conversions` 从 `REGISTERED_CONVERTERS` 拷贝，但未注册任何实际转换器

### 4.8 封装对 `_df` 的访问（apply_indicator / set_indicator_column）

**决策**：PeriodData 提供 `apply_indicator()` 和 `set_indicator_column()` 作为对 `_df` 的受控访问接口。

**理由**：
- 避免外部代码直接操作 `_df` 私有属性
- 统一指标计算结果的写入路径
- 方便将来在写入时添加校验、日志或变更跟踪

---

## 五、审计发现与修复

### 5.1 缺陷1：事件归属的架构矛盾

**位置**: v1 3.2 节 PeriodData 持有 `_events` DataFrame vs Q4 "事件在 DataFeed 级别统一管理"

**问题描述**: PeriodData 内部数据结构包含 `_events: pd.DataFrame`，但 Q4 说"事件在 DataFeed 级别统一管理"，两者矛盾。

**最终方案**: ✅ **已修复**
- 从 PeriodData 中移除 `_events` 属性
- 在 DataFeed 中管理 `_events: pd.DataFrame`
- `Event` 基类新增可选的 `period: Optional[str] = None` 字段
- `PeriodDataView` 通过构造时传入的 `events_ref` 获取事件，不持有 PeriodData 引用
- 事件分为全局事件（`period=None`）和周期特定事件（`period="1m"`等）

---

### 5.2 缺陷2：API 参数命名和语义问题

**位置**: PeriodData.get_data 参数命名

**问题描述**: `end_time` 不符合使用者视角，`periods` 语义模糊（K线根数 vs 时间单位）。

**最终方案**: ✅ **已修复**
- `end_time` -> `current_time`（从使用者视角，这是当前时间）
- `periods` -> `lookback_bars`（明确为"往前多少根K线"）
- `lookback_bars <= 0` 时抛出 ValueError
- `lookback_bars` 大于现有数据长度时返回所有可用数据

---

### 5.3 缺陷3：API 设计问题（快照实现方案）

**位置**: DataFeed.get_data vs Q1 并发机制

**问题描述**:
1. 方法名 `get_data` 暴露底层实现细节
2. 缺乏超时/等待机制
3. 快照实现需明确为逻辑视图

**最终方案**: ✅ **已修复**
- 保持方法名 `get_data`（已足够清晰）
- 增加 `timeout: Optional[float] = None` 参数
  - `None`：回测模式，直接抛错
  - `>0`：实盘模式，等待更新完成
  - `0`：非阻塞模式
- 快照通过逻辑视图实现（索引范围引用，不复制数据）
- `PeriodDataView` 保存对原始 DataFrame 的引用，不产生副本

---

### 5.4 缺陷4：build_context 函数未定义

**位置**: v1 多次使用 `build_context()` 但无定义

**问题描述**: 核心数据流中最关键的编排函数没有签名和定义。

**最终方案**: ✅ **已修复**
- 在 `strategies/runtime/data_feed.py` 中定义了 `build_context()` 模块级函数
- 完整实现了其行为：解析 requirements -> 获取多周期视图 -> 筛选事件 -> 构造 BarContext

---

### 5.5 缺陷5：BATCH 模式指标重复计算 + 数据一致性问题

**位置**: v1 Q3 BATCH 模式与 calculate_all 行为重叠

**问题描述**: BATCH 模式指标"第一次访问时全量计算"，`calculate_all()` 也是全量计算，两者行为重叠。指标计算是在完整 DataFrame 还是 sliced DataFrame 上执行未明确。

**最终方案**: ✅ **已修复**
- BATCH 模式指标始终在完整的 `PeriodData._df` 上计算
- 数据访问通过逻辑视图（时间戳/索引范围），不复制数据，不触发重新计算
- `calculate_all()` 跳过已计算的指标（通过 `is_indicator_calculated()` 检查）
- 指标函数接收完整 DataFrame，不应假设数据范围

---

### 5.6 缺陷6：周期转换时间对齐规则未定义

**位置**: v1 Q2 "自动检查是否可以聚合"逻辑不完整

**问题描述**: 未定义时间窗口规则、K线时间戳含义、OHLCV聚合规则、非标准交易时间处理。

**最终方案**: ✅ **已修复（文档层面）**，当前实现为 no-op，详细规则记录在 7.4 节

---

### 5.7 缺陷7：时间类型设计不一致

**位置**: Event.timestamp 使用 pd.Timestamp 与 Bar.datetime 使用 datetime.datetime 不一致

**问题描述**: 违反了"使用者无需关注底层数据结构"原则。

**最终方案**: ✅ **已修复**
- Event.timestamp 改为 `datetime.datetime`（与 Bar.datetime 一致）
- 所有对外的 API 时间参数标注为 `Union[pd.Timestamp, dt]`
- 内部统一转换为 `pd.Timestamp` 处理

---

### 5.8 缺陷8：指标懒加载写回机制未定义

**位置**: v1 Q3 + 模糊4

**问题描述**: 视图触发计算需要持有 PeriodData 引用，破坏了只读性；如果只在视图上计算，其他策略无法复用。

**最终方案**: ✅ **已修复**
- 指标计算的触发点明确为 `DataFeed.get_data()`（或 `build_context()`）
- `PeriodDataView` 是**纯只读**逻辑视图，不持有对 PeriodData 的引用
- 计算结果持久化到 `PeriodData._df`，后续策略可以复用
- PeriodDataView.get_indicator() 不触发任何计算，指标不存在返回 None

---

### 5.9 模糊1：多策略场景下的调度顺序

**位置**: v1 模糊1

**问题描述**: 多策略共享 DataFeed 时，update_bar / get_data / on_bar 的调用顺序未明确。

**最终方案**: ✅ **已修复（文档层面）**
- Engine 按固定顺序执行：update_bar -> 为每个策略构造 BarContext -> 调用 on_bar
- 策略不调用 update_bar，数据更新由框架/Engine 统一完成
- 策略之间不应有依赖关系，假设独立决策

---

### 5.10 模糊2：指标列名生成规则不完整

**位置**: v1 模糊2

**问题描述**: `sma(period=10) -> sma_10` 只覆盖了单参数场景，多参数或不同参数顺序可能产生不同列名。

**最终方案**: ✅ **已修复**
- 在 `register_indicator_func` 的 docstring 中明确定义列名生成规则
- 实现中按参数名称排序，确保参数顺序不影响列名
- `generate_indicator_column_name()` 函数已实现

---

### 5.11 模糊3：事件归属K线的时间范围规则

**位置**: v1 模糊3

**问题描述**: 事件归属的匹配规则未定义。

**最终方案**: ✅ **已修复（文档层面）**
- K线时间戳表示周期开始时间，周期持续时间由周期名称决定
- K线时间区间为 `[bar.datetime, bar.datetime + period_duration)`
- 事件时间戳落在该区间内即归属于该K线
- 类别：全局事件（`period=None`）和周期特定事件（`period="1m"`等）

---

### 5.12 模糊4：数据视图的 get_indicator 能否触发计算

**位置**: v1 模糊4

**问题描述**: 视图的 `get_indicator` 能否触发计算未明确。

**最终方案**: ✅ **已修复**
- 明确视图是**纯只读**，不触发任何计算
- 数据交付流程保证：更新K线 -> 确保计算完成 -> 最后交付视图
- 策略拿到视图时，计算已经完成
- 指标不存在返回 None

---

### 5.13 模糊5：data_requirements 格式语义

**位置**: v1 模糊5

**问题描述**: 早期使用 dict 格式、bars 字段语义不明确。

**最终方案**: ✅ **已修复**
- 完整定义了结构化类型：`PeriodRequirements`、`IndicatorRequirements`、`DataRequirements`
- `lookback_bars` 表示 `get_data` 的 `lookback_bars` 参数
- `min_bars` 表示策略需要的最小 K线数（可选校验）

---

### 5.14 模糊6：data_requirements 中没有事件声明入口

**位置**: v1 模糊6

**问题描述**: data_requirements 只有 periods 和 indicators，缺少事件配置。

**最终方案**: ✅ **已修复**
- 新增 `EventsRequirements` 类型，支持精细的事件筛选
- `DataRequirements.events` 字段支持 5 种场景：
  - 不获取事件
  - 只获取全局事件
  - 获取全局+特定周期事件
  - 获取所有事件
  - 获取特定类型事件

---

### 5.15 模糊7：INCREMENTAL 模式输入范围未定义

**位置**: v1 模糊7

**问题描述**: INCREMENTAL 模式下计算函数收到什么输入未定义。

**最终方案**: ✅ **已修复（文档层面）**
- INCREMENTAL 模式函数签名：
  ```python
  def incremental_indicator_func(df: pd.DataFrame, last_calc_idx: Optional[int], **params) -> pd.Series
  ```
- `last_calc_idx` 表示上次计算结束的位置（包含），增量只需计算其后到当前末尾
- 返回完整的指标 Series（长度与 df 相同）

---

### 5.16 模糊8：mock_snapshot 测试构造缺少便利工具

**位置**: v1 模糊8

**问题描述**: 测试示例中使用 `mock_view` 但没有提供构造方法。

**最终方案**: ✅ **已修复**
- 设计了 `make_view()` 测试辅助函数（在 `tests/test_data_feed.py` 中实现为测试 helper）

---

### 5.17 审计问题1：并发安全设计缺陷（高风险）

**位置**: DataFeedCache 设计

**问题描述**: DataFeedCache.get_or_create 缺少锁保护，多线程场景下可能出现同时创建同一 symbol 的多个 DataFeed 实例。

**修复方案**: ✅ **已修复**
- DataFeedCache 添加 `_lock: threading.RLock` 字段
- `get_or_create` 方法中使用 `with self._lock` 保护

---

### 5.18 审计问题2：指标计算触发时机不明确（中风险）

**位置**: PeriodData 设计

**问题描述**: 缺少指标计算状态跟踪机制。

**修复方案**: ✅ **已修复**
- 添加 `_calculated_indicators: Set[str]`
- 添加 `_indicator_last_calc_idx: Dict[str, int]`
- 新增管理方法：`is_indicator_calculated`、`get_indicator_last_calc_idx`、`mark_indicator_calculated`、`clear_indicator_calculation`

---

### 5.19 审计问题3：周期转换触发逻辑不完整（中风险）

**位置**: DataFeed 设计

**问题描述**: 缺少周期转换关系存储结构。

**修复方案**: ✅ **已修复（基础设施就绪）**
- 添加 `_period_conversions: Dict[Tuple[str, str], Callable]`
- 添加 `_derived_periods: Dict[str, str]`
- `_check_period_conversion()` 目前为 pass，基础设施就绪待启用

---

### 5.20 审计问题4：向后兼容性问题（中风险）

**位置**: Strategy 基类设计

**问题描述**: 原方案"直接改，不做旧签名兜底"。

**修复方案**: ✅ **已修复**
- `data_requirements()` 改为可选方法，默认返回 `None`
- `on_bar()` 的 `ctx` 参数改为可选，默认 `None`
- 返回 `None` 表示策略不使用新的数据管理系统

---

### 5.21 审计问题5：依赖缺失检查（低风险）

**位置**: pyproject.toml

**问题描述**: 方案使用 pandas-ta，但 pyproject.toml 中没有声明。

**说明**: ✅ **已确认**
- 当前实现使用 `core/indicators.py` 内置函数（sma_func, ema_func, rsi_func），无需 pandas-ta
- 如需 pandas-ta 扩展，需在 pyproject.toml 添加依赖

---

### 5.22 架构合理性评估

| 评估项 | 评分 | 说明 |
|--------|------|------|
| 职责分离 | ✅ 优秀 | DataFeed 调度、PeriodData 存储，分工清晰 |
| 可扩展性 | ✅ 良好 | 支持多周期、多策略、事件机制 |
| 可测试性 | ✅ 良好 | 支持 mock 注入，声明式需求便于测试 |
| 性能考虑 | ⚠️ 一般 | Pandas concat 性能在大数据量下可能有问题 |
| 并发安全 | ✅ 良好 | DataFeedCache 已添加锁，保护 get_or_create |
| 向后兼容 | ✅ 优秀 | Strategy 接口保持向后兼容 |

---

## 六、实施状态

### 6.1 已完全实现

1. **PeriodData**（`strategies/runtime/period.py`）：数据容器完整实现，包括 append、视图、指标状态管理
2. **PeriodDataView**（`strategies/runtime/period.py`）：只读逻辑视图完整实现，包括便捷访问器（bar/close/indicator/indicator_series/events）
3. **Event 类型**（`strategies/runtime/events.py`）：Event/BigTradeEvent/NewsEvent 完整实现
4. **注册体系**（`strategies/runtime/events.py`）：register_indicator_func、register_period_converter、列名生成函数完整实现
5. **DataFeed**（`strategies/runtime/data_feed.py`）：多周期调度完整实现，含 update_bar、get_data（并发安全）、calculate_all
6. **DataFeedCache**（`strategies/runtime/cache.py`）：单例完整实现，含 setup 工厂方法
7. **Requirements 类型**（`strategies/runtime/requirements.py`）：所有需求类型完整实现
8. **BarContext**（`strategies/runtime/requirements.py`）：策略上下文完整实现
9. **build_context**（`strategies/runtime/data_feed.py`）：上下文构造函数完整实现
10. **默认指标注册**（`strategies/runtime/data_feed.py` 底部）：sma/ema/rsi 三个内置指标自动注册
11. **内置指标函数**（`strategies/core/indicators.py`）：sma_func/ema_func/rsi_func 完整实现

### 6.2 基础设施就绪但未启用

1. **`_check_period_conversion()`**：方法已定义，`_period_conversions` 从 `REGISTERED_CONVERTERS` 拷贝，`_derived_periods` 已初始化，但转换逻辑为 `pass`。需要时只需实现转换函数并注册到 `REGISTERED_CONVERTERS`，然后修改 `_check_period_conversion` 即可。
2. **`period` 参数在 `get_events` 和 `get_events_at_bar` 中**：事件筛选的 period 逻辑已实现（按 period 列筛选），但事件归因于精确K线时间区间的逻辑（`get_events_at_bar`）使用简化实现（仅按 end_time）。

### 6.3 与原始设计的变化

1. **`make_view` 测试辅助工具**：原设计文档中定义在 `tests/` 中，实际实现为测试 helper（`tests/test_data_feed.py`），在数据流测试中使用直接构造 PeriodDataView 的方式。
2. **`IndicatorFuncInfo` 新增 `name` 和 `description` 字段**：比原始设计多出这两个字段，便于调试和文档生成。
3. **`generate_indicator_column_name` 按参数名排序**：原始设计按函数定义参数列表排序，实际实现改为按参数名称排序，更稳健。
4. **`BarContext.bar` 在 `build_context` 中自动构造**：从第一个周期的视图中取最新 Bar，并设置 symbol。简化了 Engine 的调用。
5. **`DataFeedCache.setup` 工厂方法**：是原始设计之外新增的方法，大幅简化了回测引擎的初始化代码。

---

## 七、使用指南

### 7.1 Engine 设置流程

```python
# 1. 获取全局 Cache
cache = DataFeedCache.get_instance()

# 2. 按策略声明一键配置 DataFeed（setup 工厂方法）
data_feed = cache.setup("CZCE.sr509", strategy.data_requirements())

# 3. 加载历史数据
data_feed.load_history_data("1m", bars_1m, events_1m)
data_feed.load_history_data("5m", bars_5m, events_5m)

# 4. 可选：预计算指标
# data_feed.calculate_all()
```

### 7.2 策略声明示例

```python
class MaStrategyCore(Strategy[MACrossParams]):

    name = STRATEGY_MA
    VERSION = f"{CORE_VERSION}-ma1"

    def data_requirements(self) -> DataRequirements:
        return DataRequirements(
            periods={
                "5m": PeriodRequirements(lookback_bars=50),
                "1m": PeriodRequirements(lookback_bars=20),
            },
            indicators={
                "5m": [
                    IndicatorRequirements(name="sma", params={"period": 10}),
                    IndicatorRequirements(name="sma", params={"period": 20}),
                ],
            },
            events=EventsRequirements.no_events(),
        )

    def on_bar(self, bar: Bar, ctx: BarContext) -> Signal:
        sma10 = ctx.multi["5m"].indicator("sma_10", -1)
        sma20 = ctx.multi["5m"].indicator("sma_20", -1)
        ...
```

### 7.3 回测运行循环

```python
# Bridge 遍历主周期数据
for bar, events in zip(bars_1m, event_groups):
    # 1. K线落地（先 update_bar，让跨周期数据就绪）
    cache.update_bar("CZCE.sr509", bar, "1m", events)

    # 2. 构造上下文
    ctx = build_context(
        data_feed, strategy.data_requirements(), bar.datetime
    )

    # 3. 调用策略
    signal = strategy.on_bar(bar, ctx)

    # 4. 执行下单
    bridge.execute(signal, bar)
```

### 7.4 测试示例

```python
def test_strategy():
    ctx = BarContext(symbol="m2509", bar=test_bar,
                     multi={"5m": mock_view, "1m": mock_view},
                     events=[])
    signal = strategy.on_bar(test_bar, ctx)
    assert signal.action == TRADE_ACTION_BUY
```

不需要 mock 全局 cache，不需要 set_instance，构造 BarContext 直接喂即可。

### 7.5 数据访问链路

```
DataFeedCache（symbol -> DataFeed）
    |
    v
DataFeed（period -> PeriodData）
    |
    v
build_context() -> BarContext（按声明裁剪）
    |
    v
Strategy.on_bar(bar, ctx)

策略不再感知 DataFeedCache 的存在：
bar, ctx -> on_bar() -> Signal
```

---

## 八、关键类型签名附录

### 8.1 模块导出总览

从 `strategies/runtime/__init__.py` 导出的所有类型：

| 类型 | 来源模块 | 说明 |
|------|----------|------|
| `Event` | `events.py` | 事件基类 |
| `BigTradeEvent` | `events.py` | 大单成交事件 |
| `NewsEvent` | `events.py` | 新闻事件 |
| `IndicatorCalcMode` | `events.py` | 指标计算模式枚举 |
| `IndicatorFuncInfo` | `events.py` | 指标函数信息 dataclass |
| `register_indicator_func` | `events.py` | 注册指标计算函数 |
| `register_period_converter` | `events.py` | 注册周期转换函数 |
| `PeriodData` | `period.py` | 单周期数据容器 |
| `PeriodDataView` | `period.py` | 只读逻辑视图 |
| `PeriodRequirements` | `requirements.py` | 周期数据需求 |
| `IndicatorRequirements` | `requirements.py` | 指标计算需求 |
| `EventsRequirements` | `requirements.py` | 事件数据需求 |
| `DataRequirements` | `requirements.py` | 策略数据需求汇总 |
| `BarContext` | `requirements.py` | 策略上下文 |
| `DataFeed` | `data_feed.py` | 多周期数据调度器 |
| `DataFeedCache` | `cache.py` | 全局单例缓存 |
| `build_context` | `data_feed.py` | 上下文构造函数 |

### 8.2 并发安全签名细节

```python
# DataFeed.update_bar 核心签名
def update_bar(self, bar: Bar, period: str,
               events: Optional[List[Event]] = None) -> None:
    """全程持有 self._lock，通过 _condition.notify_all() 通知等待线程"""

# DataFeed.get_data 并发安全签名
def get_data(self, period_name: str,
             current_time: Union[pd.Timestamp, dt],
             lookback_bars: int = 1,
             timeout: Optional[float] = None) -> Optional[PeriodDataView]:
    """通过 _lock + _updating_time + _condition 实现并发安全"""
```

### 8.3 指标计算关键方法

```python
# DataFeed._calculate_indicators_for_period
# 遍历 _registered_indicators，调用 period_data.apply_indicator + set_indicator_column
# 通过 is_indicator_calculated 跳过已计算的指标

# PeriodData.apply_indicator
def apply_indicator(self, func: Callable[..., pd.Series],
                    **params: Any) -> pd.Series:
    return func(self._df, **params)

# PeriodData.set_indicator_column
def set_indicator_column(self, name: str, series: pd.Series) -> None:
    self._df[name] = series
```

### 8.4 默认注册的内置指标

```python
# 在 strategies/runtime/data_feed.py 模块加载时自动注册
register_indicator_func('sma', sma_func, IndicatorCalcMode.BATCH,
                        description='简单移动平均线')
register_indicator_func('ema', ema_func, IndicatorCalcMode.BATCH,
                        description='指数移动平均线')
register_indicator_func('rsi', rsi_func, IndicatorCalcMode.BATCH,
                        description='相对强弱指标')
```

---

## 附录 A：术语表

| 术语 | 说明 |
|------|------|
| PeriodData | 单个周期的数据容器，存储K线和指标 |
| DataFeed | 单个品种的多周期数据管理器，调度计算、管理事件 |
| DataFeedCache | 全局单例缓存，管理多个DataFeed实例 |
| PeriodDataView | 只读逻辑视图，不复制数据，不触发计算 |
| Event | 事件数据类型，支持全局事件和周期特定事件 |
| DataRequirements | 策略的数据需求声明 |
| BarContext | 策略on_bar时接收的上下文，包含多周期数据和事件 |
| Append-Only | 只追加不修改的数据模式，保证历史数据一致性 |
| BATCH模式 | 指标一次性全量计算的模式 |
| INCREMENTAL模式 | 指标逐行/增量计算的模式 |
| build_context | 根据 DataRequirements 构造 BarContext 的编排函数 |
| setup | DataFeedCache 的工厂方法，按 DataRequirements 配置 DataFeed |

---

## 附录 B：周期转换时间对齐规则（备查）

以下规则已在文档层面定义，为周期转换实现提供完整规范：

- **K线时间戳定义**：所有 K线的时间戳表示**周期开始时间**（如 09:30 表示 09:30-09:31 的 1m K线）
- **时间窗口规则**：周期转换采用**时间窗口聚合**，而非简单按根数聚合
- **窗口范围**：时间窗口采用**左闭右开**规则，即 `[T, T+period)`，包含起始时间，不包含结束时间
- **1m -> 5m 示例**：
  - 窗口起始时间 T 为 5分钟对齐的时间（09:30, 09:35, 09:40 等）
  - 窗口范围 `[09:30, 09:35)`，聚合该窗口内所有 1m K线
  - 聚合后的 5m K线时间戳取窗口起始时间 09:30
- **聚合触发条件**：当低级周期数据覆盖了完整的高级周期窗口时，才触发聚合
- **OHLCV 聚合规则**（行业标准）：
  - open: 取窗口内第一根 K线的 open
  - high: 取窗口内所有 K线的 high 的最大值
  - low: 取窗口内所有 K线的 low 的最小值
  - close: 取窗口内最后一根 K线的 close
  - volume: 取窗口内所有 K线的 volume 之和
- **非标准交易时间**（如夜盘、节假日）：按实际交易时间处理，不强行填充缺失数据

---

## 附录 C：依赖说明

| 依赖 | 用途 | 来源 | 状态 |
|------|------|------|------|
| pandas | 核心数据结构（DataFrame） | 已有 | 运行时必需 |
| threading | 并发控制（RLock, Condition） | 标准库 | 运行时必需 |
| enum | 计算模式枚举 | 标准库 | 运行时必需 |
| dataclasses | 结构化数据定义 | 标准库 | 运行时必需 |
| pandas-ta | 技术指标计算（可选扩展） | 需添加 | 当前未使用，用内置函数代替 |