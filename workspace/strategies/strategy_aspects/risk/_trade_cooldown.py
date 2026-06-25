"""with_trade_cooldown — 交易冷却期阻断切面"""

from __future__ import annotations

import functools
from datetime import datetime, timedelta
from typing import Any

from common.constants import SIGNAL_TRADE_COOLDOWN


def with_trade_cooldown(minutes: int) -> Any:
    """类装饰器工厂：成交后在指定分钟内阻断新的入场信号。

    冷却期基于 state.fills 中最近一笔成交时间计算，只在空仓时阻断，
    不影响已有持仓的止盈止损等出场逻辑。
    """

    def _decorator(cls: type) -> type:
        original_on_bar = cls.on_bar  # type: ignore[attr-defined]

        @functools.wraps(original_on_bar)
        def _on_bar_wrapper(self: Any, state: Any, ctx: Any) -> Any:
            from ...core.types import Signal

            if state.position.direction or not state.fills:
                return original_on_bar(self, state, ctx)

            last_fill_time = _parse_fill_time(state.fills[-1].timestamp)
            if last_fill_time is None:
                return original_on_bar(self, state, ctx)

            elapsed = ctx.bar.datetime - last_fill_time
            cooldown = timedelta(minutes=minutes)
            if elapsed < cooldown:
                signal = Signal(action="", reason=SIGNAL_TRADE_COOLDOWN, volume=0)
                signal.diagnostics = {
                    "cooldown_minutes": float(minutes),
                    "elapsed_seconds": elapsed.total_seconds(),
                    "remaining_seconds": (cooldown - elapsed).total_seconds(),
                }
                return signal

            return original_on_bar(self, state, ctx)

        cls.on_bar = _on_bar_wrapper  # type: ignore[attr-defined]
        return cls

    return _decorator


def _parse_fill_time(timestamp: str) -> datetime | None:
    try:
        return datetime.fromisoformat(timestamp)
    except ValueError:
        return None
