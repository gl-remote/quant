from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any, Literal, TypedDict, cast, override

from common.constants import TRADE_ACTION_BUY, TRADE_ACTION_SELL, TRADE_DIRECTION_LONG
from common.formulas import position_size

from .core import CORE_VERSION, Bar, Fill, Signal, State, Strategy, placeholder_diagnostics
from .runtime import BarContext, DataRequirements, EventsRequirements, PeriodRequirements

TakeProfitMode = Literal["poc", "opposite", "r"]
ProfileMode = Literal["close", "range"]


@dataclass
class ValueAreaReacceptanceParams:
    kline_period: str = "5m"
    context_period: str = ""
    context_lookback_bars: int = 24
    rolling_context_bars: int = 0
    trade_start_time: str = "09:00"
    last_entry_time: str = "14:30"
    force_flat_time: str = "14:55"
    price_tick: float = 1.0
    value_area_ratio: float = 0.7
    profile_mode: ProfileMode = "range"
    min_breakout_ticks: int = 2
    failure_buffer_ticks: int = 1
    take_profit_mode: TakeProfitMode = "poc"
    take_profit_r: float = 1.0
    max_hold_bars: int = 6
    stop_widen_multiplier: float = 1.0
    strict_close_exit: bool = True
    risk_per_trade: float = 0.02
    max_position_ratio: float = 0.3
    max_trades_per_day: int = 1
    min_reaccept_ticks: int = 0
    max_breakout_bars: int = 0
    min_target_ticks: int = 0
    min_price_raw_rr: float = 0.0
    path_check_bars: int = 0
    min_path_progress_ticks: int = 0


class ValueAreaLevels(TypedDict):
    date: date
    vah: float
    val: float
    poc: float
    high: float
    low: float
    close: float
    open: float


class PersistentValueInfo(TypedDict):
    days: int
    overlap_ratio: float
    poc_drift: float
    stable_poc: bool


class WindowValueInfo(TypedDict):
    available: bool
    label: str
    vah: float
    val: float
    poc: float
    width: float
    persistence_bars: int
    overlap_ratio: float
    poc_drift: float
    stable_poc: bool


class CurrentSession(TypedDict):
    date: date
    high: float
    low: float
    close: float
    open: float
    profile: dict[float, float]


class TradeInfo(TypedDict):
    side: Literal["long", "short"]
    entry_price: float
    strict_failure: float
    stop_price: float
    target_price: float
    target_distance: float
    strict_distance: float
    price_raw_rr: float
    entry_bar_range: float
    entry_bar_range_ratio: float
    open_location: str
    prev_close_location: str
    open_poc_distance: float
    prev_close_poc_distance: float
    open_close_poc_relation: str
    persistent_value_days: int
    value_overlap_ratio: float
    poc_drift: float
    stable_poc: bool
    context_label: str
    context_available: bool
    context_location: str
    context_target_distance: float
    context_price_raw_rr: float
    context_persistence_bars: int
    context_overlap_ratio: float
    context_poc_drift: float
    context_stable_poc: bool
    vah: float
    val: float
    poc: float


class ValueAreaReacceptanceStrategyCore(Strategy[ValueAreaReacceptanceParams]):
    name: str = "value_area_reacceptance"
    VERSION: str = f"{CORE_VERSION}-value-area-reacceptance-r1"

    @override
    def data_requirements(self, config: ValueAreaReacceptanceParams) -> DataRequirements | None:
        periods = {config.kline_period: PeriodRequirements(lookback_bars=max(1, config.rolling_context_bars * 2))}
        if config.context_period:
            periods[config.context_period] = PeriodRequirements(lookback_bars=config.context_lookback_bars)
        return DataRequirements(
            periods=periods,
            indicators={},
            events=EventsRequirements.no_events(),
        )

    @override
    @placeholder_diagnostics
    def on_bar(self, state: State[ValueAreaReacceptanceParams], ctx: BarContext) -> Signal:
        config = state.strategy_config
        self._ensure_session(state, ctx, config)

        signal = Signal()
        if state.position.direction:
            signal = self._exit_signal(state, ctx, config)
        else:
            self._clear_trade_if_flat(state)
            signal = self._entry_signal(state, ctx, config)

        self._update_holding_bars(state, signal)
        self._update_current_session(state, ctx, config)
        return signal

    def _entry_signal(
        self,
        state: State[ValueAreaReacceptanceParams],
        ctx: BarContext,
        config: ValueAreaReacceptanceParams,
    ) -> Signal:
        if not self._can_enter(state, ctx, config):
            self._track_breakout(state, ctx, config)
            return Signal()

        prev = self._prev_levels(state)
        if prev is None:
            return Signal()

        bar = ctx.bar
        self._track_breakout(state, ctx, config)
        long_breakout_low = self._optional_float(state.extra.get("value_area_long_breakout_low"))
        short_breakout_high = self._optional_float(state.extra.get("value_area_short_breakout_high"))

        if long_breakout_low is not None and bar.close > prev["val"]:
            breakout_bars = self._int_extra(state, "value_area_long_breakout_bars")
            if self._reacceptance_quality_ok("long", bar.close, prev, breakout_bars, config):
                return self._build_entry_signal(state, ctx, config, "long", long_breakout_low, prev)
        if short_breakout_high is not None and bar.close < prev["vah"]:
            breakout_bars = self._int_extra(state, "value_area_short_breakout_bars")
            if self._reacceptance_quality_ok("short", bar.close, prev, breakout_bars, config):
                return self._build_entry_signal(state, ctx, config, "short", short_breakout_high, prev)
        return Signal()

    def _build_entry_signal(
        self,
        state: State[ValueAreaReacceptanceParams],
        ctx: BarContext,
        config: ValueAreaReacceptanceParams,
        side: Literal["long", "short"],
        breakout_extreme: float,
        prev: ValueAreaLevels,
    ) -> Signal:
        entry = ctx.bar.close
        buffer = config.failure_buffer_ticks * config.price_tick
        strict_failure = breakout_extreme - buffer if side == "long" else breakout_extreme + buffer
        strict_distance = abs(entry - strict_failure)
        if strict_distance <= 0:
            return Signal()

        stop_distance = strict_distance * max(config.stop_widen_multiplier, 1.0)
        stop_price = entry - stop_distance if side == "long" else entry + stop_distance
        target_price = self._target_price(side, entry, strict_distance, prev, config)
        if not self._target_is_valid(side, entry, target_price):
            return Signal()
        target_distance = abs(target_price - entry)
        if target_distance < config.min_target_ticks * config.price_tick:
            return Signal()
        if strict_distance > 0 and target_distance / strict_distance < config.min_price_raw_rr:
            return Signal()

        volume = self._calc_volume(state, entry, stop_distance, config)
        if volume <= 0:
            return Signal()

        entry_bar_range = ctx.bar.high - ctx.bar.low
        current = self._current_session(state)
        current_open = current["open"] if current is not None else ctx.bar.open
        persistence = self._persistent_value_info(state, prev, config)
        context = self._window_value_info(ctx, config)
        context_target_distance = self._window_target_distance(side, entry, context)
        state.extra["value_area_trade"] = TradeInfo(
            side=side,
            entry_price=entry,
            strict_failure=strict_failure,
            stop_price=stop_price,
            target_price=target_price,
            target_distance=target_distance,
            strict_distance=strict_distance,
            price_raw_rr=target_distance / strict_distance,
            entry_bar_range=entry_bar_range,
            entry_bar_range_ratio=entry_bar_range / strict_distance,
            open_location=self._value_area_location(current_open, prev),
            prev_close_location=self._value_area_location(prev["close"], prev),
            open_poc_distance=abs(current_open - prev["poc"]),
            prev_close_poc_distance=abs(prev["close"] - prev["poc"]),
            open_close_poc_relation=self._open_close_poc_relation(current_open, prev),
            persistent_value_days=persistence["days"],
            value_overlap_ratio=persistence["overlap_ratio"],
            poc_drift=persistence["poc_drift"],
            stable_poc=persistence["stable_poc"],
            context_label=context["label"],
            context_available=context["available"],
            context_location=self._window_value_location(entry, context),
            context_target_distance=context_target_distance,
            context_price_raw_rr=context_target_distance / strict_distance if strict_distance > 0 else 0.0,
            context_persistence_bars=context["persistence_bars"],
            context_overlap_ratio=context["overlap_ratio"],
            context_poc_drift=context["poc_drift"],
            context_stable_poc=context["stable_poc"],
            vah=prev["vah"],
            val=prev["val"],
            poc=prev["poc"],
        )
        state.extra["value_area_holding_bars"] = 0
        state.extra["value_area_path_best_progress"] = 0.0
        state.extra["value_area_trade_count"] = self._trade_count(state) + 1
        state.extra.pop("value_area_long_breakout_low", None)
        state.extra.pop("value_area_short_breakout_high", None)

        action = TRADE_ACTION_BUY if side == "long" else TRADE_ACTION_SELL
        reason = "value_area_val_reaccept_long" if side == "long" else "value_area_vah_reject_short"
        signal = Signal(action=action, reason=reason, volume=volume)
        signal.diagnostics = self._diagnostics(ctx, prev, entry, strict_failure, stop_price, target_price)
        return signal

    def _exit_signal(
        self,
        state: State[ValueAreaReacceptanceParams],
        ctx: BarContext,
        config: ValueAreaReacceptanceParams,
    ) -> Signal:
        trade = self._trade_info(state)
        if trade is None:
            return Signal()

        bar = ctx.bar
        direction = state.position.direction
        reason = ""
        action = TRADE_ACTION_SELL if direction == TRADE_DIRECTION_LONG else TRADE_ACTION_BUY
        path_progress = self._update_path_progress(state, trade, bar.high, bar.low)
        if direction == TRADE_DIRECTION_LONG:
            if bar.low <= trade["stop_price"]:
                reason = "stop_loss"
            elif config.strict_close_exit and bar.close <= trade["strict_failure"]:
                reason = "strict_failure_close"
            elif bar.high >= trade["target_price"]:
                reason = "take_profit"
            elif self._path_check_failed(state, config, path_progress):
                reason = "path_failure"
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
            elif self._path_check_failed(state, config, path_progress):
                reason = "path_failure"
            elif self._is_force_flat_time(bar.datetime.time(), config):
                reason = "force_flat"
            elif config.max_hold_bars > 0 and self._holding_bars(state) >= config.max_hold_bars:
                reason = "time_exit"

        if not reason:
            return Signal()

        reason = (
            f"{reason}|td={self._distance_bucket(trade['target_distance'])}"
            f"|rr={self._rr_bucket(trade['price_raw_rr'])}"
            f"|vr={self._volatility_bucket(trade['entry_bar_range_ratio'])}"
            f"|ol={trade['open_location']}"
            f"|cl={trade['prev_close_location']}"
            f"|op={self._distance_bucket(trade['open_poc_distance'])}"
            f"|cp={self._distance_bucket(trade['prev_close_poc_distance'])}"
            f"|ocr={trade['open_close_poc_relation']}"
            f"|pd={self._persistence_bucket(trade['persistent_value_days'])}"
            f"|ov={self._overlap_bucket(trade['value_overlap_ratio'])}"
            f"|ps={self._poc_stability_bucket(trade['stable_poc'], trade['poc_drift'])}"
            f"|ctx={trade['context_label']}"
            f"|ctxloc={trade['context_location']}"
            f"|ctd={self._distance_bucket(trade['context_target_distance'])}"
            f"|crr={self._rr_bucket(trade['context_price_raw_rr'])}"
            f"|cpb={self._context_persistence_bucket(trade['context_persistence_bars'])}"
            f"|cov={self._overlap_bucket(trade['context_overlap_ratio'])}"
            f"|cps={self._poc_stability_bucket(trade['context_stable_poc'], trade['context_poc_drift'])}"
        )
        signal = Signal(action=action, reason=reason, volume=state.position.volume)
        signal.diagnostics = {
            "close": bar.close,
            "entry_price": trade["entry_price"],
            "strict_failure": trade["strict_failure"],
            "stop_price": trade["stop_price"],
            "target_price": trade["target_price"],
            "holding_bars": float(self._holding_bars(state)),
            "path_progress": path_progress,
        }
        return signal

    def _track_breakout(
        self, state: State[ValueAreaReacceptanceParams], ctx: BarContext, config: ValueAreaReacceptanceParams
    ) -> None:
        prev = self._prev_levels(state)
        if prev is None:
            return
        bar = ctx.bar
        min_breakout = config.min_breakout_ticks * config.price_tick
        if bar.low <= prev["val"] - min_breakout:
            current = self._optional_float(state.extra.get("value_area_long_breakout_low"))
            state.extra["value_area_long_breakout_low"] = bar.low if current is None else min(current, bar.low)
            state.extra["value_area_long_breakout_bars"] = self._int_extra(state, "value_area_long_breakout_bars") + 1
        if bar.high >= prev["vah"] + min_breakout:
            current = self._optional_float(state.extra.get("value_area_short_breakout_high"))
            state.extra["value_area_short_breakout_high"] = bar.high if current is None else max(current, bar.high)
            state.extra["value_area_short_breakout_bars"] = self._int_extra(state, "value_area_short_breakout_bars") + 1

    @staticmethod
    def _reacceptance_quality_ok(
        side: Literal["long", "short"],
        entry: float,
        prev: ValueAreaLevels,
        breakout_bars: int,
        config: ValueAreaReacceptanceParams,
    ) -> bool:
        if config.max_breakout_bars > 0 and breakout_bars > config.max_breakout_bars:
            return False
        min_reaccept = config.min_reaccept_ticks * config.price_tick
        if side == "long":
            return entry >= prev["val"] + min_reaccept
        return entry <= prev["vah"] - min_reaccept

    def _target_price(
        self,
        side: Literal["long", "short"],
        entry: float,
        strict_distance: float,
        prev: ValueAreaLevels,
        config: ValueAreaReacceptanceParams,
    ) -> float:
        if config.take_profit_mode == "poc":
            return prev["poc"]
        if config.take_profit_mode == "opposite":
            return prev["vah"] if side == "long" else prev["val"]
        if side == "long":
            return entry + strict_distance * config.take_profit_r
        return entry - strict_distance * config.take_profit_r

    @staticmethod
    def _target_is_valid(side: Literal["long", "short"], entry: float, target: float) -> bool:
        return target > entry if side == "long" else target < entry

    @staticmethod
    def _calc_volume(
        state: State[ValueAreaReacceptanceParams],
        entry: float,
        stop_distance: float,
        config: ValueAreaReacceptanceParams,
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

    def _update_path_progress(
        self, state: State[ValueAreaReacceptanceParams], trade: TradeInfo, high: float, low: float
    ) -> float:
        if trade["side"] == "long":
            progress = max(0.0, high - trade["entry_price"])
        else:
            progress = max(0.0, trade["entry_price"] - low)
        best = max(self._float_extra(state, "value_area_path_best_progress"), progress)
        state.extra["value_area_path_best_progress"] = best
        return best

    def _path_check_failed(
        self, state: State[ValueAreaReacceptanceParams], config: ValueAreaReacceptanceParams, path_progress: float
    ) -> bool:
        if config.path_check_bars <= 0:
            return False
        if self._holding_bars(state) < config.path_check_bars:
            return False
        return path_progress < config.min_path_progress_ticks * config.price_tick

    def _can_enter(
        self, state: State[ValueAreaReacceptanceParams], ctx: BarContext, config: ValueAreaReacceptanceParams
    ) -> bool:
        bar_time = ctx.bar.datetime.time()
        return (
            self._prev_levels(state) is not None
            and self._time_in_range(bar_time, config.trade_start_time, config.last_entry_time)
            and not self._is_force_flat_time(bar_time, config)
            and self._trade_count(state) < config.max_trades_per_day
        )

    def _ensure_session(
        self, state: State[ValueAreaReacceptanceParams], ctx: BarContext, config: ValueAreaReacceptanceParams
    ) -> None:
        bar = ctx.bar
        session = bar.datetime.date()
        current = self._current_session(state)
        if current is not None and current["date"] == session:
            return
        if current is not None:
            levels = self._build_value_area_levels(current, config)
            state.extra["value_area_levels"] = levels
            history = self._value_area_history(state)
            history.append(levels)
            state.extra["value_area_history"] = history[-5:]
        state.extra["value_area_current_session"] = CurrentSession(
            date=session,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            open=bar.open,
            profile={},
        )
        state.extra["value_area_trade_count"] = 0
        state.extra["value_area_holding_bars"] = 0
        state.extra["value_area_path_best_progress"] = 0.0
        state.extra.pop("value_area_long_breakout_low", None)
        state.extra.pop("value_area_short_breakout_high", None)
        state.extra.pop("value_area_long_breakout_bars", None)
        state.extra.pop("value_area_short_breakout_bars", None)
        state.extra.pop("value_area_trade", None)

    def _update_current_session(
        self, state: State[ValueAreaReacceptanceParams], ctx: BarContext, config: ValueAreaReacceptanceParams
    ) -> None:
        current = self._current_session(state)
        if current is None:
            return
        bar = ctx.bar
        current["high"] = max(current["high"], bar.high)
        current["low"] = min(current["low"], bar.low)
        current["close"] = bar.close
        self._add_bar_to_profile(current["profile"], bar.low, bar.high, bar.close, bar.volume, config)
        state.extra["value_area_current_session"] = current

    @classmethod
    def _add_bar_to_profile(
        cls,
        profile: dict[float, float],
        low: float,
        high: float,
        close: float,
        volume: float,
        config: ValueAreaReacceptanceParams,
    ) -> None:
        if volume <= 0:
            return
        tick = config.price_tick
        if tick <= 0:
            return
        if config.profile_mode == "close" or high < low:
            price = cls._round_to_tick(close, tick)
            profile[price] = profile.get(price, 0.0) + volume
            return

        low_tick = int(round(low / tick))
        high_tick = int(round(high / tick))
        if high_tick < low_tick:
            low_tick, high_tick = high_tick, low_tick
        bucket_count = high_tick - low_tick + 1
        volume_per_bucket = volume / bucket_count
        for price_tick in range(low_tick, high_tick + 1):
            price = price_tick * tick
            profile[price] = profile.get(price, 0.0) + volume_per_bucket

    @classmethod
    def _build_value_area_levels(cls, session: CurrentSession, config: ValueAreaReacceptanceParams) -> ValueAreaLevels:
        profile = session["profile"]
        if not profile:
            return ValueAreaLevels(
                date=session["date"],
                vah=session["high"],
                val=session["low"],
                poc=session["close"],
                high=session["high"],
                low=session["low"],
                close=session["close"],
                open=session["open"],
            )

        prices = sorted(profile)
        poc = max(prices, key=lambda price: (profile[price], -abs(price - session["close"])))
        selected = {poc}
        selected_volume = profile[poc]
        total_volume = sum(profile.values())
        target_volume = total_volume * min(max(config.value_area_ratio, 0.0), 1.0)
        poc_index = prices.index(poc)
        low_index = poc_index
        high_index = poc_index

        while selected_volume < target_volume and (low_index > 0 or high_index < len(prices) - 1):
            lower_volume = profile[prices[low_index - 1]] if low_index > 0 else -1.0
            upper_volume = profile[prices[high_index + 1]] if high_index < len(prices) - 1 else -1.0
            if upper_volume >= lower_volume and high_index < len(prices) - 1:
                high_index += 1
                price = prices[high_index]
            else:
                low_index -= 1
                price = prices[low_index]
            selected.add(price)
            selected_volume += profile[price]

        return ValueAreaLevels(
            date=session["date"],
            vah=max(selected),
            val=min(selected),
            poc=poc,
            high=session["high"],
            low=session["low"],
            close=session["close"],
            open=session["open"],
        )

    @staticmethod
    def _clear_trade_if_flat(state: State[ValueAreaReacceptanceParams]) -> None:
        state.extra.pop("value_area_trade", None)
        state.extra["value_area_holding_bars"] = 0
        state.extra["value_area_path_best_progress"] = 0.0

    @staticmethod
    def _update_holding_bars(state: State[ValueAreaReacceptanceParams], signal: Signal) -> None:
        if state.position.direction:
            state.extra["value_area_holding_bars"] = ValueAreaReacceptanceStrategyCore._holding_bars(state) + 1
        if signal.action:
            state.extra["value_area_holding_bars"] = 0

    @staticmethod
    def _holding_bars(state: State[ValueAreaReacceptanceParams]) -> int:
        value = state.extra.get("value_area_holding_bars", 0)
        return int(value) if isinstance(value, int | float) else 0

    @staticmethod
    def _trade_count(state: State[ValueAreaReacceptanceParams]) -> int:
        value = state.extra.get("value_area_trade_count", 0)
        return int(value) if isinstance(value, int | float) else 0

    @staticmethod
    def _prev_levels(state: State[ValueAreaReacceptanceParams]) -> ValueAreaLevels | None:
        value = state.extra.get("value_area_levels")
        return cast(ValueAreaLevels, value) if isinstance(value, dict) else None

    @staticmethod
    def _current_session(state: State[ValueAreaReacceptanceParams]) -> CurrentSession | None:
        value = state.extra.get("value_area_current_session")
        return cast(CurrentSession, value) if isinstance(value, dict) else None

    @staticmethod
    def _value_area_history(state: State[ValueAreaReacceptanceParams]) -> list[ValueAreaLevels]:
        value = state.extra.get("value_area_history")
        return cast(list[ValueAreaLevels], value) if isinstance(value, list) else []

    @staticmethod
    def _trade_info(state: State[ValueAreaReacceptanceParams]) -> TradeInfo | None:
        value = state.extra.get("value_area_trade")
        return cast(TradeInfo, value) if isinstance(value, dict) else None

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        return float(value) if isinstance(value, int | float) else None

    @staticmethod
    def _int_extra(state: State[ValueAreaReacceptanceParams], key: str) -> int:
        value = state.extra.get(key, 0)
        return int(value) if isinstance(value, int | float) else 0

    @staticmethod
    def _float_extra(state: State[ValueAreaReacceptanceParams], key: str) -> float:
        value = state.extra.get(key, 0.0)
        return float(value) if isinstance(value, int | float) else 0.0

    @staticmethod
    def _distance_bucket(distance: float) -> str:
        if distance < 6:
            return "lt6"
        if distance < 8:
            return "6_8"
        if distance < 12:
            return "8_12"
        return "ge12"

    @staticmethod
    def _rr_bucket(rr: float) -> str:
        if rr < 0.5:
            return "lt0_5"
        if rr < 1.0:
            return "0_5_1"
        if rr < 1.5:
            return "1_1_5"
        return "ge1_5"

    @staticmethod
    def _volatility_bucket(entry_bar_range_ratio: float) -> str:
        if entry_bar_range_ratio < 0.5:
            return "lt0_5"
        if entry_bar_range_ratio < 1.0:
            return "0_5_1"
        if entry_bar_range_ratio < 1.5:
            return "1_1_5"
        return "ge1_5"

    @classmethod
    def _persistent_value_info(
        cls, state: State[ValueAreaReacceptanceParams], prev: ValueAreaLevels, config: ValueAreaReacceptanceParams
    ) -> PersistentValueInfo:
        history = cls._value_area_history(state)
        days = 1
        min_overlap = 0.5
        stable_poc_ticks = 4
        overlap_ratios: list[float] = []
        poc_drifts: list[float] = []
        current = prev
        for older in reversed(history[:-1]):
            overlap = cls._value_area_overlap_ratio(current, older)
            poc_drift = abs(current["poc"] - older["poc"]) / config.price_tick if config.price_tick > 0 else 0.0
            if overlap < min_overlap:
                break
            days += 1
            overlap_ratios.append(overlap)
            poc_drifts.append(poc_drift)
            current = older
        max_poc_drift = max(poc_drifts, default=0.0)
        return PersistentValueInfo(
            days=days,
            overlap_ratio=min(overlap_ratios, default=1.0),
            poc_drift=max_poc_drift,
            stable_poc=max_poc_drift <= stable_poc_ticks,
        )

    @staticmethod
    def _value_area_overlap_ratio(current: ValueAreaLevels, previous: ValueAreaLevels) -> float:
        width = current["vah"] - current["val"]
        if width <= 0:
            return 0.0
        overlap = min(current["vah"], previous["vah"]) - max(current["val"], previous["val"])
        return max(0.0, overlap) / width

    @staticmethod
    def _persistence_bucket(days: int) -> str:
        if days <= 1:
            return "1d"
        if days == 2:
            return "2d"
        return "3d_plus"

    @staticmethod
    def _overlap_bucket(overlap_ratio: float) -> str:
        if overlap_ratio < 0.5:
            return "low"
        if overlap_ratio < 0.8:
            return "mid"
        return "high"

    @staticmethod
    def _poc_stability_bucket(stable: bool, poc_drift: float) -> str:
        if stable:
            return "stable"
        if poc_drift < 8:
            return "mild_drift"
        return "drift"

    @classmethod
    def _window_value_info(cls, ctx: BarContext, config: ValueAreaReacceptanceParams) -> WindowValueInfo:
        if config.rolling_context_bars > 0:
            return cls._rolling_window_value_info(ctx, config)
        if not config.context_period:
            return cls._empty_window_value_info("none")
        view = ctx.multi.get(config.context_period)
        if view is None or view.length < 2:
            return cls._empty_window_value_info(config.context_period)

        completed_bars = [bar for bar in (view.get_bar(i) for i in range(view.length - 1)) if bar is not None]
        if not completed_bars:
            return cls._empty_window_value_info(config.context_period)

        current_levels = cls._build_value_area_levels_from_bars(completed_bars[-1:], config)
        history = [cls._build_value_area_levels_from_bars([bar], config) for bar in completed_bars]
        days = 1
        min_overlap = 0.5
        stable_poc_ticks = 4
        overlap_ratios: list[float] = []
        poc_drifts: list[float] = []
        current = current_levels
        for older in reversed(history[:-1]):
            overlap = cls._value_area_overlap_ratio(current, older)
            poc_drift = abs(current["poc"] - older["poc"]) / config.price_tick if config.price_tick > 0 else 0.0
            if overlap < min_overlap:
                break
            days += 1
            overlap_ratios.append(overlap)
            poc_drifts.append(poc_drift)
            current = older
        max_poc_drift = max(poc_drifts, default=0.0)
        return WindowValueInfo(
            available=True,
            label=config.context_period,
            vah=current_levels["vah"],
            val=current_levels["val"],
            poc=current_levels["poc"],
            width=current_levels["vah"] - current_levels["val"],
            persistence_bars=days,
            overlap_ratio=min(overlap_ratios, default=1.0),
            poc_drift=max_poc_drift,
            stable_poc=max_poc_drift <= stable_poc_ticks,
        )

    @classmethod
    def _rolling_window_value_info(cls, ctx: BarContext, config: ValueAreaReacceptanceParams) -> WindowValueInfo:
        view = ctx.multi.get(config.kline_period)
        if view is None:
            return cls._empty_window_value_info(cls._rolling_context_label(config))
        bars = [bar for bar in (view.get_bar(i) for i in range(view.length)) if bar is not None]
        window = config.rolling_context_bars
        if window <= 0 or len(bars) < window * 2:
            return cls._empty_window_value_info(cls._rolling_context_label(config))

        current_bars = bars[-window:]
        previous_bars = bars[-window * 2 : -window]
        current_levels = cls._build_value_area_levels_from_bars(current_bars, config)
        previous_levels = cls._build_value_area_levels_from_bars(previous_bars, config)
        overlap = cls._value_area_overlap_ratio(current_levels, previous_levels)
        poc_drift = (
            abs(current_levels["poc"] - previous_levels["poc"]) / config.price_tick if config.price_tick > 0 else 0.0
        )
        return WindowValueInfo(
            available=True,
            label=cls._rolling_context_label(config),
            vah=current_levels["vah"],
            val=current_levels["val"],
            poc=current_levels["poc"],
            width=current_levels["vah"] - current_levels["val"],
            persistence_bars=2 if overlap >= 0.5 else 1,
            overlap_ratio=overlap,
            poc_drift=poc_drift,
            stable_poc=poc_drift <= 4,
        )

    @staticmethod
    def _rolling_context_label(config: ValueAreaReacceptanceParams) -> str:
        return f"roll{config.rolling_context_bars}"

    @classmethod
    def _build_value_area_levels_from_bars(
        cls, bars: list[Bar], config: ValueAreaReacceptanceParams
    ) -> ValueAreaLevels:
        first = bars[0]
        session = CurrentSession(
            date=cast(datetime, first.datetime).date(),
            high=float(first.high),
            low=float(first.low),
            close=float(first.close),
            open=float(first.open),
            profile={},
        )
        for bar in bars:
            session["high"] = max(session["high"], float(bar.high))
            session["low"] = min(session["low"], float(bar.low))
            session["close"] = float(bar.close)
            cls._add_bar_to_profile(
                session["profile"], float(bar.low), float(bar.high), float(bar.close), float(bar.volume), config
            )
        return cls._build_value_area_levels(session, config)

    @staticmethod
    def _empty_window_value_info(label: str) -> WindowValueInfo:
        return WindowValueInfo(
            available=False,
            label=label or "none",
            vah=0.0,
            val=0.0,
            poc=0.0,
            width=0.0,
            persistence_bars=0,
            overlap_ratio=0.0,
            poc_drift=0.0,
            stable_poc=False,
        )

    @staticmethod
    def _window_value_location(price: float, info: WindowValueInfo) -> str:
        if not info["available"]:
            return "na"
        if price > info["vah"]:
            return "above"
        if price < info["val"]:
            return "below"
        return "inside"

    @staticmethod
    def _window_target_distance(side: Literal["long", "short"], entry: float, info: WindowValueInfo) -> float:
        if not info["available"]:
            return 0.0
        if side == "long" and info["poc"] > entry:
            return info["poc"] - entry
        if side == "short" and info["poc"] < entry:
            return entry - info["poc"]
        return 0.0

    @staticmethod
    def _context_persistence_bucket(bars: int) -> str:
        if bars <= 0:
            return "na"
        if bars == 1:
            return "1b"
        if bars == 2:
            return "2b"
        return "3b_plus"

    @staticmethod
    def _value_area_location(price: float, levels: ValueAreaLevels) -> str:
        if price > levels["vah"]:
            return "above"
        if price < levels["val"]:
            return "below"
        return "inside"

    @classmethod
    def _open_close_poc_relation(cls, current_open: float, prev: ValueAreaLevels) -> str:
        open_side = cls._poc_side(current_open, prev["poc"])
        close_side = cls._poc_side(prev["close"], prev["poc"])
        if open_side == "at" and close_side == "at":
            return "both_at"
        if open_side == close_side:
            return f"same_{open_side}"
        return f"{close_side}_to_{open_side}"

    @staticmethod
    def _poc_side(price: float, poc: float) -> str:
        if price > poc:
            return "above"
        if price < poc:
            return "below"
        return "at"

    @staticmethod
    def _diagnostics(
        ctx: BarContext,
        prev: ValueAreaLevels,
        entry: float,
        strict_failure: float,
        stop_price: float,
        target_price: float,
    ) -> dict[str, float]:
        strict_distance = abs(entry - strict_failure)
        target_distance = abs(target_price - entry)
        return {
            "close": ctx.bar.close,
            "vah": prev["vah"],
            "val": prev["val"],
            "poc": prev["poc"],
            "entry_price": entry,
            "strict_failure": strict_failure,
            "strict_distance": strict_distance,
            "stop_price": stop_price,
            "target_price": target_price,
            "price_raw_rr": target_distance / strict_distance if strict_distance > 0 else 0.0,
        }

    @staticmethod
    def _round_to_tick(price: float, tick: float) -> float:
        return round(price / tick) * tick

    @staticmethod
    def _parse_time(value: str) -> time:
        hour, minute = value.split(":", maxsplit=1)
        return time(int(hour), int(minute))

    @classmethod
    def _time_in_range(cls, current: time, start: str, end: str) -> bool:
        return cls._parse_time(start) <= current <= cls._parse_time(end)

    @classmethod
    def _is_force_flat_time(cls, current: time, config: ValueAreaReacceptanceParams) -> bool:
        return current >= cls._parse_time(config.force_flat_time)

    @override
    def on_fill(self, fill: Fill) -> None:
        pass
