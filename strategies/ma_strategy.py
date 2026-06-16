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
from typing import Any, cast, override

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
    IndicatorRequirements,
    PeriodRequirements,
    Signal,
    State,
    Strategy,
)
from strategies.strategy_aspects import (
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

    VERSION: str = f"{CORE_VERSION}-ma6"
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
    def data_requirements(self, config: MACrossParams) -> DataRequirements | None:
        """策略的数据需求声明

        【本策略的需求】
        - 主周期: 1m — MACD + KDJ
        - 5m: SMA(config.sma_short) + MACD + KDJ — 短期均线 + 入场信号确认
        - 15m: SMA(config.sma_long) — 长期均线方向（出场依赖的 ATR 由 @with_atr_stop_take_profit 切面自动注册）

        :param config: 策略配置
        :return: 数据需求声明
        """
        return DataRequirements(
            periods={
                "1m": PeriodRequirements(lookback_bars=60),
                "5m": PeriodRequirements(lookback_bars=max(config.sma_short, config.atr_period) + 1),
                "15m": PeriodRequirements(lookback_bars=max(config.sma_long, config.atr_period) + 1),
            },
            indicators={
                "1m": [
                    IndicatorRequirements(name="macd", params={"fast": 12, "slow": 26, "signal": 9}, window=35),
                    IndicatorRequirements(name="kdj", params={"n": 9, "k_period": 3, "d_period": 3}, window=9),
                ],
                "5m": [
                    IndicatorRequirements(name="sma", params={"period": config.sma_short}, window=config.sma_short),
                    IndicatorRequirements(name="macd", params={"fast": 12, "slow": 26, "signal": 9}, window=35),
                    IndicatorRequirements(name="kdj", params={"n": 9, "k_period": 3, "d_period": 3}, window=9),
                ],
                "15m": [
                    IndicatorRequirements(name="sma", params={"period": config.sma_long}, window=config.sma_long),
                ],
            },
            events=EventsRequirements.no_events(),
        )

    @override
    def on_bar(self, state: State[MACrossParams], ctx: BarContext) -> Signal:
        """处理一根K线 — 策略决策中枢

        【决策流程】

        - 5m SMA(short) 大于 15m SMA(long) 做多
            → 1m macd > 0 && 5m macd > 0
            → 1m kdj < kdj_oversold && 5m kdj < kdj_oversold
            → 空仓状态 → 买入开仓
        - 5m SMA(short) 小于 15m SMA(long) 做空
            → 1m macd < 0 && 5m macd < 0
            → 1m kdj > kdj_overbought && 5m kdj > kdj_overbought
            → 空仓状态 → 卖出开仓
        - 出场规则（持仓时，以当前持仓方向为准，按以下顺序检查）
            - 回撤止盈由 @with_trailing_stop("15m") 切面统一处理
            - ATR 止盈止损由 @with_atr_stop_take_profit("15m") 切面统一处理
            - 固定比例止盈止损由 @with_stop_take_profit 切面统一处理
            - 不检查其他退场信号，仅根据以上条件判断是否出场。

        :param state: 运行时状态
        :param ctx: 行情上下文
        :return: 交易决策信号
        """
        config = state.strategy_config
        view_1m = ctx.multi["1m"]
        view_5m = ctx.multi["5m"]
        view_15m = ctx.multi["15m"]

        sma_short_col = f"sma_{config.sma_short}"
        sma_long_col = f"sma_{config.sma_long}"
        atr_col = f"atr_{config.atr_period}"
        macd_col = "macd_12_9_26"  # fast=12, signal=9, slow=26
        kdj_col = "kdj_3_3_9"  # d_period=3, k_period=3, n=9

        def _get(view: Any, col: str, idx: int, fallback: float) -> float:
            v = view.indicator(col, idx)
            return v if v is not None else fallback

        cur_5m_short = _get(view_5m, sma_short_col, -1, 0.0)
        cur_15m_long = _get(view_15m, sma_long_col, -1, 0.0)
        cur_atr_15m = _get(view_15m, atr_col, -1, 0.0)
        macd_1m = _get(view_1m, macd_col, -1, 0.0)
        kdj_1m = _get(view_1m, kdj_col, -1, 50.0)
        macd_5m = _get(view_5m, macd_col, -1, 0.0)
        kdj_5m = _get(view_5m, kdj_col, -1, 50.0)

        long_bias = cur_5m_short > cur_15m_long
        short_bias = cur_5m_short < cur_15m_long
        direction = state.position.direction
        signal = Signal()

        # ── 空仓：做多或做空入场 ──
        if not direction:
            vol = self._calc_position_size(
                ctx.bar.close, state.capital, config.position_ratio, state.contract_size, state.margin
            )
            if (
                long_bias
                and macd_1m > 0
                and macd_5m > 0
                and kdj_1m < config.kdj_oversold
                and kdj_5m < config.kdj_oversold
            ):
                signal = Signal(action=cast(Any, TRADE_ACTION_BUY), reason="long_entry", volume=vol)
            elif (
                short_bias
                and macd_1m < 0
                and macd_5m < 0
                and kdj_1m > config.kdj_overbought
                and kdj_5m > config.kdj_overbought
            ):
                signal = Signal(action=cast(Any, TRADE_ACTION_SELL), reason="short_entry", volume=vol)

        # 填充 diagnostics — 按 data_requirements 中声明的指标全部记录
        signal.diagnostics = {
            "entry_price": state.position.entry_price,
            "highest_price": state.position.highest_price,
            "lowest_price": state.position.lowest_price,
            "current_close": ctx.bar.close,
            f"sma_{config.sma_short}": cur_5m_short,
            f"sma_{config.sma_long}": cur_15m_long,
            "atr_15m": cur_atr_15m,
            "macd_1m": macd_1m,
            "kdj_1m": kdj_1m,
            "macd_5m": macd_5m,
            "kdj_5m": kdj_5m,
        }

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
