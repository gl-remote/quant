"""vn.py 框架网关适配器 - 将纯业务逻辑策略适配为 vnpy CtaTemplate

使 MaStrategyCore 可在 vnpy BacktestingEngine 中运行。
回测引擎通过此网关调用策略，网关将 vnpy BarData 转换为核心层输入，
并将核心层信号转换为 vnpy self.buy() / self.sell() 调用。
"""

import logging
from datetime import datetime
from typing import Dict

from ..core.ma_strategy import MaStrategyCore, TradingConfig, TradeRecord as CoreTradeRecord

logger = logging.getLogger(__name__)

try:
    from vnpy_ctastrategy import CtaTemplate
    from vnpy.trader.object import BarData, TickData, OrderData, TradeData
    HAS_VNPY = True
except ImportError:
    HAS_VNPY = False
    logger.warning("vnpy未安装，策略将运行在兼容模式")
    CtaTemplate = object
    BarData = object
    TickData = object
    OrderData = object
    TradeData = object


class VnpyMaStrategy(CtaTemplate if HAS_VNPY else object):
    """双均线交叉CTA策略 (vn.py 网关)

    vn.py 标准策略接口:
      - on_init(): 策略初始化
      - on_start(): 策略启动
      - on_stop(): 策略停止
      - on_bar(bar): K线回调 (核心交易逻辑)
      - on_tick(tick): Tick回调

    策略参数 (通过 add_strategy 的 setting 字典传入):
      - sma_short: 短期均线周期
      - sma_long: 长期均线周期
      - stop_loss_ratio: 止损比例
      - take_profit_ratio: 止盈比例
      - position_ratio: 仓位比例
      - price_tick: 最小价格变动
    """

    author = "Quant System"

    parameters = [
        "sma_short", "sma_long",
        "stop_loss_ratio", "take_profit_ratio",
        "position_ratio", "price_tick"
    ]
    variables = [
        "entry_price", "pos", "sma_short_val",
        "sma_long_val", "prev_sma_short", "prev_sma_long"
    ]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict):
        if HAS_VNPY:
            super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        else:
            self.cta_engine = cta_engine
            self.strategy_name = strategy_name
            self.vt_symbol = vt_symbol

        self.sma_short: int = setting.get('sma_short', 5)
        self.sma_long: int = setting.get('sma_long', 20)
        self.stop_loss_ratio: float = setting.get('stop_loss_ratio', 0.03)
        self.take_profit_ratio: float = setting.get('take_profit_ratio', 0.05)
        self.position_ratio: float = setting.get('position_ratio', 0.1)
        self.price_tick: float = setting.get('price_tick', 1.0)

        self.entry_price: float = 0.0
        self.sma_short_val: float = 0.0
        self.sma_long_val: float = 0.0
        self.prev_sma_short: float = 0.0
        self.prev_sma_long: float = 0.0

        self._close_history: list = []
        self._trades: list = []

        self.trade_count: int = 0
        self.win_count: int = 0
        self.total_profit: float = 0.0

        core_config = TradingConfig(
            sma_short=self.sma_short,
            sma_long=self.sma_long,
            stop_loss_ratio=self.stop_loss_ratio,
            take_profit_ratio=self.take_profit_ratio,
            position_ratio=self.position_ratio,
        )
        self._core = MaStrategyCore(core_config)

    def on_init(self):
        logger.info(
            f"[{self.strategy_name}] 策略初始化: SMA({self.sma_short},{self.sma_long}) "
            f"止损={self.stop_loss_ratio:.0%} 止盈={self.take_profit_ratio:.0%}"
        )
        if HAS_VNPY:
            self.write_log(f"策略初始化: SMA({self.sma_short},{self.sma_long})")
            self.load_bar(10)

    def on_start(self):
        logger.info(f"[{self.strategy_name}] 策略启动")
        if HAS_VNPY:
            self.write_log("策略启动")

    def on_stop(self):
        logger.info(
            f"[{self.strategy_name}] 策略停止 | "
            f"交易{self.trade_count}次 胜{self.win_count} "
            f"总盈亏{self.total_profit:.2f}"
        )
        if HAS_VNPY:
            self.write_log(f"策略停止: 交易{self.trade_count}次 总盈亏{self.total_profit:.2f}")

    def on_bar(self, bar):
        close_price = bar.close_price if hasattr(bar, 'close_price') else bar.get('close_price', 0)
        self._close_history.append(close_price)

        if len(self._close_history) < self.sma_long:
            return

        signal, reason = self._core.on_bar_signal(self._close_history, close_price)

        if signal == 'buy' and self.pos == 0:
            self._execute_buy(bar)
        elif signal == 'sell' and self.pos > 0:
            self._execute_sell(bar, reason)

    def _execute_buy(self, bar):
        volume = self._calc_volume(bar.close_price)
        if volume <= 0:
            return
        if HAS_VNPY:
            self.buy(bar.close_price, volume)
        self.entry_price = bar.close_price
        self._core.on_enter(bar.close_price, volume)
        self.trade_count += 1
        logger.info(
            f"[{self.strategy_name}] {bar.datetime} 金叉买入 "
            f"@{bar.close_price:.2f} x{volume}"
        )

    def _execute_sell(self, bar, reason):
        pos = abs(self.pos) if HAS_VNPY and hasattr(self, 'pos') else self._core.state.current_position
        if HAS_VNPY:
            self.sell(bar.close_price, pos)
        profit = self._core.on_exit(bar.close_price)
        self.total_profit += profit
        self.entry_price = 0.0
        if profit > 0:
            self.win_count += 1
        logger.info(
            f"[{self.strategy_name}] {bar.datetime} {reason}卖出 "
            f"@{bar.close_price:.2f} 盈亏{profit:.2f}"
        )

    def _calc_volume(self, price: float) -> int:
        capital = self.cta_engine.capital if hasattr(self.cta_engine, 'capital') else 100000
        return self._core.calc_position_size(price, capital)

    def on_tick(self, tick: TickData):
        pass

    def on_order(self, order: OrderData):
        if HAS_VNPY:
            super().on_order(order)

    def on_trade(self, trade: TradeData):
        if HAS_VNPY:
            super().on_trade(trade)

    def get_performance(self) -> Dict:
        return {
            'trade_count': self.trade_count,
            'win_count': self.win_count,
            'lose_count': self.trade_count - self.win_count,
            'win_rate': self.win_count / max(self.trade_count, 1),
            'total_profit': self.total_profit,
        }