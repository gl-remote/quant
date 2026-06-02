"""均线交叉策略 — 纯决策逻辑，不持有状态

所有运行时数据通过 State 获取，所有行情数据通过 BarContext 获取。
Bridge 负责: 构造 Bar → 构造 ctx → 调用 on_bar(state, ctx) → 拿到 Signal → 执行下单。
"""

from dataclasses import dataclass
from typing import Any, Optional, cast
from typing_extensions import override

from strategies import (
    CORE_VERSION, Strategy, Signal, Fill,
    DataRequirements, PeriodRequirements, IndicatorRequirements, EventsRequirements,
    BarContext, State,
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
)
from common.formulas import (
    golden_cross,
    death_cross,
    stop_loss_triggered,
    take_profit_triggered,
    position_size,
)


@dataclass
class MACrossParams:
    """均线交叉策略参数"""
    sma_short: int = DEFAULT_SMA_SHORT
    sma_long: int = DEFAULT_SMA_LONG
    stop_loss_ratio: float = DEFAULT_STOP_LOSS_RATIO
    take_profit_ratio: float = DEFAULT_TAKE_PROFIT_RATIO
    position_ratio: float = DEFAULT_POSITION_RATIO


class MaStrategyCore(Strategy[MACrossParams]):
    """均线交叉策略核心 — 纯决策逻辑

    Bridge 调用流程:
      bridge.on_bar → 构造 BarContext → strategy.on_bar(state, ctx) → Signal
    """

    name: str = STRATEGY_MA
    VERSION: str = f"{CORE_VERSION}-ma3"

    def __init__(self) -> None:
        pass

    # ---- Strategy 接口 ----

    @override
    def data_requirements(self, config: MACrossParams) -> Optional[DataRequirements]:
        """策略的数据需求声明"""
        return DataRequirements(
            periods={
                "1m": PeriodRequirements(lookback_bars=max(config.sma_short, config.sma_long) + 1),
            },
            indicators={
                "1m": [
                    IndicatorRequirements(name="sma", params={"period": config.sma_short}),
                    IndicatorRequirements(name="sma", params={"period": config.sma_long}),
                ],
            },
            events=EventsRequirements.no_events(),
        )

    @override
    def on_bar(self, state: State[MACrossParams], ctx: BarContext) -> Signal:
        """处理一根K线 — 策略决策中枢

        步骤:
          1. 从 ctx 获取预计算的 SMA 指标
          2. 交叉检测
          3. 风控检查 (持仓时的止损/止盈)
          4. 生成完整 Signal (含预计算手数)
        """
        config = state.strategy_config
        view = ctx.multi["1m"]
        sma_short_col = f"sma_{config.sma_short}"
        sma_long_col = f"sma_{config.sma_long}"

        cur_short = view.indicator(sma_short_col, -1) or 0.0
        cur_long = view.indicator(sma_long_col, -1) or 0.0
        prev_short = view.indicator(sma_short_col, -2) or 0.0
        prev_long = view.indicator(sma_long_col, -2) or 0.0

        signal = Signal()

        if state.position.direction == TRADE_DIRECTION_LONG:
            if self._check_stop_loss(state.position.entry_price, ctx.bar.close, config.stop_loss_ratio):
                signal = Signal(action=cast(Any, TRADE_ACTION_SELL), reason=SIGNAL_STOP_LOSS,
                                volume=state.position.volume)
            elif self._check_take_profit(state.position.entry_price, ctx.bar.close, config.take_profit_ratio):
                signal = Signal(action=cast(Any, TRADE_ACTION_SELL), reason=SIGNAL_TAKE_PROFIT,
                                volume=state.position.volume)
            elif self._is_death_cross(cur_short, cur_long, prev_short, prev_long):
                signal = Signal(action=cast(Any, TRADE_ACTION_SELL), reason=SIGNAL_DEATH_CROSS,
                                volume=state.position.volume)
        else:
            if self._is_golden_cross(cur_short, cur_long, prev_short, prev_long):
                vol = self._calc_position_size(ctx.bar.close, state.capital, config.position_ratio,
                                               state.contract_size)
                signal = Signal(action=cast(Any, TRADE_ACTION_BUY), reason=SIGNAL_GOLDEN_CROSS, volume=vol)

        return signal

    @override
    def on_fill(self, fill: Fill) -> None:
        """成交回执 — Bridge 在下单成交后调用

        注意：State 是唯一真实的数据来源，on_fill 只是通知。
        State 的 position/fills 由 Bridge 在 on_trade 中更新。
        """
        pass

    # ---- 内部算法 ----

    @staticmethod
    def _is_golden_cross(cur_short: float, cur_long: float,
                         prev_short: float, prev_long: float) -> bool:
        return golden_cross(prev_short, prev_long, cur_short, cur_long)

    @staticmethod
    def _is_death_cross(cur_short: float, cur_long: float,
                        prev_short: float, prev_long: float) -> bool:
        return death_cross(prev_short, prev_long, cur_short, cur_long)

    @staticmethod
    def _check_stop_loss(entry_price: float, current_price: float,
                         stop_loss_ratio: float) -> bool:
        return stop_loss_triggered(entry_price, current_price, stop_loss_ratio)

    @staticmethod
    def _check_take_profit(entry_price: float, current_price: float,
                           take_profit_ratio: float) -> bool:
        return take_profit_triggered(entry_price, current_price, take_profit_ratio)

    @staticmethod
    def _calc_position_size(price: float, capital: float, position_ratio: float,
                            contract_size: int) -> int:
        return position_size(capital, position_ratio, price, contract_size)
