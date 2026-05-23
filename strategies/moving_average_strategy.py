"""均线交叉策略 - 基于 SMA 金叉/死叉的交易信号生成，含止损止盈风险控制"""

import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)

# tqsdk 延迟导入
_TqApi = _TqAuth = _TargetPosTask = _SMA = None  # noqa: E221


def _import_tqsdk():
    global _TqApi, _TqAuth, _TargetPosTask, _SMA
    try:
        from tqsdk import TqApi, TqAuth, TargetPosTask
        from tqsdk.ta import SMA
        _TqApi, _TqAuth, _TargetPosTask, _SMA = TqApi, TqAuth, TargetPosTask, SMA
        return True
    except ImportError:
        return False


class PositionStatus(Enum):
    NO_POSITION = "no_position"
    LONG_POSITION = "long_position"


@dataclass
class TradingConfig:
    sma_short_period: int = 5
    sma_long_period: int = 20
    stop_loss_ratio: float = 0.03
    take_profit_ratio: float = 0.05
    position_ratio: float = 0.1
    symbol: str = "DCE.m2109"


@dataclass
class TradeRecord:
    timestamp: str = ""
    direction: str = ""
    price: float = 0.0
    volume: int = 0
    reason: str = ""
    profit: float = 0.0


@dataclass
class StrategyState:
    position_status: PositionStatus = PositionStatus.NO_POSITION
    entry_price: float = 0.0
    current_position: int = 0
    trade_records: list = field(default_factory=list)
    prev_sma_short: float = 0.0
    prev_sma_long: float = 0.0


class MovingAverageStrategy:
    """均线交叉策略 - 金叉买入、死叉卖出，配合止损止盈"""

    def __init__(self, config: Optional[TradingConfig] = None):
        self.config = config or TradingConfig()
        self.state = StrategyState()
        self.api = None
        self.account = None
        self.signal = None
        self.signal_reason = ""

    def initialize(self, api: Optional[Any] = None):
        self.api = api
        if api:
            self.account = api.get_account()
        logger.info(f"策略初始化: {self.config.symbol} SMA({self.config.sma_short_period},{self.config.sma_long_period})")

    def calculate_sma(self, data, period: int) -> float:
        if _SMA is not None:
            try:
                result = _SMA(data, period)
                return float(result.iloc[-1]) if len(result) > 0 else 0.0
            except Exception:
                pass
        return self._sma_manual(data, period)

    def _sma_manual(self, data, period: int) -> float:
        try:
            if isinstance(data, list):
                chunk = data[-period:]
                return sum(chunk) / len(chunk) if chunk else 0.0
            if hasattr(data, 'close'):
                data = list(data.close)[-period:]
            return sum(data) / len(data) if data else 0.0
        except Exception:
            return 0.0

    def check_crossover(self, short: float, long: float, prev_short: float, prev_long: float) -> str:
        if prev_short <= prev_long and short > long:
            return 'golden_cross'
        if prev_short >= prev_long and short < long:
            return 'death_cross'
        return 'none'

    def check_stop_loss(self, current_price: float) -> bool:
        if self.state.position_status != PositionStatus.LONG_POSITION or self.state.entry_price == 0:
            return False
        return (self.state.entry_price - current_price) / self.state.entry_price >= self.config.stop_loss_ratio

    def check_take_profit(self, current_price: float) -> bool:
        if self.state.position_status != PositionStatus.LONG_POSITION or self.state.entry_price == 0:
            return False
        return (current_price - self.state.entry_price) / self.state.entry_price >= self.config.take_profit_ratio

    def execute_buy(self, symbol: str, price: float, volume: int, reason: str):
        self.state.trade_records.append(TradeRecord(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            direction="买入", price=price, volume=volume, reason=reason))
        self.state.position_status = PositionStatus.LONG_POSITION
        self.state.entry_price = price
        self.state.current_position = volume
        logger.info(f"买入: {symbol} @ {price}, 数量: {volume}, 原因: {reason}")

    def execute_sell(self, symbol: str, price: float, volume: int, reason: str):
        profit = (price - self.state.entry_price) * volume if self.state.entry_price > 0 else 0.0
        self.state.trade_records.append(TradeRecord(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            direction="卖出", price=price, volume=volume, reason=reason, profit=profit))
        self.state.position_status = PositionStatus.NO_POSITION
        self.state.entry_price = 0.0
        self.state.current_position = 0
        logger.info(f"卖出: {symbol} @ {price}, 数量: {volume}, 原因: {reason}, 盈亏: {profit:.2f}")

    def on_bar(self, kline_data):
        if kline_data.empty:
            return
        self.signal = None
        self.signal_reason = ""

        try:
            closes = list(kline_data.close)
            current_price = float(kline_data.close.iloc[-1])
        except Exception as e:
            logger.error(f"获取价格数据失败: {e}")
            return

        cur_short = self.calculate_sma(closes, self.config.sma_short_period)
        cur_long = self.calculate_sma(closes, self.config.sma_long_period)
        crossover = self.check_crossover(cur_short, cur_long,
                                          self.state.prev_sma_short, self.state.prev_sma_long)

        if self.state.position_status == PositionStatus.LONG_POSITION:
            if self.check_stop_loss(current_price):
                self.signal, self.signal_reason = 'sell', "止损"
                self.execute_sell(self.config.symbol, current_price, self.state.current_position, "止损")
            elif self.check_take_profit(current_price):
                self.signal, self.signal_reason = 'sell', "止盈"
                self.execute_sell(self.config.symbol, current_price, self.state.current_position, "止盈")
            elif crossover == 'death_cross':
                self.signal, self.signal_reason = 'sell', "死叉卖出"
                self.execute_sell(self.config.symbol, current_price, self.state.current_position, "死叉卖出")
        elif crossover == 'golden_cross':
            self.signal, self.signal_reason = 'buy', "金叉买入"

        self.state.prev_sma_short = cur_short
        self.state.prev_sma_long = cur_long

    def _calc_position_size(self, price: float) -> int:
        if not self.account:
            return 1
        try:
            fund = float(self.account.available)
            return max(1, int(fund * self.config.position_ratio / (price * 10)))
        except Exception:
            return 1

    def get_performance_summary(self) -> Dict[str, Any]:
        records = self.state.trade_records
        if not records:
            return {'total_trades': 0, 'winning_trades': 0, 'losing_trades': 0,
                    'win_rate': 0.0, 'total_profit': 0.0}
        sells = [r for r in records if r.direction == "卖出"]
        wins = [r for r in sells if r.profit > 0]
        losses = [r for r in sells if r.profit < 0]
        return {
            'total_trades': len(sells),
            'winning_trades': len(wins),
            'losing_trades': len(losses),
            'win_rate': len(wins) / len(sells) if sells else 0,
            'total_profit': sum(r.profit for r in sells)
        }

    def run(self, symbol: Optional[str] = None, auth: Optional[Any] = None):
        target = symbol or self.config.symbol
        if _TqApi is None and not _import_tqsdk():
            logger.error("天勤量化API未安装，请运行: pip install tqsdk")
            return
        try:
            api = _TqApi(auth=auth or _TqAuth("guest", ""))
            self.initialize(api)
            klines = api.get_kline_serial(target, 86400)
            logger.info(f"开始运行策略: {target}，按Ctrl+C停止")
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
            p = self.get_performance_summary()
            logger.info(f"绩效: 交易{p['total_trades']}次 胜率{p['win_rate']:.0%} 盈亏{p['total_profit']:.2f}")

    def run_with_gui(self, symbol: Optional[str] = None, auth: Optional[Any] = None):
        """带图形界面运行策略（实盘可视化）"""
        target = symbol or self.config.symbol
        if _TqApi is None and not _import_tqsdk():
            logger.error("天勤量化API未安装")
            return
        try:
            api = _TqApi(auth=auth or _TqAuth("guest", ""), web_gui=True)
            self.initialize(api)
            klines = api.get_kline_serial(target, 86400)
            logger.info(f"启动图形界面: {target}，浏览器访问 http://127.0.0.1:9876")
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