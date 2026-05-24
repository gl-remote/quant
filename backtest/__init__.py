# -*- coding: utf-8 -*-
"""
回测模块

提供两套职责清晰的回测引擎:
  - TQBacktestEngine:   单标的图形化回测 (配合天勤 TqSdk GUI)
  - VnpyBacktestEngine: 批量回测流水线 (基于 vnpy_ctastrategy.backtesting)
  - TradeRecord / BacktestResult: 交易记录与结果数据结构
  - walk_forward_split / scan_csv_files: 数据加载工具

注意: 报告生成已迁移至顶层 report/ 包 (sql_reporter.py)，
     所有报告调用统一通过 main.py cmd_report 命令调度。
     纯函数工具 (metrics/stats/formatting) 已提取至 common/ 模块。
"""

from .types import TradeRecord, BacktestResult
from .tq_backtest_engine import TQBacktestEngine
from .vnpy_backtest_engine import VnpyBacktestEngine
from .data_loader import walk_forward_split, walk_forward_split_by_ratio, scan_csv_files, filter_dataframe_by_date

# 向后兼容 re-export: 纯函数工具已移入 common/
from common.metrics import calc_max_drawdown, calc_sharpe_ratio

__all__ = [
    'VnpyBacktestEngine',
    'TQBacktestEngine',
    'TradeRecord',
    'BacktestResult',
    'walk_forward_split',
    'walk_forward_split_by_ratio',
    'scan_csv_files',
    'filter_dataframe_by_date',
    'calc_max_drawdown',       # re-export from common.metrics
    'calc_sharpe_ratio',       # re-export from common.metrics
]
