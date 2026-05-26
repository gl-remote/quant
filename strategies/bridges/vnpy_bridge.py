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
from typing import Any

from vnpy_ctastrategy import CtaTemplate

from ..core.types import Bar, Signal, Fill

logger = logging.getLogger(__name__)


class VnpyStrategyBridge(CtaTemplate):
    """vn.py 策略桥接器 — 纯协议转换层

    self._core (Strategy 实例) 和 self.price_tick 由
    _InjectedStrategy (backtest_engine) 在 __init__ 后注入。
    """

    author = "Quant System"
    parameters = ["price_tick"]
    variables = ["pos", "entry_price"]

    def __init__(self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict):
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self._core: Any | None = None
        self.price_tick = setting.get('price_tick', 1.0)
        self.entry_price: float = 0.0
        self._strategy_name = strategy_name

    # ---- vnpy 生命周期 ----

    def on_init(self) -> None:
        if self._core is None:
            logger.error(f"[{self._strategy_name}] strategy 未注入，初始化跳过")
            return
        logger.info(f"[{self._strategy_name}] 桥接器初始化: {self._core.name}")
        self.write_log(f"策略初始化: {self._core.name}")
        self.load_bar(20)

    def on_start(self) -> None:
        logger.info(f"[{self._strategy_name}] 桥接器启动")
        self.write_log("策略启动")

    def on_stop(self) -> None:
        fills_count = len(self._core.fills) if self._core else 0
        sells = len([f for f in self._core.fills if f.action == 'sell']) if self._core else 0
        logger.info(
            f"[{self._strategy_name}] 策略停止 | "
            f"fills={fills_count} sells={sells}"
        )
        self.write_log(
            f"策略停止: fills={fills_count} sells={sells}"
        )

    # ---- 核心: 数据转换 → 信号获取 → 下单执行 ----

    def on_bar(self, bar: Any) -> None:
        if self._core is None:
            return

        standardized = self._vnpy_bar_to_bar(bar)
        signal = self._core.on_bar(standardized)

        if signal.action == 'buy' and self.pos == 0:
            self._execute_buy(signal, standardized)
        elif signal.action == 'sell' and self.pos > 0:
            self._execute_sell(signal, standardized)

    def _vnpy_bar_to_bar(self, vnpy_bar: Any) -> Bar:
        return Bar(
            symbol=getattr(vnpy_bar, 'symbol', ''),
            datetime=str(getattr(vnpy_bar, 'datetime', '')),
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
            f"[{self._strategy_name}] {bar.datetime} 买入 "
            f"@{bar.close:.2f} x{volume}"
        )
        self._core.on_fill(Fill(
            timestamp=bar.datetime,
            symbol=bar.symbol,
            action='buy',
            price=bar.close,
            volume=volume,
            reason=signal.reason,
        ))

    def _execute_sell(self, signal: Signal, bar: Bar) -> None:
        pos = abs(self.pos)
        if pos <= 0:
            return
        self.sell(bar.close, pos)
        profit = (bar.close - self.entry_price) * pos
        self.entry_price = 0.0
        logger.info(
            f"[{self._strategy_name}] {bar.datetime} {signal.reason}卖出 "
            f"@{bar.close:.2f} 盈亏{profit:.2f}"
        )
        self._core.on_fill(Fill(
            timestamp=bar.datetime,
            symbol=bar.symbol,
            action='sell',
            price=bar.close,
            volume=pos,
            reason=signal.reason,
        ))

    # ---- vnpy 回调 (透传) ----

    def on_tick(self, tick: Any) -> None:
        pass

    def on_order(self, order: Any) -> None:
        super().on_order(order)

    def on_trade(self, trade: Any) -> None:
        super().on_trade(trade)
