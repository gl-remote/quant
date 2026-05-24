"""交易上下文 - 统一管理策略运行所需的所有参数

从 cmd 层构建，贯穿 bridge → engine → strategy 的完整调用链，
替代散落在各层的独立参数传递。
"""

from dataclasses import dataclass, field
from typing import Dict, Optional

from .base import Strategy


@dataclass
class TradingContext:
    """统一交易上下文

    捆绑策略实例、品种信息、交易参数、回测引擎参数和账户信息，
    在各模块间统一传递，消除参数散落问题。

    Attributes:
        strategy: 策略实例 (实现 Strategy 接口)
        symbol: 品种代码
        capital: 初始资金
        kline_period: K线周期 (分钟)
        commission_rate: 手续费率
        slippage: 滑点
        price_tick: 最小价格变动
        contract_size: 合约乘数
        account: 账户信息 (实盘/模拟交易用)
    """

    strategy: Strategy
    symbol: str = ""
    capital: float = 100000.0
    kline_period: int = 5
    commission_rate: float = 0.0003
    slippage: float = 1.0
    price_tick: float = 1.0
    contract_size: int = 10
    account: Optional[Dict[str, str]] = None