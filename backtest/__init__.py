# -*- coding: utf-8 -*-
"""
回测模块

提供批量回测流水线:
  - VnpyBacktestEngine: 批量回测引擎 (纯执行器)
  - walk_forward_split / walk_forward_split_by_ratio: Walk-Forward 窗口划分
  - runners: 批量回测编排器 (数据加载、Walk-Forward、参数搜索编排)
  - optimizer: 参数优化引擎 (Optuna 网格/贝叶斯搜索)

注意: 单标的 TQ 回测已由 cli/commands/backtest.py:_run_tq_backtest 直接实现。
     报告生成已迁移至顶层 report/ 包。
     纯函数工具 (metrics/stats/formatting) 已提取至 common/ 模块。
     CSV 扫描/加载已迁移至 data/manager.py (DataManager)。
"""

from .vnpy_backtest_engine import VnpyBacktestEngine
from .walk_forward import walk_forward_split, walk_forward_split_by_ratio
from .runners import load_batch_datasets, execute_walk_forward, execute_parameter_search
from .optimizer import run_param_search, OptunaOptimizer, OptunaResult, SearchResult

__all__ = [
    'VnpyBacktestEngine',
    'walk_forward_split',
    'walk_forward_split_by_ratio',
    'load_batch_datasets',
    'execute_walk_forward',
    'execute_parameter_search',
    'run_param_search',
    'OptunaOptimizer',
    'OptunaResult',
    'SearchResult',
]
