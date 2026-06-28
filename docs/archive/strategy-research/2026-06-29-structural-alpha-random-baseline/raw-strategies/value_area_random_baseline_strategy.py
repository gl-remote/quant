from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal, TypedDict, cast, override

from .core import CORE_VERSION, Bar, Fill, Signal, State, Strategy
from .runtime import BarContext, DataRequirements
from .value_area_reacceptance_strategy import (
    TradeInfo,
    ValueAreaLevels,
    ValueAreaReacceptanceParams,
    ValueAreaReacceptanceStrategyCore,
)

RandomBaselineMode = Literal["event_window", "direction_matched"]
RandomDirectionMode = Literal["same", "random"]


class RandomCandidate(TypedDict):
    side: Literal["long", "short"]
    breakout_extreme: float
    prev: ValueAreaLevels


@dataclass
class ValueAreaRandomBaselineParams(ValueAreaReacceptanceParams):
    random_seed: int = 42
    random_baseline_mode: RandomBaselineMode = "event_window"
    random_direction_mode: RandomDirectionMode = "same"
    random_entry_probability: float = 1.0


class ValueAreaRandomBaselineStrategyCore(Strategy[ValueAreaRandomBaselineParams]):
    name: str = "value_area_random_baseline"
    VERSION: str = f"{CORE_VERSION}-value-area-random-baseline-r1"
    config_type = ValueAreaRandomBaselineParams

    def __init__(self) -> None:
        self._base = ValueAreaReacceptanceStrategyCore()

    @override
    def data_requirements(self, config: ValueAreaRandomBaselineParams) -> DataRequirements | None:
        return self._base.data_requirements(config)

    @override
    def on_bar(self, state: State[ValueAreaRandomBaselineParams], ctx: BarContext) -> Signal:
        config = state.strategy_config
        base_state = self._base_state(state)
        self._base._ensure_session(base_state, ctx, config)  # pyright: ignore[reportPrivateUsage]

        if state.position.direction:
            signal = self._base._exit_signal(base_state, ctx, config)  # pyright: ignore[reportPrivateUsage]
        else:
            self._base._clear_trade_if_flat(base_state)  # pyright: ignore[reportPrivateUsage]
            signal = self._entry_signal(state, ctx, config)

        self._base._update_holding_bars(base_state, signal)  # pyright: ignore[reportPrivateUsage]
        self._base._update_current_session(base_state, ctx, config)  # pyright: ignore[reportPrivateUsage]
        return signal

    def _entry_signal(
        self,
        state: State[ValueAreaRandomBaselineParams],
        ctx: BarContext,
        config: ValueAreaRandomBaselineParams,
    ) -> Signal:
        base_state = self._base_state(state)
        if not self._base._can_enter(base_state, ctx, config):  # pyright: ignore[reportPrivateUsage]
            self._base._track_breakout(base_state, ctx, config)  # pyright: ignore[reportPrivateUsage]
            return Signal()

        prev = self._base._prev_levels(base_state)  # pyright: ignore[reportPrivateUsage]
        if prev is None:
            return Signal()

        self._base._track_breakout(base_state, ctx, config)  # pyright: ignore[reportPrivateUsage]
        candidates = self._candidates(state, ctx, config, prev)
        if not candidates:
            return Signal()

        rng = self._rng(state, config)
        if rng.random() > config.random_entry_probability:
            return Signal()

        candidate = rng.choice(candidates)
        side = self._random_side(rng, candidate["side"], config)
        trade_side = self._trade_side_for_target(side, candidate["prev"])
        return self._build_random_entry_signal(state, ctx, config, rng, trade_side, candidate["prev"])

    def _candidates(
        self,
        state: State[ValueAreaRandomBaselineParams],
        ctx: BarContext,
        config: ValueAreaRandomBaselineParams,
        prev: ValueAreaLevels,
    ) -> list[RandomCandidate]:
        candidates: list[RandomCandidate] = []
        base_state = self._base_state(state)
        long_breakout_low = self._base._optional_float(  # pyright: ignore[reportPrivateUsage]
            state.extra.get("value_area_long_breakout_low")
        )
        short_breakout_high = self._base._optional_float(  # pyright: ignore[reportPrivateUsage]
            state.extra.get("value_area_short_breakout_high")
        )

        if config.random_baseline_mode == "event_window":
            if long_breakout_low is not None:
                candidates.append({"side": "long", "breakout_extreme": long_breakout_low, "prev": prev})
            if short_breakout_high is not None:
                candidates.append({"side": "short", "breakout_extreme": short_breakout_high, "prev": prev})
            return candidates

        bar = ctx.bar
        if long_breakout_low is not None and bar.close > prev["val"]:
            breakout_bars = self._base._int_extra(  # pyright: ignore[reportPrivateUsage]
                base_state, "value_area_long_breakout_bars"
            )
            if self._base._reacceptance_quality_ok(  # pyright: ignore[reportPrivateUsage]
                "long", bar.close, prev, breakout_bars, config
            ):
                candidates.append({"side": "long", "breakout_extreme": long_breakout_low, "prev": prev})
        if short_breakout_high is not None and bar.close < prev["vah"]:
            breakout_bars = self._base._int_extra(  # pyright: ignore[reportPrivateUsage]
                base_state, "value_area_short_breakout_bars"
            )
            if self._base._reacceptance_quality_ok(  # pyright: ignore[reportPrivateUsage]
                "short", bar.close, prev, breakout_bars, config
            ):
                candidates.append({"side": "short", "breakout_extreme": short_breakout_high, "prev": prev})
        return candidates

    def _build_random_entry_signal(
        self,
        state: State[ValueAreaRandomBaselineParams],
        ctx: BarContext,
        config: ValueAreaRandomBaselineParams,
        rng: random.Random,
        side: Literal["long", "short"],
        prev: ValueAreaLevels,
    ) -> Signal:
        attempts = 10
        for _ in range(attempts):
            breakout_extreme = self._random_breakout_extreme(rng, ctx.bar, side, config)
            base_state = self._base_state(state)
            signal = self._base._build_entry_signal(  # pyright: ignore[reportPrivateUsage]
                base_state, ctx, config, side, breakout_extreme, prev
            )
            if signal.action:
                break
        else:
            return Signal()

        trade = self._trade_info(state)
        if trade is not None:
            trade["context_label"] = f"random_{config.random_baseline_mode}_{config.random_direction_mode}"
            state.extra["value_area_trade"] = trade

        signal.reason = f"random_{signal.reason}"
        signal.diagnostics = {**signal.diagnostics, "random_baseline": config.random_baseline_mode}
        return signal

    @staticmethod
    def _rng(state: State[ValueAreaRandomBaselineParams], config: ValueAreaRandomBaselineParams) -> random.Random:
        rng = state.extra.get("value_area_random_rng")
        if isinstance(rng, random.Random):
            return rng
        rng = random.Random(config.random_seed)
        state.extra["value_area_random_rng"] = rng
        return rng

    @staticmethod
    def _random_side(
        rng: random.Random,
        original_side: Literal["long", "short"],
        config: ValueAreaRandomBaselineParams,
    ) -> Literal["long", "short"]:
        if config.random_direction_mode == "same":
            return original_side
        return "long" if rng.random() < 0.5 else "short"

    @staticmethod
    def _trade_side_for_target(
        side: Literal["long", "short"],
        prev: ValueAreaLevels,
    ) -> Literal["long", "short"]:
        if side == "long":
            return "long" if prev["poc"] > prev["val"] else "short"
        return "short" if prev["poc"] < prev["vah"] else "long"

    @staticmethod
    def _random_breakout_extreme(
        rng: random.Random,
        bar: Bar,
        side: Literal["long", "short"],
        config: ValueAreaRandomBaselineParams,
    ) -> float:
        buffer = config.failure_buffer_ticks * config.price_tick
        extra_ticks = rng.randint(0, 10) * config.price_tick
        if side == "long":
            return min(bar.low, bar.close - buffer - extra_ticks)
        return max(bar.high, bar.close + buffer + extra_ticks)

    @staticmethod
    def _base_state(state: State[ValueAreaRandomBaselineParams]) -> State[ValueAreaReacceptanceParams]:
        return cast(State[ValueAreaReacceptanceParams], state)

    @staticmethod
    def _trade_info(state: State[ValueAreaRandomBaselineParams]) -> TradeInfo | None:
        value = state.extra.get("value_area_trade")
        return cast(TradeInfo, value) if isinstance(value, dict) else None

    @override
    def on_fill(self, fill: Fill) -> None:
        return None
