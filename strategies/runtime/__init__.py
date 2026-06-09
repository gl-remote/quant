"""运行时数据管理模块

与 strategies/core/ 平级，负责策略运行时的内存数据编排：
- 事件类型 + 指标/周期转换注册体系
- PeriodData + PeriodDataView 数据容器
- 数据需求类型
- DataFeed + 模块级 cache 内存缓存

从 strategies/ 顶层导入即可，无需直接引用此子模块。
"""

from .cache import clear_cache, get_cached_feed, set_cached_feed
from .data_feed import (
    DataFeed,
    build_context,
)
from .events import (
    BigTradeEvent,
    Event,
    IndicatorCalcMode,
    IndicatorFuncInfo,
    NewsEvent,
    register_indicator_func,
    register_period_converter,
)
from .period import PeriodData, PeriodDataView
from .requirements import (
    BarContext,
    DataRequirements,
    EventsRequirements,
    IndicatorRequirements,
    PeriodRequirements,
)

__all__ = [
    "Event",
    "BigTradeEvent",
    "NewsEvent",
    "IndicatorCalcMode",
    "IndicatorFuncInfo",
    "PeriodData",
    "PeriodDataView",
    "PeriodRequirements",
    "IndicatorRequirements",
    "EventsRequirements",
    "DataRequirements",
    "BarContext",
    "DataFeed",
    "get_cached_feed",
    "set_cached_feed",
    "clear_cache",
    "register_indicator_func",
    "register_period_converter",
    "build_context",
]
