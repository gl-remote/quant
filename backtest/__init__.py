# -*- coding: utf-8 -*-
"""
回测模块

基于 vn.py 框架的回测引擎，提供:
  - VnpyBacktestEngine: 主回测引擎 (CSV数据加载、划分、三阶段回测、报告对比)
  - BacktestEngine: 原始回测引擎 (vn.py 不可用时的降级方案)
  - TradeRecord / BacktestResult: 交易记录与结果数据结构
"""

from .backtest_engine import (
    VnpyBacktestEngine,
    BacktestEngine,
    BacktestResult,
    TradeRecord,
)

__all__ = [
    'VnpyBacktestEngine',
    'BacktestEngine',
    'BacktestResult',
    'TradeRecord',
]