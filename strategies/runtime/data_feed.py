"""量化策略数据管理模块

DataFeed 管理单个品种的多周期数据，统一对外 API。

核心原则：
- 基础周期数据通过 feed_history_df / feed_bar 加载
- 指标计算推迟到 build_context → get_data 时按需惰性计算
- 高周期在 build_context 时从基础周期数据现场聚合
"""

import os
from datetime import datetime as dt
from typing import Any

import pandas as pd
from loguru import logger

from common.symbol_utils import parse_contract

from ..core.indicators import IndicatorSpec
from ..core.types import Bar
from .aggregate import bar_start_time, parse_period_minutes
from .events import Event, EventManager
from .period import PeriodData, PeriodDataView
from .requirements import BarContext, DataRequirements
from .serialization import dump_feed, load_feed


class DataFeed:
    """管理单个品种的多周期数据"""

    def __init__(
        self,
        symbol: str,
        source: str | None = None,
        requirements: DataRequirements | None = None,
    ):
        self.symbol = symbol
        if source is None:
            ci = parse_contract(symbol)
            self.source = ci.exchange if ci else None
        else:
            self.source = source

        self._periods: dict[str, PeriodData] = {}
        self._base_period: str | None = None
        self._event_mgr = EventManager()

        # 高周期聚合缓存 — 避免每根K线都重新聚合所有数据
        # key=period_name, value={"completed": list[Bar], "buffer": list[pd.Series], "last_base_idx": int}
        self._agg_cache: dict[str, dict[str, Any]] = {}

        # 磁盘缓存目录（由 create() 设置）
        self._feeds_dir: str | None = None
        self.loaded_from_cache: bool = False

        if requirements is not None:
            self.apply_requirements(requirements)

    @property
    def base_period(self) -> str | None:
        return self._base_period

    @base_period.setter
    def base_period(self, value: str | None) -> None:
        self._base_period = value

    @property
    def events_df(self) -> pd.DataFrame:
        return self._event_mgr.df

    @events_df.setter
    def events_df(self, value: pd.DataFrame) -> None:
        self._event_mgr.df = value

    def register_period(self, period: str) -> PeriodData:
        if period not in self._periods:
            self._periods[period] = PeriodData(period)
        return self._periods[period]

    def register_indicator(self, period_name: str, indicator: IndicatorSpec) -> None:
        if period_name not in self._periods:
            raise KeyError(f"Period {period_name} not registered")
        self._periods[period_name].register_indicator(indicator)

    def load_history_df(self, period: str, df: pd.DataFrame, events: list[Event] | None = None) -> None:
        """从 DataFrame 直接加载历史数据

        幂等加载。不会自动计算指标，指标在 build_context 时惰性计算。
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
            assert existing_start is not None and existing_end is not None

            if new_start == existing_start and new_end <= existing_end:
                return
            elif new_start == existing_start and new_end > existing_end:
                append_df = df.loc[df.index > existing_end]
                if len(append_df) > 0:
                    period_data.load_df(append_df, replace=False)
            else:
                if new_start > existing_start:
                    logger.warning(
                        "[{}] load_history_df 数据范围变窄: 已有[{}, {}]，新数据[{}, {}]——早期数据将丢失",
                        period,
                        existing_start,
                        existing_end,
                        new_start,
                        new_end,
                    )
                period_data.load_df(df, replace=True)
        else:
            period_data.load_df(df, replace=False)

        if events:
            self.append_events(events)

    def append_events(self, events: list[Event]) -> None:
        self._event_mgr.append(events)

    def get_events(
        self,
        start_time: pd.Timestamp | dt | None = None,
        end_time: pd.Timestamp | dt | None = None,
        event_type: str | None = None,
        period: str | None = None,
    ) -> list[Event]:
        return self._event_mgr.query(start_time, end_time, event_type, period)

    def apply_requirements(self, reqs: DataRequirements) -> None:
        """注册周期、校验整数倍关系、注册指标

        高周期在 build_context 时从基础周期数据现场聚合，不在初始化时预构建。
        """
        all_periods = set(reqs.periods)
        for period in reqs.indicators:
            all_periods.add(period)

        for period in all_periods:
            self.register_period(period)

        period_minutes = {p: parse_period_minutes(p) for p in all_periods}
        base_period = min(period_minutes, key=lambda p: period_minutes[p])
        self._base_period = base_period
        base_minutes = period_minutes[base_period]

        for period, minutes in period_minutes.items():
            if period != self._base_period and minutes % base_minutes != 0:
                raise ValueError(
                    f"周期 {period}（{minutes}分钟）不是基础周期 {self._base_period}（{base_minutes}分钟）的整数倍，无法聚合"
                )

        for period, ind_list in reqs.indicators.items():
            for ind in ind_list:
                self.register_indicator(period, ind)

    def feed_history_df(self, df: pd.DataFrame, events: list[Event] | None = None) -> None:
        """灌入基础周期历史 K 线"""
        assert self._base_period is not None, "请先调用 apply_requirements"
        self.load_history_df(self._base_period, df, events)

    def feed_bar(self, bar: Bar, events: list[Event] | None = None) -> None:
        """喂入一根基础周期 K 线

        只追加数据，不触发任何计算。指标在 build_context 时惰性计算。
        """
        assert self._base_period is not None, "请先调用 apply_requirements"
        self._periods[self._base_period].append_bar(bar)
        if events:
            self.append_events(events)

    def has_source_data(self) -> bool:
        if self._base_period is None:
            return False
        pd_obj = self._periods.get(self._base_period)
        return pd_obj is not None and pd_obj.length > 0

    def get_source_date_range(self) -> tuple[str, str] | None:
        if self._base_period is None:
            return None
        return self.get_date_range(self._base_period)

    # --- 序列化 ────────────────────────────────────────

    def save_cache(self) -> None:
        """回测结束后保存缓存，只有本次是从 native 数据构造的才写盘"""
        if self.loaded_from_cache or self._feeds_dir is None:
            return
        dump_feed(self, self._feeds_dir)

    @classmethod
    def from_feeds(cls, feeds_dir: str) -> "DataFeed":
        return load_feed(feeds_dir)

    # --- 查询 ──────────────────────────────────────────

    def get_period(self, period_name: str) -> PeriodData | None:
        return self._periods.get(period_name)

    def get_period_names(self) -> list[str]:
        return list(self._periods.keys())

    def get_indicator_names(self, period_name: str) -> list[str]:
        period_data = self._periods.get(period_name)
        if period_data is None:
            return []
        return period_data.indicator_names

    def get_registered_indicators(self, period_name: str) -> list[IndicatorSpec]:
        period_data = self._periods.get(period_name)
        if period_data is None:
            return []
        return period_data.registered_indicators

    def get_date_range(self, period_name: str) -> tuple[str, str] | None:
        period_data = self._periods.get(period_name)
        if period_data is None or period_data.length == 0:
            return None
        first = period_data.first_time
        last = period_data.latest_time
        assert first is not None and last is not None
        return str(first.date()), str(last.date())

    def _aggregate_period_view(
        self,
        target_period: str,
        current_time: pd.Timestamp,
        lookback_bars: int,
        base_df: pd.DataFrame,
    ) -> PeriodDataView | None:
        """从基础周期数据聚合出高周期视图（带增量缓存）

        首次调用时全量聚合所有基础K线，后续只处理新增K线。
        避免每根1m K线都重新遍历所有历史数据导致的 O(N²) 性能问题。
        """
        target_minutes = parse_period_minutes(target_period)
        base_minutes = parse_period_minutes(self._base_period)  # type: ignore[arg-type]

        base_slice = base_df[base_df.index <= current_time]
        if len(base_slice) == 0:
            return None

        bars_per_high = target_minutes // base_minutes

        # ── 增量聚合缓存 ─────────────────────────────────
        cache = self._agg_cache.get(target_period)
        if cache is None:
            # 首次调用：全量聚合
            new_completed: list[Bar] = []
            new_buffer: list[pd.Series] = []
            last_base_idx = -1
            for _idx, row in base_slice.iterrows():
                new_buffer.append(row)
                if len(new_buffer) == bars_per_high:
                    agg_df = pd.DataFrame(new_buffer)
                    first_idx_name = new_buffer[0].name
                    start_time = bar_start_time(pd.Timestamp(first_idx_name), target_minutes)  # type: ignore[arg-type]
                    new_completed.append(
                        Bar(
                            symbol=self.symbol,
                            datetime=start_time.to_pydatetime(),
                            open=float(agg_df["open"].iloc[0]),
                            high=float(agg_df["high"].max()),
                            low=float(agg_df["low"].min()),
                            close=float(agg_df["close"].iloc[-1]),
                            volume=float(agg_df["volume"].sum()),
                        )
                    )
                    new_buffer = []
                last_base_idx += 1
            cache = {"completed": new_completed, "buffer": new_buffer, "last_base_idx": last_base_idx}
            self._agg_cache[target_period] = cache
        else:
            # 后续调用：只处理新增的 K线
            last_base_idx = int(cache.get("last_base_idx", -1))
            new_count = len(base_slice) - 1 - last_base_idx
            if new_count > 0:
                completed = cache["completed"]  # type: ignore[assignment]
                buffer = cache["buffer"]  # type: ignore[assignment]
                for i in range(new_count):
                    idx = last_base_idx + 1 + i
                    row = base_slice.iloc[idx]
                    buffer.append(row)
                    if len(buffer) == bars_per_high:
                        agg_df = pd.DataFrame(buffer)
                        first_idx_name = buffer[0].name
                        start_time = bar_start_time(pd.Timestamp(first_idx_name), target_minutes)  # type: ignore[arg-type]
                        completed.append(
                            Bar(
                                symbol=self.symbol,
                                datetime=start_time.to_pydatetime(),
                                open=float(agg_df["open"].iloc[0]),
                                high=float(agg_df["high"].max()),
                                low=float(agg_df["low"].min()),
                                close=float(agg_df["close"].iloc[-1]),
                                volume=float(agg_df["volume"].sum()),
                            )
                        )
                        buffer = []
                cache["last_base_idx"] = len(base_slice) - 1  # type: ignore[assignment]

        # 构造 forming bar（buffer 中不足一组的剩余部分）
        buf = cache["buffer"]
        if buf:
            agg_df = pd.DataFrame(buf)  # type: ignore[arg-type]
            bar_start = bar_start_time(agg_df.index[-1], target_minutes)
            forming_bar = Bar(
                symbol=self.symbol,
                datetime=bar_start.to_pydatetime(),
                open=float(agg_df["open"].iloc[0]),
                high=float(agg_df["high"].max()),
                low=float(agg_df["low"].min()),
                close=float(agg_df["close"].iloc[-1]),
                volume=float(agg_df["volume"].sum()),
            )
        else:
            forming_bar = None

        # 构造视图
        comp = cache["completed"]

        # 去重（跨日期场景可能有相同起始时间的 bar）
        seen_times: set[str] = set()
        unique_bars: list[Bar] = []
        for bar in comp:  # type: ignore[arg-type]
            key = str(bar.datetime)
            if key not in seen_times:
                seen_times.add(key)
                unique_bars.append(bar)

        if not unique_bars and forming_bar is None:
            return None

        agg_temp_pd = PeriodData(target_period)
        for bar in unique_bars:
            agg_temp_pd.append_bar(bar)

        # flush buffer 确保 data 属性返回完整数据
        agg_temp_pd._ensure_flushed()  # type: ignore[attr-defined]

        total = len(unique_bars)
        start_idx = max(0, total - lookback_bars)
        end_idx = total - 1

        return PeriodDataView(
            df_ref=agg_temp_pd.data,
            events_ref=self._event_mgr.df,
            start_idx=start_idx,
            end_idx=end_idx,
            current_time=current_time,
            period=target_period,
            forming_bar=forming_bar,
            forming_indicators={},
            base_df_ref=base_df,
        )

    def _pre_calculate_cache(self) -> None:
        """预计算所有已注册指标并将结果写入基础周期的 DataFrame（缓存用）

        在 create() 中持久化到磁盘前调用，确保 parquet 缓存包含指标列。
        所有周期的指标统一写入基础周期的 _df（与 calculate_indicators 策略一致）。
        """
        if self._base_period is None:
            return
        base_pd = self._periods.get(self._base_period)
        if base_pd is None or base_pd.length == 0:
            return
        latest = base_pd.latest_time
        if latest is None:
            return
        total = base_pd.length
        for pn in self.get_period_names():
            indicators = self.get_registered_indicators(pn)
            if not indicators:
                continue
            view = self.get_data(pn, latest, total)
            if view is not None:
                view.calculate_indicators(indicators)

    def get_data(
        self, period_name: str, current_time: pd.Timestamp | dt, lookback_bars: int = 1, timeout: float | None = None
    ) -> PeriodDataView | None:
        """获取指定周期截止指定时间的逻辑视图

        基础周期直接切片，高周期从基础周期数据现场聚合。
        指标在视图范围内惰性计算。
        """
        if period_name not in self._periods:
            raise KeyError(f"Period {period_name} not registered")

        current_time_ts = pd.Timestamp(current_time)
        period_data = self._periods[period_name]
        base_df = self._periods[self._base_period].data if self._base_period else None  # type: ignore[arg-type]

        if period_name == self._base_period or self._base_period is None:
            # 基础周期：直接切片
            view: PeriodDataView | None = period_data.get_data(
                current_time_ts, lookback_bars, self._event_mgr.df, base_df_ref=base_df
            )
        elif period_data.length > 0:
            # 高周期有 native 数据：优先使用
            native_latest = period_data.latest_time
            if native_latest is not None and current_time_ts > native_latest:
                # native 数据不够新 → 回退到聚合（含 forming bar）
                base_data = self._periods.get(self._base_period)
                if base_data is None or base_data.length == 0:
                    return None
                view = self._aggregate_period_view(period_name, current_time_ts, lookback_bars, base_data.data)
            else:
                view = period_data.get_data(current_time_ts, lookback_bars, self._event_mgr.df, base_df_ref=base_df)
        else:
            # 高周期无 native 数据：回退到从基础周期现场聚合
            base_data = self._periods.get(self._base_period)
            if base_data is None or base_data.length == 0:
                return None
            view = self._aggregate_period_view(period_name, current_time_ts, lookback_bars, base_data.data)

        # 在视图上惰性计算指标
        period_data = self._periods[period_name]
        if view is not None:
            view.calculate_indicators(period_data.registered_indicators)
        return view

    def build_context(
        self,
        requirements: DataRequirements,
        bar: Bar,
        timeout: float | None = None,
    ) -> BarContext:
        """构造 BarContext 上下文对象

        build_context 是唯一计算入口，在这里调动已有的计算能力。
        """
        current_time = pd.Timestamp(bar.datetime)
        multi: dict[str, PeriodDataView] = {}

        for period, req in requirements.periods.items():
            view = self.get_data(period, current_time, req.lookback_bars, timeout)
            if view is not None:
                multi[period] = view

        events: list[Event] = []
        events_req = requirements.events

        if events_req.include_global_events or events_req.include_period_events:
            max_lookback = max(req.lookback_bars for req in requirements.periods.values())
            start_time: pd.Timestamp | None = None
            try:
                if self._base_period:
                    period_min = parse_period_minutes(self._base_period)
                    start_time = current_time - pd.Timedelta(minutes=period_min * max_lookback)
            except Exception:
                pass

            all_events = self.get_events(start_time=start_time, end_time=current_time)

            for event in all_events:
                include = False
                if events_req.include_global_events and event.period is None:
                    include = True
                if not include and events_req.include_period_events:
                    if "*" in events_req.include_period_events or event.period in events_req.include_period_events:
                        include = True
                if include and events_req.event_types:
                    if event.type not in events_req.event_types:
                        include = False
                if include:
                    events.append(event)

        if bar.symbol != self.symbol:
            logger.warning(
                "[{}] build_context 收到 symbol={} 的 bar，已忽略",
                self.symbol,
                bar.symbol,
            )

        return BarContext(symbol=self.symbol, bar=bar, multi=multi, events=events)

    @classmethod
    def create(
        cls,
        symbol: str,
        requirements: DataRequirements,
    ) -> "DataFeed":
        """完整构造一个 DataFeed，自动处理缓存、增量加载、序列化

        :param symbol: 品种代码
        :param requirements: 数据需求
        """
        from data.manager import DataManager
        from data.output_paths import output_root

        from .cache import get_cached_feed, get_cached_feed_by_symbol, set_cached_feed

        all_periods = set(requirements.periods)
        for period in requirements.indicators:
            all_periods.add(period)
        if not all_periods:
            raise ValueError(f"requirements 未声明任何周期，无法推断基础周期: symbol={symbol}")
        source_period = min(all_periods, key=parse_period_minutes)

        # 1. 获取所有要求周期的 native K线数据
        dm = DataManager()
        all_loaded: dict[str, pd.DataFrame] = {}
        for period_name in sorted(all_periods, key=parse_period_minutes):
            try:
                results = dm.load_kline([symbol], interval=period_name)
            except FileNotFoundError:
                continue
            if results:
                _, df, _ = results[0]
                if "datetime" in df.columns:
                    df = df.set_index("datetime")
                all_loaded[period_name] = df

        base_df = all_loaded.get(source_period)
        if base_df is None:
            # 所有周期都没加载到数据，尝试内存缓存
            cached = get_cached_feed_by_symbol(symbol)
            if cached is not None:
                return cached
            raise FileNotFoundError(f"无法加载品种 {symbol} 的任何 K线数据")

        # 2. 尝试命中期缓存
        src_date_range = _source_date_range(base_df)
        if src_date_range is not None:
            cached = get_cached_feed(symbol, src_date_range[0], src_date_range[1])
            if cached is not None:
                return cached

        # 3. 尝试磁盘序列化缓存
        feeds_dir = str(output_root() / "feeds" / symbol)
        feed = _try_load_from_disk(feeds_dir, all_loaded, requirements, src_date_range)

        # 4. 构造/初始化缓存目录
        if feed is not None:
            feed._feeds_dir = feeds_dir
        else:
            feed = cls(symbol=symbol, requirements=requirements)
            feed._feeds_dir = feeds_dir
            for period_name, df in all_loaded.items():  # type: ignore[assignment]
                if len(df) > 0:
                    feed._periods[period_name].load_df(df, replace=True)  # type: ignore[arg-type]
                    if period_name != source_period:
                        feed._agg_cache.pop(period_name, None)  # 高周期用 native 数据，清聚合缓存

        # 5. 写入内存缓存
        if src_date_range is not None:
            set_cached_feed(symbol, feed, src_date_range[0], src_date_range[1])

        return feed


# ==================== 辅助函数 ====================


def _source_date_range(source_df: pd.DataFrame | None) -> tuple[str, str] | None:
    if source_df is None or len(source_df) == 0:
        return None
    if not isinstance(source_df.index, pd.DatetimeIndex):
        return None
    return str(source_df.index[0].date()), str(source_df.index[-1].date())


def _try_load_from_disk(
    feeds_dir: str,
    all_loaded: dict[str, pd.DataFrame],
    requirements: DataRequirements,
    src_date_range: tuple[str, str] | None,
) -> DataFeed | None:
    if not os.path.isdir(feeds_dir):
        return None

    try:
        feed = DataFeed.from_feeds(feeds_dir)
    except Exception:
        return None

    if not feed.has_source_data():
        return None

    feed_date_range = feed.get_source_date_range()
    if feed_date_range is None or src_date_range is None:
        return None

    if feed_date_range[0] != src_date_range[0] or feed_date_range[1] != src_date_range[1]:
        return None

    feed.apply_requirements(requirements)

    feed.loaded_from_cache = True
    return feed
