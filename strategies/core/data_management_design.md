# 量化策略数据管理方案设计

## 一、需求分析

### 1.1 核心需求
1. K线数据管理：维护策略运行过程中接收到的K线数据历史
2. 多周期支持：同时管理多个不同周期的K线表格（如1分钟、3分钟、5分钟等）
3. 逐根更新：模拟实盘场景，支持一根一根追加K线（更新对应周期）
4. 指标计算：使用成熟第三方库计算指标
5. 事件数据管理：支持事件数据（大单成交、新闻等），与K线、指标一起管理
6. 多策略共享：不同策略可以使用不同周期组合，共享的周期数据和指标只存一份
7. 并发安全：行级锁，只锁正在更新的周期，之前的数据可以安全读
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
5. 支持周期转换：可以从1分钟周期算出5分钟周期K线
6. 计算统一调度：来一根K线后，DataFeed 调度所有相关计算，算好后才对外提供数据
7. 行级锁并发：只在 DataFeed 级别加锁，只锁正在更新的周期，之前的数据可以安全读
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
- 行级锁并发控制（只在 DataFeed 级别加锁）
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
    _updating_time: Optional[pd.Timestamp] = None  # 正在更新的时间，用于行级锁判断

    # --- 指标注册配置 ---
    # 为每个周期注册需要计算的指标（指标名 + 参数）
    # 计算时自动生成列名，如 "sma_10", "ema_20"
    _registered_indicators: Dict[str, List[Tuple[str, dict]]]
```

---

### 3.5 模块级指标函数与周期转换函数

```python
# ==========================================
# 模块级指标计算函数注册（所有 DataFeed 共享）
# ==========================================

_REGISTERED_INDICATOR_FUNCS: Dict[str, Callable] = {}

def register_indicator_func(name: str, func: Callable) -> None:
    """全局注册指标计算函数，所有 DataFeed 共享

    指标计算函数签名要求：
    def indicator_func(df: pd.DataFrame, **params) -> pd.Series

    :param name: 指标名称
    :param func: 计算函数
    """
    _REGISTERED_INDICATOR_FUNCS[name] = func


# ==========================================
# 模块级周期转换函数注册（所有 DataFeed 共享）
# ==========================================

_REGISTERED_CONVERTERS: Dict[Tuple[str, str], Callable] = {}

def register_period_converter(source_period: str, target_period: str, func: Callable) -> None:
    """全局注册周期转换函数

    转换函数签名要求：
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

        每次update_bar或calculate_all时，会自动计算所有注册的指标

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
        更新一根K线，调度所有相关计算（核心方法，线程安全）

        执行流程（全程持有全局锁）：
        1. 锁定并记录当前正在更新的时间
        2. 更新对应周期的PeriodData（追加K线 + 可选事件）
        3. 计算该周期的所有注册指标，追加到PeriodData
        4. 检查是否触发周期转换（如1分钟累计够5根生成新的5分钟K线）
        5. 如果触发，调用转换函数生成高级周期K线
        6. 对生成的高级周期K线，同样计算其所有注册指标
        7. 清除正在更新的时间标记，解锁

        :param bar: 新K线数据
        :param period: 对应周期名称
        :param events: 本次更新对应的事件（可选）
        :raises KeyError: 如果周期未注册
        """
        pass

    def calculate_all(self) -> None:
        """
        批量预计算所有周期的所有指标（用于回测初始化）

        适用场景：
        - 回测开始前，所有历史数据已加载
        - 一次性计算所有需要的指标

        注意：
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

## 四、Strategy 使用 DataFeedCache

### 4.1 Strategy 直接使用全局 Cache（无需持有成员）
```python
class Strategy:
    # 不需要 _data_feed 成员变量了！

    def on_bar(self, bar: Bar):
        # 直接从全局 Cache 获取数据
        cache = DataFeedCache.get_instance()
        snapshot = cache.get_snapshot("btc_usdt", "5m", bar.datetime, periods=20)
        sma10 = snapshot.get_indicator("sma_10", -1)
        # 获取事件
        events = snapshot.get_events()
        # ...
```

### 4.2 测试时注入 mock Cache
```python
# 测试代码
def test_strategy():
    # 1. 创建 mock cache
    mock_cache = MockDataFeedCache()

    # 2. 注入到全局
    DataFeedCache.set_instance(mock_cache)

    # 3. 运行策略
    strategy = MyStrategy()
    strategy.on_bar(test_bar)

    # 4. 清理
    DataFeedCache.set_instance(None)
```

### 4.3 应用场景说明
- **运行时**：直接用 `DataFeedCache.get_instance()` 获取全局单例，天然共享数据
- **测试时**：用 `DataFeedCache.set_instance()` 注入 mock 或测试用的 cache
- Bridge 直接通过 DataFeedCache 更新数据，策略直接从 DataFeedCache 读取数据

---

## 五、使用流程

### 5.1 初始化阶段（回测前）
```python
# 1. 获取全局 Cache
cache = DataFeedCache.get_instance()

# 2. 创建或获取 DataFeed（按 symbol）
data_feed = cache.get_or_create("btc_usdt")

# 3. 注册所有需要的周期
data_feed.register_period("1m")
data_feed.register_period("5m")

# 4. 注册需要计算的指标（指标名 + 参数）
data_feed.register_indicator("5m", "sma", period=10)  # 生成 "sma_10"
data_feed.register_indicator("5m", "sma", period=20)  # 生成 "sma_20"
data_feed.register_indicator("5m", "ema", period=20)  # 生成 "ema_20"

# 5. 加载历史数据 + 预计算
data_feed.load_history_data("1m", bars_1m, events_1m)
data_feed.load_history_data("5m", bars_5m, events_5m)
data_feed.calculate_all()  # 一次性算完所有指标！
```

### 5.2 回测运行阶段
```python
# Bridge 遍历主周期数据，通过 Cache 更新
for bar, events in zip(bars_1m, event_groups):
    cache.update_bar("btc_usdt", bar, "1m", events)
    # 调用策略 on_bar
    strategy.on_bar(bar)

# 策略直接从 Cache 获取数据
def on_bar(self, bar):
    cache = DataFeedCache.get_instance()
    snapshot = cache.get_snapshot("btc_usdt", "5m", bar.datetime, periods=20)
    sma10 = snapshot.get_indicator("sma_10", -1)
    events = snapshot.get_events()
```

### 5.3 数据锚定方式说明
```
数据访问链路（O(1)复杂度）：
DataFeedCache（symbol → DataFeed）
    ↓
DataFeed（period → PeriodData）
    ↓
PeriodData（数据访问）

使用示例：
cache = DataFeedCache.get_instance()
snapshot = cache.get_snapshot("btc_usdt", "5m", time)
```

---

## 六、重要问题的解决方案总结

| 问题 | 解决方案 |
|------|----------|
| K线与指标分离还是合并？ | **合并**：K线+指标放一个DataFrame，索引统一，简单高效 |
| 指标与事件如何管理？ | K线+指标合并，事件单独管理，都在PeriodData内部 |
| 周期不同步问题？ | **回测前统一注册所有指标**，一次性预计算calculate_all() |
| Callable是函数还是钩子类？ | **简单函数**，模块级注册，所有DataFeed共享 |
| 数据存哪里？ | PeriodData内部统一管理，DataFeed只做调度 |
| _indicator_funcs是否每个DataFeed注册？ | **不需要**，模块级注册一次，所有DataFeed共享 |
| DataFeedCache需要锁吗？ | **不需要**，DataFeedCache只做路由，锁在DataFeed级别 |
| 快照如何实现？ | **Pandas切片 + copy**，几千周期没问题，不需要复杂函数式 |
| source参数需要吗？ | 可选，可从symbol解析（如"CZCE.sr509" → source="CZCE"） |
| 事件数据是核心吗？ | **是**，完整支持Event类型，与K线/指标一起管理 |
| 谁来调用DataFeedCache.update_bar？ | **Bridge或回测引擎**，策略只调用get_snapshot |

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
7. **避免重复计算**：指标预计算一次，多策略共享
8. **指标函数模块级注册**：避免每个DataFeed重复注册
9. **截止周期镜像**：策略只能看到指定时间点之前的数据，安全可靠
10. **行级锁并发**：只在DataFeed级别加锁，只锁正在更新的周期，之前的数据可以安全读
11. **代码简洁**：策略不需要维护状态，直接拿指标用
12. **测试友好**：支持mock注入
13. **向后兼容**：不影响现有策略
