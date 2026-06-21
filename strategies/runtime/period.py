"""单个周期的数据容器与只读逻辑视图

包含：
- PeriodData: 单个周期的数据容器，管理K线和指标
- PeriodDataView: 只读逻辑视图，不复制数据，按时间和历史条数裁剪
"""

from datetime import datetime as dt
from typing import cast

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from ..core.indicators import IndicatorSpec
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

        self._df: pd.DataFrame = pd.DataFrame(
            columns=["open", "high", "low", "close", "volume"],
            dtype="float64",
        )
        self._df.index.name = "datetime"

        # 已注册的指标列表
        self._registered_indicators: list[IndicatorSpec] = []

        # 游标：记录上一次 get_data 找到的索引，避免重复二分查找
        # -1 表示尚未查找；回测时严格顺序推进，每次 O(1)
        self._cursor: int = -1

        # append_bar 缓冲：减少 pd.concat 频次
        self._bar_buffer: list[pd.DataFrame] = []
        self._buffered_times: set[pd.Timestamp] = set()

    def flush(self) -> None:
        """将 _bar_buffer 中的数据批量 flush 到 _df"""
        if not self._bar_buffer:
            return
        batch = pd.concat(self._bar_buffer, ignore_index=False)
        self._df = pd.concat([self._df, batch], ignore_index=False)
        self._bar_buffer.clear()
        self._buffered_times.clear()

    @property
    def first_time(self) -> pd.Timestamp | None:
        """获取最早数据时间戳"""
        self.flush()
        if len(self._df) == 0:
            return None
        return cast(pd.Timestamp, self._df.index[0])

    @property
    def latest_time(self) -> pd.Timestamp | None:
        """获取最新数据时间戳"""
        self.flush()
        if len(self._df) == 0:
            return None
        return cast(pd.Timestamp, self._df.index[-1])

    @property
    def length(self) -> int:
        """获取当前数据长度（K线数量）"""
        self.flush()
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

        self.flush()

        if len(self._df) > 0:
            last_time = self._df.index[-1]
            first_new_time = new_df.index[0]
            if first_new_time <= last_time:
                raise ValueError(f"New data time {first_new_time} is not after existing last time {last_time}")

        if len(self._df) == 0:
            self._df = new_df.copy()
        else:
            self._df = pd.concat([self._df, new_df], ignore_index=False)

    def append_bar(self, bar: Bar) -> None:
        """追加单根K线

        若 bar 时间已存在则静默忽略（DataFeed 初始数据加载与实时推送可能重叠）。

        :param bar: 单根K线数据
        """
        bar_time = pd.Timestamp(bar.datetime)
        # 检查 _df + buffer 双重去重（不 flush buffer 以保证 append_bar 的 O(1) 摊销）
        if bar_time in self._df.index or bar_time in self._buffered_times:
            return

        row = pd.DataFrame(
            {"open": [bar.open], "high": [bar.high], "low": [bar.low], "close": [bar.close], "volume": [bar.volume]},
            index=pd.Index([bar_time], name="datetime"),
        )
        self._bar_buffer.append(row)
        self._buffered_times.add(bar_time)
        if len(self._bar_buffer) >= 100:
            self.flush()

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
            self._cursor = -1
            self._bar_buffer.clear()
            self._buffered_times.clear()
        else:
            self._append_df(df)

    def register_indicator(self, spec: IndicatorSpec) -> None:
        """注册需要计算的指标

        :param spec: IndicatorSpec 指标定义对象
        """
        for i, existing in enumerate(self._registered_indicators):
            if existing.name == spec.name and existing.params == spec.params:
                # 已存在的同名指标可能 func=None（来自磁盘反序列化），
                # 用新注册的完整 IndicatorSpec（含 func）替换
                if spec.func is not None and existing.func is None:
                    self._registered_indicators[i] = spec
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

    def get_data(
        self,
        current_time: pd.Timestamp | dt,
        lookback_bars: int = 1,
        events_df: pd.DataFrame | None = None,
        base_df_ref: pd.DataFrame | None = None,
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
        :param base_df_ref: 基础周期的 _df 引用（指标写回目标）
        :return: PeriodDataView只读逻辑视图对象
        :raises ValueError: 如果current_time晚于最新数据时间，或lookback_bars <= 0
        """
        if lookback_bars <= 0:
            raise ValueError("lookback_bars must be positive")

        self.flush()

        current_time_ts: pd.Timestamp = pd.Timestamp(current_time)  # type: ignore[assignment]

        latest = self.latest_time
        if latest is not None and current_time_ts > latest:
            raise ValueError(f"current_time {current_time_ts} is after latest data time {latest}")

        # 游标快速路径：回测严格顺序推进，每次 O(1)
        # 只有当 cursor + 1 的时间正好匹配时才走快速路径
        if self._cursor >= 0 and self._cursor + 1 < len(self._df):
            if self._df.index[self._cursor + 1] == current_time_ts:
                self._cursor += 1
                end_idx = self._cursor
            else:
                end_idx = self._df.index.get_indexer(pd.Index([current_time_ts]), method="ffill")[0]
                self._cursor = end_idx
        elif len(self._df) > 0:
            end_idx = self._df.index.get_indexer(pd.Index([current_time_ts]), method="ffill")[0]
            self._cursor = end_idx
        else:
            end_idx = -1

        # 计算起始索引
        start_idx = max(0, end_idx - lookback_bars + 1) if end_idx >= 0 else 0

        return PeriodDataView(
            df_ref=self._df,
            events_ref=events_df,
            start_idx=start_idx,
            end_idx=end_idx,
            current_time=current_time_ts,
            period=self.period,
            forming_bar=None,
            forming_indicators=None,
            base_df_ref=base_df_ref,
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
        base_df_ref: pd.DataFrame | None = None,
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
        :param base_df_ref: 基础周期的 _df 引用（所有周期的指标统一写回此处）
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
        self._base_df_ref = base_df_ref

    @property
    def current_time(self) -> pd.Timestamp:
        """获取视图的截止时间"""
        return self._current_time

    @property
    def start_idx(self) -> int:
        """视图起始索引（相对于 _df）"""
        return self._start_idx

    @property
    def end_idx(self) -> int:
        """视图结束索引（相对于 _df），-1 表示无数据"""
        return self._end_idx

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

        :param name: 指标名称，如 "sma_10"（已含周期前缀，由调用方生成）
        :param idx: 索引位置，支持负索引（相对于视图）
        :return: 指标值，索引越界或指标不存在返回None
        """
        # 仅在 idx=-1（最近值）时优先从缓存取，避免缓存值与请求索引不一致
        if idx == -1 and name in self._indicator_cache:
            return self._indicator_cache[name]

        pos_idx = self._resolve_idx(idx)
        if pos_idx is None:
            return None

        # forming bar 的指标从 _forming_indicators 取
        if self._forming_bar is not None and pos_idx == self._df_count:
            return self._forming_indicators.get(name)

        # 从 _base_df_ref 或 _df_ref 中取指标（列名已含周期前缀，直接匹配）
        target_df: pd.DataFrame | None = None
        if self._base_df_ref is not None and name in self._base_df_ref.columns:
            target_df = self._base_df_ref
        elif name in self._df_ref.columns:
            target_df = self._df_ref

        if target_df is None:
            return None

        real_idx = self._start_idx + pos_idx
        if real_idx < self._start_idx or real_idx > self._end_idx:
            return None

        try:
            return float(target_df[name].iloc[real_idx])
        except IndexError:
            return None

    def get_events(self) -> list[Event]:
        """获取视图时间范围内的所有事件"""
        if self._events_ref is None or len(self._events_ref) == 0:
            return []

        forming_bar_time = pd.Timestamp(self._forming_bar.datetime) if self._forming_bar is not None else None

        # 获取视图时间范围
        if self._df_count > 0 and len(self._df_ref) > 0:
            view_start = self._df_ref.index[self._start_idx]
            view_end = self._df_ref.index[self._end_idx]
        elif forming_bar_time is not None:
            view_start = forming_bar_time
            view_end = forming_bar_time
        else:
            return []

        if forming_bar_time is not None and forming_bar_time > view_end:
            view_end = forming_bar_time

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

    # --- 指标计算支持 ─────────────────────────────────

    def to_calculation_df(self) -> pd.DataFrame:
        """构建指标计算用的 DataFrame（视图切片 + forming bar）

        forming bar 以 current_time 为索引，避免与 PeriodData 中同周期的完整 bar 冲突。
        例如 15m 视图在 10:05：PeriodData 有完整的 10:00 bar，forming bar 索引为 10:05。
        """
        if self._df_count > 0:
            df = self._df_ref.iloc[self._start_idx : self._end_idx + 1].copy()
        else:
            df = pd.DataFrame(columns=self._df_ref.columns, dtype="float64")

        if self._forming_bar is not None:
            forming_row = _forming_bar_to_series(self._forming_bar)
            forming_row.name = self._current_time
            df = pd.concat([df, forming_row.to_frame().T])

        return df

    def set_cached_indicator(self, col_name: str, value: float) -> None:
        """设置指标缓存值"""
        self._indicator_cache[col_name] = value

    def write_indicator_result(self, col_name: str, result_series: pd.Series) -> None:
        """将指标计算结果写回基础周期 DataFrame

        高周期视图会将最新值额外写入当前时间戳。
        """
        if self._base_df_ref is None:
            return
        non_nan = result_series.notna()
        if non_nan.any():
            self._base_df_ref.loc[result_series.index[non_nan], col_name] = result_series[non_nan]

        if self._df_ref is not self._base_df_ref:
            last_val = result_series.iloc[-1]
            if not pd.isna(last_val):
                self._base_df_ref.loc[self._current_time, col_name] = float(last_val)

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
