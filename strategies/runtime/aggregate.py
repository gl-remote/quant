"""周期聚合模块 — 从 1m 数据聚合出高周期 K 线

核心原则：
- 只有 1m 是"真实数据"，5m/15m/1h 等全部从 1m 聚合
- 最后一根是"形成中"的 bar（每来一根 1m 就更新），前面全是已完成的 bar
- 天然防 look-ahead：10:34 时 1h bar 的 close 就是 10:34 的 close

提供两类操作：
1. 批量聚合：从 1m DataFrame 一次性生成完整的高周期 DataFrame
2. 增量更新：每来一根 1m bar，更新高周期"形成中"的最后一根 bar
"""

import re

import pandas as pd

from ..core.types import Bar

# 周期名称 → 分钟数映射
_PERIOD_MINUTES: dict[str, int] = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "2h": 120,
    "4h": 240,
    "1d": 1440,
}


def parse_period_minutes(period: str) -> int:
    """解析周期名称为分钟数

    支持格式: "1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"
    未知格式尝试从字符串提取数字+单位。

    :param period: 周期名称
    :return: 分钟数
    :raises ValueError: 无法解析的周期格式
    """
    if period in _PERIOD_MINUTES:
        return _PERIOD_MINUTES[period]

    # 尝试解析 "Nm" / "Nh" / "Nd" 格式
    m = re.match(r"^(\d+)(m|h|d)$", period.lower())
    if m:
        num, unit = int(m.group(1)), m.group(2)
        if unit == "m":
            return num
        elif unit == "h":
            return num * 60
        elif unit == "d":
            return num * 1440

    raise ValueError(f"无法解析周期: {period}")


def _bar_start_time(ts: pd.Timestamp, period_minutes: int) -> pd.Timestamp:
    """计算时间戳所属的高周期 bar 起始时间

    例如：10:34 属于 1h 周期 → 起始时间为 10:00
         10:34 属于 5m 周期 → 起始时间为 10:30

    :param ts: 1m K 线时间戳
    :param period_minutes: 高周期分钟数
    :return: 高周期 bar 的起始时间
    """
    # 转为当天零点后的分钟数
    minutes_since_midnight = ts.hour * 60 + ts.minute
    bar_start_minutes = (minutes_since_midnight // period_minutes) * period_minutes
    return ts.normalize() + pd.Timedelta(minutes=bar_start_minutes)


def aggregate_bars(df_1m: pd.DataFrame, target_period: str) -> pd.DataFrame:
    """从 1m DataFrame 批量聚合出高周期 DataFrame

    聚合规则：
    - open: 该高周期 bar 内第一根 1m 的 open
    - high: 该高周期 bar 内所有 1m 的 high 最大值
    - low: 该高周期 bar 内所有 1m 的 low 最小值
    - close: 该高周期 bar 内最后一根 1m 的 close
    - volume: 该高周期 bar 内所有 1m 的 volume 之和

    注意：最后一根高周期 bar 是"形成中"的，随 1m 数据推进会持续更新。

    :param df_1m: 1m K线 DataFrame，索引为 datetime，包含 OHLCV 列
    :param target_period: 目标周期名称，如 "5m", "15m", "1h"
    :return: 高周期 DataFrame，索引为 bar 起始时间
    """
    if len(df_1m) == 0:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    period_minutes = parse_period_minutes(target_period)

    # 计算每根 1m bar 所属的高周期起始时间
    bar_starts = pd.Series(
        [_bar_start_time(ts, period_minutes) for ts in df_1m.index],
        index=df_1m.index,
    )

    # 按高周期起始时间分组聚合
    grouped = df_1m.groupby(bar_starts)
    result = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    )

    return result


def update_forming_bar(
    current_bar: Bar,
    target_period: str,
    period_df: pd.DataFrame,
) -> pd.DatetimeIndex | None:
    """增量更新高周期"形成中"的最后一根 bar

    当一根新的 1m bar 到达时，判断它属于哪个高周期 bar：
    - 如果属于当前"形成中"的 bar → 更新该 bar 的 high/low/close/volume
    - 如果属于新的高周期 bar → 追加新 bar（当前实现由调用方处理）

    :param current_bar: 新到达的 1m bar
    :param target_period: 目标周期名称
    :param period_df: 高周期 DataFrame（会被原地修改）
    :return: 如果更新了形成中的 bar，返回其索引；否则返回 None
    """
    if len(period_df) == 0:
        return None

    period_minutes = parse_period_minutes(target_period)
    ts = pd.Timestamp(current_bar.datetime)
    bar_start = _bar_start_time(ts, period_minutes)

    # 检查是否属于最后一根（形成中的）bar
    last_idx = period_df.index[-1]
    if bar_start == last_idx:
        # 更新形成中的 bar
        period_df.loc[last_idx, "high"] = max(period_df.loc[last_idx, "high"], current_bar.high)
        period_df.loc[last_idx, "low"] = min(period_df.loc[last_idx, "low"], current_bar.low)
        period_df.loc[last_idx, "close"] = current_bar.close
        period_df.loc[last_idx, "volume"] += current_bar.volume
        return period_df.index[-1:]

    return None


def bar_to_df_row(bar: Bar) -> pd.Series:
    """将 Bar 对象转为 DataFrame 行（用于追加新 bar）

    :param bar: K线数据
    :return: pandas Series，name 为时间戳
    """
    return pd.Series(
        {
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
        },
        name=pd.Timestamp(bar.datetime),
    )


def get_forming_bar_start(current_1m_time: pd.Timestamp, target_period: str) -> pd.Timestamp:
    """获取当前 1m 时间所属的高周期 bar 起始时间

    :param current_1m_time: 当前 1m bar 的时间戳
    :param target_period: 目标周期名称
    :return: 高周期 bar 的起始时间
    """
    period_minutes = parse_period_minutes(target_period)
    return _bar_start_time(current_1m_time, period_minutes)
