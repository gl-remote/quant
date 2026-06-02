"""vn.py 桥接器 — 将 Strategy 接口桥接到 vnpy CtaTemplate

桥接器负责:
  1. 集成 runtime 数据管理架构 (DataFeed setup, 数据加载, BarContext 构造)
  2. vnpy BarData → 标准 Bar 的数据转换
  3. 调用 strategy.on_bar(state, ctx) 获取 Signal
  4. Signal → vnpy self.buy()/self.sell() 的下单翻译
  5. 通过 on_trade 同步成交状态到 State，回调 strategy.on_fill

strategy 和 state 由 backtest_engine 通过 _InjectedStrategy 在构造后注入。
vn.py 为强制依赖。
采用注入模式是因为 vn.py 回测引擎要求传入策略类而非实例，引擎内部会自行创建对象实例。
"""

import logging
from datetime import datetime
from typing import Any, Optional, cast

import pandas as pd
from vnpy_ctastrategy import CtaTemplate

from strategies import Bar, Signal, Fill, Strategy, UninitializedStrategy, State
from strategies.core.types import StrategyPosition
from strategies.runtime import DataFeedCache, build_context, DataRequirements
from common.constants import TRADE_ACTION_BUY, TRADE_ACTION_SELL, TRADE_DIRECTION_LONG
from common.types import TradeAction, PositionDirection
from data.manager import DataManager

logger = logging.getLogger(__name__)


class VnpyStrategyBridge(CtaTemplate):
    """vn.py 策略桥接器 — 集成 runtime 数据管理架构

    持有 State 和 Strategy，通过 on_trade 同步 vnpy 成交状态到 State。
    """

    author = "Quant System"
    parameters = ["price_tick"]
    variables = ["pos", "entry_price"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._core: Strategy[Any] = UninitializedStrategy()
        self._state: State = State(symbol="", period="", strategy_config=None)
        self._requirements: Optional[DataRequirements] = None
        self._data_feed: Any = None
        self.entry_price: float = 0.0

    def is_initialized(self) -> bool:
        return self._core.name != "_uninitialized"

    # ---- vnpy 生命周期 ----

    def on_init(self) -> None:
        if not self.is_initialized():
            logger.error(f"[{self.strategy_name}] strategy 未注入，初始化跳过")
            return

        logger.info(f"[{self.strategy_name}] 桥接器初始化: {self._core.name}")

        self._requirements = self._core.data_requirements(self._state.strategy_config)
        if self._requirements is None:
            logger.warning(f"[{self.strategy_name}] 策略未声明数据需求")
            self.write_log(f"策略初始化: {self._core.name}")
            self.load_bar(20)
            return

        cache = DataFeedCache.get_instance()
        data_feed = cache.setup(self._state.symbol, self._requirements)

        self._load_non_main_periods(data_feed)
        data_feed.calculate_all()
        self._data_feed = data_feed

        self.write_log(f"策略初始化: {self._core.name}")
        self.load_bar(20)

    def _load_non_main_periods(self, data_feed: Any) -> None:
        if self._requirements is None:
            return
        main_period = self._state.period
        dm = DataManager()
        for period in self._requirements.periods:
            if period == main_period:
                continue
            results = dm.load_kline([self._state.symbol], interval=period)
            for _symbol, df, _data_src in results:
                if len(df) > 0:
                    df_indexed = df.set_index('datetime')
                    data_feed.load_history_df(period, df_indexed)

    def on_start(self) -> None:
        logger.info(f"[{self.strategy_name}] 桥接器启动")
        self.write_log("策略启动")

    def on_stop(self) -> None:
        fills_count = len(self._state.fills)
        sells = len([f for f in self._state.fills if f.action == TRADE_ACTION_SELL])
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

        if self._data_feed is not None and self._requirements is not None:
            self._data_feed.update_bar(standardized, self._state.period)
            ctx = build_context(self._data_feed, self._requirements,
                                pd.Timestamp(standardized.datetime), standardized)
            signal = self._core.on_bar(self._state, ctx)
        else:
            signal = Signal()

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

    def _execute_sell(self, signal: Signal, bar: Bar) -> None:
        pos = abs(self.pos)
        if pos <= 0:
            return
        self.sell(bar.close, pos)
        self.entry_price = 0.0
        logger.info(
            f"[{self.strategy_name}] {bar.datetime} {signal.reason}卖出 "
            f"@{bar.close:.2f}"
        )

    # ---- vnpy 回调 ----

    def on_tick(self, tick: Any) -> None:
        pass

    def on_order(self, order: Any) -> None:
        super().on_order(order)

    def on_trade(self, trade: Any) -> None:
        super().on_trade(trade)

        direction = getattr(trade, 'direction', None)
        trade_price = float(getattr(trade, 'price', 0))
        trade_volume = float(getattr(trade, 'volume', 0))
        trade_datetime = getattr(trade, 'datetime', datetime.now())

        if direction is not None:
            if hasattr(direction, 'value'):
                is_long = (direction.value == TRADE_DIRECTION_LONG)
            else:
                is_long = (str(direction).upper() == TRADE_DIRECTION_LONG) if isinstance(direction, str) else False

            if is_long:
                fill = Fill(
                    timestamp=str(trade_datetime),
                    symbol=self._state.symbol,
                    action=cast(TradeAction, TRADE_ACTION_BUY),
                    price=trade_price,
                    volume=trade_volume,
                    reason="",
                )
                self._state.position = StrategyPosition(
                    direction=cast(PositionDirection, TRADE_DIRECTION_LONG),
                    entry_price=trade_price,
                    volume=trade_volume,
                )
            else:
                fill = Fill(
                    timestamp=str(trade_datetime),
                    symbol=self._state.symbol,
                    action=cast(TradeAction, TRADE_ACTION_SELL),
                    price=trade_price,
                    volume=trade_volume,
                    reason="",
                )
                self._state.position = StrategyPosition()

            self._state.fills.append(fill)
            self._core.on_fill(fill)
