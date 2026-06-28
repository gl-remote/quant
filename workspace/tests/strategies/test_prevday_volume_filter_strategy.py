from __future__ import annotations

from datetime import datetime

from common.constants import TRADE_ACTION_BUY, TRADE_ACTION_SELL, TRADE_DIRECTION_LONG, TRADE_DIRECTION_SHORT
from strategies.core import Bar, Fill, State, StrategyPosition
from strategies.prevday_volume_filter_strategy import (
    DayLevels,
    PrevdayVolumeFilterParams,
    PrevdayVolumeFilterStrategyCore,
)
from strategies.runtime import BarContext


def _ctx(
    dt: datetime,
    open_price: float,
    high: float,
    low: float,
    close: float,
    volume: float = 1000,
) -> BarContext:
    return BarContext(
        symbol="DCE.m2601",
        bar=Bar(
            symbol="DCE.m2601",
            datetime=dt,
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=volume,
        ),
        multi={},
        events=[],
    )


def _state(config: PrevdayVolumeFilterParams | None = None) -> State[PrevdayVolumeFilterParams]:
    return State(
        symbol="DCE.m2601",
        period="1m",
        strategy_config=config or PrevdayVolumeFilterParams(),
        capital=100000,
        contract_size=10,
        margin=0.1,
    )


def _set_prev_levels(state: State[PrevdayVolumeFilterParams]) -> None:
    state.extra["prevday_volume_levels"] = {
        "date": datetime(2025, 9, 1).date(),
        "high": 3020.0,
        "low": 3000.0,
        "close": 3010.0,
        "open": 3008.0,
    }
    state.extra["prevday_volume_current_levels"] = {
        "date": datetime(2025, 9, 2).date(),
        "high": 3005.0,
        "low": 3005.0,
        "close": 3005.0,
        "open": 3005.0,
    }


def _warmup(
    strategy: PrevdayVolumeFilterStrategyCore,
    state: State[PrevdayVolumeFilterParams],
    bars: int = 20,
) -> None:
    for minute in range(bars):
        strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, minute), 3005, 3007, 3003, 3006, 1000))


def test_data_requirements_uses_max_lookback() -> None:
    reqs = PrevdayVolumeFilterStrategyCore().data_requirements(
        PrevdayVolumeFilterParams(kline_period="5m", volume_lookback=30, range_lookback=10)
    )
    baseline_reqs = PrevdayVolumeFilterStrategyCore().data_requirements(
        PrevdayVolumeFilterParams(kline_period="5m", volume_filter_enabled=False, volume_lookback=30, range_lookback=10)
    )

    assert reqs is not None
    assert baseline_reqs is not None
    assert set(reqs.periods) == {"5m"}
    assert reqs.periods["5m"].lookback_bars == 30
    assert baseline_reqs.periods["5m"].lookback_bars == 1
    assert reqs.indicators == {}


def test_filter_off_allows_baseline_entry() -> None:
    strategy = PrevdayVolumeFilterStrategyCore()
    state = _state(PrevdayVolumeFilterParams(volume_filter_enabled=False, take_profit_mode="mid"))
    _set_prev_levels(state)

    breakout = strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 30), 3005, 3006, 2997, 2998, 1000))
    signal = strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 31), 2998, 3006, 2998, 3001, 1000))

    assert breakout.action == ""
    assert signal.action == TRADE_ACTION_BUY
    assert signal.reason == "prevday_volume_low_reaccept_long"
    assert signal.volume > 0
    assert signal.diagnostics["volume_filter_enabled"] is False
    trade = state.extra["prevday_volume_trade"]
    assert trade["strict_failure"] == 2996
    assert trade["stop_price"] == 2996
    assert trade["target_price"] == 3010


def test_filter_enabled_breakout_shock_allows_entry() -> None:
    strategy = PrevdayVolumeFilterStrategyCore()
    state = _state(
        PrevdayVolumeFilterParams(
            volume_filter_enabled=True,
            volume_filter_stage="breakout",
            volume_multiplier=2.0,
            range_multiplier=1.2,
            min_body_ratio=0.4,
            take_profit_mode="mid",
        )
    )
    _set_prev_levels(state)
    _warmup(strategy, state)

    breakout = strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 30), 3005, 3006, 2997, 2998, 3000))
    signal = strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 31), 2998, 3006, 2998, 3001, 1000))

    assert breakout.action == ""
    assert signal.action == TRADE_ACTION_BUY
    assert signal.diagnostics["breakout_shock"] is True
    assert signal.diagnostics["reaccept_shock"] is False
    assert signal.diagnostics["volume_ratio"] == 10 / 11
    assert signal.diagnostics["range_ratio"] == 32 / 17


def test_filter_enabled_without_shock_blocks_entry() -> None:
    strategy = PrevdayVolumeFilterStrategyCore()
    state = _state(
        PrevdayVolumeFilterParams(
            volume_filter_enabled=True,
            volume_filter_stage="breakout",
            volume_multiplier=2.0,
            range_multiplier=1.2,
            min_body_ratio=0.4,
        )
    )
    _set_prev_levels(state)
    _warmup(strategy, state)

    strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 30), 3005, 3006, 2997, 2998, 1000))
    signal = strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 31), 2998, 3006, 2998, 3001, 1000))

    assert signal.action == ""
    assert "prevday_volume_trade" not in state.extra


def test_reaccept_stage_requires_current_reaccept_bar_shock() -> None:
    strategy = PrevdayVolumeFilterStrategyCore()
    cfg = PrevdayVolumeFilterParams(
        volume_filter_enabled=True,
        volume_filter_stage="reaccept",
        volume_multiplier=2.0,
        range_multiplier=1.1,
        min_body_ratio=0.2,
        take_profit_mode="mid",
    )
    state = _state(cfg)
    _set_prev_levels(state)
    _warmup(strategy, state)

    strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 30), 3005, 3006, 2997, 2998, 3000))
    blocked = strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 31), 2998, 3006, 2998, 3001, 1000))
    allowed = strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 32), 2998, 3010, 2998, 3001, 3000))

    assert blocked.action == ""
    assert allowed.action == TRADE_ACTION_BUY
    assert allowed.diagnostics["breakout_shock"] is True
    assert allowed.diagnostics["reaccept_shock"] is True
    assert allowed.diagnostics["volume_filter_stage"] == "reaccept"


def test_exit_long_and_short_follow_stop_and_target_logic() -> None:
    strategy = PrevdayVolumeFilterStrategyCore()
    long_state = _state()
    long_state.position = StrategyPosition(direction=TRADE_DIRECTION_LONG, entry_price=3001, volume=3)
    long_state.extra["prevday_volume_current_levels"] = {
        "date": datetime(2025, 9, 2).date(),
        "high": 3005.0,
        "low": 3005.0,
        "close": 3005.0,
        "open": 3005.0,
    }
    long_state.extra["prevday_volume_trade"] = {
        "side": "long",
        "entry_price": 3001.0,
        "strict_failure": 2996.0,
        "stop_price": 2996.0,
        "target_price": 3010.0,
        "prev_high": 3020.0,
        "prev_low": 3000.0,
        "prev_close": 3010.0,
        "breakout_shock": True,
        "reaccept_shock": False,
        "volume_ratio": 1.0,
        "range_ratio": 1.0,
        "body_ratio": 0.5,
    }
    short_state = _state()
    short_state.position = StrategyPosition(direction=TRADE_DIRECTION_SHORT, entry_price=3019, volume=2)
    short_state.extra["prevday_volume_current_levels"] = {
        "date": datetime(2025, 9, 2).date(),
        "high": 3020.0,
        "low": 3018.0,
        "close": 3020.0,
        "open": 3020.0,
    }
    short_state.extra["prevday_volume_trade"] = {
        "side": "short",
        "entry_price": 3019.0,
        "strict_failure": 3024.0,
        "stop_price": 3024.0,
        "target_price": 3010.0,
        "prev_high": 3020.0,
        "prev_low": 3000.0,
        "prev_close": 3010.0,
        "breakout_shock": True,
        "reaccept_shock": False,
        "volume_ratio": 1.0,
        "range_ratio": 1.0,
        "body_ratio": 0.5,
    }

    long_signal = strategy.on_bar(long_state, _ctx(datetime(2025, 9, 2, 10, 0), 3005, 3011, 3005, 3010))
    short_signal = strategy.on_bar(short_state, _ctx(datetime(2025, 9, 2, 10, 0), 3020, 3025, 3018, 3024))

    assert long_signal.action == TRADE_ACTION_SELL
    assert long_signal.volume == 3
    assert long_signal.reason == "take_profit"
    assert short_signal.action == TRADE_ACTION_BUY
    assert short_signal.volume == 2
    assert short_signal.reason == "stop_loss"


def test_target_modes_and_helpers() -> None:
    strategy = PrevdayVolumeFilterStrategyCore()
    state = _state()
    state.extra["prevday_volume_current_levels"] = {
        "date": datetime(2025, 9, 2).date(),
        "high": 3005.0,
        "low": 3000.0,
        "close": 3002.0,
        "open": 3004.0,
    }
    prev = DayLevels(
        date=datetime(2025, 9, 1).date(),
        high=3020.0,
        low=3000.0,
        close=3010.0,
        open=3008.0,
    )
    bar = Bar(
        symbol="DCE.m2601",
        datetime=datetime(2025, 9, 2, 10, 0),
        open=3000,
        high=3010,
        low=2998,
        close=3008,
        volume=3000,
    )
    metrics = strategy._bar_shock_metrics(
        bar,
        avg_volume=1000,
        avg_range=4,
        config=PrevdayVolumeFilterParams(volume_multiplier=2.0, range_multiplier=1.2, min_body_ratio=0.5),
    )

    assert (
        strategy._target_price("long", 3001, 5, prev, state, PrevdayVolumeFilterParams(take_profit_mode="open")) == 3004
    )
    assert (
        strategy._target_price("long", 3001, 5, prev, state, PrevdayVolumeFilterParams(take_profit_mode="opposite"))
        == 3020
    )
    assert (
        strategy._target_price(
            "short", 3019, 5, prev, state, PrevdayVolumeFilterParams(take_profit_mode="r", take_profit_r=2)
        )
        == 3009
    )
    assert strategy._target_is_valid("long", 3001, 3002)
    assert not strategy._target_is_valid("long", 3001, 3000)
    assert PrevdayVolumeFilterStrategyCore._passes_volume_filter(PrevdayVolumeFilterParams(), True, False)
    assert PrevdayVolumeFilterStrategyCore._parse_time("09:30").hour == 9
    assert PrevdayVolumeFilterStrategyCore._optional_float(3) == 3.0
    assert PrevdayVolumeFilterStrategyCore._optional_float("3") is None
    assert PrevdayVolumeFilterStrategyCore._float_list([1, "x", 2.5]) == [1.0, 2.5]
    assert metrics["is_shock"] is True
    assert metrics["volume_ratio"] == 3.0


def test_volume_zero_when_risk_or_margin_invalid() -> None:
    state = _state(PrevdayVolumeFilterParams(max_position_ratio=0.0))

    assert PrevdayVolumeFilterStrategyCore._calc_volume(state, 3000, 0, state.strategy_config) == 0
    assert PrevdayVolumeFilterStrategyCore._calc_volume(state, 3000, 5, state.strategy_config) == 0


def test_on_fill_noop() -> None:
    PrevdayVolumeFilterStrategyCore().on_fill(Fill())
