"""with_stop_take_profit — 固定比例止盈止损切面"""

from __future__ import annotations

import functools
from typing import Any, cast

from common.constants import (
    SIGNAL_STOP_LOSS,
    SIGNAL_TAKE_PROFIT,
    TRADE_ACTION_BUY,
    TRADE_ACTION_SELL,
    TRADE_DIRECTION_LONG,
)
from common.formulas import stop_loss_triggered, take_profit_triggered


def with_stop_take_profit(
    cls: type,
) -> type:
    """类装饰器：为策略类注入固定比例止盈止损切面

    使用方式:
        @with_stop_take_profit
        class MyStrategy(Strategy[MyParams]):
            def on_bar(self, state, ctx):
                # 只写入场逻辑
                ...

    行为:
      - 替换 on_bar：有持仓 → 先检查固定比例止盈/止损，未触发才交原始逻辑
      - 无持仓 → 直接交原始 on_bar

    要求 strategy_config 包含:
      - take_profit_ratio: float
      - stop_loss_ratio: float

    设计说明:
      - 运行时通过 state.strategy_config 读取参数，与 Optuna 参数搜索完全兼容
      - 触发时构造精简 diagnostics（entry_price, current_close 等），不依赖策略特定指标
      - 类装饰器模式便于后续扩展：可在同一个装饰器中包装 data_requirements（注册切面所需指标）
    """

    # ── 包装 on_bar：拦截有持仓时的固定比例止盈止损 ──
    original_on_bar = cls.on_bar  # type: ignore[attr-defined]

    @functools.wraps(original_on_bar)
    def _on_bar_wrapper(
        self: Any,
        state: Any,
        ctx: Any,
    ) -> Any:
        from ...core.types import Signal

        direction = state.position.direction

        # ── 有持仓：先检查固定比例止盈止损 ──
        if direction:
            config = state.strategy_config
            entry_price = state.position.entry_price
            close = ctx.bar.close
            volume = state.position.volume

            # 止盈检查（优先级高于止损）
            if take_profit_triggered(entry_price, close, config.take_profit_ratio, direction):
                action = TRADE_ACTION_SELL if direction == TRADE_DIRECTION_LONG else TRADE_ACTION_BUY
                signal = Signal(action=cast(Any, action), reason=SIGNAL_TAKE_PROFIT, volume=volume)
                signal.diagnostics = {
                    "entry_price": entry_price,
                    "highest_price": state.position.highest_price,
                    "lowest_price": state.position.lowest_price,
                    "current_close": close,
                }
                return signal

            # 止损检查
            if stop_loss_triggered(entry_price, close, config.stop_loss_ratio, direction):
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

    # ── 预留：切面需要额外数据指标时，在此合并 data_requirements ──
    # 例如 ATR 止损切面可以：
    # original_dr = cls.data_requirements
    # def _dr_wrapper(self, config):
    #     base = original_dr(self, config)
    #     base.indicators["15m"].append(IndicatorRequirements(name="atr", params={"period": config.atr_period}))
    #     return base
    # cls.data_requirements = _dr_wrapper

    return cls
