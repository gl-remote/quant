"""均线交叉策略模块

一个简单但完整的均线交叉策略实现，作为新架构的示范策略。

重构背景:
- 旧架构：Strategy 持有 config、position、fills 等所有状态
- 新架构：State 统一持有所有运行时数据，Strategy 成为纯决策逻辑

设计理念:
- Strategy 是纯决策逻辑，不持有任何状态
- 所有运行时数据通过 State 获取
- 所有行情数据通过 BarContext 获取
- Bridge 负责: 构造 Bar → 构造 ctx → 调用 on_bar(state, ctx) → 拿到 Signal → 执行下单
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
    """均线交叉策略参数

    【设计说明】
    这是策略的配置类，所有策略参数都集中在这里。
    使用 dataclass 是为了方便参数传递和类型安全。

    【参数含义】
    sma_short: 短期均线周期
    sma_long: 长期均线周期
    stop_loss_ratio: 止损比例（相对于入场价）
    take_profit_ratio: 止盈比例（相对于入场价）
    position_ratio: 仓位比例（相对于总资金）
    """
    sma_short: int = DEFAULT_SMA_SHORT
    """短期均线周期，默认 5"""

    sma_long: int = DEFAULT_SMA_LONG
    """长期均线周期，默认 20"""

    stop_loss_ratio: float = DEFAULT_STOP_LOSS_RATIO
    """止损比例，默认 0.03 (3%)"""

    take_profit_ratio: float = DEFAULT_TAKE_PROFIT_RATIO
    """止盈比例，默认 0.05 (5%)"""

    position_ratio: float = DEFAULT_POSITION_RATIO
    """仓位比例，默认 0.1 (10%)"""


class MaStrategyCore(Strategy[MACrossParams]):
    """均线交叉策略核心 — 纯决策逻辑

    【策略逻辑】
    - 金叉（短期均线上穿长期均线）：买入
    - 死叉（短期均线下穿长期均线）：卖出
    - 持仓时检查止损和止盈
    - 空仓时只检查金叉

    【数据来源】
    - 配置: state.strategy_config
    - 持仓: state.position
    - 资金: state.capital
    - K线/指标: ctx.multi["1m"]

    【与旧架构的区别】
    旧架构（已废弃）:
      - Strategy 持有 self._config、self._position、self._fills
      - on_bar(bar, ctx)
      - 自己管理所有状态

    新架构（当前）:
      - Strategy 不持有任何状态
      - on_bar(state, ctx)
      - 所有数据通过参数传入
    """

    name: str = STRATEGY_MA
    """策略名称"""

    VERSION: str = f"{CORE_VERSION}-ma3"
    """策略版本号，ma3 表示使用新架构"""

    def __init__(self) -> None:
        """初始化策略 — 不接收任何参数

        【重构说明】
        旧架构中 __init__ 接收 strategy_params、capital、contract_size。
        新架构中这些都由 Bridge 放在 State 里，Strategy 不需要自己持有。
        """
        pass

    # ---- Strategy 接口 ----

    @override
    def data_requirements(self, config: MACrossParams) -> Optional[DataRequirements]:
        """策略的数据需求声明

        【本策略的需求】
        - 主周期: 1m — MACD + KDJ
        - 5m: SMA(config.sma_short) — 短期均线（金叉/死叉判断）
        - 15m: SMA(config.sma_long) — 长期均线（金叉/死叉判断）

        :param config: 策略配置
        :return: 数据需求声明
        """
        return DataRequirements(
            periods={
                "1m": PeriodRequirements(lookback_bars=60),
                "5m": PeriodRequirements(lookback_bars=config.sma_short + 1),
                "15m": PeriodRequirements(lookback_bars=config.sma_long + 1),
            },
            indicators={
                "1m": [
                    IndicatorRequirements(name="macd", params={"fast": 12, "slow": 26, "signal": 9}),
                    IndicatorRequirements(name="kdj", params={"n": 9, "k_period": 3, "d_period": 3}),
                ],
                "5m": [
                    IndicatorRequirements(name="sma", params={"period": config.sma_short}),
                ],
                "15m": [
                    IndicatorRequirements(name="sma", params={"period": config.sma_long}),
                ],
            },
            events=EventsRequirements.no_events(),
        )

    @override
    def on_bar(self, state: State[MACrossParams], ctx: BarContext) -> Signal:
        """处理一根K线 — 策略决策中枢

        【决策流程】
        - 5m SMA(short) 上穿 15m SMA(long) → 金叉买入
        - 5m SMA(short) 下穿 15m SMA(long) → 死叉卖出
        - 持有中先检查止损/止盈，再检查死叉

        :param state: 运行时状态
        :param ctx: 行情上下文
        :return: 交易决策信号
        """
        config = state.strategy_config
        view_5m = ctx.multi["5m"]
        view_15m = ctx.multi["15m"]
        sma_short_col = f"sma_{config.sma_short}"
        sma_long_col = f"sma_{config.sma_long}"

        cur_short = view_5m.indicator(sma_short_col, -1) or 0.0
        cur_long = view_15m.indicator(sma_long_col, -1) or 0.0
        prev_short = view_5m.indicator(sma_short_col, -2) or 0.0
        prev_long = view_15m.indicator(sma_long_col, -2) or 0.0

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

        【重要原则】
        - State 是唯一真实的数据来源
        - on_fill 只是通知，不应该改变任何数据
        - Strategy 不应该自己更新持仓，应该从 state.position 读取

        【本策略的处理】
        目前这个策略不需要在成交时做任何特殊处理，所以是空实现。
        如果策略需要在成交时触发一些逻辑，可以在这里实现。

        【数据来源】
        - state.position: 由 Bridge 在 on_trade 中更新
        - state.fills: 由 Bridge 在 on_trade 中追加
        """
        pass

    # ---- 内部算法 ----

    @staticmethod
    def _is_golden_cross(cur_short: float, cur_long: float,
                         prev_short: float, prev_long: float) -> bool:
        """检测金叉 — 短期均线上穿长期均线

        :param cur_short: 当前短期均线
        :param cur_long: 当前长期均线
        :param prev_short: 前一根短期均线
        :param prev_long: 前一根长期均线
        :return: 是否金叉
        """
        return golden_cross(prev_short, prev_long, cur_short, cur_long)

    @staticmethod
    def _is_death_cross(cur_short: float, cur_long: float,
                        prev_short: float, prev_long: float) -> bool:
        """检测死叉 — 短期均线下穿长期均线

        :param cur_short: 当前短期均线
        :param cur_long: 当前长期均线
        :param prev_short: 前一根短期均线
        :param prev_long: 前一根长期均线
        :return: 是否死叉
        """
        return death_cross(prev_short, prev_long, cur_short, cur_long)

    @staticmethod
    def _check_stop_loss(entry_price: float, current_price: float,
                         stop_loss_ratio: float) -> bool:
        """检查止损是否触发

        :param entry_price: 入场价格
        :param current_price: 当前价格
        :param stop_loss_ratio: 止损比例
        :return: 是否触发止损
        """
        return stop_loss_triggered(entry_price, current_price, stop_loss_ratio)

    @staticmethod
    def _check_take_profit(entry_price: float, current_price: float,
                           take_profit_ratio: float) -> bool:
        """检查止盈是否触发

        :param entry_price: 入场价格
        :param current_price: 当前价格
        :param take_profit_ratio: 止盈比例
        :return: 是否触发止盈
        """
        return take_profit_triggered(entry_price, current_price, take_profit_ratio)

    @staticmethod
    def _calc_position_size(price: float, capital: float, position_ratio: float,
                            contract_size: int) -> int:
        """计算仓位大小

        :param price: 当前价格
        :param capital: 总资金
        :param position_ratio: 仓位比例
        :param contract_size: 合约乘数
        :return: 手数
        """
        return position_size(capital, position_ratio, price, contract_size)
