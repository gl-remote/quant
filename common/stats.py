# -*- coding: utf-8 -*-
"""
统计聚合工具 (纯函数)

compute_summary_stats: 数值列表描述性统计
rank_by_key:          对 flat dict 列表按指定键排序

供 backtest (comparison/aggregator) 和 report (sql_reporter) 共用。
"""

from __future__ import annotations

from typing import TypedDict

import numpy as np


class SummaryStats(TypedDict):
    """compute_summary_stats 的返回值"""
    mean: float
    median: float
    std: float
    min: float
    max: float
    count: int
    positive_count: int
    negative_count: int


class SymbolSummary(TypedDict):
    """单品种聚合指标 — comparison_reporter 中间数据结构

    从 run_full_pipeline 返回的 performance/risk 字段中提取，
    所有值均为数值类型，用于排名、聚合统计和格式化输出。
    """
    symbol: str
    total_return: float
    annual_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_loss_ratio: float
    total_trades: int


def compute_summary_stats(values: list[float]) -> SummaryStats | dict[str, object]:
    """计算数值列表的描述性统计

    Args:
        values: 数值列表

    Returns:
        {mean, median, std, min, max, count, positive_count, negative_count}
        空列表返回空的 SummaryStats 或 {}
    """
    if not values:
        return {}
    arr = np.array(values, dtype=float)
    pos: int = int(np.sum(arr > 0))
    neg: int = int(np.sum(arr < 0))
    return SummaryStats(
        mean=float(np.mean(arr)),
        median=float(np.median(arr)),
        std=float(np.std(arr)),
        min=float(np.min(arr)),
        max=float(np.max(arr)),
        count=len(values),
        positive_count=pos,
        negative_count=neg,
    )


def rank_by_key(
    items: list[dict[str, object]],
    key: str,
    reverse: bool = True,
) -> list[dict[str, object]]:
    """对 flat dict 列表按指定键排序

    与 backtest/aggregator 中的同名函数不同:
      此版本操作 flat dict (it[key] 直接取值)，不要求 metrics 嵌套结构。

    Args:
        items: 字典列表，每项需包含 key 对应的字段
        key: 排序键名
        reverse: True=降序(越大越好), False=升序(越小越好)

    Returns:
        排序后的字典列表 (原对象引用，非拷贝)
    """
    valid: list[dict[str, object]] = [it for it in items if it.get(key) is not None]
    return sorted(valid, key=lambda it: it.get(key, 0), reverse=reverse)  # type: ignore[arg-type,return-value]
