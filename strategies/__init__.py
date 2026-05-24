# -*- coding: utf-8 -*-
"""
策略模块

统一策略目录，采用 "核心逻辑 + 桥接器" 架构:
  - core/            策略基类接口 (Strategy ABC) 和 TradingContext
  - ma_strategy.py   均线交叉策略 (顶层，供 --strategy 参数发现)
  - bridges/         框架桥接器 (vnpy / tqsdk)

vn.py 和 tqsdk 为强制依赖，仅在包导入层面做 try/except 以支持测试隔离。

使用方式:
  from strategies import MaStrategyCore          # 均线交叉策略核心
  from strategies import VnpyStrategyBridge       # vn.py 回测桥接器
  from strategies import TqsdkStrategyBridge      # 天勤实盘/模拟桥接器
  from strategies.core import Strategy           # 策略基类接口
"""

from .ma_strategy import MaStrategyCore, TradingConfig, StrategyState
from .core import Strategy, PositionStatus, TradeRecord, TradingContext

try:
    from .bridges import VnpyStrategyBridge
except ImportError:
    VnpyStrategyBridge = None

try:
    from .bridges import TqsdkStrategyBridge
except ImportError:
    TqsdkStrategyBridge = None

MovingAverageStrategy = TqsdkStrategyBridge

__all__ = [
    'Strategy',
    'MaStrategyCore',
    'VnpyStrategyBridge',
    'TqsdkStrategyBridge',
    'MovingAverageStrategy',
    'TradingConfig',
    'StrategyState',
    'TradeRecord',
    'PositionStatus',
    'TradingContext',
]
