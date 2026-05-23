"""
均线交叉策略

基于简单移动平均线（SMA）的交易策略。
当短期均线上穿长期均线时买入（金叉），
当短期均线下穿长期均线时卖出（死叉）。

风险控制：
- 固定比例止损（默认3%）
- 固定比例止盈（默认5%）
- 固定仓位比例（默认10%）
"""

import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TqApi = None
TqAuth = None
TargetPosTask = None
SMA = None
Future = None


logger = logging.getLogger(__name__)


def _import_tqsdk():
    """延迟导入 tqsdk，避免测试模式下的慢导入"""
    global TqApi, TqAuth, TargetPosTask, SMA, Future
    try:
        from tqsdk import TqApi as _TqApi, TqAuth as _TqAuth, TargetPosTask as _TargetPosTask
        from tqsdk.ta import SMA as _SMA
        from tqsdk.tradeable import Future as _Future
        TqApi = _TqApi
        TqAuth = _TqAuth
        TargetPosTask = _TargetPosTask
        SMA = _SMA
        Future = _Future
        return True
    except ImportError:
        return False


class PositionStatus(Enum):
    """持仓状态枚举"""
    NO_POSITION = "no_position"
    LONG_POSITION = "long_position"
    

@dataclass
class TradingConfig:
    """交易配置参数"""
    sma_short_period: int = 5
    sma_long_period: int = 20
    stop_loss_ratio: float = 0.03
    take_profit_ratio: float = 0.05
    position_ratio: float = 0.1
    
    symbol: str = "DCE.m2109"
    

@dataclass
class TradeRecord:
    """交易记录"""
    timestamp: str = ""
    direction: str = ""
    price: float = 0.0
    volume: int = 0
    reason: str = ""
    profit: float = 0.0


@dataclass
class StrategyState:
    """策略状态"""
    position_status: PositionStatus = PositionStatus.NO_POSITION
    entry_price: float = 0.0
    current_position: int = 0
    trade_records: list = field(default_factory=list)
    
    prev_sma_short: float = 0.0
    prev_sma_long: float = 0.0
    current_sma_short: float = 0.0
    current_sma_long: float = 0.0


class MovingAverageStrategy:
    """
    均线交叉策略类
    
    基于短期和长期简单移动平均线的交叉来产生交易信号。
    金叉买入，死叉卖出，配合止损止盈进行风险控制。
    
    Attributes:
        config: 交易配置
        state: 策略状态
        api: 天勤API实例
    """
    
    def __init__(self, config: Optional[TradingConfig] = None):
        """
        初始化均线策略
        
        Args:
            config: 交易配置参数，默认使用TradingConfig
        """
        self.config = config if config else TradingConfig()
        self.state = StrategyState()
        self.api = None
        self.account = None
        self.position = None
        
        self._setup_logging()
        
    def _setup_logging(self):
        """配置日志"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
    def initialize(self, api: Optional[Any] = None):
        """
        初始化策略
        
        Args:
            api: 天勤API实例，如果为None则使用模拟模式
        """
        self.api = api
        
        if self.api:
            self.account = self.api.get_account()
            self.position = self.api.get_position(self.config.symbol)
            
        logger.info(f"策略初始化完成")
        logger.info(f"交易品种: {self.config.symbol}")
        logger.info(f"SMA参数: 短期={self.config.sma_short_period}, 长期={self.config.sma_long_period}")
        logger.info(f"止损比例: {self.config.stop_loss_ratio:.2%}")
        logger.info(f"止盈比例: {self.config.take_profit_ratio:.2%}")
        logger.info(f"仓位比例: {self.config.position_ratio:.2%}")
        
    def calculate_sma(self, data: Any, period: int) -> float:
        """
        计算简单移动平均线
        
        Args:
            data: K线数据
            period: 周期
            
        Returns:
            SMA值
        """
        if SMA is None:
            return self._calculate_sma_manual(data, period)
        
        try:
            sma_value = SMA(data, period)
            if len(sma_value) > 0:
                return sma_value.iloc[-1]
        except Exception as e:
            logger.error(f"计算SMA失败: {e}")
            
        return self._calculate_sma_manual(data, period)
    
    def _calculate_sma_manual(self, data: Any, period: int) -> float:
        """
        手动计算SMA（当API不可用时使用）
        
        Args:
            data: 收盘价序列
            period: 周期
            
        Returns:
            SMA值
        """
        try:
            if hasattr(data, 'close'):
                prices = list(data.close)[-period:]
            elif isinstance(data, list):
                prices = data[-period:]
            else:
                return 0.0
                
            if len(prices) >= period:
                return sum(prices) / period
        except Exception as e:
            logger.error(f"手动计算SMA失败: {e}")
            
        return 0.0
    
    def check_crossover(self, sma_short: float, sma_long: float, 
                       prev_sma_short: float, prev_sma_long: float) -> str:
        """
        检查均线交叉
        
        Args:
            sma_short: 当前短期SMA
            sma_long: 当前长期SMA
            prev_sma_short: 前一时刻短期SMA
            prev_sma_long: 前一时刻长期SMA
            
        Returns:
            交叉类型: 'golden_cross', 'death_cross', 或 'none'
        """
        if prev_sma_short <= prev_sma_long and sma_short > sma_long:
            return 'golden_cross'
        elif prev_sma_short >= prev_sma_long and sma_short < sma_long:
            return 'death_cross'
        return 'none'
    
    def check_stop_loss(self, current_price: float) -> bool:
        """
        检查是否触发止损
        
        Args:
            current_price: 当前价格
            
        Returns:
            是否触发止损
        """
        if self.state.position_status == PositionStatus.NO_POSITION:
            return False
            
        if self.state.entry_price == 0:
            return False
            
        loss_ratio = (self.state.entry_price - current_price) / self.state.entry_price
        
        return loss_ratio >= self.config.stop_loss_ratio
    
    def check_take_profit(self, current_price: float) -> bool:
        """
        检查是否触发止盈
        
        Args:
            current_price: 当前价格
            
        Returns:
            是否触发止盈
        """
        if self.state.position_status == PositionStatus.NO_POSITION:
            return False
            
        if self.state.entry_price == 0:
            return False
            
        profit_ratio = (current_price - self.state.entry_price) / self.state.entry_price
        
        return profit_ratio >= self.config.take_profit_ratio
    
    def execute_buy(self, symbol: str, price: float, volume: int, reason: str):
        """
        执行买入操作
        
        Args:
            symbol: 交易品种
            price: 买入价格
            volume: 买入数量
            reason: 买入原因
        """
        record = TradeRecord(
            timestamp=self._get_current_time(),
            direction="买入",
            price=price,
            volume=volume,
            reason=reason
        )
        
        self.state.trade_records.append(record)
        self.state.position_status = PositionStatus.LONG_POSITION
        self.state.entry_price = price
        self.state.current_position = volume
        
        logger.info(f"执行买入: {symbol} @ {price}, 数量: {volume}, 原因: {reason}")
        
    def execute_sell(self, symbol: str, price: float, volume: int, reason: str):
        """
        执行卖出操作
        
        Args:
            symbol: 交易品种
            price: 卖出价格
            volume: 卖出数量
            reason: 卖出原因
        """
        profit = 0.0
        if self.state.entry_price > 0:
            profit = (price - self.state.entry_price) * volume
            
        record = TradeRecord(
            timestamp=self._get_current_time(),
            direction="卖出",
            price=price,
            volume=volume,
            reason=reason,
            profit=profit
        )
        
        self.state.trade_records.append(record)
        self.state.position_status = PositionStatus.NO_POSITION
        self.state.entry_price = 0.0
        self.state.current_position = 0
        
        logger.info(f"执行卖出: {symbol} @ {price}, 数量: {volume}, 原因: {reason}, 盈亏: {profit:.2f}")
        
    def _get_current_time(self) -> str:
        """
        获取当前时间字符串
        
        Returns:
            时间字符串
        """
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def on_bar(self, kline_data: Any):
        """
        K线数据回调处理
        
        这是策略的核心方法，在每个K线更新时被调用。
        
        Args:
            kline_data: K线数据对象
        """
        if not kline_data:
            return
            
        self.state.current_sma_short = self.calculate_sma(
            kline_data, self.config.sma_short_period
        )
        self.state.current_sma_long = self.calculate_sma(
            kline_data, self.config.sma_long_period
        )
        
        crossover = self.check_crossover(
            self.state.current_sma_short,
            self.state.current_sma_long,
            self.state.prev_sma_short,
            self.state.prev_sma_long
        )
        
        current_price = 0.0
        try:
            if hasattr(kline_data, 'close'):
                current_price = float(kline_data.close.iloc[-1])
            elif hasattr(kline_data, 'close'):
                current_price = float(list(kline_data.close)[-1])
        except Exception as e:
            logger.error(f"获取当前价格失败: {e}")
            return
        
        if self.state.position_status == PositionStatus.LONG_POSITION:
            if self.check_stop_loss(current_price):
                self.execute_sell(
                    self.config.symbol,
                    current_price,
                    self.state.current_position,
                    "止损"
                )
            elif self.check_take_profit(current_price):
                self.execute_sell(
                    self.config.symbol,
                    current_price,
                    self.state.current_position,
                    "止盈"
                )
            elif crossover == 'death_cross':
                self.execute_sell(
                    self.config.symbol,
                    current_price,
                    self.state.current_position,
                    "死叉卖出"
                )
        else:
            if crossover == 'golden_cross':
                position_size = self._calculate_position_size(current_price)
                self.execute_buy(
                    self.config.symbol,
                    current_price,
                    position_size,
                    "金叉买入"
                )
        
        self.state.prev_sma_short = self.state.current_sma_short
        self.state.prev_sma_long = self.state.current_sma_long
        
    def _calculate_position_size(self, price: float) -> int:
        """
        计算交易仓位
        
        根据账户资金和仓位比例计算交易手数。
        
        Args:
            price: 当前价格
            
        Returns:
            交易手数
        """
        if not self.account:
            return 1
            
        try:
            available_fund = float(self.account.available)
            position_value = available_fund * self.config.position_ratio
            contract_value = price * 10
            
            if contract_value > 0:
                size = int(position_value / contract_value)
                return max(1, size)
        except Exception as e:
            logger.error(f"计算仓位失败: {e}")
            
        return 1
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """
        获取策略绩效摘要
        
        Returns:
            包含绩效指标的字典
        """
        if not self.state.trade_records:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'total_profit': 0.0
            }
            
        winning_trades = [r for r in self.state.trade_records if r.direction == "卖出" and r.profit > 0]
        losing_trades = [r for r in self.state.trade_records if r.direction == "卖出" and r.profit < 0]
        
        total_profit = sum(r.profit for r in self.state.trade_records if r.profit != 0)
        
        return {
            'total_trades': len(self.state.trade_records),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': len(winning_trades) / len(self.state.trade_records) * 2 if self.state.trade_records else 0,
            'total_profit': total_profit
        }
    
    def run(self, symbol: Optional[str] = None, auth: Optional[Any] = None):
        """
        运行策略
        
        Args:
            symbol: 交易品种，默认使用配置中的品种
            auth: 天勤认证对象
        """
        target_symbol = symbol if symbol else self.config.symbol
        
        if TqApi is None:
            _import_tqsdk()
        
        if TqApi is None:
            logger.error("天勤量化API未安装，请运行: pip install tqsdk")
            logger.info("提示: 您可以使用回测模式进行策略测试")
            return
        
        try:
            api = TqApi(auth=auth if auth else TqAuth("guest", ""))
            self.initialize(api)
            
            klines = api.get_kline_serial(target_symbol, 86400)
            
            logger.info(f"开始运行策略: {target_symbol}")
            logger.info("按Ctrl+C停止策略")
            
            while True:
                api.wait_update()
                self.on_bar(klines)
                
        except KeyboardInterrupt:
            logger.info("策略已停止")
        except Exception as e:
            logger.error(f"策略运行错误: {e}")
        finally:
            if self.api:
                self.api.close()
                
            performance = self.get_performance_summary()
            logger.info("策略绩效摘要:")
            logger.info(f"  总交易次数: {performance['total_trades']}")
            logger.info(f"  盈利交易: {performance['winning_trades']}")
            logger.info(f"  亏损交易: {performance['losing_trades']}")
            logger.info(f"  胜率: {performance['win_rate']:.2%}")
            logger.info(f"  总盈亏: {performance['total_profit']:.2f}")
