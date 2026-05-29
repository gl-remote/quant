"""
通用类型别名 — 全项目共享的类型定义

本文件遵循 common/ 零依赖原则：纯类型定义，不 import 任何业务模块。
所有类型别名仅供静态类型检查使用，零运行时开销。

使用方式:
    from common.types import TradeAction, PositionDirection

    signal = Signal(action='buy')  # type checker validates 'buy' | 'sell' | ''

单一事实来源：全项目（core、strategies、bridges）共享同一组 Literal 类型。
与 common/constants.py 中同名运行时常量同源，修改时同步更新。
"""

from typing import Literal

TradeAction = Literal['buy', 'sell', '']
"""交易动作: 'buy' (买入) | 'sell' (卖出) | '' (无操作)"""

PositionDirection = Literal['long', '']
"""持仓方向: 'long' (多头) | '' (空仓)"""