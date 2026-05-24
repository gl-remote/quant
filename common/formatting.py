# -*- coding: utf-8 -*-
"""
安全格式化工具 (纯函数)

供 report (sql_reporter) 和未来可能的实盘/优化模块格式化指标输出。

不依赖任何业务模块。
"""

from __future__ import annotations


def format_pct(value: float | None) -> str:
    """安全格式化百分比

    若 value 绝对值 > 1 (如 15.0 表示 15%)，先归一化。

    Args:
        value: 比值 (e.g. 0.15) 或百分比值 (e.g. 15.0)

    Returns:
        格式化字符串 (e.g. '15.00%') 或 'N/A'
    """
    if value is None:
        return 'N/A'
    v: float = float(value)
    if abs(v) > 1:
        v = v / 100.0
    return f"{v:.2%}"


def format_float(value: float | None, fmt: str = '.2f') -> str:
    """安全格式化浮点数

    Args:
        value: 数值或 None
        fmt: 格式规范 (e.g. '.2f', ',.0f', '.4f')

    Returns:
        格式化字符串或 'N/A'
    """
    if value is None:
        return 'N/A'
    return f"{float(value):{fmt}}"


def ensure_float(v: float | int | str | None, default: float = 0.0) -> float:
    """安全转为 float

    Args:
        v: 数值、字符串或 None
        default: 转换失败时的默认值

    Returns:
        float 值
    """
    if v is None:
        return default
    return float(v)
