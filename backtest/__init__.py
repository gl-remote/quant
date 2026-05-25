# -*- coding: utf-8 -*-
"""
回测模块

提供批量回测流水线:
  - VnpyBacktestEngine: 批量回测流水线 (基于 vnpy_ctastrategy.backtesting)
  - walk_forward_split / walk_forward_split_by_ratio: Walk-Forward 窗口划分

注意: 单标的 TQ 回测已由 cli/commands/backtest.py:_run_tq_backtest 直接实现。
     报告生成已迁移至顶层 report/ 包。
     纯函数工具 (metrics/stats/formatting) 已提取至 common/ 模块。
     CSV 扫描/加载已迁移至 data/manager.py (DataManager)。
"""

from .vnpy_backtest_engine import VnpyBacktestEngine
from .walk_forward import walk_forward_split, walk_forward_split_by_ratio, filter_dataframe_by_date

__all__ = [
    'VnpyBacktestEngine',
    'walk_forward_split',
    'walk_forward_split_by_ratio',
    'filter_dataframe_by_date',
]
