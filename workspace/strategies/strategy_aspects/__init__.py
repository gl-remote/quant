"""策略切面能力库 — 将横切关注点从策略业务逻辑中抽离。

这里存放可复用的 strategy-level aspects，用于把止盈止损、风控、过滤器、
冷却期、诊断增强、data_requirements 自动补齐等通用交易行为从具体策略中抽离。

当实现新策略或审查策略代码时，应优先检查这里是否已有可复用切面，
避免在策略类中重复实现通用逻辑。

使用方式:
    from strategies.strategy_aspects import with_take_profit, with_stop_loss

    @with_take_profit()
    @with_stop_loss()
    class MyStrategy(Strategy[MyParams]):
        def on_bar(self, state, ctx):
            # 只写入场逻辑，横切面由切面自动处理
            ...
"""

# 协议层：基础数据结构
# 建议型方向 DSL
from ..core.indicators import IndicatorSpec
from .direction import (
    confirm_long_when,
    confirm_long_when_compare,
    confirm_short_when,
    confirm_short_when_compare,
    trend_long_when,
    trend_long_when_compare,
    trend_short_when,
    trend_short_when_compare,
)

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
    with_cooldown_after_stop_loss,
    with_cooldown_after_take_profit,
    with_stop_loss,
    with_stop_loss_atr,
    with_take_profit,
    with_take_profit_atr,
    with_trailing_take_profit,
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
    # 风控切面
    "with_take_profit",
    "with_stop_loss",
    "with_take_profit_atr",
    "with_stop_loss_atr",
    "with_trailing_take_profit",
    "with_cooldown_after_take_profit",
    "with_cooldown_after_stop_loss",
    # 建议型方向 DSL
    "confirm_long_when",
    "confirm_short_when",
    "trend_long_when",
    "trend_short_when",
    "confirm_long_when_compare",
    "confirm_short_when_compare",
    "trend_long_when_compare",
    "trend_short_when_compare",
]
