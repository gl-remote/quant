"""策略模块公共 API 入口。

本包导出策略核心、标准化运行时类型、桥接器与策略名称常量。
外部调用方优先从这里导入稳定 API；包内模块使用相对导入，避免循环依赖。

常用导入:
    from strategies import Strategy, Bar, Signal, Fill
    from strategies import MaStrategyCore, ATRStrategyCore
    from strategies import VnpyBacktestBridge, TqsdkStrategyBridge
    from strategies import CORE_VERSION, STRATEGY_MA, STRATEGY_ATR

策略开发/调整指引见 README.md。
新策略或策略调整优先使用 strategy_aspects 中的切面 DSL 表达方向、确认与风控意图。
"""

# 策略核心与类型（来自 core）
from .core import (
    Strategy,
    UninitializedStrategy,
    Bar,
    Signal,
    Fill,
    StrategyPosition,
    State,
    CORE_VERSION,
)
from .strategy_aspects import (
    DirectionAdvice,
    DirectionReason,
    DirectionSideAdvice,
    IndicatorSpec,
    StrategyAspects,
    confirm_long,
    confirm_short,
    trend_long,
    trend_short,
    entry_block_after_stop_loss,
    entry_block_after_take_profit,
    exit_for_stop_loss,
    exit_for_take_profit,
)

# 运行时数据管理（来自 runtime，与 core 同级）
from .runtime import (
    DataFeed,
    Event,
    BigTradeEvent,
    NewsEvent,
    PeriodRequirements,
    EventsRequirements,
    DataRequirements,
    BarContext,
    get_cached_feed,
    set_cached_feed,
    clear_cache,
)

# 具体策略实现
from .atr_strategy import ATRCrossParams, ATRStrategyCore
from .ma_strategy import MaStrategyCore, MACrossParams

# 工具函数（来自 utils）
from .utils import (
    load_strategy,
    get_strategy_class_name,
    apply_strategy_config,
    serialize_strategy_params,
)

# 桥接器（延迟导入，避免 import strategies 时触发 vnpy/tqsdk 副作用）
# 使用 __getattr__ 实现按需加载，仅在用户显式访问时才 import bridge 模块。
# 常规策略开发（core/runtime/aspects）不会触发 vnpy/tqsdk 初始化。


def __getattr__(name: str) -> object:
    """延迟导入桥接器，避免模块加载时触发 vnpy/tqsdk 的文件 IO 副作用。"""
    _bridge_map = {
        "VnpyBacktestBridge": ".bridges",
        "TqsdkStrategyBridge": ".bridges",
    }
    if name in _bridge_map:
        import importlib

        module = importlib.import_module(_bridge_map[name], __name__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # 版本号
    "CORE_VERSION",
    # 核心类型
    "Strategy",
    "UninitializedStrategy",
    "Bar",
    "Signal",
    "Fill",
    "StrategyPosition",
    "State",
    # 策略切面
    "DirectionReason",
    "DirectionSideAdvice",
    "DirectionAdvice",
    "StrategyAspects",
    "IndicatorSpec",
    "exit_for_take_profit",
    "exit_for_stop_loss",
    "entry_block_after_take_profit",
    "entry_block_after_stop_loss",
    "confirm_long",
    "confirm_short",
    "trend_long",
    "trend_short",
    # 数据管理类型
    "DataFeed",
    "Event",
    "BigTradeEvent",
    "NewsEvent",
    "PeriodRequirements",
    "EventsRequirements",
    "DataRequirements",
    "BarContext",
    "get_cached_feed",
    "set_cached_feed",
    "clear_cache",
    "build_context",
    # 策略实现
    "MaStrategyCore",
    "MACrossParams",
    "ATRStrategyCore",
    "ATRCrossParams",
    # 工具函数
    "load_strategy",
    "get_strategy_class_name",
    "apply_strategy_config",
    "serialize_strategy_params",
    # 桥接器
    "VnpyBacktestBridge",
    "TqsdkStrategyBridge",
]
