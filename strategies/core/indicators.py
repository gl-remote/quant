"""内置指标计算函数

所有指标统一使用 ta-lib C 库实现，输入输出通过 pd.DataFrame/pd.Series 边界转换。
ta-lib 只认 numpy 数组，pandas 依赖仅限于函数边界的薄壳转换层。
"""

import numpy as np
import pandas as pd
import talib
from numpy.typing import NDArray


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
