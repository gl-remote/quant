from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal, TypedDict, cast, override

from .core import CORE_VERSION, Bar, Fill, Signal, State, Strategy
from .prevday_reacceptance_strategy import (
    DayLevels,
    PrevdayReacceptanceParams,
    PrevdayReacceptanceStrategyCore,
)
from .runtime import BarContext, DataRequirements

RandomBaselineMode = Literal["event_window", "direction_matched"]
RandomDirectionMode = Literal["same", "random"]
TradeSide = Literal["long", "short"]


class RandomCandidate(TypedDict):
    side: TradeSide
    prev: DayLevels


@dataclass
class PrevdayRandomBaselineParams(PrevdayReacceptanceParams):
    random_seed: int = 42
    random_baseline_mode: RandomBaselineMode = "event_window"
    random_direction_mode: RandomDirectionMode = "same"
    random_entry_probability: float = 1.0


class PrevdayRandomBaselineStrategyCore(Strategy[PrevdayRandomBaselineParams]):
    name: str = "prevday_random_baseline"
    VERSION: str = f"{CORE_VERSION}-prevday-random-baseline-r1"
    config_type = PrevdayRandomBaselineParams

    def __init__(self) -> None:
        self._base = PrevdayReacceptanceStrategyCore()

    @override
    def data_requirements(self, config: PrevdayRandomBaselineParams) -> DataRequirements | None:
        return self._base.data_requirements(config)

    @override
    def on_bar(self, state: State[PrevdayRandomBaselineParams], ctx: BarContext) -> Signal:
        config = state.strategy_config
        base_state = self._base_state(state)
        self._base._ensure_session(base_state, ctx)

        if state.position.direction:
            signal = self._base._exit_signal(base_state, ctx, config)
        else:
            self._base._clear_trade_if_flat(base_state)
            signal = self._entry_signal(state, ctx, config)

        self._base._update_holding_bars(base_state, signal)
        self._base._update_current_levels(base_state, ctx)
        return signal

    def _entry_signal(
        self,
        state: State[PrevdayRandomBaselineParams],
        ctx: BarContext,
        config: PrevdayRandomBaselineParams,
    ) -> Signal:
        base_state = self._base_state(state)
        if not self._base._can_enter(base_state, ctx, config):
            self._base._track_breakout(base_state, ctx, config)
            return Signal()

        prev = self._base._prev_levels(base_state)
        if prev is None:
            return Signal()

        self._base._track_breakout(base_state, ctx, config)
        candidates = self._candidates(state, ctx, config, prev)
        if not candidates:
            return Signal()

        rng = self._rng(state, config)
        if rng.random() > config.random_entry_probability:
            return Signal()

        candidate = rng.choice(candidates)
        side = self._random_side(rng, candidate["side"], config)
        return self._build_random_entry_signal(state, ctx, config, rng, side, candidate["prev"])

    def _candidates(
        self,
        state: State[PrevdayRandomBaselineParams],
        ctx: BarContext,
        config: PrevdayRandomBaselineParams,
        prev: DayLevels,
    ) -> list[RandomCandidate]:
        long_breakout_low = self._base._optional_float(state.extra.get("prevday_long_breakout_low"))
        short_breakout_high = self._base._optional_float(state.extra.get("prevday_short_breakout_high"))
        candidates: list[RandomCandidate] = []

        if config.random_baseline_mode == "event_window":
            if long_breakout_low is not None:
                candidates.append({"side": "long", "prev": prev})
            if short_breakout_high is not None:
                candidates.append({"side": "short", "prev": prev})
            return candidates

        bar = ctx.bar
        if long_breakout_low is not None and bar.close > prev["low"]:
            candidates.append({"side": "long", "prev": prev})
        if short_breakout_high is not None and bar.close < prev["high"]:
            candidates.append({"side": "short", "prev": prev})
        return candidates

    def _build_random_entry_signal(
        self,
        state: State[PrevdayRandomBaselineParams],
        ctx: BarContext,
        config: PrevdayRandomBaselineParams,
        rng: random.Random,
        side: TradeSide,
        prev: DayLevels,
    ) -> Signal:
        base_state = self._base_state(state)
        for _ in range(10):
            breakout_extreme = self._random_breakout_extreme(rng, ctx.bar, side, config)
            signal = self._base._build_entry_signal(base_state, ctx, config, side, breakout_extreme, prev)
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
    def _rng(state: State[PrevdayRandomBaselineParams], config: PrevdayRandomBaselineParams) -> random.Random:
        rng = state.extra.get("prevday_random_rng")
        if isinstance(rng, random.Random):
            return rng
        rng = random.Random(config.random_seed)
        state.extra["prevday_random_rng"] = rng
        return rng

    @staticmethod
    def _random_side(
        rng: random.Random,
        original_side: TradeSide,
        config: PrevdayRandomBaselineParams,
    ) -> TradeSide:
        if config.random_direction_mode == "same":
            return original_side
        return "long" if rng.random() < 0.5 else "short"

    @staticmethod
    def _random_breakout_extreme(
        rng: random.Random,
        bar: Bar,
        side: TradeSide,
        config: PrevdayRandomBaselineParams,
    ) -> float:
        buffer = config.failure_buffer_ticks * config.price_tick
        extra_ticks = rng.randint(0, 10) * config.price_tick
        if side == "long":
            return min(bar.low, bar.close - buffer - extra_ticks)
        return max(bar.high, bar.close + buffer + extra_ticks)

    @staticmethod
    def _base_state(state: State[PrevdayRandomBaselineParams]) -> State[PrevdayReacceptanceParams]:
        return cast(State[PrevdayReacceptanceParams], state)

    @override
    def on_fill(self, fill: Fill) -> None:
        return None
