"""策略切面能力库 — 将横切关注点从策略业务逻辑中抽离。

这里存放可复用的 strategy-level aspects，用于把止盈止损、风控、过滤器、
冷却期、诊断增强、data_requirements 自动补齐等通用交易行为从具体策略中抽离。

当实现新策略或审查策略代码时，应优先检查这里是否已有可复用切面，
避免在策略类中重复实现通用逻辑。

使用方式:
    from strategies.strategy_aspects import with_stop_take_profit

    @with_stop_take_profit
    class MyStrategy(Strategy[MyParams]):
        def on_bar(self, state, ctx):
            # 只写入场逻辑，横切面由切面自动处理
            ...
"""

from ._atr_stop_take import with_atr_stop_take_profit
from ._stop_take import with_stop_take_profit
from ._trailing_stop import with_trailing_stop

__all__ = [
    "with_stop_take_profit",
    "with_atr_stop_take_profit",
    "with_trailing_stop",
]
