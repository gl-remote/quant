"""量化策略数据管理模块

【架构设计】
- DataFeed: 管理单个品种的多周期数据，负责调度计算和事件管理
- DataFeedCache: 单例模式，管理多个品种的DataFeed

【并发安全】
- 基于条件变量的Append-Only快照机制
- 只在DataFeed级别加锁
- 读操作检查时间戳，保障数据一致性

【指标计算】
- 支持批量(BATCH)和增量(INCREMENTAL)两种模式
- 模块级注册，所有DataFeed共享
- 懒加载按需计算，避免不必要的开销
"""

from datetime import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import pandas as pd

from .events import (
    Event,
    IndicatorCalcMode,
    REGISTERED_CONVERTERS,
    REGISTERED_INDICATOR_FUNCS,
    generate_indicator_column_name,
    register_indicator_func,
)
from .period import PeriodData, PeriodDataView
from .requirements import BarContext, DataRequirements
from ..core.types import Bar
from ..core.indicators import sma_func, ema_func, rsi_func


def _parse_source_from_symbol(symbol: str) -> Optional[str]:
    """从symbol解析source，如 "CZCE.sr509" -> source="CZCE"

    :param symbol: 交易品种
    :return: source，解析失败返回None
    """
    if '.' in symbol:
        return symbol.split('.')[0]
    return None


# parquet 序列化时区分 OHLCV 列和指标列
_OHLCV_COLUMNS = frozenset({"open", "high", "low", "close", "volume"})

# 检查 pyarrow 是否可用（parquet 必需），避免回测因缺少依赖而全挂
try:
    import pyarrow  # noqa: F401
    _PARQUET_OK = True
except ImportError:
    _PARQUET_OK = False


class DataFeed:
    """管理单个品种的多周期数据

    【设计目标】
    - 管理单个品种（symbol）的所有周期数据
    - 持有该品种的元数据（symbol、数据源等）
    - 提供统一的 update_bar 入口，调度所有相关计算
    - 基于条件变量的快照等待机制（只在 DataFeed 级别加锁）
    - 提供高效的数据访问路由（通过周期名快速定位 PeriodData）
    - 统一管理 K线、指标、事件 三类数据
    - 支持周期转换（从1m数据衍生出5m数据）
    - 回测前统一注册所有指标，避免实时计算的不同步问题
    """

    def __init__(self, symbol: str, source: Optional[str] = None):
        """初始化单个品种的多周期数据管理器

        :param symbol: 交易品种，如 "btc_usdt" 或 "CZCE.sr509"
        :param source: 数据源标识（可选，如果不提供可从symbol解析）
        """
        self.symbol = symbol
        if source is None:
            self.source = _parse_source_from_symbol(symbol)
        else:
            self.source = source

        # 周期数据管理
        self._periods: Dict[str, PeriodData] = {}

        # 事件数据管理
        self._events = pd.DataFrame(columns=['type', 'symbol', 'reason', 'period', 'data'])
        self._events = self._events.astype({
            'type': 'string',
            'symbol': 'string',
            'reason': 'string',
            'period': 'string'
        })

        # 并发控制

        # 指标注册配置
        self._registered_indicators: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}

        # 周期转换配置
        self._period_conversions: Dict[Tuple[str, str], Callable[..., List[Bar]]] = REGISTERED_CONVERTERS.copy()
        self._derived_periods: Dict[str, str] = {}

        # 数据追踪字段（类似数据库表）
        self._created_at = pd.Timestamp.now()
        self._last_updated_at = pd.Timestamp.now()
        self._update_count = 0
        self._event_count = 0

    def register_period(self, period: str) -> PeriodData:
        """注册一个新的周期，创建对应的PeriodData实例

        :param period: 周期名称，如 "1m", "5m", "1h"
        :return: 新创建或已存在的PeriodData实例
        """
        if period not in self._periods:
            self._periods[period] = PeriodData(period)
        return self._periods[period]

    def register_indicator(self, period_name: str, indicator_name: str, **params: Any) -> None:
        """为指定周期注册需要计算的指标

        指标不会立即计算，第一次访问时才懒加载；计算方式灵活（全量/逐行都支持）

        参数组合示例：
        - register_indicator("5m", "sma", period=10) → 生成列 "sma_10"
        - register_indicator("5m", "sma", period=20) → 生成列 "sma_20"
        - register_indicator("5m", "ema", period=20) → 生成列 "ema_20"

        【指标计算说明】
        - BATCH 模式指标始终在完整的 PeriodData._df 上计算
        - 数据访问是通过逻辑视图（时间戳/索引范围），不复制数据，不触发重新计算
        - calculate_all() 的作用是预计算所有注册指标，避免运行时懒加载延迟
        - 如果某个指标已经计算过，calculate_all() 会跳过该指标
        - 指标函数接收的是完整 DataFrame，不应该假设或依赖数据范围

        :param period_name: 周期名称
        :param indicator_name: 指标名称，需已在模块级注册
        :param params: 指标参数，将传递给计算函数
        :raises KeyError: 如果周期未注册或指标函数未注册
        """
        if period_name not in self._periods:
            raise KeyError(f"Period {period_name} not registered")

        if indicator_name not in REGISTERED_INDICATOR_FUNCS:
            raise KeyError(f"Indicator function {indicator_name} not registered")

        if period_name not in self._registered_indicators:
            self._registered_indicators[period_name] = []

        # 检查是否已注册
        for existing_name, existing_params in self._registered_indicators[period_name]:
            if existing_name == indicator_name and existing_params == params:
                return  # 已注册，无需重复

        self._registered_indicators[period_name].append((indicator_name, params))

    def load_history_data(self, period: str, bars: List[Bar], events: Optional[List[Event]] = None) -> None:
        """批量加载历史数据（用于回测初始化）

        幂等加载：按数据范围智能处理重复调用
        - 时间范围一致 → 跳过
        - 起始时间相同，结束时间更新 → 仅追加增量
        - 起始时间不同 → 清空该周期数据，全量加载

        注意：
        1. 不会自动计算指标，需调用calculate_all()

        :param period: 周期名称
        :param bars: 历史K线列表，需按时间升序排列
        :param events: 历史事件列表（可选）
        """
        if period not in self._periods:
            self.register_period(period)

        if not bars:
            return

        new_start = pd.Timestamp(bars[0].datetime)
        new_end = pd.Timestamp(bars[-1].datetime)
        period_data = self._periods[period]

        if period_data.length > 0:
            existing_start = period_data.first_time
            existing_end = period_data.latest_time

            if new_start == existing_start and new_end <= existing_end:
                return  # 数据已包含，跳过
            elif new_start == existing_start and new_end > existing_end:
                append_bars = [b for b in bars if pd.Timestamp(b.datetime) > existing_end]
                period_data.append_bars(append_bars)
            else:
                period_data.load_df(_bars_to_df(bars), replace=True)
        else:
            period_data.load_df(_bars_to_df(bars), replace=False)

        if events:
            self.append_events(events)

    def load_history_df(self, period: str, df: pd.DataFrame, events: Optional[List[Event]] = None) -> None:
        """从 DataFrame 直接加载历史数据（避免 Bar 转换开销）

        幂等加载：按数据范围智能处理重复调用
        - 时间范围一致 → 跳过
        - 起始时间相同，结束时间更新 → 仅追加增量行
        - 起始时间不同 → 清空该周期数据，全量加载

        并发安全：全程持有 DataFeed 锁，防止多线程 check-then-write 竞态。

        注意：
        1. 不会自动计算指标，需调用calculate_all()
        2. DataFrame 要求索引为 datetime

        :param period: 周期名称
        :param df: K线 DataFrame，索引为 datetime
        :param events: 历史事件列表（可选）
        """
        if period not in self._periods:
            self.register_period(period)

        if len(df) == 0:
            return

        new_start = df.index[0]
        new_end = df.index[-1]
        period_data = self._periods[period]

        if period_data.length > 0:
            existing_start = period_data.first_time
            existing_end = period_data.latest_time

            if new_start == existing_start and new_end <= existing_end:
                return  # 数据已包含，跳过
            elif new_start == existing_start and new_end > existing_end:
                append_df = df.loc[df.index > existing_end]
                if len(append_df) > 0:
                    period_data.load_df(append_df, replace=False)
            else:
                period_data.load_df(df, replace=True)
        else:
            period_data.load_df(df, replace=False)

        if events:
            self.append_events(events)

    def append_event(self, event: Event) -> None:
        """追加事件数据

        :param event: 事件对象
        """
        event_time = pd.Timestamp(event.timestamp)
        new_row = pd.Series({
            'type': event.type,
            'symbol': event.symbol,
            'reason': event.reason,
            'period': event.period,
            'data': event.data
        }, name=event_time)

        if len(self._events) == 0:
            self._events = new_row.to_frame().T
        else:
            self._events = pd.concat([self._events, new_row.to_frame().T])

        self._event_count += 1
        self._last_updated_at = pd.Timestamp.now()

    def append_events(self, events: List[Event]) -> None:
        """批量追加事件数据

        :param events: 事件列表
        """
        if not events:
            return

        event_dicts = []
        for event in events:
            event_dicts.append({
                'datetime': pd.Timestamp(event.timestamp),
                'type': event.type,
                'symbol': event.symbol,
                'reason': event.reason,
                'period': event.period,
                'data': event.data
            })

        new_df = pd.DataFrame(event_dicts)
        new_df = new_df.set_index('datetime')

        if len(self._events) == 0:
            self._events = new_df
        else:
            self._events = pd.concat([self._events, new_df])

        self._event_count += len(events)
        self._last_updated_at = pd.Timestamp.now()

    def get_events(self, start_time: Optional[Union[pd.Timestamp, dt]] = None,
                   end_time: Optional[Union[pd.Timestamp, dt]] = None,
                   event_type: Optional[str] = None,
                   period: Optional[str] = None) -> List[Event]:
        """获取指定时间范围内的事件

        :param start_time: 开始时间（可选）
        :param end_time: 结束时间（可选）
        :param event_type: 事件类型（可选）
        :param period: 周期名称筛选（可选，None表示所有事件）
        :return: 事件列表
        """
        if len(self._events) == 0:
            return []

        mask = pd.Series([True] * len(self._events), index=self._events.index)

        if start_time is not None:
            mask &= (self._events.index >= pd.Timestamp(start_time))

        if end_time is not None:
            mask &= (self._events.index <= pd.Timestamp(end_time))

        if event_type is not None:
            mask &= (self._events['type'] == event_type)

        if period is not None:
            mask &= ((self._events['period'] == period) | (self._events['period'].isna()))

        events_df = self._events[mask]

        events = []
        for _, row in events_df.iterrows():
            event = Event(
                timestamp=row.name.to_pydatetime(),
                type=row['type'],
                symbol=row['symbol'],
                reason=row.get('reason', ''),
                period=row.get('period'),
                data=row.get('data')
            )
            events.append(event)

        return events

    def get_events_at_bar(self, bar_time: Union[pd.Timestamp, dt], period: str) -> List[Event]:
        """获取指定K线时间范围内的所有事件（包括全局事件和该周期的特定事件）

        【事件时间归属规则】
        - K线时间戳表示周期开始时间，周期持续时间由周期名称决定（如 1m 表示 60 秒）
        - K线的时间区间为 [bar.datetime, bar.datetime + period_duration)
        - 事件时间戳落在该区间内即归属于该K线
        - 事件时间戳精度可以高于K线精度（如毫秒级事件归属到秒级K线）
        - 边界情况：事件时间戳等于 K线结束时间的，归属到下一根 K线
        - 事件分为两类：
          - 全局事件（period=None）：归属于时间范围内所有周期的 K线
          - 周期特定事件（period="1m" 等）：只归属于对应周期的 K线

        :param bar_time: K线时间
        :param period: 周期名称
        :return: 事件列表
        """
        # 简单实现：使用bar_time作为时间点，查找时间<=bar_time的事件
        # 更精确的实现需要解析period计算时间区间
        return self.get_events(end_time=bar_time)

    def update_bar(self, bar: Bar, period: str, events: Optional[List[Event]] = None) -> None:
        """更新一根K线

        :param bar: 新K线数据
        :param period: 周期名称
        :param events: 归属于这根 K线 时间范围内的事件（可选）。
        :raises KeyError: 如果周期未注册
        """
        if period not in self._periods:
            raise KeyError(f"Period {period} not registered")

        self._periods[period].append_bar(bar)

        if events:
            self.append_events(events)

        self._check_period_conversion(period)

    def _check_period_conversion(self, source_period: str) -> None:
        """检查是否触发周期转换（内部方法）

        :param source_period: 源周期
        """
        # 这里是简化实现，实际项目中需要硬编码常见的周期转换关系
        # 例如：1m -> 5m, 1m -> 15m, 1m -> 1h 等
        # 目前先留空，后续根据需要实现
        pass

    def _calculate_indicators_for_period(self, period_name: str) -> None:
        """计算指定周期的所有注册指标（内部方法）

        :param period_name: 周期名称
        """
        if period_name not in self._periods:
            return

        period_data = self._periods[period_name]

        if period_name not in self._registered_indicators:
            return

        for indicator_name, params in self._registered_indicators[period_name]:
            col_name = generate_indicator_column_name(indicator_name, params)

            # 检查是否已计算
            if period_data.is_indicator_calculated(col_name):
                continue

            # 获取指标函数信息
            func_info = REGISTERED_INDICATOR_FUNCS.get(indicator_name)
            if func_info is None:
                continue

            # 计算指标
            try:
                series = period_data.apply_indicator(func_info.func, **params)
                period_data.set_indicator_column(col_name, series)
                period_data.mark_indicator_calculated(col_name)
            except Exception:
                # 计算失败，跳过该指标
                pass

    def calculate_all(self) -> None:
        """批量预计算所有周期的所有指标（可选，用于回测初始化性能优化）

        适用场景：
        - 回测开始前，所有历史数据已加载
        - 希望一次性预计算所有指标，避免运行时懒加载的轻微延迟

        注意：
        - 不是必须调用，不调用也能用
        - 会覆盖已有的指标数据
        - 会遍历所有周期，计算所有注册指标
        - 如果某个指标已经计算过，会跳过该指标
        """
        for period_name in self._periods:
            self._calculate_indicators_for_period(period_name)

    # ── parquet 持久化 ────────────────────────────────────────

    OHLCV_COLUMNS: set[str] = {"open", "high", "low", "close", "volume"}

    def to_feeds(self, feeds_dir: str) -> None:
        """将全部周期数据 + events + 元数据写为 parquet 文件

        每个周期存 {period}.parquet，events 存 events.parquet，
        元数据（symbol/source/periods/indicators）存 _meta.json。

        如果 pyarrow 不可用，静默跳过写入（回测结果不受影响）。
        :param feeds_dir: 目标目录路径（自动创建）
        """
        if not _PARQUET_OK:
            return

        Path(feeds_dir).mkdir(parents=True, exist_ok=True)

        # 构建 _meta.json
        indicators_serializable: Dict[str, List[Dict[str, Any]]] = {}
        for pn, ind_list in self._registered_indicators.items():
            indicators_serializable[pn] = [
                {"name": n, "params": p} for n, p in ind_list
            ]
        meta = {
            "symbol": self.symbol,
            "source": self.source,
            "periods": list(self._periods.keys()),
            "indicators": indicators_serializable,
        }
        meta_path = os.path.join(feeds_dir, "_meta.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        # 各周期 parquet
        for period_name, period_data in self._periods.items():
            fp = os.path.join(feeds_dir, f"{period_name}.parquet")
            period_data._df.to_parquet(fp, index=True)  # pyright: ignore[reportPrivateUsage]

        # events
        if not self._events.empty:
            events_fp = os.path.join(feeds_dir, "events.parquet")
            self._events.to_parquet(events_fp, index=False)

    @classmethod
    def from_feeds(cls, feeds_dir: str) -> "DataFeed":
        """从 parquet 文件恢复完整 DataFeed 实例

        恢复内容包括：周期数据（含 OHLCV 和指标列）、events 表、
        指标注册配置和已计算标记。加载后无需再调 calculate_all()。

        如果 pyarrow 不可用，抛出 ImportError，调用方应降级到全量流程。

        :param feeds_dir: 源目录路径
        :return: 恢复的 DataFeed 实例
        :raises FileNotFoundError: feeds_dir 或 _meta.json 不存在
        :raises ImportError: pyarrow 不可用
        """
        meta_path = os.path.join(feeds_dir, "_meta.json")
        if not os.path.isfile(meta_path):
            raise FileNotFoundError(f"元数据文件不存在: {meta_path}")

        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        feed = cls(symbol=meta["symbol"])
        if meta.get("source"):
            feed.source = meta["source"]

        # 恢复每个周期
        for period_name in meta["periods"]:
            fp = os.path.join(feeds_dir, f"{period_name}.parquet")
            if not os.path.isfile(fp):
                continue
            df = pd.read_parquet(fp)
            # 识别指标列（非 OHLCV 的列）
            indicator_cols = [c for c in df.columns if c not in cls.OHLCV_COLUMNS]
            feed.register_period(period_name)
            feed._periods[period_name].load_df_parquet(df, indicator_cols)

        # 恢复指标注册配置
        for pn, ind_list in meta.get("indicators", {}).items():
            for ind in ind_list:
                feed.register_indicator(pn, ind["name"], **ind["params"])

        # events
        events_fp = os.path.join(feeds_dir, "events.parquet")
        if os.path.isfile(events_fp):
            feed._events = pd.read_parquet(events_fp)

        return feed

    def get_period(self, period_name: str) -> Optional[PeriodData]:
        """获取指定周期的PeriodData实例（高级用法）

        :param period_name: 周期名称
        :return: PeriodData实例，未注册返回None
        """
        return self._periods.get(period_name)

    def get_data(self, period_name: str, current_time: Union[pd.Timestamp, dt], lookback_bars: int = 1,
                 timeout: Optional[float] = None) -> Optional[PeriodDataView]:
        """获取指定周期截止指定时间的逻辑视图

        指标懒加载：首次调用时自动计算注册指标，后续复用缓存。

        :param period_name: 周期名称
        :param current_time: 当前时间，视图只包含<=此时间的数据
        :param lookback_bars: 往前多少根K线，默认1根
        :param timeout: 超时时间（秒），None表示回测模式（抛错），>0表示等待，0表示非阻塞
        :return: PeriodDataView只读逻辑视图
        :raises KeyError: 如果周期未注册
        :raises ValueError: 如果current_time晚于最新数据时间或超时
        """
        if period_name not in self._periods:
            raise KeyError(f"Period {period_name} not registered")

        current_time_ts: pd.Timestamp = pd.Timestamp(current_time)  # type: ignore[assignment]

        # 懒加载计算指标
        self._calculate_indicators_for_period(period_name)

        # 获取视图
        period_data = self._periods[period_name]
        return period_data.get_data(current_time_ts, lookback_bars, self._events)


# ==================== 辅助函数 ====================

def _bars_to_df(bars: List[Bar]) -> pd.DataFrame:
    """将 Bar 列表转为 DataFrame，索引为 datetime"""
    data = {
        'open': [b.open for b in bars],
        'high': [b.high for b in bars],
        'low': [b.low for b in bars],
        'close': [b.close for b in bars],
        'volume': [b.volume for b in bars],
    }
    df = pd.DataFrame(data, index=[pd.Timestamp(b.datetime) for b in bars])
    return df


def build_context(
    data_feed: DataFeed,
    requirements: DataRequirements,
    current_time: Union[pd.Timestamp, dt],
    bar: Bar,
    timeout: Optional[float] = None
) -> BarContext:
    """构造 BarContext 上下文对象

    行为：
    1. 解析 requirements 中的 periods 配置
    2. 对每个周期调用 data_feed.get_data(period, current_time, lookback_bars, timeout)
    3. 从 DataFeed 获取当前时间范围内的事件（按 requirements.events 配置筛选）
    4. 构造并返回 BarContext 对象
    """
    multi: Dict[str, PeriodDataView] = {}

    # 获取多周期数据
    for period, req in requirements.periods.items():
        view = data_feed.get_data(period, current_time, req.lookback_bars, timeout)
        if view is not None:
            multi[period] = view

    # 获取事件（不需要事件时直接跳过，节省锁和 DataFrame 操作）
    events: List[Event] = []
    events_req = requirements.events

    if events_req.include_global_events or events_req.include_period_events:
        all_events = data_feed.get_events(end_time=current_time)

        for event in all_events:
            include = False

            # 检查全局事件
            if events_req.include_global_events and event.period is None:
                include = True

            # 检查周期特定事件
            if not include and events_req.include_period_events:
                if "*" in events_req.include_period_events or event.period in events_req.include_period_events:
                    include = True

            # 检查事件类型白名单
            if include and events_req.event_types:
                if event.type not in events_req.event_types:
                    include = False

            if include:
                events.append(event)

    # 使用传入的 bar，不再从 multi 中提取
    bar.symbol = data_feed.symbol

    return BarContext(
        symbol=data_feed.symbol,
        bar=bar,
        multi=multi,
        events=events
    )


# ==================== 默认指标注册 ====================
# 指标实现见 core/indicators.py（sma_func, ema_func, rsi_func）

# 注册默认指标
register_indicator_func(
    'sma',
    sma_func,
    IndicatorCalcMode.BATCH,
    description='简单移动平均线 (Simple Moving Average)'
)
register_indicator_func(
    'ema',
    ema_func,
    IndicatorCalcMode.BATCH,
    description='指数移动平均线 (Exponential Moving Average)'
)
register_indicator_func(
    'rsi',
    rsi_func,
    IndicatorCalcMode.BATCH,
    description='相对强弱指标 (Relative Strength Index)'
)