"""with_take_profit — 固定比例止盈切面（建议型）"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from common.constants import SIGNAL_TAKE_PROFIT
from common.formulas import take_profit_triggered

from ._core import _exit_aspect, _write_position_diagnostics

T = TypeVar("T", bound=type)


def with_take_profit(ratio: float | None = None) -> Callable[[T], T]:
    """类装饰器工厂：为策略类注入固定比例止盈建议切面"""

    def _trigger(state: Any, ctx: Any, direction: str) -> tuple[bool, dict[str, Any]] | None:
        config = state.strategy_config
        entry_price = state.position.entry_price
        close = ctx.bar.close
        tp_ratio = ratio if ratio is not None else config.take_profit_ratio
        _write_position_diagnostics(ctx, state, close)
        if take_profit_triggered(entry_price, close, tp_ratio, direction):
            return True, {
                "type": "fixed_ratio",
                "direction": direction,
                "entry_price": entry_price,
                "current_close": close,
                "take_profit_ratio": float(tp_ratio),
                "highest_price": state.position.highest_price,
                "lowest_price": state.position.lowest_price,
            }
        return None

    return _exit_aspect("take_profit", SIGNAL_TAKE_PROFIT, _trigger)
