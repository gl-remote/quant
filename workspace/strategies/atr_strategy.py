"""ATR 策略模块

使用建议型切面 DSL 声明方向判断条件与 ATR 风控建议，策略 on_bar 消费
ctx.aspects 做出场/入场决策。

架构:
- 方向判断: confirm_long / confirm_short / trend_long / trend_short 装饰器
- 风控建议: exit_for_take_profit / exit_for_stop_loss / entry_block_after_take_profit / entry_block_after_stop_loss
- 信号后处理: _finalize_signal 装饰器（框架层，策略无感）
"""

from dataclasses import dataclass
from math import isnan
from typing import ClassVar, override

from common.constants import (
    DEFAULT_KDJ_OVERBOUGHT,
    DEFAULT_KDJ_OVERSOLD,
    DEFAULT_POSITION_RATIO,
    DEFAULT_SMA_LONG,
    DEFAULT_SMA_SHORT,
    DEFAULT_STOP_LOSS_RATIO,
    DEFAULT_TAKE_PROFIT_RATIO,
    STRATEGY_ATR,
    TRADE_ACTION_BUY,
    TRADE_ACTION_SELL,
    TRADE_DIRECTION_LONG,
)
from common.formulas import position_size

from .core import (
    CORE_VERSION,
    Fill,
    Signal,
    State,
    Strategy,
    placeholder_diagnostics,
)
from .core.indicators import generate_indicator_column_name
from .runtime import BarContext, DataRequirements, EventsRequirements, PeriodRequirements
from .strategy_aspects import (
    entry_block_after_stop_loss,
    entry_block_after_take_profit,
    exit_for_stop_loss,
    exit_for_take_profit,
    trend_long,
    trend_short,
)
from .strategy_aspects.indicators import KDJ


@dataclass
class ATRCrossParams:
    """ATR 策略参数

    【设计说明】
    这是策略的配置类，所有策略参数都集中在这里。
    使用 dataclass 是为了方便参数传递和类型安全。

    【参数含义】
    sma_short: 短期均线周期
    sma_long: 长期均线周期
    stop_loss_ratio: 止损比例（相对于入场价）
    take_profit_ratio: 止盈比例（相对于入场价）
    position_ratio: 仓位比例（相对于总资金）
    atr_period: ATR 指标计算周期
    atr_stop_loss_multiplier: ATR 止损倍数（亏损超过 atr * multiplier 时止损）
    trailing_activation_atr: 回撤止盈激活倍数（盈利超过 atr * activation 后启动跟踪）
    trailing_drawdown_ratio: 回撤止盈触发比例（激活后从最高点回落超过此比例时止盈）
    kdj_oversold: KDJ 超卖阈值，做多入场条件之一（kdj < 此值），默认 30
    kdj_overbought: KDJ 超买阈值，做空入场条件之一（kdj > 此值），默认 70
    """

    sma_short: int = DEFAULT_SMA_SHORT
    """短期均线周期，默认 10"""

    sma_long: int = DEFAULT_SMA_LONG
    """长期均线周期，默认 40"""

    stop_loss_ratio: float = DEFAULT_STOP_LOSS_RATIO
    """止损比例，默认 0.03 (3%)"""

    take_profit_ratio: float = DEFAULT_TAKE_PROFIT_RATIO
    """止盈比例，默认 0.05 (5%)"""

    position_ratio: float = DEFAULT_POSITION_RATIO
    """仓位比例，默认 0.1 (10%)"""

    atr_period: int = 14
    """ATR 指标计算周期，默认 14"""

    atr_stop_loss_multiplier: float = 2.0
    """ATR 止损倍数，默认 2.0（亏损超过 atr * multiplier 时止损）"""

    atr_take_profit_multiplier: float = 3.0
    """ATR 止盈倍数，默认 3.0（盈利超过 atr * multiplier 时止盈）"""

    trailing_activation_atr: float = 1.0
    """移动止盈激活阈值（ATR 倍数），盈利超过 atr * activation 后启动跟踪，默认 1.0"""

    trailing_drawdown_ratio: float = 0.25
    """移动止盈回撤比例，激活后从最高价回落超过此比例触发止盈，默认 0.25 (25%)"""

    kdj_oversold: int = DEFAULT_KDJ_OVERSOLD
    """KDJ 超卖阈值，保留用于兼容旧配置，默认 20"""

    kdj_overbought: int = DEFAULT_KDJ_OVERBOUGHT
    """KDJ 超买阈值，保留用于兼容旧配置，默认 80"""

    kdj_pullback_long: int = 45
    """多头背景下的 KDJ 回调阈值，kdj < 此值视为回调过，默认 45"""

    kdj_pullback_short: int = 55
    """空头背景下的 KDJ 反弹阈值，kdj > 此值视为反弹过，默认 55"""

    kdj_signal_long: int = 50
    """多头回调后 KDJ 重新转强阈值，默认 50"""

    kdj_signal_short: int = 50
    """空头反弹后 KDJ 重新转弱阈值，默认 50"""

    time_stop_bars: int = 48
    """入场后最长持仓 5m K 线数量，默认 48 根约 1 个交易日"""

    entry_cooldown_minutes: int = 10
    """止盈/止损平仓后的入场冷却分钟数，默认 10 分钟"""

    exit_on_reverse_signal: bool = False
    """持仓时遇到反向入场条件是否退出，默认关闭"""


# ── 建议型方向切面声明 ──
# 装饰器从下到上执行，运行时所有切面先评估条件写入 ctx.aspects，
# 随后策略原始 on_bar 消费这些建议做出决策。
# ── 做多方向切面 ──
@trend_long("sma({sma_short})@15m > sma({sma_long})@15m")
# ── 做空方向切面 ──
@trend_short("sma({sma_short})@15m < sma({sma_long})@15m")
# ── 风控切面 ──
@entry_block_after_take_profit("cooldown() < {entry_cooldown_minutes}")
@entry_block_after_stop_loss("cooldown() < {entry_cooldown_minutes}")
@exit_for_take_profit(
    "peak_profit() >= atr@15m * {trailing_activation_atr} && drawdown_pct() >= {trailing_drawdown_ratio}"
)
@exit_for_take_profit("profit_abs() >= atr@15m * {atr_take_profit_multiplier}")
@exit_for_stop_loss("loss_abs() >= atr@15m * {atr_stop_loss_multiplier}")
@exit_for_take_profit("profit_pct() >= {take_profit_ratio}")
@exit_for_stop_loss("loss_pct() >= {stop_loss_ratio}")
class ATRStrategyCore(Strategy[ATRCrossParams]):
    """ATR 策略核心 — 消费方向与风控建议做决策

    方向判断与风控建议均由切面装饰器声明并写入 ctx.aspects，
    on_bar 负责消费这些建议完成出场/入场决策。
    信号后处理由 _finalize_signal 装饰器自动完成。

    决策规则:
    - 有持仓 + ctx.aspects.risk 非空 → 出场（取第一个 risk reason 作为 signal reason）
    - 空仓 + ctx.aspects.risk 含 cooldown → 不入場
    - 空仓 + ctx.aspects.risk 为空 + 所有 long reason key 都出现 → 买入
    - 空仓 + ctx.aspects.risk 为空 + 所有 short reason key 都出现 → 卖出
    """

    name: str = STRATEGY_ATR
    """策略名称"""

    VERSION: str = f"{CORE_VERSION}-atr1"
    """策略版本号，atr1 表示使用 ATR 建议型切面 DSL"""

    __direction_keys__: ClassVar[dict[str, set[str]]]
    """由建议型切面装饰器自动注册的方向 key 集合"""

    def __init__(self) -> None:
        pass

    # ---- Strategy 接口 ----

    @override
    def data_requirements(self, config: ATRCrossParams) -> DataRequirements | None:
        reqs = super().data_requirements(config)
        if reqs is None:
            return None
        reqs.merge(
            DataRequirements(
                periods={"5m": PeriodRequirements(lookback_bars=2)},
                indicators={"5m": [KDJ]},
                events=EventsRequirements.no_events(),
            )
        )
        return reqs

    @override
    @placeholder_diagnostics
    def on_bar(self, state: State[ATRCrossParams], ctx: BarContext) -> Signal:
        """消费方向建议与风控建议，做出场/入场决策"""
        config = state.strategy_config
        direction = state.position.direction
        signal = Signal()

        risk = ctx.aspects.risk
        exit_reasons = risk.take_profit.exit + risk.stop_loss.exit

        # ── 有持仓：exit 风控建议触发 → 出场 ──
        if direction and exit_reasons:
            first_exit = exit_reasons[0]
            action = TRADE_ACTION_SELL if direction == TRADE_DIRECTION_LONG else TRADE_ACTION_BUY
            signal = Signal(
                action=action,
                reason=first_exit.name,
                volume=state.position.volume,
            )
            signal.diagnostics = first_exit.detail
        elif direction and config.exit_on_reverse_signal and self._has_reverse_signal(state, ctx, config):
            action = TRADE_ACTION_SELL if direction == TRADE_DIRECTION_LONG else TRADE_ACTION_BUY
            signal = Signal(action=action, reason="reverse_exit", volume=state.position.volume)
        elif direction and self._holding_bars(state) >= config.time_stop_bars:
            action = TRADE_ACTION_SELL if direction == TRADE_DIRECTION_LONG else TRADE_ACTION_BUY
            signal = Signal(action=action, reason="time_stop", volume=state.position.volume)

        # ── 空仓：无任何风控建议时按方向建议入场 ──
        elif not direction and not risk.all_reasons:
            long_keys: set[str] = ctx.aspects.direction.long.keys
            short_keys: set[str] = ctx.aspects.direction.short.keys
            direction_keys: dict[str, set[str]] = type(self).__direction_keys__

            vol = self.calc_position_size(
                ctx.bar.close, state.capital, config.position_ratio, state.contract_size, state.margin
            )

            if direction_keys["long"] <= long_keys and self._has_long_pullback(ctx, config):
                signal = Signal(action=TRADE_ACTION_BUY, reason="long_entry", volume=vol)
            elif direction_keys["short"] <= short_keys and self._has_short_pullback(ctx, config):
                signal = Signal(action=TRADE_ACTION_SELL, reason="short_entry", volume=vol)

        self._update_holding_bars(state, signal)
        return signal

    def _has_long_pullback(self, ctx: BarContext, config: ATRCrossParams) -> bool:
        values = self._recent_kdj_values(ctx, 2)
        if len(values) < 2:
            return False
        return values[-1] > config.kdj_signal_long

    def _has_short_pullback(self, ctx: BarContext, config: ATRCrossParams) -> bool:
        values = self._recent_kdj_values(ctx, 2)
        if len(values) < 2:
            return False
        return values[-1] < config.kdj_signal_short

    def _has_reverse_signal(self, state: State[ATRCrossParams], ctx: BarContext, config: ATRCrossParams) -> bool:
        direction_keys: dict[str, set[str]] = type(self).__direction_keys__
        if state.position.direction == TRADE_DIRECTION_LONG:
            return direction_keys["short"] <= ctx.aspects.direction.short.keys and self._has_short_pullback(ctx, config)
        return direction_keys["long"] <= ctx.aspects.direction.long.keys and self._has_long_pullback(ctx, config)

    @staticmethod
    def _recent_kdj_values(ctx: BarContext, lookback_bars: int) -> list[float]:
        view = ctx.multi.get("5m")
        if view is None:
            return []
        col = generate_indicator_column_name(KDJ.name, KDJ.params, period="5m")
        return [value for value in view.indicator_history(col, lookback_bars) if not isnan(value)]

    @staticmethod
    def _holding_bars(state: State[ATRCrossParams]) -> int:
        value = state.extra.get("atr_holding_bars", 0)
        return int(value) if isinstance(value, int | float) else 0

    @staticmethod
    def _update_holding_bars(state: State[ATRCrossParams], signal: Signal) -> None:
        if state.position.direction:
            state.extra["atr_holding_bars"] = ATRStrategyCore._holding_bars(state) + 1
        if signal.action:
            state.extra["atr_holding_bars"] = 0

    @override
    def on_fill(self, fill: Fill) -> None:
        pass

    # ---- 仅保留仓位计算 ----

    @staticmethod
    def calc_position_size(
        price: float, capital: float, position_ratio: float, contract_size: int, margin: float = 1.0
    ) -> int:
        """计算仓位大小

        :param price: 当前价格
        :param capital: 总资金
        :param position_ratio: 仓位比例
        :param contract_size: 合约乘数
        :param margin: 保证金比例
        :return: 手数
        """
        return position_size(capital, position_ratio, price, contract_size, margin)
