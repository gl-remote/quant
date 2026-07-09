from __future__ import annotations

from types import SimpleNamespace

import pytest
from backtest.optimizer import (
    LOW_ACTIVITY_SCORE,
    MIN_TRADES_PER_RESULT,
    calculate_optimization_score,
)


def _result(
    *,
    success: bool = True,
    total_trades: int = MIN_TRADES_PER_RESULT,
    annual_return: float = 10.0,
    max_ddpercent: float = 5.0,
) -> SimpleNamespace:
    return SimpleNamespace(
        success=success,
        total_trades=total_trades,
        annual_return=annual_return,
        max_ddpercent=max_ddpercent,
    )


def test_score_penalizes_no_successful_results() -> None:
    assert calculate_optimization_score([_result(success=False)]) == LOW_ACTIVITY_SCORE


def test_score_penalizes_low_trade_activity() -> None:
    results = [
        _result(total_trades=MIN_TRADES_PER_RESULT),
        _result(total_trades=MIN_TRADES_PER_RESULT - 1),
    ]

    assert calculate_optimization_score(results) == LOW_ACTIVITY_SCORE


def test_score_averages_calmar_for_active_results() -> None:
    results = [
        _result(total_trades=MIN_TRADES_PER_RESULT, annual_return=10.0, max_ddpercent=5.0),
        _result(total_trades=MIN_TRADES_PER_RESULT + 1, annual_return=6.0, max_ddpercent=3.0),
    ]

    assert calculate_optimization_score(results) == pytest.approx(2.0)
