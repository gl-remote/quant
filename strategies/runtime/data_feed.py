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
- 上下文构造：build_context

【内部约定】
- 基础周期（_base_period）由 apply_requirements 从声明的周期中自动推断为最小周期
- 高周期历史 K 线由调用方提供，聚合仅补充形成中的未完成 bar
- 调用方无需关心聚合细节，只需声明需要哪些周期和指标
"""

import os
from datetime import datetime as dt
from typing import TYPE_CHECKING

import pandas as pd
from loguru import logger

from common.symbol_utils import parse_contract

from ..core.indicators import IndicatorSpec
from ..core.types import Bar
from .aggregate import get_forming_bar_start, parse_period_minutes
from .events import Event, EventManager
from .period import PeriodData, PeriodDataView
from .requirements import BarContext, DataRequirements
from .serialization import dump_feed, load_feed

if TYPE_CHECKING:
    pass


class DataFeed:
    """管理单个品种的多周期数据

    【设计目标】
    - 管理单个品种（symbol）的所有周期数据
    - 持有该品种的元数据（symbol、数据源等）
    - 提供高层 API，调用方无需关心基础周期/聚合/懒计算等内部细节
    - 提供高效的数据访问路由（通过周期名快速定位 PeriodData）
    - 统一管理 K线、指标、事件 三类数据
    - 基础周期由 apply_requirements 自动推断为声明的最小周期，高周期由它聚合生成

    【工厂方法】
        DataFeed.create(symbol, requirements, feeds_dir, data_manager) -> DataFeed
        完整构造：自动处理缓存、从数据库加载所有周期、计算指标、序列化。
    """

    def __init__(
        self,
        symbol: str,
        source: str | None = None,
        requirements: DataRequirements | None = None,
    ):
        """初始化单个品种的多周期数据管理器

        :param symbol: 交易品种，如 "btc_usdt" 或 "CZCE.sr509"
        :param source: 数据源标识（可选，如果不提供可从symbol解析）
        :param requirements: 策略数据需求（可选），如果提供会自动调用 apply_requirements
        """
        self.symbol = symbol
        if source is None:
            ci = parse_contract(symbol)
            self.source = ci.exchange if ci else None
        else:
            self.source = source

        # 周期数据管理
        self._periods: dict[str, PeriodData] = {}

        # 基础周期：由 apply_requirements 自动推断为最小周期，高周期由它聚合得到
        self._base_period: str | None = None

        # 事件数据管理
        self._event_mgr = EventManager()

        # 聚合配置：高周期由基础周期自动聚合得到
        self._aggregation_targets: list[str] = []

        # 如果提供了 requirements，自动配置
        if requirements is not None:
            self.apply_requirements(requirements)

    @property
    def base_period(self) -> str | None:
        """获取基础周期名称"""
        return self._base_period

    @base_period.setter
    def base_period(self, value: str | None) -> None:
        """设置基础周期（供反序列化使用）"""
        self._base_period = value

    @property
    def events_df(self) -> pd.DataFrame:
        """获取事件 DataFrame（供序列化使用）"""
        return self._event_mgr.df

    @events_df.setter
    def events_df(self, value: pd.DataFrame) -> None:
        """设置事件 DataFrame（供反序列化使用）"""
        self._event_mgr.df = value

    def register_period(self, period: str) -> PeriodData:
        """注册一个新的周期，创建对应的PeriodData实例

        :param period: 周期名称，如 "1m", "5m", "1h"
        :return: 新创建或已存在的PeriodData实例
        """
        if period not in self._periods:
            self._periods[period] = PeriodData(period)
        return self._periods[period]

    def register_indicator(self, period_name: str, indicator: IndicatorSpec) -> None:
        """为指定周期注册需要计算的指标

        :param period_name: 周期名称
        :param indicator: IndicatorSpec 指标定义对象
        :raises KeyError: 如果周期未注册
        """
        if period_name not in self._periods:
            raise KeyError(f"Period {period_name} not registered")

        self._periods[period_name].register_indicator(indicator)

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
            assert existing_start is not None and existing_end is not None

            if new_start == existing_start and new_end <= existing_end:
                return  # 数据已包含，跳过
            elif new_start == existing_start and new_end > existing_end:
                append_df = df.loc[df.index > existing_end]
                if len(append_df) > 0:
                    period_data.load_df(append_df, replace=False)
            else:
                # new_start != existing_start，触发全量覆盖
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
        """批量追加事件数据

        :param events: 事件列表
        """
        self._event_mgr.append(events)

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
        return self._event_mgr.query(start_time, end_time, event_type, period)

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
        # 1. 收集所有需要的周期（periods + indicators 中出现的所有周期）
        all_periods = set(reqs.periods)
        for period in reqs.indicators:
            all_periods.add(period)

        # 2. 注册所有声明的周期
        for period in all_periods:
            self.register_period(period)

        # 3. 自动推断基础周期（最小周期）
        period_minutes = {p: parse_period_minutes(p) for p in all_periods}
        base_period = min(period_minutes, key=lambda p: period_minutes[p])
        self._base_period = base_period
        base_minutes = period_minutes[base_period]

        # 4. 校验：目标周期必须是基础周期的整数倍
        for period, minutes in period_minutes.items():
            if period != self._base_period and minutes % base_minutes != 0:
                raise ValueError(
                    f"周期 {period}（{minutes}分钟）不是基础周期 {self._base_period}（{base_minutes}分钟）的整数倍，无法聚合"
                )

        # 5. 启用聚合：高周期自动由基础周期聚合得到
        self.setup_aggregation(list(all_periods))

        # 6. 注册指标
        for period, ind_list in reqs.indicators.items():
            for ind in ind_list:
                self.register_indicator(period, ind)

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

            if not period_data.has_forming_bar:
                # 首次：设置形成中 bar
                period_data.set_forming_bar(_make_aggregated_bar(source_bar, bar_start))
            else:
                forming_bar = period_data.forming_bar
                assert forming_bar is not None
                forming_time = pd.Timestamp(forming_bar.datetime)
                if bar_start == forming_time:
                    # 仍在同一个高周期 bar 内 → 更新形成中 bar
                    period_data.update_forming_bar(source_bar)
                elif bar_start > forming_time:
                    # 新高周期 bar 开始 → 完成旧的，开始新的
                    period_data.complete_forming_bar()
                    period_data.set_forming_bar(_make_aggregated_bar(source_bar, bar_start))
                else:
                    logger.warning(
                        "[{}] bar_start({}) < forming_time({}), period={} —— 源 bar 时间异常，跳过聚合",
                        self.symbol,
                        bar_start,
                        forming_time,
                        target_period,
                    )

            # 形成中 bar 更新后，需要重算该周期指标
            period_data.calculate_indicators()

    def build_aggregations(self) -> None:
        """构建所有高周期聚合数据。

        遍历基础周期的全部 K 线，逐步构建高周期（5m, 15m 等）聚合数据。
        仅在目标周期无已加载数据时才构建（跳过已有数据的周期）。
        """
        assert self._base_period is not None
        base_data = self._periods.get(self._base_period)
        if base_data is None or base_data.length == 0:
            return
        if not self._aggregation_targets:
            return

        # 跳过已有数据的目标周期（如通过 load_history_df 预填充的场景）
        active_targets = [
            p for p in self._aggregation_targets if self._periods.get(p) is not None and self._periods[p].length == 0
        ]
        if not active_targets:
            return

        for idx in base_data.data.index:
            row = base_data.data.loc[idx]
            bar = Bar(
                symbol=self.symbol,
                datetime=idx.to_pydatetime(),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
            )
            self._step_aggregation(bar)

        for target_period in active_targets:
            period_data = self._periods.get(target_period)
            if period_data and period_data.has_forming_bar:
                period_data.complete_forming_bar()

    def calculate_all(self, force: bool = False) -> None:
        """批量预计算所有周期的所有指标（可选，用于回测初始化性能优化）

        适用场景：
        - 回测开始前，所有历史数据已加载
        - 希望一次性预计算所有指标，避免运行时懒加载的轻微延迟

        注意：
        - 不是必须调用，不调用也能用
        - force=True 时会覆盖已有的指标数据（用于 build_aggregations 后的全量重算）
        - force=False（默认）时会跳过已计算的指标

        :param force: 强制全量重算，清除已有的部分指标结果
        """
        for period_data in self._periods.values():
            period_data.calculate_indicators(force=force)

    def calculate_period(self, period_name: str) -> None:
        """只计算指定周期的所有注册指标（跳过已计算且最后一行非 NaN 的指标）"""
        period_data = self._periods.get(period_name)
        if period_data is not None:
            period_data.calculate_indicators()

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
        return period_data.indicator_names

    def get_registered_indicators(self, period_name: str) -> list[IndicatorSpec]:
        """获取指定周期已注册的指标配置列表

        :param period_name: 周期名称
        :return: IndicatorSpec 列表，周期不存在返回空列表
        """
        period_data = self._periods.get(period_name)
        if period_data is None:
            return []
        return period_data.registered_indicators

    def get_date_range(self, period_name: str) -> tuple[str, str] | None:
        """获取指定周期的数据日期范围

        :param period_name: 周期名称
        :return: (min_dt, max_dt) 日期字符串，周期不存在或无数据返回 None
        """
        period_data = self._periods.get(period_name)
        if period_data is None or period_data.length == 0:
            return None
        first = period_data.first_time
        last = period_data.latest_time
        assert first is not None and last is not None
        return str(first.date()), str(last.date())

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

        period_data = self._periods[period_name]
        current_time_ts = pd.Timestamp(current_time)
        # 懒加载计算指标（如果还没计算）
        period_data.calculate_indicators()
        return period_data.get_data(current_time_ts, lookback_bars, self._event_mgr.df)

    def build_context(
        self,
        requirements: DataRequirements,
        bar: Bar,
        timeout: float | None = None,
    ) -> BarContext:
        """构造 BarContext 上下文对象

        行为：
        1. 解析 requirements 中的 periods 配置
        2. 对每个周期调用 self.get_data(period, current_time, lookback_bars, timeout)
        3. 从 self 获取当前时间范围内的事件（按 requirements.events 配置筛选）
        4. 构造并返回 BarContext 对象
        """
        current_time = pd.Timestamp(bar.datetime)
        multi: dict[str, PeriodDataView] = {}

        # 获取多周期数据
        for period, req in requirements.periods.items():
            view = self.get_data(period, current_time, req.lookback_bars, timeout)
            if view is not None:
                multi[period] = view

        # 获取事件（不需要事件时直接跳过，节省锁和 DataFrame 操作）
        events: list[Event] = []
        events_req = requirements.events

        if events_req.include_global_events or events_req.include_period_events:
            # 按最大 lookback 窗口计算 start_time，避免每次遍历全量历史事件
            max_lookback = max(req.lookback_bars for req in requirements.periods.values())
            # 从当前时间倒推最大 lookback 窗口；若找不到对应周期分钟数则不回退
            start_time: pd.Timestamp | None = None
            try:
                # 取基础周期分钟数估算窗口宽度，统一为单位时间
                if self._base_period:
                    period_min = parse_period_minutes(self._base_period)
                    start_time = current_time - pd.Timedelta(minutes=period_min * max_lookback)
            except Exception:
                pass

            all_events = self.get_events(start_time=start_time, end_time=current_time)

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
        if bar.symbol != self.symbol:
            logger.warning(
                "[{}] build_context 收到 symbol={} 的 bar，已修正为 {}",
                self.symbol,
                bar.symbol,
                self.symbol,
            )
            bar.symbol = self.symbol

        return BarContext(symbol=self.symbol, bar=bar, multi=multi, events=events)

    @classmethod
    def create(
        cls,
        symbol: str,
        requirements: DataRequirements,
    ) -> "DataFeed":
        """完整构造一个 DataFeed，自动处理缓存、增量加载、序列化

        【流程逻辑】
        1. 根据 requirements 找出基础周期（最小间隔）
        2. 先查内存缓存，命中直接返回（零 I/O）
        3. 内存未命中，尝试从磁盘 feeds 目录反序列化加载
        4. 检查源数据日期范围是否匹配，不匹配则全量重加载
        5. 如果磁盘加载成功，合并缺失的周期/指标需求，增量计算
        6. 最后写入内存缓存并返回

        :param symbol: 交易品种
        :param requirements: 数据需求
        :return: 构造完成的 DataFeed
        """
        from data.manager import DataManager
        from data.output_paths import output_root

        from .cache import get_cached_feed, get_cached_feed_by_symbol, set_cached_feed

        dm = DataManager()
        feeds_dir = str(output_root() / "feeds" / symbol)

        # 按 requirements 推断基础周期（最小周期），用作源数据加载粒度。
        # 高周期由 apply_requirements 自动从基础周期聚合得到。
        all_periods = set(requirements.periods)
        for period in requirements.indicators:
            all_periods.add(period)
        if not all_periods:
            raise ValueError(f"requirements 未声明任何周期，无法推断基础周期: symbol={symbol}")
        source_period = min(all_periods, key=parse_period_minutes)

        # 从 CSV 加载基础周期源数据
        base_df: pd.DataFrame | None = None
        try:
            results = dm.load_kline([symbol], interval=source_period)
        except FileNotFoundError:
            cached = get_cached_feed_by_symbol(symbol)
            if cached is not None:
                return cached
            raise
        if results:
            _, base_df, _ = results[0]
            # load_kline 返回的 DataFrame 以 "datetime" 列存储，需转为 DatetimeIndex
            if "datetime" in base_df.columns:
                base_df = base_df.set_index("datetime")

        # 计算源数据日期范围（缓存 key）
        src_date_range = _source_date_range(base_df)

        # 0. 查内存缓存（零 I/O 路径）
        if src_date_range is not None:
            cached = get_cached_feed(symbol, src_date_range[0], src_date_range[1])
            if cached is not None:
                return cached

        # 1. 尝试从磁盘加载
        feed = _try_load_from_disk(feeds_dir, base_df, requirements, src_date_range)

        # 2. 磁盘加载失败，全量构造
        if feed is None:
            feed = cls(symbol=symbol, requirements=requirements)
            if base_df is not None and len(base_df) > 0 and isinstance(base_df.index, pd.DatetimeIndex):
                feed.feed_history_df(base_df)
            feed.calculate_all()
            feed.build_aggregations()
            feed.calculate_all(force=True)
            feed.to_feeds(feeds_dir)

        # 写入内存缓存
        if src_date_range is not None:
            set_cached_feed(symbol, feed, src_date_range[0], src_date_range[1])

        return feed


# ==================== 辅助函数 ====================


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


def _source_date_range(source_df: pd.DataFrame | None) -> tuple[str, str] | None:
    """提取源数据的日期范围（用于缓存 key）"""
    if source_df is None or len(source_df) == 0:
        return None
    if not isinstance(source_df.index, pd.DatetimeIndex):
        return None
    return str(source_df.index[0].date()), str(source_df.index[-1].date())


def _try_load_from_disk(
    feeds_dir: str,
    source_df: pd.DataFrame | None,
    requirements: DataRequirements,
    src_date_range: tuple[str, str] | None,
) -> DataFeed | None:
    """尝试从磁盘加载 DataFeed，日期不匹配或加载失败返回 None"""
    if not os.path.isdir(feeds_dir):
        return None

    try:
        feed = DataFeed.from_feeds(feeds_dir)
    except Exception:
        return None

    # 检查源数据是否存在且日期匹配
    if not feed.has_source_data():
        return None

    feed_date_range = feed.get_source_date_range()
    if feed_date_range is None or src_date_range is None:
        return None

    if feed_date_range[0] != src_date_range[0] or feed_date_range[1] != src_date_range[1]:
        return None

    # 磁盘数据有效，增量合并缺失的周期/指标
    existing_periods = set(feed.get_period_names())
    existing_indicators = {
        (pn, spec.name, tuple(sorted(spec.params.items())))
        for pn in requirements.indicators
        for spec in feed.get_registered_indicators(pn)
    }

    feed.apply_requirements(requirements)

    new_periods = set(feed.get_period_names()) - existing_periods
    new_indicators = {
        (pn, spec.name, tuple(sorted(spec.params.items())))
        for pn in requirements.indicators
        for spec in feed.get_registered_indicators(pn)
    } - existing_indicators

    if new_periods or new_indicators:
        feed.calculate_all(force=True)
        feed.to_feeds(feeds_dir)

    return feed
