"""常用指标定义和工厂

提供预定义的 IndicatorSpec 常量和工厂函数，
供建议型切面 DSL 使用。
"""

from __future__ import annotations

from .primitives import IndicatorSpec

MACD = IndicatorSpec(
    name="macd",
    column="macd_12_9_26",
    params={"fast": 12, "slow": 26, "signal": 9},
    window=35,
)

KDJ = IndicatorSpec(
    name="kdj",
    column="kdj_3_3_9",
    params={"n": 9, "k_period": 3, "d_period": 3},
    window=9,
)


def SMA(period: int | str) -> IndicatorSpec:  # noqa: N802
    """SMA 指标工厂 — 支持模板值，如 SMA("{sma_short}")"""
    return IndicatorSpec(
        name="sma",
        column=f"sma_{period}",
        params={"period": period},
        window=period,
    )
