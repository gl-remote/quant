from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from typing import Any, Literal, TypedDict, cast, override

from common.constants import TRADE_ACTION_BUY, TRADE_ACTION_SELL, TRADE_DIRECTION_LONG
from common.formulas import position_size

from .core import CORE_VERSION, Fill, Signal, State, Strategy, placeholder_diagnostics
from .runtime import BarContext, DataRequirements, EventsRequirements, PeriodRequirements

TakeProfitMode = Literal["mid", "close", "open", "opposite", "r"]


@dataclass
class PrevdayReacceptanceParams:
    kline_period: str = "1m"
    trade_start_time: str = "09:00"
    last_entry_time: str = "14:30"
    force_flat_time: str = "14:55"
    price_tick: float = 1.0
    min_breakout_ticks: int = 2
    failure_buffer_ticks: int = 1
    take_profit_mode: TakeProfitMode = "mid"
    take_profit_r: float = 1.0
    max_hold_bars: int = 60
    stop_widen_multiplier: float = 1.0
    strict_close_exit: bool = True
    risk_per_trade: float = 0.02
    max_position_ratio: float = 0.3
    max_trades_per_day: int = 2


class DayLevels(TypedDict):
    date: date
    high: float
    low: float
    close: float
    open: float


class TradeInfo(TypedDict):
    side: Literal["long", "short"]
    entry_price: float
    strict_failure: float
    stop_price: float
    target_price: float
    prev_high: float
    prev_low: float
    prev_close: float


class PrevdayReacceptanceStrategyCore(Strategy[PrevdayReacceptanceParams]):
    name: str = "prevday_reacceptance"
    VERSION: str = f"{CORE_VERSION}-prevday-reacceptance-r1"

    @override
    def data_requirements(self, config: PrevdayReacceptanceParams) -> DataRequirements | None:
        return DataRequirements(
            periods={config.kline_period: PeriodRequirements(lookback_bars=1)},
            indicators={},
            events=EventsRequirements.no_events(),
        )

    @override
    @placeholder_diagnostics
    def on_bar(self, state: State[PrevdayReacceptanceParams], ctx: BarContext) -> Signal:
        config = state.strategy_config
        self._ensure_session(state, ctx)

        signal = Signal()
        if state.position.direction:
            signal = self._exit_signal(state, ctx, config)
        else:
            self._clear_trade_if_flat(state)
            signal = self._entry_signal(state, ctx, config)

        self._update_holding_bars(state, signal)
        self._update_current_levels(state, ctx)
        return signal

    def _entry_signal(
        self,
        state: State[PrevdayReacceptanceParams],
        ctx: BarContext,
        config: PrevdayReacceptanceParams,
    ) -> Signal:
        if not self._can_enter(state, ctx, config):
            self._track_breakout(state, ctx, config)
            return Signal()

        prev = self._prev_levels(state)
        if prev is None:
            return Signal()

        bar = ctx.bar
        self._track_breakout(state, ctx, config)
        long_breakout_low = self._optional_float(state.extra.get("prevday_long_breakout_low"))
        short_breakout_high = self._optional_float(state.extra.get("prevday_short_breakout_high"))

        if long_breakout_low is not None and bar.close > prev["low"]:
            return self._build_entry_signal(state, ctx, config, "long", long_breakout_low, prev)
        if short_breakout_high is not None and bar.close < prev["high"]:
            return self._build_entry_signal(state, ctx, config, "short", short_breakout_high, prev)
        return Signal()

    def _build_entry_signal(
        self,
        state: State[PrevdayReacceptanceParams],
        ctx: BarContext,
        config: PrevdayReacceptanceParams,
        side: Literal["long", "short"],
        breakout_extreme: float,
        prev: DayLevels,
    ) -> Signal:
        entry = ctx.bar.close
        buffer = config.failure_buffer_ticks * config.price_tick
        strict_failure = breakout_extreme - buffer if side == "long" else breakout_extreme + buffer
        strict_distance = abs(entry - strict_failure)
        if strict_distance <= 0:
            return Signal()

        stop_distance = strict_distance * max(config.stop_widen_multiplier, 1.0)
        stop_price = entry - stop_distance if side == "long" else entry + stop_distance
        target_price = self._target_price(side, entry, strict_distance, prev, state, config)
        if not self._target_is_valid(side, entry, target_price):
            return Signal()

        volume = self._calc_volume(state, entry, stop_distance, config)
        if volume <= 0:
            return Signal()

        state.extra["prevday_trade"] = TradeInfo(
            side=side,
            entry_price=entry,
            strict_failure=strict_failure,
            stop_price=stop_price,
            target_price=target_price,
            prev_high=prev["high"],
            prev_low=prev["low"],
            prev_close=prev["close"],
        )
        state.extra["prevday_holding_bars"] = 0
        state.extra["prevday_trade_count"] = self._trade_count(state) + 1
        state.extra.pop("prevday_long_breakout_low", None)
        state.extra.pop("prevday_short_breakout_high", None)

        action = TRADE_ACTION_BUY if side == "long" else TRADE_ACTION_SELL
        reason = "prevday_low_reaccept_long" if side == "long" else "prevday_high_reject_short"
        signal = Signal(action=action, reason=reason, volume=volume)
        signal.diagnostics = self._diagnostics(ctx, prev, entry, strict_failure, stop_price, target_price)
        return signal

    def _exit_signal(
        self,
        state: State[PrevdayReacceptanceParams],
        ctx: BarContext,
        config: PrevdayReacceptanceParams,
    ) -> Signal:
        trade = self._trade_info(state)
        if trade is None:
            return Signal()

        bar = ctx.bar
        direction = state.position.direction
        reason = ""
        action = TRADE_ACTION_SELL if direction == TRADE_DIRECTION_LONG else TRADE_ACTION_BUY
        if direction == TRADE_DIRECTION_LONG:
            if bar.low <= trade["stop_price"]:
                reason = "stop_loss"
            elif config.strict_close_exit and bar.close <= trade["strict_failure"]:
                reason = "strict_failure_close"
            elif bar.high >= trade["target_price"]:
                reason = "take_profit"
            elif self._is_force_flat_time(bar.datetime.time(), config):
                reason = "force_flat"
            elif config.max_hold_bars > 0 and self._holding_bars(state) >= config.max_hold_bars:
                reason = "time_exit"
        else:
            if bar.high >= trade["stop_price"]:
                reason = "stop_loss"
            elif config.strict_close_exit and bar.close >= trade["strict_failure"]:
                reason = "strict_failure_close"
            elif bar.low <= trade["target_price"]:
                reason = "take_profit"
            elif self._is_force_flat_time(bar.datetime.time(), config):
                reason = "force_flat"
            elif config.max_hold_bars > 0 and self._holding_bars(state) >= config.max_hold_bars:
                reason = "time_exit"

        if not reason:
            return Signal()

        signal = Signal(action=action, reason=reason, volume=state.position.volume)
        signal.diagnostics = {
            "close": bar.close,
            "entry_price": trade["entry_price"],
            "strict_failure": trade["strict_failure"],
            "stop_price": trade["stop_price"],
            "target_price": trade["target_price"],
            "holding_bars": float(self._holding_bars(state)),
        }
        return signal

    def _track_breakout(
        self, state: State[PrevdayReacceptanceParams], ctx: BarContext, config: PrevdayReacceptanceParams
    ) -> None:
        prev = self._prev_levels(state)
        if prev is None:
            return
        bar = ctx.bar
        min_breakout = config.min_breakout_ticks * config.price_tick
        if bar.low <= prev["low"] - min_breakout:
            current = self._optional_float(state.extra.get("prevday_long_breakout_low"))
            state.extra["prevday_long_breakout_low"] = bar.low if current is None else min(current, bar.low)
        if bar.high >= prev["high"] + min_breakout:
            current = self._optional_float(state.extra.get("prevday_short_breakout_high"))
            state.extra["prevday_short_breakout_high"] = bar.high if current is None else max(current, bar.high)

    def _target_price(
        self,
        side: Literal["long", "short"],
        entry: float,
        strict_distance: float,
        prev: DayLevels,
        state: State[PrevdayReacceptanceParams],
        config: PrevdayReacceptanceParams,
    ) -> float:
        if config.take_profit_mode == "mid":
            return (prev["high"] + prev["low"]) / 2
        if config.take_profit_mode == "close":
            return prev["close"]
        if config.take_profit_mode == "open":
            current = self._current_levels(state)
            return current["open"] if current is not None else entry
        if config.take_profit_mode == "opposite":
            return prev["high"] if side == "long" else prev["low"]
        if side == "long":
            return entry + strict_distance * config.take_profit_r
        return entry - strict_distance * config.take_profit_r

    @staticmethod
    def _target_is_valid(side: Literal["long", "short"], entry: float, target: float) -> bool:
        return target > entry if side == "long" else target < entry

    @staticmethod
    def _calc_volume(
        state: State[PrevdayReacceptanceParams],
        entry: float,
        stop_distance: float,
        config: PrevdayReacceptanceParams,
    ) -> int:
        risk_value = state.capital * config.risk_per_trade
        risk_per_lot = stop_distance * state.contract_size
        if risk_per_lot <= 0:
            return 0
        risk_volume = int(risk_value / risk_per_lot)
        margin_volume = position_size(
            state.capital, config.max_position_ratio, entry, state.contract_size, state.margin
        )
        return max(0, min(risk_volume, margin_volume))

    def _can_enter(
        self, state: State[PrevdayReacceptanceParams], ctx: BarContext, config: PrevdayReacceptanceParams
    ) -> bool:
        bar_time = ctx.bar.datetime.time()
        return (
            self._prev_levels(state) is not None
            and self._time_in_range(bar_time, config.trade_start_time, config.last_entry_time)
            and not self._is_force_flat_time(bar_time, config)
            and self._trade_count(state) < config.max_trades_per_day
        )

    def _ensure_session(self, state: State[PrevdayReacceptanceParams], ctx: BarContext) -> None:
        bar = ctx.bar
        session = bar.datetime.date()
        current = self._current_levels(state)
        if current is not None and current["date"] == session:
            return
        if current is not None:
            state.extra["prevday_levels"] = current
        state.extra["prevday_current_levels"] = DayLevels(
            date=session,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            open=bar.open,
        )
        state.extra["prevday_trade_count"] = 0
        state.extra["prevday_holding_bars"] = 0
        state.extra.pop("prevday_long_breakout_low", None)
        state.extra.pop("prevday_short_breakout_high", None)
        state.extra.pop("prevday_trade", None)

    def _update_current_levels(self, state: State[PrevdayReacceptanceParams], ctx: BarContext) -> None:
        current = self._current_levels(state)
        if current is None:
            return
        bar = ctx.bar
        current["high"] = max(current["high"], bar.high)
        current["low"] = min(current["low"], bar.low)
        current["close"] = bar.close
        state.extra["prevday_current_levels"] = current

    @staticmethod
    def _clear_trade_if_flat(state: State[PrevdayReacceptanceParams]) -> None:
        state.extra.pop("prevday_trade", None)
        state.extra["prevday_holding_bars"] = 0

    @staticmethod
    def _update_holding_bars(state: State[PrevdayReacceptanceParams], signal: Signal) -> None:
        if state.position.direction:
            state.extra["prevday_holding_bars"] = PrevdayReacceptanceStrategyCore._holding_bars(state) + 1
        if signal.action:
            state.extra["prevday_holding_bars"] = 0

    @staticmethod
    def _holding_bars(state: State[PrevdayReacceptanceParams]) -> int:
        value = state.extra.get("prevday_holding_bars", 0)
        return int(value) if isinstance(value, int | float) else 0

    @staticmethod
    def _trade_count(state: State[PrevdayReacceptanceParams]) -> int:
        value = state.extra.get("prevday_trade_count", 0)
        return int(value) if isinstance(value, int | float) else 0

    @staticmethod
    def _prev_levels(state: State[PrevdayReacceptanceParams]) -> DayLevels | None:
        value = state.extra.get("prevday_levels")
        return cast(DayLevels, value) if isinstance(value, dict) else None

    @staticmethod
    def _current_levels(state: State[PrevdayReacceptanceParams]) -> DayLevels | None:
        value = state.extra.get("prevday_current_levels")
        return cast(DayLevels, value) if isinstance(value, dict) else None

    @staticmethod
    def _trade_info(state: State[PrevdayReacceptanceParams]) -> TradeInfo | None:
        value = state.extra.get("prevday_trade")
        return cast(TradeInfo, value) if isinstance(value, dict) else None

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        return float(value) if isinstance(value, int | float) else None

    @staticmethod
    def _diagnostics(
        ctx: BarContext,
        prev: DayLevels,
        entry: float,
        strict_failure: float,
        stop_price: float,
        target_price: float,
    ) -> dict[str, float]:
        strict_distance = abs(entry - strict_failure)
        target_distance = abs(target_price - entry)
        return {
            "close": ctx.bar.close,
            "prev_high": prev["high"],
            "prev_low": prev["low"],
            "prev_close": prev["close"],
            "entry_price": entry,
            "strict_failure": strict_failure,
            "strict_distance": strict_distance,
            "stop_price": stop_price,
            "target_price": target_price,
            "price_raw_rr": target_distance / strict_distance if strict_distance > 0 else 0.0,
        }

    @staticmethod
    def _parse_time(value: str) -> time:
        hour, minute = value.split(":", maxsplit=1)
        return time(int(hour), int(minute))

    @classmethod
    def _time_in_range(cls, current: time, start: str, end: str) -> bool:
        return cls._parse_time(start) <= current <= cls._parse_time(end)

    @classmethod
    def _is_force_flat_time(cls, current: time, config: PrevdayReacceptanceParams) -> bool:
        return current >= cls._parse_time(config.force_flat_time)

    @override
    def on_fill(self, fill: Fill) -> None:
        pass
