from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from typing import Any, Literal, TypedDict, cast, override

from common.constants import TRADE_ACTION_BUY, TRADE_ACTION_SELL, TRADE_DIRECTION_LONG
from common.formulas import position_size

from .core import CORE_VERSION, Bar, Fill, Signal, State, Strategy
from .runtime import BarContext, DataRequirements, EventsRequirements, PeriodRequirements

TakeProfitMode = Literal["mid", "close", "open", "opposite", "r"]
VolumeFilterStage = Literal["breakout", "reaccept", "either"]
TradeSide = Literal["long", "short"]


@dataclass
class PrevdayVolumeFilterParams:
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
    volume_filter_enabled: bool = True
    volume_filter_stage: VolumeFilterStage = "breakout"
    volume_lookback: int = 20
    volume_multiplier: float = 2.0
    range_lookback: int = 20
    range_multiplier: float = 1.0
    min_body_ratio: float = 0.0


class DayLevels(TypedDict):
    date: date
    high: float
    low: float
    close: float
    open: float


class ShockMetrics(TypedDict):
    is_shock: bool
    volume_ratio: float
    range_ratio: float
    body_ratio: float


class TradeInfo(TypedDict):
    side: TradeSide
    entry_price: float
    strict_failure: float
    stop_price: float
    target_price: float
    prev_high: float
    prev_low: float
    prev_close: float
    breakout_shock: bool
    reaccept_shock: bool
    volume_ratio: float
    range_ratio: float
    body_ratio: float


class PrevdayVolumeFilterStrategyCore(Strategy[PrevdayVolumeFilterParams]):
    name: str = "prevday_volume_filter"
    VERSION: str = f"{CORE_VERSION}-prevday-volume-filter-r1"

    @override
    def data_requirements(self, config: PrevdayVolumeFilterParams) -> DataRequirements | None:
        lookback = max(1, config.volume_lookback, config.range_lookback) if config.volume_filter_enabled else 1
        return DataRequirements(
            periods={config.kline_period: PeriodRequirements(lookback_bars=lookback)},
            indicators={},
            events=EventsRequirements.no_events(),
        )

    @override
    def on_bar(self, state: State[PrevdayVolumeFilterParams], ctx: BarContext) -> Signal:
        config = state.strategy_config
        self._ensure_session(state, ctx)

        metrics = self._shock_metrics(state, ctx, config)
        state.extra["prevday_volume_last_metrics"] = metrics
        if state.position.direction:
            signal = self._exit_signal(state, ctx, config)
        else:
            self._clear_trade_if_flat(state)
            signal = self._entry_signal(state, ctx, config, metrics)

        self._update_holding_bars(state, signal)
        self._update_current_levels(state, ctx)
        self._update_bar_history(state, ctx, config)
        return signal

    def _entry_signal(
        self,
        state: State[PrevdayVolumeFilterParams],
        ctx: BarContext,
        config: PrevdayVolumeFilterParams,
        metrics: ShockMetrics,
    ) -> Signal:
        if not self._can_enter(state, ctx, config):
            self._track_breakout(state, ctx, config, metrics)
            return Signal()

        prev = self._prev_levels(state)
        if prev is None:
            return Signal()

        bar = ctx.bar
        self._track_breakout(state, ctx, config, metrics)
        long_breakout_low = self._optional_float(state.extra.get("prevday_volume_long_breakout_low"))
        short_breakout_high = self._optional_float(state.extra.get("prevday_volume_short_breakout_high"))
        breakout_shock = bool(state.extra.get("prevday_volume_breakout_shock", False))
        reaccept_shock = metrics["is_shock"]

        if long_breakout_low is not None and bar.close > prev["low"]:
            return self._build_entry_signal(
                state, ctx, config, "long", long_breakout_low, prev, breakout_shock, reaccept_shock, metrics
            )
        if short_breakout_high is not None and bar.close < prev["high"]:
            return self._build_entry_signal(
                state, ctx, config, "short", short_breakout_high, prev, breakout_shock, reaccept_shock, metrics
            )
        return Signal()

    def _build_entry_signal(
        self,
        state: State[PrevdayVolumeFilterParams],
        ctx: BarContext,
        config: PrevdayVolumeFilterParams,
        side: TradeSide,
        breakout_extreme: float,
        prev: DayLevels,
        breakout_shock: bool,
        reaccept_shock: bool,
        metrics: ShockMetrics,
    ) -> Signal:
        if not self._passes_volume_filter(config, breakout_shock, reaccept_shock):
            return Signal()

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

        state.extra["prevday_volume_trade"] = TradeInfo(
            side=side,
            entry_price=entry,
            strict_failure=strict_failure,
            stop_price=stop_price,
            target_price=target_price,
            prev_high=prev["high"],
            prev_low=prev["low"],
            prev_close=prev["close"],
            breakout_shock=breakout_shock,
            reaccept_shock=reaccept_shock,
            volume_ratio=metrics["volume_ratio"],
            range_ratio=metrics["range_ratio"],
            body_ratio=metrics["body_ratio"],
        )
        state.extra["prevday_volume_holding_bars"] = 0
        state.extra["prevday_volume_trade_count"] = self._trade_count(state) + 1
        state.extra.pop("prevday_volume_long_breakout_low", None)
        state.extra.pop("prevday_volume_short_breakout_high", None)
        state.extra.pop("prevday_volume_breakout_shock", None)

        action = TRADE_ACTION_BUY if side == "long" else TRADE_ACTION_SELL
        reason = "prevday_volume_low_reaccept_long" if side == "long" else "prevday_volume_high_reject_short"
        signal = Signal(action=action, reason=reason, volume=volume)
        signal.diagnostics = self._diagnostics(
            ctx,
            prev,
            entry,
            strict_failure,
            stop_price,
            target_price,
            config,
            breakout_shock,
            reaccept_shock,
            metrics,
        )
        return signal

    def _exit_signal(
        self,
        state: State[PrevdayVolumeFilterParams],
        ctx: BarContext,
        config: PrevdayVolumeFilterParams,
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
            "prev_high": trade["prev_high"],
            "prev_low": trade["prev_low"],
            "volume_filter_enabled": config.volume_filter_enabled,
            "volume_filter_stage": config.volume_filter_stage,
            "breakout_shock": trade["breakout_shock"],
            "reaccept_shock": trade["reaccept_shock"],
            "volume_ratio": trade["volume_ratio"],
            "range_ratio": trade["range_ratio"],
            "body_ratio": trade["body_ratio"],
        }
        return signal

    def _track_breakout(
        self,
        state: State[PrevdayVolumeFilterParams],
        ctx: BarContext,
        config: PrevdayVolumeFilterParams,
        metrics: ShockMetrics,
    ) -> None:
        prev = self._prev_levels(state)
        if prev is None:
            return
        bar = ctx.bar
        min_breakout = config.min_breakout_ticks * config.price_tick
        if bar.low <= prev["low"] - min_breakout:
            current = self._optional_float(state.extra.get("prevday_volume_long_breakout_low"))
            state.extra["prevday_volume_long_breakout_low"] = bar.low if current is None else min(current, bar.low)
            if metrics["is_shock"]:
                state.extra["prevday_volume_breakout_shock"] = True
        if bar.high >= prev["high"] + min_breakout:
            current = self._optional_float(state.extra.get("prevday_volume_short_breakout_high"))
            state.extra["prevday_volume_short_breakout_high"] = bar.high if current is None else max(current, bar.high)
            if metrics["is_shock"]:
                state.extra["prevday_volume_breakout_shock"] = True

    def _shock_metrics(
        self, state: State[PrevdayVolumeFilterParams], ctx: BarContext, config: PrevdayVolumeFilterParams
    ) -> ShockMetrics:
        volumes, ranges = self._history_from_context(ctx, config)
        if len(volumes) < config.volume_lookback or len(ranges) < config.range_lookback:
            volumes = self._float_list(state.extra.get("prevday_volume_volumes"))
            ranges = self._float_list(state.extra.get("prevday_volume_ranges"))
        if len(volumes) < config.volume_lookback or len(ranges) < config.range_lookback:
            return ShockMetrics(is_shock=False, volume_ratio=0.0, range_ratio=0.0, body_ratio=0.0)

        avg_volume = sum(volumes[-config.volume_lookback :]) / config.volume_lookback
        avg_range = sum(ranges[-config.range_lookback :]) / config.range_lookback
        return self._bar_shock_metrics(ctx.bar, avg_volume, avg_range, config)

    @staticmethod
    def _history_from_context(ctx: BarContext, config: PrevdayVolumeFilterParams) -> tuple[list[float], list[float]]:
        history = ctx.multi.get(config.kline_period)
        if history is None:
            return [], []

        volumes: list[float] = []
        ranges: list[float] = []
        for index in range(history.length - 1, -1, -1):
            historical = history.bar(index)
            if historical is None or historical.datetime >= ctx.bar.datetime:
                continue
            if len(volumes) < config.volume_lookback:
                volumes.append(float(historical.volume))
            if len(ranges) < config.range_lookback:
                ranges.append(max(historical.high - historical.low, 0.0))
            if len(volumes) >= config.volume_lookback and len(ranges) >= config.range_lookback:
                break
        return list(reversed(volumes)), list(reversed(ranges))

    @staticmethod
    def _bar_shock_metrics(
        bar: Bar, avg_volume: float, avg_range: float, config: PrevdayVolumeFilterParams
    ) -> ShockMetrics:
        bar_range = bar.high - bar.low
        if avg_volume <= 0 or avg_range <= 0 or bar_range <= 0:
            return ShockMetrics(is_shock=False, volume_ratio=0.0, range_ratio=0.0, body_ratio=0.0)

        volume_ratio = bar.volume / avg_volume
        range_ratio = bar_range / avg_range
        body_ratio = abs(bar.close - bar.open) / bar_range
        return ShockMetrics(
            is_shock=(
                volume_ratio >= config.volume_multiplier
                and range_ratio >= config.range_multiplier
                and body_ratio >= config.min_body_ratio
            ),
            volume_ratio=volume_ratio,
            range_ratio=range_ratio,
            body_ratio=body_ratio,
        )

    @staticmethod
    def _passes_volume_filter(config: PrevdayVolumeFilterParams, breakout_shock: bool, reaccept_shock: bool) -> bool:
        if not config.volume_filter_enabled:
            return True
        if config.volume_filter_stage == "breakout":
            return breakout_shock
        if config.volume_filter_stage == "reaccept":
            return reaccept_shock
        return breakout_shock or reaccept_shock

    def _target_price(
        self,
        side: TradeSide,
        entry: float,
        strict_distance: float,
        prev: DayLevels,
        state: State[PrevdayVolumeFilterParams],
        config: PrevdayVolumeFilterParams,
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
    def _target_is_valid(side: TradeSide, entry: float, target: float) -> bool:
        return target > entry if side == "long" else target < entry

    @staticmethod
    def _calc_volume(
        state: State[PrevdayVolumeFilterParams],
        entry: float,
        stop_distance: float,
        config: PrevdayVolumeFilterParams,
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
        self, state: State[PrevdayVolumeFilterParams], ctx: BarContext, config: PrevdayVolumeFilterParams
    ) -> bool:
        bar_time = ctx.bar.datetime.time()
        return (
            self._prev_levels(state) is not None
            and self._time_in_range(bar_time, config.trade_start_time, config.last_entry_time)
            and not self._is_force_flat_time(bar_time, config)
            and self._trade_count(state) < config.max_trades_per_day
        )

    def _ensure_session(self, state: State[PrevdayVolumeFilterParams], ctx: BarContext) -> None:
        bar = ctx.bar
        session = bar.datetime.date()
        current = self._current_levels(state)
        if current is not None and current["date"] == session:
            return
        if current is not None:
            state.extra["prevday_volume_levels"] = current
        state.extra["prevday_volume_current_levels"] = DayLevels(
            date=session,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            open=bar.open,
        )
        state.extra["prevday_volume_trade_count"] = 0
        state.extra["prevday_volume_holding_bars"] = 0
        state.extra["prevday_volume_volumes"] = []
        state.extra["prevday_volume_ranges"] = []
        state.extra.pop("prevday_volume_long_breakout_low", None)
        state.extra.pop("prevday_volume_short_breakout_high", None)
        state.extra.pop("prevday_volume_breakout_shock", None)
        state.extra.pop("prevday_volume_trade", None)

    def _update_current_levels(self, state: State[PrevdayVolumeFilterParams], ctx: BarContext) -> None:
        current = self._current_levels(state)
        if current is None:
            return
        bar = ctx.bar
        current["high"] = max(current["high"], bar.high)
        current["low"] = min(current["low"], bar.low)
        current["close"] = bar.close
        state.extra["prevday_volume_current_levels"] = current

    def _update_bar_history(
        self, state: State[PrevdayVolumeFilterParams], ctx: BarContext, config: PrevdayVolumeFilterParams
    ) -> None:
        volumes = self._float_list(state.extra.get("prevday_volume_volumes"))
        ranges = self._float_list(state.extra.get("prevday_volume_ranges"))
        volumes.append(float(ctx.bar.volume))
        ranges.append(max(ctx.bar.high - ctx.bar.low, 0.0))
        max_len = max(1, config.volume_lookback, config.range_lookback)
        state.extra["prevday_volume_volumes"] = volumes[-max_len:]
        state.extra["prevday_volume_ranges"] = ranges[-max_len:]

    @staticmethod
    def _clear_trade_if_flat(state: State[PrevdayVolumeFilterParams]) -> None:
        state.extra.pop("prevday_volume_trade", None)
        state.extra["prevday_volume_holding_bars"] = 0

    @staticmethod
    def _update_holding_bars(state: State[PrevdayVolumeFilterParams], signal: Signal) -> None:
        if state.position.direction:
            state.extra["prevday_volume_holding_bars"] = PrevdayVolumeFilterStrategyCore._holding_bars(state) + 1
        if signal.action:
            state.extra["prevday_volume_holding_bars"] = 0

    @staticmethod
    def _holding_bars(state: State[PrevdayVolumeFilterParams]) -> int:
        value = state.extra.get("prevday_volume_holding_bars", 0)
        return int(value) if isinstance(value, int | float) else 0

    @staticmethod
    def _trade_count(state: State[PrevdayVolumeFilterParams]) -> int:
        value = state.extra.get("prevday_volume_trade_count", 0)
        return int(value) if isinstance(value, int | float) else 0

    @staticmethod
    def _prev_levels(state: State[PrevdayVolumeFilterParams]) -> DayLevels | None:
        value = state.extra.get("prevday_volume_levels")
        return cast(DayLevels, value) if isinstance(value, dict) else None

    @staticmethod
    def _current_levels(state: State[PrevdayVolumeFilterParams]) -> DayLevels | None:
        value = state.extra.get("prevday_volume_current_levels")
        return cast(DayLevels, value) if isinstance(value, dict) else None

    @staticmethod
    def _trade_info(state: State[PrevdayVolumeFilterParams]) -> TradeInfo | None:
        value = state.extra.get("prevday_volume_trade")
        return cast(TradeInfo, value) if isinstance(value, dict) else None

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        return float(value) if isinstance(value, int | float) else None

    @staticmethod
    def _float_list(value: Any) -> list[float]:
        if not isinstance(value, list):
            return []
        return [float(item) for item in value if isinstance(item, int | float)]

    @staticmethod
    def _diagnostics(
        ctx: BarContext,
        prev: DayLevels,
        entry: float,
        strict_failure: float,
        stop_price: float,
        target_price: float,
        config: PrevdayVolumeFilterParams,
        breakout_shock: bool,
        reaccept_shock: bool,
        metrics: ShockMetrics,
    ) -> dict[str, float | bool | str]:
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
            "volume_filter_enabled": config.volume_filter_enabled,
            "volume_filter_stage": config.volume_filter_stage,
            "breakout_shock": breakout_shock,
            "reaccept_shock": reaccept_shock,
            "volume_ratio": metrics["volume_ratio"],
            "range_ratio": metrics["range_ratio"],
            "body_ratio": metrics["body_ratio"],
        }

    @staticmethod
    def _parse_time(value: str) -> time:
        hour, minute = value.split(":", maxsplit=1)
        return time(int(hour), int(minute))

    @classmethod
    def _time_in_range(cls, current: time, start: str, end: str) -> bool:
        return cls._parse_time(start) <= current <= cls._parse_time(end)

    @classmethod
    def _is_force_flat_time(cls, current: time, config: PrevdayVolumeFilterParams) -> bool:
        return current >= cls._parse_time(config.force_flat_time)

    @override
    def on_fill(self, fill: Fill) -> None:
        pass
