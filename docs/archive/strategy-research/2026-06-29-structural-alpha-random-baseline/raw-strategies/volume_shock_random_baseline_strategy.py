from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal, TypedDict, cast, override

from .core import CORE_VERSION, Bar, Fill, Signal, State, Strategy
from .runtime import BarContext, DataRequirements
from .volume_shock_boundary_strategy import (
    ShockInfo,
    TradeSide,
    VolumeShockBoundaryParams,
    VolumeShockBoundaryStrategyCore,
)

RandomBaselineMode = Literal["event_window", "direction_matched"]
RandomDirectionMode = Literal["same", "random"]


class RandomCandidate(TypedDict):
    side: TradeSide
    shock: ShockInfo


@dataclass
class VolumeShockRandomBaselineParams(VolumeShockBoundaryParams):
    random_seed: int = 42
    random_baseline_mode: RandomBaselineMode = "event_window"
    random_direction_mode: RandomDirectionMode = "same"
    random_entry_probability: float = 1.0


class VolumeShockRandomBaselineStrategyCore(Strategy[VolumeShockRandomBaselineParams]):
    name: str = "volume_shock_random_baseline"
    VERSION: str = f"{CORE_VERSION}-volume-shock-random-baseline-r1"
    config_type = VolumeShockRandomBaselineParams

    def __init__(self) -> None:
        self._base = VolumeShockBoundaryStrategyCore()

    @override
    def data_requirements(self, config: VolumeShockRandomBaselineParams) -> DataRequirements | None:
        return self._base.data_requirements(config)

    @override
    def on_bar(self, state: State[VolumeShockRandomBaselineParams], ctx: BarContext) -> Signal:
        config = state.strategy_config
        base_state = self._base_state(state)
        self._base._ensure_session(base_state, ctx)

        if state.position.direction:
            signal = self._base._exit_signal(base_state, ctx, config)
        else:
            self._base._clear_trade_if_flat(base_state)
            signal = self._entry_signal(state, ctx, config)

        self._base._update_holding_bars(base_state, signal)
        self._base._update_bar_history(base_state, ctx, config)
        self._base._detect_shock(base_state, ctx, config)
        self._base._increment_bar_index(base_state)
        return signal

    def _entry_signal(
        self,
        state: State[VolumeShockRandomBaselineParams],
        ctx: BarContext,
        config: VolumeShockRandomBaselineParams,
    ) -> Signal:
        base_state = self._base_state(state)
        shock = self._base._active_shock(base_state, ctx, config)
        if shock is None or not self._base._can_enter(base_state, ctx, config):
            return Signal()

        bar = ctx.bar
        self._base._track_breakout(base_state, bar_low=bar.low, bar_high=bar.high, shock=shock, config=config)
        candidates = self._candidates(state, ctx, config, shock)
        if not candidates:
            return Signal()

        rng = self._rng(state, config)
        if rng.random() > config.random_entry_probability:
            return Signal()

        candidate = rng.choice(candidates)
        side = self._random_side(rng, candidate["side"], config)
        return self._build_random_entry_signal(state, ctx, config, rng, side, candidate["shock"])

    def _candidates(
        self,
        state: State[VolumeShockRandomBaselineParams],
        ctx: BarContext,
        config: VolumeShockRandomBaselineParams,
        shock: ShockInfo,
    ) -> list[RandomCandidate]:
        long_breakout_low = self._base._optional_float(state.extra.get("volume_shock_long_breakout_low"))
        short_breakout_high = self._base._optional_float(state.extra.get("volume_shock_short_breakout_high"))
        candidates: list[RandomCandidate] = []

        if config.random_baseline_mode == "event_window":
            if shock["direction"] == "down" and long_breakout_low is not None:
                candidates.append({"side": "long", "shock": shock})
            if shock["direction"] == "up" and short_breakout_high is not None:
                candidates.append({"side": "short", "shock": shock})
            return candidates

        bar = ctx.bar
        if shock["direction"] == "down" and long_breakout_low is not None and bar.close > shock["low"]:
            candidates.append({"side": "long", "shock": shock})
        if shock["direction"] == "up" and short_breakout_high is not None and bar.close < shock["high"]:
            candidates.append({"side": "short", "shock": shock})
        return candidates

    def _build_random_entry_signal(
        self,
        state: State[VolumeShockRandomBaselineParams],
        ctx: BarContext,
        config: VolumeShockRandomBaselineParams,
        rng: random.Random,
        side: TradeSide,
        shock: ShockInfo,
    ) -> Signal:
        base_state = self._base_state(state)
        for _ in range(10):
            breakout_extreme = self._random_breakout_extreme(rng, ctx.bar, side, config)
            signal = self._base._build_entry_signal(base_state, ctx, config, side, breakout_extreme, shock)
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
    def _rng(state: State[VolumeShockRandomBaselineParams], config: VolumeShockRandomBaselineParams) -> random.Random:
        rng = state.extra.get("volume_shock_random_rng")
        if isinstance(rng, random.Random):
            return rng
        rng = random.Random(config.random_seed)
        state.extra["volume_shock_random_rng"] = rng
        return rng

    @staticmethod
    def _random_side(
        rng: random.Random,
        original_side: TradeSide,
        config: VolumeShockRandomBaselineParams,
    ) -> TradeSide:
        if config.random_direction_mode == "same":
            return original_side
        return "long" if rng.random() < 0.5 else "short"

    @staticmethod
    def _random_breakout_extreme(
        rng: random.Random,
        bar: Bar,
        side: TradeSide,
        config: VolumeShockRandomBaselineParams,
    ) -> float:
        buffer = config.failure_buffer_ticks * config.price_tick
        extra_ticks = rng.randint(0, 10) * config.price_tick
        if side == "long":
            return min(bar.low, bar.close - buffer - extra_ticks)
        return max(bar.high, bar.close + buffer + extra_ticks)

    @staticmethod
    def _base_state(state: State[VolumeShockRandomBaselineParams]) -> State[VolumeShockBoundaryParams]:
        return cast(State[VolumeShockBoundaryParams], state)

    @override
    def on_fill(self, fill: Fill) -> None:
        return None
