"""vn.py 桥接器 — 将 Strategy 接口桥接到 vnpy CtaTemplate

桥接器仅负责:
  1. vnpy BarData → 标准 Bar 的数据转换
  2. 调用 strategy.on_bar(bar) 获取 Signal
  3. Signal → vnpy self.buy()/self.sell() 的下单翻译
  4. 成交后回调 strategy.on_fill(fill)

所有交易状态 (仓位/记录/绩效) 由 Strategy 管理，桥接器不持有任何交易状态。

strategy 由 backtest_engine 通过 _InjectedStrategy 在构造后注入。
vn.py 为强制依赖。
"""

import logging
from datetime import datetime
from typing import Any

from vnpy_ctastrategy import CtaTemplate

from strategies import Bar, Signal, Fill, Strategy, UninitializedStrategy
from common.constants import TRADE_ACTION_BUY, TRADE_ACTION_SELL

logger = logging.getLogger(__name__)


class VnpyStrategyBridge(CtaTemplate):
    """vn.py 策略桥接器 — 纯协议转换层

    self._core (Strategy 实例) 由
    _InjectedStrategy (backtest_engine) 在 __init__ 后注入。
    """

    author = "Quant System"
    parameters = ["price_tick"]
    variables = ["pos", "entry_price"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._core: Strategy[Any] = UninitializedStrategy()
        self._fills: list[Fill] = []
        self.entry_price: float = 0.0

    @property
    def fills(self) -> list[Fill]:
        return list(self._fills)

    # ---- vnpy 生命周期 ----

    def on_init(self) -> None:
        if self._core.name == "_uninitialized":
            logger.error(f"[{self.strategy_name}] strategy 未注入，初始化跳过")
            return
        logger.info(f"[{self.strategy_name}] 桥接器初始化: {self._core.name}")
        self.write_log(f"策略初始化: {self._core.name}")
        self.load_bar(20)

    def on_start(self) -> None:
        logger.info(f"[{self.strategy_name}] 桥接器启动")
        self.write_log("策略启动")

    def on_stop(self) -> None:
        fills_count = len(self._fills)
        sells = len([f for f in self._fills if f.action == TRADE_ACTION_SELL])
        logger.info(
            f"[{self.strategy_name}] 策略停止 | "
            f"fills={fills_count} sells={sells}"
        )
        self.write_log(
            f"策略停止: fills={fills_count} sells={sells}"
        )

    # ---- 核心: 数据转换 → 信号获取 → 下单执行 ----

    def on_bar(self, bar: Any) -> None:
        standardized = self._vnpy_bar_to_bar(bar)
        signal = self._core.on_bar(standardized)

        if signal.action == TRADE_ACTION_BUY and self.pos == 0:
            self._execute_buy(signal, standardized)
        elif signal.action == TRADE_ACTION_SELL and self.pos > 0:
            self._execute_sell(signal, standardized)

    def _vnpy_bar_to_bar(self, vnpy_bar: Any) -> Bar:
        return Bar(
            symbol=getattr(vnpy_bar, 'symbol', ''),
            datetime=getattr(vnpy_bar, 'datetime', datetime.min),
            open=float(getattr(vnpy_bar, 'open_price', 0)),
            high=float(getattr(vnpy_bar, 'high_price', 0)),
            low=float(getattr(vnpy_bar, 'low_price', 0)),
            close=float(getattr(vnpy_bar, 'close_price', 0)),
            volume=float(getattr(vnpy_bar, 'volume', 0)),
        )

    def _execute_buy(self, signal: Signal, bar: Bar) -> None:
        volume = signal.volume
        if volume <= 0:
            return
        self.buy(bar.close, volume)
        self.entry_price = bar.close
        logger.info(
            f"[{self.strategy_name}] {bar.datetime} 买入 "
            f"@{bar.close:.2f} x{volume}"
        )
        fill = Fill(
            timestamp=str(bar.datetime),
            symbol=bar.symbol,
            action=TRADE_ACTION_BUY,
            price=bar.close,
            volume=volume,
            reason=signal.reason,
        )
        self._fills.append(fill)
        self._core.on_fill(fill)

    def _execute_sell(self, signal: Signal, bar: Bar) -> None:
        pos = abs(self.pos)
        if pos <= 0:
            return
        self.sell(bar.close, pos)
        profit = (bar.close - self.entry_price) * pos
        self.entry_price = 0.0
        logger.info(
            f"[{self.strategy_name}] {bar.datetime} {signal.reason}卖出 "
            f"@{bar.close:.2f} 盈亏{profit:.2f}"
        )
        fill = Fill(
            timestamp=str(bar.datetime),
            symbol=bar.symbol,
            action=TRADE_ACTION_SELL,
            price=bar.close,
            volume=pos,
            reason=signal.reason,
        )
        self._fills.append(fill)
        self._core.on_fill(fill)

    # ---- vnpy 回调 (透传) ----

    def on_tick(self, tick: Any) -> None:
        pass

    def on_order(self, order: Any) -> None:
        super().on_order(order)

    def on_trade(self, trade: Any) -> None:
        super().on_trade(trade)
