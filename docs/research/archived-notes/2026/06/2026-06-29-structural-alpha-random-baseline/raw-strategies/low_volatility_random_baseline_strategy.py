from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal, cast, override

from .core import CORE_VERSION, Bar, Fill, Signal, State, Strategy
from .low_volatility_restart_strategy import (
    CompressionInfo,
    ImpulseInfo,
    LowVolatilityRestartParams,
    LowVolatilityRestartStrategyCore,
    TradeSide,
)
from .runtime import BarContext, DataRequirements

RandomDirectionMode = Literal["same", "random"]


@dataclass
class LowVolatilityRandomBaselineParams(LowVolatilityRestartParams):
    random_seed: int = 42
    random_direction_mode: RandomDirectionMode = "same"
    random_entry_probability: float = 1.0


class LowVolatilityRandomBaselineStrategyCore(Strategy[LowVolatilityRandomBaselineParams]):
    name: str = "low_volatility_random_baseline"
    VERSION: str = f"{CORE_VERSION}-low-volatility-random-baseline-r1"
    config_type = LowVolatilityRandomBaselineParams

    def __init__(self) -> None:
        self._base = LowVolatilityRestartStrategyCore()

    @override
    def data_requirements(self, config: LowVolatilityRandomBaselineParams) -> DataRequirements | None:
        return self._base.data_requirements(config)

    @override
    def on_bar(self, state: State[LowVolatilityRandomBaselineParams], ctx: BarContext) -> Signal:
        config = state.strategy_config
        base_state = self._base_state(state)
        self._base._ensure_session(base_state, ctx)
        history = self._base._historical_bars(ctx, config)
        atr = self._base._average_true_range(history, config.atr_lookback)
        state.extra["low_vol_restart_atr"] = atr

        if state.position.direction:
            signal = self._base._exit_signal(base_state, ctx, config)
        else:
            self._base._clear_trade_if_flat(base_state)
            signal = self._entry_signal(state, ctx, config, history, atr)

        self._base._update_holding_bars(base_state, signal)
        return signal

    def _entry_signal(
        self,
        state: State[LowVolatilityRandomBaselineParams],
        ctx: BarContext,
        config: LowVolatilityRandomBaselineParams,
        history: list[Bar],
        atr: float,
    ) -> Signal:
        if not self._base._can_enter(self._base_state(state), ctx, config) or atr <= 0:
            return Signal()

        compression = self._base._compression_info(history, config, atr)
        if compression is None:
            return Signal()
        impulse = self._base._impulse_info(history, config, atr)
        if impulse is None:
            return Signal()

        side = self._base._breakout_side(ctx.bar, compression, config)
        if side is None or not self._base._direction_allowed(side, impulse["direction"], config.direction_mode):
            return Signal()

        rng = self._rng(state, config)
        if rng.random() > config.random_entry_probability:
            return Signal()

        random_side = self._random_side(rng, side, config)
        return self._build_random_entry_signal(state, ctx, config, rng, random_side, compression, impulse, atr)

    def _build_random_entry_signal(
        self,
        state: State[LowVolatilityRandomBaselineParams],
        ctx: BarContext,
        config: LowVolatilityRandomBaselineParams,
        rng: random.Random,
        side: TradeSide,
        compression: CompressionInfo,
        impulse: ImpulseInfo,
        atr: float,
    ) -> Signal:
        base_state = self._base_state(state)
        for _ in range(10):
            random_compression = self._random_compression(rng, ctx.bar, side, compression, config)
            signal = self._base._build_entry_signal(base_state, ctx, config, side, random_compression, impulse, atr)
            if signal.action:
                signal.reason = f"random_{signal.reason}"
                signal.diagnostics = {
                    **signal.diagnostics,
                    "random_direction_mode": config.random_direction_mode,
                }
                return signal
        return Signal()

    @staticmethod
    def _rng(
        state: State[LowVolatilityRandomBaselineParams], config: LowVolatilityRandomBaselineParams
    ) -> random.Random:
        rng = state.extra.get("low_vol_random_rng")
        if isinstance(rng, random.Random):
            return rng
        rng = random.Random(config.random_seed)
        state.extra["low_vol_random_rng"] = rng
        return rng

    @staticmethod
    def _random_side(
        rng: random.Random,
        original_side: TradeSide,
        config: LowVolatilityRandomBaselineParams,
    ) -> TradeSide:
        if config.random_direction_mode == "same":
            return original_side
        return "long" if rng.random() < 0.5 else "short"

    @staticmethod
    def _random_compression(
        rng: random.Random,
        bar: Bar,
        side: TradeSide,
        compression: CompressionInfo,
        config: LowVolatilityRandomBaselineParams,
    ) -> CompressionInfo:
        buffer = config.failure_buffer_ticks * config.price_tick
        extra_ticks = rng.randint(0, 10) * config.price_tick
        if side == "long":
            random_low = bar.close - buffer - extra_ticks
            random_high = max(compression["high"], bar.close)
        else:
            random_high = bar.close + buffer + extra_ticks
            random_low = min(compression["low"], bar.close)
        return CompressionInfo(
            high=random_high,
            low=random_low,
            width=max(0.0, random_high - random_low),
            average_range=compression["average_range"],
        )

    @staticmethod
    def _base_state(state: State[LowVolatilityRandomBaselineParams]) -> State[LowVolatilityRestartParams]:
        return cast(State[LowVolatilityRestartParams], state)

    @override
    def on_fill(self, fill: Fill) -> None:
        return None
