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
