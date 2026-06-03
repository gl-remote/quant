"""内置指标计算函数

所有指标统一使用 pandas-ta 库实现。
"""

from typing import cast

import pandas as pd
import pandas_ta as ta


def sma_func(df: pd.DataFrame, period: int) -> pd.Series:
    return ta.sma(df["close"], length=period)


def ema_func(df: pd.DataFrame, period: int) -> pd.Series:
    return ta.ema(df["close"], length=period)


def rsi_func(df: pd.DataFrame, period: int = 14) -> pd.Series:
    return ta.rsi(df["close"], length=period)


def macd_func(df: pd.DataFrame, fast: int = 12, slow: int = 26,
              signal: int = 9) -> pd.Series:
    result = ta.macd(df["close"], fast=fast, slow=slow, signal=signal)
    return cast(pd.Series, result[f"MACDh_{fast}_{slow}_{signal}"])


def kdj_func(df: pd.DataFrame, n: int = 9, k_period: int = 3,
             d_period: int = 3) -> pd.Series:
    result = ta.kdj(high=df["high"], low=df["low"], close=df["close"],
                    length=n, signal=k_period)
    # pandas-ta 的 KDJ 列名只含 length 和 signal，不含 d_period
    return cast(pd.Series, result[f"J_{n}_{k_period}"])