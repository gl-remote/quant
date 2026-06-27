"""内置指标计算函数

所有指标统一使用 ta-lib C 库实现，输入输出通过 pd.DataFrame/pd.Series 边界转换。
ta-lib 只认 numpy 数组，pandas 依赖仅限于函数边界的薄壳转换层。
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import talib
from numpy.typing import NDArray


@dataclass(frozen=True)
class IndicatorSpec:
    """指标定义 — 描述指标如何计算

    window 可包含模板值（如 "{sma_short}"），在构建 data_requirements 时从 strategy_config 解析。
    """

    name: str
    params: dict[str, Any]
    window: int | str | float = 250
    func: Callable[..., NDArray[np.float64]] | None = None


def generate_indicator_column_name(name: str, params: dict[str, Any], period: str = "") -> str:
    """生成指标列名，按参数名称排序确保确定性

    :param name: 指标名称，如 "sma"
    :param params: 参数 dict，如 {"period": 10}
    :param period: 周期前缀，如 "5m" — 结果 "5m_sma_10"
    """
    sorted_params = sorted(params.items())
    param_parts = [f"{value}" for _, value in sorted_params]
    base = f"{name}_{'_'.join(param_parts)}" if param_parts else name
    return f"{period}_{base}" if period else base


def sma_func(df: pd.DataFrame, period: int) -> NDArray[np.float64]:
    return talib.SMA(np.asarray(df["close"], dtype=float), timeperiod=period)


def ema_func(df: pd.DataFrame, period: int) -> NDArray[np.float64]:
    return talib.EMA(np.asarray(df["close"], dtype=float), timeperiod=period)


def rsi_func(df: pd.DataFrame, period: int = 14) -> NDArray[np.float64]:
    return talib.RSI(np.asarray(df["close"], dtype=float), timeperiod=period)


def macd_func(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> NDArray[np.float64]:
    _, _, hist = talib.MACD(np.asarray(df["close"], dtype=float), fastperiod=fast, slowperiod=slow, signalperiod=signal)
    return hist


def kdj_func(df: pd.DataFrame, n: int = 9, k_period: int = 3, d_period: int = 3) -> NDArray[np.float64]:
    k, d = talib.STOCH(
        np.asarray(df["high"], dtype=float),
        np.asarray(df["low"], dtype=float),
        np.asarray(df["close"], dtype=float),
        fastk_period=n,
        slowk_period=k_period,
        slowd_period=d_period,
    )
    return 3 * k - 2 * d


def atr_func(df: pd.DataFrame, period: int = 14) -> NDArray[np.float64]:
    return talib.ATR(
        np.asarray(df["high"], dtype=float),
        np.asarray(df["low"], dtype=float),
        np.asarray(df["close"], dtype=float),
        timeperiod=period,
    )
