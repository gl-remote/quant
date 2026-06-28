from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Any, Literal, Protocol, TypedDict, cast, override

from common.constants import TRADE_ACTION_BUY, TRADE_ACTION_SELL, TRADE_DIRECTION_LONG
from common.formulas import position_size

from .core import CORE_VERSION, Bar, Fill, Signal, State, Strategy
from .runtime import BarContext, DataRequirements, EventsRequirements, PeriodRequirements

ReacceptMode = Literal["band_inner", "band_mid"]
TakeProfitMode = Literal["band_mid", "r", "opposite_band"]
TradeSide = Literal["long", "short"]
BandKind = Literal["support", "resistance"]


@dataclass
class HourlyLiquiditySweepParams:
    kline_period: str = "5m"
    structure_period: str = "1h"
    trade_start_time: str = "09:00"
    last_entry_time: str = "14:00"
    force_flat_time: str = "14:50"
    price_tick: float = 1.0
    lookback_hours: int = 24
    touch_tolerance_ticks: int = 4
    min_touches: int = 2
    min_breakout_ticks: int = 2
    failure_buffer_ticks: int = 1
    reaccept_mode: ReacceptMode = "band_inner"
    take_profit_mode: TakeProfitMode = "r"
    take_profit_r: float = 1.0
    max_hold_bars: int = 12
    stop_widen_multiplier: float = 1.0
    strict_close_exit: bool = True
    risk_per_trade: float = 0.02
    max_position_ratio: float = 0.3
    max_trades_per_day: int = 1
    atr_lookback: int = 14
    volatility_filter_enabled: bool = False
    min_sweep_atr: float = 0.0
    max_strict_distance_atr: float = 0.0
    min_target_atr: float = 0.0


class BarView(Protocol):
    @property
    def length(self) -> int: ...

    def get_bar(self, idx: int = -1) -> Bar | None: ...


class BandInfo(TypedDict):
    kind: BandKind
    lower: float
    upper: float
    mid: float
    touches: int
    first_index: int
    last_index: int


class BandCluster(TypedDict):
    prices: list[float]
    touches: int
    first_index: int
    last_index: int


class TradeInfo(TypedDict):
    side: TradeSide
    entry_price: float
    strict_failure: float
    stop_price: float
    target_price: float
    support_lower: float
    support_upper: float
    support_touches: int
    resistance_lower: float
    resistance_upper: float
    resistance_touches: int


class HourlyLiquiditySweepStrategyCore(Strategy[HourlyLiquiditySweepParams]):
    name: str = "hourly_liquidity_sweep"
    VERSION: str = f"{CORE_VERSION}-hourly-liquidity-sweep-r5"

    @override
    def data_requirements(self, config: HourlyLiquiditySweepParams) -> DataRequirements | None:
        structure_lookback = max(
            2,
            config.min_touches,
            config.atr_lookback + 1,
            self._structure_lookback_bars(config.lookback_hours, config.structure_period),
        )
        return DataRequirements(
            periods={
                config.kline_period: PeriodRequirements(lookback_bars=1),
                config.structure_period: PeriodRequirements(lookback_bars=structure_lookback),
            },
            indicators={},
            events=EventsRequirements.no_events(),
        )

    @override
    def on_bar(self, state: State[HourlyLiquiditySweepParams], ctx: BarContext) -> Signal:
        config = state.strategy_config
        self._ensure_session(state, ctx)
        support, resistance, structure_bars = self._active_bands(ctx, config)
        state.extra["hourly_sweep_support_band"] = support
        state.extra["hourly_sweep_resistance_band"] = resistance
        state.extra["hourly_sweep_atr"] = self._average_true_range(structure_bars, config.atr_lookback)

        if state.position.direction:
            signal = self._exit_signal(state, ctx, config)
        else:
            self._clear_trade_if_flat(state)
            signal = self._entry_signal(state, ctx, config, support, resistance)

        self._update_holding_bars(state, signal)
        return signal

    def _entry_signal(
        self,
        state: State[HourlyLiquiditySweepParams],
        ctx: BarContext,
        config: HourlyLiquiditySweepParams,
        support: BandInfo | None,
        resistance: BandInfo | None,
    ) -> Signal:
        self._track_sweeps(state, ctx, config, support, resistance)
        if not self._can_enter(state, ctx, config):
            return Signal()

        bar = ctx.bar
        long_sweep_low = self._optional_float(state.extra.get("hourly_sweep_long_sweep_low"))
        short_sweep_high = self._optional_float(state.extra.get("hourly_sweep_short_sweep_high"))

        if support is not None and long_sweep_low is not None and self._long_reaccepted(bar, support, config):
            return self._build_entry_signal(state, ctx, config, "long", long_sweep_low, support, resistance)
        if resistance is not None and short_sweep_high is not None and self._short_reaccepted(bar, resistance, config):
            return self._build_entry_signal(state, ctx, config, "short", short_sweep_high, support, resistance)
        return Signal()

    def _build_entry_signal(
        self,
        state: State[HourlyLiquiditySweepParams],
        ctx: BarContext,
        config: HourlyLiquiditySweepParams,
        side: TradeSide,
        sweep_extreme: float,
        support: BandInfo | None,
        resistance: BandInfo | None,
    ) -> Signal:
        entry = ctx.bar.close
        buffer = config.failure_buffer_ticks * config.price_tick
        strict_failure = sweep_extreme - buffer if side == "long" else sweep_extreme + buffer
        strict_distance = abs(entry - strict_failure)
        if strict_distance <= 0:
            return Signal()

        target_price = self._target_price(side, entry, strict_distance, support, resistance, config)
        if target_price is None or not self._target_is_valid(side, entry, target_price):
            return Signal()

        atr = self._optional_float(state.extra.get("hourly_sweep_atr"))
        if not self._passes_volatility_filter(side, entry, sweep_extreme, strict_distance, target_price, atr, config):
            return Signal()

        stop_distance = strict_distance * max(config.stop_widen_multiplier, 1.0)
        stop_price = entry - stop_distance if side == "long" else entry + stop_distance
        volume = self._calc_volume(state, entry, stop_distance, config)
        if volume <= 0:
            return Signal()

        state.extra["hourly_sweep_trade"] = TradeInfo(
            side=side,
            entry_price=entry,
            strict_failure=strict_failure,
            stop_price=stop_price,
            target_price=target_price,
            support_lower=support["lower"] if support is not None else 0.0,
            support_upper=support["upper"] if support is not None else 0.0,
            support_touches=support["touches"] if support is not None else 0,
            resistance_lower=resistance["lower"] if resistance is not None else 0.0,
            resistance_upper=resistance["upper"] if resistance is not None else 0.0,
            resistance_touches=resistance["touches"] if resistance is not None else 0,
        )
        state.extra["hourly_sweep_holding_bars"] = 0
        state.extra["hourly_sweep_trade_count"] = self._trade_count(state) + 1
        state.extra.pop("hourly_sweep_long_sweep_low", None)
        state.extra.pop("hourly_sweep_short_sweep_high", None)

        action = TRADE_ACTION_BUY if side == "long" else TRADE_ACTION_SELL
        reason = "hourly_sweep_support_reaccept_long" if side == "long" else "hourly_sweep_resistance_reject_short"
        signal = Signal(action=action, reason=reason, volume=volume)
        signal.diagnostics = self._diagnostics(
            ctx,
            support,
            resistance,
            entry,
            strict_failure,
            sweep_extreme,
            target_price,
            atr,
            config,
        )
        return signal

    def _exit_signal(
        self,
        state: State[HourlyLiquiditySweepParams],
        ctx: BarContext,
        config: HourlyLiquiditySweepParams,
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
            "support_lower": trade["support_lower"],
            "support_upper": trade["support_upper"],
            "support_touches": float(trade["support_touches"]),
            "resistance_lower": trade["resistance_lower"],
            "resistance_upper": trade["resistance_upper"],
            "resistance_touches": float(trade["resistance_touches"]),
            "reaccept_mode": config.reaccept_mode,
            "take_profit_mode": config.take_profit_mode,
            "lookback_hours": float(config.lookback_hours),
            "hourly_atr": self._optional_float(state.extra.get("hourly_sweep_atr")) or 0.0,
            "volatility_filter_enabled": str(config.volatility_filter_enabled),
        }
        return signal

    def _track_sweeps(
        self,
        state: State[HourlyLiquiditySweepParams],
        ctx: BarContext,
        config: HourlyLiquiditySweepParams,
        support: BandInfo | None,
        resistance: BandInfo | None,
    ) -> None:
        bar = ctx.bar
        min_breakout = config.min_breakout_ticks * config.price_tick
        if support is not None and bar.low <= support["lower"] - min_breakout:
            current = self._optional_float(state.extra.get("hourly_sweep_long_sweep_low"))
            state.extra["hourly_sweep_long_sweep_low"] = bar.low if current is None else min(current, bar.low)
        if resistance is not None and bar.high >= resistance["upper"] + min_breakout:
            current = self._optional_float(state.extra.get("hourly_sweep_short_sweep_high"))
            state.extra["hourly_sweep_short_sweep_high"] = bar.high if current is None else max(current, bar.high)

    def _active_bands(
        self, ctx: BarContext, config: HourlyLiquiditySweepParams
    ) -> tuple[BandInfo | None, BandInfo | None, list[Bar]]:
        structure_view = cast(BarView | None, ctx.multi.get(config.structure_period))
        if structure_view is None:
            return None, None, []

        bars = self._historical_structure_bars(structure_view, ctx.bar, config)
        return self._support_band(bars, config), self._resistance_band(bars, config), bars

    def _historical_structure_bars(
        self, structure_view: BarView, current_bar: Bar, config: HourlyLiquiditySweepParams
    ) -> list[Bar]:
        limit = self._structure_lookback_bars(config.lookback_hours, config.structure_period)
        bars: list[Bar] = []
        for index in range(structure_view.length - 1, -1, -1):
            historical = structure_view.get_bar(index)
            if historical is None or historical.datetime >= current_bar.datetime:
                continue
            bars.append(historical)
            if len(bars) >= limit:
                break
        return list(reversed(bars))

    @classmethod
    def _support_band(cls, bars: list[Bar], config: HourlyLiquiditySweepParams) -> BandInfo | None:
        bands = cls._price_bands([bar.low for bar in bars], "support", config)
        if not bands:
            return None
        return max(bands, key=lambda band: (band["touches"], band["last_index"], -band["mid"]))

    @classmethod
    def _resistance_band(cls, bars: list[Bar], config: HourlyLiquiditySweepParams) -> BandInfo | None:
        bands = cls._price_bands([bar.high for bar in bars], "resistance", config)
        if not bands:
            return None
        return max(bands, key=lambda band: (band["touches"], band["last_index"], band["mid"]))

    @classmethod
    def _price_bands(cls, prices: list[float], kind: BandKind, config: HourlyLiquiditySweepParams) -> list[BandInfo]:
        tolerance = config.touch_tolerance_ticks * config.price_tick
        clusters: list[BandCluster] = []
        for index, price in enumerate(prices):
            cluster_index = cls._matching_cluster_index(clusters, price, tolerance)
            if cluster_index is None:
                clusters.append(BandCluster(prices=[price], touches=1, first_index=index, last_index=index))
                continue
            cluster = clusters[cluster_index]
            cluster["prices"].append(price)
            cluster["touches"] += 1
            cluster["last_index"] = index

        bands: list[BandInfo] = []
        for cluster in clusters:
            if cluster["touches"] < config.min_touches:
                continue
            lower = min(cluster["prices"])
            upper = max(cluster["prices"])
            bands.append(
                BandInfo(
                    kind=kind,
                    lower=lower,
                    upper=upper,
                    mid=(lower + upper) / 2,
                    touches=cluster["touches"],
                    first_index=cluster["first_index"],
                    last_index=cluster["last_index"],
                )
            )
        return bands

    @staticmethod
    def _matching_cluster_index(clusters: list[BandCluster], price: float, tolerance: float) -> int | None:
        for index, cluster in enumerate(clusters):
            cluster_mid = sum(cluster["prices"]) / len(cluster["prices"])
            if abs(price - cluster_mid) <= tolerance:
                return index
        return None

    @staticmethod
    def _long_reaccepted(bar: Bar, support: BandInfo, config: HourlyLiquiditySweepParams) -> bool:
        if config.reaccept_mode == "band_mid":
            return bar.close >= support["mid"]
        return bar.close >= support["lower"]

    @staticmethod
    def _short_reaccepted(bar: Bar, resistance: BandInfo, config: HourlyLiquiditySweepParams) -> bool:
        if config.reaccept_mode == "band_mid":
            return bar.close <= resistance["mid"]
        return bar.close <= resistance["upper"]

    @staticmethod
    def _target_price(
        side: TradeSide,
        entry: float,
        strict_distance: float,
        support: BandInfo | None,
        resistance: BandInfo | None,
        config: HourlyLiquiditySweepParams,
    ) -> float | None:
        if config.take_profit_mode == "band_mid":
            band = support if side == "long" else resistance
            return band["mid"] if band is not None else None
        if config.take_profit_mode == "opposite_band":
            band = resistance if side == "long" else support
            return band["mid"] if band is not None else None
        if side == "long":
            return entry + strict_distance * config.take_profit_r
        return entry - strict_distance * config.take_profit_r

    @staticmethod
    def _target_is_valid(side: TradeSide, entry: float, target: float) -> bool:
        return target > entry if side == "long" else target < entry

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

    @classmethod
    def _passes_volatility_filter(
        cls,
        side: TradeSide,
        entry: float,
        sweep_extreme: float,
        strict_distance: float,
        target_price: float,
        atr: float | None,
        config: HourlyLiquiditySweepParams,
    ) -> bool:
        if not config.volatility_filter_enabled:
            return True
        if atr is None or atr <= 0:
            return False

        sweep_depth = abs(entry - sweep_extreme)
        target_distance = abs(target_price - entry)
        if config.min_sweep_atr > 0 and sweep_depth / atr < config.min_sweep_atr:
            return False
        if config.max_strict_distance_atr > 0 and strict_distance / atr > config.max_strict_distance_atr:
            return False
        if config.min_target_atr > 0 and target_distance / atr < config.min_target_atr:
            return False
        return cls._target_is_valid(side, entry, target_price)

    @staticmethod
    def _calc_volume(
        state: State[HourlyLiquiditySweepParams],
        entry: float,
        stop_distance: float,
        config: HourlyLiquiditySweepParams,
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

    @classmethod
    def _structure_lookback_bars(cls, lookback_hours: int, structure_period: str) -> int:
        minutes = cls._period_minutes(structure_period)
        return max(1, int((lookback_hours * 60 + minutes - 1) // minutes))

    @staticmethod
    def _period_minutes(period: str) -> int:
        unit = period[-1]
        value_text = period[:-1]
        value = int(value_text) if value_text else 1
        if unit == "m":
            return value
        if unit == "h":
            return value * 60
        if unit == "d":
            return value * 24 * 60
        return 60

    def _can_enter(
        self, state: State[HourlyLiquiditySweepParams], ctx: BarContext, config: HourlyLiquiditySweepParams
    ) -> bool:
        bar_time = ctx.bar.datetime.time()
        return (
            self._time_in_range(bar_time, config.trade_start_time, config.last_entry_time)
            and not self._is_force_flat_time(bar_time, config)
            and self._trade_count(state) < config.max_trades_per_day
        )

    def _ensure_session(self, state: State[HourlyLiquiditySweepParams], ctx: BarContext) -> None:
        session = ctx.bar.datetime.date()
        if state.extra.get("hourly_sweep_session") == session:
            return
        state.extra["hourly_sweep_session"] = session
        state.extra["hourly_sweep_trade_count"] = 0
        state.extra["hourly_sweep_holding_bars"] = 0
        state.extra.pop("hourly_sweep_long_sweep_low", None)
        state.extra.pop("hourly_sweep_short_sweep_high", None)
        if not state.position.direction:
            state.extra.pop("hourly_sweep_trade", None)

    @staticmethod
    def _clear_trade_if_flat(state: State[HourlyLiquiditySweepParams]) -> None:
        state.extra.pop("hourly_sweep_trade", None)
        state.extra["hourly_sweep_holding_bars"] = 0

    @staticmethod
    def _update_holding_bars(state: State[HourlyLiquiditySweepParams], signal: Signal) -> None:
        if state.position.direction:
            state.extra["hourly_sweep_holding_bars"] = HourlyLiquiditySweepStrategyCore._holding_bars(state) + 1
        if signal.action:
            state.extra["hourly_sweep_holding_bars"] = 0

    @staticmethod
    def _holding_bars(state: State[HourlyLiquiditySweepParams]) -> int:
        value = state.extra.get("hourly_sweep_holding_bars", 0)
        return int(value) if isinstance(value, int | float) else 0

    @staticmethod
    def _trade_count(state: State[HourlyLiquiditySweepParams]) -> int:
        value = state.extra.get("hourly_sweep_trade_count", 0)
        return int(value) if isinstance(value, int | float) else 0

    @staticmethod
    def _trade_info(state: State[HourlyLiquiditySweepParams]) -> TradeInfo | None:
        value = state.extra.get("hourly_sweep_trade")
        return cast(TradeInfo, value) if isinstance(value, dict) else None

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        return float(value) if isinstance(value, int | float) else None

    @staticmethod
    def _diagnostics(
        ctx: BarContext,
        support: BandInfo | None,
        resistance: BandInfo | None,
        entry: float,
        strict_failure: float,
        sweep_extreme: float,
        target_price: float,
        atr: float | None,
        config: HourlyLiquiditySweepParams,
    ) -> dict[str, float | str]:
        strict_distance = abs(entry - strict_failure)
        target_distance = abs(target_price - entry)
        sweep_depth = abs(entry - sweep_extreme)
        hourly_atr = atr or 0.0
        return {
            "close": ctx.bar.close,
            "support_lower": support["lower"] if support is not None else 0.0,
            "support_upper": support["upper"] if support is not None else 0.0,
            "support_touches": float(support["touches"] if support is not None else 0),
            "resistance_lower": resistance["lower"] if resistance is not None else 0.0,
            "resistance_upper": resistance["upper"] if resistance is not None else 0.0,
            "resistance_touches": float(resistance["touches"] if resistance is not None else 0),
            "entry_price": entry,
            "strict_failure": strict_failure,
            "strict_distance": strict_distance,
            "target_price": target_price,
            "price_raw_rr": target_distance / strict_distance if strict_distance > 0 else 0.0,
            "hourly_atr": hourly_atr,
            "sweep_depth_atr": sweep_depth / hourly_atr if hourly_atr > 0 else 0.0,
            "strict_distance_atr": strict_distance / hourly_atr if hourly_atr > 0 else 0.0,
            "target_distance_atr": target_distance / hourly_atr if hourly_atr > 0 else 0.0,
            "volatility_filter_enabled": str(config.volatility_filter_enabled),
            "min_sweep_atr": config.min_sweep_atr,
            "max_strict_distance_atr": config.max_strict_distance_atr,
            "min_target_atr": config.min_target_atr,
            "reaccept_mode": config.reaccept_mode,
            "take_profit_mode": config.take_profit_mode,
            "lookback_hours": float(config.lookback_hours),
        }

    @staticmethod
    def _parse_time(value: str) -> time:
        hour, minute = value.split(":", maxsplit=1)
        return time(int(hour), int(minute))

    @classmethod
    def _time_in_range(cls, current: time, start: str, end: str) -> bool:
        return cls._parse_time(start) <= current <= cls._parse_time(end)

    @classmethod
    def _is_force_flat_time(cls, current: time, config: HourlyLiquiditySweepParams) -> bool:
        return current >= cls._parse_time(config.force_flat_time)

    @override
    def on_fill(self, fill: Fill) -> None:
        pass
