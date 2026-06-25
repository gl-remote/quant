"""策略切面能力库 — 将横切关注点从策略业务逻辑中抽离。

当实现新策略或审查策略代码时，应优先检查这里是否已有可复用切面，
避免在策略类中重复实现通用逻辑。

使用方式:
    from strategies.strategy_aspects import (
        confirm_long, confirm_short, trend_long, trend_short,
    )

    @confirm_long("macd@1m > 0")
    @trend_long("sma({sma_short})@5m > sma({sma_long})@5m")
    class MyStrategy(Strategy[MyParams]):
        ...
"""

# 协议层：基础数据结构
from ..core.indicators import IndicatorSpec
from .direction import confirm_long, confirm_short, trend_long, trend_short

# 指标定义
from .indicators import KDJ, MACD, SMA
from .primitives import (
    DirectionAdvice,
    DirectionReason,
    DirectionSideAdvice,
    MetricRef,
    RiskAdvice,
    RiskReason,
    StrategyAspects,
    at,
)

# 风控切面
from .risk import (
    entry_block_after_stop_loss,
    entry_block_after_take_profit,
    exit_for_stop_loss,
    exit_for_take_profit,
)

__all__ = [
    # 协议层
    "DirectionReason",
    "DirectionSideAdvice",
    "DirectionAdvice",
    "RiskReason",
    "RiskAdvice",
    "StrategyAspects",
    "IndicatorSpec",
    "MetricRef",
    "at",
    # 指标定义
    "MACD",
    "KDJ",
    "SMA",
    # 建议型方向 DSL
    "confirm_long",
    "confirm_short",
    "trend_long",
    "trend_short",
    # 风控切面
    "exit_for_take_profit",
    "exit_for_stop_loss",
    "entry_block_after_take_profit",
    "entry_block_after_stop_loss",
]
