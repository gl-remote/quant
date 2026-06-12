"""单个周期的数据容器与只读逻辑视图

包含：
- PeriodData: 单个周期的数据容器，管理K线和指标
- PeriodDataView: 只读逻辑视图，不复制数据，按时间和历史条数裁剪
"""

from collections.abc import Callable
from datetime import datetime as dt
from typing import Any, cast

import pandas as pd

from ..core.types import Bar
from .events import Event


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
        self._df: pd.DataFrame = pd.DataFrame(columns=["datetime", "open", "high", "low", "close", "volume"])
        self._df = self._df.astype(
            {"open": "float64", "high": "float64", "low": "float64", "close": "float64", "volume": "float64"}
        )

        # 数据追踪字段（类似数据库表）
        self._created_at = pd.Timestamp.now()
        self._last_updated_at = pd.Timestamp.now()
        self._update_count = 0

        # 指标计算状态跟踪
        self._calculated_indicators: set[str] = set()
        self._indicator_last_calc_idx: dict[str, int] = {}

    @property
    def first_time(self) -> pd.Timestamp | None:
        """获取最早数据时间戳"""
        if len(self._df) == 0:
            return None
        return cast(pd.Timestamp, self._df.index[0])

    @property
    def latest_time(self) -> pd.Timestamp | None:
        """获取最新数据时间戳"""
        if len(self._df) == 0:
            return None
        return cast(pd.Timestamp, self._df.index[-1])

    @property
    def length(self) -> int:
        """获取当前数据长度（K线数量）"""
        return len(self._df)

    def append_bars(self, bars: list[Bar]) -> None:
        """批量追加K线数据（用于回测初始化）

        注意事项：
        1. 必须按时间升序排列
        2. 时间戳不能与已有的数据重复
        3. Append-Only：历史数据不会被修改
        4. 更新数据追踪字段：_last_updated_at 和 _update_count

        :param bars: K线列表
        :raises ValueError: 如果bars为空或时间顺序不对
        """
        if not bars:
            raise ValueError("Bars list is empty")

        # 验证时间顺序
        prev_time = None
        if len(self._df) > 0:
            prev_time = self._df.index[-1]

        bar_dicts = []
        for bar in bars:
            bar_time = pd.Timestamp(bar.datetime)
            if prev_time is not None and bar_time <= prev_time:
                raise ValueError(f"Bar time {bar_time} is not after previous time {prev_time}")
            prev_time = bar_time

            bar_dicts.append(
                {
                    "datetime": bar_time,
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume,
                }
            )

        # 转换为DataFrame并追加
        new_df = pd.DataFrame(bar_dicts)
        new_df = new_df.set_index("datetime")

        if len(self._df) == 0:
            self._df = new_df
        else:
            self._df.loc[new_df.index] = new_df

        # 更新数据追踪字段
        self._last_updated_at = pd.Timestamp.now()
        self._update_count += len(bars)

    def load_df(self, df: pd.DataFrame, replace: bool = False) -> None:
        """从 DataFrame 直接加载数据，避免 Bar 转换开销

        DataFrame 要求索引为 datetime，包含 open/high/low/close/volume 列。

        :param df: K线 DataFrame，索引为 datetime
        :param replace: True 时清空已有数据后加载，False 时追加
        """
        if replace:
            self._df = df.copy()
            self._calculated_indicators.clear()
            self._indicator_last_calc_idx.clear()
        else:
            if len(self._df) == 0:
                self._df = df.copy()
            else:
                new_rows = df.loc[~df.index.isin(self._df.index)]
                if len(new_rows) > 0:
                    self._df.loc[new_rows.index] = new_rows

        self._last_updated_at = pd.Timestamp.now()
        self._update_count += 1

    def append_bar(self, bar: Bar) -> None:
        """追加单根K线（每个 PeriodData 独立，无并发，无需幂等检查）

        注意：此方法不再清除指标缓存。指标计算状态由 DataFeed
        在 calculate_all / calculate_period 中统一管理。

        :param bar: 单根K线数据
        """
        bar_time = pd.Timestamp(bar.datetime)

        new_row = pd.Series(
            {"open": bar.open, "high": bar.high, "low": bar.low, "close": bar.close, "volume": bar.volume},
            name=bar_time,
        )

        self._df.loc[bar_time] = new_row

        # 更新数据追踪字段
        self._last_updated_at = pd.Timestamp.now()
        self._update_count += 1

    def append_indicators(self, indicators: pd.DataFrame) -> None:
        """追加指标数据

        指标DataFrame要求：
        1. 索引必须与K线的datetime对齐
        2. 列名应为指标名（如 "sma_10", "ema_20"）

        注意事项：
        1. 更新数据追踪字段：_last_updated_at 和 _update_count

        :param indicators: 指标DataFrame，行数应等于或小于当前K线数
        :raises ValueError: 如果索引不匹配
        """
        # 验证索引
        if len(indicators) > len(self._df):
            raise ValueError("Indicators DataFrame has more rows than K-line data")

        # 合并指标数据
        for col in indicators.columns:
            self._df[col] = indicators[col]

        # 更新数据追踪字段
        self._last_updated_at = pd.Timestamp.now()

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

        :param current_time: 当前时间，视图将只包含<=此时间的数据
        :param lookback_bars: 需要的历史K线数，从current_time往前数，默认1根
        :param events_df: 事件DataFrame（由DataFeed传入）
        :return: PeriodDataView只读逻辑视图对象
        :raises ValueError: 如果current_time晚于最新数据时间，或lookback_bars <= 0
        """
        if lookback_bars <= 0:
            raise ValueError("lookback_bars must be positive")

        current_time_ts: pd.Timestamp = pd.Timestamp(current_time)  # type: ignore[assignment]

        # 检查时间是否有效
        if len(self._df) == 0:
            raise ValueError("No data available")

        assert self.latest_time is not None  # 上一步已确保有数据
        if current_time_ts > self.latest_time:
            raise ValueError(f"current_time {current_time_ts} is after latest data time {self.latest_time}")

        # 找到截止时间对应的索引
        end_idx = self._df.index.get_indexer(pd.Index([current_time_ts]), method="ffill")[0]
        if end_idx < 0:
            end_idx = 0

        # 计算起始索引
        start_idx = max(0, end_idx - lookback_bars + 1)

        return PeriodDataView(
            df_ref=self._df,
            events_ref=events_df,
            start_idx=start_idx,
            end_idx=end_idx,
            current_time=current_time_ts,
            period=self.period,
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
            row = self._df.iloc[idx]
            row_name = cast(pd.Timestamp, row.name)
            return Bar(
                symbol="",  # 单个周期不保存symbol，由DataFeed管理
                datetime=row_name.to_pydatetime(),
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
            )
        except IndexError:
            return None

    def get_bar_by_time(self, time: pd.Timestamp | dt) -> Bar | None:
        """通过精确时间戳获取K线

        :param time: 要查找的时间戳
        :return: 匹配的Bar对象，未找到返回None
        """
        time_ts = pd.Timestamp(time)
        if time_ts not in self._df.index:
            return None

        row = self._df.loc[time_ts]
        row_name = cast(pd.Timestamp, row.name)
        return Bar(
            symbol="",
            datetime=row_name.to_pydatetime(),
            open=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
            volume=row["volume"],
        )

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

    # --- 指标计算状态管理方法 ---

    def load_df_parquet(self, df: pd.DataFrame, indicator_columns: list[str]) -> None:
        """从 parquet 加载 DataFrame 并批量标记已计算指标

        专为 DataFeed.from_feeds 设计，一行完成数据加载 + 指标状态恢复。
        load_df(replace=True) 会清空已有数据和指标标记，然后逐个恢复。

        :param df: 含 index=datetime、columns=OHLCV+indicators 的 DataFrame
        :param indicator_columns: 需标记为已计算的指标列名列表
        """
        self.load_df(df, replace=True)
        last_idx = len(self._df) - 1
        for col in indicator_columns:
            if col in self._df.columns:
                self.mark_indicator_calculated(col, last_idx)

    def is_indicator_calculated(self, name: str) -> bool:
        """检查指标是否已计算

        :param name: 指标列名（如 "sma_10"）
        :return: 是否已计算
        """
        return name in self._calculated_indicators

    def get_indicator_last_calc_idx(self, name: str) -> int | None:
        """获取指标最后计算到的行索引

        :param name: 指标列名
        :return: 最后计算到的行索引，None表示未计算过
        """
        return self._indicator_last_calc_idx.get(name)

    def mark_indicator_calculated(self, name: str, last_idx: int | None = None) -> None:
        """标记指标已计算

        :param name: 指标列名
        :param last_idx: 最后计算到的行索引，None表示计算到当前末尾
        """
        self._calculated_indicators.add(name)
        if last_idx is not None:
            self._indicator_last_calc_idx[name] = last_idx
        else:
            self._indicator_last_calc_idx[name] = len(self._df) - 1

    def clear_indicator_calculation(self, name: str | None = None) -> None:
        """清除指标计算状态

        :param name: 指标列名，None表示清除所有
        """
        if name is None:
            self._calculated_indicators.clear()
            self._indicator_last_calc_idx.clear()
        else:
            self._calculated_indicators.discard(name)
            self._indicator_last_calc_idx.pop(name, None)

    def apply_indicator(self, func: Callable[..., pd.Series], **params: Any) -> pd.Series:
        """对内部数据应用指标计算函数

        封装对 self._df 的访问，外部调用者无需直接操作 _df。

        :param func: 指标计算函数，签名 func(df: pd.DataFrame, **params) -> pd.Series
        :param params: 指标参数
        :return: 计算结果 Series
        """
        return func(self._df, **params)

    def set_indicator_column(self, name: str, series: pd.Series) -> None:
        """将指标计算结果写入内部存储

        封装对 self._df[name] = series 的访问，外部无需直接操作 _df。

        :param name: 指标列名（如 "sma_10"）
        :param series: 指标计算结果 Series
        """
        self._df[name] = series


class PeriodDataView:
    """只读逻辑视图

    【设计目标】
    - 只读逻辑视图，防止策略修改数据
    - 只包含截止指定时间点和指定历史K线范围的数据
    - 不受后续数据更新影响（Append-Only 保证）
    - 高效实现：通过索引范围访问原始数据，不复制数据
    - 纯只读，不触发任何计算
    """

    def __init__(
        self,
        df_ref: pd.DataFrame,
        events_ref: pd.DataFrame | None,
        start_idx: int,
        end_idx: int,
        current_time: pd.Timestamp,
        period: str,
    ):
        """初始化逻辑视图（内部使用，不应直接构造）

        :param df_ref: 原始K线+指标DataFrame的引用（不复制）
        :param events_ref: 原始事件DataFrame的引用（不复制）
        :param start_idx: 视图的起始索引（包含）
        :param end_idx: 视图的结束索引（包含）
        :param current_time: 视图的截止时间
        :param period: 周期名称
        """
        self._df_ref = df_ref
        self._events_ref = events_ref
        self._start_idx = start_idx
        self._end_idx = end_idx
        self._current_time = current_time
        self._period = period

    @property
    def current_time(self) -> pd.Timestamp:
        """获取视图的截止时间"""
        return self._current_time

    @property
    def length(self) -> int:
        """获取视图中K线数量"""
        return self._end_idx - self._start_idx + 1

    @property
    def period(self) -> str:
        """获取周期名称"""
        return self._period

    def get_bar(self, idx: int = -1) -> Bar | None:
        """通过索引获取K线（索引相对于视图）

        :param idx: 索引位置，支持负索引（相对于视图）
        :return: Bar对象，索引越界返回None
        """
        # 转换为相对于原始DataFrame的索引
        real_idx = self._start_idx + idx if idx >= 0 else self._end_idx + idx + 1

        if real_idx < self._start_idx or real_idx > self._end_idx:
            return None

        try:
            row = self._df_ref.iloc[real_idx]
            row_name = cast(pd.Timestamp, row.name)
            return Bar(
                symbol="",
                datetime=row_name.to_pydatetime(),
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
            )
        except IndexError:
            return None

    def get_indicator(self, name: str, idx: int = -1) -> float | None:
        """通过索引获取指标值（索引相对于视图）
        注意：此方法不触发计算，指标不存在返回 None

        :param name: 指标名称，如 "sma_10"
        :param idx: 索引位置，支持负索引（相对于视图）
        :return: 指标值，索引越界或指标不存在返回None
        """
        if name not in self._df_ref.columns:
            return None

        # 转换为相对于原始DataFrame的索引
        real_idx = self._start_idx + idx if idx >= 0 else self._end_idx + idx + 1

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
        view_start = self._df_ref.index[self._start_idx]
        view_end = self._df_ref.index[self._end_idx]

        # 筛选时间范围内的事件
        mask = (self._events_ref.index >= view_start) & (self._events_ref.index <= view_end)
        events_df = self._events_ref[mask]

        # 转换回Event对象
        events = []
        for _, row in events_df.iterrows():
            row_name = cast(pd.Timestamp, row.name)
            event = Event(
                timestamp=row_name.to_pydatetime(),
                type=row["type"],
                symbol=row["symbol"],
                reason=row.get("reason", ""),
                period=row.get("period"),
                data=row.get("data"),
            )
            events.append(event)

        return events

    def get_all_bars(self) -> pd.DataFrame:
        """获取视图中所有K线+指标DataFrame（只读视图，不复制）"""
        return cast(pd.DataFrame, self._df_ref.iloc[self._start_idx : self._end_idx + 1].copy())

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
        """便捷方法：获取指标序列"""
        if name not in self._df_ref.columns:
            raise KeyError(f"Indicator {name} not found")
        return self._df_ref[name].iloc[self._start_idx : self._end_idx + 1].copy()

    def events(self) -> list[Event]:
        """便捷方法：获取事件列表"""
        return self.get_events()
