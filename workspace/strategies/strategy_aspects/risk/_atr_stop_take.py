"""with_atr_stop_take_profit — ATR 止盈止损切面

与固定比例止损止盈切面的区别:
  - 需要从 ctx.multi 读取 ATR 指标值（依赖 data_requirements 声明）
  - 因此需要同时包装 data_requirements 自动注册 ATR 指标
"""

from __future__ import annotations

import functools
from typing import Any, cast

from common.constants import (
    SIGNAL_STOP_LOSS,
    SIGNAL_TAKE_PROFIT,
    TRADE_ACTION_BUY,
    TRADE_ACTION_SELL,
    TRADE_DIRECTION_LONG,
    TRADE_DIRECTION_SHORT,
)

from strategies.core.indicators import atr_func, generate_indicator_column_name


def with_atr_stop_take_profit(period: str = "15m") -> Any:
    """类装饰器工厂：为策略类注入 ATR 止盈止损切面

    Args:
        period: 读取 ATR 指标的多周期名称，默认 "15m"

    使用方式:
        @with_atr_stop_take_profit("15m")
        class MyStrategy(Strategy[MyParams]):
            def on_bar(self, state, ctx):
                # 只写入场逻辑
                ...

    行为:
      - 替换 on_bar：有持仓 → 先检查 ATR 止盈/止损，未触发才交后续逻辑
      - 替换 data_requirements：自动将 ATR 指标注册到指定周期

    要求 strategy_config 包含:
      - atr_period: int — ATR 计算周期
      - atr_stop_loss_multiplier: float
      - atr_take_profit_multiplier: float
    """

    def _decorator(cls: type) -> type:
        # ── 包装 data_requirements：自动注册 ATR 指标 ──
        original_dr = cls.data_requirements  # type: ignore[attr-defined]

        @functools.wraps(original_dr)
        def _dr_wrapper(self: Any, config: Any) -> Any:
            from ...core.indicators import IndicatorSpec
            from ...runtime.requirements import DataRequirements

            base = original_dr(self, config)
            if base is None:
                return base

            from ...runtime.requirements import PeriodRequirements

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

        # ── 包装 on_bar：拦截有持仓时的 ATR 止盈止损 ──
        original_on_bar = cls.on_bar  # type: ignore[attr-defined]

        @functools.wraps(original_on_bar)
        def _on_bar_wrapper(
            self: Any,
            state: Any,
            ctx: Any,
        ) -> Any:
            from ...core.types import Signal

            direction = state.position.direction

            if direction:
                config = state.strategy_config
                entry_price = state.position.entry_price
                close = ctx.bar.close
                volume = state.position.volume

                # 从 ctx.multi 读取 ATR 值
                period_view = ctx.multi.get(period)
                if period_view is None:
                    return original_on_bar(self, state, ctx)

                atr_col = generate_indicator_column_name("atr", {"period": config.atr_period}, period=period)
                atr_value = period_view.indicator(atr_col, -1)
                if atr_value is None or atr_value <= 0:
                    return original_on_bar(self, state, ctx)

                action: str

                # ATR 止盈检查
                target_profit = atr_value * config.atr_take_profit_multiplier
                if direction == TRADE_DIRECTION_LONG:
                    triggered = close > entry_price + target_profit
                elif direction == TRADE_DIRECTION_SHORT:
                    triggered = close < entry_price - target_profit
                else:
                    triggered = False

                if triggered:
                    action = TRADE_ACTION_SELL if direction == TRADE_DIRECTION_LONG else TRADE_ACTION_BUY
                    signal = Signal(action=cast(Any, action), reason=SIGNAL_TAKE_PROFIT, volume=volume)
                    signal.diagnostics = {
                        "entry_price": entry_price,
                        "highest_price": state.position.highest_price,
                        "lowest_price": state.position.lowest_price,
                        "current_close": close,
                    }
                    return signal

                # ATR 止损检查
                max_loss = atr_value * config.atr_stop_loss_multiplier
                if direction == TRADE_DIRECTION_LONG:
                    triggered = close < entry_price - max_loss
                elif direction == TRADE_DIRECTION_SHORT:
                    triggered = close > entry_price + max_loss
                else:
                    triggered = False

                if triggered:
                    action = TRADE_ACTION_SELL if direction == TRADE_DIRECTION_LONG else TRADE_ACTION_BUY
                    signal = Signal(action=cast(Any, action), reason=SIGNAL_STOP_LOSS, volume=volume)
                    signal.diagnostics = {
                        "entry_price": entry_price,
                        "highest_price": state.position.highest_price,
                        "lowest_price": state.position.lowest_price,
                        "current_close": close,
                    }
                    return signal

            # ── 无持仓 / 未触发 → 交原始逻辑 ──
            return original_on_bar(self, state, ctx)

        cls.on_bar = _on_bar_wrapper  # type: ignore[attr-defined]
        return cls

    return _decorator
