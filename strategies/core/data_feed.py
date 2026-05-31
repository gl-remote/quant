"""量化策略数据管理模块

【架构设计】
- Event: 事件基类，支持多种事件类型（大单、新闻、自定义）
- PeriodData: 单个周期的数据容器，管理K线和指标，提供快照
- PeriodDataView: 只读逻辑视图，不复制数据，按时间和历史条数裁剪
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

from dataclasses import dataclass, field
from datetime import datetime as dt
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union, cast
import threading
import pandas as pd
from pandas._libs import NaTType

from .types import Bar


# ==================== 事件类型定义 ====================

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


# ==================== 模块级指标计算函数注册 ====================

class IndicatorCalcMode(Enum):
    BATCH = "batch"  # 一次性计算所有数据（默认）
    INCREMENTAL = "incremental"  # 逐行/增量式计算，适合 update_bar 时触发


@dataclass
class IndicatorFuncInfo:
    func: Callable[..., pd.Series]
    calc_mode: IndicatorCalcMode
    name: str
    description: Optional[str] = None


_REGISTERED_INDICATOR_FUNCS: Dict[str, IndicatorFuncInfo] = {}


def register_indicator_func(name: str, func: Callable[..., pd.Series], 
                            calc_mode: IndicatorCalcMode = IndicatorCalcMode.BATCH,
                            description: Optional[str] = None) -> None:
    """全局注册指标计算函数，所有 DataFeed 共享

    指标计算函数签名要求：
    def indicator_func(df: pd.DataFrame, **params) -> pd.Series

    【指标列名生成规则】
    - 列名格式：{indicator_name}_{param1_value}_{param2_value}_...
    - 参数按函数定义时的参数列表顺序排列
    - 参数值使用字符串表示，特殊字符转义
    - 示例：
      - 假设函数定义为 def sma(df, period): ...
        - sma(period=10) → sma_10
      - 假设函数定义为 def bbands(df, period, std): ...
        - bbands(period=20, std=2) → bbands_20_2
        - bbands(std=2, period=20) → bbands_20_2（同样按函数定义顺序）

    :param name: 指标名称
    :param func: 计算函数
    :param calc_mode: 计算模式，BATCH（默认）一次性全量计算，INCREMENTAL适合实时增量
    :param description: 指标描述（可选）
    """
    _REGISTERED_INDICATOR_FUNCS[name] = IndicatorFuncInfo(
        func=func, 
        calc_mode=calc_mode,
        name=name,
        description=description
    )


def _generate_indicator_column_name(name: str, params: Dict[str, Any]) -> str:
    """生成指标列名

    【参数顺序】
    - 按参数名称排序，确保参数顺序不影响列名生成
    """
    sorted_params = sorted(params.items())
    param_parts = [f"{value}" for _, value in sorted_params]
    if param_parts:
        return f"{name}_{'_'.join(param_parts)}"
    return name


# ==================== 模块级周期转换函数注册 ====================

_REGISTERED_CONVERTERS: Dict[Tuple[str, str], Callable[..., List[Bar]]] = {}


def register_period_converter(source_period: str, target_period: str, func: Callable[..., List[Bar]]) -> None:
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


# ==================== 数据需求类型定义 ====================

@dataclass
class PeriodRequirements:
    """单个周期的数据需求（类比表的查询需求）"""
    lookback_bars: int  # 查询的历史K线数量（最近N个周期）
    min_bars: Optional[int] = None  # 策略需要的最小K线数（可选，用于校验）


@dataclass
class IndicatorRequirements:
    """单个指标的计算需求"""
    name: str  # 指标名
    params: Dict[str, Any]  # 指标参数


@dataclass
class EventsRequirements:
    """事件数据需求"""
    # 是否需要全局事件（period=None 的事件）
    include_global_events: bool = False

    # 需要的周期特定事件：周期名列表，"*" 表示所有周期
    include_period_events: List[str] = field(default_factory=list)

    # 事件类型白名单：如果为空则获取所有类型；否则只获取指定类型
    event_types: List[str] = field(default_factory=list)

    @classmethod
    def all_events(cls) -> 'EventsRequirements':
        """便捷方法：获取所有事件（全局 + 所有周期特定事件）"""
        return cls(
            include_global_events=True,
            include_period_events=["*"],
            event_types=[]
        )

    @classmethod
    def no_events(cls) -> 'EventsRequirements':
        """便捷方法：不获取任何事件"""
        return cls(
            include_global_events=False,
            include_period_events=[],
            event_types=[]
        )


@dataclass
class DataRequirements:
    """策略的数据需求（类比数据库查询计划）

    DataFeed 和 PeriodData 命名说明：
    - DataFeed ≈ 数据库（Database），用 symbol + source 作为唯一标识
    - PeriodData ≈ 数据表（Table），用 period 作为唯一标识（在 DataFeed 内）
    - 不需要额外的 name 字段，当前设计已经足够清晰
    """
    # 周期配置：key 是周期名（对应 PeriodData 的 period 字段），value 是该周期的需求
    periods: Dict[str, PeriodRequirements]

    # 指标配置：key 是周期名，value 是该周期需要的指标列表
    indicators: Dict[str, List[IndicatorRequirements]]

    # 事件配置
    events: EventsRequirements = field(default_factory=EventsRequirements.no_events)


@dataclass
class BarContext:
    """当前 bar 的策略上下文——引擎按 data_requirements 声明构造"""
    symbol: str
    bar: Bar
    # 多周期数据，key=周期名，key 集合 = data_requirements 中声明的周期
    multi: Dict[str, 'PeriodDataView']
    # 当前 bar 时间范围内的事件
    events: List[Event]


# ==================== PeriodData: 单个周期的数据容器 ====================

class PeriodData:
    """单个周期的数据容器

    【设计目标】
    - 统一管理该周期的 K线、指标两类数据（事件由 DataFeed 统一管理）
    - 提供逻辑视图，策略只能看到指定时间点之前的数据
    - 支持数据追加（Append-Only，历史数据不修改）
    - 底层存储使用 Pandas DataFrame
    - 高效的数据访问，通过逻辑视图实现，不复制数据

    【两种使用场景】
    - 场景1：由 DataFeed 统一管理（多策略共享）
    - 场景2：策略自己持有（策略私有数据，不共享）
    """

    def __init__(self, period: str):
        """初始化单个周期的数据容器

        初始化过程：
        1. 创建空的K线+指标DataFrame，包含datetime, open, high, low, close, volume列
        2. 初始化状态变量和数据追踪字段

        :param period: 周期名称，如 "1m", "5m", "1h", "1d" 等
        """
        self.period = period

        # K线数据（OHLCV） + 指标数据（合并在一起，索引统一为datetime）
        self._df = pd.DataFrame(columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])
        self._df = self._df.astype({
            'open': 'float64',
            'high': 'float64',
            'low': 'float64',
            'close': 'float64',
            'volume': 'float64'
        })

        # 数据追踪字段（类似数据库表）
        self._created_at = pd.Timestamp.now()
        self._last_updated_at = pd.Timestamp.now()
        self._update_count = 0

        # 指标计算状态跟踪
        self._calculated_indicators: Set[str] = set()
        self._indicator_last_calc_idx: Dict[str, int] = {}

    @property
    def latest_time(self) -> Optional[pd.Timestamp]:
        """获取最新数据时间戳"""
        if len(self._df) == 0:
            return None
        return cast(pd.Timestamp, self._df.index[-1])

    @property
    def length(self) -> int:
        """获取当前数据长度（K线数量）"""
        return len(self._df)

    def append_bars(self, bars: List[Bar]) -> None:
        """批量追加K线数据（用于回测初始化）

        注意事项：
        1. 必须按时间升序排列
        2. 时间戳不能与已有的数据重复
        3. Append-Only：历史数据不会被修改
        4. 更新数据追踪字段：_last_updated_at 和 _update_count

        :param bars: K线列表
        :raises ValueError: 如果bars为空或时间顺序不对
        """
        if not bars:
            raise ValueError("Bars list is empty")

        # 验证时间顺序
        prev_time = None
        if len(self._df) > 0:
            prev_time = self._df.index[-1]

        bar_dicts = []
        for bar in bars:
            bar_time = pd.Timestamp(bar.datetime)
            if prev_time is not None and bar_time <= prev_time:
                raise ValueError(f"Bar time {bar_time} is not after previous time {prev_time}")
            prev_time = bar_time

            bar_dicts.append({
                'datetime': bar_time,
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume
            })

        # 转换为DataFrame并追加
        new_df = pd.DataFrame(bar_dicts)
        new_df = new_df.set_index('datetime')

        if len(self._df) == 0:
            self._df = new_df
        else:
            self._df = pd.concat([self._df, new_df])

        # 更新数据追踪字段
        self._last_updated_at = pd.Timestamp.now()
        self._update_count += len(bars)

    def append_bar(self, bar: Bar) -> None:
        """追加单根K线（用于实时/逐根更新场景）

        注意事项：
        1. 追加的时间戳必须晚于已有的最新时间
        2. 通常被DataFeed.update_bar调用，策略不应直接调用此方法
        3. Append-Only：历史数据不会被修改
        4. 更新数据追踪字段：_last_updated_at 和 _update_count

        :param bar: 单根K线数据
        :raises ValueError: 如果时间戳早于或等于最新数据时间
        """
        bar_time = pd.Timestamp(bar.datetime)

        if len(self._df) > 0:
            latest = self._df.index[-1]
            if bar_time <= latest:
                raise ValueError(f"Bar time {bar_time} is not after latest time {latest}")

        # 追加新数据
        new_row = pd.Series({
            'open': bar.open,
            'high': bar.high,
            'low': bar.low,
            'close': bar.close,
            'volume': bar.volume
        }, name=bar_time)

        self._df = pd.concat([self._df, new_row.to_frame().T])

        # 更新数据追踪字段
        self._last_updated_at = pd.Timestamp.now()
        self._update_count += 1

    def append_indicators(self, indicators: pd.DataFrame) -> None:
        """追加指标数据

        指标DataFrame要求：
        1. 索引必须与K线的datetime对齐
        2. 列名应为指标名（如 "sma_10", "ema_20"）

        注意事项：
        1. 更新数据追踪字段：_last_updated_at 和 _update_count

        :param indicators: 指标DataFrame，行数应等于或小于当前K线数
        :raises ValueError: 如果索引不匹配
        """
        # 验证索引
        if len(indicators) > len(self._df):
            raise ValueError("Indicators DataFrame has more rows than K-line data")

        # 合并指标数据
        for col in indicators.columns:
            self._df[col] = indicators[col]

        # 更新数据追踪字段
        self._last_updated_at = pd.Timestamp.now()

    def get_data(self, current_time: Union[pd.Timestamp, dt], lookback_bars: int = 1,
                 events_df: Optional[pd.DataFrame] = None) -> 'PeriodDataView':
        """获取截止指定时间点的逻辑视图（只读，用于策略安全访问）

        视图特性：
        1. 只包含截止到current_time的数据，不包含之后的未来数据
        2. 只读访问，策略无法修改原始数据
        3. 不受后续数据更新影响，保证数据一致性（Append-Only）
        4. 可指定需要的历史K线数，限定视图范围
        5. 逻辑视图，不复制数据，通过索引范围访问原始数据

        :param current_time: 当前时间，视图将只包含<=此时间的数据
        :param lookback_bars: 需要的历史K线数，从current_time往前数，默认1根
        :param events_df: 事件DataFrame（由DataFeed传入）
        :return: PeriodDataView只读逻辑视图对象
        :raises ValueError: 如果current_time晚于最新数据时间，或lookback_bars <= 0
        """
        if lookback_bars <= 0:
            raise ValueError("lookback_bars must be positive")

        current_time_ts: pd.Timestamp = pd.Timestamp(current_time)  # type: ignore[assignment]

        # 检查时间是否有效
        if len(self._df) == 0:
            raise ValueError("No data available")

        if current_time_ts > self._df.index[-1]:
            raise ValueError(f"current_time {current_time_ts} is after latest data time {self._df.index[-1]}")

        # 找到截止时间对应的索引
        end_idx = self._df.index.get_indexer(pd.Index([current_time_ts]), method='ffill')[0]
        if end_idx < 0:
            end_idx = 0

        # 计算起始索引
        start_idx = max(0, end_idx - lookback_bars + 1)

        return PeriodDataView(
            df_ref=self._df,
            events_ref=events_df,
            start_idx=start_idx,
            end_idx=end_idx,
            current_time=current_time_ts,
            period=self.period
        )

    def get_bar(self, idx: int) -> Optional[Bar]:
        """通过索引获取K线

        索引规则：
        0: 最早的K线
        -1: 最新的K线

        :param idx: 索引位置，支持负索引
        :return: Bar对象，索引越界返回None
        """
        if len(self._df) == 0:
            return None

        try:
            row = self._df.iloc[idx]
            row_name = cast(pd.Timestamp, row.name)
            return Bar(
                symbol='',  # 单个周期不保存symbol，由DataFeed管理
                datetime=row_name.to_pydatetime(),
                open=row['open'],
                high=row['high'],
                low=row['low'],
                close=row['close'],
                volume=row['volume']
            )
        except IndexError:
            return None

    def get_bar_by_time(self, time: Union[pd.Timestamp, dt]) -> Optional[Bar]:
        """通过精确时间戳获取K线

        :param time: 要查找的时间戳
        :return: 匹配的Bar对象，未找到返回None
        """
        time_ts = pd.Timestamp(time)
        if time_ts not in self._df.index:
            return None

        row = self._df.loc[time_ts]
        row_name = cast(pd.Timestamp, row.name)
        return Bar(
            symbol='',
            datetime=row_name.to_pydatetime(),
            open=row['open'],
            high=row['high'],
            low=row['low'],
            close=row['close'],
            volume=row['volume']
        )

    def get_indicator(self, name: str, idx: int) -> Optional[float]:
        """通过索引获取指标值

        :param name: 指标名称，如 "sma_10", "rsi_14"
        :param idx: 索引位置，支持负索引，-1表示最新
        :return: 指标值，索引越界或指标不存在返回None
        """
        if name not in self._df.columns:
            return None

        if len(self._df) == 0:
            return None

        try:
            return float(self._df[name].iloc[idx])
        except IndexError:
            return None

    def get_indicator_series(self, name: str) -> pd.Series:
        """获取指标完整序列

        :param name: 指标名称
        :return: 指标Series，索引为datetime
        :raises KeyError: 如果指标不存在
        """
        if name not in self._df.columns:
            raise KeyError(f"Indicator {name} not found")
        return self._df[name].copy()

    # --- 指标计算状态管理方法 ---

    def is_indicator_calculated(self, name: str) -> bool:
        """检查指标是否已计算

        :param name: 指标列名（如 "sma_10"）
        :return: 是否已计算
        """
        return name in self._calculated_indicators

    def get_indicator_last_calc_idx(self, name: str) -> Optional[int]:
        """获取指标最后计算到的行索引

        :param name: 指标列名
        :return: 最后计算到的行索引，None表示未计算过
        """
        return self._indicator_last_calc_idx.get(name)

    def mark_indicator_calculated(self, name: str, last_idx: Optional[int] = None) -> None:
        """标记指标已计算

        :param name: 指标列名
        :param last_idx: 最后计算到的行索引，None表示计算到当前末尾
        """
        self._calculated_indicators.add(name)
        if last_idx is not None:
            self._indicator_last_calc_idx[name] = last_idx
        else:
            self._indicator_last_calc_idx[name] = len(self._df) - 1

    def clear_indicator_calculation(self, name: Optional[str] = None) -> None:
        """清除指标计算状态

        :param name: 指标列名，None表示清除所有
        """
        if name is None:
            self._calculated_indicators.clear()
            self._indicator_last_calc_idx.clear()
        else:
            self._calculated_indicators.discard(name)
            self._indicator_last_calc_idx.pop(name, None)

    def apply_indicator(self, func: Callable[..., pd.Series], **params: Any) -> pd.Series:
        """对内部数据应用指标计算函数

        封装对 self._df 的访问，外部调用者无需直接操作 _df。

        :param func: 指标计算函数，签名 func(df: pd.DataFrame, **params) -> pd.Series
        :param params: 指标参数
        :return: 计算结果 Series
        """
        return func(self._df, **params)

    def set_indicator_column(self, name: str, series: pd.Series) -> None:
        """将指标计算结果写入内部存储

        封装对 self._df[name] = series 的访问，外部无需直接操作 _df。

        :param name: 指标列名（如 "sma_10"）
        :param series: 指标计算结果 Series
        """
        self._df[name] = series


# ==================== PeriodDataView: 只读逻辑视图 ====================

class PeriodDataView:
    """只读逻辑视图

    【设计目标】
    - 只读逻辑视图，防止策略修改数据
    - 只包含截止指定时间点和指定历史K线范围的数据
    - 不受后续数据更新影响（Append-Only 保证）
    - 高效实现：通过索引范围访问原始数据，不复制数据
    - 纯只读，不触发任何计算
    """

    def __init__(self, df_ref: pd.DataFrame, events_ref: Optional[pd.DataFrame],
                 start_idx: int, end_idx: int, current_time: pd.Timestamp, period: str):
        """初始化逻辑视图（内部使用，不应直接构造）

        :param df_ref: 原始K线+指标DataFrame的引用（不复制）
        :param events_ref: 原始事件DataFrame的引用（不复制）
        :param start_idx: 视图的起始索引（包含）
        :param end_idx: 视图的结束索引（包含）
        :param current_time: 视图的截止时间
        :param period: 周期名称
        """
        self._df_ref = df_ref
        self._events_ref = events_ref
        self._start_idx = start_idx
        self._end_idx = end_idx
        self._current_time = current_time
        self._period = period

    @property
    def current_time(self) -> pd.Timestamp:
        """获取视图的截止时间"""
        return self._current_time

    @property
    def length(self) -> int:
        """获取视图中K线数量"""
        return self._end_idx - self._start_idx + 1

    @property
    def period(self) -> str:
        """获取周期名称"""
        return self._period

    def get_bar(self, idx: int = -1) -> Optional[Bar]:
        """通过索引获取K线（索引相对于视图）

        :param idx: 索引位置，支持负索引（相对于视图）
        :return: Bar对象，索引越界返回None
        """
        # 转换为相对于原始DataFrame的索引
        if idx >= 0:
            real_idx = self._start_idx + idx
        else:
            real_idx = self._end_idx + idx + 1

        if real_idx < self._start_idx or real_idx > self._end_idx:
            return None

        try:
            row = self._df_ref.iloc[real_idx]
            row_name = cast(pd.Timestamp, row.name)
            return Bar(
                symbol='',
                datetime=row_name.to_pydatetime(),
                open=row['open'],
                high=row['high'],
                low=row['low'],
                close=row['close'],
                volume=row['volume']
            )
        except IndexError:
            return None

    def get_indicator(self, name: str, idx: int = -1) -> Optional[float]:
        """通过索引获取指标值（索引相对于视图）
        注意：此方法不触发计算，指标不存在返回 None

        :param name: 指标名称，如 "sma_10"
        :param idx: 索引位置，支持负索引（相对于视图）
        :return: 指标值，索引越界或指标不存在返回None
        """
        if name not in self._df_ref.columns:
            return None

        # 转换为相对于原始DataFrame的索引
        if idx >= 0:
            real_idx = self._start_idx + idx
        else:
            real_idx = self._end_idx + idx + 1

        if real_idx < self._start_idx or real_idx > self._end_idx:
            return None

        try:
            return float(self._df_ref[name].iloc[real_idx])
        except IndexError:
            return None

    def get_events(self) -> List[Event]:
        """获取视图时间范围内的所有事件"""
        if self._events_ref is None or len(self._events_ref) == 0:
            return []

        # 获取视图时间范围
        view_start = self._df_ref.index[self._start_idx]
        view_end = self._df_ref.index[self._end_idx]

        # 筛选时间范围内的事件
        mask = (self._events_ref.index >= view_start) & (self._events_ref.index <= view_end)
        events_df = self._events_ref[mask]

        # 转换回Event对象
        events = []
        for _, row in events_df.iterrows():
            row_name = cast(pd.Timestamp, row.name)
            event = Event(
                timestamp=row_name.to_pydatetime(),
                type=row['type'],
                symbol=row['symbol'],
                reason=row.get('reason', ''),
                period=row.get('period'),
                data=row.get('data')
            )
            events.append(event)

        return events

    def get_all_bars(self) -> pd.DataFrame:
        """获取视图中所有K线+指标DataFrame（只读视图，不复制）"""
        return cast(pd.DataFrame, self._df_ref.iloc[self._start_idx:self._end_idx + 1].copy())

    # --- 便捷访问器 ---

    def bar(self, idx: int = -1) -> Bar | None:
        """便捷方法：获取K线"""
        return self.get_bar(idx)

    def close(self, idx: int = -1) -> float | None:
        """便捷方法：获取收盘价"""
        bar = self.get_bar(idx)
        return bar.close if bar is not None else None

    def indicator(self, name: str, idx: int = -1) -> float | None:
        """便捷方法：获取指标值"""
        return self.get_indicator(name, idx)

    def indicator_series(self, name: str) -> pd.Series:
        """便捷方法：获取指标序列"""
        if name not in self._df_ref.columns:
            raise KeyError(f"Indicator {name} not found")
        return self._df_ref[name].iloc[self._start_idx:self._end_idx + 1].copy()

    def events(self) -> List[Event]:
        """便捷方法：获取事件列表"""
        return self.get_events()


# ==================== DataFeed: 管理单个品种的多周期数据 ====================

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
