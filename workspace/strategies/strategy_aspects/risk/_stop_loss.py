"""with_stop_loss — 固定比例止损切面（建议型）"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any, TypeVar

from common.constants import SIGNAL_STOP_LOSS
from common.formulas import stop_loss_triggered

from strategies.strategy_aspects.primitives import RiskReason

T = TypeVar("T", bound=type)


def with_stop_loss(ratio: float | None = None) -> Callable[[T], T]:
    """类装饰器工厂：为策略类注入固定比例止损建议切面

    Args:
        ratio: 止损比例；为 None 时从 config.stop_loss_ratio 读取

    使用方式:
        @with_stop_loss()
        class MyStrategy(Strategy[MyParams]):
            ...

    行为:
      - 有持仓 → 检查止损条件，触发时将 RiskReason 写入 ctx.aspects.risk.stop_loss.exit
      - 无持仓 → 不写入
      - 始终继续执行原始 on_bar，不拦截
    """

    def _decorator(cls: T) -> T:
        original_on_bar = cls.on_bar  # type: ignore[attr-defined]

        @functools.wraps(original_on_bar)
        def _on_bar_wrapper(self: Any, state: Any, ctx: Any) -> Any:
            direction = state.position.direction

            if direction:
                config = state.strategy_config
                entry_price = state.position.entry_price
                close = ctx.bar.close
                sl_ratio = ratio if ratio is not None else config.stop_loss_ratio

                ctx.aspects.diagnostics["entry_price"] = entry_price
                ctx.aspects.diagnostics["highest_price"] = state.position.highest_price
                ctx.aspects.diagnostics["lowest_price"] = state.position.lowest_price
                ctx.aspects.diagnostics["current_close"] = close

                if stop_loss_triggered(entry_price, close, sl_ratio, direction):
                    ctx.aspects.risk.stop_loss.exit.append(
                        RiskReason(
                            role="stop_loss",
                            name=SIGNAL_STOP_LOSS,
                            detail={
                                "type": "fixed_ratio",
                                "direction": direction,
                                "entry_price": entry_price,
                                "current_close": close,
                                "stop_loss_ratio": float(sl_ratio),
                                "highest_price": state.position.highest_price,
                                "lowest_price": state.position.lowest_price,
                            },
                        )
                    )

            return original_on_bar(self, state, ctx)

        cls.on_bar = _on_bar_wrapper  # type: ignore[attr-defined]
        return cls

    return _decorator
