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

from vnpy_ctastrategy import CtaTemplate

from strategies import Bar, Signal, Fill, Strategy, UninitializedStrategy, State
from strategies.core.types import StrategyPosition
from strategies.runtime import DataFeed, build_context, DataRequirements
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
        self.entry_price: float = 0.0

    def is_initialized(self) -> bool:
        """检查策略是否已初始化（注入）

        :return: 是否已注入真实的 Strategy
        """
        return self._core.name != "_uninitialized"

    # ---- vnpy 生命周期 ----

    def on_init(self) -> None:
        """vnpy 初始化回调 — 在这里完成 DataFeed 初始化

        【初始化流程】
        步骤 1: 检查是否已注入 Strategy
        步骤 2: 调用 strategy.data_requirements(config) 获取数据需求
        步骤 3: 从 DataFeedCache 获取或创建 DataFeed
        步骤 4: 加载非主周期的历史数据（DataManager → DataFeed）
        步骤 5: 预计算所有指标
        步骤 6: 调用 vnpy 的 load_bar 加载主周期数据

        【为什么主周期不预加载】
        主周期数据由 vnpy 引擎通过 on_bar 逐根回放，不需要预加载。
        非主周期数据需要预加载，因为 vnpy 引擎不会回放。
        """
        if not self.is_initialized():
            logger.error(f"[{self.strategy_name}] strategy 未注入，初始化跳过")
            return

        logger.info(f"[{self.strategy_name}] 桥接器初始化: {self._core.name}")

        # 获取策略的数据需求
        self._requirements = self._core.data_requirements(self._state.strategy_config)
        if self._requirements is None:
            logger.warning(f"[{self.strategy_name}] 策略未声明数据需求")
            self.write_log(f"策略初始化: {self._core.name}")
            self.load_bar(20)
            return

        # 每个 bridge 创建自己的 DataFeed，不共享，无需缓存/锁
        data_feed = DataFeed(symbol=self._state.symbol)
        for period_name in self._requirements.periods:
            data_feed.register_period(period_name)
        for period_name, indicators in self._requirements.indicators.items():
            for indicator in indicators:
                data_feed.register_indicator(period_name, indicator.name, **indicator.params)

        # 加载非主周期的历史数据
        self._load_non_main_periods(data_feed)

        # 指标不预计算（主周期此时为空），由 get_data 懒加载首次触发
        self._data_feed = data_feed

        self.write_log(f"策略初始化: {self._core.name}")
        self.load_bar(20)

    def _load_non_main_periods(self, data_feed: Any) -> None:
        """加载非主周期的历史数据

        【数据来源】
        从 DataManager（单例）加载，DataManager 已经有缓存，不需要重复加载。

        【为什么非主周期需要预加载】
        - 主周期：由 vnpy 引擎通过 on_bar 逐根回放
        - 非主周期：vnpy 引擎不会回放，所以需要 Bridge 自己预加载

        【优化】
        使用 data_feed.load_history_df() 直接加载 DataFrame，避免 Bar 转换的开销。
        """
        if self._requirements is None:
            return

        main_period = self._state.period
        dm = DataManager()

        for period in self._requirements.periods:
            if period == main_period:
                continue  # 主周期由 vnpy 引擎通过 on_bar 回放，不需要预加载

            # 从 DataManager 加载非主周期数据
            results = dm.load_kline([self._state.symbol], interval=period)
            for _symbol, df, _data_src in results:
                if len(df) > 0:
                    # 直接加载 DataFrame 到 DataFeed（避免 Bar 转换开销）
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
        """vnpy K线回调 — 核心决策流程

        【处理流程】
        步骤 1: 将 vnpy BarData → 标准 Bar
        步骤 2: 调用 DataFeed.update_bar() 更新主周期数据
        步骤 3: 调用 build_context() 构造 BarContext
        步骤 4: 调用 strategy.on_bar(state, ctx) 获取 Signal
        步骤 5: 根据 Signal 执行下单（buy/sell）

        【为什么 build_context 需要传入 bar】
        ctx.bar 就是当前这根 K线，但 build_context 需要显式传入是为了：
        - 明确当前处理的是哪根 K线
        - 避免歧义
        """
        # 将 vnpy BarData 转换为标准 Bar
        standardized = self._vnpy_bar_to_bar(bar)

        if self._data_feed is not None and self._requirements is not None:
            # 更新 DataFeed（主周期数据）
            self._data_feed.update_bar(standardized, self._state.period)

            # 构造 BarContext
            ctx = build_context(
                self._data_feed,
                self._requirements,
                standardized.datetime,  # 直接传 datetime 对象，不需要转换
                standardized  # 显式传入当前 bar
            )

            # 调用策略决策
            signal = self._core.on_bar(self._state, ctx)
        else:
            signal = Signal()

        # 执行下单
        if signal.action == TRADE_ACTION_BUY and self.pos == 0:
            self._execute_buy(signal, standardized)
        elif signal.action == TRADE_ACTION_SELL and self.pos > 0:
            self._execute_sell(signal, standardized)

    def _vnpy_bar_to_bar(self, vnpy_bar: Any) -> Bar:
        """vnpy BarData → 标准 Bar 的数据转换

        【字段映射】
        vnpy 的 open_price → 标准 Bar 的 open
        vnpy 的 high_price → 标准 Bar 的 high
        vnpy 的 low_price → 标准 Bar 的 low
        vnpy 的 close_price → 标准 Bar 的 close
        vnpy 的 volume → 标准 Bar 的 volume

        【为什么需要转换】
        因为我们的 Strategy 接口使用标准 Bar，不依赖 vnpy 的具体实现。
        这样可以方便地适配其他引擎（如 Tqsdk）。

        :param vnpy_bar: vnpy 的 BarData 对象
        :return: 标准 Bar 对象
        """
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
        """执行买入 — 调用 vnpy 的 buy()

        【为什么先检查 self.pos】
        vnpy 的 pos 是 vnpy 引擎的持仓（我们只读，用于检查）
        避免重复下单。

        :param signal: 交易信号
        :param bar: 当前 K线
        """
        volume = signal.volume
        if volume <= 0:
            return
        self.buy(bar.close, volume)
        self.entry_price = bar.close
        logger.debug(
            f"[{self.strategy_name}] {bar.datetime} 买入 "
            f"@{bar.close:.2f} x{volume}"
        )

    def _execute_sell(self, signal: Signal, bar: Bar) -> None:
        """执行卖出 — 调用 vnpy 的 sell()

        【为什么用 self.pos 而不是 state.position】
        self.pos 是 vnpy 引擎的持仓，是最准确的。
        state.position 会在 on_trade 中更新，但 on_trade 在成交后才调用。

        :param signal: 交易信号
        :param bar: 当前 K线
        """
        pos = abs(self.pos)
        if pos <= 0:
            return
        self.sell(bar.close, pos)
        self.entry_price = 0.0
        logger.debug(
            f"[{self.strategy_name}] {bar.datetime} {signal.reason}卖出 "
            f"@{bar.close:.2f}"
        )

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
