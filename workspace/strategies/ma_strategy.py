"""均线交叉策略模块

使用建议型切面 DSL 声明方向判断条件与风控建议，策略 on_bar 消费
ctx.aspects 做出场/入场决策。

架构:
- 方向判断: confirm_long_when / confirm_short_when / trend_*_when_compare 装饰器
- 风控建议: exit_take_profit_when / exit_stop_loss_when / exit_take_profit_atr / exit_stop_loss_atr / exit_take_profit_trailing / entry_block_take_profit_cooldown / entry_block_stop_loss_cooldown
- 信号后处理: _finalize_signal 装饰器（框架层，策略无感）
"""

from dataclasses import dataclass
from datetime import datetime
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

    signal_profile: str = "trend_macd"
    """信号组合：trend_macd / trend_pullback / trend_full / 兼容旧 profile"""

    exit_on_reverse_signal: bool = True
    """持仓时是否允许反向方向信号退出"""

    kdj_pullback_long: int = 45
    """多头背景下的 5m KDJ 回调阈值"""

    kdj_pullback_short: int = 55
    """空头背景下的 5m KDJ 反弹阈值"""

    reverse_confirm_bars: int = 0
    """反向退出需要连续确认的成交/信号间隔 bar 数，0 表示单根确认"""

    min_hold_bars: int = 0
    """最短持仓 bar 数，未达到时只允许止损退出"""

    max_hold_bars: int = 0
    """最长持仓 bar 数，0 表示不启用时间退出"""

    entry_cooldown_bars: int = 0
    """任意平仓后冷却 bar 数，0 表示不启用"""

    trend_gap_atr: float = 0.0
    """15m 均线差距至少达到 ATR 倍数，0 表示不启用"""


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
@exit_for_stop_loss("loss_abs() >= atr@15m * {atr_stop_loss_multiplier}")
@exit_for_take_profit("profit_pct() >= {take_profit_ratio}")
@exit_for_stop_loss("loss_pct() >= {stop_loss_ratio}")
class MaStrategyCore(Strategy[MACrossParams]):
    """均线交叉策略核心 — 消费方向与风控建议做决策

    方向判断与风控建议均由切面装饰器声明并写入 ctx.aspects，
    on_bar 负责消费这些建议完成出场/入场决策。
    信号后处理由 _finalize_signal 装饰器自动完成。

    决策规则:
    - 有持仓 + ctx.aspects.risk 非空 → 出场（取第一个 risk reason 作为 signal reason）
    - 空仓 + ctx.aspects.risk 含 cooldown → 不入場
    - 空仓 + ctx.aspects.risk 为空 + 所有 long reason key 都出现 → 买入
    - 空仓 + ctx.aspects.risk 为空 + 所有 short reason key 都出现 → 卖出
    """

    name: str = STRATEGY_MA
    """策略名称"""

    VERSION: str = f"{CORE_VERSION}-ma8"
    """策略版本号，ma8 表示中低频趋势结构"""

    __direction_keys__: ClassVar[dict[str, set[str]]]
    """由建议型切面装饰器自动注册的方向 key 集合"""

    def __init__(self) -> None:
        pass

    # ---- Strategy 接口 ----

    @override
    @placeholder_diagnostics
    def on_bar(self, state: State[MACrossParams], ctx: BarContext) -> Signal:
        """消费方向建议与风控建议，做出场/入场决策"""
        config = state.strategy_config
        direction = state.position.direction
        signal = Signal()

        risk = ctx.aspects.risk
        long_keys: set[str] = ctx.aspects.direction.long.keys
        short_keys: set[str] = ctx.aspects.direction.short.keys
        direction_keys: dict[str, set[str]] = type(self).__direction_keys__
        required_direction_keys = self._required_direction_keys(direction_keys, config.signal_profile)
        hold_bars = self._bars_since_position_entry(state, ctx)
        cooldown_bars = self._bars_since_last_close(state, ctx)

        # ── 有持仓：硬止损优先，不受最短持仓限制 ──
        stop_loss_exits = risk.stop_loss.exit
        take_profit_exits = risk.take_profit.exit
        if direction and stop_loss_exits:
            first_exit = stop_loss_exits[0]
            action = TRADE_ACTION_SELL if direction == TRADE_DIRECTION_LONG else TRADE_ACTION_BUY
            signal = Signal(action=action, reason=first_exit.name, volume=state.position.volume)
            signal.diagnostics = first_exit.detail

        elif direction:
            can_soft_exit = hold_bars is None or hold_bars >= config.min_hold_bars
            if can_soft_exit and take_profit_exits:
                first_exit = take_profit_exits[0]
                action = TRADE_ACTION_SELL if direction == TRADE_DIRECTION_LONG else TRADE_ACTION_BUY
                signal = Signal(action=action, reason=first_exit.name, volume=state.position.volume)
                signal.diagnostics = first_exit.detail
            elif (
                can_soft_exit
                and config.exit_on_reverse_signal
                and self._has_confirmed_reverse(
                    state,
                    ctx,
                    required_direction_keys,
                    long_keys,
                    short_keys,
                )
            ):
                action = TRADE_ACTION_SELL if direction == TRADE_DIRECTION_LONG else TRADE_ACTION_BUY
                reason = "reverse_short_exit" if direction == TRADE_DIRECTION_LONG else "reverse_long_exit"
                signal = Signal(action=action, reason=reason, volume=state.position.volume)
            elif config.max_hold_bars > 0 and hold_bars is not None and hold_bars >= config.max_hold_bars:
                action = TRADE_ACTION_SELL if direction == TRADE_DIRECTION_LONG else TRADE_ACTION_BUY
                signal = Signal(action=action, reason="time_exit", volume=state.position.volume)

        # ── 空仓：无任何风控建议且冷却结束时按方向建议入场 ──
        elif not risk.all_reasons and not self._in_entry_cooldown(config, cooldown_bars):
            if self._trend_gap_ok(ctx, config):
                vol = self.calc_position_size(
                    ctx.bar.close, state.capital, config.position_ratio, state.contract_size, state.margin
                )

                if required_direction_keys["long"] <= long_keys:
                    signal = Signal(action=TRADE_ACTION_BUY, reason="long_entry", volume=vol)
                elif required_direction_keys["short"] <= short_keys:
                    signal = Signal(action=TRADE_ACTION_SELL, reason="short_entry", volume=vol)

        return signal

    @override
    def on_fill(self, fill: Fill) -> None:
        pass

    @staticmethod
    def _required_direction_keys(direction_keys: dict[str, set[str]], signal_profile: str) -> dict[str, set[str]]:
        profiles = {
            "sma_only": {"sma_"},
            "sma_macd": {"sma_", "macd_"},
            "sma_kdj": {"sma_", "kdj_"},
            "full": {"sma_", "macd_", "kdj_"},
            "trend_macd": {"sma_", "macd_"},
            "trend_pullback": {"sma_", "kdj_"},
            "trend_full": {"sma_", "macd_", "kdj_"},
        }
        prefixes = profiles.get(signal_profile, profiles["trend_macd"])
        return {
            side: {key for key in keys if any(key.startswith(prefix) for prefix in prefixes)}
            for side, keys in direction_keys.items()
        }

    @staticmethod
    def _bars_since_position_entry(state: State[MACrossParams], ctx: BarContext) -> int | None:
        entry_fill = next((fill for fill in reversed(state.fills) if fill.volume > 0), None)
        if entry_fill is None:
            return None
        return MaStrategyCore._elapsed_bars(entry_fill.timestamp, ctx.bar.datetime, state.period)

    @staticmethod
    def _bars_since_last_close(state: State[MACrossParams], ctx: BarContext) -> int | None:
        last_close = next((fill for fill in reversed(state.fills) if fill.reason and "entry" not in fill.reason), None)
        if last_close is None:
            return None
        return MaStrategyCore._elapsed_bars(last_close.timestamp, ctx.bar.datetime, state.period)

    @staticmethod
    def _elapsed_bars(start: str, end: datetime, period: str) -> int | None:
        try:
            start_dt = datetime.fromisoformat(str(start))
        except ValueError:
            return None
        minutes = max((end - start_dt).total_seconds() / 60.0, 0.0)
        return int(minutes // MaStrategyCore._period_minutes(period))

    @staticmethod
    def _period_minutes(period: str) -> int:
        if period.endswith("m"):
            return max(int(period[:-1]), 1)
        if period.endswith("h"):
            return max(int(period[:-1]) * 60, 1)
        if period.endswith("d"):
            return max(int(period[:-1]) * 60 * 24, 1)
        return 1

    @staticmethod
    def _in_entry_cooldown(config: MACrossParams, cooldown_bars: int | None) -> bool:
        return (
            config.entry_cooldown_bars > 0 and cooldown_bars is not None and cooldown_bars < config.entry_cooldown_bars
        )

    @staticmethod
    def _has_confirmed_reverse(
        state: State[MACrossParams],
        ctx: BarContext,
        required_direction_keys: dict[str, set[str]],
        long_keys: set[str],
        short_keys: set[str],
    ) -> bool:
        config = state.strategy_config
        reverse_keys = (
            required_direction_keys["short"]
            if state.position.direction == TRADE_DIRECTION_LONG
            else required_direction_keys["long"]
        )
        current_keys = short_keys if state.position.direction == TRADE_DIRECTION_LONG else long_keys
        if not reverse_keys <= current_keys:
            state.extra.pop("ma_reverse_seen_at", None)
            return False
        if config.reverse_confirm_bars <= 0:
            return True
        cached_seen = state.extra.get("ma_reverse_seen_at")
        if not isinstance(cached_seen, str):
            cached_seen = ctx.bar.datetime.isoformat()
            state.extra["ma_reverse_seen_at"] = cached_seen
        confirmed_bars = MaStrategyCore._elapsed_bars(cached_seen, ctx.bar.datetime, state.period)
        return confirmed_bars is not None and confirmed_bars >= config.reverse_confirm_bars

    @staticmethod
    def _trend_gap_ok(ctx: BarContext, config: MACrossParams) -> bool:
        if config.trend_gap_atr <= 0:
            return True
        view = ctx.multi.get("15m")
        if view is None:
            return False
        short_col = f"15m_sma_{config.sma_short}"
        long_col = f"15m_sma_{config.sma_long}"
        atr_col = f"15m_atr_{config.atr_period}"
        sma_short = view.indicator(short_col, -1)
        sma_long = view.indicator(long_col, -1)
        atr = view.indicator(atr_col, -1)
        if sma_short is None or sma_long is None or atr is None or atr == 0:
            return False
        return abs(sma_short - sma_long) >= atr * config.trend_gap_atr

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
