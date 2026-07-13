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

    window 表示计算当前指标值所需的最小历史 bar 数，可包含模板值（如 "{sma_short}"），
    在构建 data_requirements 时从 strategy_config 解析。
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


def daily_atr_bps_func(df: pd.DataFrame, period: int = 10) -> NDArray[np.float64]:
    """日线 ATR(period) / close * 10000，产出 bps 量纲的波动率。

    用于 va-asymmetry-composite 策略的 A 层日线波动率基准：
    - 止损/sizing 直接消费 bps 值；
    - t-PIT 归一化中 bps 与原始 ATR 秩等价（MAD/中位数线性不变）。

    2026-07-13 修正：ATR 平滑方式从 Wilder's（talib.ATR，指数衰减 α=1/N）
    改为等权 SMA(TR, N)，与研究侧 poc_va.daily_atr_sma 对齐（诊断报告 §5
    差异 1，影响权重 ★★★★★）。
    """
    high = np.asarray(df["high"], dtype=float)
    low = np.asarray(df["low"], dtype=float)
    close = np.asarray(df["close"], dtype=float)
    prev_close = np.concatenate([[np.nan], close[:-1]])
    tr = np.maximum.reduce(
        [
            high - low,
            np.abs(high - prev_close),
            np.abs(low - prev_close),
        ]
    )
    atr = pd.Series(tr).rolling(period, min_periods=period).mean().to_numpy(dtype=float)
    close_safe = np.where(close > 0, close, np.nan)
    return atr / close_safe * 10000.0
