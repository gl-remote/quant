from __future__ import annotations

from datetime import datetime

from common.constants import TRADE_ACTION_BUY, TRADE_ACTION_SELL, TRADE_DIRECTION_LONG, TRADE_DIRECTION_SHORT
from strategies.core import Bar, State, StrategyPosition
from strategies.runtime import BarContext
from strategies.volume_shock_boundary_strategy import (
    ShockInfo,
    VolumeShockBoundaryParams,
    VolumeShockBoundaryStrategyCore,
)


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


def _state(config: VolumeShockBoundaryParams | None = None) -> State[VolumeShockBoundaryParams]:
    return State(
        symbol="DCE.m2601",
        period="1m",
        strategy_config=config or VolumeShockBoundaryParams(),
        capital=100000,
        contract_size=10,
        margin=0.1,
    )


def _warmup(strategy: VolumeShockBoundaryStrategyCore, state: State[VolumeShockBoundaryParams]) -> None:
    for minute in range(20):
        strategy.on_bar(state, _ctx(datetime(2025, 9, 1, 9, minute), 3000, 3002, 2998, 3001, 1000))


def test_data_requirements_uses_configured_period_and_lookback() -> None:
    reqs = VolumeShockBoundaryStrategyCore().data_requirements(
        VolumeShockBoundaryParams(kline_period="5m", volume_lookback=30, range_lookback=10)
    )

    assert reqs is not None
    assert set(reqs.periods) == {"5m"}
    assert reqs.periods["5m"].lookback_bars == 30
    assert reqs.indicators == {}


def test_down_shock_low_reacceptance_entry_sets_trade_info() -> None:
    strategy = VolumeShockBoundaryStrategyCore()
    state = _state(VolumeShockBoundaryParams(take_profit_mode="mid", volume_multiplier=2.0, range_multiplier=1.2))
    _warmup(strategy, state)

    shock_signal = strategy.on_bar(state, _ctx(datetime(2025, 9, 1, 9, 20), 3000, 3001, 2988, 2990, 3000))
    breakout = strategy.on_bar(state, _ctx(datetime(2025, 9, 1, 9, 21), 2990, 2991, 2986, 2987, 1000))
    signal = strategy.on_bar(state, _ctx(datetime(2025, 9, 1, 9, 22), 2987, 2995, 2987, 2989, 1000))

    assert shock_signal.action == ""
    assert breakout.action == ""
    assert signal.action == TRADE_ACTION_BUY
    assert signal.reason == "volume_shock_low_reaccept_long"
    assert signal.volume > 0
    trade = state.extra["volume_shock_trade"]
    assert trade["strict_failure"] == 2985
    assert trade["stop_price"] == 2985
    assert trade["target_price"] == 2994.5
    assert state.extra["volume_shock_trade_count"] == 1


def test_up_shock_high_rejection_entry_sets_trade_info() -> None:
    strategy = VolumeShockBoundaryStrategyCore()
    state = _state(VolumeShockBoundaryParams(take_profit_mode="opposite", volume_multiplier=2.0, range_multiplier=1.2))
    _warmup(strategy, state)

    strategy.on_bar(state, _ctx(datetime(2025, 9, 1, 9, 20), 3000, 3012, 2999, 3011, 3000))
    strategy.on_bar(state, _ctx(datetime(2025, 9, 1, 9, 21), 3011, 3014, 3010, 3013, 1000))
    signal = strategy.on_bar(state, _ctx(datetime(2025, 9, 1, 9, 22), 3013, 3013, 3005, 3011, 1000))

    assert signal.action == TRADE_ACTION_SELL
    assert signal.reason == "volume_shock_high_reject_short"
    trade = state.extra["volume_shock_trade"]
    assert trade["strict_failure"] == 3015
    assert trade["target_price"] == 2999


def test_shock_expires_and_trade_limit_blocks_entry() -> None:
    strategy = VolumeShockBoundaryStrategyCore()
    cfg = VolumeShockBoundaryParams(
        volume_multiplier=2.0,
        range_multiplier=1.2,
        shock_valid_bars=1,
        max_trades_per_day=1,
    )
    state = _state(cfg)
    _warmup(strategy, state)

    strategy.on_bar(state, _ctx(datetime(2025, 9, 1, 9, 20), 3000, 3001, 2988, 2990, 3000))
    strategy.on_bar(state, _ctx(datetime(2025, 9, 1, 9, 21), 2990, 2991, 2986, 2987, 1000))
    expired = strategy.on_bar(state, _ctx(datetime(2025, 9, 1, 9, 22), 2987, 2995, 2987, 2989, 1000))

    assert expired.action == ""

    state.extra["volume_shock_trade_count"] = 1
    state.extra["volume_shock_active"] = {
        "date": datetime(2025, 9, 1).date(),
        "direction": "down",
        "high": 3001.0,
        "low": 2988.0,
        "mid": 2994.5,
        "close": 2990.0,
        "bar_index": state.extra["volume_shock_bar_index"],
        "volume_ratio": 3.0,
        "range_ratio": 2.0,
        "body_ratio": 0.7,
        "traded": False,
    }
    state.extra["volume_shock_long_breakout_low"] = 2986.0
    blocked = strategy.on_bar(state, _ctx(datetime(2025, 9, 1, 9, 23), 2987, 2995, 2987, 2989, 1000))

    assert blocked.action == ""


def test_exit_long_by_take_profit() -> None:
    strategy = VolumeShockBoundaryStrategyCore()
    state = _state()
    state.position = StrategyPosition(direction=TRADE_DIRECTION_LONG, entry_price=2989, volume=3)
    state.extra["volume_shock_session"] = datetime(2025, 9, 1).date()
    state.extra["volume_shock_trade"] = {
        "side": "long",
        "entry_price": 2989.0,
        "strict_failure": 2985.0,
        "stop_price": 2985.0,
        "target_price": 2994.5,
        "shock_high": 3001.0,
        "shock_low": 2988.0,
        "shock_mid": 2994.5,
        "volume_ratio": 3.0,
        "range_ratio": 2.0,
    }

    signal = strategy.on_bar(state, _ctx(datetime(2025, 9, 1, 10, 0), 2990, 2995, 2990, 2994, 1000))

    assert signal.action == TRADE_ACTION_SELL
    assert signal.volume == 3
    assert signal.reason == "take_profit"


def test_exit_short_by_stop_loss() -> None:
    strategy = VolumeShockBoundaryStrategyCore()
    state = _state()
    state.position = StrategyPosition(direction=TRADE_DIRECTION_SHORT, entry_price=3011, volume=2)
    state.extra["volume_shock_session"] = datetime(2025, 9, 1).date()
    state.extra["volume_shock_trade"] = {
        "side": "short",
        "entry_price": 3011.0,
        "strict_failure": 3015.0,
        "stop_price": 3015.0,
        "target_price": 2999.0,
        "shock_high": 3012.0,
        "shock_low": 2999.0,
        "shock_mid": 3005.5,
        "volume_ratio": 3.0,
        "range_ratio": 2.0,
    }

    signal = strategy.on_bar(state, _ctx(datetime(2025, 9, 1, 10, 0), 3012, 3016, 3010, 3015, 1000))

    assert signal.action == TRADE_ACTION_BUY
    assert signal.volume == 2
    assert signal.reason == "stop_loss"


def test_target_modes_and_helpers() -> None:
    strategy = VolumeShockBoundaryStrategyCore()
    shock = ShockInfo(
        date=datetime(2025, 9, 1).date(),
        direction="down",
        high=3001.0,
        low=2988.0,
        mid=2994.5,
        close=2990.0,
        bar_index=1,
        volume_ratio=3.0,
        range_ratio=2.0,
        body_ratio=0.7,
        traded=False,
    )

    assert strategy._target_price("long", 2989, 4, shock, VolumeShockBoundaryParams(take_profit_mode="mid")) == 2994.5
    assert (
        strategy._target_price("long", 2989, 4, shock, VolumeShockBoundaryParams(take_profit_mode="opposite")) == 3001
    )
    assert (
        strategy._target_price(
            "short", 3011, 4, shock, VolumeShockBoundaryParams(take_profit_mode="r", take_profit_r=2.0)
        )
        == 3003
    )
