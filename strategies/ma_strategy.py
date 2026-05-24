"""均线交叉策略 — 完整的自包含策略核心

不依赖任何外部框架。拥有:
  - SMA 计算 + 金叉/死叉检测 + 止盈止损判断
  - 仓位管理 (entry_price/position/volume)
  - 交易记录 (fills)
  - 技术指标缓存 (_close_history)

Bridge 只需: 构造 Bar → 调用 on_bar() → 拿到 Signal → 执行下单 → 回调 on_fill()
"""

from dataclasses import dataclass, field
from typing import List, Optional

from .core.base import Strategy
from .core.types import Bar, Signal, Fill, StrategyPosition


@dataclass
class TradingConfig:
    sma_short: int = 5
    sma_long: int = 20
    stop_loss_ratio: float = 0.03
    take_profit_ratio: float = 0.05
    position_ratio: float = 0.1
    contract_size: int = 10
    capital: float = 100000.0
    commission_rate: float = 0.0003   # 手续费率 (0.03%)
    slippage: float = 1.0             # 滑点 (最小变动价位)


class MaStrategyCore(Strategy):
    """均线交叉策略核心

    负责全部业务逻辑，Bridge 仅做数据转换和下单执行。
    """

    name: str = "ma"

    def __init__(self, config: Optional[TradingConfig] = None):
        self._config = config or TradingConfig()
        self._position = StrategyPosition()
        self._fills: List[Fill] = []
        self._close_history: List[float] = []
        self._prev_sma_short: float = 0.0
        self._prev_sma_long: float = 0.0

    # ---- Strategy 接口 ----

    @property
    def config(self) -> TradingConfig:
        return self._config

    @config.setter
    def config(self, value: TradingConfig):
        self._config = value

    @property
    def position(self) -> StrategyPosition:
        return self._position

    @property
    def fills(self) -> List[Fill]:
        """交易成交记录 (只读副本)"""
        return list(self._fills)

    def reset(self) -> None:
        self._position = StrategyPosition()
        self._fills.clear()
        self._close_history.clear()
        self._prev_sma_short = 0.0
        self._prev_sma_long = 0.0

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

        # 信号优先级 (由 if/elif 顺序决定):
        #   持仓时: 止损 > 止盈 > 死叉
        #   空仓时: 金叉买入
        # 参见 doc/api-reference.md "信号优先级"
        if self._position.direction == 'long':
            if self._check_stop_loss(bar.close):
                signal = Signal(action='sell', reason='stop_loss',
                                volume=self._position.volume)
            elif self._check_take_profit(bar.close):
                signal = Signal(action='sell', reason='take_profit',
                                volume=self._position.volume)
            elif self._is_death_cross(cur_short, cur_long):
                signal = Signal(action='sell', reason='death_cross',
                                volume=self._position.volume)
        else:
            if self._is_golden_cross(cur_short, cur_long):
                vol = self._calc_position_size(bar.close)
                signal = Signal(action='buy', reason='golden_cross', volume=vol)

        self._prev_sma_short = cur_short
        self._prev_sma_long = cur_long
        return signal

    def on_fill(self, fill: Fill) -> None:
        """成交回执 — Bridge 在下单成交后调用"""
        if fill.action == 'buy':
            self._position = StrategyPosition(
                direction='long',
                entry_price=fill.price,
                volume=fill.volume,
            )
        elif fill.action == 'sell':
            self._position = StrategyPosition()
        self._fills.append(fill)

    # ---- 内部算法 ----

    def _calc_sma(self, period: int) -> float:
        if not self._close_history or period <= 0:
            return 0.0
        chunk = self._close_history[-period:]
        return sum(chunk) / len(chunk)

    def _is_golden_cross(self, cur_short: float, cur_long: float) -> bool:
        return (self._prev_sma_short <= self._prev_sma_long
                and cur_short > cur_long)

    def _is_death_cross(self, cur_short: float, cur_long: float) -> bool:
        return (self._prev_sma_short >= self._prev_sma_long
                and cur_short < cur_long)

    def _check_stop_loss(self, current_price: float) -> bool:
        if self._position.entry_price <= 0:
            return False
        return ((self._position.entry_price - current_price)
                / self._position.entry_price >= self._config.stop_loss_ratio)

    def _check_take_profit(self, current_price: float) -> bool:
        if self._position.entry_price <= 0:
            return False
        return ((current_price - self._position.entry_price)
                / self._position.entry_price >= self._config.take_profit_ratio)

    def _calc_position_size(self, price: float) -> int:
        c = self._config
        vol = c.capital * c.position_ratio / (price * c.contract_size)
        return max(1, int(vol))
