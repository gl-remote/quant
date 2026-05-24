# -*- coding: utf-8 -*-
"""
common — 通用纯函数工具层

零 I/O、零副作用、不依赖业务模块（backtest/report/strategies/data）。
供 backtest、report、live、optimize 等所有上层模块共用。

子模块:
  - metrics:    绩效指标计算 (max_drawdown, sharpe_ratio)
  - stats:      统计聚合工具 (compute_summary_stats, rank_by_key)
  - formatting: 安全格式化 (format_pct, format_float, ensure_float)
"""

from .metrics import calc_max_drawdown, calc_sharpe_ratio
from .stats import compute_summary_stats, rank_by_key
from .formatting import format_pct, format_float, ensure_float

__all__ = [
    'calc_max_drawdown',
    'calc_sharpe_ratio',
    'compute_summary_stats',
    'rank_by_key',
    'format_pct',
    'format_float',
    'ensure_float',
]
