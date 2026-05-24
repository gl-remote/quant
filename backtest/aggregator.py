# -*- coding: utf-8 -*-
"""纯函数聚合工具

无副作用、无 I/O 的统计汇总与排名函数，供 comparison_reporter 和
vnpy_backtest_engine.py Walk-Forward 聚合复用。
"""

from __future__ import annotations

from typing import TypedDict, cast

import numpy as np

from common.formatting import parse_percentage  # noqa: F401 — re-export for backcompat


# ── 类型 ─────────────────────────────────────────────────

class SymbolMetricItem(TypedDict):
    """{symbol, metrics: {key: value}} — 回测结果中的单品种聚合条目"""
    symbol: str
    metrics: dict[str, object]


class RankPair(TypedDict):
    """rank_by_key 返回的 {symbol, value} 排名条目"""
    symbol: str
    value: float


# ── 排名 (backtest 专用: 操作 {symbol, metrics: {}} 结构) ─

def _sortable(metrics: dict[str, object], key: str) -> float:
    """提取排序键。调用方已通过 filter 确保 key 值非 None。
    
    float() 转换在运行时安全：所有值均为数值类型（float/int）。
    """
    return float(metrics[key])  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]


def rank_by_key(
    items: list[SymbolMetricItem],
    key: str,
    reverse: bool = True,
) -> list[RankPair]:
    """从嵌套结构中提取指定指标并按值排名

    与 common.stats.rank_by_key 不同:
      - 输入要求 {symbol, metrics: {key: value}} 嵌套结构
      - 返回瘦身后的 {symbol, value} 对（丢弃其他指标字段）
      - 跳过 key 值为 None 的条目，metrics 缺失时安全跳过
    """
    # 过滤: 跳过 metrics 缺失或 key 值为 None 的项
    # 用 .get('metrics', {}) 代替 [] → 防 KeyError
    valid: list[SymbolMetricItem] = [
        it for it in items
        if it.get('metrics', {}).get(key) is not None
    ]
    # 排序: 所有条目已确保 key 存在且非 None
    sorted_items = sorted(
        valid,
        key=lambda it: _sortable(it['metrics'], key),  # type: ignore
        reverse=reverse,
    )
    return [
        RankPair(symbol=it['symbol'], value=cast(float, it['metrics'][key]))
        for it in sorted_items
    ]


# ── Walk-Forward 聚合 ────────────────────────────────────

def aggregate_walk_forward(window_results: list[dict[str, object]]) -> dict[str, float]:
    """聚合 Walk-Forward 所有窗口的测试集指标

    从各窗口的 statistics 中提取收益率/夏普/回撤/胜率，
    计算均值和标准差，输出稳定性评分。

    Args:
        window_results: [{statistics: {total_return, sharpe_ratio, max_drawdown, win_rate}}, ...]

    Returns:
        {return_mean, return_std, sharpe_mean, sharpe_std,
         max_drawdown_mean, max_drawdown_worst,
         win_rate_mean, win_rate_std,
         positive_window_ratio, stability_score}
    """
    returns: list[float] = []
    sharpes: list[float] = []
    drawdowns: list[float] = []
    win_rates: list[float] = []

    for wr in window_results:
        stats = wr.get('statistics', {})
        returns.append(parse_percentage(stats.get('total_return', 0)))
        sharpes.append(float(stats.get('sharpe_ratio', 0)))
        drawdowns.append(parse_percentage(stats.get('max_drawdown', 0)))
        win_rates.append(parse_percentage(stats.get('win_rate', 0)))

    arr_returns = np.array(returns, dtype=float)

    return {
        'return_mean': float(np.mean(arr_returns)),
        'return_std': float(np.std(arr_returns)),
        'sharpe_mean': float(np.mean(sharpes)),
        'sharpe_std': float(np.std(sharpes)),
        'max_drawdown_mean': float(np.mean(drawdowns)),
        'max_drawdown_worst': float(np.max(drawdowns)),
        'win_rate_mean': float(np.mean(win_rates)),
        'win_rate_std': float(np.std(win_rates)),
        'positive_window_ratio': float(np.sum(arr_returns > 0) / len(arr_returns)),
        'stability_score': float(max(0.0, min(1.0,
            1.0 - float(np.std(arr_returns)) / max(abs(float(np.mean(arr_returns))), 1e-9)
        ))),
    }
