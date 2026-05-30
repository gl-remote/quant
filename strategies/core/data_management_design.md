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
- 统一管理该周期的 **K线、指标、事件** 三类数据
- 提供截止周期镜像，策略只能看到指定时间点之前的数据
- 支持数据追加
- 底层存储使用 Pandas DataFrame

#### 3.2.2 核心功能
1. 数据存储：持有该周期的 K线+指标（合并DataFrame） + 事件数据
2. 数据访问：通过时间/索引获取 Bar、指标、事件
3. 数据追加：追加新的 K线、指标、事件数据
4. 截止周期镜像：获取截止指定时间点的数据快照，不包含后面的数据

#### 3.2.3 数据结构
```python
class PeriodData:
    # K线数据（OHLCV） + 指标数据（合并在一起，索引统一为datetime）
    _df: pd.DataFrame
    # 事件数据，单独管理（稀疏数据），按timestamp索引
    _events: pd.DataFrame
    _latest_time: Optional[pd.Timestamp]  # 最新数据时间
```

#### 3.2.4 函数签名
```python
class PeriodData:
    def __init__(self, period: str):
        """
        初始化单个周期的数据容器

        初始化过程：
        1. 创建空的K线+指标DataFrame，包含datetime, open, high, low, close, volume列
        2. 创建空的事件DataFrame
        3. 初始化状态变量

        :param period: 周期名称，如 "1m", "5m", "1h", "1d" 等
        """
        pass

    def append_bars(self, bars: List[Bar]) -> None:
        """
        批量追加K线数据（用于回测初始化）

        注意事项：
        1. 必须按时间升序排列
        2. 时间戳不能与已有的数据重复

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

    # --- 事件相关方法 ---

    def append_event(self, event: Event) -> None:
        """
        追加事件数据

        :param event: 事件对象
        """
        pass

    def append_events(self, events: List[Event]) -> None:
        """
        批量追加事件数据

        :param events: 事件列表
        """
        pass

    def get_events(self, start_time: Optional[pd.Timestamp] = None, 
                   end_time: Optional[pd.Timestamp] = None,
                   event_type: Optional[str] = None) -> List[Event]:
        """
        获取指定时间范围内的事件

        :param start_time: 开始时间（可选）
        :param end_time: 结束时间（可选）
        :param event_type: 事件类型（可选）
        :return: 事件列表
        """
        pass

    def get_events_at_bar(self, bar_idx: int) -> List[Event]:
        """
        获取指定K线对应的所有事件

        :param bar_idx: K线索引
        :return: 该K线时间范围内的事件列表
        """
        pass

    # --- 快照方法 ---

    def get_snapshot(self, end_time: pd.Timestamp, periods: int = 1) -> PeriodDataSnapshot:
        """
        获取截止指定时间点的数据快照（只读，用于策略安全访问）

        快照特性：
        1. 只包含截止到end_time的数据，不包含之后的未来数据
        2. 只读访问，策略无法修改原始数据
        3. 不受后续数据更新影响，保证数据一致性
        4. 可指定需要的历史周期数，节省内存
        5. 包含 K线、指标、事件 三类数据

        实现：使用 Pandas 切片 + copy，几千周期完全没问题

        :param end_time: 截止时间，快照将只包含<=此时间的数据
        :param periods: 需要的历史周期数，从end_time往前数，默认1个周期
        :return: PeriodDataSnapshot只读快照对象
        :raises ValueError: 如果end_time晚于最新数据时间
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

    def get_bar_by_time(self, time: pd.Timestamp) -> Optional[Bar]:
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
    def has_events(self) -> bool:
        """是否有事件数据"""
        pass
```

---

### 3.3 PeriodDataSnapshot（快照类，只读）

#### 3.3.1 设计目标
- 只读数据快照，防止策略修改数据
- 只包含截止指定时间点的数据
- 不受后续数据更新影响
- 实现简单：Pandas 切片 + copy，几千周期没问题

#### 3.3.2 函数签名
```python
class PeriodDataSnapshot:
    def __init__(self, df: pd.DataFrame, events: pd.DataFrame, end_time: pd.Timestamp):
        """
        初始化数据快照（内部使用，不应直接构造）

        :param df: 截止到end_time的K线+指标DataFrame
        :param events: 截止到end_time的事件DataFrame
        :param end_time: 快照的截止时间
        """
        pass

    def get_bar(self, idx: int) -> Optional[Bar]:
        """
        通过索引获取K线

        :param idx: 索引位置，支持负索引
        :return: Bar对象，索引越界返回None
        """
        pass

    def get_indicator(self, name: str, idx: int) -> Optional[float]:
        """
        通过索引获取指标值

        :param name: 指标名称，如 "sma_10"
        :param idx: 索引位置，支持负索引
        :return: 指标值，索引越界或指标不存在返回None
        """
        pass

    def get_events(self) -> List[Event]:
        """获取快照时间范围内的所有事件"""
        pass

    def get_all_bars(self) -> pd.DataFrame:
        """获取快照中所有K线+指标DataFrame（只读）"""
        pass

    @property
    def end_time(self) -> pd.Timestamp:
        """获取快照的截止时间"""
        pass

    @property
    def length(self) -> int:
        """获取快照中K线数量"""
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


