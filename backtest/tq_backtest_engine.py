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
from .metrics import calc_max_drawdown, calc_sharpe_ratio


class TQBacktestEngine:
    """天勤回测引擎 — 单标的图形窗口展示

    用于 tq-backtest 实盘/模拟模式的交易跟踪，提供轻量级的
    交易记录、权益曲线和绩效指标计算，与天勤 TqSdk 的图形界面配合。

    使用方式:
        engine = TQBacktestEngine(initial_capital=100000)
        engine.add_trade(TradeRecord(...))
        print(engine.generate_report())
    """

    def __init__(self, initial_capital: float = 100000.0):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.current_position = 0
        self.entry_price = 0.0
        self.trade_history: List[TradeRecord] = []
        self.equity_curve: List[float] = [initial_capital]
        self.max_equity = initial_capital

    def add_trade(self, trade: TradeRecord):
        """记录一笔交易并更新持仓/权益

        Args:
            trade: TradeRecord 实例，direction 为 'buy' 或 'sell'
        """
        self.trade_history.append(trade)
        if trade.direction == 'buy':
            old_pos = self.current_position
            self.current_position += trade.quantity
            self.current_capital -= trade.price * trade.quantity
            # 加权平均成本价，避免多次买入时被最后一次价格覆盖
            if old_pos == 0:
                self.entry_price = trade.price
            else:
                self.entry_price = (
                    old_pos * self.entry_price + trade.quantity * trade.price
                ) / self.current_position
        elif trade.direction == 'sell':
            self.current_position -= trade.quantity
            # 只加回卖出金额，profit 为信息字段，价差已体现在 (sell - entry) 中
            self.current_capital += trade.price * trade.quantity

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
        result.max_drawdown = calc_max_drawdown(self.equity_curve)
        # 行业标准: gross_profit / abs(gross_loss)，非平均盈亏比
        total_win = sum(t.profit for t in winning)
        total_loss = sum(t.profit for t in losing)
        if total_loss != 0:
            result.profit_factor = total_win / abs(total_loss)
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
            f"总收益率: {((r.final_equity - self.initial_capital) / self.initial_capital):.2%}",
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
