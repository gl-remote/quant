"""Contract tests: validate real run artifacts against JSON schemas.

These tests read the latest ``project_data/reports/runs/r{N}/data/*.json`` files and check them
against the schemas defined in ``workspace/packages/contracts/schemas/``.

If no run directory exists (e.g. first-time clone), tests are skipped.
"""

import json
from pathlib import Path

import pytest
from quantsmith_contracts.validate import validate_run_artifacts


def test_latest_run_artifacts_conform_to_schemas(
    latest_run_dir: Path | None,
    nav_path: Path | None,
) -> None:
    """All 7 artifacts of the latest run + nav.json pass schema validation."""
    if latest_run_dir is None:
        pytest.skip("No project_data/reports/runs/r{N}/ directory found — run `make backtest-ma` first")

    issues = validate_run_artifacts(str(latest_run_dir), nav_path=str(nav_path) if nav_path else None)
    if issues:
        failing = "\n".join(f"  {i}" for i in issues)
        pytest.fail(f"Contract validation failed ({len(issues)} issue(s)):\n{failing}")


def test_fixture_run_artifacts_conform_to_schemas(tmp_path: Path) -> None:
    """A minimal deterministic fixture guards schemas without relying on local project_data."""
    run_dir = tmp_path / "reports" / "runs" / "r1"
    data_dir = run_dir / "data"
    data_dir.mkdir(parents=True)
    nav_path = tmp_path / "reports" / "data" / "nav.json"
    nav_path.parent.mkdir(parents=True)

    artifacts = {
        "run.json": {
            "id": 1,
            "strategy": "ma_strategy",
            "engine": "vnpy",
            "symbols": 1,
            "status": "success",
            "created_at": "2026-01-01T00:00:00",
        },
        "summary.json": [
            {
                "id": 1,
                "symbol": "DCE.m2601",
                "total_return": 0.12,
                "total_trades": 1,
                "end_balance": 112000.0,
                "start_date": "2026-01-01",
                "end_date": "2026-01-02",
                "kline_interval": "5m",
            }
        ],
        "backtests.json": [
            {
                "id": 1,
                "symbol": "DCE.m2601",
                "strategy": "ma_strategy",
                "status": "success",
                "start_date": "2026-01-01",
                "end_date": "2026-01-02",
                "initial_capital": 100000.0,
                "end_balance": 112000.0,
                "total_return": 0.12,
                "total_trades": 1,
                "params": [{"name": "sma_short", "value": 5}],
                "daily": [{"date": "2026-01-02", "equity": 112000.0, "daily_return": 0.12}],
            }
        ],
        "equity.json": {
            "DCE.m2601": {
                "dates": ["2026-01-02"],
                "equity": [112000.0],
                "drawdown": [0.0],
            }
        },
        "trades.json": {
            "DCE.m2601": [
                {
                    "datetime": "2026-01-02T10:00:00",
                    "symbol": "DCE.m2601",
                    "direction": "long",
                    "offset": "open",
                }
            ]
        },
        "optuna.json": {
            "study_name": "fixture-study",
            "trial_count": 1,
            "best_value": 1.0,
            "best_params": [{"name": "sma_short", "value": 5}],
            "optimization_history": {"series": [{"name": "value", "data": [[1, 1.0]]}]},
        },
        "logs.json": "fixture log",
        "clearing_diagnostics.json": [
            {
                "backtest_id": 1,
                "symbol": "DCE.m2601",
                "trade_count": 2,
                "total_net_pnl": 250.0,
                "cost_adjusted_win_rate": 0.5,
                "cost_adjusted_payoff_ratio": 2.0,
                "breakeven_win_rate": 0.33,
                "win_rate_margin": 0.17,
                "max_single_loss": -100.0,
                "max_consecutive_losses": 1,
                "exit_reason_distribution": {"take_profit": 1, "strict_failure": 1},
                "raw_account_r_multiples": [2.0, -1.0],
                "mae_values": [4.0, 10.0],
                "mfe_values": [12.0, 2.0],
            }
        ],
    }
    for name, payload in artifacts.items():
        (data_dir / name).write_text(json.dumps(payload), encoding="utf-8")

    nav_payload = [
        {
            "id": 1,
            "strategy": "ma_strategy",
            "engine": "vnpy",
            "symbols": 1,
            "status": "success",
            "created": "2026-01-01T00:00:00",
        }
    ]
    nav_path.write_text(json.dumps(nav_payload), encoding="utf-8")

    assert validate_run_artifacts(run_dir, nav_path=nav_path) == []
