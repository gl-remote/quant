"""内置指标计算函数

这些是框架自带的默认指标实现，仅供 strategies/runtime/ 注册使用。
依赖关系：仅依赖 pandas，不依赖 strategies/runtime/ 中的任何内容。
"""

from typing import cast

import pandas as pd


def sma_func(df: pd.DataFrame, period: int) -> pd.Series:
    """SMA指标计算函数 - 内置实现"""
    return cast(pd.Series, df['close'].rolling(window=period).mean())


def ema_func(df: pd.DataFrame, period: int) -> pd.Series:
    """EMA指标计算函数 - 内置实现"""
    return cast(pd.Series, df['close'].ewm(span=period, adjust=False).mean())


def rsi_func(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """RSI指标计算函数 - 内置实现"""
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return cast(pd.Series, 100 - (100 / (1 + rs)))