# -*- coding: utf-8 -*-
"""
策略模块

统一策略目录，采用 "核心逻辑 + 网关适配器" 架构:
  - core/            纯业务逻辑 (无框架依赖)
  - gateways/        框架网关适配器 (vnpy / tqsdk)

vn.py 和 tqsdk 为强制依赖，不再支持降级模式。

使用方式:
  from strategies import VnpyMaStrategy    # vn.py 回测策略
  from strategies import TqsdkMaStrategy   # 天勤实盘/模拟策略
  from strategies.core import MaStrategyCore  # 纯算法逻辑
"""

from .core import MaStrategyCore, TradingConfig, StrategyState, TradeRecord, PositionStatus
from .gateways import VnpyMaStrategy, TqsdkMaStrategy

MovingAverageStrategy = TqsdkMaStrategy

__all__ = [
    'MaStrategyCore',
    'VnpyMaStrategy',
    'TqsdkMaStrategy',
    'MovingAverageStrategy',
    'TradingConfig',
    'StrategyState',
    'TradeRecord',
    'PositionStatus',
]