"""with_cooldown_after_take_profit — 止盈后冷静期建议切面"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any, TypeVar

from common.constants import SIGNAL_TAKE_PROFIT, SIGNAL_TRADE_COOLDOWN

from ._core import _entry_block_aspect, _parse_fill_time

T = TypeVar("T", bound=type)


def with_cooldown_after_take_profit(minutes: int) -> Callable[[T], T]:
    """类装饰器工厂：止盈成交后在指定分钟内产生入场阻断建议。"""

    def _trigger(state: Any, ctx: Any) -> tuple[bool, dict[str, Any]] | None:
        last_fill = state.fills[-1]
        if SIGNAL_TAKE_PROFIT not in last_fill.reason:
            return None
        last_fill_time = _parse_fill_time(last_fill.timestamp)
        if last_fill_time is None:
            return None
        elapsed = ctx.bar.datetime - last_fill_time
        cooldown = timedelta(minutes=minutes)
        if elapsed < cooldown:
            return True, {
                "cooldown_minutes": float(minutes),
                "elapsed_seconds": elapsed.total_seconds(),
                "remaining_seconds": (cooldown - elapsed).total_seconds(),
            }
        return None

    return _entry_block_aspect("take_profit", SIGNAL_TRADE_COOLDOWN, _trigger)
