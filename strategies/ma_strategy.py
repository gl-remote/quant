"""均线交叉策略 — 完整的自包含策略核心

支持两种模式:
  1. 兼容模式（默认）: 使用内部 _close_history 缓存
  2. 新数据管理模式: 通过 data_requirements() 声明需求，使用 BarContext

Bridge 只需: 构造 Bar → 调用 on_bar() → 拿到 Signal → 执行下单 → 回调 on_fill()
成交记录 (fills) 由 Bridge 管理，策略只更新仓位。
"""

from dataclasses import dataclass
from typing import Any, Optional, cast
from typing_extensions import override

from strategies import (
    CORE_VERSION, Strategy, Bar, Signal, Fill, StrategyPosition,
    DataRequirements, PeriodRequirements, IndicatorRequirements, EventsRequirements,
    BarContext,
)
from common.constants import (
    TRADE_ACTION_BUY,
    TRADE_ACTION_SELL,
    TRADE_DIRECTION_LONG,
    SIGNAL_STOP_LOSS,
    SIGNAL_TAKE_PROFIT,
    SIGNAL_DEATH_CROSS,
    SIGNAL_GOLDEN_CROSS,
    STRATEGY_MA,
    DEFAULT_SMA_SHORT,
    DEFAULT_SMA_LONG,
    DEFAULT_STOP_LOSS_RATIO,
    DEFAULT_TAKE_PROFIT_RATIO,
    DEFAULT_POSITION_RATIO,
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_CONTRACT_SIZE,
)
from common.formulas import (
    simple_moving_average,
    golden_cross,
    death_cross,
    stop_loss_triggered,
    take_profit_triggered,
    position_size,
)


@dataclass
class MACrossParams:
    """均线交叉策略参数

    纯策略参数，不存环境数据 (capital/contract_size 由 MaStrategyCore 管理)。
    """
    sma_short: int = DEFAULT_SMA_SHORT
    sma_long: int = DEFAULT_SMA_LONG
    stop_loss_ratio: float = DEFAULT_STOP_LOSS_RATIO
    take_profit_ratio: float = DEFAULT_TAKE_PROFIT_RATIO
    position_ratio: float = DEFAULT_POSITION_RATIO
    use_data_feed: bool = False  # 是否使用新的数据管理系统


class MaStrategyCore(Strategy[MACrossParams]):
    """均线交叉策略核心

    负责全部业务逻辑，Bridge 仅做数据转换和下单执行。

    构造时接受策略参数和环境数据。
    """

    name: str = STRATEGY_MA
    VERSION: str = f"{CORE_VERSION}-ma2"  # 更新版本号以反映新功能

    def __init__(self, strategy_params: dict[str, Any] | None = None,
                 capital: float | None = None,
                 contract_size: int | None = None):
        if strategy_params is not None:
            self._config = MACrossParams(
                sma_short=strategy_params.get('sma_short', DEFAULT_SMA_SHORT),
                sma_long=strategy_params.get('sma_long', DEFAULT_SMA_LONG),
                stop_loss_ratio=strategy_params.get('stop_loss_ratio', DEFAULT_STOP_LOSS_RATIO),
                take_profit_ratio=strategy_params.get('take_profit_ratio', DEFAULT_TAKE_PROFIT_RATIO),
                position_ratio=strategy_params.get('position_ratio', DEFAULT_POSITION_RATIO),
                use_data_feed=strategy_params.get('use_data_feed', False),
            )
        else:
            self._config = MACrossParams()
        self._capital = float(capital) if capital is not None else float(DEFAULT_INITIAL_CAPITAL)
        self._contract_size = int(contract_size) if contract_size is not None else int(DEFAULT_CONTRACT_SIZE)

        self._position = StrategyPosition()
        # 兼容模式的状态
        self._close_history: list[float] = []
        self._prev_sma_short: float = 0.0
        self._prev_sma_long: float = 0.0

    # ---- Strategy 接口 ----

    @override
    def data_requirements(self) -> Optional[DataRequirements]:
        """策略的数据需求声明 — 新数据管理模式

        只有当 use_data_feed=True 时才返回需求声明，否则保持兼容模式。
        """
        if not self._config.use_data_feed:
            return None

        # 声明所需的周期、指标和事件
        return DataRequirements(
            periods={
                "1m": PeriodRequirements(lookback_bars=max(self._config.sma_short, self._config.sma_long) + 1),
            },
            indicators={
                "1m": [
                    IndicatorRequirements(name="sma", params={"period": self._config.sma_short}),
                    IndicatorRequirements(name="sma", params={"period": self._config.sma_long}),
                ],
            },
            events=EventsRequirements.no_events(),
        )

    @property
    @override
    def config(self) -> MACrossParams:
        return self._config

    @config.setter
    def config(self, value: MACrossParams) -> None:
        self._config = value

    @property
    @override
    def position(self) -> StrategyPosition:
        return self._position

    @override
    def reset(self) -> None:
        self._position = StrategyPosition()
        self._close_history.clear()
        self._prev_sma_short = 0.0
        self._prev_sma_long = 0.0

    @override
    def on_bar(self, bar: Bar, ctx: Optional[BarContext] = None) -> Signal:
        """处理一根K线 — 策略决策中枢

        支持两种模式:
          1. 兼容模式 (ctx 为 None): 使用内部 _close_history 缓存
          2. 新数据管理模式 (ctx 不为 None): 使用预计算的指标

        步骤:
          1. 获取 SMA 值（从 ctx 或内部计算）
          2. 交叉检测
          3. 风控检查 (持仓时的止损/止盈)
          4. 生成完整 Signal (含预计算手数)
        """
        if self._config.use_data_feed and ctx is not None:
            # 使用新数据管理系统
            return self._on_bar_with_data_feed(bar, ctx)
        else:
            # 兼容模式
            return self._on_bar_compatible(bar)

    def _on_bar_compatible(self, bar: Bar) -> Signal:
        """兼容模式的 on_bar 实现"""
        self._close_history.append(bar.close)

        cur_short = self._calc_sma(self._config.sma_short)
        cur_long = self._calc_sma(self._config.sma_long)

        signal = Signal()

        if self._position.direction == TRADE_DIRECTION_LONG:
            if self._check_stop_loss(bar.close):
                signal = Signal(action=cast(Any, TRADE_ACTION_SELL), reason=SIGNAL_STOP_LOSS,
                                volume=self._position.volume)
            elif self._check_take_profit(bar.close):
                signal = Signal(action=cast(Any, TRADE_ACTION_SELL), reason=SIGNAL_TAKE_PROFIT,
                                volume=self._position.volume)
            elif self._is_death_cross(cur_short, cur_long):
                signal = Signal(action=cast(Any, TRADE_ACTION_SELL), reason=SIGNAL_DEATH_CROSS,
                                volume=self._position.volume)
        else:
            if self._is_golden_cross(cur_short, cur_long):
                vol = self._calc_position_size(bar.close)
                signal = Signal(action=cast(Any, TRADE_ACTION_BUY), reason=SIGNAL_GOLDEN_CROSS, volume=vol)

        self._prev_sma_short = cur_short
        self._prev_sma_long = cur_long
        return signal

    def _on_bar_with_data_feed(self, bar: Bar, ctx: BarContext) -> Signal:
        """新数据管理模式的 on_bar 实现"""
        # 从 ctx 获取预计算的指标
        view = ctx.multi["1m"]
        sma_short_col = f"sma_{self._config.sma_short}"
        sma_long_col = f"sma_{self._config.sma_long}"

        # 获取当前和前一个值
        cur_short = view.indicator(sma_short_col, -1) or 0.0
        cur_long = view.indicator(sma_long_col, -1) or 0.0
        prev_short = view.indicator(sma_short_col, -2) or 0.0
        prev_long = view.indicator(sma_long_col, -2) or 0.0

        signal = Signal()

        if self._position.direction == TRADE_DIRECTION_LONG:
            if self._check_stop_loss(bar.close):
                signal = Signal(action=cast(Any, TRADE_ACTION_SELL), reason=SIGNAL_STOP_LOSS,
                                volume=self._position.volume)
            elif self._check_take_profit(bar.close):
                signal = Signal(action=cast(Any, TRADE_ACTION_SELL), reason=SIGNAL_TAKE_PROFIT,
                                volume=self._position.volume)
            elif self._is_death_cross(cur_short, cur_long, prev_short, prev_long):
                signal = Signal(action=cast(Any, TRADE_ACTION_SELL), reason=SIGNAL_DEATH_CROSS,
                                volume=self._position.volume)
        else:
            if self._is_golden_cross(cur_short, cur_long, prev_short, prev_long):
                vol = self._calc_position_size(bar.close)
                signal = Signal(action=cast(Any, TRADE_ACTION_BUY), reason=SIGNAL_GOLDEN_CROSS, volume=vol)

        return signal

    @override
    def on_fill(self, fill: Fill) -> None:
        """成交回执 — Bridge 在下单成交后调用"""
        if fill.action == TRADE_ACTION_BUY:
            self._position = StrategyPosition(
                direction=cast(Any, TRADE_DIRECTION_LONG),
                entry_price=fill.price,
                volume=fill.volume,
            )
        elif fill.action == TRADE_ACTION_SELL:
            self._position = StrategyPosition()

    # ---- 内部算法 ----

    def _calc_sma(self, period: int) -> float:
        """兼容模式的 SMA 计算"""
        return simple_moving_average(self._close_history, period)

    def _is_golden_cross(self, cur_short: float, cur_long: float,
                        prev_short: Optional[float] = None, prev_long: Optional[float] = None) -> bool:
        """金叉检测 — 支持两种模式

        兼容模式: 使用内部 _prev_sma_short/_prev_sma_long
        新数据模式: 使用传入的 prev_short/prev_long
        """
        if prev_short is None:
            prev_short = self._prev_sma_short
        if prev_long is None:
            prev_long = self._prev_sma_long

        return golden_cross(prev_short, prev_long, cur_short, cur_long)

    def _is_death_cross(self, cur_short: float, cur_long: float,
                        prev_short: Optional[float] = None, prev_long: Optional[float] = None) -> bool:
        """死叉检测 — 支持两种模式"""
        if prev_short is None:
            prev_short = self._prev_sma_short
        if prev_long is None:
            prev_long = self._prev_sma_long

        return death_cross(prev_short, prev_long, cur_short, cur_long)

    def _check_stop_loss(self, current_price: float) -> bool:
        return stop_loss_triggered(self._position.entry_price, current_price,
                                   self._config.stop_loss_ratio)

    def _check_take_profit(self, current_price: float) -> bool:
        return take_profit_triggered(self._position.entry_price, current_price,
                                     self._config.take_profit_ratio)

    def _calc_position_size(self, price: float) -> int:
        return position_size(self._capital, self._config.position_ratio,
                             price, self._contract_size)
