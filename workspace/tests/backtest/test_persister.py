"""测试 backtest/persister.py — 回测结果持久化编排。"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest
from backtest.optimizer import SearchResult
from backtest.persister import BacktestResultPersister, SearchResultPersister, WalkForwardPersister
from backtest.results import WalkForwardAggregate, WalkForwardResult, WalkForwardWindowResult
from common.types import BacktestResult


class _FakeDataManager:
    def __init__(self) -> None:
        self.store = SimpleNamespace(db_path="sqlite:///fake-optuna.db")
        self.backtests: list[dict[str, Any]] = []
        self.daily: list[tuple[int, list[dict[str, object]]]] = []
        self.trades: list[tuple[int, list[dict[str, object]]]] = []
        self.validated: list[int] = []
        self.consistency_errors: list[str] = []

    def insert_backtest(self, result: BacktestResult, *, run_id: int | None = None, data_src: str | None = None) -> int:
        backtest_id = len(self.backtests) + 1
        self.backtests.append({"result": result, "run_id": run_id, "data_src": data_src})
        return backtest_id

    def insert_backtest_daily(self, backtest_id: int, daily: list[dict[str, object]]) -> None:
        self.daily.append((backtest_id, daily))

    def insert_backtest_trades(self, backtest_id: int, trades: list[dict[str, object]]) -> None:
        self.trades.append((backtest_id, trades))

    def validate_consistency(self, backtest_id: int) -> list[str]:
        self.validated.append(backtest_id)
        return self.consistency_errors


def _make_result(symbol: str = "DCE.m2601", *, success: bool = True) -> BacktestResult:
    return BacktestResult(symbol=symbol, strategy="ma_strategy", success=success)


def test_backtest_result_persister_writes_success_details_and_metadata() -> None:
    dm = _FakeDataManager()
    result = _make_result()
    result.daily_results = [{"datetime": "2026-01-01", "equity": 100000.0}]
    result.fills = [{"datetime": "2026-01-01 10:00:00", "symbol": "DCE.m2601"}]

    backtest_id = BacktestResultPersister(dm).persist_result(
        result,
        run_id=7,
        data_src="memory://DCE.m2601",
        strategy_params={"sma_short": 5, "signal_profile": "sma_only"},
        git_hash="abc1234",
    )

    assert backtest_id == 1
    assert result.status == "success"
    assert result.strategy_params == {"sma_short": 5, "signal_profile": "sma_only"}
    assert result.git_hash == "abc1234"
    assert dm.backtests == [{"result": result, "run_id": 7, "data_src": "memory://DCE.m2601"}]
    assert dm.daily == [(1, result.daily_results)]
    assert dm.trades == [(1, result.fills)]
    assert dm.validated == [1]


def test_backtest_result_persister_failed_result_only_writes_main_record() -> None:
    dm = _FakeDataManager()
    result = _make_result(success=False)
    result.daily_results = [{"datetime": "2026-01-01", "equity": 100000.0}]
    result.fills = [{"datetime": "2026-01-01 10:00:00", "symbol": "DCE.m2601"}]

    backtest_id = BacktestResultPersister(dm).persist_result(result, run_id=7)

    assert backtest_id == 1
    assert result.status == "failed"
    assert len(dm.backtests) == 1
    assert dm.daily == []
    assert dm.trades == []
    assert dm.validated == []


def test_backtest_result_persister_skip_validation_still_writes_details() -> None:
    dm = _FakeDataManager()
    result = _make_result()
    result.daily_results = [{"datetime": "2026-01-01", "equity": 100000.0}]
    result.fills = [{"datetime": "2026-01-01 10:00:00", "symbol": "DCE.m2601"}]

    BacktestResultPersister(dm).persist_result(result, skip_validation=True)

    assert dm.daily == [(1, result.daily_results)]
    assert dm.trades == [(1, result.fills)]
    assert dm.validated == []


def test_search_result_persister_adds_trial_config_and_returns_success_ids() -> None:
    dm = _FakeDataManager()
    success_result = _make_result("DCE.m2601", success=True)
    failed_result = _make_result("DCE.c2601", success=False)
    search_result = SearchResult(
        trial_data=[
            {
                "strategy_params": {"sma_short": 5, "sma_long": 20},
                "engine_results": [success_result, failed_result],
            }
        ]
    )
    datasets = [
        ("DCE.m2601", pd.DataFrame({"close": [1.0]}), "memory://m"),
        ("DCE.c2601", pd.DataFrame({"close": [2.0]}), "memory://c"),
    ]

    ids = SearchResultPersister(dm).persist_search_result(
        search_result,
        datasets=datasets,
        search_type="grid",
        study_name="study-1",
        git_hash="abc1234",
        run_id=9,
    )

    assert ids == [1]
    assert len(dm.backtests) == 2
    assert dm.backtests[0]["data_src"] == "memory://m"
    assert dm.backtests[1]["data_src"] == "memory://c"
    assert success_result.strategy_params == {"sma_short": 5, "sma_long": 20}
    assert failed_result.strategy_params == {"sma_short": 5, "sma_long": 20}
    assert success_result.git_hash == "abc1234"
    assert success_result.engine_config == {
        "type": "vnpy",
        "optimizer": "grid",
        "study_name": "study-1",
        "study_db": "sqlite:///fake-optuna.db",
        "trial_index": 0,
    }


def test_walk_forward_persister_requires_aggregate() -> None:
    wf_result = WalkForwardResult(success=True, windows=1)

    with pytest.raises(ValueError, match="缺少 aggregate"):
        WalkForwardPersister(_FakeDataManager()).persist_walk_forward(
            wf_result,
            symbol="DCE.m2601",
            strategy="ma_strategy",
            strategy_params={"sma_short": 5},
            strategy_version="1.0",
            git_hash="abc1234",
            start_date="2026-01-01",
            end_date="2026-01-31",
            data_src="memory://m",
        )


def test_walk_forward_persister_aggregates_window_details_and_skips_validation() -> None:
    dm = _FakeDataManager()
    wf_result = WalkForwardResult(
        success=True,
        windows=2,
        aggregate=WalkForwardAggregate(
            return_mean=0.12,
            return_std=0.03,
            sharpe_mean=1.5,
            max_drawdown_mean=-0.08,
        ),
        window_results=[
            WalkForwardWindowResult(
                window=0,
                train_rows=10,
                val_rows=2,
                test_rows=3,
                train_start="2026-01-01",
                train_end="2026-01-10",
                test_start="2026-01-11",
                test_end="2026-01-13",
                daily_results=[{"datetime": "2026-01-11", "equity": 101000.0}],
                trades=[{"datetime": "2026-01-11 10:00:00", "symbol": "DCE.m2601"}],
            ),
            WalkForwardWindowResult(
                window=1,
                train_rows=10,
                val_rows=2,
                test_rows=3,
                train_start="2026-02-01",
                train_end="2026-02-10",
                test_start="2026-02-11",
                test_end="2026-02-13",
                daily_results=[{"datetime": "2026-02-11", "equity": 102000.0}],
                trades=[{"datetime": "2026-02-11 10:00:00", "symbol": "DCE.m2601"}],
            ),
        ],
    )

    backtest_id = WalkForwardPersister(dm).persist_walk_forward(
        wf_result,
        symbol="DCE.m2601",
        strategy="ma_strategy",
        strategy_params={"sma_short": 5},
        strategy_version="1.0",
        git_hash="abc1234",
        start_date="2026-01-01",
        end_date="2026-02-13",
        data_src="memory://m",
    )

    persisted = dm.backtests[0]["result"]
    assert backtest_id == 1
    assert persisted.success is True
    assert persisted.status == "success"
    assert persisted.engine_config == {"type": "vnpy", "mode": "walk-forward", "windows": 2}
    assert persisted.total_return == 0.12
    assert persisted.daily_std == 0.03
    assert persisted.sharpe_ratio == 1.5
    assert persisted.max_drawdown == -0.08
    assert dm.backtests[0]["data_src"] == "memory://m"
    assert len(dm.daily[0][1]) == 2
    assert len(dm.trades[0][1]) == 2
    assert dm.validated == []
