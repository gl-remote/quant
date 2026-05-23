"""回测引擎模块 - 策略回测与绩效评估"""

from typing import List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import numpy as np


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


class BacktestEngine:
    """回测引擎 - 执行历史数据回测并生成绩效报告"""

    def __init__(self, initial_capital: float = 100000.0):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.current_position = 0
        self.entry_price = 0.0
        self.trade_history: List[TradeRecord] = []
        self.equity_curve: List[float] = [initial_capital]
        self.max_equity = initial_capital

    def add_trade(self, trade: TradeRecord):
        self.trade_history.append(trade)
        if trade.direction == 'buy':
            self.current_position += trade.quantity
            self.entry_price = trade.price
            self.current_capital -= trade.price * trade.quantity
        elif trade.direction == 'sell':
            self.current_position -= trade.quantity
            self.current_capital += trade.price * trade.quantity + trade.profit

        equity = self.current_capital + (self.current_position * self.entry_price
                                          if self.current_position > 0 else 0)
        self.equity_curve.append(equity)
        if equity > self.max_equity:
            self.max_equity = equity

    def calculate_metrics(self) -> BacktestResult:
        result = BacktestResult()
        result.final_equity = self.equity_curve[-1] if self.equity_curve else self.initial_capital
        if not self.trade_history:
            return result

        sells = [t for t in self.trade_history if t.direction == 'sell']
        result.total_trades = len(sells)
        winning = [t for t in sells if t.profit > 0]
        losing = [t for t in sells if t.profit < 0]
        result.winning_trades = len(winning)
        result.losing_trades = len(losing)
        if result.total_trades > 0:
            result.win_rate = result.winning_trades / result.total_trades
        result.total_profit = sum(t.profit for t in sells)
        if winning:
            result.avg_profit = sum(t.profit for t in winning) / len(winning)
        if losing:
            result.avg_loss = sum(t.profit for t in losing) / len(losing)
        result.max_drawdown = self._calc_max_drawdown()
        if result.avg_loss != 0:
            result.profit_factor = abs(result.avg_profit / result.avg_loss)
        result.sharpe_ratio = self._calc_sharpe_ratio()
        return result

    def _calc_max_drawdown(self) -> float:
        if len(self.equity_curve) < 2:
            return 0.0
        peak = self.equity_curve[0]
        max_dd = 0.0
        for equity in self.equity_curve[1:]:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak
            if dd > max_dd:
                max_dd = dd
        return max_dd

    def _calc_sharpe_ratio(self) -> float:
        if len(self.equity_curve) < 2:
            return 0.0
        returns = np.diff(self.equity_curve) / np.array(self.equity_curve[:-1])
        if len(returns) == 0:
            return 0.0
        std = np.std(returns)
        return 0.0 if std == 0 else (np.mean(returns) / std) * np.sqrt(252)

    def generate_report(self) -> str:
        r = self.calculate_metrics()
        return (
            f"{'=' * 60}\n"
            f"回测报告\n"
            f"{'=' * 60}\n"
            f"初始资金: {self.initial_capital:,.2f}\n"
            f"最终资金: {r.final_equity:,.2f}\n"
            f"总收益率: {((r.final_equity - self.initial_capital) / self.initial_capital):.2%}\n\n"
            f"交易统计:\n"
            f"  总交易次数: {r.total_trades}\n"
            f"  盈利交易: {r.winning_trades}\n"
            f"  亏损交易: {r.losing_trades}\n"
            f"  胜率: {r.win_rate:.2%}\n\n"
            f"盈亏统计:\n"
            f"  总盈亏: {r.total_profit:,.2f}\n"
            f"  平均盈利: {r.avg_profit:,.2f}\n"
            f"  平均亏损: {r.avg_loss:,.2f}\n"
            + (f"  盈亏比: {r.profit_factor:.2f}\n" if r.profit_factor > 0 else "") +
            f"  最大回撤: {r.max_drawdown:.2%}\n"
            f"  夏普比率: {r.sharpe_ratio:.2f}\n"
            f"{'=' * 60}"
        )
