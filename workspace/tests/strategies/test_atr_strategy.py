from math import nan
from types import SimpleNamespace

from strategies.atr_strategy import ATRCrossParams, ATRStrategyCore
from strategies.strategy_aspects.indicators import KDJ


def test_atr_p1_requirements_use_15m_background_and_5m_trigger() -> None:
    reqs = ATRStrategyCore().data_requirements(ATRCrossParams())

    assert "5m" in reqs.periods
    assert "15m" in reqs.periods
    assert "1m" not in reqs.periods
    assert "5m" in reqs.indicators
    assert "15m" in reqs.indicators


def test_atr_pullback_params_defaults() -> None:
    cfg = ATRCrossParams()

    assert cfg.kdj_pullback_long == 45
    assert cfg.kdj_pullback_short == 55
    assert cfg.kdj_signal_long == 50
    assert cfg.kdj_signal_short == 50
    assert cfg.time_stop_bars == 48
    assert cfg.entry_cooldown_minutes == 10
    assert not cfg.exit_on_reverse_signal


def test_atr_pullback_memory_allows_signal_after_recent_pullback() -> None:
    values = [60.0, 42.0, 53.0]
    ctx = SimpleNamespace(
        multi={"5m": SimpleNamespace(indicator_history=lambda _name, bars: values[-bars:])},
    )
    cfg = ATRCrossParams(kdj_pullback_long=45, kdj_signal_long=50)

    assert ATRStrategyCore()._has_long_pullback(ctx, cfg)


def test_atr_pullback_memory_requires_retrigger() -> None:
    values = [60.0, 42.0, 49.0]
    ctx = SimpleNamespace(
        multi={"5m": SimpleNamespace(indicator_history=lambda _name, bars: values[-bars:])},
    )
    cfg = ATRCrossParams(kdj_signal_long=50)

    assert not ATRStrategyCore()._has_long_pullback(ctx, cfg)


def test_recent_kdj_values_filters_nan_values() -> None:
    values = [nan, 48.0, nan, 53.0]
    ctx = SimpleNamespace(
        multi={"5m": SimpleNamespace(indicator_history=lambda _name, bars: values[-bars:])},
    )

    assert ATRStrategyCore._recent_kdj_values(ctx, 4) == [48.0, 53.0]


def test_recent_kdj_values_reads_5m_kdj_column_with_requested_lookback() -> None:
    calls = []

    def indicator_history(name: str, bars: int) -> list[float]:
        calls.append((name, bars))
        return [53.0]

    ctx = SimpleNamespace(multi={"5m": SimpleNamespace(indicator_history=indicator_history)})

    assert ATRStrategyCore._recent_kdj_values(ctx, 2) == [53.0]
    assert calls == [("5m_kdj_3_3_9", 2)]
    assert calls[0][0] == f"5m_{KDJ.name}_3_3_9"


def test_recent_kdj_values_returns_empty_without_5m_view() -> None:
    ctx = SimpleNamespace(multi={})

    assert ATRStrategyCore._recent_kdj_values(ctx, 2) == []


def test_short_pullback_uses_recent_indicator_history() -> None:
    values = [60.0, 48.0]
    ctx = SimpleNamespace(
        multi={"5m": SimpleNamespace(indicator_history=lambda _name, bars: values[-bars:])},
    )
    cfg = ATRCrossParams(kdj_signal_short=50)

    assert ATRStrategyCore()._has_short_pullback(ctx, cfg)
