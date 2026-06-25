"""with_trailing_take_profit — 回撤止盈切面（建议型）

依赖于 ctx.multi 中的 ATR 指标值，自动注册到 data_requirements。
"""

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


def with_trailing_take_profit(period: str = "15m") -> Callable[[T], T]:
    """类装饰器工厂：为策略类注入回撤止盈建议切面"""

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

        peak_price = state.position.highest_price if direction == TRADE_DIRECTION_LONG else state.position.lowest_price
        if peak_price <= 0:
            return None

        activation_threshold = atr_value * config.trailing_activation_atr

        if direction == TRADE_DIRECTION_LONG:
            if peak_price <= entry_price + activation_threshold:
                return None
            triggered = (peak_price - close) / peak_price > config.trailing_drawdown_ratio
        elif direction == TRADE_DIRECTION_SHORT:
            if peak_price >= entry_price - activation_threshold:
                return None
            triggered = (close - peak_price) / peak_price > config.trailing_drawdown_ratio
        else:
            triggered = False

        if triggered:
            return True, {
                "type": "trailing_stop",
                "direction": direction,
                "entry_price": entry_price,
                "current_close": close,
                "peak_price": peak_price,
                "atr_value": float(atr_value),
                "trailing_activation_atr": float(config.trailing_activation_atr),
                "trailing_drawdown_ratio": float(config.trailing_drawdown_ratio),
            }
        return None

    return _decorator
