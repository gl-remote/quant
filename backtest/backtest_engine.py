"""
回测引擎模块

提供策略回测功能和绩效评估。
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import numpy as np


@dataclass
class TradeRecord:
    """交易记录"""
    timestamp: datetime
    symbol: str
    direction: str  # 'buy' or 'sell'
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
    """
    回测引擎
    
    负责执行历史数据回测并生成绩效报告。
    """
    
    def __init__(self, initial_capital: float = 100000.0):
        """
        初始化回测引擎
        
        Args:
            initial_capital: 初始资金
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.current_position = 0
        self.entry_price = 0.0
        self.trade_history: List[TradeRecord] = []
        self.equity_curve: List[float] = [initial_capital]
        self.equity_dates: List[datetime] = []
        self.max_equity = initial_capital
    
    def add_trade(self, trade: TradeRecord):
        """
        添加交易记录
        
        Args:
            trade: 交易记录对象
        """
        self.trade_history.append(trade)
        
        if trade.direction == 'buy':
            self.current_position += trade.quantity
            self.entry_price = trade.price
            self.current_capital -= trade.price * trade.quantity
            
        elif trade.direction == 'sell':
            self.current_position -= trade.quantity
            self.current_capital += trade.price * trade.quantity + trade.profit
            
        self.equity_curve.append(self.current_capital + 
                                (self.current_position * self.entry_price if self.current_position > 0 else 0))
        
        if self.equity_curve[-1] > self.max_equity:
            self.max_equity = self.equity_curve[-1]
    
    def calculate_metrics(self) -> BacktestResult:
        """
        计算绩效指标
        
        Returns:
            回测结果对象
        """
        result = BacktestResult()
        result.final_equity = self.equity_curve[-1] if self.equity_curve else self.initial_capital
        
        if not self.trade_history:
            return result
            
        sell_trades = [t for t in self.trade_history if t.direction == 'sell']
        result.total_trades = len(sell_trades)
        
        winning = [t for t in sell_trades if t.profit > 0]
        losing = [t for t in sell_trades if t.profit < 0]
        
        result.winning_trades = len(winning)
        result.losing_trades = len(losing)
        
        if result.total_trades > 0:
            result.win_rate = result.winning_trades / result.total_trades
            
        result.total_profit = sum(t.profit for t in sell_trades)
        
        if winning:
            result.avg_profit = sum(t.profit for t in winning) / len(winning)
            
        if losing:
            result.avg_loss = sum(t.profit for t in losing) / len(losing)
            
        result.max_drawdown = self._calculate_max_drawdown()
        
        if result.avg_loss != 0:
            result.profit_factor = abs(result.avg_profit / result.avg_loss)
        
        result.sharpe_ratio = self._calculate_sharpe_ratio()
        
        return result
    
    def _calculate_max_drawdown(self) -> float:
        """
        计算最大回撤
        
        Returns:
            最大回撤比例
        """
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
    
    def _calculate_sharpe_ratio(self) -> float:
        """
        计算夏普比率（简化版）
        
        Returns:
            夏普比率
        """
        if len(self.equity_curve) < 2:
            return 0.0
            
        returns = []
        for i in range(1, len(self.equity_curve)):
            if self.equity_curve[i-1] > 0:
                returns.append(self.equity_curve[i] / self.equity_curve[i-1] - 1)
        
        if not returns:
            return 0.0
            
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        return mean_return / std_return * np.sqrt(252)
    
    def generate_report(self) -> str:
        """
        生成回测报告
        
        Returns:
            格式化的回测报告字符串
        """
        result = self.calculate_metrics()
        
        report = []
        report.append("=" * 60)
        report.append("回测报告")
        report.append("=" * 60)
        report.append(f"初始资金: {self.initial_capital:,.2f}")
        report.append(f"最终资金: {result.final_equity:,.2f}")
        report.append(f"总收益率: {((result.final_equity - self.initial_capital) / self.initial_capital):.2%}")
        report.append("")
        report.append("交易统计:")
        report.append(f"  总交易次数: {result.total_trades}")
        report.append(f"  盈利交易: {result.winning_trades}")
        report.append(f"  亏损交易: {result.losing_trades}")
        report.append(f"  胜率: {result.win_rate:.2%}")
        report.append("")
        report.append("盈亏统计:")
        report.append(f"  总盈亏: {result.total_profit:,.2f}")
        report.append(f"  平均盈利: {result.avg_profit:,.2f}")
        report.append(f"  平均亏损: {result.avg_loss:,.2f}")
        
        if result.profit_factor > 0:
            report.append(f"  盈亏比: {result.profit_factor:.2f}")
            
        report.append(f"  最大回撤: {result.max_drawdown:.2%}")
        report.append(f"  夏普比率: {result.sharpe_ratio:.2f}")
        report.append("=" * 60)
        
        return "\n".join(report)
    
    def run_backtest(self, strategy, data: List[Dict[str, Any]]):
        """
        执行完整回测
        
        Args:
            strategy: 策略对象
            data: 历史数据列表，每个元素包含 'datetime', 'open', 'high', 'low', 'close', 'volume'
        """
        for bar in data:
            strategy.on_bar(bar)
            
            if strategy.signal == 'buy' and self.current_position == 0:
                quantity = int((self.current_capital * strategy.config.position_ratio) / bar['close'])
                if quantity > 0:
                    trade = TradeRecord(
                        timestamp=bar['datetime'],
                        symbol=strategy.config.symbol,
                        direction='buy',
                        price=bar['close'],
                        quantity=quantity,
                        reason="金叉买入"
                    )
                    self.add_trade(trade)
                    strategy.signal = None
            
            elif strategy.signal == 'sell' and self.current_position > 0:
                profit = (bar['close'] - self.entry_price) * self.current_position
                trade = TradeRecord(
                    timestamp=bar['datetime'],
                    symbol=strategy.config.symbol,
                    direction='sell',
                    price=bar['close'],
                    quantity=self.current_position,
                    profit=profit,
                    reason=strategy.signal_reason
                )
                self.add_trade(trade)
                strategy.signal = None
