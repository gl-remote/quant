"""with_take_profit_atr — ATR 止盈切面（建议型）"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from common.constants import SIGNAL_TAKE_PROFIT, TRADE_DIRECTION_LONG, TRADE_DIRECTION_SHORT

from strategies.core.indicators import generate_indicator_column_name

from ._core import (
    _atr_data_requirements_builder,
    _exit_aspect,
    _wrap_data_requirements,
    _write_position_diagnostics,
)

T = TypeVar("T", bound=type)


def with_take_profit_atr(period: str = "15m") -> Callable[[T], T]:
    """类装饰器工厂：为策略类注入 ATR 止盈建议切面"""

    def _decorator(cls: T) -> T:
        _wrap_data_requirements(cls, _atr_data_requirements_builder(period))
        return _exit_aspect("take_profit", SIGNAL_TAKE_PROFIT, _trigger)(cls)

    def _trigger(state: Any, ctx: Any, direction: str) -> tuple[bool, dict[str, Any]] | None:
        config = state.strategy_config
        entry_price = state.position.entry_price
        close = ctx.bar.close
        _write_position_diagnostics(ctx, state, close)

        period_view = ctx.multi.get(period)
        if period_view is None:
            return None

        atr_col = generate_indicator_column_name("atr", {"period": config.atr_period}, period=period)
        atr_value = period_view.indicator(atr_col, -1)
        if atr_value is None or atr_value <= 0:
            return None

        target_profit = atr_value * config.atr_take_profit_multiplier
        if direction == TRADE_DIRECTION_LONG:
            tp_triggered = close > entry_price + target_profit
        elif direction == TRADE_DIRECTION_SHORT:
            tp_triggered = close < entry_price - target_profit
        else:
            tp_triggered = False

        if tp_triggered:
            return True, {
                "type": "atr",
                "direction": direction,
                "entry_price": entry_price,
                "current_close": close,
                "atr_value": float(atr_value),
                "atr_take_profit_multiplier": float(config.atr_take_profit_multiplier),
            }
        return None

    return _decorator
