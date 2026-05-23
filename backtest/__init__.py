# -*- coding: utf-8 -*-
"""
回测模块

提供回测引擎和绩效分析功能。
"""

from .backtest_engine import BacktestEngine, BacktestResult

__all__ = ['BacktestEngine', 'BacktestResult']
