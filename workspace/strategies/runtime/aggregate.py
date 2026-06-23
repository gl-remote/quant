"""周期聚合模块 — 从基础周期数据聚合出高周期 K 线

核心原则：
- 基础周期是声明的最小周期，所有高周期都由它聚合得到
- 最后一根是"形成中"的 bar（每来一根 source bar 就更新），前面全是已完成的 bar
- 天然防 look-ahead：10:34 时 1h bar 的 close 就是 10:34 的 close
"""

import re

import pandas as pd

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
    """解析周期名称为分钟数（供内部调用）

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


def bar_start_time(ts: pd.Timestamp, period_minutes: int) -> pd.Timestamp:
    """计算时间戳所属的高周期 bar 起始时间

    例如：10:34 属于 1h 周期 → 起始时间为 10:00
         10:34 属于 5m 周期 → 起始时间为 10:30

    :param ts: 源周期 K 线时间戳
    :param period_minutes: 高周期分钟数
    :return: 高周期 bar 的起始时间
    """
    # 转为当天零点后的分钟数
    minutes_since_midnight = ts.hour * 60 + ts.minute
    bar_start_minutes = (minutes_since_midnight // period_minutes) * period_minutes
    return ts.normalize() + pd.Timedelta(minutes=bar_start_minutes)
