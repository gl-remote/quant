from __future__ import annotations

from datetime import datetime

from common.constants import TRADE_ACTION_BUY, TRADE_ACTION_SELL, TRADE_DIRECTION_LONG, TRADE_DIRECTION_SHORT
from strategies.core import Bar, Fill, State, StrategyPosition
from strategies.core.indicators import generate_indicator_column_name
from strategies.runtime import BarContext
from strategies.runtime.period import PeriodData
from strategies.strategy_aspects.indicators import KDJ
from strategies.value_area_reacceptance_strategy import (
    CurrentSession,
    ValueAreaLevels,
    ValueAreaReacceptanceParams,
    ValueAreaReacceptanceStrategyCore,
)


def _ctx(dt: datetime, open_price: float, high: float, low: float, close: float, volume: float = 1000) -> BarContext:
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


def _bar(dt: datetime, open_price: float, high: float, low: float, close: float, volume: float = 1000) -> Bar:
    return Bar(symbol="DCE.m2601", datetime=dt, open=open_price, high=high, low=low, close=close, volume=volume)


def _ctx_with_multi(
    dt: datetime,
    open_price: float,
    high: float,
    low: float,
    close: float,
    bars: list[Bar],
) -> BarContext:
    period_data = PeriodData("5m")
    period_data.append_bars(bars)
    return BarContext(
        symbol="DCE.m2601",
        bar=_bar(dt, open_price, high, low, close),
        multi={"5m": period_data.get_data(dt, lookback_bars=len(bars))},
        events=[],
    )


def _ctx_with_indicator(
    dt: datetime,
    open_price: float,
    high: float,
    low: float,
    close: float,
    period: str,
    indicator_name: str,
    indicator_value: float,
) -> BarContext:
    period_data = PeriodData(period)
    period_data.append_bars([_bar(dt, open_price, high, low, close)])
    period_data.data[indicator_name] = indicator_value
    return BarContext(
        symbol="DCE.m2601",
        bar=_bar(dt, open_price, high, low, close),
        multi={period: period_data.get_data(dt, lookback_bars=1)},
        events=[],
    )


def _state(config: ValueAreaReacceptanceParams | None = None) -> State[ValueAreaReacceptanceParams]:
    return State(
        symbol="DCE.m2601",
        period="5m",
        strategy_config=config or ValueAreaReacceptanceParams(),
        capital=100000,
        contract_size=10,
        margin=0.1,
    )


def test_data_requirements_uses_configured_period() -> None:
    reqs = ValueAreaReacceptanceStrategyCore().data_requirements(ValueAreaReacceptanceParams(kline_period="1m"))

    assert reqs is not None
    assert set(reqs.periods) == {"1m"}
    assert reqs.periods["1m"].lookback_bars == 1
    assert reqs.indicators == {}

    kdj_reqs = ValueAreaReacceptanceStrategyCore().data_requirements(
        ValueAreaReacceptanceParams(kline_period="1m", kdj_long_max=45, kdj_short_min=55)
    )
    assert kdj_reqs is not None
    assert set(kdj_reqs.indicators) == {"1m"}
    assert kdj_reqs.indicators["1m"][0].name == "kdj"

    rolling_reqs = ValueAreaReacceptanceStrategyCore().data_requirements(
        ValueAreaReacceptanceParams(kline_period="5m", rolling_context_bars=12)
    )
    assert rolling_reqs is not None
    assert rolling_reqs.periods["5m"].lookback_bars == 24


def test_session_rolls_current_profile_into_value_area_levels() -> None:
    strategy = ValueAreaReacceptanceStrategyCore()
    state = _state(ValueAreaReacceptanceParams(price_tick=1.0, profile_mode="close"))

    strategy.on_bar(state, _ctx(datetime(2025, 9, 1, 9, 0), 3000, 3001, 2999, 3000, 100))
    strategy.on_bar(state, _ctx(datetime(2025, 9, 1, 9, 5), 3000, 3006, 2999, 3005, 300))
    strategy.on_bar(state, _ctx(datetime(2025, 9, 1, 9, 10), 3005, 3011, 3004, 3010, 100))
    strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 0), 3010, 3012, 3008, 3011, 100))
    strategy.on_bar(state, _ctx(datetime(2025, 9, 3, 9, 0), 3011, 3013, 3009, 3012, 100))

    levels = state.extra["value_area_levels"]
    history = state.extra["value_area_history"]
    current = state.extra["value_area_current_session"]
    assert levels["date"] == datetime(2025, 9, 2).date()
    assert len(history) == 2
    assert history[-1]["date"] == datetime(2025, 9, 2).date()
    assert current["date"] == datetime(2025, 9, 3).date()


def test_long_reacceptance_entry_sets_trade_info_and_volume() -> None:
    strategy = ValueAreaReacceptanceStrategyCore()
    state = _state(ValueAreaReacceptanceParams(take_profit_mode="poc", min_breakout_ticks=2))
    state.extra["value_area_levels"] = ValueAreaLevels(
        date=datetime(2025, 9, 1).date(),
        vah=3020.0,
        val=3000.0,
        poc=3010.0,
        high=3030.0,
        low=2990.0,
        close=3012.0,
        open=3008.0,
    )
    state.extra["value_area_current_session"] = CurrentSession(
        date=datetime(2025, 9, 2).date(), high=3005.0, low=3005.0, close=3005.0, open=3005.0, profile={}
    )

    breakout = strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 30), 3005, 3006, 2997, 2998))
    signal = strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 35), 2998, 3006, 2998, 3001))

    assert breakout.action == ""
    assert signal.action == TRADE_ACTION_BUY
    assert signal.reason == "value_area_val_reaccept_long"
    assert signal.volume > 0
    trade = state.extra["value_area_trade"]
    assert trade["strict_failure"] == 2996
    assert trade["stop_price"] == 2996
    assert trade["target_price"] == 3010
    assert trade["open_location"] == "inside"
    assert trade["prev_close_location"] == "inside"
    assert trade["open_close_poc_relation"] == "above_to_below"
    assert state.extra["value_area_trade_count"] == 1


def test_short_reacceptance_entry_sets_trade_info() -> None:
    strategy = ValueAreaReacceptanceStrategyCore()
    state = _state(ValueAreaReacceptanceParams(take_profit_mode="poc", min_breakout_ticks=2))
    state.extra["value_area_levels"] = ValueAreaLevels(
        date=datetime(2025, 9, 1).date(),
        vah=3020.0,
        val=3000.0,
        poc=3010.0,
        high=3030.0,
        low=2990.0,
        close=3012.0,
        open=3008.0,
    )
    state.extra["value_area_current_session"] = CurrentSession(
        date=datetime(2025, 9, 2).date(), high=3015.0, low=3015.0, close=3015.0, open=3015.0, profile={}
    )

    strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 10, 0), 3015, 3023, 3015, 3022))
    signal = strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 10, 5), 3022, 3022, 3018, 3019))

    assert signal.action == TRADE_ACTION_SELL
    assert signal.reason == "value_area_vah_reject_short"
    trade = state.extra["value_area_trade"]
    assert trade["strict_failure"] == 3024
    assert trade["target_price"] == 3010


def test_kdj_threshold_filter_blocks_weak_reacceptance() -> None:
    strategy = ValueAreaReacceptanceStrategyCore()
    config = ValueAreaReacceptanceParams(
        kline_period="1m", take_profit_mode="poc", min_breakout_ticks=2, kdj_long_max=45
    )
    state = _state(config)
    state.extra["value_area_levels"] = ValueAreaLevels(
        date=datetime(2025, 9, 1).date(),
        vah=3020.0,
        val=3000.0,
        poc=3010.0,
        high=3030.0,
        low=2990.0,
        close=3012.0,
        open=3008.0,
    )
    state.extra["value_area_current_session"] = CurrentSession(
        date=datetime(2025, 9, 2).date(), high=3005.0, low=3005.0, close=3005.0, open=3005.0, profile={}
    )
    col = generate_indicator_column_name(KDJ.name, KDJ.params, period="1m")

    strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 30), 3005, 3006, 2997, 2998))
    signal = strategy.on_bar(
        state, _ctx_with_indicator(datetime(2025, 9, 2, 9, 35), 2998, 3006, 2998, 3001, "1m", col, 60)
    )

    assert signal.action == ""
    assert "value_area_trade" not in state.extra


def test_kdj_threshold_filter_allows_confirmed_reacceptance() -> None:
    strategy = ValueAreaReacceptanceStrategyCore()
    config = ValueAreaReacceptanceParams(
        kline_period="1m", take_profit_mode="poc", min_breakout_ticks=2, kdj_long_max=45
    )
    state = _state(config)
    state.extra["value_area_levels"] = ValueAreaLevels(
        date=datetime(2025, 9, 1).date(),
        vah=3020.0,
        val=3000.0,
        poc=3010.0,
        high=3030.0,
        low=2990.0,
        close=3012.0,
        open=3008.0,
    )
    state.extra["value_area_current_session"] = CurrentSession(
        date=datetime(2025, 9, 2).date(), high=3005.0, low=3005.0, close=3005.0, open=3005.0, profile={}
    )
    col = generate_indicator_column_name(KDJ.name, KDJ.params, period="1m")

    strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 30), 3005, 3006, 2997, 2998))
    signal = strategy.on_bar(
        state, _ctx_with_indicator(datetime(2025, 9, 2, 9, 35), 2998, 3006, 2998, 3001, "1m", col, 40)
    )

    assert signal.action == TRADE_ACTION_BUY
    assert signal.alpha.fields["kdj_value"] == 40.0


def test_entry_blocked_without_valid_target() -> None:
    strategy = ValueAreaReacceptanceStrategyCore()
    state = _state(ValueAreaReacceptanceParams(take_profit_mode="poc", min_breakout_ticks=2))
    state.extra["value_area_levels"] = ValueAreaLevels(
        date=datetime(2025, 9, 1).date(),
        vah=3020.0,
        val=3000.0,
        poc=2999.0,
        high=3030.0,
        low=2990.0,
        close=3012.0,
        open=3008.0,
    )
    state.extra["value_area_current_session"] = CurrentSession(
        date=datetime(2025, 9, 2).date(), high=3005.0, low=3005.0, close=3005.0, open=3005.0, profile={}
    )

    strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 30), 3005, 3006, 2997, 2998))
    signal = strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 35), 2998, 3006, 2998, 3001))

    assert signal.action == ""
    assert "value_area_trade" not in state.extra


def test_quality_filters_block_weak_reacceptance() -> None:
    strategy = ValueAreaReacceptanceStrategyCore()
    state = _state(ValueAreaReacceptanceParams(take_profit_mode="poc", min_breakout_ticks=2, min_reaccept_ticks=2))
    state.extra["value_area_levels"] = ValueAreaLevels(
        date=datetime(2025, 9, 1).date(),
        vah=3020.0,
        val=3000.0,
        poc=3010.0,
        high=3030.0,
        low=2990.0,
        close=3012.0,
        open=3008.0,
    )
    state.extra["value_area_current_session"] = CurrentSession(
        date=datetime(2025, 9, 2).date(), high=3005.0, low=3005.0, close=3005.0, open=3005.0, profile={}
    )

    strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 30), 3005, 3006, 2997, 2998))
    weak_signal = strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 35), 2998, 3006, 2998, 3001))
    strong_signal = strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 40), 3001, 3006, 3001, 3002))

    assert weak_signal.action == ""
    assert strong_signal.action == TRADE_ACTION_BUY


def test_quality_filters_block_long_breakout_stay_and_small_target() -> None:
    strategy = ValueAreaReacceptanceStrategyCore()
    state = _state(
        ValueAreaReacceptanceParams(
            take_profit_mode="poc", min_breakout_ticks=2, max_breakout_bars=1, min_target_ticks=4
        )
    )
    state.extra["value_area_levels"] = ValueAreaLevels(
        date=datetime(2025, 9, 1).date(),
        vah=3020.0,
        val=3000.0,
        poc=3003.0,
        high=3030.0,
        low=2990.0,
        close=3012.0,
        open=3008.0,
    )
    state.extra["value_area_current_session"] = CurrentSession(
        date=datetime(2025, 9, 2).date(), high=3005.0, low=3005.0, close=3005.0, open=3005.0, profile={}
    )

    strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 30), 3005, 3006, 2997, 2998))
    strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 35), 2998, 2999, 2996, 2997))
    blocked_by_stay = strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 40), 2997, 3002, 2997, 3001))

    state.extra["value_area_long_breakout_bars"] = 1
    blocked_by_target = strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 45), 3001, 3002, 3001, 3001))

    assert blocked_by_stay.action == ""
    assert blocked_by_target.action == ""


def test_quality_filters_block_by_actual_rr_against_stop_distance() -> None:
    strategy = ValueAreaReacceptanceStrategyCore()
    state = _state(
        ValueAreaReacceptanceParams(
            take_profit_mode="poc",
            min_breakout_ticks=2,
            min_price_raw_rr=0.5,
            stop_widen_multiplier=1.5,
            target_distance_ratio=0.8,
        )
    )
    state.extra["value_area_levels"] = ValueAreaLevels(
        date=datetime(2025, 9, 1).date(),
        vah=3020.0,
        val=3000.0,
        poc=3005.0,
        high=3030.0,
        low=2990.0,
        close=3012.0,
        open=3008.0,
    )
    state.extra["value_area_current_session"] = CurrentSession(
        date=datetime(2025, 9, 2).date(), high=3005.0, low=3005.0, close=3005.0, open=3005.0, profile={}
    )

    strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 30), 3005, 3006, 2997, 2998))
    signal = strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 9, 35), 2998, 3006, 2998, 3001))

    assert signal.action == ""
    assert "value_area_trade" not in state.extra


def test_exit_long_by_take_profit() -> None:
    strategy = ValueAreaReacceptanceStrategyCore()
    state = _state()
    state.position = StrategyPosition(direction=TRADE_DIRECTION_LONG, entry_price=3001, volume=3)
    state.extra["value_area_trade"] = {
        "side": "long",
        "entry_price": 3001.0,
        "strict_failure": 2996.0,
        "stop_price": 2996.0,
        "target_price": 3010.0,
        "target_distance": 9.0,
        "strict_distance": 5.0,
        "price_raw_rr": 1.8,
        "entry_bar_range": 5.0,
        "entry_bar_range_ratio": 1.0,
        "open_location": "inside",
        "prev_close_location": "inside",
        "open_poc_distance": 5.0,
        "prev_close_poc_distance": 2.0,
        "open_close_poc_relation": "above_to_below",
        "persistent_value_days": 3,
        "value_overlap_ratio": 0.85,
        "poc_drift": 3.0,
        "stable_poc": True,
        "context_label": "1h",
        "context_available": True,
        "context_location": "inside",
        "context_target_distance": 9.0,
        "context_price_raw_rr": 1.8,
        "context_persistence_bars": 3,
        "context_overlap_ratio": 0.85,
        "context_poc_drift": 3.0,
        "context_stable_poc": True,
        "vah": 3020.0,
        "val": 3000.0,
        "poc": 3010.0,
    }
    state.extra["value_area_current_session"] = CurrentSession(
        date=datetime(2025, 9, 2).date(), high=3005.0, low=3005.0, close=3005.0, open=3005.0, profile={}
    )

    signal = strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 10, 0), 3005, 3011, 3005, 3010))

    assert signal.action == TRADE_ACTION_SELL
    assert signal.volume == 3
    assert signal.reason == (
        "take_profit|td=8_12|rr=ge1_5|vr=1_1_5|ol=inside|cl=inside|op=lt6|cp=lt6"
        "|ocr=above_to_below|pd=3d_plus|ov=high|ps=stable"
        "|ctx=1h|ctxloc=inside|ctd=8_12|crr=ge1_5|cpb=3b_plus|cov=high|cps=stable"
    )


def test_exit_short_by_stop_loss() -> None:
    strategy = ValueAreaReacceptanceStrategyCore()
    state = _state()
    state.position = StrategyPosition(direction=TRADE_DIRECTION_SHORT, entry_price=3019, volume=2)
    state.extra["value_area_trade"] = {
        "side": "short",
        "entry_price": 3019.0,
        "strict_failure": 3024.0,
        "stop_price": 3024.0,
        "target_price": 3010.0,
        "target_distance": 9.0,
        "strict_distance": 5.0,
        "price_raw_rr": 1.8,
        "entry_bar_range": 5.0,
        "entry_bar_range_ratio": 1.0,
        "open_location": "inside",
        "prev_close_location": "inside",
        "open_poc_distance": 5.0,
        "prev_close_poc_distance": 2.0,
        "open_close_poc_relation": "above_to_below",
        "persistent_value_days": 3,
        "value_overlap_ratio": 0.85,
        "poc_drift": 3.0,
        "stable_poc": True,
        "context_label": "1h",
        "context_available": True,
        "context_location": "inside",
        "context_target_distance": 9.0,
        "context_price_raw_rr": 1.8,
        "context_persistence_bars": 3,
        "context_overlap_ratio": 0.85,
        "context_poc_drift": 3.0,
        "context_stable_poc": True,
        "vah": 3020.0,
        "val": 3000.0,
        "poc": 3010.0,
    }
    state.extra["value_area_current_session"] = CurrentSession(
        date=datetime(2025, 9, 2).date(), high=3020.0, low=3018.0, close=3020.0, open=3020.0, profile={}
    )

    signal = strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 10, 0), 3020, 3025, 3018, 3024))

    assert signal.action == TRADE_ACTION_BUY
    assert signal.volume == 2
    assert signal.reason == (
        "stop_loss|td=8_12|rr=ge1_5|vr=1_1_5|ol=inside|cl=inside|op=lt6|cp=lt6"
        "|ocr=above_to_below|pd=3d_plus|ov=high|ps=stable"
        "|ctx=1h|ctxloc=inside|ctd=8_12|crr=ge1_5|cpb=3b_plus|cov=high|cps=stable"
    )


def test_path_failure_exits_when_trade_does_not_progress() -> None:
    strategy = ValueAreaReacceptanceStrategyCore()
    state = _state(ValueAreaReacceptanceParams(path_check_bars=1, min_path_progress_ticks=2))
    state.position = StrategyPosition(direction=TRADE_DIRECTION_LONG, entry_price=3001, volume=3)
    state.extra["value_area_holding_bars"] = 1
    state.extra["value_area_trade"] = {
        "side": "long",
        "entry_price": 3001.0,
        "strict_failure": 2996.0,
        "stop_price": 2996.0,
        "target_price": 3010.0,
        "target_distance": 9.0,
        "strict_distance": 5.0,
        "price_raw_rr": 1.8,
        "entry_bar_range": 5.0,
        "entry_bar_range_ratio": 1.0,
        "open_location": "inside",
        "prev_close_location": "inside",
        "open_poc_distance": 5.0,
        "prev_close_poc_distance": 2.0,
        "open_close_poc_relation": "above_to_below",
        "persistent_value_days": 3,
        "value_overlap_ratio": 0.85,
        "poc_drift": 3.0,
        "stable_poc": True,
        "context_label": "1h",
        "context_available": True,
        "context_location": "inside",
        "context_target_distance": 9.0,
        "context_price_raw_rr": 1.8,
        "context_persistence_bars": 3,
        "context_overlap_ratio": 0.85,
        "context_poc_drift": 3.0,
        "context_stable_poc": True,
        "vah": 3020.0,
        "val": 3000.0,
        "poc": 3010.0,
    }
    state.extra["value_area_current_session"] = CurrentSession(
        date=datetime(2025, 9, 2).date(), high=3001.0, low=3000.0, close=3001.0, open=3001.0, profile={}
    )

    signal = strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 10, 0), 3001, 3002, 3000, 3001))

    assert signal.action == TRADE_ACTION_SELL
    assert signal.volume == 3
    assert signal.reason == (
        "path_failure|td=8_12|rr=ge1_5|vr=1_1_5|ol=inside|cl=inside|op=lt6|cp=lt6"
        "|ocr=above_to_below|pd=3d_plus|ov=high|ps=stable"
        "|ctx=1h|ctxloc=inside|ctd=8_12|crr=ge1_5|cpb=3b_plus|cov=high|cps=stable"
    )
    assert signal.diagnostics["path_progress"] == 1.0


def test_path_failure_allows_trade_with_enough_progress() -> None:
    strategy = ValueAreaReacceptanceStrategyCore()
    state = _state(ValueAreaReacceptanceParams(path_check_bars=1, min_path_progress_ticks=2))
    state.position = StrategyPosition(direction=TRADE_DIRECTION_SHORT, entry_price=3019, volume=2)
    state.extra["value_area_holding_bars"] = 1
    state.extra["value_area_trade"] = {
        "side": "short",
        "entry_price": 3019.0,
        "strict_failure": 3024.0,
        "stop_price": 3024.0,
        "target_price": 3010.0,
        "target_distance": 9.0,
        "strict_distance": 5.0,
        "price_raw_rr": 1.8,
        "entry_bar_range": 5.0,
        "entry_bar_range_ratio": 1.0,
        "open_location": "inside",
        "prev_close_location": "inside",
        "open_poc_distance": 5.0,
        "prev_close_poc_distance": 2.0,
        "open_close_poc_relation": "above_to_below",
        "persistent_value_days": 3,
        "value_overlap_ratio": 0.85,
        "poc_drift": 3.0,
        "stable_poc": True,
        "context_label": "1h",
        "context_available": True,
        "context_location": "inside",
        "context_target_distance": 9.0,
        "context_price_raw_rr": 1.8,
        "context_persistence_bars": 3,
        "context_overlap_ratio": 0.85,
        "context_poc_drift": 3.0,
        "context_stable_poc": True,
        "vah": 3020.0,
        "val": 3000.0,
        "poc": 3010.0,
    }
    state.extra["value_area_current_session"] = CurrentSession(
        date=datetime(2025, 9, 2).date(), high=3019.0, low=3019.0, close=3019.0, open=3019.0, profile={}
    )

    signal = strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 10, 0), 3019, 3020, 3016, 3018))

    assert signal.action == ""
    assert state.extra["value_area_path_best_progress"] == 3.0


def test_mfe_pullback_exits_after_enough_progress_and_reversal() -> None:
    strategy = ValueAreaReacceptanceStrategyCore()
    state = _state(ValueAreaReacceptanceParams(mfe_pullback_min_progress_ticks=4, mfe_pullback_ticks=2))
    state.position = StrategyPosition(direction=TRADE_DIRECTION_LONG, entry_price=3001, volume=3)
    state.extra["value_area_trade"] = {
        "side": "long",
        "entry_price": 3001.0,
        "strict_failure": 2996.0,
        "stop_price": 2996.0,
        "target_price": 3010.0,
        "target_distance": 9.0,
        "strict_distance": 5.0,
        "price_raw_rr": 1.8,
        "entry_bar_range": 5.0,
        "entry_bar_range_ratio": 1.0,
        "open_location": "inside",
        "prev_close_location": "inside",
        "open_poc_distance": 5.0,
        "prev_close_poc_distance": 2.0,
        "open_close_poc_relation": "above_to_below",
        "persistent_value_days": 3,
        "value_overlap_ratio": 0.85,
        "poc_drift": 3.0,
        "stable_poc": True,
        "context_label": "1h",
        "context_available": True,
        "context_location": "inside",
        "context_target_distance": 9.0,
        "context_price_raw_rr": 1.8,
        "context_persistence_bars": 3,
        "context_overlap_ratio": 0.85,
        "context_poc_drift": 3.0,
        "context_stable_poc": True,
        "vah": 3020.0,
        "val": 3000.0,
        "poc": 3010.0,
    }
    state.extra["value_area_current_session"] = CurrentSession(
        date=datetime(2025, 9, 2).date(), high=3001.0, low=3001.0, close=3001.0, open=3001.0, profile={}
    )

    signal = strategy.on_bar(state, _ctx(datetime(2025, 9, 2, 10, 0), 3001, 3006, 3002, 3003))

    assert signal.action == TRADE_ACTION_SELL
    assert signal.volume == 3
    assert signal.reason.startswith("mfe_pullback|")
    assert signal.diagnostics["path_progress"] == 5.0


def test_target_modes_and_helpers() -> None:
    strategy = ValueAreaReacceptanceStrategyCore()
    prev = ValueAreaLevels(
        date=datetime(2025, 9, 1).date(),
        vah=3020.0,
        val=3000.0,
        poc=3010.0,
        high=3030.0,
        low=2990.0,
        close=3012.0,
        open=3008.0,
    )

    assert (
        strategy._raw_target_price("long", 3001, 5, prev, ValueAreaReacceptanceParams(take_profit_mode="opposite"))
        == 3020
    )
    assert (
        strategy._raw_target_price("short", 3019, 5, prev, ValueAreaReacceptanceParams(take_profit_mode="opposite"))
        == 3000
    )
    assert (
        strategy._raw_target_price(
            "short", 3019, 5, prev, ValueAreaReacceptanceParams(take_profit_mode="r", take_profit_r=2)
        )
        == 3009
    )
    assert (
        strategy._execution_target_price("long", 3001, 3010, ValueAreaReacceptanceParams(target_band_ticks=1)) == 3009
    )
    assert (
        strategy._execution_target_price("short", 3019, 3010, ValueAreaReacceptanceParams(target_band_ticks=1)) == 3011
    )
    assert (
        strategy._execution_target_price("long", 3001, 3010, ValueAreaReacceptanceParams(target_distance_ratio=0.8))
        == 3008.2
    )
    assert strategy._target_is_valid("long", 3001, 3002)
    assert not strategy._target_is_valid("long", 3001, 3000)
    assert ValueAreaReacceptanceStrategyCore._parse_time("09:30").hour == 9
    assert ValueAreaReacceptanceStrategyCore._optional_float(3) == 3.0
    assert ValueAreaReacceptanceStrategyCore._optional_float("3") is None
    assert ValueAreaReacceptanceStrategyCore._distance_bucket(5.9) == "lt6"
    assert ValueAreaReacceptanceStrategyCore._distance_bucket(7.9) == "6_8"
    assert ValueAreaReacceptanceStrategyCore._distance_bucket(11.9) == "8_12"
    assert ValueAreaReacceptanceStrategyCore._distance_bucket(12) == "ge12"
    assert ValueAreaReacceptanceStrategyCore._rr_bucket(0.4) == "lt0_5"
    assert ValueAreaReacceptanceStrategyCore._rr_bucket(0.9) == "0_5_1"
    assert ValueAreaReacceptanceStrategyCore._rr_bucket(1.4) == "1_1_5"
    assert ValueAreaReacceptanceStrategyCore._rr_bucket(1.5) == "ge1_5"
    assert ValueAreaReacceptanceStrategyCore._volatility_bucket(0.4) == "lt0_5"
    assert ValueAreaReacceptanceStrategyCore._volatility_bucket(0.9) == "0_5_1"
    assert ValueAreaReacceptanceStrategyCore._volatility_bucket(1.4) == "1_1_5"
    assert ValueAreaReacceptanceStrategyCore._volatility_bucket(1.5) == "ge1_5"
    assert ValueAreaReacceptanceStrategyCore._value_area_location(3021, prev) == "above"
    assert ValueAreaReacceptanceStrategyCore._value_area_location(3010, prev) == "inside"
    assert ValueAreaReacceptanceStrategyCore._value_area_location(2999, prev) == "below"
    assert ValueAreaReacceptanceStrategyCore._open_close_poc_relation(3008, prev) == "above_to_below"
    assert ValueAreaReacceptanceStrategyCore._open_close_poc_relation(3012, prev) == "same_above"
    older = ValueAreaLevels(
        date=datetime(2025, 8, 31).date(),
        vah=3018.0,
        val=3002.0,
        poc=3009.0,
        high=3022.0,
        low=2998.0,
        close=3010.0,
        open=3008.0,
    )
    assert ValueAreaReacceptanceStrategyCore._value_area_overlap_ratio(prev, older) == 0.8
    assert ValueAreaReacceptanceStrategyCore._persistence_bucket(1) == "1d"
    assert ValueAreaReacceptanceStrategyCore._persistence_bucket(2) == "2d"
    assert ValueAreaReacceptanceStrategyCore._persistence_bucket(3) == "3d_plus"
    assert ValueAreaReacceptanceStrategyCore._overlap_bucket(0.4) == "low"
    assert ValueAreaReacceptanceStrategyCore._overlap_bucket(0.7) == "mid"
    assert ValueAreaReacceptanceStrategyCore._overlap_bucket(0.8) == "high"
    assert ValueAreaReacceptanceStrategyCore._poc_stability_bucket(True, 3) == "stable"
    assert ValueAreaReacceptanceStrategyCore._poc_stability_bucket(False, 6) == "mild_drift"
    assert ValueAreaReacceptanceStrategyCore._poc_stability_bucket(False, 8) == "drift"


def test_rolling_window_value_info_uses_5m_profile_windows() -> None:
    config = ValueAreaReacceptanceParams(price_tick=1.0, profile_mode="close", rolling_context_bars=2)
    bars = [
        _bar(datetime(2025, 9, 2, 9, 0), 3000, 3001, 2999, 3000, 100),
        _bar(datetime(2025, 9, 2, 9, 5), 3000, 3006, 2999, 3005, 300),
        _bar(datetime(2025, 9, 2, 9, 10), 3005, 3011, 3004, 3010, 300),
        _bar(datetime(2025, 9, 2, 9, 15), 3010, 3012, 3008, 3011, 100),
    ]
    ctx = _ctx_with_multi(datetime(2025, 9, 2, 9, 15), 3010, 3012, 3008, 3011, bars)

    info = ValueAreaReacceptanceStrategyCore._window_value_info(ctx, config)

    assert info["available"]
    assert info["label"] == "roll2"
    assert info["persistence_bars"] == 1
    assert info["poc"] == 3010.0
    assert info["overlap_ratio"] == 0.0


def test_volume_zero_when_risk_or_margin_invalid() -> None:
    state = _state(ValueAreaReacceptanceParams(max_position_ratio=0.0))

    assert ValueAreaReacceptanceStrategyCore._calc_volume(state, 3000, 0, state.strategy_config) == 0
    assert ValueAreaReacceptanceStrategyCore._calc_volume(state, 3000, 5, state.strategy_config) == 0


def test_on_fill_noop() -> None:
    ValueAreaReacceptanceStrategyCore().on_fill(Fill())
