"""量化策略数据管理模块

【架构设计】
- DataFeed: 管理单个品种的多周期数据，对外暴露统一的高层 API
- 内部细节（基础周期、周期聚合、指标懒计算）对调用方透明
- 模块级 cache 按 symbol 缓存 DataFeed，减少回测中重复 parquet I/O

【对外 API 概览】
- 配置：apply_requirements(reqs)
- 数据装载：feed_history_df(df) / feed_bar(bar)
- 数据查询：get_data / get_period / get_period_names / get_date_range / get_source_date_range
- 指标查询：get_indicator_names / get_registered_indicators
- 序列化：to_feeds / from_feeds
- 上下文构造：build_ctx_cache（回测）/ 模块级 build_context（实盘）

【内部约定】
- 基础周期（_base_period）由 apply_requirements 从声明的周期中自动推断为最小周期
- 所有高周期 K 线由基础周期通过聚合自动生成
- 调用方无需关心聚合细节，只需声明需要哪些周期和指标
"""

import os
from datetime import datetime as dt
from typing import Any

import pandas as pd
from loguru import logger

from ..core.indicators import atr_func, ema_func, kdj_func, macd_func, rsi_func, sma_func
from ..core.types import Bar
from .aggregate import get_forming_bar_start, parse_period_minutes
from .events import Event
from .indicators import (
    REGISTERED_INDICATOR_FUNCS,
    IndicatorCalcMode,
    generate_indicator_column_name,
    register_indicator_func,
)
from .period import PeriodData, PeriodDataView
from .requirements import BarContext, DataRequirements
from .serialization import _OHLCV_COLUMNS, dump_feed, load_feed


def _parse_source_from_symbol(symbol: str) -> str | None:
    """从symbol解析source，如 "CZce.sr509" -> source="CZCE"

    :param symbol: 交易品种
    :return: source，解析失败返回None
    """
    if "." in symbol:
        return symbol.split(".")[0]
    return None


class DataFeed:
    """管理单个品种的多周期数据

    【设计目标】
    - 管理单个品种（symbol）的所有周期数据
    - 持有该品种的元数据（symbol、数据源等）
    - 提供高层 API，调用方无需关心基础周期/聚合/懒计算等内部细节
    - 提供高效的数据访问路由（通过周期名快速定位 PeriodData）
    - 统一管理 K线、指标、事件 三类数据
    - 基础周期由 apply_requirements 自动推断为声明的最小周期，高周期由它聚合生成
    """

    def __init__(self, symbol: str, source: str | None = None):
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
        self._periods: dict[str, PeriodData] = {}

        # 基础周期：由 apply_requirements 自动推断为最小周期，高周期由它聚合得到
        self._base_period: str | None = None

        # 事件数据管理
        self._events = pd.DataFrame(columns=["type", "symbol", "reason", "period", "data"])
        self._events = self._events.astype(
            {"type": "string", "symbol": "string", "reason": "string", "period": "string"}
        )

        # 指标注册配置
        self._registered_indicators: dict[str, list[tuple[str, dict[str, Any]]]] = {}

        # 聚合配置：高周期由基础周期自动聚合得到
        self._aggregation_targets: list[str] = []

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

    def load_history_data(self, period: str, bars: list[Bar], events: list[Event] | None = None) -> None:
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

    def load_history_df(self, period: str, df: pd.DataFrame, events: list[Event] | None = None) -> None:
        """从 DataFrame 直接加载历史数据（避免 Bar 转换开销）

        幂等加载：按数据范围智能处理重复调用
        - 时间范围一致 → 跳过
        - 起始时间相同，结束时间更新 → 仅追加增量行
        - 起始时间不同 → 清空该周期数据，全量加载

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

    def append_events(self, events: list[Event]) -> None:
        """批量追加事件数据

        :param events: 事件列表
        """
        if not events:
            return

        event_dicts = []
        for event in events:
            event_dicts.append(
                {
                    "datetime": pd.Timestamp(event.timestamp),
                    "type": event.type,
                    "symbol": event.symbol,
                    "reason": event.reason,
                    "period": event.period,
                    "data": event.data,
                }
            )

        new_df = pd.DataFrame(event_dicts)
        new_df = new_df.set_index("datetime")

        if len(self._events) == 0:
            self._events = new_df
        else:
            self._events = pd.concat([self._events, new_df])

        self._event_count += len(events)
        self._last_updated_at = pd.Timestamp.now()

    def get_events(
        self,
        start_time: pd.Timestamp | dt | None = None,
        end_time: pd.Timestamp | dt | None = None,
        event_type: str | None = None,
        period: str | None = None,
    ) -> list[Event]:
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
            mask &= self._events.index >= pd.Timestamp(start_time)

        if end_time is not None:
            mask &= self._events.index <= pd.Timestamp(end_time)

        if event_type is not None:
            mask &= self._events["type"] == event_type

        if period is not None:
            mask &= (self._events["period"] == period) | (self._events["period"].isna())

        events_df = self._events[mask]

        events = []
        for _, row in events_df.iterrows():
            event = Event(
                timestamp=row.name.to_pydatetime(),
                type=row["type"],
                symbol=row["symbol"],
                reason=row.get("reason", ""),
                period=row.get("period"),
                data=row.get("data"),
            )
            events.append(event)

        return events

    def setup_aggregation(self, target_periods: list[str]) -> None:
        """配置周期聚合：指定需要从基础周期聚合出的高周期（内部接口）

        外部调用方应使用 apply_requirements() 一步到位，本方法主要供
        apply_requirements / from_feeds 内部使用，以及历史测试代码兼容。

        :param target_periods: 需要聚合的高周期列表，如 ["5m", "15m", "1h"]
        :raises ValueError: 如果 _base_period 未设置
        """
        if self._base_period is None:
            raise ValueError("基础周期未设置，请先调用 apply_requirements")

        # 排除基础周期本身
        self._aggregation_targets = [p for p in target_periods if p != self._base_period]

        # 确保基础周期已注册（聚合的数据源）
        if self._aggregation_targets and self._base_period not in self._periods:
            self.register_period(self._base_period)

        # 确保所有目标周期已注册
        for period in self._aggregation_targets:
            if period not in self._periods:
                self.register_period(period)

    def apply_requirements(self, reqs: DataRequirements) -> None:
        """根据策略 DataRequirements 一次性配置 DataFeed

        【调用方视角】
        外部只需一行调用就能完成：注册基础/高周期 + 启用聚合 + 注册指标。
        基础周期自动推断为声明的最小周期，调用方无需感知。

        :param reqs: 策略数据需求
        :raises ValueError: 如果目标周期不是基础周期的整数倍
        """
        # 1. 注册所有声明的周期
        for period in reqs.periods:
            self.register_period(period)

        # 2. 自动推断基础周期（最小周期）
        period_minutes = {p: parse_period_minutes(p) for p in reqs.periods}
        self._base_period = min(period_minutes, key=period_minutes.get)  # type: ignore[arg-type]
        base_minutes = period_minutes[self._base_period]

        # 3. 校验：目标周期必须是基础周期的整数倍
        for period, minutes in period_minutes.items():
            if period != self._base_period and minutes % base_minutes != 0:
                raise ValueError(
                    f"周期 {period}（{minutes}分钟）不是基础周期 {self._base_period}（{base_minutes}分钟）的整数倍，无法聚合"
                )

        # 4. 启用聚合：高周期自动由基础周期聚合得到
        self.setup_aggregation(list(reqs.periods.keys()))

        # 5. 注册指标
        for period, ind_list in reqs.indicators.items():
            for ind in ind_list:
                self.register_indicator(period, ind.name, **ind.params)

    def feed_history_df(self, df: pd.DataFrame, events: list[Event] | None = None) -> None:
        """灌入基础周期历史 K 线（高层 API）

        高周期由 DataFeed 内部聚合生成，调用方无需关心基础周期是哪个。

        :param df: 基础周期 K线 DataFrame，索引为 datetime
        :param events: 历史事件列表（可选）
        """
        assert self._base_period is not None, "请先调用 apply_requirements"
        self.load_history_df(self._base_period, df, events)

    def feed_bar(self, bar: Bar, events: list[Event] | None = None) -> None:
        """喂入一根基础周期实时 K 线（高层 API）

        高周期会自动通过聚合更新，调用方无需关心基础周期是哪个。

        :param bar: 基础周期 K 线
        :param events: 该 K 线时间范围内的事件（可选）
        """
        assert self._base_period is not None, "请先调用 apply_requirements"
        self.update_bar(bar, self._base_period, events)

    def has_source_data(self) -> bool:
        """是否已加载基础周期数据"""
        if self._base_period is None:
            return False
        pd_obj = self._periods.get(self._base_period)
        return pd_obj is not None and pd_obj.length > 0

    def get_source_date_range(self) -> tuple[str, str] | None:
        """获取基础周期的数据日期范围（用于新鲜度判定等）"""
        if self._base_period is None:
            return None
        return self.get_date_range(self._base_period)

    def update_bar(self, bar: Bar, period: str, events: list[Event] | None = None) -> None:
        """更新一根K线

        当 period == _base_period 且已配置聚合时，自动级联更新所有高周期。

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

        # 聚合：基础周期 bar 到达时自动更新高周期
        if period == self._base_period and self._aggregation_targets:
            self._step_aggregation(bar)

    def _step_aggregation(self, source_bar: Bar) -> None:
        """基础周期 bar 到达时，把该 bar 推进到所有高周期（内部方法）

        对每个高周期：
        1. 判断 source_bar 属于哪个高周期 bar（通过起始时间）
        2. 如果属于当前"形成中"的 bar → update_forming_bar
        3. 如果属于新的高周期 bar → complete_forming_bar + set_forming_bar
        4. 重算该高周期的指标（因为形成中 bar 更新了）

        :param source_bar: 新到达的基础周期 bar
        """
        ts = pd.Timestamp(source_bar.datetime)
        for target_period in self._aggregation_targets:
            period_data = self._periods.get(target_period)
            if period_data is None:
                continue

            bar_start = get_forming_bar_start(ts, target_period)

            if period_data._forming_bar is None:
                # 首次：设置形成中 bar
                period_data.set_forming_bar(_make_aggregated_bar(source_bar, bar_start))
            else:
                forming_time = pd.Timestamp(period_data._forming_bar.datetime)  # pyright: ignore[reportPrivateUsage]
                if bar_start == forming_time:
                    # 仍在同一个高周期 bar 内 → 更新形成中 bar
                    period_data.update_forming_bar(source_bar)
                elif bar_start > forming_time:
                    # 新高周期 bar 开始 → 完成旧的，开始新的
                    period_data.complete_forming_bar()
                    period_data.set_forming_bar(_make_aggregated_bar(source_bar, bar_start))

            # 形成中 bar 更新后，需要重算该周期指标
            period_data.clear_indicator_calculation()
            self._calculate_indicators_for_period(target_period)

    def _calculate_indicators_for_period(self, period_name: str, incremental: bool = False) -> None:
        """计算指定周期的所有注册指标

        incremental=True 时跳过已算到最新行的指标（按 last_calc_idx 判断），
        对确实需要计算的指标仍做全量计算（非切片增量）。

        对于有 forming bar 的周期，额外计算 forming bar 的指标值并缓存。

        :param period_name: 周期名称
        :param incremental: True 时跳过已到最新的指标
        """
        if period_name not in self._periods:
            return

        period_data = self._periods[period_name]

        if period_name not in self._registered_indicators:
            return

        has_forming = period_data._forming_bar is not None  # pyright: ignore[reportPrivateUsage]

        # 如果有 forming bar，需要临时追加到 _df 来计算指标
        if has_forming and period_data._forming_bar is not None:  # pyright: ignore[reportPrivateUsage]
            forming_bar = period_data._forming_bar  # pyright: ignore[reportPrivateUsage]
            forming_time = pd.Timestamp(forming_bar.datetime)
            forming_row = pd.Series(
                {
                    "open": forming_bar.open,
                    "high": forming_bar.high,
                    "low": forming_bar.low,
                    "close": forming_bar.close,
                    "volume": forming_bar.volume,
                },
                name=forming_time,
            )
            period_data._df.loc[forming_time] = forming_row  # pyright: ignore[reportPrivateUsage]

        try:
            for indicator_name, params in self._registered_indicators[period_name]:
                col_name = generate_indicator_column_name(indicator_name, params)
                df_len = len(period_data._df)  # pyright: ignore[reportPrivateUsage]

                # 增量检查：如果已经算过且没有新行，跳过
                if period_data.is_indicator_calculated(col_name):
                    last_calc_idx = period_data.get_indicator_last_calc_idx(col_name)
                    if last_calc_idx is not None and last_calc_idx >= df_len - 1:
                        # 没有新行追加，指标值仍然最新，跳过重算
                        continue

                # 获取指标函数信息
                func_info = REGISTERED_INDICATOR_FUNCS.get(indicator_name)
                if func_info is None:
                    continue

                # 计算指标（全量计算，传入完整 DataFrame）
                try:
                    series = period_data.apply_indicator(func_info.func, **params)
                    period_data.set_indicator_column(col_name, series)
                    period_data.mark_indicator_calculated(col_name)
                except Exception as e:
                    logger.warning("指标计算失败 [{}][{}]: {}", period_name, indicator_name, e)

            # 如果有 forming bar，提取最后一行的指标值到缓存，然后从 _df 中移除
            if has_forming and period_data._forming_bar is not None:  # pyright: ignore[reportPrivateUsage]
                forming_bar = period_data._forming_bar  # pyright: ignore[reportPrivateUsage]
                forming_time = pd.Timestamp(forming_bar.datetime)
                # 提取 forming bar 行的指标值
                for indicator_name, params in self._registered_indicators[period_name]:
                    col_name = generate_indicator_column_name(indicator_name, params)
                    if col_name in period_data._df.columns:  # pyright: ignore[reportPrivateUsage]
                        val = period_data._df.loc[forming_time, col_name]  # pyright: ignore[reportPrivateUsage]
                        period_data._forming_indicators[col_name] = float(val)  # pyright: ignore[reportPrivateUsage]
                # 从 _df 中移除 forming bar 行
                period_data._df.drop(forming_time, inplace=True)  # pyright: ignore[reportPrivateUsage]
                # 标记指标只算到 _df 末尾（不含 forming bar）
                for indicator_name, params in self._registered_indicators[period_name]:
                    col_name = generate_indicator_column_name(indicator_name, params)
                    period_data.mark_indicator_calculated(col_name, len(period_data._df) - 1)  # pyright: ignore[reportPrivateUsage]

        except Exception:
            # 异常时确保 forming bar 被移除
            if has_forming and period_data._forming_bar is not None:  # pyright: ignore[reportPrivateUsage]
                forming_time = pd.Timestamp(period_data._forming_bar.datetime)  # pyright: ignore[reportPrivateUsage]
                if forming_time in period_data._df.index:  # pyright: ignore[reportPrivateUsage]
                    period_data._df.drop(forming_time, inplace=True)  # pyright: ignore[reportPrivateUsage]
            raise

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

    def calculate_period(self, period_name: str, incremental: bool = True) -> None:
        """只计算指定周期的所有注册指标

        Args:
            period_name: 周期名称
            incremental: True（默认）时跳过已算到最新的指标，
                         相当于增量计算；False 时强制全量重算。
        """
        self._calculate_indicators_for_period(period_name, incremental=incremental)

    # --- 序列化 ────────────────────────────────────────

    def to_feeds(self, feeds_dir: str) -> None:
        """将 DataFeed 完整状态序列化到目录

        文件布局：{feeds_dir}/_meta.json + {period}.parquet x N + events.parquet
        未来可扩展到其它存储介质，接口不变。

        如果 pyarrow 不可用，静默跳过写入。

        :param feeds_dir: 目标目录路径（自动创建父目录）
        """
        dump_feed(self, feeds_dir)

    @classmethod
    def from_feeds(cls, feeds_dir: str) -> "DataFeed":
        """从目录反序列化恢复 DataFeed 完整实例

        恢复后指标已在 DataFrame 中，不需要重新计算，可直接使用。

        :param feeds_dir: 源目录路径
        :return: 恢复的 DataFeed 实例
        :raises FileNotFoundError: 目录或 _meta.json 不存在
        :raises ImportError: pyarrow 不可用
        """
        return load_feed(feeds_dir)

    def get_period(self, period_name: str) -> PeriodData | None:
        """获取指定周期的PeriodData实例（高级用法）

        :param period_name: 周期名称
        :return: PeriodData实例，未注册返回None
        """
        return self._periods.get(period_name)

    def get_period_names(self) -> list[str]:
        """获取所有已注册的周期名称列表

        :return: 周期名称列表
        """
        return list(self._periods.keys())

    def get_indicator_names(self, period_name: str) -> list[str]:
        """获取指定周期中已计算的指标列名（排除 OHLCV 列）

        :param period_name: 周期名称
        :return: 指标列名列表，周期不存在返回空列表
        """
        period_data = self._periods.get(period_name)
        if period_data is None:
            return []
        return [c for c in period_data._df.columns if c not in _OHLCV_COLUMNS]  # pyright: ignore[reportPrivateUsage]

    def get_registered_indicators(self, period_name: str) -> list[tuple[str, dict[str, Any]]]:
        """获取指定周期已注册的指标配置列表

        :param period_name: 周期名称
        :return: [(indicator_name, params)] 列表，周期不存在返回空列表
        """
        return list(self._registered_indicators.get(period_name, []))

    def get_date_range(self, period_name: str) -> tuple[str, str] | None:
        """获取指定周期的数据日期范围

        :param period_name: 周期名称
        :return: (min_dt, max_dt) 日期字符串，周期不存在或无数据返回 None
        """
        period_data = self._periods.get(period_name)
        if period_data is None or period_data.length == 0:
            return None
        idx = period_data._df.index  # pyright: ignore[reportPrivateUsage]
        return str(idx[0].date()), str(idx[-1].date())

    def build_ctx_cache(self, requirements: DataRequirements, symbol: str) -> dict[pd.Timestamp, BarContext]:
        """回测专用：逐基础周期推进预构造所有 BarContext

        启用聚合时按基础周期逐根推进，每步：
        1. 触发聚合更新高周期形成中 bar → 重算高周期指标
        2. 构造当前时间点的 BarContext（含所有周期视图）

        未启用聚合时按主周期逐行构造（兼容历史路径）。

        前置条件：基础周期历史数据已通过 feed_history_df 加载。

        :param requirements: 策略数据需求
        :param symbol: 品种标识
        :return: {timestamp: BarContext} 字典
        """
        # ── 启用聚合：逐基础周期推进 ──
        if self._aggregation_targets and self._base_period is not None and self._base_period in self._periods:
            return self._build_ctx_cache_aggregated(requirements, symbol)

        # ── 未启用聚合：按主周期逐行构造（兼容历史路径） ──
        main_period = next(iter(requirements.periods))
        main_pd = self._periods.get(main_period)
        if main_pd is None or main_pd.length == 0:
            return {}

        cache: dict[pd.Timestamp, BarContext] = {}
        main_df = main_pd._df  # pyright: ignore[reportPrivateUsage]

        for idx in range(len(main_df)):
            ts: pd.Timestamp = main_df.index[idx]  # type: ignore[assignment]
            bar = _row_to_bar(symbol, ts, main_df.iloc[idx])
            multi: dict[str, PeriodDataView] = {}
            for period, req in requirements.periods.items():
                view = self.get_data(period, ts, req.lookback_bars)
                if view is not None:
                    multi[period] = view
            cache[ts] = BarContext(symbol=symbol, bar=bar, multi=multi, events=[])

        return cache

    def _build_ctx_cache_aggregated(
        self, requirements: DataRequirements, symbol: str
    ) -> dict[pd.Timestamp, BarContext]:
        """聚合模式下逐基础周期推进构造 BarContext（内部方法）

        从已加载的基础周期数据出发，复用 _step_aggregation 把每根 bar
        推进到所有高周期，并构造对应时间点的 BarContext。

        :param requirements: 策略数据需求
        :param symbol: 品种标识
        :return: {timestamp: BarContext} 字典
        """
        source_pd = self._periods.get(self._base_period) if self._base_period else None
        if source_pd is None or source_pd.length == 0:
            return {}

        df_source = source_pd._df  # pyright: ignore[reportPrivateUsage]

        # 清空高周期数据，重新聚合
        for target_period in self._aggregation_targets:
            period_data = self._periods.get(target_period)
            if period_data is not None:
                period_data.load_df(pd.DataFrame(columns=["open", "high", "low", "close", "volume"]), replace=True)
                period_data._forming_bar = None  # pyright: ignore[reportPrivateUsage]
                period_data._forming_indicators.clear()  # pyright: ignore[reportPrivateUsage]
                period_data.clear_indicator_calculation()

        cache: dict[pd.Timestamp, BarContext] = {}

        for idx in range(len(df_source)):
            ts: pd.Timestamp = df_source.index[idx]  # type: ignore[assignment]
            bar = _row_to_bar(symbol, ts, df_source.iloc[idx])

            # 推进高周期（与实时 update_bar 走同一条路径）
            self._step_aggregation(bar)

            multi: dict[str, PeriodDataView] = {}
            for period, req in requirements.periods.items():
                view = self.get_data(period, ts, req.lookback_bars)
                if view is not None:
                    multi[period] = view

            cache[ts] = BarContext(symbol=symbol, bar=bar, multi=multi, events=[])

        return cache

    def get_data(
        self, period_name: str, current_time: pd.Timestamp | dt, lookback_bars: int = 1, timeout: float | None = None
    ) -> PeriodDataView | None:
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


def _bars_to_df(bars: list[Bar]) -> pd.DataFrame:
    """将 Bar 列表转为 DataFrame，索引为 datetime"""
    data = {
        "open": [b.open for b in bars],
        "high": [b.high for b in bars],
        "low": [b.low for b in bars],
        "close": [b.close for b in bars],
        "volume": [b.volume for b in bars],
    }
    df = pd.DataFrame(data, index=[pd.Timestamp(b.datetime) for b in bars])
    return df


def _row_to_bar(symbol: str, ts: pd.Timestamp, row: pd.Series) -> Bar:
    """从 DataFrame 一行 OHLCV 构造标准 Bar"""
    return Bar(
        symbol=symbol,
        datetime=ts.to_pydatetime(),
        open=float(row["open"]),
        high=float(row["high"]),
        low=float(row["low"]),
        close=float(row["close"]),
        volume=float(row["volume"]),
    )


def _make_aggregated_bar(source_bar: Bar, bar_start: pd.Timestamp) -> Bar:
    """以基础周期 bar 作为高周期 bar 的初值，时间戳对齐到高周期起始"""
    return Bar(
        symbol=source_bar.symbol,
        datetime=bar_start.to_pydatetime(),
        open=source_bar.open,
        high=source_bar.high,
        low=source_bar.low,
        close=source_bar.close,
        volume=source_bar.volume,
    )


def build_context(
    data_feed: DataFeed,
    requirements: DataRequirements,
    current_time: pd.Timestamp | dt,
    bar: Bar,
    timeout: float | None = None,
) -> BarContext:
    """构造 BarContext 上下文对象

    行为：
    1. 解析 requirements 中的 periods 配置
    2. 对每个周期调用 data_feed.get_data(period, current_time, lookback_bars, timeout)
    3. 从 DataFeed 获取当前时间范围内的事件（按 requirements.events 配置筛选）
    4. 构造并返回 BarContext 对象
    """
    multi: dict[str, PeriodDataView] = {}

    # 获取多周期数据
    for period, req in requirements.periods.items():
        view = data_feed.get_data(period, current_time, req.lookback_bars, timeout)
        if view is not None:
            multi[period] = view

    # 获取事件（不需要事件时直接跳过，节省锁和 DataFrame 操作）
    events: list[Event] = []
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

    return BarContext(symbol=data_feed.symbol, bar=bar, multi=multi, events=events)


# ==================== 默认指标注册 ====================
# 指标实现见 core/indicators.py（sma_func, ema_func, rsi_func）

# 注册默认指标
register_indicator_func("sma", sma_func, IndicatorCalcMode.BATCH, description="简单移动平均线 (Simple Moving Average)")
register_indicator_func(
    "ema", ema_func, IndicatorCalcMode.BATCH, description="指数移动平均线 (Exponential Moving Average)"
)
register_indicator_func("rsi", rsi_func, IndicatorCalcMode.BATCH, description="相对强弱指标 (Relative Strength Index)")
register_indicator_func(
    "macd", macd_func, IndicatorCalcMode.BATCH, description="MACD快慢线差值 (Moving Average Convergence Divergence)"
)
register_indicator_func("kdj", kdj_func, IndicatorCalcMode.BATCH, description="KDJ随机指标J值")
register_indicator_func("atr", atr_func, IndicatorCalcMode.BATCH, description="平均真实波幅 (Average True Range)")


# ==================== 便捷工厂方法 ====================


def create_data_feed(
    symbol: str,
    requirements: DataRequirements,
    feeds_dir: str,
    source_df: pd.DataFrame | None = None,
) -> DataFeed:
    """便捷工厂方法：完整构造一个 DataFeed，自动处理缓存、增量加载、序列化

    【流程逻辑】
    1. 先查内存缓存，命中直接返回（零 I/O）
    2. 内存未命中，尝试从磁盘 feeds 目录反序列化加载
    3. 检查源数据日期范围是否匹配，不匹配则全量重加载
    4. 如果磁盘加载成功，合并缺失的周期/指标需求，增量计算
    5. 最后写入内存缓存并返回

    :param symbol: 交易品种
    :param requirements: 数据需求
    :param feeds_dir: 序列化缓存目录
    :param source_df: 源周期（1m）数据，如果为 None 则需要调用方后续灌入
    :return: 构造完成的 DataFeed
    """
    from .cache import get_cached_feed, set_cached_feed

    # 0. 查内存缓存（零 I/O 路径）
    if source_df is not None and len(source_df) > 0:
        min_dt = str(source_df.index[0].date())
        max_dt = str(source_df.index[-1].date())
        cached = get_cached_feed(symbol, min_dt, max_dt)
        if cached is not None:
            return cached

    # 1. 尝试从磁盘加载，判断是否需要全量重算
    feed: DataFeed
    data_stale = True

    if os.path.isdir(feeds_dir):
        try:
            feed = DataFeed.from_feeds(feeds_dir)
            # 检查源数据是否存在且日期匹配
            if feed.has_source_data():
                feed_date_range = feed.get_source_date_range()
                if feed_date_range is not None and source_df is not None:
                    src_min_dt = str(source_df.index[0].date())
                    src_max_dt = str(source_df.index[-1].date())
                    if feed_date_range[0] == src_min_dt and feed_date_range[1] == src_max_dt:
                        data_stale = False

        except Exception:
            # 加载失败，全量重算
            pass

    if data_stale:
        # 全量加载
        feed = DataFeed(symbol=symbol)
        feed.apply_requirements(requirements)
        if source_df is not None and len(source_df) > 0:
            feed.feed_history_df(source_df.set_index("datetime"))
        feed.calculate_all()
        feed.to_feeds(feeds_dir)
    else:
        # 增量合并缺失的周期/指标
        feed.apply_requirements(requirements)
        changed = False
        existing_periods = set(feed.get_period_names())
        existing_indicators = {
            (pn, n, tuple(sorted(p.items())))
            for pn in requirements.indicators
            for n, p in feed.get_registered_indicators(pn)
        }
        feed.apply_requirements(requirements)
        new_periods = set(feed.get_period_names()) - existing_periods
        new_indicators = {
            (pn, n, tuple(sorted(p.items())))
            for pn in requirements.indicators
            for n, p in feed.get_registered_indicators(pn)
        } - existing_indicators
        if new_periods or new_indicators:
            changed = True
        if changed:
            feed.calculate_all()
            feed.to_feeds(feeds_dir)

    # 写入内存缓存
    if source_df is not None and len(source_df) > 0:
        min_dt = str(source_df.index[0].date())
        max_dt = str(source_df.index[-1].date())
        set_cached_feed(symbol, feed, min_dt, max_dt)

    return feed
