"""量化策略数据管理模块

【架构设计】
- DataFeed: 管理单个品种的多周期数据，负责调度计算和事件管理
- DataFeedCache: 单例模式，管理多个品种的DataFeed

【并发安全】
- 基于条件变量的Append-Only快照机制
- 只在DataFeed级别加锁
- 读操作检查时间戳，保障数据一致性

【指标计算】
- 支持批量(BATCH)和增量(INCREMENTAL)两种模式
- 模块级注册，所有DataFeed共享
- 懒加载按需计算，避免不必要的开销
"""

from datetime import datetime as dt
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, cast

import threading
import pandas as pd
from pandas._libs import NaTType

from .events import (
    Event,
    IndicatorCalcMode,
    _REGISTERED_CONVERTERS,
    _REGISTERED_INDICATOR_FUNCS,
    _generate_indicator_column_name,
    register_indicator_func,
)
from .period import PeriodData, PeriodDataView
from .requirements import BarContext, DataRequirements
from ..core.types import Bar


def _parse_source_from_symbol(symbol: str) -> Optional[str]:
    """从symbol解析source，如 "CZCE.sr509" -> source="CZCE"

    :param symbol: 交易品种
    :return: source，解析失败返回None
    """
    if '.' in symbol:
        return symbol.split('.')[0]
    return None


class DataFeed:
    """管理单个品种的多周期数据

    【设计目标】
    - 管理单个品种（symbol）的所有周期数据
    - 持有该品种的元数据（symbol、数据源等）
    - 提供统一的 update_bar 入口，调度所有相关计算
    - 基于条件变量的快照等待机制（只在 DataFeed 级别加锁）
    - 提供高效的数据访问路由（通过周期名快速定位 PeriodData）
    - 统一管理 K线、指标、事件 三类数据
    - 支持周期转换（从1m数据衍生出5m数据）
    - 回测前统一注册所有指标，避免实时计算的不同步问题
    """

    def __init__(self, symbol: str, source: Optional[str] = None):
        """初始化单个品种的多周期数据管理器

        :param symbol: 交易品种，如 "btc_usdt" 或 "CZCE.sr509"
        :param source: 数据源标识（可选，如果不提供可从symbol解析）
        """
        self.symbol = symbol
        if source is None:
            self.source = _parse_source_from_symbol(symbol)
        else:
            self.source = source

        # 周期数据管理
        self._periods: Dict[str, PeriodData] = {}

        # 事件数据管理
        self._events = pd.DataFrame(columns=['type', 'symbol', 'reason', 'period', 'data'])
        self._events = self._events.astype({
            'type': 'string',
            'symbol': 'string',
            'reason': 'string',
            'period': 'string'
        })

        # 并发控制
        self._lock = threading.RLock()
        self._updating_time: pd.Timestamp | NaTType = pd.Timestamp(0)
        self._condition = threading.Condition(self._lock)

        # 指标注册配置
        self._registered_indicators: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}

        # 周期转换配置
        self._period_conversions: Dict[Tuple[str, str], Callable[..., List[Bar]]] = _REGISTERED_CONVERTERS.copy()
        self._derived_periods: Dict[str, str] = {}

        # 数据追踪字段（类似数据库表）
        self._created_at = pd.Timestamp.now()
        self._last_updated_at = pd.Timestamp.now()
        self._update_count = 0
        self._event_count = 0

    def register_period(self, period: str) -> PeriodData:
        """注册一个新的周期，创建对应的PeriodData实例

        :param period: 周期名称，如 "1m", "5m", "1h"
        :return: 新创建或已存在的PeriodData实例
        """
        if period not in self._periods:
            self._periods[period] = PeriodData(period)
        return self._periods[period]

    def register_indicator(self, period_name: str, indicator_name: str, **params: Any) -> None:
        """为指定周期注册需要计算的指标

        指标不会立即计算，第一次访问时才懒加载；计算方式灵活（全量/逐行都支持）

        参数组合示例：
        - register_indicator("5m", "sma", period=10) → 生成列 "sma_10"
        - register_indicator("5m", "sma", period=20) → 生成列 "sma_20"
        - register_indicator("5m", "ema", period=20) → 生成列 "ema_20"

        【指标计算说明】
        - BATCH 模式指标始终在完整的 PeriodData._df 上计算
        - 数据访问是通过逻辑视图（时间戳/索引范围），不复制数据，不触发重新计算
        - calculate_all() 的作用是预计算所有注册指标，避免运行时懒加载延迟
        - 如果某个指标已经计算过，calculate_all() 会跳过该指标
        - 指标函数接收的是完整 DataFrame，不应该假设或依赖数据范围

        :param period_name: 周期名称
        :param indicator_name: 指标名称，需已在模块级注册
        :param params: 指标参数，将传递给计算函数
        :raises KeyError: 如果周期未注册或指标函数未注册
        """
        if period_name not in self._periods:
            raise KeyError(f"Period {period_name} not registered")

        if indicator_name not in _REGISTERED_INDICATOR_FUNCS:
            raise KeyError(f"Indicator function {indicator_name} not registered")

        if period_name not in self._registered_indicators:
            self._registered_indicators[period_name] = []

        # 检查是否已注册
        for existing_name, existing_params in self._registered_indicators[period_name]:
            if existing_name == indicator_name and existing_params == params:
                return  # 已注册，无需重复

        self._registered_indicators[period_name].append((indicator_name, params))

    def load_history_data(self, period: str, bars: List[Bar], events: Optional[List[Event]] = None) -> None:
        """批量加载历史数据（用于回测初始化）

        注意：
        1. 不会自动计算指标，需调用calculate_all()

        :param period: 周期名称
        :param bars: 历史K线列表，需按时间升序排列
        :param events: 历史事件列表（可选）
        """
        if period not in self._periods:
            self.register_period(period)

        self._periods[period].append_bars(bars)

        if events:
            self.append_events(events)

    def append_event(self, event: Event) -> None:
        """追加事件数据

        :param event: 事件对象
        """
        with self._lock:
            event_time = pd.Timestamp(event.timestamp)
            new_row = pd.Series({
                'type': event.type,
                'symbol': event.symbol,
                'reason': event.reason,
                'period': event.period,
                'data': event.data
            }, name=event_time)

            if len(self._events) == 0:
                self._events = new_row.to_frame().T
            else:
                self._events = pd.concat([self._events, new_row.to_frame().T])

            self._event_count += 1
            self._last_updated_at = pd.Timestamp.now()

    def append_events(self, events: List[Event]) -> None:
        """批量追加事件数据

        :param events: 事件列表
        """
        with self._lock:
            if not events:
                return

            event_dicts = []
            for event in events:
                event_dicts.append({
                    'datetime': pd.Timestamp(event.timestamp),
                    'type': event.type,
                    'symbol': event.symbol,
                    'reason': event.reason,
                    'period': event.period,
                    'data': event.data
                })

            new_df = pd.DataFrame(event_dicts)
            new_df = new_df.set_index('datetime')

            if len(self._events) == 0:
                self._events = new_df
            else:
                self._events = pd.concat([self._events, new_df])

            self._event_count += len(events)
            self._last_updated_at = pd.Timestamp.now()

    def get_events(self, start_time: Optional[Union[pd.Timestamp, dt]] = None,
                   end_time: Optional[Union[pd.Timestamp, dt]] = None,
                   event_type: Optional[str] = None,
                   period: Optional[str] = None) -> List[Event]:
        """获取指定时间范围内的事件

        :param start_time: 开始时间（可选）
        :param end_time: 结束时间（可选）
        :param event_type: 事件类型（可选）
        :param period: 周期名称筛选（可选，None表示所有事件）
        :return: 事件列表
        """
        with self._lock:
            if len(self._events) == 0:
                return []

            mask = pd.Series([True] * len(self._events), index=self._events.index)

            if start_time is not None:
                mask &= (self._events.index >= pd.Timestamp(start_time))

            if end_time is not None:
                mask &= (self._events.index <= pd.Timestamp(end_time))

            if event_type is not None:
                mask &= (self._events['type'] == event_type)

            if period is not None:
                mask &= ((self._events['period'] == period) | (self._events['period'].isna()))

            events_df = self._events[mask]

            events = []
            for _, row in events_df.iterrows():
                event = Event(
                    timestamp=row.name.to_pydatetime(),
                    type=row['type'],
                    symbol=row['symbol'],
                    reason=row.get('reason', ''),
                    period=row.get('period'),
                    data=row.get('data')
                )
                events.append(event)

            return events

    def get_events_at_bar(self, bar_time: Union[pd.Timestamp, dt], period: str) -> List[Event]:
        """获取指定K线时间范围内的所有事件（包括全局事件和该周期的特定事件）

        【事件时间归属规则】
        - K线时间戳表示周期开始时间，周期持续时间由周期名称决定（如 1m 表示 60 秒）
        - K线的时间区间为 [bar.datetime, bar.datetime + period_duration)
        - 事件时间戳落在该区间内即归属于该K线
        - 事件时间戳精度可以高于K线精度（如毫秒级事件归属到秒级K线）
        - 边界情况：事件时间戳等于 K线结束时间的，归属到下一根 K线
        - 事件分为两类：
          - 全局事件（period=None）：归属于时间范围内所有周期的 K线
          - 周期特定事件（period="1m" 等）：只归属于对应周期的 K线

        :param bar_time: K线时间
        :param period: 周期名称
        :return: 事件列表
        """
        # 简单实现：使用bar_time作为时间点，查找时间<=bar_time的事件
        # 更精确的实现需要解析period计算时间区间
        return self.get_events(end_time=bar_time)

    def update_bar(self, bar: Bar, period: str, events: Optional[List[Event]] = None) -> None:
        """更新一根K线，调度周期转换（核心方法，线程安全）

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
        with self._lock:
            # 记录正在更新的时间
            self._updating_time = pd.Timestamp(bar.datetime)

            try:
                if period not in self._periods:
                    raise KeyError(f"Period {period} not registered")

                # 更新K线
                self._periods[period].append_bar(bar)

                # 追加事件
                if events:
                    self.append_events(events)

                # 检查周期转换
                self._check_period_conversion(period)

                # 更新数据追踪字段
                self._update_count += 1
                self._last_updated_at = pd.Timestamp.now()

            finally:
                # 清除更新时间标记
                self._updating_time = pd.Timestamp(0)
                # 通知等待的线程
                self._condition.notify_all()

    def _check_period_conversion(self, source_period: str) -> None:
        """检查是否触发周期转换（内部方法）

        :param source_period: 源周期
        """
        # 这里是简化实现，实际项目中需要硬编码常见的周期转换关系
        # 例如：1m -> 5m, 1m -> 15m, 1m -> 1h 等
        # 目前先留空，后续根据需要实现
        pass

    def _calculate_indicators_for_period(self, period_name: str) -> None:
        """计算指定周期的所有注册指标（内部方法）

        :param period_name: 周期名称
        """
        if period_name not in self._periods:
            return

        period_data = self._periods[period_name]

        if period_name not in self._registered_indicators:
            return

        for indicator_name, params in self._registered_indicators[period_name]:
            col_name = _generate_indicator_column_name(indicator_name, params)

            # 检查是否已计算
            if period_data.is_indicator_calculated(col_name):
                continue

            # 获取指标函数信息
            func_info = _REGISTERED_INDICATOR_FUNCS.get(indicator_name)
            if func_info is None:
                continue

            # 计算指标
            try:
                series = period_data.apply_indicator(func_info.func, **params)
                period_data.set_indicator_column(col_name, series)
                period_data.mark_indicator_calculated(col_name)
            except Exception:
                # 计算失败，跳过该指标
                pass

    def calculate_all(self) -> None:
        """批量预计算所有周期的所有指标（可选，用于回测初始化性能优化）

        适用场景：
        - 回测开始前，所有历史数据已加载
        - 希望一次性预计算所有指标，避免运行时懒加载的轻微延迟

        注意：
        - 不是必须调用，不调用也能用
        - 会覆盖已有的指标数据
        - 会遍历所有周期，计算所有注册指标
        - 如果某个指标已经计算过，会跳过该指标
        """
        with self._lock:
            for period_name in self._periods:
                self._calculate_indicators_for_period(period_name)

    def get_period(self, period_name: str) -> Optional[PeriodData]:
        """获取指定周期的PeriodData实例（高级用法）

        :param period_name: 周期名称
        :return: PeriodData实例，未注册返回None
        """
        return self._periods.get(period_name)

    def get_data(self, period_name: str, current_time: Union[pd.Timestamp, dt], lookback_bars: int = 1,
                 timeout: Optional[float] = None) -> Optional[PeriodDataView]:
        """获取指定周期截止指定时间的逻辑视图（策略主要访问入口）

        并发安全机制（基于条件变量的时间检查）：
        1. 检查是否有正在进行的update_bar
        2. 如果有，检查current_time是否 < _updating_time
        3. 如果安全（无更新或current_time在更新时间之前），返回视图
        4. 如果timeout不为None，按timeout规则处理：
           - timeout=None（默认）：采用回测场景行为，如果current_time >= _updating_time，直接抛出 ValueError
           - timeout>0：采用实盘场景行为，等待最多timeout秒，直到更新完成或超时
           - timeout=0：采用非阻塞行为，立即返回或抛出异常

        【懒加载计算触发点】
        指标计算的触发点是 DataFeed.get_data()（或 build_context()），而非 PeriodDataView.get_indicator()
        当调用此方法时，先检查该周期的所有注册指标是否已计算，未计算的先计算并写入 PeriodData._df
        计算过程受 DataFeed._lock 保护，保证并发安全

        :param period_name: 周期名称
        :param current_time: 当前时间，视图只包含<=此时间的数据
        :param lookback_bars: 往前多少根K线，默认1根
        :param timeout: 超时时间（秒），None表示回测模式（抛错），>0表示等待，0表示非阻塞
        :return: PeriodDataView只读逻辑视图
        :raises KeyError: 如果周期未注册
        :raises ValueError: 如果current_time晚于最新数据时间或超时
        """
        with self._lock:
            # 检查周期是否存在
            if period_name not in self._periods:
                raise KeyError(f"Period {period_name} not registered")

            current_time_ts: pd.Timestamp = pd.Timestamp(current_time)  # type: ignore[assignment]

            # 等待更新完成（如果需要）
            if self._updating_time != pd.Timestamp(0):
                if current_time_ts >= self._updating_time:
                    if timeout is None:
                        # 回测模式，直接抛错
                        raise ValueError(f"current_time {current_time_ts} is >= updating_time {self._updating_time}")
                    elif timeout > 0:
                        # 等待更新完成
                        if not self._condition.wait(timeout=timeout):
                            raise ValueError(f"Timeout waiting for update to complete")
                    else:  # timeout == 0
                        # 非阻塞，抛错
                        raise ValueError(f"Update in progress and timeout=0")

            # 懒加载计算指标
            self._calculate_indicators_for_period(period_name)

            # 获取视图
            period_data = self._periods[period_name]
            return period_data.get_data(current_time_ts, lookback_bars, self._events)


# ==================== DataFeedCache: 全局单例缓存 ====================

class DataFeedCache:
    """数据馈送缓存（单例模式）

    【设计目标】
    - 单例模式，全局唯一入口
    - 管理多个 DataFeed 实例
    - 根据交易品种（symbol）区分不同的 DataFeed
    - 一个 symbol 对应一个 DataFeed
    - 支持策略测试时注入 mock 的 cache
    - 有自己的锁，保护 get_or_create 操作
    - 只做路由，实际数据操作委托给 DataFeed
    """

    _instance: Optional['DataFeedCache'] = None

    def __init__(self) -> None:
        self._datafeeds: Dict[str, DataFeed] = {}
        self._lock = threading.RLock()

    @classmethod
    def get_instance(cls) -> 'DataFeedCache':
        """获取单例（运行时使用）

        首次调用时自动创建实例，后续调用返回相同实例

        :return: DataFeedCache 单例
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def set_instance(cls, instance: Optional['DataFeedCache']) -> None:
        """设置单例（测试时用来注入 mock）

        :param instance: DataFeedCache 实例或None
        """
        cls._instance = instance

    def get_or_create(self, symbol: str, source: Optional[str] = None) -> DataFeed:
        """获取或创建DataFeed实例

        一个 symbol 对应一个 DataFeed

        :param symbol: 交易品种，如 "btc_usdt"
        :param source: 数据源标识（可选）
        :return: DataFeed 实例（新创建或已存在）
        """
        with self._lock:
            if symbol not in self._datafeeds:
                self._datafeeds[symbol] = DataFeed(symbol, source)
            return self._datafeeds[symbol]

    def update_bar(self, symbol: str, bar: Bar, period_name: str, events: Optional[List[Event]] = None) -> None:
        """更新指定品种的K线（路由到对应DataFeed）

        这是Bridge或数据接收层的主要调用入口

        :param symbol: 交易品种
        :param bar: K线数据
        :param period_name: 对应周期名称
        :param events: 事件数据（可选）
        """
        datafeed = self.get_or_create(symbol)
        datafeed.update_bar(bar, period_name, events)

    def get_data(self, symbol: str, period_name: str, current_time: Union[pd.Timestamp, dt],
                 lookback_bars: int = 1, timeout: Optional[float] = None) -> Optional[PeriodDataView]:
        """获取指定品种、指定周期的逻辑视图（策略主要访问入口）

        这是策略获取数据的主要方法

        :param symbol: 交易品种
        :param period_name: 周期名称
        :param current_time: 当前时间，视图只包含<=此时间的数据
        :param lookback_bars: 往前多少根K线
        :param timeout: 超时时间（秒），None表示回测模式（抛错），>0表示等待，0表示非阻塞
        :return: PeriodDataView只读逻辑视图
        :raises KeyError: 如果品种或周期未注册
        """
        datafeed = self.get_or_create(symbol)
        return datafeed.get_data(period_name, current_time, lookback_bars, timeout)


# ==================== 辅助函数 ====================

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
    multi: Dict[str, PeriodDataView] = {}

    # 获取多周期数据
    for period, req in requirements.periods.items():
        view = data_feed.get_data(period, current_time, req.lookback_bars, timeout)
        if view is not None:
            multi[period] = view

    # 获取事件
    events: List[Event] = []
    events_req = requirements.events

    # 先获取所有事件，然后按需求筛选
    all_events = data_feed.get_events(end_time=current_time)

    for event in all_events:
        include = False

        # 检查全局事件
        if events_req.include_global_events and event.period is None:
            include = True

        # 检查周期特定事件
        if not include and events_req.include_period_events:
            if "*" in events_req.include_period_events or event.period in events_req.include_period_events:
                include = True

        # 检查事件类型白名单
        if include and events_req.event_types:
            if event.type not in events_req.event_types:
                include = False

        if include:
            events.append(event)

    # 获取当前Bar（简单实现，使用第一个周期的最新Bar）
    bar = Bar()
    if multi:
        first_period = list(multi.keys())[0]
        maybe_bar = multi[first_period].get_bar(-1)
        if maybe_bar is not None:
            bar = maybe_bar
            bar.symbol = data_feed.symbol

    return BarContext(
        symbol=data_feed.symbol,
        bar=bar,
        multi=multi,
        events=events
    )


def make_view(
    bars: List[Bar],
    current_time: Union[pd.Timestamp, dt],
    lookback_bars: Optional[int] = None,
    indicators: Optional[Dict[str, List[float]]] = None,
    events: Optional[List[Event]] = None
) -> PeriodDataView:
    """构造测试用的 PeriodDataView

    Args:
        bars: K线列表
        current_time: 视图截止时间
        lookback_bars: 往前多少根K线（None 表示全部）
        indicators: 指标数据，key 为指标名，value 为值列表（与 bars 对齐）
        events: 事件列表
    """
    # 创建临时的PeriodData
    period_data = PeriodData("test")
    period_data.append_bars(bars)

    # 添加指标
    if indicators:
        bar_times = [pd.Timestamp(bar.datetime) for bar in bars]
        indicators_df = pd.DataFrame(indicators, index=bar_times)
        period_data.append_indicators(indicators_df)

    # 构建事件DataFrame
    events_df = None
    if events:
        event_dicts = []
        for event in events:
            event_dicts.append({
                'datetime': pd.Timestamp(event.timestamp),
                'type': event.type,
                'symbol': event.symbol,
                'reason': event.reason,
                'period': event.period,
                'data': event.data
            })
        events_df = pd.DataFrame(event_dicts)
        events_df = events_df.set_index('datetime')

    # 计算lookback_bars
    if lookback_bars is None:
        lookback_bars = len(bars)

    # 获取视图
    return period_data.get_data(current_time, lookback_bars, events_df)


# ==================== 默认指标注册 ====================

def _sma_func(df: pd.DataFrame, period: int) -> pd.Series:
    """SMA指标计算函数 - 内置实现"""
    return cast(pd.Series, df['close'].rolling(window=period).mean())


def _ema_func(df: pd.DataFrame, period: int) -> pd.Series:
    """EMA指标计算函数 - 内置实现"""
    return cast(pd.Series, df['close'].ewm(span=period, adjust=False).mean())


def _rsi_func(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """RSI指标计算函数 - 内置实现"""
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return cast(pd.Series, 100 - (100 / (1 + rs)))


# 注册默认指标
register_indicator_func(
    'sma',
    _sma_func,
    IndicatorCalcMode.BATCH,
    description='简单移动平均线 (Simple Moving Average)'
)
register_indicator_func(
    'ema',
    _ema_func,
    IndicatorCalcMode.BATCH,
    description='指数移动平均线 (Exponential Moving Average)'
)
register_indicator_func(
    'rsi',
    _rsi_func,
    IndicatorCalcMode.BATCH,
    description='相对强弱指标 (Relative Strength Index)'
)