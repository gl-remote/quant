from __future__ import annotations

from datetime import datetime, timedelta
from typing import cast

from common.constants import TRADE_ACTION_BUY, TRADE_ACTION_SELL, TRADE_DIRECTION_LONG, TRADE_DIRECTION_SHORT
from strategies.core import Bar, Fill, State, StrategyPosition
from strategies.low_volatility_restart_strategy import (
    LowVolatilityRestartParams,
    LowVolatilityRestartStrategyCore,
)
from strategies.runtime import BarContext
from strategies.runtime.period import PeriodDataView


class FakeBarView:
    def __init__(self, bars: list[Bar]) -> None:
        self._bars = bars

    @property
    def length(self) -> int:
        return len(self._bars)

    def get_bar(self, idx: int = -1) -> Bar | None:
        try:
            return self._bars[idx]
        except IndexError:
            return None

    def bar(self, idx: int = -1) -> Bar | None:
        return self.get_bar(idx)


def _bar(
    dt: datetime,
    open_price: float,
    high: float,
    low: float,
    close: float,
    volume: float = 1000,
) -> Bar:
    return Bar(
        symbol="DCE.m2601",
        datetime=dt,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def _ctx(bar: Bar, history: list[Bar] | None = None) -> BarContext:
    multi = {"5m": cast(PeriodDataView, FakeBarView(history))} if history is not None else {}
    return BarContext(symbol="DCE.m2601", bar=bar, multi=multi, events=[])


def _state(config: LowVolatilityRestartParams | None = None) -> State[LowVolatilityRestartParams]:
    cfg = config or LowVolatilityRestartParams()
    return State(
        symbol="DCE.m2601",
        period=cfg.kline_period,
        strategy_config=cfg,
        capital=100000,
        contract_size=10,
        margin=0.1,
    )


def _history(impulse_up: bool = True, compression_high: float = 3012, compression_low: float = 3008) -> list[Bar]:
    start = datetime(2025, 9, 1, 9, 0)
    bars: list[Bar] = []
    price = 3000.0
    for index in range(12):
        bars.append(_bar(start + timedelta(minutes=5 * index), price, price + 4, price - 4, price + 1))
        price += 1

    impulse_time = start + timedelta(minutes=60)
    if impulse_up:
        bars.append(_bar(impulse_time, 3010, 3028, 3008, 3026))
    else:
        bars.append(_bar(impulse_time, 3026, 3028, 3008, 3010))

    compression_start = impulse_time + timedelta(minutes=5)
    closes = [3010, 3011, 3009, 3010.5, 3009.5, 3011]
    for index, close in enumerate(closes):
        bars.append(
            _bar(
                compression_start + timedelta(minutes=5 * index),
                close,
                compression_high,
                compression_low,
                close,
            )
        )
    return bars


def test_data_requirements_use_execution_lookback() -> None:
    reqs = LowVolatilityRestartStrategyCore().data_requirements(
        LowVolatilityRestartParams(kline_period="5m", atr_lookback=14, impulse_lookback=12, compression_bars=6)
    )

    assert reqs is not None
    assert set(reqs.periods) == {"5m"}
    assert reqs.periods["5m"].lookback_bars == 19
    assert reqs.indicators == {}
    assert not reqs.events.include_global_events


def test_compression_and_impulse_detection() -> None:
    strategy = LowVolatilityRestartStrategyCore()
    cfg = LowVolatilityRestartParams(
        compression_bars=6,
        impulse_lookback=12,
        min_impulse_atr=1.2,
        max_compression_width_atr=0.8,
        max_compression_bar_range_atr=0.5,
    )
    history = _history()
    atr = strategy._average_true_range(history, cfg.atr_lookback)

    compression = strategy._compression_info(history, cfg, atr)
    impulse = strategy._impulse_info(history, cfg, atr)

    assert compression is not None
    assert compression["high"] == 3012.0
    assert compression["low"] == 3008.0
    assert compression["width"] / atr <= 0.8
    assert impulse is not None
    assert impulse["direction"] == "up"
    assert impulse["true_range"] / atr >= 1.2


def test_upside_breakout_triggers_long() -> None:
    strategy = LowVolatilityRestartStrategyCore()
    cfg = LowVolatilityRestartParams(
        min_impulse_atr=1.2,
        max_compression_width_atr=0.8,
        max_compression_bar_range_atr=0.5,
        direction_mode="breakout",
        take_profit_r=1.5,
    )
    state = _state(cfg)
    breakout_bar = _bar(datetime(2025, 9, 1, 10, 35), 3012, 3015, 3011, 3014)

    signal = strategy.on_bar(state, _ctx(breakout_bar, _history()))

    assert signal.action == TRADE_ACTION_BUY
    assert signal.reason == "low_vol_restart_long"
    assert signal.volume > 0
    assert signal.diagnostics["compression_high"] == 3012.0
    assert signal.diagnostics["strict_failure"] == 3007.0
    assert signal.diagnostics["target_price"] == 3024.5
    assert signal.diagnostics["direction_mode"] == "breakout"


def test_downside_breakout_triggers_short() -> None:
    strategy = LowVolatilityRestartStrategyCore()
    cfg = LowVolatilityRestartParams(
        min_impulse_atr=1.2,
        max_compression_width_atr=0.8,
        max_compression_bar_range_atr=0.7,
        direction_mode="breakout",
    )
    state = _state(cfg)
    breakout_bar = _bar(datetime(2025, 9, 1, 10, 35), 3008, 3009, 3004, 3006)

    signal = strategy.on_bar(state, _ctx(breakout_bar, _history(impulse_up=False)))

    assert signal.action == TRADE_ACTION_SELL
    assert signal.reason == "low_vol_restart_short"
    assert signal.diagnostics["strict_failure"] == 3013.0
    assert signal.diagnostics["target_price"] == 2999.0
    assert signal.diagnostics["impulse_direction"] == "down"


def test_direction_modes_filter_continuation_and_reversal() -> None:
    strategy = LowVolatilityRestartStrategyCore()
    continuation_state = _state(
        LowVolatilityRestartParams(
            min_impulse_atr=1.2,
            max_compression_width_atr=0.8,
            max_compression_bar_range_atr=0.5,
            direction_mode="impulse_continuation",
        )
    )
    reversal_state = _state(
        LowVolatilityRestartParams(
            min_impulse_atr=1.2,
            max_compression_width_atr=0.8,
            max_compression_bar_range_atr=0.5,
            direction_mode="impulse_reversal",
        )
    )
    breakout_bar = _bar(datetime(2025, 9, 1, 10, 35), 3012, 3015, 3011, 3014)

    continuation = strategy.on_bar(continuation_state, _ctx(breakout_bar, _history(impulse_up=True)))
    blocked_reversal = strategy.on_bar(reversal_state, _ctx(breakout_bar, _history(impulse_up=True)))

    assert continuation.action == TRADE_ACTION_BUY
    assert blocked_reversal.action == ""


def test_no_entry_without_low_volatility_compression() -> None:
    strategy = LowVolatilityRestartStrategyCore()
    cfg = LowVolatilityRestartParams(
        min_impulse_atr=1.2,
        max_compression_width_atr=0.4,
        max_compression_bar_range_atr=0.2,
    )
    state = _state(cfg)
    breakout_bar = _bar(datetime(2025, 9, 1, 10, 35), 3012, 3015, 3011, 3014)

    signal = strategy.on_bar(state, _ctx(breakout_bar, _history()))

    assert signal.action == ""
    assert "low_vol_restart_trade" not in state.extra


def test_long_and_short_exit_stop_and_take_profit() -> None:
    strategy = LowVolatilityRestartStrategyCore()
    long_state = _state()
    long_state.position = StrategyPosition(direction=TRADE_DIRECTION_LONG, entry_price=3014, volume=3)
    long_state.extra["low_vol_restart_session"] = datetime(2025, 9, 1).date()
    long_state.extra["low_vol_restart_trade"] = {
        "side": "long",
        "entry_price": 3014.0,
        "strict_failure": 3007.0,
        "stop_price": 3007.0,
        "target_price": 3021.0,
        "compression_high": 3012.0,
        "compression_low": 3008.0,
        "impulse_direction": "up",
    }
    short_state = _state()
    short_state.position = StrategyPosition(direction=TRADE_DIRECTION_SHORT, entry_price=3006, volume=2)
    short_state.extra["low_vol_restart_session"] = datetime(2025, 9, 1).date()
    short_state.extra["low_vol_restart_trade"] = {
        "side": "short",
        "entry_price": 3006.0,
        "strict_failure": 3013.0,
        "stop_price": 3013.0,
        "target_price": 2999.0,
        "compression_high": 3012.0,
        "compression_low": 3008.0,
        "impulse_direction": "down",
    }

    long_signal = strategy.on_bar(long_state, _ctx(_bar(datetime(2025, 9, 1, 11, 0), 3014, 3022, 3013, 3021)))
    short_signal = strategy.on_bar(short_state, _ctx(_bar(datetime(2025, 9, 1, 11, 0), 3006, 3014, 3005, 3013)))

    assert long_signal.action == TRADE_ACTION_SELL
    assert long_signal.volume == 3
    assert long_signal.reason == "take_profit"
    assert short_signal.action == TRADE_ACTION_BUY
    assert short_signal.volume == 2
    assert short_signal.reason == "stop_loss"


def test_helpers_and_on_fill_noop() -> None:
    strategy = LowVolatilityRestartStrategyCore()
    state = _state(LowVolatilityRestartParams(max_position_ratio=0.0))

    assert strategy._direction_allowed("long", "up", "breakout")
    assert strategy._direction_allowed("long", "up", "impulse_continuation")
    assert not strategy._direction_allowed("short", "up", "impulse_continuation")
    assert strategy._direction_allowed("short", "up", "impulse_reversal")
    assert strategy._target_is_valid("long", 3000, 3001)
    assert not strategy._target_is_valid("short", 3000, 3001)
    assert strategy._calc_volume(state, 3000, 0, state.strategy_config) == 0
    assert strategy._calc_volume(state, 3000, 5, state.strategy_config) == 0
    strategy.on_fill(Fill())
