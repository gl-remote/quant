# 量化策略数据管理方案设计

## 一、需求分析

### 1.1 核心需求
1. K线数据管理：维护策略运行过程中接收到的K线数据历史
2. 多周期支持：同时管理多个不同周期的K线表格（如1分钟、3分钟、5分钟等）
3. 逐根更新：模拟实盘场景，支持一根一根追加K线（更新对应周期）
4. 指标计算：使用成熟第三方库计算指标
5. 事件数据管理：支持事件数据（大单成交、新闻等），与K线、指标一起管理
6. 多策略共享：不同策略可以使用不同周期组合，共享的周期数据和指标只存一份
7. 并发安全：基于条件变量的快照等待，只锁正在更新的周期，之前的数据可以安全读
8. 截止周期镜像：策略只能看到指定周期及之前的数据，不受后面数据干扰
9. 简易实现：优先考虑代码简洁、易理解
10. 回测场景：只考虑几千个周期的回测

### 1.2 现有问题
1. 每个策略自己维护数据缓存（如_close_history）
2. 多个策略回测相同数据时，指标重复计算
3. 没有统一的数据管理接口，每个策略重复实现类似逻辑
4. 不支持多周期数据统一管理
5. 没有事件数据管理

---

## 二、总体架构设计

### 2.1 核心组件
只需新增一个文件：strategies/core/data_feed.py

核心类：
1. PeriodData（数据类）：单个周期的表格，纯存数据，提供截止周期镜像
2. DataFeed（管理类）：管理多个 PeriodData 实例，负责调度计算
3. DataFeedCache（上层缓存类）：单例模式，管理多个 DataFeed 实例，区分不同品种（核心组件）
4. PeriodDataSnapshot（快照类）：只读快照
5. Event（事件基类）：事件数据类型定义

### 2.2 设计原则
1. 使用 Pandas + pandas-ta 计算指标（成熟第三方库）
2. 职责分离：
   - DataFeed（管理类）：负责 update_bar 调度计算、管理周期数据、处理周期转换
   - PeriodData（数据类）：纯存数据，提供截止周期镜像，不负责计算
3. 多周期表格管理：一个 DataFeed 管理多个周期的 K线、指标、事件
4. 周期共享：策略A用1、3、5周期，策略B用2、4、5周期，5周期数据共享
5. 支持周期转换：硬编码常见周期转换关系（1m→5m, 1m→15m, 1m→1h等），支持两种场景：从低级周期生成高级K线，跨周期指标计算
6. 懒加载按需计算：指标第一次访问时才计算，后面策略自动复用；计算方式灵活（全量/逐行都支持），回测场景优先易用性，性能随缘
7. 基于条件变量的快照等待：只在 DataFeed 级别加锁，读操作检查时间戳，必要时等待更新完成
8. 截止周期镜像：提供快照功能，策略只能看到指定周期及之前的数据
9. 指标函数模块级注册：指标计算函数在模块级注册，所有 DataFeed 共享
10. 保持现有架构兼容，最小化改动

---

## 三、类详细设计

### 3.1 Event 事件类型定义

```python
@dataclass
class Event:
    """事件基类"""
    timestamp: pd.Timestamp
    type: str  # 'big_trade' | 'news' | 'orderbook_imbalance' | 'custom'
    symbol: str
    period: Optional[str] = None  # None 表示全局事件，否则绑定到特定周期
    data: Any = None

@dataclass
class BigTradeEvent(Event):
    """大单成交事件"""
    price: float
    volume: float
    direction: str  # 'buy' | 'sell'

@dataclass
class NewsEvent(Event):
    """新闻事件"""
    title: str
    content: Optional[str] = None
    importance: int = 1  # 1-5
```

---

### 3.2 PeriodData（数据类，单个周期）

#### 3.2.1 设计目标
- 统一管理该周期的 **K线、指标** 两类数据（事件由 DataFeed 统一管理）
- 提供逻辑视图，策略只能看到指定时间点之前的数据
- 支持数据追加（Append-Only，历史数据不修改）
- 底层存储使用 Pandas DataFrame
- 高效的数据访问，通过逻辑视图实现，不复制数据

#### 3.2.2 核心功能
1. 数据存储：持有该周期的 K线+指标（合并DataFrame）
2. 数据访问：通过时间/索引获取 Bar、指标
3. 数据追加：追加新的 K线、指标数据（Append-Only）
4. 逻辑视图：获取截止指定时间点的逻辑视图，不包含后面的数据，不复制数据

#### 3.2.3 数据结构
```python
class PeriodData:
    # K线数据（OHLCV） + 指标数据（合并在一起，索引统一为datetime）
    _df: pd.DataFrame
    _latest_time: Optional[pd.Timestamp]  # 最新数据时间
    _period: str  # 周期名称
```

#### 3.2.4 函数签名
```python
class PeriodData:
    def __init__(self, period: str):
        """
        初始化单个周期的数据容器

        初始化过程：
        1. 创建空的K线+指标DataFrame，包含datetime, open, high, low, close, volume列
        2. 初始化状态变量

        :param period: 周期名称，如 "1m", "5m", "1h", "1d" 等
        """
        pass

    def append_bars(self, bars: List[Bar]) -> None:
        """
        批量追加K线数据（用于回测初始化）

        注意事项：
        1. 必须按时间升序排列
        2. 时间戳不能与已有的数据重复
        3. Append-Only：历史数据不会被修改

        :param bars: K线列表
        :raises ValueError: 如果bars为空或时间顺序不对
        """
        pass

    def append_bar(self, bar: Bar) -> None:
        """
        追加单根K线（用于实时/逐根更新场景）

        注意事项：
        1. 追加的时间戳必须晚于已有的最新时间
        2. 通常被DataFeed.update_bar调用，策略不应直接调用此方法
        3. Append-Only：历史数据不会被修改

        :param bar: 单根K线数据
        :raises ValueError: 如果时间戳早于或等于最新数据时间
        """
        pass

    def append_indicators(self, indicators: pd.DataFrame) -> None:
        """
        追加指标数据

        指标DataFrame要求：
        1. 索引必须与K线的datetime对齐
        2. 列名应为指标名（如 "sma_10", "ema_20"）

        :param indicators: 指标DataFrame，行数应等于或小于当前K线数
        :raises ValueError: 如果索引不匹配
        """
        pass

    # --- 视图方法 ---

    def get_data(self, current_time: Union[pd.Timestamp, datetime.datetime], lookback_bars: int = 1) -> PeriodDataView:
        """
        获取截止指定时间点的逻辑视图（只读，用于策略安全访问）

        视图特性：
        1. 只包含截止到current_time的数据，不包含之后的未来数据
        2. 只读访问，策略无法修改原始数据
        3. 不受后续数据更新影响，保证数据一致性（Append-Only）
        4. 可指定需要的历史K线数，限定视图范围
        5. 逻辑视图，不复制数据，通过索引范围访问原始数据

        :param current_time: 当前时间，视图将只包含<=此时间的数据
        :param lookback_bars: 需要的历史K线数，从current_time往前数，默认1根
        :return: PeriodDataView只读逻辑视图对象
        :raises ValueError: 如果current_time晚于最新数据时间，或lookback_bars <= 0
        """
        pass

    # --- 数据访问方法 ---

    def get_bar(self, idx: int) -> Optional[Bar]:
        """
        通过索引获取K线

        索引规则：
        0: 最早的K线
        -1: 最新的K线

        :param idx: 索引位置，支持负索引
        :return: Bar对象，索引越界返回None
        """
        pass

    def get_bar_by_time(self, time: Union[pd.Timestamp, datetime.datetime]) -> Optional[Bar]:
        """
        通过精确时间戳获取K线

        :param time: 要查找的时间戳
        :return: 匹配的Bar对象，未找到返回None
        """
        pass

    def get_indicator(self, name: str, idx: int) -> Optional[float]:
        """
        通过索引获取指标值

        :param name: 指标名称，如 "sma_10", "rsi_14"
        :param idx: 索引位置，支持负索引，-1表示最新
        :return: 指标值，索引越界或指标不存在返回None
        """
        pass

    def get_indicator_series(self, name: str) -> pd.Series:
        """
        获取指标完整序列

        :param name: 指标名称
        :return: 指标Series，索引为datetime
        :raises KeyError: 如果指标不存在
        """
        pass

    # --- 属性 ---

    @property
    def latest_time(self) -> Optional[pd.Timestamp]:
        """获取最新数据时间戳"""
        pass

    @property
    def length(self) -> int:
        """获取当前数据长度（K线数量）"""
        pass

    @property
    def period(self) -> str:
        """获取周期名称"""
        pass
```

---

### 3.3 PeriodDataView（逻辑视图类，只读）

#### 3.3.1 设计目标
- 只读逻辑视图，防止策略修改数据
- 只包含截止指定时间点和指定历史K线范围的数据
- 不受后续数据更新影响（Append-Only 保证）
- 高效实现：通过索引范围访问原始数据，不复制数据
- 纯只读，不触发任何计算

#### 3.3.2 数据结构
```python
class PeriodDataView:
    # 对原始 DataFrame 的引用（不复制数据）
    _df_ref: pd.DataFrame
    # 对原始事件数据的引用（不复制数据）
    _events_ref: pd.DataFrame
    # 视图的起始索引（包含）
    _start_idx: int
    # 视图的结束索引（包含）
    _end_idx: int
    # 视图的截止时间
    _current_time: pd.Timestamp
    # 周期名称
    _period: str
```

#### 3.3.3 函数签名
```python
class PeriodDataView:
    def __init__(self, df_ref: pd.DataFrame, events_ref: pd.DataFrame, 
                 start_idx: int, end_idx: int, current_time: pd.Timestamp, period: str):
        """
        初始化逻辑视图（内部使用，不应直接构造）

        :param df_ref: 原始K线+指标DataFrame的引用（不复制）
        :param events_ref: 原始事件DataFrame的引用（不复制）
        :param start_idx: 视图的起始索引（包含）
        :param end_idx: 视图的结束索引（包含）
        :param current_time: 视图的截止时间
        :param period: 周期名称
        """
        pass

    def get_bar(self, idx: int) -> Optional[Bar]:
        """
        通过索引获取K线（索引相对于视图）

        :param idx: 索引位置，支持负索引（相对于视图）
        :return: Bar对象，索引越界返回None
        """
        pass

    def get_indicator(self, name: str, idx: int) -> Optional[float]:
        """
        通过索引获取指标值（索引相对于视图）
        注意：此方法不触发计算，指标不存在返回 None

        :param name: 指标名称，如 "sma_10"
        :param idx: 索引位置，支持负索引（相对于视图）
        :return: 指标值，索引越界或指标不存在返回None
        """
        pass

    def get_events(self) -> List[Event]:
        """获取视图时间范围内的所有事件"""
        pass

    def get_all_bars(self) -> pd.DataFrame:
        """获取视图中所有K线+指标DataFrame（只读视图，不复制）"""
        pass

    @property
    def current_time(self) -> pd.Timestamp:
        """获取视图的截止时间"""
        pass

    @property
    def length(self) -> int:
        """获取视图中K线数量"""
        pass

    @property
    def period(self) -> str:
        """获取周期名称"""
        pass
```

---

### 3.4 DataFeed（管理类，多周期）

#### 3.4.1 设计目标
- 管理单个品种（symbol）的所有周期数据
- 持有该品种的元数据（symbol、数据源等）
- 提供统一的 update_bar 入口，调度所有相关计算
- 基于条件变量的快照等待机制（只在 DataFeed 级别加锁）
- 提供高效的数据访问路由（通过周期名快速定位 PeriodData）
- 统一管理 K线、指标、事件 三类数据
- 支持周期转换（从1m数据衍生出5m数据）
- 回测前统一注册所有指标，避免实时计算的不同步问题

#### 3.4.2 核心功能
1. 注册周期：创建并管理 PeriodData，通过周期名O(1)访问
2. 注册指标：为指定周期注册需要计算的指标（名称+参数组合）
3. update_bar 调度：来一根 K线后，更新对应周期，调度所有相关计算
4. 数据访问：通过周期名获取对应的 PeriodData
5. 事件管理：追加和查询事件数据

#### 3.4.3 数据结构
```python
class DataFeed:
    # --- 元数据 ---
    symbol: str  # 交易品种，如 "btc_usdt" 或 "CZCE.sr509"
    source: Optional[str] = None  # 数据源标识（从symbol解析或传入）

    # --- 周期数据管理 ---
    # 高效锚定：通过周期名直接索引，O(1)访问
    # 每个 PeriodData 内部统一管理：K线、指标、事件
    _periods: Dict[str, PeriodData]  # key: 周期名，value: PeriodData

    # --- 并发控制 ---
    _lock: threading.RLock  # 只在这里加锁，DataFeedCache不需要锁
    _updating_time: Optional[pd.Timestamp] = None  # 正在更新的时间，用于快照安全检查

    # --- 指标注册配置 ---
    # 为每个周期注册需要计算的指标（指标名 + 参数）
    # 计算时自动生成列名，如 "sma_10", "ema_20"
    _registered_indicators: Dict[str, List[Tuple[str, dict]]]
    # key: 周期名，value: [(指标名, 参数字典)]
    # 例："5m" → [("sma", {"period": 10}), ("sma", {"period": 20})]
    # 同一指标名+不同参数算不同列（sma_10 vs sma_20）
```

---

### 3.5 模块级指标函数与周期转换函数

```python
# ==========================================
# 模块级指标计算函数注册（所有 DataFeed 共享）
# ==========================================

class IndicatorCalcMode(Enum):
    BATCH = "batch"  # 一次性计算所有数据（默认）
    INCREMENTAL = "incremental"  # 逐行/增量式计算，适合 update_bar 时触发

@dataclass
class IndicatorFuncInfo:
    func: Callable
    calc_mode: IndicatorCalcMode

_REGISTERED_INDICATOR_FUNCS: Dict[str, IndicatorFuncInfo] = {}

def register_indicator_func(name: str, func: Callable, calc_mode: IndicatorCalcMode = IndicatorCalcMode.BATCH) -> None:
    """全局注册指标计算函数，所有 DataFeed 共享

    指标计算函数签名要求：
    def indicator_func(df: pd.DataFrame, **params) -> pd.Series

    :param name: 指标名称
    :param func: 计算函数
    :param calc_mode: 计算模式，BATCH（默认）一次性全量计算，INCREMENTAL适合实时增量
    """
    _REGISTERED_INDICATOR_FUNCS[name] = IndicatorFuncInfo(func=func, calc_mode=calc_mode)


# ==========================================
# 模块级周期转换函数注册（所有 DataFeed 共享）
# ==========================================

_REGISTERED_CONVERTERS: Dict[Tuple[str, str], Callable] = {}

def register_period_converter(source_period: str, target_period: str, func: Callable) -> None:
    """全局注册周期转换函数

    支持两种场景：
    1. 从低级周期生成高级K线（1m → 5m）
    2. 跨周期指标计算（用 1m 数据计算 5m 指标）

    转换函数签名要求（K线聚合场景）：
    def converter_func(source_data: PeriodData) -> List[Bar]

    :param source_period: 源周期（如 "1m"）
    :param target_period: 目标周期（如 "5m"）
    :param func: 转换函数
    """
    _REGISTERED_CONVERTERS[(source_period, target_period)] = func


# ==========================================
# 默认注册一些常用指标（使用 pandas-ta）
# ==========================================
# 在模块初始化时自动注册
```

---

### 3.6 DataFeed 函数签名

```python
class DataFeed:
    def __init__(self, symbol: str, source: Optional[str] = None):
        """
        初始化单个品种的多周期数据管理器

        :param symbol: 交易品种，如 "btc_usdt" 或 "CZCE.sr509"
        :param source: 数据源标识（可选，如果不提供可从symbol解析）
        """
        self.symbol = symbol
        if source is None:
            # 尝试从symbol解析source，如 "CZCE.sr509" -> source="CZCE"
            self.source = _parse_source_from_symbol(symbol)
        else:
            self.source = source
        pass

    def register_period(self, period: str) -> PeriodData:
        """
        注册一个新的周期，创建对应的PeriodData实例

        :param period: 周期名称，如 "1m", "5m", "1h"
        :return: 新创建或已存在的PeriodData实例
        """
        pass

    def register_indicator(self, period: str, indicator_name: str, **params) -> None:
        """
        为指定周期注册需要计算的指标

        指标不会立即计算，第一次访问时才懒加载；计算方式灵活（全量/逐行都支持）

        参数组合示例：
        - register_indicator("5m", "sma", period=10) -> 生成列 "sma_10"
        - register_indicator("5m", "sma", period=20) -> 生成列 "sma_20"
        - register_indicator("5m", "ema", period=20) -> 生成列 "ema_20"

        :param period: 周期名称
        :param indicator_name: 指标名称，需已在模块级注册
        :param params: 指标参数，将传递给计算函数
        :raises KeyError: 如果周期未注册或指标函数未注册
        """
        pass

    def load_history_data(self, period: str, bars: List[Bar], events: Optional[List[Event]] = None) -> None:
        """
        批量加载历史数据（用于回测初始化）

        注意：
        1. 不会自动计算指标，需调用calculate_all()

        :param period: 周期名称
        :param bars: 历史K线列表，需按时间升序排列
        :param events: 历史事件列表（可选）
        """
        pass

    def update_bar(self, bar: Bar, period: str, events: Optional[List[Event]] = None) -> None:
        """
        更新一根K线，调度周期转换（核心方法，线程安全）

        执行流程（全程持有全局锁）：
        1. 锁定并记录当前正在更新的时间
        2. 更新对应周期的PeriodData（追加K线 + 可选事件）
        3. 检查是否触发周期转换（如1分钟累计够5根生成新的5分钟K线）
        4. 如果触发，调用转换函数生成并追加高级周期K线
        5. 可选：对注册为 INCREMENTAL 模式的指标，触发增量计算
        6. 清除正在更新的时间标记，解锁

        注意：
        - BATCH模式指标不会自动计算，采用懒加载机制，第一次访问时才按需计算
        - INCREMENTAL模式指标可以选择在 update_bar 时触发增量计算（可选）

        :param bar: 新K线数据
        :param period: 对应周期名称
        :param events: 归属于这根 K线 时间范围内的事件（可选）。
            例如这根 1m K线期间发生了一次大单成交，作为 events 传入。
            框架将它们关联到该 K线，后续可通过 get_events_at_bar(bar_idx) 查询。
        :raises KeyError: 如果周期未注册
        """
        pass

    def calculate_all(self) -> None:
        """
        批量预计算所有周期的所有指标（可选，用于回测初始化性能优化）

        适用场景：
        - 回测开始前，所有历史数据已加载
        - 希望一次性预计算所有指标，避免运行时懒加载的轻微延迟

        注意：
        - 不是必须调用，不调用也能用
        - 会覆盖已有的指标数据
        - 会遍历所有周期，计算所有注册指标
        """
        pass

    def get_period(self, period: str) -> Optional[PeriodData]:
        """
        获取指定周期的PeriodData实例（高级用法）

        :param period: 周期名称
        :return: PeriodData实例，未注册返回None
        """
        pass

    def get_snapshot(self, period: str, end_time: pd.Timestamp, periods: int = 1) -> Optional[PeriodDataSnapshot]:
        """
        获取指定周期截止指定时间的快照（策略主要访问入口）

        并发安全检查：
        1. 检查是否有正在进行的update_bar
        2. 如果有，检查end_time是否 < _updating_time
        3. 如果安全（无更新或end_time在更新时间之前），返回快照

        :param period: 周期名称
        :param end_time: 截止时间，快照只包含<=此时间的数据
        :param periods: 需要的历史周期数，默认1个
        :return: PeriodDataSnapshot只读快照
        :raises KeyError: 如果周期未注册
        :raises ValueError: 如果end_time晚于最新数据时间
        """
        pass
```

---

### 3.7 DataFeedCache（上层缓存类，核心组件）

#### 3.7.1 设计目标
- 单例模式，全局唯一入口
- 管理多个 DataFeed 实例
- 根据交易品种（symbol）区分不同的 DataFeed
- 一个 symbol 对应一个 DataFeed
- 支持策略测试时注入 mock 的 cache
- 不需要自己的锁，只做路由

#### 3.7.2 数据结构
```python
class DataFeedCache:
    _instance: Optional["DataFeedCache"] = None
    _datafeeds: Dict[str, DataFeed]  # key: symbol（交易对），value: DataFeed
    # DataFeedCache 自己不需要锁，只做路由
```

#### 3.7.3 函数签名
```python
class DataFeedCache:
    @classmethod
    def get_instance(cls) -> "DataFeedCache":
        """
        获取单例（运行时使用）

        首次调用时自动创建实例，后续调用返回相同实例

        :return: DataFeedCache 单例
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def set_instance(cls, instance: Optional["DataFeedCache"]) -> None:
        """
        设置单例（测试时用来注入 mock）

        :param instance: DataFeedCache 实例或None
        """
        cls._instance = instance

    def get_or_create(self, symbol: str, source: Optional[str] = None) -> DataFeed:
        """
        获取或创建DataFeed实例

        一个 symbol 对应一个 DataFeed

        :param symbol: 交易品种，如 "btc_usdt"
        :param source: 数据源标识（可选）
        :return: DataFeed 实例（新创建或已存在）
        """
        pass

    def update_bar(self, symbol: str, bar: Bar, period: str, events: Optional[List[Event]] = None) -> None:
        """
        更新指定品种的K线（路由到对应DataFeed）

        这是Bridge或数据接收层的主要调用入口

        :param symbol: 交易品种
        :param bar: K线数据
        :param period: 对应周期名称
        :param events: 事件数据（可选）
        """
        pass

    def get_snapshot(self, symbol: str, period: str, end_time: pd.Timestamp, periods: int = 1) -> Optional[PeriodDataSnapshot]:
        """
        获取指定品种、指定周期的快照（策略主要访问入口）

        这是策略获取数据的主要方法

        :param symbol: 交易品种
        :param period: 周期名称
        :param end_time: 截止时间，快照只包含<=此时间的数据
        :param periods: 需要的历史周期数
        :return: PeriodDataSnapshot只读快照
        :raises KeyError: 如果品种或周期未注册
        """
        pass
```

---

## 四、Strategy 使用 DataFeedCache（方案确定）

### 4.1 设计结论

- **Bar**：复用现有 `strategies.Bar`，不重新定义
- **数据访问**：声明式需求 + `ctx` 注入，策略不在 on_bar 里自行拉取数据
- **兼容性**：直接改，不做旧签名兜底（当前只有一个 `MaStrategyCore`，改造成本可控）

### 4.2 Strategy 新增接口

```python
class Strategy(ABC, Generic[T]):

    @abstractmethod
    def data_requirements(self) -> dict[str, Any]:
        """策略的数据需求声明，由 Bridge/Engine 在初始化时读取
        框架据此注册周期、注册指标，并在 on_bar 时构造 ctx。
        返回格式由具体策略定义，框架只读不解析。
        """
        ...

    @abstractmethod
    def on_bar(self, bar: Bar, ctx: BarContext) -> Signal:
        """处理一根K线，接收已准备完毕的上下文
        ctx 包含所有声明的跨周期数据和事件。
        签名不再支持无 ctx 版本——旧策略需要迁移。
        """
        ...
```

### 4.3 BarContext 类型

```python
@dataclass
class BarContext:
    """当前 bar 的策略上下文——引擎按 data_requirements 声明构造"""
    symbol: str
    bar: Bar
    # 多周期数据，key=周期名，key 集合 = data_requirements 中声明的周期
    multi: dict[str, PeriodDataSnapshot]
    # 当前 bar 时间范围内的事件
    events: list[Event]
```

### 4.4 PeriodDataSnapshot 访问器

```python
class PeriodDataSnapshot:
    def bar(self, idx: int = -1) -> Bar | None: ...
    def close(self, idx: int = -1) -> float | None: ...
    def indicator(self, name: str, idx: int = -1) -> float | None: ...
    def indicator_series(self, name: str) -> pd.Series: ...
    def events(self) -> list[Event]: ...
```

### 4.5 策略示例

```python
class MaStrategyCore(Strategy[MACrossParams]):

    name = STRATEGY_MA
    VERSION = f"{CORE_VERSION}-ma1"

    def data_requirements(self) -> dict:
        return {
            "periods": {
                "5m": {"bars": 50},
                "1m": {"bars": 20},
            },
            "indicators": {
                "5m": [{"name": "sma", "period": 10},
                        {"name": "sma", "period": 20}],
            },
        }

    def on_bar(self, bar: Bar, ctx: BarContext) -> Signal:
        sma10 = ctx.multi["5m"].indicator("sma_10", -1)
        sma20 = ctx.multi["5m"].indicator("sma_20", -1)
        ...
```

### 4.6 测试

```python
def test_strategy():
    ctx = BarContext(symbol="m2509", bar=test_bar,
                     multi={"5m": mock_snapshot, "1m": mock_snapshot},
                     events=[])
    signal = strategy.on_bar(test_bar, ctx)
    assert signal.action == TRADE_ACTION_BUY
```

不需要 mock 全局 cache，不需要 set_instance，构造 BarContext 直接喂即可。

### 4.7 完整数据流

```
init:
  策略.data_requirements → Bridge/Engine 读取
  → 注册周期、注册指标到 DataFeed

回测循环:
  for bar in bars:
    DataFeed.update_bar(bar)          # K 线落地
    ctx = build_context(strategy)     # 按需求声明拉快照
    signal = strategy.on_bar(bar, ctx)  # 策略拿数据做决策
    Bridge.execute(signal)            # 翻译为 vnpy buy/sell
```

---

## 五、使用流程

### 5.1 初始化阶段（回测前）
```python
# 1. 获取全局 Cache
cache = DataFeedCache.get_instance()

# 2. 创建或获取 DataFeed（按 symbol）
data_feed = cache.get_or_create("CZCE.sr509")

# 3. 注册所有需要的周期
data_feed.register_period("1m")
data_feed.register_period("5m")

# 4. 读取策略声明，批量注册指标
# data_feed.register_indicator 由 Engine 在读取 data_requirements 后统一调用
# 策略无需手动注册

# 5. 加载历史数据
data_feed.load_history_data("1m", bars_1m, events_1m)
data_feed.load_history_data("5m", bars_5m, events_5m)

# 6. 可选：预计算所有指标（性能优化）
# data_feed.calculate_all()
```

### 5.2 回测运行阶段
```python
# Bridge 遍历主周期数据，通过 Cache 更新
for bar, events in zip(bars_1m, event_groups):
    # 1. K线落地到 DataFeed（必须先 update_bar，让跨周期数据就绪）
    #    例如 1m → 5m：第 1、2、3、4 根 1m bar 不会触发聚合，
    #    第 5 根到达时自动聚合成一根 5m bar 并写入 5m 周期的 PeriodData。
    #    如果先调 on_bar 再 update_bar，on_bar 拿到的 snapshot 不包含最新 K线。
    cache.update_bar("CZCE.sr509", bar, "1m", events)

    # 2. 读取策略声明，构造 BarContext
    ctx = build_context(
        data_feed, strategy.data_requirements(), bar.datetime
    )

    # 3. 调用策略
    signal = strategy.on_bar(bar, ctx)

    # 4. 执行下单
    bridge.execute(signal, bar)

# 策略不需要自己从 cache 拿数据，ctx 里已准备完毕
```

### 5.3 数据锚定方式说明
```
数据访问链路（O(1)复杂度）：
DataFeedCache（symbol → DataFeed）
    ↓
DataFeed（period → PeriodData）
    ↓
build_context() → BarContext（按声明裁剪）
    ↓
Strategy.on_bar(bar, ctx)

策略不再感知 DataFeedCache 的存在：
bar, ctx → on_bar() → Signal
```

---

## 六、重要问题的解决方案总结

| 问题 | 解决方案 | 为什么 |
|------|----------|--------|
| K线与指标分离还是合并？ | **合并**：K线+指标放一个DataFrame，索引统一 | 策略读取时通常同时需要K线值和指标值，分离意味着每次查询要 join/merge，合并后一次 `.loc` 拿到全部，简单高效 |
| 指标与事件如何管理？ | K线+指标合并，事件单独管理，都在PeriodData内部 | 事件是稀疏数据（非每根K线都有），合并到 DataFrame 会导致大量 NaN 列。单独存用时间索引查询，天然高效 |
| 周期不同步问题？ | **懒加载按需计算**，append-only 快照机制保障数据一致性 | 指标只算一次、多策略共享，不需要预判策略访问顺序。append-only 保证旧数据不会被修改，快照就是安全的 |
| Callable是函数还是钩子类？ | **简单函数**，模块级注册，所有DataFeed共享 | 不涉及状态管理，函数足以描述转换逻辑。类的额外开销（构造/销毁/生命周期）在几千周期回测中毫无收益 |
| 数据存哪里？ | PeriodData内部统一管理，DataFeed只做调度 | DataFeed 属于"调度侧"（知道什么时候该算什么），PeriodData 属于"存储侧"（知道怎么存和取），职责分离比合在一起好维护 |
| _indicator_funcs是否每个DataFeed注册？ | **不需要**，模块级注册一次，所有DataFeed共享 | 指标函数是纯计算逻辑，与品种/周期无关。例如 sma(df, period=10) 对任何品种的计算方式一样，没必要每个 DataFeed 存一份函数引用 |
| DataFeedCache需要锁吗？ | **不需要**，DataFeedCache只做路由，锁在DataFeed级别 | DataFeedCache 只有读操作（`get_or_create` 在缓存命中时也是读），写操作在 DataFeed.update_bar 内部，锁放在操作发生的层级更合理 |
| 快照如何实现？ | **Pandas切片 + copy** | 几千周期数据，DataFrame copy 是纳秒级操作。为这个写函数式不可变结构徒增复杂度，没有实际回报 |
| source参数需要吗？ | 可选，可从symbol解析 | 期货合约 `CZCE.sr509` 的 `CZCE` 就是交易所代码（source），纯 convention 就能解析。保留参数是为了覆盖无法从 symbol 推断的场景（如自定义品种） |
| 事件数据是核心吗？ | **是**，完整支持Event类型 | 事件数据（大单/新闻/异动）在策略信号中越来越重要，尤其在多因子和 ML 策略中。在架构层面预留这个口子比后期补合算得多 |
| 策略如何获取数据？ | **声明式需求 + ctx 注入** | 策略走全局 Cache 拉数据 → 耦合全局单例、单测需要 mock。声明式让框架在 on_bar 之前就准备好所有数据，策略只做事，不做数据获取 |
| Bar 类型用现有的还是重新定义？ | **复用 `strategies.Bar`** | DataFrame 列名与 Bar 字段直接对齐（`open→open`，无 `open_price` 映射），零转换成本。策略从 Bridge 和从 ctx 拿到的 K线是同一类型 |
| 旧策略兼容性怎么办？ | **不做兼容**，直接改 | 当前只有一个策略（MaStrategyCore），改造成本可忽略。为"未来可能有旧策略"做兼容垫片属于过早抽象 |

---

## 七、优势总结
1. **职责清晰**：
   - PeriodData 纯存数据，提供快照，简单可靠
   - DataFeed 负责调度和计算，逻辑集中
2. **完整支持三类数据**：K线 + 指标 + 事件，统一管理
3. **多周期支持**：统一管理多个周期的数据和指标
4. **周期转换**：支持从低级周期算出高级周期（1分钟→5分钟）
5. **共享机制**：相同周期的数据和指标多策略共享，只存一份
6. **使用成熟库**：pandas-ta，不需要自己写指标计算
7. **懒加载按需计算**：指标第一次访问时才计算，后面策略自动复用；计算方式灵活（全量/逐行都支持）
8. **指标函数模块级注册**：避免每个DataFeed重复注册
9. **回测场景优先**：易用性第一，性能随缘，append-only 快照机制保障数据安全
10. **截止周期镜像**：策略只能看到指定时间点之前的数据，安全可靠
11. **基于条件变量的快照等待**：只在DataFeed级别加锁，读操作检查时间戳，必要时等待更新完成
12. **代码简洁**：策略不需要维护状态，直接拿指标用
13. **测试友好**：支持mock注入
14. **向后兼容**：不影响现有策略

---

## 八、设计问题与思考 (QA)

### Q1: 如何正确描述我们的并发机制？（修正名词误用）

**之前的误用**：
- 之前叫「行级锁」是不准确的！
- 我们的数据是 Append-Only（只追加不修改），不需要锁定特定行

**正确的术语**：
- **标准名称**：**基于条件变量的 Append-Only 快照机制**
- **关键技术点**：
  1. Append-Only 数据：只追加，不修改
  2. 条件变量（Condition Variable）：用于等待更新完成
  3. 时间戳检查：`get_snapshot` 检查 `end_time` 是否 < `_updating_time`
  4. 快照：提供截止时间点的一致性数据

**需要明确**：
- 如果 `end_time >= _updating_time`，`get_snapshot` 应该怎样？
  - **方案A（推荐回测）**：抛错（回测场景单线程，理论不会发生，安全检查）
  - **方案B（实盘）**：等待更新完成（轮询或条件变量）
  - **方案C（灵活）**：让用户指定超时机制，可选等待

**我们的推荐**：先实现简单的时间戳检查，需要等待机制可选参数

---

### Q2: 周期转换的机制是怎样的？

**方案确定**：
- 周期转换关系**硬编码**，支持常见组合（1m→5m, 1m→15m, 1m→1h, 5m→15m 等）
- 支持**两种计算场景**：
  1. **从低级周期生成高级K线**：1m 数据聚合生成 5m/15m/1h K线，追加到高级周期
  2. **跨周期指标计算**：用 1m 数据，计算 5m 周期的指标
- **天然对齐**：不同 PeriodData 数据按时间天然对齐，只需要按时间点正确读取
- **追加模式**：转换后的高级周期K线总是追加，不替换已有数据

**周期转换关系示例**（可扩展）：
```
1m ──→ 5m ──→ 15m ──→ 1h
  └──────────────→ 1h
```

**触发条件**：
- 当调用 `update_bar` 更新低级周期时，自动检查是否可以聚合出完整的高级周期K线
- 如果可以，则调用周期转换函数，生成并追加到高级周期

---

### Q3: 指标计算机制是怎样的？

**方案确定**：灵活懒加载 + 计算模式标记，回测场景优先易用性

**核心思路**：
1. 底层存储：pandas，支持高效批量计算
2. 懒加载按需计算：某个策略第一次访问某个指标时触发，后面的策略复用
3. 安全性保障：append-only 快照 + `_updating_time` 检查，只访问更新时间点之前的数据
4. 计算方式灵活：既支持全量计算，也支持逐行计算，通过 `IndicatorCalcMode` 标记明确
5. 避免重复计算：框架根据计算模式和指标是否已计算，智能决定是否触发

**指标计算模式**（注册时明确）：
- **BATCH（默认）**：一次性全量计算，适合pandas-ta这类批量计算的指标
- **INCREMENTAL**：逐行/增量式计算，适合 `update_bar` 时实时触发的指标

**指标计算触发时机**：
- **第一次访问时**：不管什么模式，都全量计算到当前数据末尾
- **`update_bar` 追加新K线后**：
  - BATCH模式：不自动计算，等下次访问时重新全量算（或者按需算）
  - INCREMENTAL模式：可以在 `update_bar` 时自动触发增量计算（可选）
- **后续访问**：直接返回已计算好的结果

**无需担心的问题**：
- ✅ 多个策略同时访问同一个指标：因为是 append-only，就算同时触发多次，结果一致，多算几次也没关系（回测场景，性能随缘）
- ✅ 数据一致性：有 `_updating_time` 快照机制保障
- ✅ 增量/全量灵活：指标函数注册时标记清楚，框架自动处理

**使用示例**：
```python
# 注册指标时明确模式
register_indicator_func("sma", sma_func, IndicatorCalcMode.BATCH)  # 批量计算
register_indicator_func("custom_signal", custom_func, IndicatorCalcMode.INCREMENTAL)  # 增量计算

# 策略A先访问
snapshot = cache.get_snapshot("btc_usdt", "1m", time1)
sma10 = snapshot.get_indicator("sma_10")  # 触发全量计算

# 策略B后访问
snapshot = cache.get_snapshot("btc_usdt", "1m", time1)
sma10 = snapshot.get_indicator("sma_10")  # 直接复用，不重复计算

# 策略C访问不同时间
snapshot = cache.get_snapshot("btc_usdt", "1m", time2)  # 只访问 time2 之前的数据，安全
```

---

### Q4: 事件数据与周期的关系是怎样的？

**方案确定**：事件与symbol绑定，DataFeed级别统一管理

**核心思路**：
1. 一个DataFeed对应一个symbol，事件在DataFeed级别统一管理，不绑定到特定周期
2. 所有周期都可以访问该symbol的事件，通过时间范围查询
3. `get_events_at_bar` 返回该K线时间范围内的所有事件（不限于某周期）

**实现方式**：
- 方案A：DataFeed持有一个全局的事件列表/ DataFrame
- 方案B：选择其中一个PeriodData（如主周期）专门管理事件
- 现阶段先选简单方案，未来需要全局事件（如主力合约事件）时再扩展

**访问示例**：
```python
# 访问1分钟周期时，也能获取该symbol的所有事件
snapshot = cache.get_snapshot("CZCE.sr509", "1m", time)
events = snapshot.get_events()  # 返回该时间范围的所有事件

# 访问5分钟周期时，同样的事件
snapshot = cache.get_snapshot("CZCE.sr509", "5m", time)
events = snapshot.get_events()  # 返回的是同样的事件
```

---

### Q5: 多个策略需要不同指标组合时怎么办？

**方案确定**：上层统一注册，懒加载按需计算，自动共享

**核心思路**：
1. 初始化阶段，由上层（如回测引擎）统一注册所有策略需要的指标
2. 指标懒加载，第一次访问时才计算，避免无用计算
3. 已经计算的指标自动共享，所有策略都能用
4. 即使多注册了一些没用的指标，因为懒加载，也不会有额外开销

**流程示例**：
```python
# 初始化阶段：回测引擎统一注册
data_feed = cache.get_or_create("CZCE.sr509")
data_feed.register_indicator("1m", "sma", period=10)  # 策略A需要
data_feed.register_indicator("1m", "sma", period=20)  # 策略B需要

# 回测阶段：
# 策略A先访问 sma_10 → 触发计算
snapshot1 = cache.get_snapshot("CZCE.sr509", "1m", time)
sma10 = snapshot1.get_indicator("sma_10")

# 策略B后访问 sma_10 → 直接复用
# 策略B访问 sma_20 → 触发计算
snapshot2 = cache.get_snapshot("CZCE.sr509", "1m", time)
sma10 = snapshot2.get_indicator("sma_10")  # 直接用
sma20 = snapshot2.get_indicator("sma_20")  # 触发计算
```

**优势**：
- 简单：上层统一管理指标注册
- 高效：懒加载按需计算，不浪费算力
- 共享：计算一次，所有策略受益
- 容错：多注册了也没关系，不访问就不会算
```

---

### Q6: Bar 类型用现有的还是重新定义？数据怎么给到策略？

**结论**：
  
1. **Bar**：复用现有 `strategies.core.types.Bar`。DataFrame 列名与 Bar 字段直接对齐，零映射成本。
  
2. **数据传递**：声明式需求 + `ctx` 注入，不走全局 Cache。
   - `Strategy` 新增 `data_requirements()` 声明需要哪些周期和指标
   - `on_bar(bar, ctx)` 直接接收已构造好的 `BarContext`
   - `BarContext.multi` 按声明裁剪，只包含策略需要的周期
   - 策略不再调用 `DataFeedCache.get_instance()`
  
3. **无兼容设计**：直接替换旧签名，当前只有一个策略（MaStrategyCore），改造成本可控。
  
4. **字符串指标名的静态检查缺失**：接受 Trade-off，运行时在 `build_context` 阶段校验声明与注册是否匹配，拼错提前抛错，不静默失败。

---

## 九、设计审计

### 缺陷

#### 缺陷1：事件归属的架构矛盾

**位置**: 3.2 节 PeriodData 持有 `_events` DataFrame vs Q4

PeriodData 的内部数据结构明确包含 `_events: pd.DataFrame`（第104行），快照也通过 `PeriodDataSnapshot.get_events()` 从 PeriodData 返回事件。但 Q4 说"事件在 DataFeed 级别统一管理，不绑定到特定周期"。

**矛盾**: 如果事件是 DataFeed 级的，就不应该存在 PeriodData 里。两者只能选一个。实现时会产生争议——事件是跟周期走还是跟 symbol 走？

**建议**: 明确选定一种方案：要么将 `_events` 移到 DataFeed，快照通过 DataFeed 聚合所有周期的事件；要么接受"事件绑定到主周期"，放弃"DataFeed 级别统一管理"的说法。

**修改建议**: 
1. **选择方案**：混合方案，兼顾全局事件和周期绑定事件
   - DataFeed 统一管理所有事件，但事件可以有可选的 `period` 字段
   - 这样既支持全局事件（`period=None`），也支持周期特定事件（`period="1m"` 等）
2. **修改内容**：
   - 从 PeriodData 中移除 `_events` 属性
   - 在 DataFeed 中新增 `_events: pd.DataFrame` 属性
   - 相应地，将 PeriodData 中的事件相关方法（`append_event`、`append_events`、`get_events`、`get_events_at_bar`）移到 DataFeed 中
   - 更新 `Event` 基类，新增可选的 `period: Optional[str] = None` 字段
   - `append_event`/`append_events` 支持传入 `period` 参数
   - `get_events` 支持按 `period` 筛选（可选）
   - `get_events_at_bar` 同时返回该时间范围内的全局事件和该周期的特定事件
   - 修改 PeriodDataSnapshot，将 `get_events()` 改为从构造时传入的事件数据中获取（由 DataFeed 负责裁剪到快照时间范围，同时包含全局事件和对应周期的事件）
   - 更新 Q4 的描述，与实现保持一致

---

#### 缺陷2：API 参数命名和语义问题

**位置**: PeriodData.get_snapshot

```python
def get_snapshot(self, end_time: pd.Timestamp, periods: int = 1) -> PeriodDataSnapshot
```

**问题点**：
1. 方法名 `get_snapshot` 暴露了底层实现细节
2. `end_time` 参数命名不符合使用者视角，应该用 `current_time`
3. `periods` 的语义模糊："一个周期"是指**1根K线**还是**1个时间单位（如1分钟）**？对于1m K线，end_time=10:03, periods=3，是返回 10:01-10:03（3根K线）还是 10:00-10:03（3分钟）？这直接决定了策略能看到多少历史数据。

**建议**: 重命名方法和参数，明确语义。

**修改建议**:
1. 方法重命名：`PeriodData.get_snapshot` → `PeriodData.get_data`
2. 参数重命名：
   - `end_time` → `current_time`
   - `periods` → `lookback_bars`
3. 更新所有相关的文档说明，明确表示"从 current_time 往前数 `lookback_bars` 根 K线"
4. 如果传入 `lookback_bars=0` 或负数，抛出 ValueError
5. 如果传入 `lookback_bars` 大于现有数据长度，则返回所有可用数据
6. 因为是 Append-Only 数据，快照是逻辑上的，不需要每次复制数据

---

#### 缺陷3：API 设计问题

**位置**: DataFeed.get_snapshot vs Q1

**问题点**：
1. 方法名 `get_snapshot` 暴露了底层实现细节（"快照"是内部概念，对外 API 应该隐藏
2. `end_time` 参数命名不符合使用者视角，应该用 `current_time`（从使用者视角，这是当前时间）
3. `periods` 参数命名与之前统一的 `lookback_bars` 不一致
4. Q1 讨论了三种方案（回测抛错、实盘等待、可选超时），但函数签名中没有体现等待/超时机制
5. 快照实现方案需要调整：因为是 Append-Only 数据，读历史数据不需要复制数据，快照是逻辑上的（通过索引/时间戳范围实现，不产生新的数据副本

**建议**: 重新设计 API，隐藏快照是内部实现细节，对外提供更符合使用者视角的 API。

**修改建议**:
1. **方法重命名**：
   - `DataFeed.get_snapshot` → `DataFeed.get_data`
   - `DataFeedCache.get_snapshot` → `DataFeedCache.get_data`
   - `PeriodData.get_snapshot` → `PeriodData.get_data`
2. **参数重命名**：
   - `end_time` → `current_time`（从使用者视角，这是当前时间
   - `periods` → `lookback_bars`（与缺陷2的修改保持一致
3. **在 `get_data` 签名中增加 `timeout: Optional[float] = None` 参数
4. **更新 docstring**，说明：
   - 如果 `timeout=None`（默认），采用回测场景行为：如果 `current_time >= _updating_time`，直接抛出 ValueError
   - 如果 `timeout>0`，采用实盘场景行为：等待最多 `timeout` 秒，直到更新完成或超时
   - 如果 `timeout=0`，采用非阻塞行为：立即返回或抛出异常
5. **更新快照实现方案**：
   - 因为是 Append-Only 数据，历史数据不会被修改，快照是逻辑上的，不需要每次复制数据
   - 通过时间戳范围和索引范围实现逻辑快照，直接引用原始数据，不产生副本
   - PeriodDataSnapshot 保存对原始 DataFrame 的引用，通过 iloc/loc 范围访问，而不是复制
6. 在 Q1 中明确说明当前实现采用的默认行为
7. 更新文档中所有使用 `get_snapshot` 的地方都改为 `get_data`

---

#### 缺陷4：`build_context` 函数未定义

**位置**: 第777行、第821-823行

多次使用 `build_context()` 作为核心数据流的关键函数，但文档中没有任何地方定义它的签名和行为。它属于哪个类？是模块级函数还是 DataFeed 的方法？它如何解析 `data_requirements()` 并映射到数据访问调用？

这是整个数据流中最关键的编排函数，没有定义就不能正确实现回测循环。

**建议**: 增加 `build_context(data_feed, requirements, current_time) -> BarContext` 的函数签名和完整定义。

**修改建议**:
1. 在 4.3 节之后新增 4.8 节，专门定义 `build_context` 函数
2. 定义函数签名为模块级函数：
   ```python
   def build_context(
       data_feed: DataFeed,
       requirements: DataRequirements,
       current_time: Union[pd.Timestamp, datetime.datetime],
       timeout: Optional[float] = None
   ) -> BarContext
   ```
3. 详细说明其行为：
   - 解析 `requirements` 中的 `periods` 配置
   - 对每个周期调用 `data_feed.get_data(period, current_time, lookback_bars, timeout)`
   - 从 DataFeed 获取当前时间范围内的事件（根据 requirements.events 配置）
   - 构造并返回 `BarContext` 对象
4. 补充 `data_requirements` 的完整 schema 定义：

**DataRequirements 完整 Schema 定义**（类比数据库/表概念）：
```python
@dataclass
class PeriodRequirements:
    """单个周期的数据需求（类比表的查询需求）"""
    lookback_bars: int  # 查询的历史K线数量
    min_bars: Optional[int] = None  # 策略需要的最小K线数（可选，用于校验）

@dataclass
class IndicatorRequirements:
    """单个指标的计算需求"""
    name: str  # 指标名称
    params: dict[str, Any]  # 指标参数

@dataclass
class DataRequirements:
    """策略的数据需求（类比数据库查询计划）"""
    # 周期配置：key 是周期名称（对应 PeriodData 的 period 字段），value 是该周期的需求
    periods: dict[str, PeriodRequirements]
    
    # 指标配置：key 是周期名称，value 是该周期需要的指标列表
    indicators: dict[str, list[IndicatorRequirements]]
    
    # 事件配置：
    # - False: 不获取事件
    # - True: 获取所有事件（全局+所有周期特定）
    # - List[str|None]: 获取指定周期的事件，None 表示全局事件
    events: Union[bool, list[Optional[str]]] = False
```

**DataFeed 和 PeriodData 命名说明**：
- `DataFeed` ≈ 数据库（Database），用 `symbol` + `source` 作为唯一标识
- `PeriodData` ≈ 数据表（Table），用 `period` 作为唯一标识（在 DataFeed 内）
- 不需要额外的 name 字段，当前设计已经足够清晰

---

#### 缺陷5：BATCH 模式指标存在重复全量计算 + 数据一致性问题

**位置**: 第954-958行

BATCH 模式指标"第一次访问时全量计算到当前数据末尾"，但 `calculate_all()` 也是全量计算，两者行为重叠且可能冲突。

更关键的问题：**BATCH 指标计算的输入数据范围是什么？**
- 如果在完整的 `PeriodData._df` 上计算（所有历史数据），然后通过逻辑视图（不复制数据）截断——这没问题。
- 但如果指标函数内部需要基于当前时间之前的子集计算，视图拿到的是完整数据上算好的值，可能引用了未来数据。

文档没有说明指标计算是在 full DataFrame 还是 sliced DataFrame 上执行，也没有说明数据访问是通过复制还是逻辑视图。

**建议**: 明确 BATCH 模式始终在完整 DataFrame 上计算，数据访问通过逻辑视图（不复制数据）实现。如果需要对子集计算，策略应在视图范围内自行计算。

**修改建议**:
1. 在 Q3 中明确说明：
   - BATCH 模式指标始终在完整的 `PeriodData._df` 上计算
   - 数据访问是通过逻辑视图（时间戳/索引范围），不复制数据，不触发重新计算
   - `calculate_all()` 的作用是预计算所有注册指标，避免运行时懒加载延迟
   - 如果某个指标已经计算过，`calculate_all()` 会跳过该指标
2. 在 `register_indicator` 的 docstring 中说明此行为
3. 明确指标函数接收的是完整 DataFrame，不应该假设或依赖数据范围
4. 因为是 Append-Only 数据，历史数据不会被修改，逻辑视图是安全的

---

#### 缺陷6：周期转换的时间边界对齐规则未定义

**位置**: 第933-935行

"自动检查是否可以聚合出完整的高级周期K线"——具体检查逻辑未定义：
- 1m → 5m，时间窗口是 `[T, T+5min)` 还是按K线根数（每5根）？
- 如果 1m 数据的时间戳标记为周期开始时间（09:30），还是结束时间（09:31）？
- 非标准交易时间（夜盘、节假日）如何处理？

**建议**: 定义时间切片对齐规则，并说明聚合后5m K线的时间戳取什么值（起始时间还是结束时间）。

**修改建议**:
1. 在 Q2 中新增"时间对齐规则"小节，详细说明：
   - **K线时间戳定义**：所有 K线的时间戳表示**周期开始时间**（如 09:30 表示 09:30-09:31 的 1m K线），这是金融数据行业标准惯例
   - **时间窗口规则**：周期转换采用**时间窗口聚合**，而非简单按根数聚合
   - **窗口范围**：时间窗口采用**左闭右开**规则，即 `[T, T+period)`，包含起始时间，不包含结束时间
   - **1m → 5m 示例**：
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
2. 在周期转换函数的注册机制中，明确每个转换对的对齐规则

---

#### 缺陷7：`end_time` 类型与现有 `Bar.datetime` 类型不兼容

**位置**: PeriodData.get_snapshot `end_time: pd.Timestamp` vs `Bar.datetime: datetime.datetime`

`get_snapshot` 要求 `pd.Timestamp`，但回测数据流中传入的是 `bar.datetime`（`datetime.datetime` 类型）。虽然 pd.Timestamp 可以接受 datetime 构造，但这是一个隐式依赖。

**建议**: 将参数类型标注为 `Union[pd.Timestamp, datetime]` 或在 docstring 中说明接受 datetime。

**修改建议**:
1. 将所有接受时间参数的方法（`get_snapshot`、`get_events`、`append_event` 等）的类型标注改为 `Union[pd.Timestamp, datetime.datetime]`
2. 在 docstring 中明确说明接受 `datetime.datetime` 或 `pd.Timestamp`
3. 在方法实现中，内部统一转换为 `pd.Timestamp` 处理

---

#### 缺陷8：指标懒加载写回机制未定义

**位置**: 第954-960行

当通过 `PeriodDataView.get_indicator()` 访问指标时，懒加载计算应该在哪里触发？计算结果写回哪里？
- 如果视图触发计算，就需要持有对 PeriodData 的引用，破坏了视图的只读性
- 如果只在视图上计算，其他策略无法复用结果，失去共享意义

文档说"后面的策略自动复用"，暗示计算结果会持久化到 PeriodData，但设计上没有明确触发点。

**建议**: 明确懒加载计算只在 DataFeed 层触发，视图是纯只读，不持有对 PeriodData 的引用。

**修改建议**:
1. 选择方案：**懒加载计算只在 DataFeed 层触发，PeriodDataView 是纯只读逻辑视图**
2. 修改 Q3 说明：
   - 指标计算的触发点是 `DataFeed.get_data()`（或 `build_context()`），而非 `PeriodDataView.get_indicator()`
   - `PeriodDataView` 是纯只读对象，不持有对 PeriodData 的引用，不触发任何计算
   - 当调用 `DataFeed.get_data()` 时，先检查该周期的所有注册指标是否已计算，未计算的先计算并写入 `PeriodData._df`
   - 计算过程受 `DataFeed._lock` 保护，保证并发安全
   - PeriodDataView 是逻辑视图，通过时间戳/索引范围访问原始数据，不复制数据
3. 修改 `PeriodDataView.get_indicator()` 的 docstring，明确说明如果指标不存在返回 None
4. 在 `PeriodDataView` 中保存对原始 DataFrame 的引用和视图范围信息，而不是复制数据
5. 因为是 Append-Only 数据，历史数据不会被修改，逻辑视图是安全的

---

### 模糊不清的问题

#### 模糊1：多策略场景下的调度顺序

文档设计了多策略共享 DataFeed 的机制，但没有说明两个策略的 `update_bar` / `get_snapshot` / `on_bar` 的调用顺序。单线程回测虽然不会出现竞态，但策略A更新后策略B能否正确拿到数据取决于 Engine 的实现顺序。

**修改建议**:
1. 在文档中新增"多策略调度规则"小节，明确说明：
   - 在单线程回测场景下，Engine 按以下顺序执行：
     1. 调用 `DataFeed.update_bar()` 更新数据
     2. 依次为每个策略构造 `BarContext` 并调用 `on_bar()`
   - 所有策略共享同一个 DataFeed，后执行的策略可以看到前序策略执行期间没有修改的数据（因为是 append-only）
   - 策略之间不应该有依赖关系，假设它们是独立决策的

---

#### 模糊2：指标列名生成规则不完整

`sma(period=10) → sma_10` 的规则只覆盖了单参数场景。对于 `bbands(period=20, std=2)` 应该生成什么列名？不同参数顺序是否影响列名？如果 `func_a(x=1, y=2)` 和 `func_a(y=2, x=1)` 生成不同列名但逻辑相同，会导致重复计算。

**建议**: 定义指标列名的规范化规则（如参数按参数名排序拼接）。

**修改建议**:
1. 在 3.5 节中新增"指标列名生成规则"小节，详细说明：
   - 列名格式：`{indicator_name}_{param1_value}_{param2_value}_...`
   - 参数按参数名字母顺序排序后拼接
   - 参数值使用字符串表示，特殊字符转义
   - 示例：
     - `sma(period=10)` → `sma_10`
     - `bbands(period=20, std=2)` → `bbands_20_2`
     - `func_a(y=2, x=1)` → `func_a_1_2`（因为 x 按字母顺序在 y 前面）
2. 在 `register_indicator` 的 docstring 中引用此规则

---

#### 模糊3：事件归属K线的时间范围规则

`update_bar(bar, period, events)` 的 events 是"归属于这根 K线 时间范围内的事件"。但事件可能发生在K线的任意时刻，且事件的时间戳精度可能高于K线粒度。这个"归属"的匹配规则是什么？按K线的 `[open_time, close_time)` 区间完全包含事件时间？

**建议**: 明确定义事件归属的时间窗口对齐规则。

**修改建议**:
1. 在 Q4 或事件相关章节中新增"事件时间归属规则"小节，明确说明：
   - K线时间戳表示周期开始时间，周期持续时间由周期名称决定（如 1m 表示 60 秒）
   - K线的时间区间为 `[bar.datetime, bar.datetime + period_duration)`
   - 事件时间戳落在该区间内即归属于该K线
   - 事件时间戳精度可以高于K线精度（如毫秒级事件归属到秒级K线）
   - 边界情况：事件时间戳等于 K线结束时间的，归属到下一根 K线
   - 事件分为两类：
     - 全局事件（`period=None`）：归属于时间范围内所有周期的 K线
     - 周期特定事件（`period="1m"` 等）：只归属于对应周期的 K线

---

#### 模糊4：数据视图的 `get_indicator` 能否触发计算

`PeriodData.get_indicator()` 可能触发懒加载，但 `PeriodDataSnapshot`（应该改名为 `PeriodDataView`）是只读视图。如果视图不包含某指标，调用 `view.get_indicator()` 应该返回 None 还是触发计算？如果触发计算，计算写回哪里？

**建议**: 明确视图是纯只读，不触发任何计算，指标不存在就返回 None。

**修改建议**:
1. 将 `PeriodDataSnapshot` 重命名为 `PeriodDataView`，更准确地反映它是一个逻辑视图而不是数据副本
2. 在 3.3 节 `PeriodDataView` 的设计目标中明确说明："纯只读对象，不触发任何计算，是原始数据的逻辑视图，不复制数据"
3. 在 `PeriodDataView.get_indicator()` 的 docstring 中明确说明：如果指标不存在返回 None
4. 在缺陷8的修改中同步说明此设计决策
5. 因为是 Append-Only 数据，历史数据不会被修改，逻辑视图是安全的

---

#### 模糊5：`data_requirements` 格式中 `"bars"` 字段的语义

```python
"5m": {"bars": 50}
```

`"bars": 50` 是什么意思？是 `get_snapshot` 的 `periods` 参数值？还是策略需要保证至少有50根K线？还是缓存大小上限？文档没有定义 `data_requirements` 的完整 schema。此外，`data_requirements` 的返回类型标注为 `dict`，过于宽泛。

**修改建议**:
1. 在新增的 4.8 节中，完整定义 `data_requirements` 的 schema：
   ```python
   @dataclass
   class PeriodRequirements:
       lookback_bars: int  # get_snapshot 的 lookback_bars 参数
       min_bars: Optional[int] = None  # 策略需要的最小K线数（可选）

   @dataclass
   class IndicatorRequirements:
       name: str
       params: dict[str, Any]

   @dataclass
   class DataRequirements:
       periods: dict[str, PeriodRequirements]  # key: 周期名
       indicators: dict[str, list[IndicatorRequirements]]  # key: 周期名
       events: bool = False  # 是否需要事件数据
   ```
2. 更新策略示例，使用结构化的类型
3. 明确 `"bars": 50` 等价于 `lookback_bars: 50`

---

#### 模糊6：`data_requirements` 中没有事件的声明入口

需求分析中事件是核心需求（需求5），但 `data_requirements` 示例只有 `periods` 和 `indicators`。策略如何声明需要事件数据？是所有注册了周期的策略都自动获得事件，还是需要显式声明？

**修改建议**:
1. 在 `data_requirements` 的 schema 中新增 `events` 配置，支持更精细的控制：
   ```python
   @dataclass
   class DataRequirements:
       periods: dict[str, PeriodRequirements]  # key: 周期名
       indicators: dict[str, list[IndicatorRequirements]]  # key: 周期名
       events: Union[bool, list[Optional[str]]] = False  # True: 所有事件; False: 无事件; 列表: 指定周期的事件 + 全局事件
   ```
2. 更新策略示例，展示不同场景：
   ```python
   # 场景1: 需要所有事件
   def data_requirements(self) -> DataRequirements:
       return DataRequirements(
           periods={...},
           indicators={...},
           events=True
       )
   
   # 场景2: 只需要全局事件和 1m 周期的特定事件
   def data_requirements(self) -> DataRequirements:
       return DataRequirements(
           periods={...},
           indicators={...},
           events=[None, "1m"]  # None 表示全局事件
       )
   ```
3. 更新 `build_context` 的行为：根据 `requirements.events` 配置筛选事件

---

#### 模糊7：`IndicatorCalcMode.INCREMENTAL` 的输入范围

INCREMENTAL 模式下，计算函数收到的输入是什么——只有最新增加的一行数据，还是整个 DataFrame 但标记了上次计算到哪一行？如果只有新增行，像 SMA 这类需要历史值的指标无法增量计算（因为没有历史上下文）。

**建议**: 定义增量计算函数的输入签名，明确是否传递历史数据或计算状态。

**修改建议**:
1. 在 3.5 节中新增"增量计算函数签名"小节，明确说明：
   - INCREMENTAL 模式的指标函数签名：
     ```python
     def incremental_indicator_func(
         df: pd.DataFrame,  # 完整的 DataFrame
         last_calc_idx: Optional[int],  # 上次计算到的行索引（None 表示第一次计算）
         **params
     ) -> pd.Series
     ```
   - `last_calc_idx` 表示上次计算结束的位置（包含），增量计算只需计算 `last_calc_idx + 1` 到当前末尾
   - 返回完整的指标 Series（长度与 df 相同），已计算的部分保持不变
   - 对于需要历史状态的指标（如 SMA），可以从 `df` 中获取完整历史，不需要额外保存状态
2. 更新 Q3 中的相关说明

---

#### 模糊8：`mock_snapshot` 测试构造缺少便利工具

测试示例中直接使用了 `mock_snapshot`，但没有提供方便构造 `PeriodDataSnapshot` 的方法。直接构造需要准备完整的 DataFrame，对单测来说成本较高。建议提供一个 `SnapshotBuilder` 或 `make_snapshot(bars: List[Bar], end_time)` 辅助函数。

**修改建议**:
1. 在 4.6 节或新增的 4.9 节中，定义测试辅助工具：
   ```python
   def make_snapshot(
       bars: List[Bar],
       end_time: Union[pd.Timestamp, datetime.datetime],
       lookback_bars: Optional[int] = None,
       indicators: Optional[dict[str, list[float]]] = None,
       events: Optional[List[Event]] = None
   ) -> PeriodDataSnapshot:
       """
       构造测试用的 PeriodDataSnapshot
       
       Args:
           bars: K线列表
           end_time: 快照截止时间
           lookback_bars: 往前多少根K线（None 表示全部）
           indicators: 指标数据，key 为指标名，value 为值列表（与 bars 对齐）
           events: 事件列表
       """
       # 实现细节...
   ```
2. 更新测试示例，使用 `make_snapshot` 构造 mock 数据

---


