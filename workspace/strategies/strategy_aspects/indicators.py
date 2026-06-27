"""常用指标定义和工厂

提供预定义的 IndicatorSpec 常量和工厂函数，
供建议型切面 DSL 使用。

IndicatorSpec.window 统一表示“计算当前指标值所需的最小历史 bar 数”，不是业务参数窗口。
业务参数应写入 params，例如 KDJ 的 n=9、k_period=3、d_period=3。

window 设置规则：
- 简单滚动指标按直接依赖长度设置，如 SMA(period) 使用 period；
- TA-Lib 递推、平滑或组合指标按实际稳定输出所需输入长度设置，必须覆盖前置 NaN 和内部平滑；
- 如果指标需要比业务参数更多历史，直接放大 window，不另设额外字段。
"""

from ..core.indicators import IndicatorSpec, atr_func, kdj_func, macd_func, sma_func

IndicatorParam = int | float | str

MACD = IndicatorSpec(
    name="macd",
    params={"fast": 12, "slow": 26, "signal": 9},
    window=35,
    func=macd_func,
)

KDJ = IndicatorSpec(
    name="kdj",
    params={"n": 9, "k_period": 3, "d_period": 3},
    window=20,
    func=kdj_func,
)


def SMA(period: IndicatorParam) -> IndicatorSpec:  # noqa: N802
    """SMA 指标工厂 — 支持模板值，如 SMA("{sma_short}")"""
    return IndicatorSpec(
        name="sma",
        params={"period": period},
        window=period,
        func=sma_func,
    )


def ATR(period: IndicatorParam = 14) -> IndicatorSpec:  # noqa: N802
    """ATR 指标工厂 — 支持模板值，如 ATR("{atr_period}")"""
    return IndicatorSpec(
        name="atr",
        params={"period": period},
        window=period + 1 if isinstance(period, int) else period,
        func=atr_func,
    )


def build_indicator(name: str, params: tuple[IndicatorParam, ...]) -> IndicatorSpec | None:
    """按 DSL 指标名和参数构造 IndicatorSpec。"""
    if name == "macd":
        return MACD
    if name == "kdj":
        return KDJ
    if name == "sma":
        if not params:
            return None
        return SMA(params[0])
    if name == "atr":
        return ATR(params[0]) if params else ATR()
    return None
