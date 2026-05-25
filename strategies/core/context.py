"""交易上下文 - 统一管理策略运行所需的所有参数

从 cmd 层构建，贯穿 bridge → engine → strategy 的完整调用链，
替代散落在各层的独立参数传递。
"""

import dataclasses
from dataclasses import dataclass, field
from typing import Dict, Optional

from .base import Strategy
from common.constants import (
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_COMMISSION_RATE,
    DEFAULT_SLIPPAGE,
    DEFAULT_PRICE_TICK,
    DEFAULT_CONTRACT_SIZE,
    DEFAULT_KLINE_PERIOD,
)


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
    capital: float = DEFAULT_INITIAL_CAPITAL
    kline_period: int = DEFAULT_KLINE_PERIOD
    commission_rate: float = DEFAULT_COMMISSION_RATE
    slippage: float = DEFAULT_SLIPPAGE
    price_tick: float = DEFAULT_PRICE_TICK
    contract_size: int = DEFAULT_CONTRACT_SIZE
    account: Optional[Dict[str, str]] = None

    @classmethod
    def build(cls, strategy: Strategy, symbol: str,
              config_manager, capital: float = DEFAULT_INITIAL_CAPITAL):
        """工厂方法：从 ConfigManager 构建统一的 TradingContext

        Args:
            strategy: 策略实例
            symbol: 品种代码
            config_manager: ConfigManager 实例
            capital: 初始资金 (可被 backtest config 覆盖)

        Returns:
            TradingContext 实例
        """
        bc = config_manager.get_backtest_config()
        account = config_manager.get_account_info()

        # 同步资金/合约乘数到 strategy.config，使策略能正确计算手数
        cfg = strategy.config
        try:
            valid_keys = {f.name for f in dataclasses.fields(cfg)}
        except TypeError:
            valid_keys = set()

        if 'capital' in valid_keys:
            cfg.capital = capital
        elif hasattr(cfg, 'capital'):
            cfg.capital = capital

        if 'contract_size' in valid_keys:
            cfg.contract_size = bc.get('contract_size', DEFAULT_CONTRACT_SIZE)
        elif hasattr(cfg, 'contract_size'):
            cfg.contract_size = bc.get('contract_size', DEFAULT_CONTRACT_SIZE)

        return cls(
            strategy=strategy,
            symbol=symbol,
            capital=capital,
            kline_period=config_manager.get_strategy_config().get('kline_period', DEFAULT_KLINE_PERIOD),
            commission_rate=bc.get('commission_rate', DEFAULT_COMMISSION_RATE),
            slippage=bc.get('slippage', DEFAULT_SLIPPAGE),
            price_tick=bc.get('price_tick', DEFAULT_PRICE_TICK),
            contract_size=bc.get('contract_size', DEFAULT_CONTRACT_SIZE),
            account=account if account else None,
        )