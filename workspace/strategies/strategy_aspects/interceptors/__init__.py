"""拦截型切面 — 触发后可以提前返回 Signal"""

from ._atr_stop_take import with_atr_stop_take_profit
from ._stop_take import with_stop_take_profit
from ._trade_cooldown import with_trade_cooldown
from ._trailing_stop import with_trailing_stop

__all__ = [
    "with_stop_take_profit",
    "with_atr_stop_take_profit",
    "with_trade_cooldown",
    "with_trailing_stop",
]
