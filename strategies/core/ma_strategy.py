"""均线交叉策略 - 纯业务逻辑层

不依赖任何外部框架 (vn.py / tqsdk)，仅包含 SMA 计算、信号检测、
止盈止损判断等核心算法。供各网关适配器调用。
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class PositionStatus(Enum):
    NO_POSITION = "no_position"
    LONG_POSITION = "long_position"


@dataclass
class TradingConfig:
    sma_short: int = 5
    sma_long: int = 20
    stop_loss_ratio: float = 0.03
    take_profit_ratio: float = 0.05
    position_ratio: float = 0.1


@dataclass
class StrategyState:
    position_status: PositionStatus = PositionStatus.NO_POSITION
    entry_price: float = 0.0
    current_position: int = 0
    prev_sma_short: float = 0.0
    prev_sma_long: float = 0.0


@dataclass
class TradeRecord:
    timestamp: str = ""
    direction: str = ""
    price: float = 0.0
    volume: int = 0
    reason: str = ""
    profit: float = 0.0


class MaStrategyCore:
    """均线交叉策略核心 - 纯算法逻辑，无框架依赖

    负责:
      - SMA 计算
      - 金叉/死叉信号检测
      - 止盈止损判断
      - 状态管理

    不负责:
      - 行情数据获取 (由网关处理)
      - 订单执行 (由网关处理)
      - 框架生命周期 (由网关处理)
    """

    def __init__(self, config: Optional[TradingConfig] = None):
        self.config = config or TradingConfig()
        self.state = StrategyState()

    def calculate_sma(self, data: List[float], period: int) -> float:
        if not data or period <= 0:
            return 0.0
        chunk = data[-period:]
        return sum(chunk) / len(chunk)

    def check_crossover(self, short: float, long: float,
                        prev_short: float, prev_long: float) -> str:
        if prev_short <= prev_long and short > long:
            return 'golden_cross'
        if prev_short >= prev_long and short < long:
            return 'death_cross'
        return 'none'

    def check_stop_loss(self, current_price: float) -> bool:
        if (self.state.position_status != PositionStatus.LONG_POSITION
                or self.state.entry_price <= 0):
            return False
        return ((self.state.entry_price - current_price) /
                self.state.entry_price >= self.config.stop_loss_ratio)

    def check_take_profit(self, current_price: float) -> bool:
        if (self.state.position_status != PositionStatus.LONG_POSITION
                or self.state.entry_price <= 0):
            return False
        return ((current_price - self.state.entry_price) /
                self.state.entry_price >= self.config.take_profit_ratio)

    def on_bar_signal(self, closes: List[float], current_price: float) -> Tuple[Optional[str], str]:
        """处理一根K线，返回交易信号和原因

        Args:
            closes: 历史收盘价序列 (含当前)
            current_price: 当前收盘价

        Returns:
            (signal, reason):
              signal: 'buy' / 'sell' / None
              reason: 'golden_cross' / 'death_cross' / 'stop_loss' / 'take_profit' / ''
        """
        if not closes:
            return None, ''

        cur_short = self.calculate_sma(closes, self.config.sma_short)
        cur_long = self.calculate_sma(closes, self.config.sma_long)
        crossover = self.check_crossover(
            cur_short, cur_long,
            self.state.prev_sma_short, self.state.prev_sma_long,
        )

        signal = None
        reason = ''

        if self.state.position_status == PositionStatus.LONG_POSITION:
            if self.check_stop_loss(current_price):
                signal, reason = 'sell', 'stop_loss'
            elif self.check_take_profit(current_price):
                signal, reason = 'sell', 'take_profit'
            elif crossover == 'death_cross':
                signal, reason = 'sell', 'death_cross'
        elif crossover == 'golden_cross':
            signal, reason = 'buy', 'golden_cross'

        self.state.prev_sma_short = cur_short
        self.state.prev_sma_long = cur_long
        return signal, reason

    def on_enter(self, price: float, volume: int):
        """持仓入场"""
        self.state.position_status = PositionStatus.LONG_POSITION
        self.state.entry_price = price
        self.state.current_position = volume

    def on_exit(self, exit_price: float) -> float:
        """持仓出场，返回盈亏金额"""
        if self.state.entry_price <= 0 or self.state.current_position <= 0:
            self.state.position_status = PositionStatus.NO_POSITION
            self.state.entry_price = 0.0
            self.state.current_position = 0
            return 0.0
        profit = (exit_price - self.state.entry_price) * self.state.current_position
        self.state.position_status = PositionStatus.NO_POSITION
        self.state.entry_price = 0.0
        self.state.current_position = 0
        return profit

    def calc_position_size(self, price: float, capital: float,
                           contract_size: int = 10) -> int:
        vol = capital * self.config.position_ratio / (price * contract_size)
        return max(1, int(vol))

    def get_performance(self, trade_records: List[TradeRecord]) -> Dict[str, Any]:
        sells = [r for r in trade_records if r.direction == "sell"]
        if not sells:
            return {
                'total_trades': 0, 'winning_trades': 0, 'losing_trades': 0,
                'win_rate': 0.0, 'total_profit': 0.0,
            }
        wins = [r for r in sells if r.profit > 0]
        losses = [r for r in sells if r.profit < 0]
        return {
            'total_trades': len(sells),
            'winning_trades': len(wins),
            'losing_trades': len(losses),
            'win_rate': len(wins) / len(sells) if sells else 0,
            'total_profit': sum(r.profit for r in sells),
        }