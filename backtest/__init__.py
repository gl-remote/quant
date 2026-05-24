# -*- coding: utf-8 -*-
"""
回测模块

提供两套职责清晰的回测引擎:
  - TQBacktestEngine:   单标的图形化回测 (配合天勤 TqSdk GUI)
  - VnpyBacktestEngine: 批量回测流水线 (基于 vnpy_ctastrategy.backtesting)
  - TradeRecord / BacktestResult: 交易记录与结果数据结构
  - walk_forward_split / scan_csv_files / generate_merged_report: 工具函数
"""

from .backtest_engine import (
    VnpyBacktestEngine,
    TQBacktestEngine,
    BacktestResult,
    TradeRecord,
)
from .data_loader import walk_forward_split, walk_forward_split_by_ratio, scan_csv_files
from .comparison import generate_merged_report

__all__ = [
    'VnpyBacktestEngine',
    'TQBacktestEngine',
    'BacktestResult',
    'TradeRecord',
    'walk_forward_split',
    'walk_forward_split_by_ratio',
    'scan_csv_files',
    'generate_merged_report',
]