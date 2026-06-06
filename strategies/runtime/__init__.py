"""策略运行时模块

负责策略运行时的完整基础设施：
- 策略基类 (Strategy ABC) + 标准化数据类型 (Bar, Signal, Fill)
- 运行时状态容器 (State)
- 事件类型 + 指标/周期转换注册体系
- PeriodData + PeriodDataView 数据容器
- 数据需求类型
- DataFeed + 模块级 cache 内存缓存
- 内置指标计算函数

从 strategies/ 顶层导入即可，无需直接引用此子模块。
"""

from .base import Strategy, UninitializedStrategy
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
from .state import State
from .types import Bar, Fill, Signal, StrategyPosition

# 核心版本号
CORE_VERSION = "v2.0.0"

__all__ = [
    # 版本号
    "CORE_VERSION",
    # 核心基类和类型
    "Strategy",
    "UninitializedStrategy",
    "Bar",
    "Signal",
    "Fill",
    "StrategyPosition",
    # 运行时状态
    "State",
    # 事件类型
    "Event",
    "BigTradeEvent",
    "NewsEvent",
    "IndicatorCalcMode",
    "IndicatorFuncInfo",
    # 数据容器
    "PeriodData",
    "PeriodDataView",
    # 数据需求类型
    "PeriodRequirements",
    "IndicatorRequirements",
    "EventsRequirements",
    "DataRequirements",
    "BarContext",
    # 数据管理
    "DataFeed",
    "get_cached_feed",
    "set_cached_feed",
    "clear_cache",
    # 注册函数
    "register_indicator_func",
    "register_period_converter",
    # 辅助函数
    "build_context",
]
