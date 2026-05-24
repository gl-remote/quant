"""vn.py 桥接器 - 将 Strategy 接口实现桥接到 vnpy CtaTemplate

桥接器职责 (纯粹的桥接层):
  - 将 vnpy BarData 转换后传递给 Strategy.on_bar_signal()
  - 将 Strategy 返回的信号 (buy/sell) 转换为 vnpy self.buy() / self.sell()
  - 记录交易统计 (trade_count/win_count/total_profit)

策略由调用方 (backtest_engine) 通过 _InjectedStrategy 在构造后注入。
桥接器自身不持有也不加载任何默认策略。

vn.py 为强制依赖。
"""

import logging
from typing import Dict, Any, Optional

from vnpy_ctastrategy import CtaTemplate

logger = logging.getLogger(__name__)


class VnpyStrategyBridge(CtaTemplate):

    """vn.py 策略桥接器 - 将任意 Strategy 接口实现桥接到 vnpy CtaTemplate


    self._core 和 self.price_tick 由 _InjectedStrategy (定义在 backtest_engine)
    在 __init__ 返回后注入，桥接器本身不加载任何默认策略。

    vnpy 通过 add_strategy(cls, setting) 传入 4 个参数，这是 vnpy 框架强制约定。
    """

    author = "Quant System"

    parameters = ["price_tick"]
    variables = ["pos", "entry_price"]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict):
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self._core: Optional[Any] = None
        self.price_tick = setting.get('price_tick', 1.0)
        self.entry_price: float = 0.0
        self._close_history: list = []
        self.trade_count: int = 0
        self.win_count: int = 0
        self.total_profit: float = 0.0

    def on_init(self) -> None:
        if self._core is None:
            logger.error(f"[{self.strategy_name}] _core 未注入，初始化跳过")
            return
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
        if self._core is None:
            return
        close_price = bar.close_price if hasattr(bar, 'close_price') else bar.get('close_price', 0)
        bar_dt = getattr(bar, 'datetime', None)
        self._close_history.append(close_price)

        signal, reason = self._core.on_bar_signal(self._close_history, close_price)

        if signal == 'buy' and self.pos == 0:
            self._execute_buy(close_price, bar_dt)
        elif signal == 'sell' and self.pos > 0:
            self._execute_sell(close_price, reason, bar_dt)

    def _execute_buy(self, price: float, bar_dt: Any) -> None:
        capital = self.cta_engine.capital if hasattr(self.cta_engine, 'capital') else 100000
        volume = self._core.calc_position_size(price, capital)
        if volume <= 0:
            return
        self.buy(price, volume)
        self.entry_price = price
        self._core.on_enter(price, volume)
        self.trade_count += 1
        logger.info(
            f"[{self.strategy_name}] {bar_dt} 买入 "
            f"@{price:.2f} x{volume}"
        )

    def _execute_sell(self, price: float, reason: str, bar_dt: Any) -> None:
        pos = abs(self.pos)
        self.sell(price, pos)
        profit = self._core.on_exit(price)
        self.total_profit += profit
        self.entry_price = 0.0
        if profit > 0:
            self.win_count += 1
        logger.info(
            f"[{self.strategy_name}] {bar_dt} {reason}卖出 "
            f"@{price:.2f} 盈亏{profit:.2f}"
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
