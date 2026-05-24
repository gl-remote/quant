# -*- coding: utf-8 -*-
"""
回测模块

提供两套职责清晰的回测引擎:
  - TQBacktestEngine:   单标的图形化回测 (配合天勤 TqSdk GUI)
  - VnpyBacktestEngine: 批量回测流水线 (基于 vnpy_ctastrategy.backtesting)
  - TradeRecord / BacktestResult: 交易记录与结果数据结构
  - walk_forward_split / scan_csv_files / generate_merged_report: 工具函数
  - calc_max_drawdown / calc_sharpe_ratio: 绩效指标工具
"""

from .types import TradeRecord, BacktestResult
from .tq_backtest_engine import TQBacktestEngine
from .vnpy_backtest_engine import VnpyBacktestEngine
from .data_loader import walk_forward_split, walk_forward_split_by_ratio, scan_csv_files
from .comparison import generate_merged_report
from .metrics import calc_max_drawdown, calc_sharpe_ratio

__all__ = [
    'VnpyBacktestEngine',
    'TQBacktestEngine',
    'TradeRecord',
    'BacktestResult',
    'walk_forward_split',
    'walk_forward_split_by_ratio',
    'scan_csv_files',
    'generate_merged_report',
    'calc_max_drawdown',
    'calc_sharpe_ratio',
]