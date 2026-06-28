from __future__ import annotations

from datetime import datetime

from common.constants import TRADE_ACTION_BUY, TRADE_ACTION_SELL, TRADE_DIRECTION_LONG, TRADE_DIRECTION_SHORT
from strategies.core import Bar, Fill, State, StrategyPosition
from strategies.prevday_reacceptance_strategy import (
    DayLevels,
    PrevdayReacceptanceParams,
    PrevdayReacceptanceStrategyCore,
)
from strategies.runtime import BarContext


def _ctx(dt: datetime, open_price: float, high: float, low: float, close: float) -> BarContext:
    return BarContext(
        symbol="DCE.m2601",
        bar=Bar(
            symbol="DCE.m2601",
            datetime=dt,
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=1000,
        ),
        multi={},
        events=[],
    )


def _state(config: PrevdayReacceptanceParams | None = None) -> State[PrevdayReacceptanceParams]:
    return State(
        symbol="DCE.m2601",
        period="1m",
        strategy_config=config or PrevdayReacceptanceParams(),
        capital=100000,
        contract_size=10,
        margin=0.1,
    )


def test_data_requirements_uses_configured_period() -> None:
    reqs = PrevdayReacceptanceStrategyCore().data_requirements(PrevdayReacceptanceParams(kline_period="5m"))

    assert reqs is not None
    assert set(reqs.periods) == {"5m"}
    assert reqs.periods["5m"].lookback_bars == 1
    assert reqs.indicators == {}


def test_session_rolls_current_day_into_prev_levels() -> None:
    strategy = PrevdayReacceptanceStrategyCore()
    state = _state()

    strategy.on_bar(state, _ctx(datetime(2025, 9, 1, 9, 0), 3000, 3010, 2990, 3005))
    strategy.on_bar(state, _ctx(datetime(2025, 9, 1, 10, 0), 3005, 3020, 2985, 3010))
    strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 0), 3010, 3015, 3000, 3008))

    prev = state.extra["prevday_levels"]
    current = state.extra["prevday_current_levels"]
    assert prev["high"] == 3020
    assert prev["low"] == 2985
    assert prev["close"] == 3010
    assert current["date"] == datetime(2025, 9, 2).date()


def test_long_reacceptance_entry_sets_trade_info_and_volume() -> None:
    strategy = PrevdayReacceptanceStrategyCore()
    state = _state(PrevdayReacceptanceParams(take_profit_mode="mid", min_breakout_ticks=2))
    state.extra["prevday_levels"] = {
        "date": datetime(2025, 9, 1).date(),
        "high": 3020.0,
        "low": 3000.0,
        "close": 3010.0,
        "open": 3008.0,
    }
    state.extra["prevday_current_levels"] = {
        "date": datetime(2025, 9, 2).date(),
        "high": 3005.0,
        "low": 3005.0,
        "close": 3005.0,
        "open": 3005.0,
    }

    breakout = strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 30), 3005, 3006, 2997, 2998))
    signal = strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 31), 2998, 3006, 2998, 3001))

    assert breakout.action == ""
    assert signal.action == TRADE_ACTION_BUY
    assert signal.reason == "prevday_low_reaccept_long"
    assert signal.volume > 0
    trade = state.extra["prevday_trade"]
    assert trade["strict_failure"] == 2996
    assert trade["stop_price"] == 2996
    assert trade["target_price"] == 3010
    assert state.extra["prevday_trade_count"] == 1


def test_short_reacceptance_entry_sets_trade_info() -> None:
    strategy = PrevdayReacceptanceStrategyCore()
    state = _state(PrevdayReacceptanceParams(take_profit_mode="close", min_breakout_ticks=2))
    state.extra["prevday_levels"] = {
        "date": datetime(2025, 9, 1).date(),
        "high": 3020.0,
        "low": 3000.0,
        "close": 3010.0,
        "open": 3008.0,
    }
    state.extra["prevday_current_levels"] = {
        "date": datetime(2025, 9, 2).date(),
        "high": 3015.0,
        "low": 3015.0,
        "close": 3015.0,
        "open": 3015.0,
    }

    strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 10, 0), 3015, 3023, 3015, 3022))
    signal = strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 10, 1), 3022, 3022, 3018, 3019))

    assert signal.action == TRADE_ACTION_SELL
    assert signal.reason == "prevday_high_reject_short"
    trade = state.extra["prevday_trade"]
    assert trade["strict_failure"] == 3024
    assert trade["target_price"] == 3010


def test_entry_blocked_without_valid_target() -> None:
    strategy = PrevdayReacceptanceStrategyCore()
    state = _state(PrevdayReacceptanceParams(take_profit_mode="close", min_breakout_ticks=2))
    state.extra["prevday_levels"] = {
        "date": datetime(2025, 9, 1).date(),
        "high": 3020.0,
        "low": 3000.0,
        "close": 2999.0,
        "open": 3008.0,
    }
    state.extra["prevday_current_levels"] = {
        "date": datetime(2025, 9, 2).date(),
        "high": 3005.0,
        "low": 3005.0,
        "close": 3005.0,
        "open": 3005.0,
    }

    strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 30), 3005, 3006, 2997, 2998))
    signal = strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 31), 2998, 3006, 2998, 3001))

    assert signal.action == ""
    assert "prevday_trade" not in state.extra


def test_exit_long_by_take_profit() -> None:
    strategy = PrevdayReacceptanceStrategyCore()
    state = _state()
    state.position = StrategyPosition(direction=TRADE_DIRECTION_LONG, entry_price=3001, volume=3)
    state.extra["prevday_trade"] = {
        "side": "long",
        "entry_price": 3001.0,
        "strict_failure": 2996.0,
        "stop_price": 2996.0,
        "target_price": 3010.0,
        "prev_high": 3020.0,
        "prev_low": 3000.0,
        "prev_close": 3010.0,
    }
    state.extra["prevday_current_levels"] = {
        "date": datetime(2025, 9, 2).date(),
        "high": 3005.0,
        "low": 3005.0,
        "close": 3005.0,
        "open": 3005.0,
    }

    signal = strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 10, 0), 3005, 3011, 3005, 3010))

    assert signal.action == TRADE_ACTION_SELL
    assert signal.volume == 3
    assert signal.reason == "take_profit"


def test_exit_short_by_stop_loss() -> None:
    strategy = PrevdayReacceptanceStrategyCore()
    state = _state()
    state.position = StrategyPosition(direction=TRADE_DIRECTION_SHORT, entry_price=3019, volume=2)
    state.extra["prevday_trade"] = {
        "side": "short",
        "entry_price": 3019.0,
        "strict_failure": 3024.0,
        "stop_price": 3024.0,
        "target_price": 3010.0,
        "prev_high": 3020.0,
        "prev_low": 3000.0,
        "prev_close": 3010.0,
    }
    state.extra["prevday_current_levels"] = {
        "date": datetime(2025, 9, 2).date(),
        "high": 3020.0,
        "low": 3018.0,
        "close": 3020.0,
        "open": 3020.0,
    }

    signal = strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 10, 0), 3020, 3025, 3018, 3024))

    assert signal.action == TRADE_ACTION_BUY
    assert signal.volume == 2
    assert signal.reason == "stop_loss"


def test_force_flat_and_max_trade_limit_block_new_entry() -> None:
    strategy = PrevdayReacceptanceStrategyCore()
    cfg = PrevdayReacceptanceParams(max_trades_per_day=1)
    state = _state(cfg)
    state.extra["prevday_levels"] = {
        "date": datetime(2025, 9, 1).date(),
        "high": 3020.0,
        "low": 3000.0,
        "close": 3010.0,
        "open": 3008.0,
    }
    state.extra["prevday_current_levels"] = {
        "date": datetime(2025, 9, 2).date(),
        "high": 3005.0,
        "low": 3005.0,
        "close": 3005.0,
        "open": 3005.0,
    }
    state.extra["prevday_trade_count"] = 1

    blocked_by_count = strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 31), 2998, 3006, 2997, 3001))
    state.extra["prevday_trade_count"] = 0
    blocked_by_time = strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 14, 56), 2998, 3006, 2997, 3001))

    assert blocked_by_count.action == ""
    assert blocked_by_time.action == ""


def test_target_modes_and_helpers() -> None:
    strategy = PrevdayReacceptanceStrategyCore()
    state = _state()
    state.extra["prevday_current_levels"] = {
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

    assert (
        strategy._target_price("long", 3001, 5, prev, state, PrevdayReacceptanceParams(take_profit_mode="open")) == 3004
    )
    assert (
        strategy._target_price("long", 3001, 5, prev, state, PrevdayReacceptanceParams(take_profit_mode="opposite"))
        == 3020
    )
    assert (
        strategy._target_price("short", 3019, 5, prev, state, PrevdayReacceptanceParams(take_profit_mode="opposite"))
        == 3000
    )
    assert (
        strategy._target_price(
            "short", 3019, 5, prev, state, PrevdayReacceptanceParams(take_profit_mode="r", take_profit_r=2)
        )
        == 3009
    )
    assert strategy._target_is_valid("long", 3001, 3002)
    assert not strategy._target_is_valid("long", 3001, 3000)
    assert PrevdayReacceptanceStrategyCore._parse_time("09:30").hour == 9
    assert PrevdayReacceptanceStrategyCore._optional_float(3) == 3.0
    assert PrevdayReacceptanceStrategyCore._optional_float("3") is None


def test_volume_zero_when_risk_or_margin_invalid() -> None:
    state = _state(PrevdayReacceptanceParams(max_position_ratio=0.0))

    assert PrevdayReacceptanceStrategyCore._calc_volume(state, 3000, 0, state.strategy_config) == 0
    assert PrevdayReacceptanceStrategyCore._calc_volume(state, 3000, 5, state.strategy_config) == 0


def test_on_fill_noop() -> None:
    PrevdayReacceptanceStrategyCore().on_fill(Fill())
