"""运行时数据管理模块

与 strategies/core/ 平级，负责策略运行时的内存数据编排：
- DataFeed: 单个品种多周期数据管理器
- DataRequirements: 策略声明数据需求（周期+指标+事件）
- BarContext: 当前 bar 的上下文，供策略决策使用
- 缓存工具：避免重复反序列化和指标计算

核心流程：
1. 策略声明 DataRequirements
2. 桥接代码构造 DataFeed 并灌入数据
3. 每根 bar 调用 build_context 得到 BarContext
4. 策略基于 BarContext 生成信号

从 strategies/ 顶层导入即可，无需直接引用子模块。
"""

from .cache import clear_cache, get_cached_feed, set_cached_feed
from .data_feed import SOURCE_PERIOD, DataFeed, build_context, create_data_feed
from .events import BigTradeEvent, Event, NewsEvent
from .requirements import (
    BarContext,
    DataRequirements,
    EventsRequirements,
    IndicatorRequirements,
    PeriodRequirements,
)

__all__ = [
    # 常量
    "SOURCE_PERIOD",
    # 核心类
    "DataFeed",
    # 工厂方法：完整构造 DataFeed，自动处理缓存和增量加载
    "create_data_feed",
    # 数据需求声明（策略需要声明自己要什么）
    "PeriodRequirements",
    "IndicatorRequirements",
    "EventsRequirements",
    "DataRequirements",
    # 上下文（策略接收这个）
    "BarContext",
    # 事件类型（策略可能产生事件）
    "Event",
    "BigTradeEvent",
    "NewsEvent",
    # 缓存工具（桥接代码用来优化性能）
    "get_cached_feed",
    "set_cached_feed",
    "clear_cache",
    # 上下文构造（桥接/回测需要）
    "build_context",
]
