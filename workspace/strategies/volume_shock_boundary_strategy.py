from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from typing import Any, Literal, TypedDict, cast, override

from common.constants import TRADE_ACTION_BUY, TRADE_ACTION_SELL, TRADE_DIRECTION_LONG
from common.formulas import position_size

from .core import CORE_VERSION, Fill, Signal, State, Strategy
from .runtime import BarContext, DataRequirements, EventsRequirements, PeriodRequirements

TakeProfitMode = Literal["mid", "opposite", "r"]
ShockDirection = Literal["up", "down"]
TradeSide = Literal["long", "short"]


@dataclass
class VolumeShockBoundaryParams:
    kline_period: str = "1m"
    trade_start_time: str = "09:00"
    last_entry_time: str = "14:30"
    force_flat_time: str = "14:55"
    price_tick: float = 1.0
    volume_lookback: int = 20
    volume_multiplier: float = 2.5
    range_lookback: int = 20
    range_multiplier: float = 1.2
    min_body_ratio: float = 0.5
    shock_valid_bars: int = 60
    min_breakout_ticks: int = 1
    failure_buffer_ticks: int = 1
    take_profit_mode: TakeProfitMode = "mid"
    take_profit_r: float = 1.0
    max_hold_bars: int = 60
    stop_widen_multiplier: float = 1.0
    strict_close_exit: bool = True
    risk_per_trade: float = 0.02
    max_position_ratio: float = 0.3
    max_trades_per_day: int = 2


class ShockInfo(TypedDict):
    date: date
    direction: ShockDirection
    high: float
    low: float
    mid: float
    close: float
    bar_index: int
    volume_ratio: float
    range_ratio: float
    body_ratio: float
    traded: bool


class TradeInfo(TypedDict):
    side: TradeSide
    entry_price: float
    strict_failure: float
    stop_price: float
    target_price: float
    shock_high: float
    shock_low: float
    shock_mid: float
    volume_ratio: float
    range_ratio: float


class VolumeShockBoundaryStrategyCore(Strategy[VolumeShockBoundaryParams]):
    name: str = "volume_shock_boundary"
    VERSION: str = f"{CORE_VERSION}-volume-shock-boundary-r1"

    @override
    def data_requirements(self, config: VolumeShockBoundaryParams) -> DataRequirements | None:
        lookback = max(config.volume_lookback, config.range_lookback, 1)
        return DataRequirements(
            periods={config.kline_period: PeriodRequirements(lookback_bars=lookback)},
            indicators={},
            events=EventsRequirements.no_events(),
        )

    @override
    def on_bar(self, state: State[VolumeShockBoundaryParams], ctx: BarContext) -> Signal:
        config = state.strategy_config
        self._ensure_session(state, ctx)

        if state.position.direction:
            signal = self._exit_signal(state, ctx, config)
        else:
            self._clear_trade_if_flat(state)
            signal = self._entry_signal(state, ctx, config)

        self._update_holding_bars(state, signal)
        self._update_bar_history(state, ctx, config)
        self._detect_shock(state, ctx, config)
        self._increment_bar_index(state)
        return signal

    def _entry_signal(
        self,
        state: State[VolumeShockBoundaryParams],
        ctx: BarContext,
        config: VolumeShockBoundaryParams,
    ) -> Signal:
        shock = self._active_shock(state, ctx, config)
        if shock is None or not self._can_enter(state, ctx, config):
            return Signal()

        bar = ctx.bar
        self._track_breakout(state, bar_low=bar.low, bar_high=bar.high, shock=shock, config=config)
        long_breakout_low = self._optional_float(state.extra.get("volume_shock_long_breakout_low"))
        short_breakout_high = self._optional_float(state.extra.get("volume_shock_short_breakout_high"))

        if shock["direction"] == "down" and long_breakout_low is not None and bar.close > shock["low"]:
            return self._build_entry_signal(state, ctx, config, "long", long_breakout_low, shock)
        if shock["direction"] == "up" and short_breakout_high is not None and bar.close < shock["high"]:
            return self._build_entry_signal(state, ctx, config, "short", short_breakout_high, shock)
        return Signal()

    def _build_entry_signal(
        self,
        state: State[VolumeShockBoundaryParams],
        ctx: BarContext,
        config: VolumeShockBoundaryParams,
        side: TradeSide,
        breakout_extreme: float,
        shock: ShockInfo,
    ) -> Signal:
        entry = ctx.bar.close
        buffer = config.failure_buffer_ticks * config.price_tick
        strict_failure = breakout_extreme - buffer if side == "long" else breakout_extreme + buffer
        strict_distance = abs(entry - strict_failure)
        if strict_distance <= 0:
            return Signal()

        stop_distance = strict_distance * max(config.stop_widen_multiplier, 1.0)
        stop_price = entry - stop_distance if side == "long" else entry + stop_distance
        target_price = self._target_price(side, entry, strict_distance, shock, config)
        if not self._target_is_valid(side, entry, target_price):
            return Signal()

        volume = self._calc_volume(state, entry, stop_distance, config)
        if volume <= 0:
            return Signal()

        state.extra["volume_shock_trade"] = TradeInfo(
            side=side,
            entry_price=entry,
            strict_failure=strict_failure,
            stop_price=stop_price,
            target_price=target_price,
            shock_high=shock["high"],
            shock_low=shock["low"],
            shock_mid=shock["mid"],
            volume_ratio=shock["volume_ratio"],
            range_ratio=shock["range_ratio"],
        )
        state.extra["volume_shock_holding_bars"] = 0
        state.extra["volume_shock_trade_count"] = self._trade_count(state) + 1
        shock["traded"] = True
        state.extra["volume_shock_active"] = shock
        state.extra.pop("volume_shock_long_breakout_low", None)
        state.extra.pop("volume_shock_short_breakout_high", None)

        action = TRADE_ACTION_BUY if side == "long" else TRADE_ACTION_SELL
        reason = "volume_shock_low_reaccept_long" if side == "long" else "volume_shock_high_reject_short"
        signal = Signal(action=action, reason=reason, volume=volume)
        signal.diagnostics = self._diagnostics(ctx, shock, entry, strict_failure, stop_price, target_price)
        return signal

    def _exit_signal(
        self,
        state: State[VolumeShockBoundaryParams],
        ctx: BarContext,
        config: VolumeShockBoundaryParams,
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
            "shock_high": trade["shock_high"],
            "shock_low": trade["shock_low"],
            "shock_mid": trade["shock_mid"],
        }
        return signal

    def _detect_shock(
        self, state: State[VolumeShockBoundaryParams], ctx: BarContext, config: VolumeShockBoundaryParams
    ) -> None:
        bar = ctx.bar
        volumes = self._float_list(state.extra.get("volume_shock_volumes"))
        ranges = self._float_list(state.extra.get("volume_shock_ranges"))
        if len(volumes) < config.volume_lookback or len(ranges) < config.range_lookback:
            return

        avg_volume = sum(volumes[-config.volume_lookback :]) / config.volume_lookback
        avg_range = sum(ranges[-config.range_lookback :]) / config.range_lookback
        bar_range = bar.high - bar.low
        body = abs(bar.close - bar.open)
        if avg_volume <= 0 or avg_range <= 0 or bar_range <= 0:
            return

        volume_ratio = bar.volume / avg_volume
        range_ratio = bar_range / avg_range
        body_ratio = body / bar_range
        if (
            volume_ratio < config.volume_multiplier
            or range_ratio < config.range_multiplier
            or body_ratio < config.min_body_ratio
            or bar.close == bar.open
        ):
            return

        direction: ShockDirection = "up" if bar.close > bar.open else "down"
        state.extra["volume_shock_active"] = ShockInfo(
            date=bar.datetime.date(),
            direction=direction,
            high=bar.high,
            low=bar.low,
            mid=(bar.high + bar.low) / 2,
            close=bar.close,
            bar_index=self._bar_index(state),
            volume_ratio=volume_ratio,
            range_ratio=range_ratio,
            body_ratio=body_ratio,
            traded=False,
        )
        state.extra.pop("volume_shock_long_breakout_low", None)
        state.extra.pop("volume_shock_short_breakout_high", None)

    def _track_breakout(
        self,
        state: State[VolumeShockBoundaryParams],
        *,
        bar_low: float,
        bar_high: float,
        shock: ShockInfo,
        config: VolumeShockBoundaryParams,
    ) -> None:
        min_breakout = config.min_breakout_ticks * config.price_tick
        if shock["direction"] == "down" and bar_low <= shock["low"] - min_breakout:
            current = self._optional_float(state.extra.get("volume_shock_long_breakout_low"))
            state.extra["volume_shock_long_breakout_low"] = bar_low if current is None else min(current, bar_low)
        if shock["direction"] == "up" and bar_high >= shock["high"] + min_breakout:
            current = self._optional_float(state.extra.get("volume_shock_short_breakout_high"))
            state.extra["volume_shock_short_breakout_high"] = bar_high if current is None else max(current, bar_high)

    def _active_shock(
        self, state: State[VolumeShockBoundaryParams], ctx: BarContext, config: VolumeShockBoundaryParams
    ) -> ShockInfo | None:
        value = state.extra.get("volume_shock_active")
        if not isinstance(value, dict):
            return None
        shock = cast(ShockInfo, value)
        if shock["date"] != ctx.bar.datetime.date() or shock["traded"]:
            return None
        if self._bar_index(state) - shock["bar_index"] > config.shock_valid_bars:
            return None
        return shock

    def _target_price(
        self,
        side: TradeSide,
        entry: float,
        strict_distance: float,
        shock: ShockInfo,
        config: VolumeShockBoundaryParams,
    ) -> float:
        if config.take_profit_mode == "mid":
            return shock["mid"]
        if config.take_profit_mode == "opposite":
            return shock["high"] if side == "long" else shock["low"]
        if side == "long":
            return entry + strict_distance * config.take_profit_r
        return entry - strict_distance * config.take_profit_r

    @staticmethod
    def _target_is_valid(side: TradeSide, entry: float, target: float) -> bool:
        return target > entry if side == "long" else target < entry

    @staticmethod
    def _calc_volume(
        state: State[VolumeShockBoundaryParams],
        entry: float,
        stop_distance: float,
        config: VolumeShockBoundaryParams,
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
        self, state: State[VolumeShockBoundaryParams], ctx: BarContext, config: VolumeShockBoundaryParams
    ) -> bool:
        bar_time = ctx.bar.datetime.time()
        return (
            self._time_in_range(bar_time, config.trade_start_time, config.last_entry_time)
            and not self._is_force_flat_time(bar_time, config)
            and self._trade_count(state) < config.max_trades_per_day
        )

    def _ensure_session(self, state: State[VolumeShockBoundaryParams], ctx: BarContext) -> None:
        session = ctx.bar.datetime.date()
        if state.extra.get("volume_shock_session") == session:
            return
        state.extra["volume_shock_session"] = session
        state.extra["volume_shock_bar_index"] = 0
        state.extra["volume_shock_trade_count"] = 0
        state.extra["volume_shock_holding_bars"] = 0
        state.extra["volume_shock_volumes"] = []
        state.extra["volume_shock_ranges"] = []
        state.extra.pop("volume_shock_active", None)
        state.extra.pop("volume_shock_long_breakout_low", None)
        state.extra.pop("volume_shock_short_breakout_high", None)
        state.extra.pop("volume_shock_trade", None)

    def _update_bar_history(
        self, state: State[VolumeShockBoundaryParams], ctx: BarContext, config: VolumeShockBoundaryParams
    ) -> None:
        volumes = self._float_list(state.extra.get("volume_shock_volumes"))
        ranges = self._float_list(state.extra.get("volume_shock_ranges"))
        volumes.append(float(ctx.bar.volume))
        ranges.append(max(ctx.bar.high - ctx.bar.low, 0.0))
        max_len = max(config.volume_lookback, config.range_lookback, 1)
        state.extra["volume_shock_volumes"] = volumes[-max_len:]
        state.extra["volume_shock_ranges"] = ranges[-max_len:]

    @staticmethod
    def _clear_trade_if_flat(state: State[VolumeShockBoundaryParams]) -> None:
        state.extra.pop("volume_shock_trade", None)
        state.extra["volume_shock_holding_bars"] = 0

    @staticmethod
    def _update_holding_bars(state: State[VolumeShockBoundaryParams], signal: Signal) -> None:
        if state.position.direction:
            state.extra["volume_shock_holding_bars"] = VolumeShockBoundaryStrategyCore._holding_bars(state) + 1
        if signal.action:
            state.extra["volume_shock_holding_bars"] = 0

    @staticmethod
    def _increment_bar_index(state: State[VolumeShockBoundaryParams]) -> None:
        state.extra["volume_shock_bar_index"] = VolumeShockBoundaryStrategyCore._bar_index(state) + 1

    @staticmethod
    def _bar_index(state: State[VolumeShockBoundaryParams]) -> int:
        value = state.extra.get("volume_shock_bar_index", 0)
        return int(value) if isinstance(value, int | float) else 0

    @staticmethod
    def _holding_bars(state: State[VolumeShockBoundaryParams]) -> int:
        value = state.extra.get("volume_shock_holding_bars", 0)
        return int(value) if isinstance(value, int | float) else 0

    @staticmethod
    def _trade_count(state: State[VolumeShockBoundaryParams]) -> int:
        value = state.extra.get("volume_shock_trade_count", 0)
        return int(value) if isinstance(value, int | float) else 0

    @staticmethod
    def _trade_info(state: State[VolumeShockBoundaryParams]) -> TradeInfo | None:
        value = state.extra.get("volume_shock_trade")
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
        shock: ShockInfo,
        entry: float,
        strict_failure: float,
        stop_price: float,
        target_price: float,
    ) -> dict[str, float]:
        strict_distance = abs(entry - strict_failure)
        target_distance = abs(target_price - entry)
        return {
            "close": ctx.bar.close,
            "shock_high": shock["high"],
            "shock_low": shock["low"],
            "shock_mid": shock["mid"],
            "shock_volume_ratio": shock["volume_ratio"],
            "shock_range_ratio": shock["range_ratio"],
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
    def _is_force_flat_time(cls, current: time, config: VolumeShockBoundaryParams) -> bool:
        return current >= cls._parse_time(config.force_flat_time)

    @override
    def on_fill(self, fill: Fill) -> None:
        pass
