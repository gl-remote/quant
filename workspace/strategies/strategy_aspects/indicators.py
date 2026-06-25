"""常用指标定义和工厂

提供预定义的 IndicatorSpec 常量和工厂函数，
供建议型切面 DSL 使用。
"""

from ..core.indicators import IndicatorSpec, atr_func, kdj_func, macd_func, sma_func

MACD = IndicatorSpec(
    name="macd",
    params={"fast": 12, "slow": 26, "signal": 9},
    window=35,
    func=macd_func,
)

KDJ = IndicatorSpec(
    name="kdj",
    params={"n": 9, "k_period": 3, "d_period": 3},
    window=9,
    func=kdj_func,
)


def SMA(period: int | str) -> IndicatorSpec:  # noqa: N802
    """SMA 指标工厂 — 支持模板值，如 SMA("{sma_short}")"""
    return IndicatorSpec(
        name="sma",
        params={"period": period},
        window=period,
        func=sma_func,
    )


def ATR(period: int | str = 14) -> IndicatorSpec:  # noqa: N802
    """ATR 指标工厂 — 支持模板值，如 ATR("{atr_period}")"""
    return IndicatorSpec(
        name="atr",
        params={"period": period},
        window=period,
        func=atr_func,
    )
