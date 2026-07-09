from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Any, Literal, Protocol, TypedDict, cast, override

from common.constants import TRADE_ACTION_BUY, TRADE_ACTION_SELL, TRADE_DIRECTION_LONG
from common.formulas import position_size

from .core import CORE_VERSION, Bar, Fill, Signal, State, Strategy, placeholder_diagnostics
from .runtime import BarContext, DataRequirements, EventsRequirements, PeriodRequirements

DirectionMode = Literal["breakout", "impulse_continuation", "impulse_reversal"]
TradeSide = Literal["long", "short"]
ImpulseDirection = Literal["up", "down"]


@dataclass
class LowVolatilityRestartParams:
    kline_period: str = "5m"
    trade_start_time: str = "09:00"
    last_entry_time: str = "14:00"
    force_flat_time: str = "14:50"
    price_tick: float = 1.0
    atr_lookback: int = 14
    impulse_lookback: int = 12
    compression_bars: int = 6
    min_impulse_atr: float = 1.5
    min_impulse_body_ratio: float = 0.5
    max_compression_width_atr: float = 1.0
    max_compression_bar_range_atr: float = 0.45
    min_breakout_ticks: int = 1
    failure_buffer_ticks: int = 1
    direction_mode: DirectionMode = "breakout"
    take_profit_r: float = 1.0
    max_hold_bars: int = 12
    strict_close_exit: bool = True
    risk_per_trade: float = 0.02
    max_position_ratio: float = 0.3
    max_trades_per_day: int = 1


class BarView(Protocol):
    @property
    def length(self) -> int: ...

    def get_bar(self, idx: int = -1) -> Bar | None: ...


class CompressionInfo(TypedDict):
    high: float
    low: float
    width: float
    average_range: float


class ImpulseInfo(TypedDict):
    direction: ImpulseDirection
    true_range: float
    body_ratio: float
    high: float
    low: float


class TradeInfo(TypedDict):
    side: TradeSide
    entry_price: float
    strict_failure: float
    stop_price: float
    target_price: float
    compression_high: float
    compression_low: float
    impulse_direction: ImpulseDirection


class LowVolatilityRestartStrategyCore(Strategy[LowVolatilityRestartParams]):
    name: str = "low_volatility_restart"
    VERSION: str = f"{CORE_VERSION}-low-volatility-restart-r6"

    @override
    def data_requirements(self, config: LowVolatilityRestartParams) -> DataRequirements | None:
        lookback = max(
            config.atr_lookback + 1,
            config.impulse_lookback + config.compression_bars + 1,
        )
        return DataRequirements(
            periods={config.kline_period: PeriodRequirements(lookback_bars=lookback)},
            indicators={},
            events=EventsRequirements.no_events(),
        )

    @override
    @placeholder_diagnostics
    def on_bar(self, state: State[LowVolatilityRestartParams], ctx: BarContext) -> Signal:
        config = state.strategy_config
        self._ensure_session(state, ctx)
        history = self._historical_bars(ctx, config)
        atr = self._average_true_range(history, config.atr_lookback)
        state.extra["low_vol_restart_atr"] = atr

        if state.position.direction:
            signal = self._exit_signal(state, ctx, config)
        else:
            self._clear_trade_if_flat(state)
            signal = self._entry_signal(state, ctx, config, history, atr)

        self._update_holding_bars(state, signal)
        return signal

    def _entry_signal(
        self,
        state: State[LowVolatilityRestartParams],
        ctx: BarContext,
        config: LowVolatilityRestartParams,
        history: list[Bar],
        atr: float,
    ) -> Signal:
        if not self._can_enter(state, ctx, config) or atr <= 0:
            return Signal()

        compression = self._compression_info(history, config, atr)
        if compression is None:
            return Signal()
        impulse = self._impulse_info(history, config, atr)
        if impulse is None:
            return Signal()

        side = self._breakout_side(ctx.bar, compression, config)
        if side is None or not self._direction_allowed(side, impulse["direction"], config.direction_mode):
            return Signal()

        return self._build_entry_signal(state, ctx, config, side, compression, impulse, atr)

    def _build_entry_signal(
        self,
        state: State[LowVolatilityRestartParams],
        ctx: BarContext,
        config: LowVolatilityRestartParams,
        side: TradeSide,
        compression: CompressionInfo,
        impulse: ImpulseInfo,
        atr: float,
    ) -> Signal:
        entry = ctx.bar.close
        buffer = config.failure_buffer_ticks * config.price_tick
        strict_failure = compression["low"] - buffer if side == "long" else compression["high"] + buffer
        strict_distance = abs(entry - strict_failure)
        if strict_distance <= 0:
            return Signal()

        target_price = (
            entry + strict_distance * config.take_profit_r
            if side == "long"
            else entry - strict_distance * config.take_profit_r
        )
        if not self._target_is_valid(side, entry, target_price):
            return Signal()

        volume = self._calc_volume(state, entry, strict_distance, config)
        if volume <= 0:
            return Signal()

        stop_price = strict_failure
        state.extra["low_vol_restart_trade"] = TradeInfo(
            side=side,
            entry_price=entry,
            strict_failure=strict_failure,
            stop_price=stop_price,
            target_price=target_price,
            compression_high=compression["high"],
            compression_low=compression["low"],
            impulse_direction=impulse["direction"],
        )
        state.extra["low_vol_restart_holding_bars"] = 0
        state.extra["low_vol_restart_trade_count"] = self._trade_count(state) + 1

        action = TRADE_ACTION_BUY if side == "long" else TRADE_ACTION_SELL
        signal = Signal(action=action, reason=f"low_vol_restart_{side}", volume=volume)
        signal.diagnostics = self._diagnostics(
            ctx, compression, impulse, entry, strict_failure, target_price, atr, config
        )
        return signal

    def _exit_signal(
        self,
        state: State[LowVolatilityRestartParams],
        ctx: BarContext,
        config: LowVolatilityRestartParams,
    ) -> Signal:
        trade = self._trade_info(state)
        if trade is None:
            return Signal()

        bar = ctx.bar
        direction = state.position.direction
        action = TRADE_ACTION_SELL if direction == TRADE_DIRECTION_LONG else TRADE_ACTION_BUY
        reason = ""
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
        strict_distance = abs(trade["entry_price"] - trade["strict_failure"])
        signal.diagnostics = {
            "close": bar.close,
            "entry_price": trade["entry_price"],
            "strict_failure": trade["strict_failure"],
            "strict_distance": strict_distance,
            "stop_price": trade["stop_price"],
            "target_price": trade["target_price"],
            "price_raw_rr": abs(trade["target_price"] - trade["entry_price"]) / strict_distance
            if strict_distance > 0
            else 0.0,
            "holding_bars": float(self._holding_bars(state)),
            "compression_high": trade["compression_high"],
            "compression_low": trade["compression_low"],
            "impulse_direction": trade["impulse_direction"],
            "direction_mode": config.direction_mode,
            "take_profit_r": config.take_profit_r,
            "atr": self._optional_float(state.extra.get("low_vol_restart_atr")) or 0.0,
        }
        return signal

    def _historical_bars(self, ctx: BarContext, config: LowVolatilityRestartParams) -> list[Bar]:
        view = cast(BarView | None, ctx.multi.get(config.kline_period))
        if view is None:
            return []

        bars: list[Bar] = []
        for index in range(view.length - 1, -1, -1):
            historical = view.get_bar(index)
            if historical is None or historical.datetime >= ctx.bar.datetime:
                continue
            bars.append(historical)
            if len(bars) >= max(config.atr_lookback + 1, config.impulse_lookback + config.compression_bars):
                break
        return list(reversed(bars))

    @classmethod
    def _compression_info(
        cls, history: list[Bar], config: LowVolatilityRestartParams, atr: float
    ) -> CompressionInfo | None:
        if len(history) < config.compression_bars or config.compression_bars <= 0:
            return None
        bars = history[-config.compression_bars :]
        high = max(bar.high for bar in bars)
        low = min(bar.low for bar in bars)
        width = high - low
        average_range = sum(cls._bar_range(bar) for bar in bars) / len(bars)
        if width / atr > config.max_compression_width_atr:
            return None
        if average_range / atr > config.max_compression_bar_range_atr:
            return None
        return CompressionInfo(high=high, low=low, width=width, average_range=average_range)

    @classmethod
    def _impulse_info(cls, history: list[Bar], config: LowVolatilityRestartParams, atr: float) -> ImpulseInfo | None:
        if len(history) < config.impulse_lookback + config.compression_bars:
            return None
        candidates = history[-(config.impulse_lookback + config.compression_bars) : -config.compression_bars]
        for bar in reversed(candidates):
            true_range = cls._bar_range(bar)
            if true_range / atr < config.min_impulse_atr:
                continue
            body_ratio = abs(bar.close - bar.open) / true_range if true_range > 0 else 0.0
            if body_ratio < config.min_impulse_body_ratio:
                continue
            direction: ImpulseDirection = "up" if bar.close >= bar.open else "down"
            return ImpulseInfo(
                direction=direction,
                true_range=true_range,
                body_ratio=body_ratio,
                high=bar.high,
                low=bar.low,
            )
        return None

    @staticmethod
    def _breakout_side(bar: Bar, compression: CompressionInfo, config: LowVolatilityRestartParams) -> TradeSide | None:
        breakout = config.min_breakout_ticks * config.price_tick
        if bar.close >= compression["high"] + breakout:
            return "long"
        if bar.close <= compression["low"] - breakout:
            return "short"
        return None

    @staticmethod
    def _direction_allowed(side: TradeSide, impulse_direction: ImpulseDirection, mode: DirectionMode) -> bool:
        if mode == "breakout":
            return True
        continuation = (side == "long" and impulse_direction == "up") or (
            side == "short" and impulse_direction == "down"
        )
        if mode == "impulse_continuation":
            return continuation
        return not continuation

    @staticmethod
    def _bar_range(bar: Bar) -> float:
        return max(0.0, bar.high - bar.low)

    @classmethod
    def _average_true_range(cls, bars: list[Bar], lookback: int) -> float:
        if lookback <= 0 or len(bars) < 2:
            return 0.0
        true_ranges: list[float] = []
        recent = bars[-(lookback + 1) :]
        for index in range(1, len(recent)):
            current = recent[index]
            previous = recent[index - 1]
            true_ranges.append(
                max(
                    current.high - current.low,
                    abs(current.high - previous.close),
                    abs(current.low - previous.close),
                )
            )
        if not true_ranges:
            return 0.0
        values = true_ranges[-lookback:]
        return sum(values) / len(values)

    @staticmethod
    def _target_is_valid(side: TradeSide, entry: float, target: float) -> bool:
        return target > entry if side == "long" else target < entry

    @staticmethod
    def _calc_volume(
        state: State[LowVolatilityRestartParams],
        entry: float,
        stop_distance: float,
        config: LowVolatilityRestartParams,
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
        self, state: State[LowVolatilityRestartParams], ctx: BarContext, config: LowVolatilityRestartParams
    ) -> bool:
        bar_time = ctx.bar.datetime.time()
        return (
            self._time_in_range(bar_time, config.trade_start_time, config.last_entry_time)
            and not self._is_force_flat_time(bar_time, config)
            and self._trade_count(state) < config.max_trades_per_day
        )

    def _ensure_session(self, state: State[LowVolatilityRestartParams], ctx: BarContext) -> None:
        session = ctx.bar.datetime.date()
        if state.extra.get("low_vol_restart_session") == session:
            return
        state.extra["low_vol_restart_session"] = session
        state.extra["low_vol_restart_trade_count"] = 0
        state.extra["low_vol_restart_holding_bars"] = 0
        if not state.position.direction:
            state.extra.pop("low_vol_restart_trade", None)

    @staticmethod
    def _clear_trade_if_flat(state: State[LowVolatilityRestartParams]) -> None:
        state.extra.pop("low_vol_restart_trade", None)
        state.extra["low_vol_restart_holding_bars"] = 0

    @staticmethod
    def _update_holding_bars(state: State[LowVolatilityRestartParams], signal: Signal) -> None:
        if state.position.direction:
            state.extra["low_vol_restart_holding_bars"] = LowVolatilityRestartStrategyCore._holding_bars(state) + 1
        if signal.action:
            state.extra["low_vol_restart_holding_bars"] = 0

    @staticmethod
    def _holding_bars(state: State[LowVolatilityRestartParams]) -> int:
        value = state.extra.get("low_vol_restart_holding_bars", 0)
        return int(value) if isinstance(value, int | float) else 0

    @staticmethod
    def _trade_count(state: State[LowVolatilityRestartParams]) -> int:
        value = state.extra.get("low_vol_restart_trade_count", 0)
        return int(value) if isinstance(value, int | float) else 0

    @staticmethod
    def _trade_info(state: State[LowVolatilityRestartParams]) -> TradeInfo | None:
        value = state.extra.get("low_vol_restart_trade")
        return cast(TradeInfo, value) if isinstance(value, dict) else None

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        return float(value) if isinstance(value, int | float) else None

    @staticmethod
    def _diagnostics(
        ctx: BarContext,
        compression: CompressionInfo,
        impulse: ImpulseInfo,
        entry: float,
        strict_failure: float,
        target_price: float,
        atr: float,
        config: LowVolatilityRestartParams,
    ) -> dict[str, float | str]:
        strict_distance = abs(entry - strict_failure)
        target_distance = abs(target_price - entry)
        return {
            "close": ctx.bar.close,
            "entry_price": entry,
            "strict_failure": strict_failure,
            "strict_distance": strict_distance,
            "target_price": target_price,
            "price_raw_rr": target_distance / strict_distance if strict_distance > 0 else 0.0,
            "compression_high": compression["high"],
            "compression_low": compression["low"],
            "compression_width": compression["width"],
            "compression_width_atr": compression["width"] / atr if atr > 0 else 0.0,
            "compression_average_range_atr": compression["average_range"] / atr if atr > 0 else 0.0,
            "impulse_direction": impulse["direction"],
            "impulse_true_range_atr": impulse["true_range"] / atr if atr > 0 else 0.0,
            "impulse_body_ratio": impulse["body_ratio"],
            "atr": atr,
            "direction_mode": config.direction_mode,
            "take_profit_r": config.take_profit_r,
            "compression_bars": float(config.compression_bars),
            "impulse_lookback": float(config.impulse_lookback),
        }

    @staticmethod
    def _parse_time(value: str) -> time:
        hour, minute = value.split(":", maxsplit=1)
        return time(int(hour), int(minute))

    @classmethod
    def _time_in_range(cls, current: time, start: str, end: str) -> bool:
        return cls._parse_time(start) <= current <= cls._parse_time(end)

    @classmethod
    def _is_force_flat_time(cls, current: time, config: LowVolatilityRestartParams) -> bool:
        return current >= cls._parse_time(config.force_flat_time)

    @override
    def on_fill(self, fill: Fill) -> None:
        pass
