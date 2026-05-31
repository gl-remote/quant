"""数据需求类型定义

包含策略声明数据需求的 dataclass 类型。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .events import Event
from .types import Bar


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