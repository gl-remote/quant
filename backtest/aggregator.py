# -*- coding: utf-8 -*-
"""
纯函数聚合工具

无副作用、无 I/O 的统计汇总与排名函数。
compute_summary_stats 来自 lib.stats，其余函数供 comparison.py 和
vnpy_backtest_engine.py Walk-Forward 聚合复用。
"""

from typing import Any

import numpy as np

from lib.stats import compute_summary_stats  # noqa: F401 — re-export


# ── 排名 (backtest 专用: 操作 {symbol, metrics: {}} 结构) ─

def rank_by_key(
    items: list[dict],
    key: str,
    reverse: bool = True,
) -> list[dict]:
    """对背靠 symbols_data 列表按 metrics 内键排序

    与 lib.stats.rank_by_key 不同: 此函数操作 {symbol, metrics: {}} 嵌套结构。

    Args:
        items: 含 'symbol' 和 'metrics' 字段的字典列表
        key: metrics 中的排序键名
        reverse: True=降序(越大越好), False=升序(越小越好)

    Returns:
        [{symbol, value}, ...] 排序后的列表，跳过 key 为 None 的项目
    """
    valid = [it for it in items if it['metrics'].get(key) is not None]
    sorted_items = sorted(
        valid,
        key=lambda it: it['metrics'].get(key, 0),
        reverse=reverse,
    )
    return [{'symbol': it['symbol'], 'value': it['metrics'].get(key, 0)}
            for it in sorted_items]


# ── 百分比字符串解析 ─────────────────────────────────────

def parse_percentage(value: Any) -> float:
    """将百分比字符串或数值统一转为 float 比值

    '15.00%' → 0.15
    0.15     → 0.15
    """
    if isinstance(value, str):
        return float(value.rstrip('%')) / 100.0
    return float(value)


# ── Walk-Forward 聚合 ────────────────────────────────────

def aggregate_walk_forward(window_results: list[dict]) -> dict[str, float]:
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
            1.0 - np.std(arr_returns) / max(abs(np.mean(arr_returns)), 1e-9)
        ))),
    }
