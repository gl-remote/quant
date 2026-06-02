"""vn.py 桥接器模块

将 Strategy 接口桥接到 vnpy CtaTemplate，是整个架构的核心适配层。

重构背景:
- 旧架构：Bridge 只做简单的数据转换，Strategy 自己管理状态
- 新架构：Bridge 集成 runtime 数据管理架构，统一管理 State

核心职责:
  1. 集成 runtime 数据管理架构 (DataFeed setup, 数据加载, BarContext 构造)
  2. vnpy BarData → 标准 Bar 的数据转换
  3. 调用 strategy.on_bar(state, ctx) 获取 Signal
  4. Signal → vnpy self.buy()/self.sell() 的下单翻译
  5. 通过 on_trade 同步成交状态到 State，回调 strategy.on_fill

设计说明:
- strategy 和 state 由 backtest_engine 通过 _InjectedStrategy 在构造后注入
- vn.py 为强制依赖
- 采用注入模式是因为 vn.py 回测引擎要求传入策略类而非实例，引擎内部会自行创建对象实例
"""

from loguru import logger
from datetime import datetime
from typing import Any, Optional, cast

import pandas as pd
from vnpy_ctastrategy import CtaTemplate

from strategies import Bar, Signal, Fill, Strategy, UninitializedStrategy, State
from strategies.core.types import StrategyPosition
from strategies.runtime import DataFeed, DataRequirements
from strategies.runtime.requirements import BarContext
from strategies.runtime.period import PeriodDataView
from common.constants import TRADE_ACTION_BUY, TRADE_ACTION_SELL, TRADE_DIRECTION_LONG
from common.types import TradeAction, PositionDirection
from data.manager import DataManager

class VnpyStrategyBridge(CtaTemplate):
    """vn.py 策略桥接器 — 集成 runtime 数据管理架构

    【设计理念】
    Bridge 是连接 vnpy 引擎和我们 Strategy 之间的适配层：
    - 向下：适配 vnpy 的 CtaTemplate 接口
    - 向上：适配我们的 Strategy 接口
    - 中间：管理 State 和 DataFeed

    【核心持有】
    - _core: Strategy 实例，纯决策逻辑
    - _state: State 实例，所有运行时数据
    - _data_feed: DataFeed 实例，行情数据管理
    - _requirements: DataRequirements，缓存的数据需求

    【状态同步】
    - vnpy 的 pos: vnpy 引擎的持仓（只读，用于下单检查）
    - _state.position: 我们的持仓（由 Bridge 在 on_trade 中更新）
    - 两者数据同源，但用途不同
    """

    author = "Quant System"
    parameters = ["price_tick"]
    variables = ["pos", "entry_price"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """初始化桥接器 — 构造空的 _core 和 _state

        【注入模式】
        因为 vnpy 回测引擎要求传入策略类而非实例，引擎内部会自行创建对象。
        所以我们在 __init__ 中构造空的占位符，然后由外部（_InjectedStrategy）注入真实的 _core 和 _state。

        【占位符说明】
        - _core: 初始化为 UninitializedStrategy，调用时会报错提示未注入
        - _state: 初始化为空的 State，参数由外部注入
        """
        super().__init__(*args, **kwargs)
        self._core: Strategy[Any] = UninitializedStrategy()
        self._state: State[Any] = State(symbol="", period="", strategy_config=None)
        self._requirements: Optional[DataRequirements] = None
        self._data_feed: Any = None
        self._ctx_cache: dict[pd.Timestamp, BarContext] = {}
        self.entry_price: float = 0.0

    def is_initialized(self) -> bool:
        """检查策略是否已初始化（注入）

        :return: 是否已注入真实的 Strategy
        """
        return self._core.name != "_uninitialized"

    # ---- vnpy 生命周期 ----

    def on_init(self) -> None:
        """vnpy 初始化回调 — 预加载数据、预计算指标、预构造上下文

        on_bar 中只做 O(1) 的 dict 查找，零重算、零时间戳搜索。
        """
        if not self.is_initialized():
            logger.error(f"[{self.strategy_name}] strategy 未注入，初始化跳过")
            return

        logger.info(f"[{self.strategy_name}] 桥接器初始化: {self._core.name}")

        self._requirements = self._core.data_requirements(self._state.strategy_config)
        if self._requirements is None:
            self.write_log(f"策略初始化: {self._core.name}")
            self.load_bar(20)
            return

        # 创建 DataFeed，注册周期和指标
        data_feed = DataFeed(symbol=self._state.symbol)
        for period_name in self._requirements.periods:
            data_feed.register_period(period_name)
        for period_name, indicators in self._requirements.indicators.items():
            for indicator in indicators:
                data_feed.register_indicator(period_name, indicator.name, **indicator.params)

        # 加载全部数据并预计算指标（一次性完成）
        self._load_all_periods(data_feed)
        data_feed.calculate_all()
        self._data_feed = data_feed

        # 预构造所有 BarContext：按主周期时间戳逐条构造，存到 dict
        main_period = self._state.period
        main_pd = data_feed.get_period(main_period)
        if main_pd is not None:
            main_df: pd.DataFrame = main_pd._df  # pyright: ignore[reportPrivateUsage]
            for idx in range(len(main_df)):
                ts: pd.Timestamp = main_df.index[idx]  # type: ignore[assignment]
                row = main_df.iloc[idx]
                bar = Bar(
                    symbol=self._state.symbol,
                    datetime=cast(datetime, ts.to_pydatetime()),
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=float(row['volume']),
                )
                multi: dict[str, PeriodDataView] = {}
                for period, req in self._requirements.periods.items():
                    pd_obj = data_feed.get_period(period)
                    if pd_obj is None:
                        continue
                    pdf: pd.DataFrame = pd_obj._df  # pyright: ignore[reportPrivateUsage]
                    end_idx = int(pdf.index.get_indexer(
                        pd.Index([ts]), method='ffill')[0])
                    if end_idx < 0:
                        end_idx = 0
                    start_idx = max(0, end_idx - req.lookback_bars + 1)
                    multi[period] = PeriodDataView(
                        df_ref=pdf,
                        events_ref=None,
                        start_idx=start_idx,
                        end_idx=end_idx,
                        current_time=ts,
                        period=period,
                    )
                self._ctx_cache[ts] = BarContext(
                    symbol=self._state.symbol,
                    bar=bar,
                    multi=multi,
                    events=[],
                )

        self.write_log(f"策略初始化: {self._core.name}")
        self.load_bar(20)

    def _load_all_periods(self, data_feed: Any) -> None:
        """加载所有周期的历史数据（包括主周期）

        从 DataManager 一次性加载所有周期的完整数据集到 DataFeed，
        用于预计算指标，避免在 vnpy 逐根回放时重复计算。
        """
        if self._requirements is None:
            return

        dm = DataManager()

        for period in self._requirements.periods:
            results = dm.load_kline([self._state.symbol], interval=period)
            for _symbol, df, _data_src in results:
                if len(df) > 0:
                    df_indexed = df.set_index('datetime')
                    data_feed.load_history_df(period, df_indexed)

    def on_start(self) -> None:
        """vnpy 启动回调
        """
        logger.info(f"[{self.strategy_name}] 桥接器启动")
        self.write_log("策略启动")

    def on_stop(self) -> None:
        """vnpy 停止回调 — 记录策略停止时的统计信息
        """
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
        """vnpy K线回调 — 从预构造缓存中 O(1) 获取上下文

        所有重活（数据加载、指标计算、上下文构造）已在 on_init 完成，
        此处仅做 dict 查找 + 策略调用 + 下单。
        """
        raw_dt: Any = getattr(bar, 'datetime', None)
        if raw_dt is None:
            return
        bar_time = cast(pd.Timestamp, pd.Timestamp(raw_dt))

        ctx = self._ctx_cache.get(bar_time)
        if ctx is not None:
            signal = self._core.on_bar(self._state, ctx)
        else:
            signal = Signal()

        close_price = float(getattr(bar, 'close_price', 0))
        if signal.action == TRADE_ACTION_BUY and self.pos == 0:
            self._execute_buy(signal, close_price, bar_time)
        elif signal.action == TRADE_ACTION_SELL and self.pos > 0:
            self._execute_sell(signal, close_price, bar_time)

    def _execute_buy(self, signal: Signal, price: float, bar_time: pd.Timestamp) -> None:
        """执行买入"""
        volume = signal.volume
        if volume <= 0:
            return
        self.buy(price, volume)
        self.entry_price = price
        logger.debug(
            f"[{self.strategy_name}] {bar_time} 买入 @{price:.2f} x{volume}")

    def _execute_sell(self, signal: Signal, price: float, bar_time: pd.Timestamp) -> None:
        """执行卖出"""
        pos = abs(self.pos)
        if pos <= 0:
            return
        self.sell(price, pos)
        self.entry_price = 0.0
        logger.debug(
            f"[{self.strategy_name}] {bar_time} {signal.reason}卖出 @{price:.2f}")

    # ---- vnpy 回调 ----

    def on_tick(self, tick: Any) -> None:
        """vnpy Tick回调 — 本策略不使用 Tick 数据
        """
        pass

    def on_order(self, order: Any) -> None:
        """vnpy 订单回调 — 委托变化时调用
        """
        super().on_order(order)

    def on_trade(self, trade: Any) -> None:
        """vnpy 成交回调 — 同步成交状态到 State

        【设计说明】
        vnpy 在订单成交后会调用这个回调，我们在这里：
        1. 更新 _state.position（根据成交信息）
        2. 构造 Fill 并追加到 _state.fills
        3. 调用 strategy.on_fill(fill) 通知策略

        【为什么不在 _execute_buy/_execute_sell 中更新 State】
        因为下单不等于成交，只有成交后才是真实的持仓变化。
        vnpy 引擎会在成交后调用 on_trade，这是更新 State 的正确时机。

        【State 是唯一真实来源】
        Strategy 应该从 state.position 读取持仓，而不是自己管理。
        """
        super().on_trade(trade)

        # 从 vnpy Trade 对象提取成交信息
        direction = getattr(trade, 'direction', None)
        trade_price = float(getattr(trade, 'price', 0))
        trade_volume = float(getattr(trade, 'volume', 0))
        trade_datetime = getattr(trade, 'datetime', datetime.now())

        if direction is not None:
            # 判断是买入还是卖出
            if hasattr(direction, 'value'):
                is_long = (direction.value == TRADE_DIRECTION_LONG)
            else:
                is_long = (str(direction).upper() == TRADE_DIRECTION_LONG) if isinstance(direction, str) else False

            if is_long:
                # 买入：更新 position 为多头
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
                # 卖出：清空 position
                fill = Fill(
                    timestamp=str(trade_datetime),
                    symbol=self._state.symbol,
                    action=cast(TradeAction, TRADE_ACTION_SELL),
                    price=trade_price,
                    volume=trade_volume,
                    reason="",
                )
                self._state.position = StrategyPosition()

            # 追加到 fills 列表
            self._state.fills.append(fill)

            # 通知策略成交了
            self._core.on_fill(fill)
