"""均线交叉策略 — 完整的自包含策略核心

不依赖任何外部框架。拥有:
  - SMA 计算 + 金叉/死叉检测 + 止盈止损判断
  - 仓位管理 (entry_price/position/volume)
  - 交易记录 (fills)
  - 技术指标缓存 (_close_history)

Bridge 只需: 构造 Bar → 调用 on_bar() → 拿到 Signal → 执行下单 → 回调 on_fill()
"""

from dataclasses import dataclass
from typing import Any
from typing_extensions import override

from strategies import CORE_VERSION, Strategy, Bar, Signal, Fill, StrategyPosition
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


class MaStrategyCore(Strategy[MACrossParams]):
    """均线交叉策略核心

    负责全部业务逻辑，Bridge 仅做数据转换和下单执行。

    构造时接受策略参数和环境数据。
    """

    name: str = STRATEGY_MA
    VERSION: str = f"{CORE_VERSION}-ma1"

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
            )
        else:
            self._config = MACrossParams()
        self._capital = float(capital) if capital is not None else float(DEFAULT_INITIAL_CAPITAL)
        self._contract_size = int(contract_size) if contract_size is not None else int(DEFAULT_CONTRACT_SIZE)

        self._position = StrategyPosition()
        self._fills: list[Fill] = []
        self._close_history: list[float] = []
        self._prev_sma_short: float = 0.0
        self._prev_sma_long: float = 0.0

    # ---- Strategy 接口 ----

    @property
    @override
    def config(self) -> MACrossParams:
        return self._config

    @config.setter
    def config(self, value: MACrossParams):
        self._config = value

    @property
    @override
    def position(self) -> StrategyPosition:
        return self._position

    @property
    def fills(self) -> list[Fill]:
        """交易成交记录 (只读副本)"""
        return list(self._fills)

    @override
    def reset(self) -> None:
        self._position = StrategyPosition()
        self._fills.clear()
        self._close_history.clear()
        self._prev_sma_short = 0.0
        self._prev_sma_long = 0.0

    @override
    def on_bar(self, bar: Bar) -> Signal:
        """处理一根K线 — 策略决策中枢

        步骤:
          1. 更新收盘价缓存
          2. 计算双均线 + 交叉检测
          3. 风控检查 (持仓时的止损/止盈)
          4. 生成完整 Signal (含预计算手数)
        """
        self._close_history.append(bar.close)

        cur_short = self._calc_sma(self._config.sma_short)
        cur_long = self._calc_sma(self._config.sma_long)

        signal = Signal()

        if self._position.direction == TRADE_DIRECTION_LONG:
            if self._check_stop_loss(bar.close):
                signal = Signal(action=TRADE_ACTION_SELL, reason=SIGNAL_STOP_LOSS,
                                volume=self._position.volume)
            elif self._check_take_profit(bar.close):
                signal = Signal(action=TRADE_ACTION_SELL, reason=SIGNAL_TAKE_PROFIT,
                                volume=self._position.volume)
            elif self._is_death_cross(cur_short, cur_long):
                signal = Signal(action=TRADE_ACTION_SELL, reason=SIGNAL_DEATH_CROSS,
                                volume=self._position.volume)
        else:
            if self._is_golden_cross(cur_short, cur_long):
                vol = self._calc_position_size(bar.close)
                signal = Signal(action=TRADE_ACTION_BUY, reason=SIGNAL_GOLDEN_CROSS, volume=vol)

        self._prev_sma_short = cur_short
        self._prev_sma_long = cur_long
        return signal

    @override
    def on_fill(self, fill: Fill) -> None:
        """成交回执 — Bridge 在下单成交后调用"""
        if fill.action == TRADE_ACTION_BUY:
            self._position = StrategyPosition(
                direction=TRADE_DIRECTION_LONG,
                entry_price=fill.price,
                volume=fill.volume,
            )
        elif fill.action == TRADE_ACTION_SELL:
            self._position = StrategyPosition()
        self._fills.append(fill)

    # ---- 内部算法 ----

    def _calc_sma(self, period: int) -> float:
        return simple_moving_average(self._close_history, period)

    def _is_golden_cross(self, cur_short: float, cur_long: float) -> bool:
        return golden_cross(self._prev_sma_short, self._prev_sma_long,
                            cur_short, cur_long)

    def _is_death_cross(self, cur_short: float, cur_long: float) -> bool:
        return death_cross(self._prev_sma_short, self._prev_sma_long,
                           cur_short, cur_long)

    def _check_stop_loss(self, current_price: float) -> bool:
        return stop_loss_triggered(self._position.entry_price, current_price,
                                   self._config.stop_loss_ratio)

    def _check_take_profit(self, current_price: float) -> bool:
        return take_profit_triggered(self._position.entry_price, current_price,
                                     self._config.take_profit_ratio)

    def _calc_position_size(self, price: float) -> int:
        return position_size(self._capital, self._config.position_ratio,
                             price, self._contract_size)
