"""运行时数据管理模块

与 strategies/core/ 平级，负责策略运行时的内存数据编排：
- 事件类型 + 指标/周期转换注册体系
- PeriodData + PeriodDataView 数据容器
- 数据需求类型
- DataFeed + DataFeedCache 多周期数据调度

从 strategies/ 顶层导入即可，无需直接引用此子模块。
"""

from .events import (
    Event,
    BigTradeEvent,
    NewsEvent,
    IndicatorCalcMode,
    IndicatorFuncInfo,
    register_indicator_func,
    register_period_converter,
)
from .period import PeriodData, PeriodDataView
from .requirements import (
    PeriodRequirements,
    IndicatorRequirements,
    EventsRequirements,
    DataRequirements,
    BarContext,
)
from .data_feed import (
    DataFeed,
    DataFeedCache,
    build_context,
    make_view,
)

__all__ = [
    'Event', 'BigTradeEvent', 'NewsEvent',
    'IndicatorCalcMode', 'IndicatorFuncInfo',
    'PeriodData', 'PeriodDataView',
    'PeriodRequirements', 'IndicatorRequirements', 'EventsRequirements', 'DataRequirements',
    'BarContext',
    'DataFeed', 'DataFeedCache',
    'register_indicator_func', 'register_period_converter',
    'build_context', 'make_view',
]