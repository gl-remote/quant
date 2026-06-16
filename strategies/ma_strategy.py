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
from typing import Any, ClassVar, cast, override

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
from strategies import (
    CORE_VERSION,
    BarContext,
    DataRequirements,
    EventsRequirements,
    Fill,
    Signal,
    State,
    Strategy,
)
from strategies.strategy_aspects import (
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
@trend_long_when_compare(at(SMA("{sma_short}"), "5m"), ">", at(SMA("{sma_long}"), "15m"))
@confirm_long_when(at(MACD, "1m"), ">", 0)
@confirm_long_when(at(MACD, "5m"), ">", 0)
@confirm_long_when(at(KDJ, "1m"), "<", "kdj_oversold")
@confirm_long_when(at(KDJ, "5m"), "<", "kdj_oversold")
# ── 做空方向切面 ──
@trend_short_when_compare(at(SMA("{sma_short}"), "5m"), "<", at(SMA("{sma_long}"), "15m"))
@confirm_short_when(at(MACD, "1m"), "<", 0)
@confirm_short_when(at(MACD, "5m"), "<", 0)
@confirm_short_when(at(KDJ, "1m"), ">", "kdj_overbought")
@confirm_short_when(at(KDJ, "5m"), ">", "kdj_overbought")
# ── 拦截型切面声明 ──
@with_trailing_stop("15m")
@with_atr_stop_take_profit("15m")
@with_stop_take_profit
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

    VERSION: str = f"{CORE_VERSION}-ma7"
    """策略版本号，ma7 表示使用建议型切面 DSL"""

    __direction_keys__: ClassVar[dict[str, set[str]]]
    """由建议型切面装饰器自动注册的方向 key 集合"""

    def __init__(self) -> None:
        """初始化策略 — 不接收任何参数

        【重构说明】
        旧架构中 __init__ 接收 strategy_params、capital、contract_size。
        新架构中这些都由 Bridge 放在 State 里，Strategy 不需要自己持有。
        """
        pass

    # ---- Strategy 接口 ----

    @override
    def data_requirements(self, config: MACrossParams) -> DataRequirements | None:
        """策略的数据需求声明

        周期、lookback 和指标需求均由切面装饰器自动注册。

        :param config: 策略配置
        :return: 数据需求声明
        """
        return DataRequirements(
            periods={},
            indicators={},
            events=EventsRequirements.no_events(),
        )

    @override
    def on_bar(self, state: State[MACrossParams], ctx: BarContext) -> Signal:
        """处理一根K线 — 策略决策中枢

        【决策流程】
        建议型切面已将方向理由写入 ctx.aspects.direction，
        策略只需检查所有声明的理由是否都满足。

        - 所有 long reason key 都出现 → 买入
        - 所有 short reason key 都出现 → 卖出
        - 出场规则由拦截型切面处理

        :param state: 运行时状态
        :param ctx: 行情上下文
        :return: 交易决策信号
        """
        config = state.strategy_config
        direction = state.position.direction
        signal = Signal()

        # ── 空仓：做多或做空入场 ──
        if not direction:
            long_keys = ctx.aspects.direction.long.keys
            short_keys = ctx.aspects.direction.short.keys
            direction_keys = type(self).__direction_keys__

            vol = self._calc_position_size(
                ctx.bar.close, state.capital, config.position_ratio, state.contract_size, state.margin
            )

            if direction_keys["long"] <= long_keys:
                signal = Signal(action=cast(Any, TRADE_ACTION_BUY), reason="long_entry", volume=vol)
            elif direction_keys["short"] <= short_keys:
                signal = Signal(action=cast(Any, TRADE_ACTION_SELL), reason="short_entry", volume=vol)

        # 填充 diagnostics：切面已写入持仓信息、指标值和方向建议
        ctx.aspects.flush_direction_diagnostics()

        signal.diagnostics = ctx.aspects.diagnostics

        # 有信号时 reason 改为 JSON 格式，写入 backtest_trades 表
        if signal.action:
            import json

            signal.reason = json.dumps(
                {
                    "r": signal.reason,
                    **signal.diagnostics,
                }
            )

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

    # ---- 仅保留仓位计算 ----

    @staticmethod
    def _calc_position_size(
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
