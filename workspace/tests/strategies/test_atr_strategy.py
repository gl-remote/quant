from types import SimpleNamespace

from strategies.atr_strategy import ATRCrossParams, ATRStrategyCore


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
