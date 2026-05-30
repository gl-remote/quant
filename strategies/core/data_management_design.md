# 量化策略数据管理方案设计

## 一、需求分析

### 1.1 核心需求
1. K线数据管理：维护策略运行过程中接收到的K线数据历史
2. 多周期支持：同时管理多个不同周期的K线表格（如1分钟、3分钟、5分钟等）
3. 逐根更新：模拟实盘场景，支持一根一根追加K线（更新对应周期）
4. 指标计算：使用成熟第三方库计算指标
5. 多策略共享：不同策略可以使用不同周期组合，共享的周期数据和指标只存一份
6. 并发安全：行级锁，只锁正在更新的周期，之前的数据可以安全读
7. 截止周期镜像：策略只能看到指定周期及之前的数据，不受后面数据干扰
8. 简易实现：优先考虑代码简洁、易理解
9. 回测场景：只考虑几千个周期的回测

### 1.2 现有问题
1. 每个策略自己维护数据缓存（如_close_history）
2. 多个策略回测相同数据时，指标重复计算
3. 没有统一的数据管理接口，每个策略重复实现类似逻辑
4. 不支持多周期数据统一管理

---

## 二、总体架构设计

### 2.1 核心组件
只需新增一个文件：strategies/core/data_feed.py

核心类：
1. PeriodData（数据类）：单个周期的表格，纯存数据，提供截止周期镜像
2. DataFeed（管理类）：管理多个 PeriodData 实例，负责调度计算
3. DataFeedCache（上层缓存类）：单例模式，管理多个 DataFeed 实例，区分不同数据源（核心组件）

### 2.2 设计原则
1. 使用 Pandas + pandas-ta 或 ta-lib 计算指标（成熟第三方库）
2. 职责分离：
   - DataFeed（管理类）：负责 update_bar 调度计算、管理计算函数、处理周期转换
   - PeriodData（数据类）：纯存数据，提供截止周期镜像，不负责计算
3. 多周期表格管理：一个 DataFeed 管理多个周期的 K线和指标
4. 周期共享：策略A用1、3、5周期，策略B用2、4、5周期，5周期数据共享
5. 支持周期转换：可以从1分钟周期算出5分钟周期K线
6. 计算统一调度：来一根K线后，DataFeed 调度所有相关计算，算好后才对外提供数据
7. 行级锁并发：只锁正在更新的周期，之前的数据可以安全读
8. 截止周期镜像：提供快照功能，策略只能看到指定周期及之前的数据
9. 保持现有架构兼容，最小化改动

---

## 三、类详细设计

### 3.1 PeriodData（数据类，单个周期）

#### 3.1.1 设计目标
- 纯数据存储，不负责计算
- 提供截止周期镜像，策略只能看到指定时间点之前的数据
- 支持数据追加
- 底层存储可替换（可以是 Pandas DataFrame，也可以是第三方计算库）

#### 3.1.2 核心功能
1. 数据存储：持有该周期的 K线数据和指标数据
2. 数据访问：通过时间/索引获取 Bar 和指标
3. 数据追加：追加新的 K线和指标数据
4. 截止周期镜像：获取截止指定时间点的数据快照，不包含后面的数据

#### 3.1.3 数据结构
```python
class PeriodData:
    _df: pd.DataFrame  # K线数据（OHLCV）
    _indicators: pd.DataFrame  # 指标数据（可以和K线合并，待定）
    _latest_time: Optional[pd.Timestamp]  # 最新数据时间
    _updating_time: Optional[pd.Timestamp]  # 正在更新的时间（用于行级锁）
```

#### 3.1.4 函数签名
```python
class PeriodData:
    def __init__(self, period: str):
        """
        初始化单个周期的数据容器
        :param period: 周期名称，如 "1m", "5m"
        """
        pass

    def append_bars(self, bars: List[Bar]) -> None:
        """
        批量追加K线数据
        :param bars: K线列表
        """
        pass

    def append_bar(self, bar: Bar) -> None:
        """
        追加单根K线
        :param bar: K线数据
        """
        pass

    def append_indicators(self, indicators: pd.DataFrame) -> None:
        """
        追加指标数据
        :param indicators: 指标DataFrame，索引与K线对齐
        """
        pass

    def get_snapshot(self, end_time: pd.Timestamp, periods: int = 1) -> PeriodDataSnapshot:
        """
        获取截止指定时间点的数据快照
        :param end_time: 截止时间
        :param periods: 需要的历史周期数
        :return: 数据快照对象
        """
        pass

    def get_bar(self, idx: int) -> Optional[Bar]:
        """
        通过索引获取K线
        :param idx: 索引，-1表示最新
        :return: K线数据
        """
        pass

    def get_bar_by_time(self, time: pd.Timestamp) -> Optional[Bar]:
        """
        通过时间获取K线
        :param time: 时间戳
        :return: K线数据
        """
        pass

    def get_indicator(self, name: str, idx: int) -> Optional[float]:
        """
        通过索引获取指标值
        :param name: 指标名称，如 "sma_10"
        :param idx: 索引，-1表示最新
        :return: 指标值
        """
        pass

    def get_indicator_series(self, name: str) -> pd.Series:
        """
        获取指标完整序列
        :param name: 指标名称
        :return: 指标序列
        """
        pass

    @property
    def latest_time(self) -> Optional[pd.Timestamp]:
        """获取最新数据时间"""
        pass

    @property
    def length(self) -> int:
        """获取数据长度"""
        pass
```

---

### 3.2 DataFeed（管理类，多周期）

#### 3.2.1 设计目标
- 管理多个 PeriodData 实例
- 提供统一的 update_bar 入口，调度所有相关计算
- 管理计算函数（指标计算、周期转换）
- 行级锁并发控制
- 提供数据访问路由

#### 3.2.2 核心功能
1. 注册周期：创建并管理 PeriodData
2. 绑定计算函数：注册指标计算函数、周期转换函数
3. 注册指标：为指定周期注册需要计算的指标
4. update_bar 调度：来一根 K线后，更新对应周期，调度所有相关计算
5. 数据访问：通过周期名获取对应的 PeriodData

#### 3.2.3 数据结构
```python
class DataFeed:
    _periods: Dict[str, PeriodData]  # key: 周期名+参数(如果需要)，value: PeriodData
    _lock: threading.RLock  # 全局锁，用于行级锁控制
    _indicator_funcs: Dict[str, Callable]  # 指标名 -> 计算函数
    _period_converters: Dict[Tuple[str, str], Callable]  # (源周期, 目标周期) -> 转换函数
    _registered_indicators: Dict[str, List[Tuple[str, dict]]]  # 周期名 -> [(指标名, 参数)]
```

#### 3.2.4 并发控制
1. update_bar 时加锁，记录正在更新的时间
2. 读取时检查依赖周期是否小于正在更新的时间，小于则可以安全读
3. 计算完成后更新 latest_time，清除 updating_time

#### 3.2.5 函数签名
```python
class DataFeed:
    def __init__(self):
        """初始化数据管理器"""
        pass

    def register_period(self, period: str) -> PeriodData:
        """
        注册一个周期
        :param period: 周期名称，如 "1m", "5m"
        :return: PeriodData 实例
        """
        pass

    def bind_indicator_func(self, name: str, func: Callable) -> None:
        """
        绑定指标计算函数
        :param name: 指标名称，如 "sma"
        :param func: 计算函数，签名: func(df: pd.DataFrame, **params) -> pd.Series
        """
        pass

    def bind_period_converter(self, source_period: str, target_period: str, func: Callable) -> None:
        """
        绑定周期转换函数
        :param source_period: 源周期，如 "1m"
        :param target_period: 目标周期，如 "5m"
        :param func: 转换函数，签名: func(source_data: PeriodData) -> List[Bar]
        """
        pass

    def register_indicator(self, period: str, indicator_name: str, **params) -> None:
        """
        为指定周期注册需要计算的指标
        :param period: 周期名称
        :param indicator_name: 指标名称，如 "sma"
        :param params: 指标参数，如 period=10
        """
        pass

    def load_history_data(self, period: str, bars: List[Bar]) -> None:
        """
        批量加载历史数据
        :param period: 周期名称
        :param bars: 历史K线列表
        """
        pass

    def update_bar(self, bar: Bar, period: str) -> None:
        """
        更新一根K线，调度所有相关计算
        :param bar: K线数据
        :param period: 周期名称
        """
        # 伪代码流程：
        # with self._lock:
        #     1. 设置正在更新的时间
        #     2. 更新对应周期的PeriodData
        #     3. 计算该周期的所有注册指标
        #     4. 检查是否触发周期转换（如1分钟够5根了）
        #     5. 如果触发，转换生成高级周期K线并计算其指标
        #     6. 清除正在更新的时间，更新latest_time
        pass

    def calculate_all(self) -> None:
        """
        批量预计算所有周期的所有指标（用于回测初始化）
        """
        pass

    def get_period(self, period: str) -> Optional[PeriodData]:
        """
        获取指定周期的PeriodData
        :param period: 周期名称
        :return: PeriodData 实例
        """
        pass

    def get_snapshot(self, period: str, end_time: pd.Timestamp, periods: int = 1) -> Optional[PeriodDataSnapshot]:
        """
        获取指定周期截止指定时间的快照
        :param period: 周期名称
        :param end_time: 截止时间
        :param periods: 需要的历史周期数
        :return: 数据快照
        """
        # 检查依赖周期是否安全（不在更新中，或更新时间 > end_time）
        # 如果安全，返回PeriodData的snapshot
        pass
```

---

### 3.3 PeriodDataSnapshot（快照类，只读）

#### 3.3.1 设计目标
- 只读数据快照，防止策略修改数据
- 只包含截止指定时间点的数据
- 不受后续数据更新影响

#### 3.3.2 函数签名
```python
class PeriodDataSnapshot:
    def __init__(self, df: pd.DataFrame, indicators: pd.DataFrame, end_time: pd.Timestamp):
        pass

    def get_bar(self, idx: int) -> Optional[Bar]:
        pass

    def get_indicator(self, name: str, idx: int) -> Optional[float]:
        pass

    def get_all_bars(self) -> pd.DataFrame:
        pass

    def get_all_indicators(self) -> pd.DataFrame:
        pass

    @property
    def end_time(self) -> pd.Timestamp:
        pass

    @property
    def length(self) -> int:
        pass
```

---

### 3.4 DataFeedCache（上层缓存类，核心组件）

#### 3.4.1 设计目标
- 单例模式，全局唯一入口
- 管理多个 DataFeed 实例
- 根据数据源（如不同品种、不同交易所）区分不同的 DataFeed
- 支持策略测试时注入 mock 的 cache

#### 3.4.2 数据结构
```python
class DataFeedCache:
    _instance: Optional["DataFeedCache"] = None
    _datafeeds: Dict[str, DataFeed]  # key: 数据源标识，value: DataFeed
    _lock: threading.RLock
```

#### 3.4.3 函数签名
```python
class DataFeedCache:
    @classmethod
    def get_instance(cls) -> "DataFeedCache":
        """
        获取单例（运行时使用）
        :return: DataFeedCache 单例
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def set_instance(cls, instance: Optional["DataFeedCache"]) -> None:
        """
        设置单例（测试时用来注入 mock）
        :param instance: DataFeedCache 实例或 None
        """
        cls._instance = instance

    def get_or_create(self, source_id: str) -> DataFeed:
        """
        获取或创建DataFeed
        :param source_id: 数据源标识，如 "btc_usdt_binance"
        :return: DataFeed 实例
        """
        pass

    def update_bar(self, source_id: str, bar: Bar, period: str) -> None:
        """
        更新指定数据源的K线（路由到对应DataFeed）
        :param source_id: 数据源标识
        :param bar: K线数据
        :param period: 周期名称
        """
        pass

    def get_snapshot(self, source_id: str, period: str, end_time: pd.Timestamp, periods: int = 1) -> Optional[PeriodDataSnapshot]:
        """
        获取指定数据源、指定周期的快照
        :param source_id: 数据源标识
        :param period: 周期名称
        :param end_time: 截止时间
        :param periods: 需要的历史周期数
        :return: 数据快照
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

### 4.4 向后兼容
保持原有的 Strategy 接口完全不变，现有策略无需修改即可继续运行

---

## 五、使用流程

### 5.1 初始化阶段
```python
# 1. 获取全局 Cache
cache = DataFeedCache.get_instance()

# 2. 创建或获取 DataFeed
data_feed = cache.get_or_create("btc_usdt")

# 3. 注册所有需要的周期
data_feed.register_period("1m")
data_feed.register_period("5m")

# 4. 绑定计算函数
data_feed.bind_indicator_func("sma", sma_func)
data_feed.bind_indicator_func("ema", ema_func)
data_feed.bind_period_converter("1m", "5m", convert_1m_to_5m)

# 5. 注册需要计算的指标
data_feed.register_indicator("5m", "sma", period=10)
data_feed.register_indicator("5m", "sma", period=20)
data_feed.register_indicator("5m", "ema", period=20)

# 6. 策略不需要绑定数据！直接用全局 Cache
```

### 5.2 单策略多周期回测
```python
# 1. 获取 DataFeed 并批量加载历史数据
cache = DataFeedCache.get_instance()
data_feed = cache.get_or_create("btc_usdt")
data_feed.load_history_data("1m", bars_1m)
data_feed.load_history_data("5m", bars_5m)

# 2. 一次性预计算所有指标
data_feed.calculate_all()

# 3. Bridge 遍历主周期数据，通过 Cache 更新
for bar in bars_1m:
    cache.update_bar("btc_usdt", bar, "1m")
    # 调用策略 on_bar

# 4. 策略直接从 Cache 获取数据
def on_bar(self, bar):
    cache = DataFeedCache.get_instance()
    snapshot = cache.get_snapshot("btc_usdt", "5m", bar.datetime, periods=20)
    sma10 = snapshot.get_indicator("sma_10", -1)
```

### 5.3 多策略不同周期组合并行回测
```python
# 1. 初始化全局 Cache，一次性设置好所有数据
cache = DataFeedCache.get_instance()
data_feed = cache.get_or_create("btc_usdt")

# 2. 注册所有周期、绑定函数、注册指标、预计算
data_feed.register_period("1m")
data_feed.register_period("2m")
data_feed.register_period("3m")
data_feed.register_period("4m")
data_feed.register_period("5m")
# ... 绑定函数、注册指标、预计算 ...

# 3. 所有策略直接用同一个全局 Cache，天然共享数据！
# 不用 attach，不用传参，所有策略都能访问到相同的数据

# 4. 回测引擎并行运行（行级锁保证安全）
```

### 5.4 逐根更新模拟实盘
```python
# 1. 初始化全局 Cache
cache = DataFeedCache.get_instance()
data_feed = cache.get_or_create("btc_usdt")
# ... 注册周期、绑定函数、注册指标 ...

# 2. 从实时数据流接收 Bar，通过 Cache 更新
for bar in realtime_bars:
    # update_bar 内部加锁，调度所有计算
    cache.update_bar("btc_usdt", bar, "1m")
    
    # 3. 策略直接从 Cache 读取
    snapshot = cache.get_snapshot("btc_usdt", "5m", bar.datetime)
    sma10 = snapshot.get_indicator("sma_10", -1)
```

---

## 六、优势总结
1. 职责清晰：
   - PeriodData 纯存数据，提供快照，简单可靠
   - DataFeed 负责调度和计算，逻辑集中
2. 多周期支持：统一管理多个周期的数据和指标
3. 周期转换：支持从低级周期算出高级周期（1分钟→5分钟）
4. 共享机制：相同周期的数据和指标多策略共享，只存一份
5. 使用成熟库：pandas-ta 或 ta-lib，不需要自己写指标计算
6. 避免重复计算：指标预计算一次，多策略共享
7. 截止周期镜像：策略只能看到指定时间点之前的数据，安全可靠
8. 行级锁并发：只锁正在更新的周期，之前的数据可以安全读，性能更好
9. 代码简洁：策略不需要维护状态，直接拿指标用
10. 向后兼容：不影响现有策略
11. 可扩展：PeriodData 底层存储可替换，支持第三方计算库
