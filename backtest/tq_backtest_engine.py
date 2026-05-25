# -*- coding: utf-8 -*-
"""
天勤回测引擎 — 单标的图形窗口展示 (tq-backtest)

专用于 tq-backtest 实盘/模拟模式：
  - 手动记录每笔交易，跟踪持仓和权益曲线
  - 计算绩效指标（胜率/夏普/最大回撤/盈亏比）
  - 生成文本回测报告
  - 配合天勤 TqSdk 的图形界面提供可视化

职责明确：
  - TQBacktestEngine:   单标的图形化分析 (天勤 TqSdk)
  - VnpyBacktestEngine: 批量回测流水线 (vn.py)
"""

from typing import List

from .types import TradeRecord, BacktestResult
from common.metrics import calc_max_drawdown, calc_sharpe_ratio
from common.constants import (
    TRADE_ACTION_BUY,
    TRADE_ACTION_SELL,
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_COMMISSION_RATE,
    DEFAULT_SLIPPAGE,
)
from common.formulas import trade_cost as calc_trade_cost, profit_factor, average_entry_price, total_return


class TQBacktestEngine:
    """天勤回测引擎 — 单标的图形窗口展示

    用于 tq-backtest 实盘/模拟模式的交易跟踪，提供轻量级的
    交易记录、权益曲线和绩效指标计算，与天勤 TqSdk 的图形界面配合。

    使用方式:
        engine = TQBacktestEngine(initial_capital=100000,
                                  commission_rate=0.0003, slippage=1.0)
        engine.add_trade(TradeRecord(...))
        print(engine.generate_report())
    """

    def __init__(
        self,
        initial_capital: float = DEFAULT_INITIAL_CAPITAL,
        commission_rate: float = DEFAULT_COMMISSION_RATE,
        slippage: float = DEFAULT_SLIPPAGE,
    ):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.current_position = 0
        self.entry_price = 0.0
        self.trade_history: List[TradeRecord] = []
        self.equity_curve: List[float] = [initial_capital]
        self.max_equity = initial_capital
        self.commission_rate = commission_rate
        self.slippage = slippage

    def _trade_cost(self, price: float, quantity: int) -> float:
        """单边交易成本: 手续费 + 滑点"""
        return calc_trade_cost(price, quantity,
                             self.commission_rate, self.slippage)

    def add_trade(self, trade: TradeRecord):
        """记录一笔交易并更新持仓/权益

        买入扣减 价格*数量 + 手续费 + 滑点
        卖出增加 价格*数量 - 手续费 - 滑点

        Args:
            trade: TradeRecord 实例，direction 为 'buy' 或 'sell'
        """
        self.trade_history.append(trade)
        cost = self._trade_cost(trade.price, trade.quantity)
        if trade.direction == TRADE_ACTION_BUY:
            old_pos = self.current_position
            self.current_position += trade.quantity
            self.current_capital -= (trade.price * trade.quantity + cost)
            if old_pos == 0:
                self.entry_price = trade.price
            else:
                self.entry_price = average_entry_price(
                    old_pos, self.entry_price, trade.quantity, trade.price)
        elif trade.direction == TRADE_ACTION_SELL:
            self.current_position -= trade.quantity
            self.current_capital += (trade.price * trade.quantity - cost)

        equity = self.current_capital + (self.current_position * self.entry_price
                                          if self.current_position > 0 else 0)
        self.equity_curve.append(equity)
        if equity > self.max_equity:
            self.max_equity = equity

    def calculate_metrics(self) -> BacktestResult:
        """计算所有绩效指标

        Returns:
            BacktestResult 包含: 总交易数、胜率、盈亏比、夏普比率、最大回撤、最终权益
        """
        result = BacktestResult()
        result.final_equity = self.equity_curve[-1] if self.equity_curve else self.initial_capital
        if not self.trade_history:
            return result

        sells = [t for t in self.trade_history if t.direction == TRADE_ACTION_SELL]
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
        result.max_drawdown = calc_max_drawdown(self.equity_curve)
        total_win = sum(t.profit for t in winning)
        total_loss = sum(t.profit for t in losing)
        result.profit_factor = profit_factor(total_win, total_loss)
        result.sharpe_ratio = calc_sharpe_ratio(self.equity_curve)
        return result

    def generate_report(self) -> str:
        """生成纯文本回测报告

        Returns:
            格式化的回测报告文本
        """
        r = self.calculate_metrics()
        lines = [
            f"{'=' * 60}",
            f"回测报告",
            f"{'=' * 60}",
            f"初始资金: {self.initial_capital:,.2f}",
            f"最终资金: {r.final_equity:,.2f}",
            f"总收益率: {total_return(self.initial_capital, r.final_equity):.2%}",
            "",
            f"交易统计:",
            f"  总交易次数: {r.total_trades}",
            f"  盈利交易: {r.winning_trades}",
            f"  亏损交易: {r.losing_trades}",
            f"  胜率: {r.win_rate:.2%}",
            "",
            f"盈亏统计:",
            f"  总盈亏: {r.total_profit:,.2f}",
            f"  平均盈利: {r.avg_profit:,.2f}",
            f"  平均亏损: {r.avg_loss:,.2f}",
        ]
        if r.profit_factor > 0:
            lines.append(f"  盈亏比: {r.profit_factor:.2f}")
        lines.extend([
            f"  最大回撤: {r.max_drawdown:.2%}",
            f"  夏普比率: {r.sharpe_ratio:.2f}",
            f"{'=' * 60}",
        ])
        return "\n".join(lines)
