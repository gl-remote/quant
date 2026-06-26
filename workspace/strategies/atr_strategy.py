"""ATR 策略模块

使用建议型切面 DSL 声明方向判断条件与 ATR 风控建议，策略 on_bar 消费
ctx.aspects 做出场/入场决策。

架构:
- 方向判断: confirm_long / confirm_short / trend_long / trend_short 装饰器
- 风控建议: exit_for_take_profit / exit_for_stop_loss / entry_block_after_take_profit / entry_block_after_stop_loss
- 信号后处理: @_auto_finalize 装饰器（框架层，策略无感）
"""

from dataclasses import dataclass
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
)
from .runtime import BarContext
from .strategy_aspects import (
    confirm_long,
    confirm_short,
    entry_block_after_stop_loss,
    entry_block_after_take_profit,
    exit_for_stop_loss,
    exit_for_take_profit,
    trend_long,
    trend_short,
)


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


# ── 建议型方向切面声明 ──
# 装饰器从下到上执行，运行时所有切面先评估条件写入 ctx.aspects，
# 随后策略原始 on_bar 消费这些建议做出决策。
# ── 做多方向切面 ──
@confirm_long("macd@5m > 0")
@confirm_long("kdj@5m < {kdj_pullback_long}")
@trend_long("sma({sma_short})@15m > sma({sma_long})@15m")
# ── 做空方向切面 ──
@confirm_short("macd@5m < 0")
@confirm_short("kdj@5m > {kdj_pullback_short}")
@trend_short("sma({sma_short})@15m < sma({sma_long})@15m")
# ── 风控切面 ──
@entry_block_after_take_profit("cooldown() < 10")
@entry_block_after_stop_loss("cooldown() < 10")
@exit_for_take_profit(
    "peak_profit() >= atr@15m * {trailing_activation_atr} && drawdown_pct() >= {trailing_drawdown_ratio}"
)
@exit_for_take_profit("profit_abs() >= atr@15m * {atr_take_profit_multiplier}")
@exit_for_stop_loss("profit_abs() >= atr@15m * {atr_stop_loss_multiplier}")
@exit_for_take_profit("profit_pct() >= {take_profit_ratio}")
@exit_for_stop_loss("profit_pct() >= {stop_loss_ratio}")
class ATRStrategyCore(Strategy[ATRCrossParams]):
    """ATR 策略核心 — 消费方向与风控建议做决策

    方向判断与风控建议均由切面装饰器声明并写入 ctx.aspects，
    on_bar 负责消费这些建议完成出场/入场决策。
    信号后处理由 @_auto_finalize 装饰器自动完成。

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

        # ── 空仓：无任何风控建议时按方向建议入场 ──
        elif not direction and not risk.all_reasons:
            long_keys: set[str] = ctx.aspects.direction.long.keys
            short_keys: set[str] = ctx.aspects.direction.short.keys
            direction_keys: dict[str, set[str]] = type(self).__direction_keys__

            vol = self.calc_position_size(
                ctx.bar.close, state.capital, config.position_ratio, state.contract_size, state.margin
            )

            if direction_keys["long"] <= long_keys:
                signal = Signal(action=TRADE_ACTION_BUY, reason="long_entry", volume=vol)
            elif direction_keys["short"] <= short_keys:
                signal = Signal(action=TRADE_ACTION_SELL, reason="short_entry", volume=vol)

        return signal

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
