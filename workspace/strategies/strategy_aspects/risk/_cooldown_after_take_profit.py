"""with_cooldown_after_take_profit — 止盈后冷静期建议切面"""

from __future__ import annotations

import functools
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, TypeVar

from common.constants import SIGNAL_TAKE_PROFIT, SIGNAL_TRADE_COOLDOWN

from strategies.strategy_aspects.primitives import RiskReason

T = TypeVar("T", bound=type)


def with_cooldown_after_take_profit(minutes: int) -> Callable[[T], T]:
    """类装饰器工厂：止盈成交后在指定分钟内产生入场阻断建议。

    冷却期基于 state.fills 中最近一笔成交时间计算，只在空仓时写入建议。
    """

    def _decorator(cls: T) -> T:
        original_on_bar = cls.on_bar  # type: ignore[attr-defined]

        @functools.wraps(original_on_bar)
        def _on_bar_wrapper(self: Any, state: Any, ctx: Any) -> Any:
            if not state.position.direction and state.fills:
                last_fill = state.fills[-1]
                if SIGNAL_TAKE_PROFIT in last_fill.reason:
                    last_fill_time = _parse_fill_time(last_fill.timestamp)
                    if last_fill_time is not None:
                        elapsed = ctx.bar.datetime - last_fill_time
                        cooldown = timedelta(minutes=minutes)
                        if elapsed < cooldown:
                            ctx.aspects.risk.take_profit.entry_block.append(
                                RiskReason(
                                    role="take_profit",
                                    name=SIGNAL_TRADE_COOLDOWN,
                                    detail={
                                        "cooldown_minutes": float(minutes),
                                        "elapsed_seconds": elapsed.total_seconds(),
                                        "remaining_seconds": (cooldown - elapsed).total_seconds(),
                                    },
                                )
                            )

            return original_on_bar(self, state, ctx)

        cls.on_bar = _on_bar_wrapper  # type: ignore[attr-defined]
        return cls

    return _decorator


def _parse_fill_time(timestamp: str) -> datetime | None:
    try:
        return datetime.fromisoformat(timestamp)
    except ValueError:
        return None
