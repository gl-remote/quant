from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal, TypedDict, cast, override

from .core import CORE_VERSION, Bar, Fill, Signal, State, Strategy
from .prevday_volume_filter_strategy import (
    DayLevels,
    PrevdayVolumeFilterParams,
    PrevdayVolumeFilterStrategyCore,
    ShockMetrics,
    TradeSide,
)
from .runtime import BarContext, DataRequirements

RandomBaselineMode = Literal["event_window", "direction_matched"]
RandomDirectionMode = Literal["same", "random"]


class RandomCandidate(TypedDict):
    side: TradeSide
    prev: DayLevels
    breakout_shock: bool
    reaccept_shock: bool
    metrics: ShockMetrics


@dataclass
class PrevdayVolumeRandomBaselineParams(PrevdayVolumeFilterParams):
    random_seed: int = 42
    random_baseline_mode: RandomBaselineMode = "event_window"
    random_direction_mode: RandomDirectionMode = "same"
    random_entry_probability: float = 1.0


class PrevdayVolumeRandomBaselineStrategyCore(Strategy[PrevdayVolumeRandomBaselineParams]):
    name: str = "prevday_volume_random_baseline"
    VERSION: str = f"{CORE_VERSION}-prevday-volume-random-baseline-r1"
    config_type = PrevdayVolumeRandomBaselineParams

    def __init__(self) -> None:
        self._base = PrevdayVolumeFilterStrategyCore()

    @override
    def data_requirements(self, config: PrevdayVolumeRandomBaselineParams) -> DataRequirements | None:
        return self._base.data_requirements(config)

    @override
    def on_bar(self, state: State[PrevdayVolumeRandomBaselineParams], ctx: BarContext) -> Signal:
        config = state.strategy_config
        base_state = self._base_state(state)
        self._base._ensure_session(base_state, ctx)

        metrics = self._base._shock_metrics(base_state, ctx, config)
        state.extra["prevday_volume_last_metrics"] = metrics
        if state.position.direction:
            signal = self._base._exit_signal(base_state, ctx, config)
        else:
            self._base._clear_trade_if_flat(base_state)
            signal = self._entry_signal(state, ctx, config, metrics)

        self._base._update_holding_bars(base_state, signal)
        self._base._update_current_levels(base_state, ctx)
        self._base._update_bar_history(base_state, ctx, config)
        return signal

    def _entry_signal(
        self,
        state: State[PrevdayVolumeRandomBaselineParams],
        ctx: BarContext,
        config: PrevdayVolumeRandomBaselineParams,
        metrics: ShockMetrics,
    ) -> Signal:
        base_state = self._base_state(state)
        if not self._base._can_enter(base_state, ctx, config):
            self._base._track_breakout(base_state, ctx, config, metrics)
            return Signal()

        prev = self._base._prev_levels(base_state)
        if prev is None:
            return Signal()

        self._base._track_breakout(base_state, ctx, config, metrics)
        candidates = self._candidates(state, ctx, config, prev, metrics)
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
            candidate["prev"],
            candidate["breakout_shock"],
            candidate["reaccept_shock"],
            candidate["metrics"],
        )

    def _candidates(
        self,
        state: State[PrevdayVolumeRandomBaselineParams],
        ctx: BarContext,
        config: PrevdayVolumeRandomBaselineParams,
        prev: DayLevels,
        metrics: ShockMetrics,
    ) -> list[RandomCandidate]:
        long_breakout_low = self._base._optional_float(state.extra.get("prevday_volume_long_breakout_low"))
        short_breakout_high = self._base._optional_float(state.extra.get("prevday_volume_short_breakout_high"))
        breakout_shock = bool(state.extra.get("prevday_volume_breakout_shock", False))
        reaccept_shock = metrics["is_shock"]
        candidates: list[RandomCandidate] = []

        if config.random_baseline_mode == "event_window":
            if long_breakout_low is not None:
                candidates.append(
                    {
                        "side": "long",
                        "prev": prev,
                        "breakout_shock": breakout_shock,
                        "reaccept_shock": reaccept_shock,
                        "metrics": metrics,
                    }
                )
            if short_breakout_high is not None:
                candidates.append(
                    {
                        "side": "short",
                        "prev": prev,
                        "breakout_shock": breakout_shock,
                        "reaccept_shock": reaccept_shock,
                        "metrics": metrics,
                    }
                )
            return candidates

        bar = ctx.bar
        if long_breakout_low is not None and bar.close > prev["low"]:
            candidates.append(
                {
                    "side": "long",
                    "prev": prev,
                    "breakout_shock": breakout_shock,
                    "reaccept_shock": reaccept_shock,
                    "metrics": metrics,
                }
            )
        if short_breakout_high is not None and bar.close < prev["high"]:
            candidates.append(
                {
                    "side": "short",
                    "prev": prev,
                    "breakout_shock": breakout_shock,
                    "reaccept_shock": reaccept_shock,
                    "metrics": metrics,
                }
            )
        return candidates

    def _build_random_entry_signal(
        self,
        state: State[PrevdayVolumeRandomBaselineParams],
        ctx: BarContext,
        config: PrevdayVolumeRandomBaselineParams,
        rng: random.Random,
        side: TradeSide,
        prev: DayLevels,
        breakout_shock: bool,
        reaccept_shock: bool,
        metrics: ShockMetrics,
    ) -> Signal:
        base_state = self._base_state(state)
        for _ in range(10):
            breakout_extreme = self._random_breakout_extreme(rng, ctx.bar, side, config)
            signal = self._base._build_entry_signal(
                base_state,
                ctx,
                config,
                side,
                breakout_extreme,
                prev,
                breakout_shock,
                reaccept_shock,
                metrics,
            )
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
        state: State[PrevdayVolumeRandomBaselineParams], config: PrevdayVolumeRandomBaselineParams
    ) -> random.Random:
        rng = state.extra.get("prevday_volume_random_rng")
        if isinstance(rng, random.Random):
            return rng
        rng = random.Random(config.random_seed)
        state.extra["prevday_volume_random_rng"] = rng
        return rng

    @staticmethod
    def _random_side(
        rng: random.Random,
        original_side: TradeSide,
        config: PrevdayVolumeRandomBaselineParams,
    ) -> TradeSide:
        if config.random_direction_mode == "same":
            return original_side
        return "long" if rng.random() < 0.5 else "short"

    @staticmethod
    def _random_breakout_extreme(
        rng: random.Random,
        bar: Bar,
        side: TradeSide,
        config: PrevdayVolumeRandomBaselineParams,
    ) -> float:
        buffer = config.failure_buffer_ticks * config.price_tick
        extra_ticks = rng.randint(0, 10) * config.price_tick
        if side == "long":
            return min(bar.low, bar.close - buffer - extra_ticks)
        return max(bar.high, bar.close + buffer + extra_ticks)

    @staticmethod
    def _base_state(state: State[PrevdayVolumeRandomBaselineParams]) -> State[PrevdayVolumeFilterParams]:
        return cast(State[PrevdayVolumeFilterParams], state)

    @override
    def on_fill(self, fill: Fill) -> None:
        return None
