"""事件类型与模块级注册体系

包含：事件类型定义、指标计算模式/函数注册、周期转换函数注册。
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime as dt
from enum import Enum
from typing import Any

import pandas as pd

from ..core.types import Bar

# ==================== 事件类型定义 ====================


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


# ==================== 模块级指标计算函数注册 ====================


class IndicatorCalcMode(Enum):
    BATCH = "batch"  # 一次性计算所有数据（默认）
    INCREMENTAL = "incremental"  # 逐行/增量式计算，适合 update_bar 时触发


@dataclass
class IndicatorFuncInfo:
    func: Callable[..., pd.Series]
    calc_mode: IndicatorCalcMode
    name: str
    description: str | None = None


REGISTERED_INDICATOR_FUNCS: dict[str, IndicatorFuncInfo] = {}


def register_indicator_func(
    name: str,
    func: Callable[..., pd.Series],
    calc_mode: IndicatorCalcMode = IndicatorCalcMode.BATCH,
    description: str | None = None,
) -> None:
    """全局注册指标计算函数，所有 DataFeed 共享

    指标计算函数签名要求：
    def indicator_func(df: pd.DataFrame, **params) -> pd.Series

    【指标列名生成规则】
    - 列名格式：{indicator_name}_{param1_value}_{param2_value}_...
    - 参数按函数定义时的参数列表顺序排列
    - 参数值使用字符串表示，特殊字符转义
    - 示例：
      - 假设函数定义为 def sma(df, period): ...
        - sma(period=10) → sma_10
      - 假设函数定义为 def bbands(df, period, std): ...
        - bbands(period=20, std=2) → bbands_20_2
        - bbands(std=2, period=20) → bbands_20_2（同样按函数定义顺序）

    :param name: 指标名称
    :param func: 计算函数
    :param calc_mode: 计算模式，BATCH（默认）一次性全量计算，INCREMENTAL适合实时增量
    :param description: 指标描述（可选）
    """
    REGISTERED_INDICATOR_FUNCS[name] = IndicatorFuncInfo(
        func=func, calc_mode=calc_mode, name=name, description=description
    )


def generate_indicator_column_name(name: str, params: dict[str, Any]) -> str:
    """生成指标列名

    【参数顺序】
    - 按参数名称排序，确保参数顺序不影响列名生成
    """
    sorted_params = sorted(params.items())
    param_parts = [f"{value}" for _, value in sorted_params]
    if param_parts:
        return f"{name}_{'_'.join(param_parts)}"
    return name


# ==================== 模块级周期转换函数注册 ====================

REGISTERED_CONVERTERS: dict[tuple[str, str], Callable[..., list[Bar]]] = {}


def register_period_converter(source_period: str, target_period: str, func: Callable[..., list[Bar]]) -> None:
    """全局注册周期转换函数

    支持两种场景：
    1. 从低级周期生成高级K线（1m → 5m）
    2. 跨周期指标计算（用 1m 数据计算 5m 指标）

    转换函数签名要求（K线聚合场景）：
    def converter_func(source_data: PeriodData) -> List[Bar]

    :param source_period: 源周期（如 "1m"）
    :param target_period: 目标周期（如 "5m"）
    :param func: 转换函数
    """
    REGISTERED_CONVERTERS[(source_period, target_period)] = func
