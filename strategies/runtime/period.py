"""单个周期的数据容器与只读逻辑视图

包含：
- PeriodData: 单个周期的数据容器，管理K线和指标
- PeriodDataView: 只读逻辑视图，不复制数据，按时间和历史条数裁剪
"""

from datetime import datetime as dt
from typing import cast

import numpy as np
import pandas as pd
from loguru import logger
from numpy.typing import NDArray

from ..core.indicators import IndicatorSpec, generate_indicator_column_name
from ..core.types import Bar
from .events import Event

# OHLCV 标准列名
_OHLCV_COLUMNS = frozenset({"open", "high", "low", "close", "volume"})


def _make_bar_from_row(row: pd.Series, symbol: str = "") -> Bar:
    """从 DataFrame 一行构造 Bar 对象"""
    row_name = cast(pd.Timestamp, row.name)
    return Bar(
        symbol=symbol,
        datetime=row_name.to_pydatetime(),
        open=row["open"],
        high=row["high"],
        low=row["low"],
        close=row["close"],
        volume=row["volume"],
    )


def _forming_bar_to_series(bar: Bar) -> pd.Series:
    """将 forming Bar 转为 DataFrame 行（pd.Series，name 为时间戳）"""
    forming_time = pd.Timestamp(bar.datetime)
    return pd.Series(
        {"open": bar.open, "high": bar.high, "low": bar.low, "close": bar.close, "volume": bar.volume},
        name=forming_time,
    )


class PeriodData:
    """单个周期的数据容器

    【设计目标】
    - 统一管理该周期的 K线、指标两类数据（事件由 DataFeed 统一管理）
    - 提供逻辑视图，策略只能看到指定时间点之前的数据
    - 支持数据追加（Append-Only，历史数据不修改）
    - 底层存储使用 Pandas DataFrame
    - 高效的数据访问，通过逻辑视图实现，不复制数据

    【两种使用场景】
    - 场景1：由 DataFeed 统一管理（多策略共享）
    - 场景2：策略自己持有（策略私有数据，不共享）
    """

    def __init__(self, period: str):
        """初始化单个周期的数据容器

        初始化过程：
        1. 创建空的K线+指标DataFrame，包含datetime, open, high, low, close, volume列
        2. 初始化状态变量和数据追踪字段

        :param period: 周期名称，如 "1m", "5m", "1h", "1d" 等
        """
        self.period = period

        # K线数据（OHLCV） + 指标数据（合并在一起，索引统一为datetime）
        # 索引为空的 DataFrame，后续加载数据时会自动设置 datetime 索引
        self._df: pd.DataFrame = pd.DataFrame(
            columns=["open", "high", "low", "close", "volume"],
            dtype="float64",
        )
        self._df.index.name = "datetime"

        # 形成中的 bar：由 _aggregate_period_view 构造视图时使用
        # 或由 calculate_indicators 在拼接 forming bar 时引用
        self._forming_bar: Bar | None = None
        # 形成中 bar 的指标缓存 {indicator_name: value}
        self._forming_indicators: dict[str, float] = {}

        # 已注册的指标列表
        self._registered_indicators: list[IndicatorSpec] = []

    @property
    def first_time(self) -> pd.Timestamp | None:
        """获取最早数据时间戳"""
        if len(self._df) == 0:
            return None
        return cast(pd.Timestamp, self._df.index[0])

    @property
    def latest_time(self) -> pd.Timestamp | None:
        """获取最新数据时间戳（含形成中 bar）"""
        if self._forming_bar is not None:
            return pd.Timestamp(self._forming_bar.datetime)
        if len(self._df) == 0:
            return None
        return cast(pd.Timestamp, self._df.index[-1])

    @property
    def length(self) -> int:
        """获取当前数据长度（K线数量）"""
        return len(self._df)

    @property
    def data(self) -> pd.DataFrame:
        """获取底层 DataFrame（只读）"""
        return self._df

    def _append_df(self, new_df: pd.DataFrame) -> None:
        """内部方法：将新 DataFrame 追加到 _df，带时间顺序校验

        :param new_df: 要追加的 DataFrame，索引为 datetime
        :raises ValueError: 如果时间顺序不对（新数据的时间 <= 已有最新时间）
        """
        if len(new_df) == 0:
            return

        if len(self._df) > 0:
            last_time = self._df.index[-1]
            first_new_time = new_df.index[0]
            if first_new_time <= last_time:
                raise ValueError(f"New data time {first_new_time} is not after existing last time {last_time}")

        if len(self._df) == 0:
            self._df = new_df.copy()
        else:
            self._df = pd.concat([self._df, new_df])

    def append_bar(self, bar: Bar) -> None:
        """追加单根K线

        :param bar: 单根K线数据
        :raises ValueError: 如果 bar 时间 <= 已有最新时间
        """
        bar_time = pd.Timestamp(bar.datetime)
        new_df = pd.DataFrame(
            {"open": [bar.open], "high": [bar.high], "low": [bar.low], "close": [bar.close], "volume": [bar.volume]},
            index=pd.Index([bar_time], name="datetime"),
        )
        self._append_df(new_df)

    def append_bars(self, bars: list[Bar]) -> None:
        """批量追加K线数据（用于回测初始化）

        :param bars: K线列表
        :raises ValueError: 如果bars为空或时间顺序不对
        """
        if not bars:
            raise ValueError("Bars list is empty")

        records = [
            {
                "datetime": pd.Timestamp(bar.datetime),
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
            }
            for bar in bars
        ]
        new_df = pd.DataFrame(records).set_index("datetime")
        self._append_df(new_df)

    def load_df(self, df: pd.DataFrame, replace: bool = False) -> None:
        """从 DataFrame 直接加载数据，避免 Bar 转换开销

        DataFrame 要求索引为 datetime，包含 open/high/low/close/volume 列。

        :param df: K线 DataFrame，索引为 datetime
        :param replace: True 时清空已有数据后加载，False 时追加
        """
        if replace:
            self._df = df.copy()
        else:
            self._append_df(df)

    def update_forming_bar(self, bar: Bar) -> None:
        """更新形成中的 bar（不写入 _df）"""
        if self._forming_bar is None:
            raise RuntimeError("No forming bar to update, call set_forming_bar first")
        self._forming_bar = Bar(
            symbol=self._forming_bar.symbol,
            datetime=self._forming_bar.datetime,
            open=self._forming_bar.open,
            high=max(self._forming_bar.high, bar.high),
            low=min(self._forming_bar.low, bar.low),
            close=bar.close,
            volume=self._forming_bar.volume + bar.volume,
        )
        self._forming_indicators.clear()

    def set_forming_bar(self, bar: Bar) -> None:
        self._forming_bar = bar
        self._forming_indicators.clear()

    def complete_forming_bar(self) -> None:
        if self._forming_bar is None:
            return
        self.append_bar(self._forming_bar)
        self._forming_bar = None
        self._forming_indicators.clear()

    @property
    def has_forming_bar(self) -> bool:
        return self._forming_bar is not None

    @property
    def forming_bar(self) -> Bar | None:
        return self._forming_bar

    def reset(self) -> None:
        self._df = pd.DataFrame(
            columns=["open", "high", "low", "close", "volume"],
            dtype="float64",
        )
        self._df.index.name = "datetime"
        self._forming_bar = None
        self._forming_indicators.clear()

    def register_indicator(self, spec: IndicatorSpec) -> None:
        """注册需要计算的指标

        :param spec: IndicatorSpec 指标定义对象
        """
        for existing in self._registered_indicators:
            if existing.name == spec.name and existing.params == spec.params:
                return
        self._registered_indicators.append(spec)

    @property
    def indicator_names(self) -> list[str]:
        """获取已计算的指标列名（排除 OHLCV 列）"""
        return [c for c in self._df.columns if c not in _OHLCV_COLUMNS]

    @property
    def registered_indicators(self) -> list[IndicatorSpec]:
        """获取已注册的指标配置列表（只读副本）"""
        return list(self._registered_indicators)

    def calculate_indicators(self, force: bool = False) -> None:
        """计算所有注册指标

        跳过已计算且最后一行非 NaN 的指标，对需要计算的指标做全量计算。
        对于有 forming bar 的周期，在临时拼接的 DataFrame 上计算，
        结果分别写回 _df 和 _forming_indicators，不修改 _df 本身。

        首次计算（列不存在或 force=True）时对全量数据计算，
        后续增量更新仅计算 window 尾部。

        :param force: 强制全量重算，清除已有的部分指标结果
        """
        if not self._registered_indicators:
            return

        for spec in self._registered_indicators:
            col_name = generate_indicator_column_name(spec.name, spec.params)

            # 跳过已计算且最后一行非 NaN 的指标（force 模式下不跳过）
            # 如有 forming bar，还需其指标缓存也已计算
            if not force and col_name in self._df.columns:
                if len(self._df) > 0 and not self._df[col_name].isna().iloc[-1]:
                    if self._forming_bar is None or col_name in self._forming_indicators:
                        continue

            if spec.func is None:
                continue

            try:
                window = spec.window if isinstance(spec.window, int) else 250
                is_first_compute = force or col_name not in self._df.columns

                # 首次计算/强制重算：对全量数据计算；增量更新：仅计算 window 尾部
                if is_first_compute:
                    compute_df = self._df
                else:
                    tail_len = min(window, len(self._df))
                    compute_df = self._df.tail(tail_len)

                # 拼接 forming bar 到临时 DataFrame，不修改 _df
                if self._forming_bar is not None:
                    forming_row = _forming_bar_to_series(self._forming_bar)
                    compute_df = pd.concat([compute_df, forming_row.to_frame().T])

                if len(compute_df) == 0:
                    continue

                result = spec.func(compute_df, **spec.params)
                result_series = pd.Series(result, index=compute_df.index)

                # 结果写回 _df（只写 _df 中存在的行）
                if col_name not in self._df.columns:
                    self._df[col_name] = np.nan
                df_mask = compute_df.index.isin(self._df.index)
                self._df.loc[compute_df.index[df_mask], col_name] = result_series[df_mask]

                # forming bar 的指标值写入缓存
                if self._forming_bar is not None:
                    forming_time = pd.Timestamp(self._forming_bar.datetime)
                    if forming_time in result_series.index:
                        val = result_series[forming_time]
                        self._forming_indicators[col_name] = float(val) if not pd.isna(val) else np.nan

            except Exception as e:
                logger.warning("指标计算失败 [{}][{}]: {}", self.period, spec.name, e)

    def append_indicators(self, indicators: pd.DataFrame) -> None:
        """追加指标数据

        指标DataFrame要求：
        1. 索引必须与K线的datetime对齐
        2. 列名应为指标名（如 "sma_10", "ema_20")

        :param indicators: 指标DataFrame，行数应等于或小于当前K线数
        :raises ValueError: 如果索引不匹配
        """
        # 验证索引
        if len(indicators) > len(self._df):
            raise ValueError("Indicators DataFrame has more rows than K-line data")

        # 合并指标数据
        for col in indicators.columns:
            self._df[col] = indicators[col]

    def get_data(
        self, current_time: pd.Timestamp | dt, lookback_bars: int = 1, events_df: pd.DataFrame | None = None
    ) -> "PeriodDataView":
        """获取截止指定时间点的逻辑视图（只读，用于策略安全访问）

        视图特性：
        1. 只包含截止到current_time的数据，不包含之后的未来数据
        2. 只读访问，策略无法修改原始数据
        3. 不受后续数据更新影响，保证数据一致性（Append-Only）
        4. 可指定需要的历史K线数，限定视图范围
        5. 逻辑视图，不复制数据，通过索引范围访问原始数据
        6. 若存在形成中 bar 且时间 <= current_time，视图会包含它

        :param current_time: 当前时间，视图将只包含<=此时间的数据
        :param lookback_bars: 需要的历史K线数，从current_time往前数，默认1根
        :param events_df: 事件DataFrame（由DataFeed传入）
        :return: PeriodDataView只读逻辑视图对象
        :raises ValueError: 如果current_time晚于最新数据时间，或lookback_bars <= 0
        """
        if lookback_bars <= 0:
            raise ValueError("lookback_bars must be positive")

        current_time_ts: pd.Timestamp = pd.Timestamp(current_time)  # type: ignore[assignment]

        # 检查时间是否有效（考虑 forming bar）
        # forming bar 的时间戳是其起始时间（如 10:00），但 visual 上它覆盖到
        # (start, start + period_minutes] 的时间范围。因此允许 current_time 位于
        # (forming_bar.datetime, forming_bar.datetime + period] 区间内。
        latest = self.latest_time
        if latest is not None and current_time_ts > latest:
            # 检查是否在 forming bar 的 effective 范围内
            forming_end = None
            try:
                from .aggregate import parse_period_minutes

                period_minutes = parse_period_minutes(self.period)
                if latest is not None:
                    forming_end = latest + pd.Timedelta(minutes=period_minutes)
            except Exception:
                pass
            if forming_end is None or current_time_ts > forming_end:
                raise ValueError(f"current_time {current_time_ts} is after latest data time {latest}")

        # 判断 forming bar 是否应包含在视图中
        include_forming = False
        if self._forming_bar is not None:
            forming_time = pd.Timestamp(self._forming_bar.datetime)
            if forming_time <= current_time_ts:
                include_forming = True

        # 找到截止时间对应的索引（ffill: 取 <= current_time 的最后一根 bar）
        if len(self._df) > 0:
            end_idx = self._df.index.get_indexer(pd.Index([current_time_ts]), method="ffill")[0]
            # end_idx < 0 表示 current_time 在第一根 bar 之前，没有可见的完整 bar
        else:
            end_idx = -1  # _df 为空，没有完整 bar

        # 计算起始索引
        start_idx = max(0, end_idx - lookback_bars + 1) if end_idx >= 0 else 0

        return PeriodDataView(
            df_ref=self._df,
            events_ref=events_df,
            start_idx=start_idx,
            end_idx=end_idx,
            current_time=current_time_ts,
            period=self.period,
            forming_bar=self._forming_bar if include_forming else None,
            forming_indicators=self._forming_indicators if include_forming else None,
        )

    def get_bar(self, idx: int) -> Bar | None:
        """通过索引获取K线

        索引规则：
        0: 最早的K线
        -1: 最新的K线

        :param idx: 索引位置，支持负索引
        :return: Bar对象，索引越界返回None
        """
        if len(self._df) == 0:
            return None

        try:
            return _make_bar_from_row(self._df.iloc[idx])
        except IndexError:
            return None

    def get_indicator(self, name: str, idx: int) -> float | None:
        """通过索引获取指标值

        :param name: 指标名称，如 "sma_10", "rsi_14"
        :param idx: 索引位置，支持负索引，-1表示最新
        :return: 指标值，索引越界或指标不存在返回None
        """
        if name not in self._df.columns:
            return None

        if len(self._df) == 0:
            return None

        try:
            return float(self._df[name].iloc[idx])
        except IndexError:
            return None

    def get_indicator_series(self, name: str) -> pd.Series:
        """获取指标完整序列

        :param name: 指标名称
        :return: 指标Series，索引为datetime
        :raises KeyError: 如果指标不存在
        """
        if name not in self._df.columns:
            raise KeyError(f"Indicator {name} not found")
        return self._df[name].copy()

    def set_indicator_column(self, name: str, data: NDArray[np.float64]) -> None:
        """将指标计算结果写入内部存储

        封装对 self._df[name] = data 的访问，外部无需直接操作 _df。

        :param name: 指标列名（如 "sma_10"）
        :param data: 指标计算结果 numpy 数组
        """
        self._df[name] = data

    def to_parquet(self, path: str) -> None:
        """将数据序列化到 parquet 文件

        :param path: 目标文件路径
        """
        self._df.to_parquet(path, index=True)


class PeriodDataView:
    """只读逻辑视图

    【设计目标】
    - 只读逻辑视图，防止策略修改数据
    - 只包含截止指定时间点和指定历史K线范围的数据
    - 不受后续数据更新影响（Append-Only 保证）
    - 高效实现：通过索引范围访问原始数据，不复制数据
    - 纯只读，不触发任何计算
    - 支持包含形成中的 bar（高周期聚合时，forming bar 作为虚拟最后一行）

    【形成中 bar 的处理】
    - forming_bar 不在 _df 中，作为虚拟最后一行附加在视图末尾
    - 视图索引：0..N-1 为 _df 中的行，N 为 forming_bar（如果存在）
    - forming_indicators 提供形成中 bar 的指标值
    """

    def __init__(
        self,
        df_ref: pd.DataFrame,
        events_ref: pd.DataFrame | None,
        start_idx: int,
        end_idx: int,
        current_time: pd.Timestamp,
        period: str,
        forming_bar: Bar | None = None,
        forming_indicators: dict[str, float] | None = None,
    ):
        """初始化逻辑视图（内部使用，不应直接构造）

        :param df_ref: 原始K线+指标DataFrame的引用（不复制）
        :param events_ref: 原始事件DataFrame的引用（不复制）
        :param start_idx: 视图的起始索引（包含，相对于 _df）
        :param end_idx: 视图的结束索引（包含，相对于 _df），-1 表示 _df 无数据
        :param current_time: 视图的截止时间
        :param period: 周期名称
        :param forming_bar: 形成中的 bar（作为虚拟最后一行）
        :param forming_indicators: 形成中 bar 的指标缓存
        """
        self._df_ref = df_ref
        self._events_ref = events_ref
        self._start_idx = start_idx
        self._end_idx = end_idx
        self._current_time = current_time
        self._period = period
        self._forming_bar = forming_bar
        self._forming_indicators = forming_indicators or {}
        self._indicator_cache: dict[str, float] = {}

    def calculate_indicators(self, registered_indicators: list[IndicatorSpec]) -> None:
        """基于视图范围内的数据计算指标，结果缓存在视图内部

        不写回 _df_ref。指标计算仅基于视图中可见的已完成 bar + forming bar。
        """
        if not registered_indicators:
            return

        from ..core.indicators import generate_indicator_column_name

        # 取视图范围内的 _df 子集
        if self._df_count > 0:
            view_df = self._df_ref.iloc[self._start_idx : self._end_idx + 1].copy()
        else:
            view_df = pd.DataFrame(columns=self._df_ref.columns, dtype="float64")

        # 拼接 forming bar
        if self._forming_bar is not None:
            forming_row = _forming_bar_to_series(self._forming_bar)
            view_df = pd.concat([view_df, forming_row.to_frame().T])

        if len(view_df) == 0:
            return

        for spec in registered_indicators:
            col_name = generate_indicator_column_name(spec.name, spec.params)
            if spec.func is None:
                continue
            if col_name in self._indicator_cache:
                continue

            try:
                result = spec.func(view_df, **spec.params)
                result_series = pd.Series(result, index=view_df.index)
                last_val = result_series.iloc[-1]
                self._indicator_cache[col_name] = float(last_val) if not pd.isna(last_val) else np.nan
            except Exception as e:
                logger.warning("指标计算失败 [{}][{}]: {}", self._period, spec.name, e)

    @property
    def current_time(self) -> pd.Timestamp:
        """获取视图的截止时间"""
        return self._current_time

    @property
    def _df_count(self) -> int:
        """视图中来自 _df 的行数"""
        return max(0, self._end_idx - self._start_idx + 1) if self._end_idx >= 0 else 0

    @property
    def length(self) -> int:
        """获取视图中K线数量（含 forming bar）"""
        return self._df_count + (1 if self._forming_bar is not None else 0)

    @property
    def period(self) -> str:
        """获取周期名称"""
        return self._period

    def _resolve_idx(self, idx: int) -> int | None:
        """将任意索引（含负索引）解析为正索引，越界返回 None

        返回值范围：0..total-1，其中 total = _df_count + (1 if forming_bar)
        """
        total = self.length
        pos_idx = total + idx if idx < 0 else idx
        if pos_idx < 0 or pos_idx >= total:
            return None
        return pos_idx

    def get_bar(self, idx: int = -1) -> Bar | None:
        """通过索引获取K线（索引相对于视图）

        :param idx: 索引位置，支持负索引（相对于视图）
        :return: Bar对象，索引越界返回None
        """
        pos_idx = self._resolve_idx(idx)
        if pos_idx is None:
            return None

        # forming bar 在最后
        if self._forming_bar is not None and pos_idx == self._df_count:
            return self._forming_bar

        # 从 _df 中取
        real_idx = self._start_idx + pos_idx
        if real_idx < self._start_idx or real_idx > self._end_idx:
            return None

        try:
            return _make_bar_from_row(self._df_ref.iloc[real_idx])
        except IndexError:
            return None

    def get_indicator(self, name: str, idx: int = -1) -> float | None:
        """通过索引获取指标值（索引相对于视图）
        注意：此方法不触发计算，指标不存在返回 None

        :param name: 指标名称，如 "sma_10"
        :param idx: 索引位置，支持负索引（相对于视图）
        :return: 指标值，索引越界或指标不存在返回None
        """
        # 优先从视图内部缓存取（指标已在 build_context 时算好缓存在这里）
        if name in self._indicator_cache:
            return self._indicator_cache[name]

        pos_idx = self._resolve_idx(idx)
        if pos_idx is None:
            return None

        # forming bar 的指标从 _forming_indicators 取
        if self._forming_bar is not None and pos_idx == self._df_count:
            return self._forming_indicators.get(name)

        # 从 _df 中取（兼容预计算指标的场景）
        if name not in self._df_ref.columns:
            return None

        real_idx = self._start_idx + pos_idx
        if real_idx < self._start_idx or real_idx > self._end_idx:
            return None

        try:
            return float(self._df_ref[name].iloc[real_idx])
        except IndexError:
            return None

    def get_events(self) -> list[Event]:
        """获取视图时间范围内的所有事件"""
        if self._events_ref is None or len(self._events_ref) == 0:
            return []

        # 获取视图时间范围
        if self._df_count > 0 and len(self._df_ref) > 0:
            view_start = self._df_ref.index[self._start_idx]
            view_end = self._df_ref.index[self._end_idx]
        elif self._forming_bar is not None:
            forming_time = pd.Timestamp(self._forming_bar.datetime)
            view_start = forming_time
            view_end = forming_time
        else:
            return []

        # 如果有 forming bar，扩展时间范围
        if self._forming_bar is not None:
            forming_time = pd.Timestamp(self._forming_bar.datetime)
            if forming_time > view_end:
                view_end = forming_time

        # 筛选时间范围内的事件
        mask = (self._events_ref.index >= view_start) & (self._events_ref.index <= view_end)
        events_df = self._events_ref[mask]

        return [
            Event(
                timestamp=cast(pd.Timestamp, row.name).to_pydatetime(),
                type=row["type"],
                symbol=row["symbol"],
                reason=row.get("reason", ""),
                period=row.get("period"),
                data=row.get("data"),
            )
            for _, row in events_df.iterrows()
        ]

    def get_all_bars(self) -> pd.DataFrame:
        """获取视图中所有K线+指标DataFrame（含 forming bar）"""
        if self._df_count > 0:
            result = self._df_ref.iloc[self._start_idx : self._end_idx + 1].copy()
        else:
            result = pd.DataFrame(columns=self._df_ref.columns, dtype="float64")
            result.index.name = "datetime"

        if self._forming_bar is not None:
            forming_row = _forming_bar_to_series(self._forming_bar)
            # 添加 forming bar 的指标值
            for ind_name, ind_val in self._forming_indicators.items():
                forming_row[ind_name] = ind_val
            result.loc[forming_row.name] = forming_row

        return result

    # --- 便捷访问器 ---

    def bar(self, idx: int = -1) -> Bar | None:
        """便捷方法：获取K线"""
        return self.get_bar(idx)

    def close(self, idx: int = -1) -> float | None:
        """便捷方法：获取收盘价"""
        bar = self.get_bar(idx)
        return bar.close if bar is not None else None

    def indicator(self, name: str, idx: int = -1) -> float | None:
        """便捷方法：获取指标值"""
        return self.get_indicator(name, idx)

    def indicator_series(self, name: str) -> pd.Series:
        """便捷方法：获取指标序列（含 forming bar 的指标值）"""
        if self._df_count > 0:
            if name not in self._df_ref.columns:
                raise KeyError(f"Indicator {name} not found")
            result = self._df_ref[name].iloc[self._start_idx : self._end_idx + 1].copy()
        else:
            result = pd.Series(dtype="float64", name=name)

        if self._forming_bar is not None and name in self._forming_indicators:
            forming_time = pd.Timestamp(self._forming_bar.datetime)
            result.loc[str(forming_time)] = self._forming_indicators[name]

        return result

    def events(self) -> list[Event]:
        """便捷方法：获取事件列表"""
        return self.get_events()
