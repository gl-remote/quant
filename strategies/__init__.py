# -*- coding: utf-8 -*-
"""
策略模块

架构: Strategy (大脑) + Bridge (四肢)
  - core/            Strategy ABC + Bar/Signal/Fill 标准化类型
  - ma_strategy.py   均线交叉策略 (继承 Strategy，自主管理全部状态)
  - bridges/         框架桥接器 (vnpy / tqsdk，纯协议转换)

使用方式:
  from strategies import MaStrategyCore          # 策略核心
  from strategies import VnpyStrategyBridge       # vn.py 桥接器
  from strategies import TqsdkStrategyBridge      # 天勤桥接器
  from strategies.core import Strategy, Bar, Signal  # 基类 + 数据类型
"""

__version__ = "0.2.0-dev"

from .ma_strategy import MaStrategyCore, TradingConfig
from .core import Strategy, Bar, Signal, Fill, StrategyPosition, Performance, TradingContext

try:
    from .bridges import VnpyStrategyBridge
except ImportError:
    VnpyStrategyBridge = None

try:
    from .bridges import TqsdkStrategyBridge
except ImportError:
    TqsdkStrategyBridge = None

__all__ = [
    'Strategy', 'MaStrategyCore', 'TradingConfig',
    'Bar', 'Signal', 'Fill', 'StrategyPosition', 'Performance',
    'VnpyStrategyBridge', 'TqsdkStrategyBridge', 'TradingContext',
]
