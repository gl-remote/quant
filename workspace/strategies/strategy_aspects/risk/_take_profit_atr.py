"""with_take_profit_atr — ATR 止盈切面（建议型）"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any, TypeVar

from common.constants import SIGNAL_TAKE_PROFIT, TRADE_DIRECTION_LONG, TRADE_DIRECTION_SHORT

from strategies.core.indicators import atr_func, generate_indicator_column_name
from strategies.strategy_aspects.primitives import RiskReason

T = TypeVar("T", bound=type)


def with_take_profit_atr(period: str = "15m") -> Callable[[T], T]:
    """类装饰器工厂：为策略类注入 ATR 止盈建议切面

    Args:
        period: 读取 ATR 指标的多周期名称，默认 "15m"

    使用方式:
        @with_take_profit_atr("15m")
        class MyStrategy(Strategy[MyParams]):
            ...

    行为:
      - 有持仓 → 检查 ATR 止盈条件，触发时将 RiskReason 写入 ctx.aspects.risk.take_profit.exit
      - 始终继续执行原始 on_bar，不拦截
      - 自动将 ATR 指标注册到 data_requirements 的指定周期

    要求 strategy_config 包含:
      - atr_period: int
      - atr_take_profit_multiplier: float
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

        # ── 包装 on_bar ──
        original_on_bar = cls.on_bar  # type: ignore[attr-defined]

        @functools.wraps(original_on_bar)
        def _on_bar_wrapper(self: Any, state: Any, ctx: Any) -> Any:
            direction = state.position.direction

            if direction:
                config = state.strategy_config
                entry_price = state.position.entry_price
                close = ctx.bar.close

                ctx.aspects.diagnostics["entry_price"] = entry_price
                ctx.aspects.diagnostics["highest_price"] = state.position.highest_price
                ctx.aspects.diagnostics["lowest_price"] = state.position.lowest_price
                ctx.aspects.diagnostics["current_close"] = close

                period_view = ctx.multi.get(period)
                if period_view is not None:
                    atr_col = generate_indicator_column_name("atr", {"period": config.atr_period}, period=period)
                    atr_value = period_view.indicator(atr_col, -1)
                    if atr_value is not None and atr_value > 0:
                        target_profit = atr_value * config.atr_take_profit_multiplier
                        if direction == TRADE_DIRECTION_LONG:
                            tp_triggered = close > entry_price + target_profit
                        elif direction == TRADE_DIRECTION_SHORT:
                            tp_triggered = close < entry_price - target_profit
                        else:
                            tp_triggered = False

                        if tp_triggered:
                            ctx.aspects.risk.take_profit.exit.append(
                                RiskReason(
                                    role="take_profit",
                                    name=SIGNAL_TAKE_PROFIT,
                                    detail={
                                        "type": "atr",
                                        "direction": direction,
                                        "entry_price": entry_price,
                                        "current_close": close,
                                        "atr_value": float(atr_value),
                                        "atr_take_profit_multiplier": float(config.atr_take_profit_multiplier),
                                    },
                                )
                            )

            return original_on_bar(self, state, ctx)

        cls.on_bar = _on_bar_wrapper  # type: ignore[attr-defined]
        return cls

    return _decorator
