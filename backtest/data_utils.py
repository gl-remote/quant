"""
回测数据转换工具

提供:
  - df_to_vnpy_datalines: DataFrame → vnpy BarData 列表
  - INTERVAL_MAP: 周期字符串 → vnpy Interval 枚举
"""

from __future__ import annotations

from loguru import logger
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from vnpy.trader.constant import Interval
    from vnpy.trader.object import BarData

INTERVAL_MAP: dict[str, Interval] = {}


def _init_interval_map() -> dict[str, Interval]:
    """懒初始化周期映射表"""
    global INTERVAL_MAP
    if INTERVAL_MAP:
        return INTERVAL_MAP
    from vnpy.trader.constant import Interval

    INTERVAL_MAP.update({
        '1m': getattr(Interval, 'MINUTE', Interval.MINUTE),
        '5m': getattr(Interval, 'MINUTE_5', Interval.MINUTE),
        '15m': getattr(Interval, 'MINUTE_15', Interval.MINUTE),
        '30m': getattr(Interval, 'MINUTE_30', Interval.MINUTE),
        '1h': Interval.HOUR,
        'd': Interval.DAILY,
    })
    return INTERVAL_MAP


def resolve_interval(interval_str: str) -> Interval:
    """解析周期字符串为 vnpy Interval 枚举

    Args:
        interval_str: 周期字符串，如 '1m', '5m', 'd'

    Returns:
        vnpy Interval 枚举值
    """
    return _init_interval_map().get(interval_str, _init_interval_map()['d'])


def df_to_vnpy_datalines(
    df: pd.DataFrame,
    pure_symbol: str,
    exchange_code: str,
    interval: Interval | None = None,
) -> list[BarData]:
    """将 DataFrame 转换为 vn.py 回测引擎可用的 BarData 列表

    将 K 线 CSV (datetime, open, high, low, close, volume) 转换为
    vnpy BarData 对象列表，可直接注入 BacktestingEngine.history_data

    Args:
        df: K 线数据
        pure_symbol: 纯品种代号 (e.g. m2509)
        exchange_code: 交易所代码 (e.g. DCE)
        interval: vnpy Interval 枚举，None 时回退到 Interval.DAILY

    Returns:
        vnpy BarData 对象列表
    """
    from vnpy.trader.object import BarData
    from vnpy.trader.constant import Exchange, Interval

    required_cols = {'datetime', 'open', 'high', 'low', 'close', 'volume'}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"数据缺少必要列: {missing}")

    exchange: Exchange = Exchange(exchange_code)
    bar_interval: Interval = interval if interval is not None else Interval.DAILY

    bars: list[BarData] = [
        BarData(
            symbol=pure_symbol,
            exchange=exchange,
            datetime=pd.Timestamp(row['datetime']).to_pydatetime(),
            interval=bar_interval,
            open_price=row['open'],
            high_price=row['high'],
            low_price=row['low'],
            close_price=row['close'],
            volume=row['volume'],
            gateway_name="CSV",
        )
        for row in df.to_dict(orient='records')
    ]

    logger.info(f"转换完成: {len(bars)} 条 BarData")
    return bars