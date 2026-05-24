"""vn.py 框架网关适配器 - 将 Strategy 接口实现适配为 vnpy CtaTemplate

网关职责 (纯粹的适配层):
  - 将 vnpy BarData 转换后传递给 Strategy.on_bar_signal()
  - 将 Strategy 返回的信号 (buy/sell) 转换为 vnpy self.buy() / self.sell()
  - 记录交易统计 (trade_count/win_count/total_profit)

策略由调用方 (backtest_engine) 通过 _InjectedStrategy 在构造后注入。
网关自身不持有也不加载任何默认策略。

vn.py 为强制依赖。
"""

import logging
from typing import Dict, Any

from vnpy_ctastrategy import CtaTemplate
from vnpy.trader.object import BarData, TickData, OrderData, TradeData

from ..core.base import TradeRecord as CoreTradeRecord

logger = logging.getLogger(__name__)


class VnpyStrategyGateway(CtaTemplate):

    """vn.py 策略网关 - 将任意 Strategy 接口实现适配为 vnpy CtaTemplate


    self._core 和 self.price_tick 由 _InjectedStrategy (定义在 backtest_engine)
    在 __init__ 返回后注入，网关本身不加载任何默认策略。

    vnpy 通过 add_strategy(cls, setting) 传入 4 个参数，这是 vnpy 框架强制约定。
    """

    author = "Quant System"

    parameters = ["price_tick"]
    variables = ["pos", "entry_price"]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict):
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.price_tick = setting.get('price_tick', 1.0)
        self.entry_price: float = 0.0
        self._close_history: list = []
        self.trade_count: int = 0
        self.win_count: int = 0
        self.total_profit: float = 0.0

    def on_init(self) -> None:
        cfg = self._core.config
        logger.info(f"[{self.strategy_name}] 策略初始化: {self._core.name}")
        self.write_log(f"策略初始化: {self._core.name}")
        self.load_bar(getattr(cfg, 'sma_long', 20))

    def on_start(self) -> None:
        logger.info(f"[{self.strategy_name}] 策略启动")
        self.write_log("策略启动")

    def on_stop(self) -> None:
        logger.info(
            f"[{self.strategy_name}] 策略停止 | "
            f"交易{self.trade_count}次 胜{self.win_count} "
            f"总盈亏{self.total_profit:.2f}"
        )
        self.write_log(f"策略停止: 交易{self.trade_count}次 总盈亏{self.total_profit:.2f}")

    def on_bar(self, bar: Any) -> None:
        close_price = bar.close_price if hasattr(bar, 'close_price') else bar.get('close_price', 0)
        self._close_history.append(close_price)

        signal, reason = self._core.on_bar_signal(self._close_history, close_price)

        if signal == 'buy' and self.pos == 0:
            self._execute_buy(bar)
        elif signal == 'sell' and self.pos > 0:
            self._execute_sell(bar, reason)

    def _execute_buy(self, bar: Any) -> None:
        volume = self._core.calc_position_size(
            bar.close_price,
            self.cta_engine.capital if hasattr(self.cta_engine, 'capital') else 100000,
        )
        if volume <= 0:
            return
        self.buy(bar.close_price, volume)
        self.entry_price = bar.close_price
        self._core.on_enter(bar.close_price, volume)
        self.trade_count += 1
        logger.info(
            f"[{self.strategy_name}] {bar.datetime} 买入 "
            f"@{bar.close_price:.2f} x{volume}"
        )

    def _execute_sell(self, bar: Any, reason: str) -> None:
        pos = abs(self.pos)
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

    def on_tick(self, tick: Any) -> None:
        pass

    def on_order(self, order: Any) -> None:
        super().on_order(order)

    def on_trade(self, trade: Any) -> None:
        super().on_trade(trade)

    def get_performance(self) -> Dict[str, Any]:
        return {
            'trade_count': self.trade_count,
            'win_count': self.win_count,
            'lose_count': self.trade_count - self.win_count,
            'win_rate': self.win_count / max(self.trade_count, 1),
            'total_profit': self.total_profit,
        }