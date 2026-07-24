from __future__ import annotations

from datetime import datetime, timedelta
from typing import cast

from common.constants import TRADE_ACTION_BUY, TRADE_ACTION_SELL, TRADE_DIRECTION_LONG, TRADE_DIRECTION_SHORT
from strategies.core import Bar, Fill, State, StrategyPosition
from strategies.hourly_liquidity_sweep_strategy import (
    HourlyLiquiditySweepParams,
    HourlyLiquiditySweepStrategyCore,
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


def _ctx(bar: Bar, structure_bars: list[Bar] | None = None) -> BarContext:
    multi = {"1h": cast(PeriodDataView, FakeBarView(structure_bars))} if structure_bars is not None else {}
    return BarContext(symbol="DCE.m2601", bar=bar, multi=multi, events=[])


def _state(config: HourlyLiquiditySweepParams | None = None) -> State[HourlyLiquiditySweepParams]:
    cfg = config or HourlyLiquiditySweepParams()
    return State(
        symbol="DCE.m2601",
        period=cfg.kline_period,
        strategy_config=cfg,
        capital=100000,
        contract_size=10,
        margin=0.1,
    )


def _structure_bars(include_resistance: bool = True, include_support: bool = True) -> list[Bar]:
    start = datetime(2025, 9, 1, 9, 0)
    highs = [3020.0, 3000.0, 3022.0, 3005.0, 3018.0, 3010.0]
    lows = [3000.0, 3015.0, 3002.0, 3018.0, 2999.0, 3025.0]
    bars: list[Bar] = []
    for index, (high, low) in enumerate(zip(highs, lows, strict=True)):
        adjusted_high = high if include_resistance else 3010.0 + index * 10
        adjusted_low = low if include_support else 3000.0 - index * 10
        bars.append(
            _bar(
                start + timedelta(hours=index),
                open_price=(adjusted_high + adjusted_low) / 2,
                high=adjusted_high,
                low=adjusted_low,
                close=(adjusted_high + adjusted_low) / 2,
            )
        )
    return bars


def test_data_requirements_include_execution_and_structure_lookback() -> None:
    reqs = HourlyLiquiditySweepStrategyCore().data_requirements(
        HourlyLiquiditySweepParams(kline_period="5m", structure_period="1h", lookback_hours=48, min_touches=2)
    )

    assert reqs is not None
    assert set(reqs.periods) == {"5m", "1h"}
    assert reqs.periods["5m"].lookback_bars == 1
    assert reqs.periods["1h"].lookback_bars == 48
    assert reqs.indicators == {}
    assert not reqs.events.include_global_events


def test_band_clustering_identifies_support_and_resistance() -> None:
    strategy = HourlyLiquiditySweepStrategyCore()
    cfg = HourlyLiquiditySweepParams(touch_tolerance_ticks=4, min_touches=2)
    current = _bar(datetime(2025, 9, 2, 9, 0), 3005, 3006, 3004, 3005)

    support, resistance, _ = strategy._active_bands(_ctx(current, _structure_bars()), cfg)

    assert support is not None
    assert support["kind"] == "support"
    assert support["lower"] == 2999.0
    assert support["upper"] == 3002.0
    assert support["touches"] == 3
    assert resistance is not None
    assert resistance["kind"] == "resistance"
    assert resistance["lower"] == 3018.0
    assert resistance["upper"] == 3022.0
    assert resistance["touches"] == 3


def test_support_sweep_then_band_inner_reaccept_triggers_long() -> None:
    strategy = HourlyLiquiditySweepStrategyCore()
    cfg = HourlyLiquiditySweepParams(reaccept_mode="band_inner", take_profit_mode="r")
    state = _state(cfg)
    structure = _structure_bars()

    breakout = strategy.on_bar(state, _ctx(_bar(datetime(2025, 9, 2, 9, 30), 3001, 3004, 2996, 2998), structure))
    signal = strategy.on_bar(state, _ctx(_bar(datetime(2025, 9, 2, 9, 35), 2998, 3003, 2998, 2999), structure))

    assert breakout.action == ""
    assert signal.action == TRADE_ACTION_BUY
    assert signal.reason == "hourly_sweep_support_reaccept_long"
    assert signal.volume > 0
    assert signal.diagnostics["support_touches"] == 3.0
    assert signal.diagnostics["entry_price"] == 2999.0
    assert signal.diagnostics["strict_failure"] == 2995.0
    assert signal.diagnostics["target_price"] == 3003.0


def test_resistance_sweep_then_band_mid_reaccept_triggers_short() -> None:
    strategy = HourlyLiquiditySweepStrategyCore()
    cfg = HourlyLiquiditySweepParams(reaccept_mode="band_mid", take_profit_mode="r")
    state = _state(cfg)
    structure = _structure_bars()

    strategy.on_bar(state, _ctx(_bar(datetime(2025, 9, 2, 10, 0), 3020, 3025, 3018, 3023), structure))
    signal = strategy.on_bar(state, _ctx(_bar(datetime(2025, 9, 2, 10, 5), 3023, 3024, 3016, 3020), structure))

    assert signal.action == TRADE_ACTION_SELL
    assert signal.reason == "hourly_sweep_resistance_reject_short"
    assert signal.diagnostics["resistance_touches"] == 3.0
    assert signal.diagnostics["entry_price"] == 3020.0
    assert signal.diagnostics["strict_failure"] == 3026.0
    assert signal.diagnostics["target_price"] == 3014.0


def test_without_min_touches_does_not_enter() -> None:
    strategy = HourlyLiquiditySweepStrategyCore()
    cfg = HourlyLiquiditySweepParams(min_touches=4)
    state = _state(cfg)
    structure = _structure_bars()

    strategy.on_bar(state, _ctx(_bar(datetime(2025, 9, 2, 9, 30), 3001, 3004, 2996, 2998), structure))
    signal = strategy.on_bar(state, _ctx(_bar(datetime(2025, 9, 2, 9, 35), 2998, 3003, 2998, 3000), structure))

    assert signal.action == ""
    assert "hourly_sweep_trade" not in state.extra


def test_opposite_band_target_requires_valid_opposite_band() -> None:
    strategy = HourlyLiquiditySweepStrategyCore()
    cfg = HourlyLiquiditySweepParams(take_profit_mode="opposite_band")
    missing_opposite_state = _state(cfg)
    support_only = _structure_bars(include_resistance=False)

    strategy.on_bar(
        missing_opposite_state,
        _ctx(_bar(datetime(2025, 9, 2, 9, 30), 3001, 3004, 2996, 2998), support_only),
    )
    blocked = strategy.on_bar(
        missing_opposite_state,
        _ctx(_bar(datetime(2025, 9, 2, 9, 35), 2998, 3003, 2998, 2999), support_only),
    )

    valid_state = _state(cfg)
    both_bands = _structure_bars()
    strategy.on_bar(valid_state, _ctx(_bar(datetime(2025, 9, 2, 9, 30), 3001, 3004, 2996, 2998), both_bands))
    allowed = strategy.on_bar(valid_state, _ctx(_bar(datetime(2025, 9, 2, 9, 35), 2998, 3003, 2998, 2999), both_bands))

    assert blocked.action == ""
    assert allowed.action == TRADE_ACTION_BUY
    assert allowed.diagnostics["target_price"] == 3020.0


def test_long_and_short_exit_stop_and_take_profit() -> None:
    strategy = HourlyLiquiditySweepStrategyCore()
    long_state = _state()
    long_state.position = StrategyPosition(direction=TRADE_DIRECTION_LONG, entry_price=2999, volume=3)
    long_state.extra["hourly_sweep_session"] = datetime(2025, 9, 2).date()
    long_state.extra["hourly_sweep_trade"] = {
        "side": "long",
        "entry_price": 2999.0,
        "strict_failure": 2995.0,
        "stop_price": 2995.0,
        "target_price": 3003.0,
        "support_lower": 2999.0,
        "support_upper": 3002.0,
        "support_touches": 3,
        "resistance_lower": 3018.0,
        "resistance_upper": 3022.0,
        "resistance_touches": 3,
    }
    short_state = _state()
    short_state.position = StrategyPosition(direction=TRADE_DIRECTION_SHORT, entry_price=3020, volume=2)
    short_state.extra["hourly_sweep_session"] = datetime(2025, 9, 2).date()
    short_state.extra["hourly_sweep_trade"] = {
        "side": "short",
        "entry_price": 3020.0,
        "strict_failure": 3026.0,
        "stop_price": 3026.0,
        "target_price": 3014.0,
        "support_lower": 2999.0,
        "support_upper": 3002.0,
        "support_touches": 3,
        "resistance_lower": 3018.0,
        "resistance_upper": 3022.0,
        "resistance_touches": 3,
    }

    long_signal = strategy.on_bar(long_state, _ctx(_bar(datetime(2025, 9, 2, 11, 0), 2999, 3004, 2998, 3003)))
    short_signal = strategy.on_bar(short_state, _ctx(_bar(datetime(2025, 9, 2, 11, 0), 3020, 3027, 3018, 3026)))

    assert long_signal.action == TRADE_ACTION_SELL
    assert long_signal.volume == 3
    assert long_signal.reason == "take_profit"
    assert short_signal.action == TRADE_ACTION_BUY
    assert short_signal.volume == 2
    assert short_signal.reason == "stop_loss"


def test_volatility_filter_blocks_small_sweep_and_allows_large_sweep() -> None:
    strategy = HourlyLiquiditySweepStrategyCore()
    cfg = HourlyLiquiditySweepParams(
        reaccept_mode="band_inner",
        take_profit_mode="r",
        volatility_filter_enabled=True,
        atr_lookback=3,
        min_sweep_atr=0.3,
        max_strict_distance_atr=2.0,
        min_target_atr=0.5,
    )
    structure = _structure_bars()

    blocked_state = _state(cfg)
    strategy.on_bar(blocked_state, _ctx(_bar(datetime(2025, 9, 2, 9, 30), 3001, 3004, 2996, 2998), structure))
    blocked = strategy.on_bar(blocked_state, _ctx(_bar(datetime(2025, 9, 2, 9, 35), 2998, 3003, 2998, 2999), structure))

    allowed_state = _state(cfg)
    strategy.on_bar(allowed_state, _ctx(_bar(datetime(2025, 9, 2, 9, 30), 3001, 3004, 2992, 2998), structure))
    allowed = strategy.on_bar(allowed_state, _ctx(_bar(datetime(2025, 9, 2, 9, 35), 2998, 3003, 2998, 2999), structure))

    assert blocked.action == ""
    assert allowed.action == TRADE_ACTION_BUY
    assert allowed.diagnostics["hourly_atr"] > 0
    assert allowed.diagnostics["sweep_depth_atr"] >= 0.3
    assert allowed.diagnostics["volatility_filter_enabled"] == "True"


def test_helpers_and_on_fill_noop() -> None:
    strategy = HourlyLiquiditySweepStrategyCore()
    state = _state(HourlyLiquiditySweepParams(max_position_ratio=0.0))

    assert strategy._period_minutes("5m") == 5
    assert strategy._period_minutes("1h") == 60
    assert strategy._structure_lookback_bars(25, "2h") == 13
    assert strategy._target_is_valid("long", 3000, 3001)
    assert not strategy._target_is_valid("short", 3000, 3001)
    assert strategy._calc_volume(state, 3000, 0, state.strategy_config) == 0
    assert strategy._calc_volume(state, 3000, 5, state.strategy_config) == 0
    strategy.on_fill(Fill())
