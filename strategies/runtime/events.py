"""事件类型定义与管理

包含：
- Event 基类、BigTradeEvent、NewsEvent 等具体事件类型
- EventManager: 事件存储与查询，从 DataFeed 中提取的独立职责
"""

from dataclasses import dataclass
from datetime import datetime as dt
from typing import Any

import pandas as pd
from loguru import logger


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


class EventManager:
    """事件存储与查询管理器

    从 DataFeed 中提取的独立职责，封装事件的 DataFrame 存储、追加和筛选查询。
    """

    def __init__(self) -> None:
        self._df: pd.DataFrame = pd.DataFrame(columns=["type", "symbol", "reason", "period", "data"])
        self._df = self._df.astype({"type": "string", "symbol": "string", "reason": "string", "period": "string"})
        self._count = 0

    @property
    def df(self) -> pd.DataFrame:
        """获取底层 DataFrame（供序列化使用）"""
        return self._df

    @df.setter
    def df(self, value: pd.DataFrame) -> None:
        """设置底层 DataFrame（供反序列化使用）"""
        self._df = value
        self._count = len(value)

    @property
    def count(self) -> int:
        """已追加的事件总数"""
        return self._count

    def append(self, events: list[Event]) -> None:
        """批量追加事件数据

        :param events: 事件列表
        """
        if not events:
            return

        event_dicts = [
            {
                "datetime": pd.Timestamp(event.timestamp),
                "type": event.type,
                "symbol": event.symbol,
                "reason": event.reason,
                "period": event.period,
                "data": event.data,
            }
            for event in events
        ]

        new_df = pd.DataFrame(event_dicts).set_index("datetime")

        if len(self._df) == 0:
            self._df = new_df
        else:
            self._df = pd.concat([self._df, new_df])

        self._count += len(events)

    def query(
        self,
        start_time: pd.Timestamp | dt | None = None,
        end_time: pd.Timestamp | dt | None = None,
        event_type: str | None = None,
        period: str | None = None,
    ) -> list[Event]:
        """查询指定条件的事件

        :param start_time: 开始时间（可选）
        :param end_time: 结束时间（可选）
        :param event_type: 事件类型（可选）
        :param period: 周期名称筛选（可选，None表示所有事件）
        :return: 事件列表
        """
        if len(self._df) == 0:
            return []

        mask = pd.Series([True] * len(self._df), index=self._df.index)

        if start_time is not None:
            mask &= self._df.index >= pd.Timestamp(start_time)

        if end_time is not None:
            mask &= self._df.index <= pd.Timestamp(end_time)

        if event_type is not None:
            mask &= self._df["type"] == event_type

        if period is not None:
            mask &= (self._df["period"] == period) | (self._df["period"].isna())

        events_df = self._df[mask]
        # 已知的事件子类类型（序列化时只能存 type 字符串）
        subclass_types = frozenset({"big_trade", "news"})
        if len(events_df) > 0 and events_df["type"].isin(subclass_types).any():
            logger.warning("事件类型中包含子类（big_trade/news）但反序列化为基础 Event，子类额外字段将丢失")

        return [
            Event(
                timestamp=pd.Timestamp(row.name).to_pydatetime(),  # type: ignore[arg-type]
                type=row["type"],
                symbol=row["symbol"],
                reason=row.get("reason", ""),
                period=row.get("period"),
                data=row.get("data"),
            )
            for _, row in events_df.iterrows()
        ]
