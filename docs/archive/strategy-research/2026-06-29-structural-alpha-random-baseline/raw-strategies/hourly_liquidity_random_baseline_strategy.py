from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal, TypedDict, cast, override

from .core import CORE_VERSION, Bar, Fill, Signal, State, Strategy
from .hourly_liquidity_sweep_strategy import (
    BandInfo,
    HourlyLiquiditySweepParams,
    HourlyLiquiditySweepStrategyCore,
    TradeSide,
)
from .runtime import BarContext, DataRequirements

RandomBaselineMode = Literal["event_window", "direction_matched"]
RandomDirectionMode = Literal["same", "random"]


class RandomCandidate(TypedDict):
    side: TradeSide
    support: BandInfo | None
    resistance: BandInfo | None


@dataclass
class HourlyLiquidityRandomBaselineParams(HourlyLiquiditySweepParams):
    random_seed: int = 42
    random_baseline_mode: RandomBaselineMode = "event_window"
    random_direction_mode: RandomDirectionMode = "same"
    random_entry_probability: float = 1.0


class HourlyLiquidityRandomBaselineStrategyCore(Strategy[HourlyLiquidityRandomBaselineParams]):
    name: str = "hourly_liquidity_random_baseline"
    VERSION: str = f"{CORE_VERSION}-hourly-liquidity-random-baseline-r1"
    config_type = HourlyLiquidityRandomBaselineParams

    def __init__(self) -> None:
        self._base = HourlyLiquiditySweepStrategyCore()

    @override
    def data_requirements(self, config: HourlyLiquidityRandomBaselineParams) -> DataRequirements | None:
        return self._base.data_requirements(config)

    @override
    def on_bar(self, state: State[HourlyLiquidityRandomBaselineParams], ctx: BarContext) -> Signal:
        config = state.strategy_config
        base_state = self._base_state(state)
        self._base._ensure_session(base_state, ctx)
        support, resistance, structure_bars = self._base._active_bands(ctx, config)
        state.extra["hourly_sweep_support_band"] = support
        state.extra["hourly_sweep_resistance_band"] = resistance
        state.extra["hourly_sweep_atr"] = self._base._average_true_range(structure_bars, config.atr_lookback)

        if state.position.direction:
            signal = self._base._exit_signal(base_state, ctx, config)
        else:
            self._base._clear_trade_if_flat(base_state)
            signal = self._entry_signal(state, ctx, config, support, resistance)

        self._base._update_holding_bars(base_state, signal)
        return signal

    def _entry_signal(
        self,
        state: State[HourlyLiquidityRandomBaselineParams],
        ctx: BarContext,
        config: HourlyLiquidityRandomBaselineParams,
        support: BandInfo | None,
        resistance: BandInfo | None,
    ) -> Signal:
        base_state = self._base_state(state)
        self._base._track_sweeps(base_state, ctx, config, support, resistance)
        if not self._base._can_enter(base_state, ctx, config):
            return Signal()

        candidates = self._candidates(state, ctx, config, support, resistance)
        if not candidates:
            return Signal()

        rng = self._rng(state, config)
        if rng.random() > config.random_entry_probability:
            return Signal()

        candidate = rng.choice(candidates)
        side = self._random_side(rng, candidate["side"], config)
        return self._build_random_entry_signal(
            state,
            ctx,
            config,
            rng,
            side,
            candidate["support"],
            candidate["resistance"],
        )

    def _candidates(
        self,
        state: State[HourlyLiquidityRandomBaselineParams],
        ctx: BarContext,
        config: HourlyLiquidityRandomBaselineParams,
        support: BandInfo | None,
        resistance: BandInfo | None,
    ) -> list[RandomCandidate]:
        long_sweep_low = self._base._optional_float(state.extra.get("hourly_sweep_long_sweep_low"))
        short_sweep_high = self._base._optional_float(state.extra.get("hourly_sweep_short_sweep_high"))
        candidates: list[RandomCandidate] = []

        if config.random_baseline_mode == "event_window":
            if support is not None and long_sweep_low is not None:
                candidates.append({"side": "long", "support": support, "resistance": resistance})
            if resistance is not None and short_sweep_high is not None:
                candidates.append({"side": "short", "support": support, "resistance": resistance})
            return candidates

        bar = ctx.bar
        if support is not None and long_sweep_low is not None and self._base._long_reaccepted(bar, support, config):
            candidates.append({"side": "long", "support": support, "resistance": resistance})
        if (
            resistance is not None
            and short_sweep_high is not None
            and self._base._short_reaccepted(bar, resistance, config)
        ):
            candidates.append({"side": "short", "support": support, "resistance": resistance})
        return candidates

    def _build_random_entry_signal(
        self,
        state: State[HourlyLiquidityRandomBaselineParams],
        ctx: BarContext,
        config: HourlyLiquidityRandomBaselineParams,
        rng: random.Random,
        side: TradeSide,
        support: BandInfo | None,
        resistance: BandInfo | None,
    ) -> Signal:
        base_state = self._base_state(state)
        for _ in range(10):
            sweep_extreme = self._random_sweep_extreme(rng, ctx.bar, side, config)
            signal = self._base._build_entry_signal(base_state, ctx, config, side, sweep_extreme, support, resistance)
            if signal.action:
                signal.reason = f"random_{signal.reason}"
                signal.diagnostics = {
                    **signal.diagnostics,
                    "random_baseline": config.random_baseline_mode,
                    "random_direction_mode": config.random_direction_mode,
                }
                return signal
        return Signal()

    @staticmethod
    def _rng(
        state: State[HourlyLiquidityRandomBaselineParams], config: HourlyLiquidityRandomBaselineParams
    ) -> random.Random:
        rng = state.extra.get("hourly_liquidity_random_rng")
        if isinstance(rng, random.Random):
            return rng
        rng = random.Random(config.random_seed)
        state.extra["hourly_liquidity_random_rng"] = rng
        return rng

    @staticmethod
    def _random_side(
        rng: random.Random,
        original_side: TradeSide,
        config: HourlyLiquidityRandomBaselineParams,
    ) -> TradeSide:
        if config.random_direction_mode == "same":
            return original_side
        return "long" if rng.random() < 0.5 else "short"

    @staticmethod
    def _random_sweep_extreme(
        rng: random.Random,
        bar: Bar,
        side: TradeSide,
        config: HourlyLiquidityRandomBaselineParams,
    ) -> float:
        buffer = config.failure_buffer_ticks * config.price_tick
        extra_ticks = rng.randint(0, 10) * config.price_tick
        if side == "long":
            return min(bar.low, bar.close - buffer - extra_ticks)
        return max(bar.high, bar.close + buffer + extra_ticks)

    @staticmethod
    def _base_state(state: State[HourlyLiquidityRandomBaselineParams]) -> State[HourlyLiquiditySweepParams]:
        return cast(State[HourlyLiquiditySweepParams], state)

    @override
    def on_fill(self, fill: Fill) -> None:
        return None
