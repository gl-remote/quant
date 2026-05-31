"""DataFeed 全局单例缓存

管理多个品种的 DataFeed 实例，提供统一的路由入口。
"""

from datetime import datetime as dt
from typing import Dict, List, Optional, Union

import threading
import pandas as pd

from .data_feed import DataFeed
from .events import Event
from .period import PeriodDataView
from .requirements import DataRequirements
from ..core.types import Bar


class DataFeedCache:
    """数据馈送缓存（单例模式）

    【设计目标】
    - 单例模式，全局唯一入口
    - 管理多个 DataFeed 实例
    - 根据交易品种（symbol）区分不同的 DataFeed
    - 一个 symbol 对应一个 DataFeed
    - 支持策略测试时注入 mock 的 cache
    - 有自己的锁，保护 get_or_create 操作
    - 只做路由，实际数据操作委托给 DataFeed
    """

    _instance: Optional['DataFeedCache'] = None

    def __init__(self) -> None:
        self._datafeeds: Dict[str, DataFeed] = {}
        self._lock = threading.RLock()

    @classmethod
    def get_instance(cls) -> 'DataFeedCache':
        """获取单例（运行时使用）

        首次调用时自动创建实例，后续调用返回相同实例

        :return: DataFeedCache 单例
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def set_instance(cls, instance: Optional['DataFeedCache']) -> None:
        """设置单例（测试时用来注入 mock）

        :param instance: DataFeedCache 实例或None
        """
        cls._instance = instance

    def get_or_create(self, symbol: str, source: Optional[str] = None) -> DataFeed:
        """获取或创建DataFeed实例

        一个 symbol 对应一个 DataFeed

        :param symbol: 交易品种，如 "btc_usdt"
        :param source: 数据源标识（可选）
        :return: DataFeed 实例（新创建或已存在）
        """
        with self._lock:
            if symbol not in self._datafeeds:
                self._datafeeds[symbol] = DataFeed(symbol, source)
            return self._datafeeds[symbol]

    def update_bar(self, symbol: str, bar: Bar, period_name: str, events: Optional[List[Event]] = None) -> None:
        """更新指定品种的K线（路由到对应DataFeed）

        这是Bridge或数据接收层的主要调用入口

        :param symbol: 交易品种
        :param bar: K线数据
        :param period_name: 对应周期名称
        :param events: 事件数据（可选）
        """
        datafeed = self.get_or_create(symbol)
        datafeed.update_bar(bar, period_name, events)

    def get_data(self, symbol: str, period_name: str, current_time: Union[pd.Timestamp, dt],
                 lookback_bars: int = 1, timeout: Optional[float] = None) -> Optional[PeriodDataView]:
        """获取指定品种、指定周期的逻辑视图（策略主要访问入口）

        这是策略获取数据的主要方法

        :param symbol: 交易品种
        :param period_name: 周期名称
        :param current_time: 当前时间，视图只包含<=此时间的数据
        :param lookback_bars: 往前多少根K线
        :param timeout: 超时时间（秒），None表示回测模式（抛错），>0表示等待，0表示非阻塞
        :return: PeriodDataView只读逻辑视图
        :raises KeyError: 如果品种或周期未注册
        """
        datafeed = self.get_or_create(symbol)
        return datafeed.get_data(period_name, current_time, lookback_bars, timeout)

    def setup(self, symbol: str, requirements: DataRequirements) -> DataFeed:
        """按策略的数据需求声明配置 DataFeed

        回测引擎只需调用一次此方法，即可完成周期注册和指标注册。

        :param symbol: 交易品种
        :param requirements: 策略声明的数据需求
        :return: 配置完成的 DataFeed 实例
        """
        datafeed = self.get_or_create(symbol)

        for period_name in requirements.periods:
            datafeed.register_period(period_name)

        for period_name, indicators in requirements.indicators.items():
            for indicator in indicators:
                datafeed.register_indicator(period_name, indicator.name, **indicator.params)

        return datafeed