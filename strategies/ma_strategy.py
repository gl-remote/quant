"""均线交叉策略模块

使用建议型切面 DSL 声明方向判断条件，拦截型切面处理出场逻辑，
策略 on_bar 只做纯决策（方向建议子集判断 → 入场信号）。

架构:
- 方向判断: confirm_long_when / confirm_short_when / trend_*_when_compare 装饰器
- 出场逻辑: with_stop_take_profit / with_atr_stop_take_profit / with_trailing_stop
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
    STRATEGY_MA,
    TRADE_ACTION_BUY,
    TRADE_ACTION_SELL,
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
    KDJ,
    MACD,
    SMA,
    at,
    confirm_long_when,
    confirm_short_when,
    trend_long_when_compare,
    trend_short_when_compare,
    with_atr_stop_take_profit,
    with_stop_take_profit,
    with_trade_cooldown,
    with_trailing_stop,
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
    """KDJ 超卖阈值，kdj < 此值视为超卖（做多入场条件之一），默认 20"""

    kdj_overbought: int = DEFAULT_KDJ_OVERBOUGHT
    """KDJ 超买阈值，kdj > 此值视为超买（做空入场条件之一），默认 80"""


# ── 建议型方向切面声明 ──
# 装饰器从下到上执行，建议型切面在外层先评估条件写入 ctx.aspects，
# 拦截型切面在内层先执行（有持仓时提前返回出场信号）。
# ── 做多方向切面 ──
@trend_long_when_compare(at(SMA("{sma_short}"), "5m"), ">", at(SMA("{sma_long}"), "1h"))
@confirm_long_when(at(MACD, "1h"), ">", 0)
@confirm_long_when(at(MACD, "5m"), ">", 0)
@confirm_long_when(at(KDJ, "1h"), "<", "kdj_oversold")
@confirm_long_when(at(KDJ, "5m"), "<", "kdj_oversold")
# ── 做空方向切面 ──
@trend_short_when_compare(at(SMA("{sma_short}"), "5m"), "<", at(SMA("{sma_long}"), "1h"))
@confirm_short_when(at(MACD, "1h"), "<", 0)
@confirm_short_when(at(MACD, "5m"), "<", 0)
@confirm_short_when(at(KDJ, "1h"), ">", "kdj_overbought")
@confirm_short_when(at(KDJ, "5m"), ">", "kdj_overbought")
# ── 拦截型切面声明 ──
@with_trade_cooldown(minutes=10)
@with_trailing_stop("15m")
@with_atr_stop_take_profit("15m")
@with_stop_take_profit
class MaStrategyCore(Strategy[MACrossParams]):
    """均线交叉策略核心 — 纯决策逻辑

    方向判断由建议型切面装饰器声明，on_bar 只需检查所有声明的理由是否满足。
    出场逻辑由拦截型切面自动处理，信号后处理由 @_auto_finalize 装饰器自动完成。

    决策规则:
    - 所有 long reason key 都出现 → 买入
    - 所有 short reason key 都出现 → 卖出
    """

    name: str = STRATEGY_MA
    """策略名称"""

    VERSION: str = f"{CORE_VERSION}-ma7"
    """策略版本号，ma7 表示使用建议型切面 DSL"""

    __direction_keys__: ClassVar[dict[str, set[str]]]
    """由建议型切面装饰器自动注册的方向 key 集合"""

    def __init__(self) -> None:
        pass

    # ---- Strategy 接口 ----

    @override
    def on_bar(self, state: State[MACrossParams], ctx: BarContext) -> Signal:
        """空仓时检查方向建议是否全部满足，满足则入场"""
        config = state.strategy_config
        direction = state.position.direction
        signal = Signal()

        # ── 空仓：做多或做空入场 ──
        if not direction:
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
