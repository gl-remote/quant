"""with_trailing_take_profit — 回撤止盈切面（建议型）

依赖于 ctx.multi 中的 ATR 指标值，自动注册到 data_requirements。
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any, TypeVar

from common.constants import SIGNAL_TAKE_PROFIT, TRADE_DIRECTION_LONG, TRADE_DIRECTION_SHORT

from strategies.core.indicators import atr_func, generate_indicator_column_name
from strategies.strategy_aspects.primitives import RiskReason

T = TypeVar("T", bound=type)


def with_trailing_take_profit(period: str = "15m") -> Callable[[T], T]:
    """类装饰器工厂：为策略类注入回撤止盈建议切面

    Args:
        period: 读取 ATR 的多周期名称，默认 "15m"

    使用方式:
        @with_trailing_take_profit("15m")
        class MyStrategy(Strategy[MyParams]):
            ...

    行为:
      - 替换 data_requirements：自动将 ATR 指标注册到指定周期
      - 有持仓时检查回撤止盈条件，触发时将 RiskReason 写入 ctx.aspects.risk.take_profit.exit
      - 始终继续执行原始 on_bar，不拦截

    要求 strategy_config 包含:
      - atr_period: int
      - trailing_activation_atr: float — 激活倍数
      - trailing_drawdown_ratio: float — 回撤比例
    """

    def _decorator(cls: T) -> T:
        # ── 包装 data_requirements：自动注册 ATR 指标 ──
        original_dr = cls.data_requirements  # type: ignore[attr-defined]

        @functools.wraps(original_dr)
        def _dr_wrapper(self: Any, config: Any) -> Any:
            from ...core.indicators import IndicatorSpec
            from ...runtime.requirements import DataRequirements, PeriodRequirements

            base = original_dr(self, config)
            if base is None:
                return base

            extra = DataRequirements(
                periods={
                    period: PeriodRequirements(lookback_bars=config.atr_period + 1),
                },
                indicators={
                    period: [
                        IndicatorSpec(
                            name="atr", params={"period": config.atr_period}, func=atr_func, window=config.atr_period
                        )
                    ],
                },
            )
            base.merge(extra)
            return base

        cls.data_requirements = _dr_wrapper  # type: ignore[attr-defined]

        # ── 包装 on_bar：有持仓时写入回撤止盈建议 ──
        original_on_bar = cls.on_bar  # type: ignore[attr-defined]

        @functools.wraps(original_on_bar)
        def _on_bar_wrapper(self: Any, state: Any, ctx: Any) -> Any:
            direction = state.position.direction
            if not direction:
                return original_on_bar(self, state, ctx)

            config = state.strategy_config
            entry_price = state.position.entry_price
            close = ctx.bar.close

            ctx.aspects.diagnostics["entry_price"] = entry_price
            ctx.aspects.diagnostics["highest_price"] = state.position.highest_price
            ctx.aspects.diagnostics["lowest_price"] = state.position.lowest_price
            ctx.aspects.diagnostics["current_close"] = close

            period_view = ctx.multi.get(period)
            if period_view is None:
                return original_on_bar(self, state, ctx)

            atr_col = generate_indicator_column_name("atr", {"period": config.atr_period}, period=period)
            atr_value = period_view.indicator(atr_col, -1)
            if atr_value is None or atr_value <= 0:
                return original_on_bar(self, state, ctx)

            peak_price = (
                state.position.highest_price if direction == TRADE_DIRECTION_LONG else state.position.lowest_price
            )
            if peak_price <= 0:
                return original_on_bar(self, state, ctx)

            activation_threshold = atr_value * config.trailing_activation_atr

            if direction == TRADE_DIRECTION_LONG:
                if peak_price <= entry_price + activation_threshold:
                    return original_on_bar(self, state, ctx)
                triggered = (peak_price - close) / peak_price > config.trailing_drawdown_ratio
            elif direction == TRADE_DIRECTION_SHORT:
                if peak_price >= entry_price - activation_threshold:
                    return original_on_bar(self, state, ctx)
                triggered = (close - peak_price) / peak_price > config.trailing_drawdown_ratio
            else:
                triggered = False

            if triggered:
                ctx.aspects.risk.take_profit.exit.append(
                    RiskReason(
                        role="take_profit",
                        name=SIGNAL_TAKE_PROFIT,
                        detail={
                            "type": "trailing_stop",
                            "direction": direction,
                            "entry_price": entry_price,
                            "current_close": close,
                            "peak_price": peak_price,
                            "atr_value": float(atr_value),
                            "trailing_activation_atr": float(config.trailing_activation_atr),
                            "trailing_drawdown_ratio": float(config.trailing_drawdown_ratio),
                        },
                    )
                )

            return original_on_bar(self, state, ctx)

        cls.on_bar = _on_bar_wrapper  # type: ignore[attr-defined]
        return cls

    return _decorator
