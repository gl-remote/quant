# -*- coding: utf-8 -*-
"""
回测数据结构

TradeRecord / BacktestResult 是 TQBacktestEngine 和 VnpyBacktestEngine
共用的数据类，从 backtest_engine.py 中提取到此独立模块，避免循环依赖。
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class TradeRecord:
    """交易记录"""
    timestamp: datetime
    symbol: str
    direction: str
    price: float
    quantity: int
    profit: float = 0.0
    reason: str = ""


@dataclass
class BacktestResult:
    """回测结果"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_profit: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    avg_profit: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    final_equity: float = 0.0
