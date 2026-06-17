"""事件类型定义

包含：Event 基类、BigTradeEvent、NewsEvent 等具体事件类型。
"""

from dataclasses import dataclass
from datetime import datetime as dt
from typing import Any


@dataclass(kw_only=True)
class Event:
    """事件基类

    【设计原则】
    - 与 Bar.datetime 保持一致，使用 datetime 对象
    - 策略层无需关注底层存储细节
    - 内部实现可以自由转换为 pd.Timestamp

    【事件时间作用范围说明】
    - 事件时间戳表示事件发生的具体时间
    - 事件归属：根据时间戳，归属于时间区间包含该时间的 K 线
    - period 字段作用：
      - None：全局事件，所有周期的 K 线都可以看到该事件
      - "1m"：周期特定事件，只在 1m 周期的 K 线中可见
    """

    timestamp: dt  # 事件发生的时间
    type: str  # 'big_trade' | 'news' | 'orderbook_imbalance' | 'custom'
    symbol: str  # 交易品种
    reason: str = ""  # 事件原因/描述，类似 Signal.reason
    period: str | None = None  # None 表示全局事件，否则绑定到特定周期
    data: Any = None


@dataclass(kw_only=True)
class BigTradeEvent(Event):
    """大单成交事件"""

    price: float
    volume: float
    direction: str  # 'buy' | 'sell'


@dataclass(kw_only=True)
class NewsEvent(Event):
    """新闻事件"""

    title: str
    content: str | None = None
    importance: int = 1  # 1-5
