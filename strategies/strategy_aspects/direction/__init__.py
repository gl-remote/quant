"""建议型方向 DSL — 只写入 ctx.aspects.direction，不直接返回交易信号"""

from ._confirm import confirm_long_when, confirm_short_when
from ._trend import trend_long_when_compare, trend_short_when_compare

__all__ = [
    "confirm_long_when",
    "confirm_short_when",
    "trend_long_when_compare",
    "trend_short_when_compare",
]
