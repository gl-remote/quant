"""标准化数据类型 — 框架无关，贯穿 Strategy ↔ Bridge 的通信协议

Strategy 产生决策 (Signal)，Bridge 转换为框架指令。
Bridge 接收行情 (Bar)，喂给 Strategy 产生信号。
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List


@dataclass
class Bar:
    """标准化K线数据 — 框架无关

    所有 Bridge 将自身框架的原始数据转换为此格式后再传给 Strategy，
    Strategy 因此无需感知 vnpy BarData / tqsdk kline_serial 等异构格式。
    """
    symbol: str = ""
    datetime: str = ""
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0


@dataclass
class Signal:
    """策略产生的完整交易决策

    Strategy.on_bar() 返回此对象，Bridge 据此执行或转发。
    volume 由策略预计算，Bridge 只需执行，不做数量决策。
    """
    action: str = ""        # 'buy' | 'sell' | ''
    reason: str = ""        # 'golden_cross' | 'stop_loss' | 'take_profit' | ...
    volume: int = 0         # 策略预计算的开仓手数


@dataclass
class Position:
    """持仓快照"""
    direction: str = ""        # 'long' | ''
    entry_price: float = 0.0
    volume: int = 0


@dataclass
class Fill:
    """订单成交记录 — Bridge 通知 Strategy 的成交回执"""
    timestamp: str = ""
    symbol: str = ""
    action: str = ""        # 'buy' | 'sell'
    price: float = 0.0
    volume: int = 0
    reason: str = ""        # 触发原因


@dataclass
class Performance:
    """策略绩效统计"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_profit: float = 0.0
