"""
回测引擎模块

提供策略回测功能和绩效评估。
"""

from typing import List, Dict, Any
from dataclasses import dataclass
from datetime import datetime


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
        self.trade_history: List[Dict[str, Any]] = []
        self.equity_curve: List[float] = [initial_capital]
        
    def add_trade(self, trade: Dict[str, Any]):
        """
        添加交易记录
        
        Args:
            trade: 交易记录字典
        """
        self.trade_history.append(trade)
        
        if trade['direction'] == 'sell':
            self.current_capital += trade['profit']
            
        self.equity_curve.append(self.current_capital)
        
    def calculate_metrics(self) -> BacktestResult:
        """
        计算绩效指标
        
        Returns:
            回测结果对象
        """
        result = BacktestResult()
        
        if not self.trade_history:
            return result
            
        sell_trades = [t for t in self.trade_history if t['direction'] == 'sell']
        result.total_trades = len(sell_trades)
        
        winning = [t for t in sell_trades if t['profit'] > 0]
        losing = [t for t in sell_trades if t['profit'] < 0]
        
        result.winning_trades = len(winning)
        result.losing_trades = len(losing)
        
        if result.total_trades > 0:
            result.win_rate = result.winning_trades / result.total_trades
            
        result.total_profit = sum(t['profit'] for t in sell_trades)
        
        if winning:
            result.avg_profit = sum(t['profit'] for t in winning) / len(winning)
            
        if losing:
            result.avg_loss = sum(t['profit'] for t in losing) / len(losing)
            
        result.max_drawdown = self._calculate_max_drawdown()
        
        return result
    
    def _calculate_max_drawdown(self) -> float:
        """
        计算最大回撤
        
        Returns:
            最大回撤比例
        """
        if not self.equity_curve:
            return 0.0
            
        peak = self.equity_curve[0]
        max_dd = 0.0
        
        for equity in self.equity_curve:
            if equity > peak:
                peak = equity
                
            dd = (peak - equity) / peak
            if dd > max_dd:
                max_dd = dd
                
        return max_dd
    
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
        report.append(f"最终资金: {self.current_capital:,.2f}")
        report.append(f"总收益率: {((self.current_capital - self.initial_capital) / self.initial_capital):.2%}")
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
        
        if result.avg_loss != 0:
            profit_loss_ratio = abs(result.avg_profit / result.avg_loss)
            report.append(f"  盈亏比: {profit_loss_ratio:.2f}")
            
        report.append(f"  最大回撤: {result.max_drawdown:.2%}")
        report.append("=" * 60)
        
        return "\n".join(report)
