"""DataFeed 全局单例缓存

管理多个品种的 DataFeed 实例，提供统一的路由入口。

注意：当前 vnpy bridge 每条回测直接创建 DataFeed 实例，此缓存暂未使用。
保留类定义以便未来 TqSdk 实盘或多品种场景复用。
"""

from datetime import datetime as dt
from typing import Dict, List, Optional, Union

import pandas as pd

from .data_feed import DataFeed
from .events import Event
from .period import PeriodDataView
from .requirements import DataRequirements
from ..core.types import Bar


class DataFeedCache:
    """数据馈送缓存（单例模式）

    - 单例模式，全局唯一入口
    - 管理多个 DataFeed 实例
    - 一个 symbol 对应一个 DataFeed
    - 只做路由，实际数据操作委托给 DataFeed
    """

    _instance: Optional['DataFeedCache'] = None

    def __init__(self) -> None:
        self._datafeeds: Dict[str, DataFeed] = {}

    @classmethod
    def get_instance(cls) -> 'DataFeedCache':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def set_instance(cls, instance: Optional['DataFeedCache']) -> None:
        cls._instance = instance

    def get_or_create(self, symbol: str, source: Optional[str] = None) -> DataFeed:
        if symbol not in self._datafeeds:
            self._datafeeds[symbol] = DataFeed(symbol, source)
        return self._datafeeds[symbol]

    def update_bar(self, symbol: str, bar: Bar, period_name: str,
                   events: Optional[List[Event]] = None) -> None:
        datafeed = self.get_or_create(symbol)
        datafeed.update_bar(bar, period_name, events)

    def get_data(self, symbol: str, period_name: str,
                 current_time: Union[pd.Timestamp, dt],
                 lookback_bars: int = 1,
                 timeout: Optional[float] = None) -> Optional[PeriodDataView]:
        datafeed = self.get_or_create(symbol)
        return datafeed.get_data(period_name, current_time, lookback_bars, timeout)

    def setup(self, symbol: str, requirements: DataRequirements) -> DataFeed:
        datafeed = self.get_or_create(symbol)
        for period_name in requirements.periods:
            datafeed.register_period(period_name)
        for period_name, indicators in requirements.indicators.items():
            for indicator in indicators:
                datafeed.register_indicator(
                    period_name, indicator.name, **indicator.params)
        return datafeed