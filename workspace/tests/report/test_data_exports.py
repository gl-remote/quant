"""report JSON artifact 导出回归测试。"""

from __future__ import annotations

import json

from config import ConfigManager
from data import DataManager
from data.store import DataStore
from report.builder.data_exports import run_data_exports
from tests.helpers.backtest_records import insert_full_backtest


def test_no_search_run_exports_empty_optuna_artifact(temp_db_path, tmp_path, monkeypatch):
    import data.output_paths as data_paths
    import report.output_paths as report_paths

    monkeypatch.setattr(data_paths, "project_data_root", lambda: tmp_path)
    monkeypatch.setattr(data_paths, "reports_root", lambda: tmp_path / "reports")
    monkeypatch.setattr(data_paths, "cache_root", lambda: tmp_path / "cache")
    monkeypatch.setattr(data_paths, "report_build_cache_dir", lambda: tmp_path / "cache" / "report_build")
    monkeypatch.setattr(report_paths, "reports_root", lambda: tmp_path / "reports")

    dm = DataManager(ConfigManager(env="backtest"))
    dm._store = DataStore(temp_db_path)
    run_id = dm.store.create_run("ma", "vnpy", 1)
    insert_full_backtest(dm.store)
    dm.store.finish_run(run_id)

    run_data_exports(str(tmp_path / "reports"), run_id, incremental=True, dm=dm)

    optuna_path = tmp_path / "reports" / "runs" / f"r{run_id}" / "data" / "optuna.json"
    payload = json.loads(optuna_path.read_text(encoding="utf-8"))

    assert payload == {
        "study_name": "",
        "trial_count": 0,
        "best_value": None,
        "best_params": [],
        "optimization_history": None,
        "param_importances": None,
        "parallel_coordinate": None,
        "contours": None,
    }


def test_run_exports_clearing_diagnostics_artifact(temp_db_path, tmp_path, monkeypatch):
    import data.output_paths as data_paths
    import report.output_paths as report_paths

    monkeypatch.setattr(data_paths, "project_data_root", lambda: tmp_path)
    monkeypatch.setattr(data_paths, "reports_root", lambda: tmp_path / "reports")
    monkeypatch.setattr(data_paths, "cache_root", lambda: tmp_path / "cache")
    monkeypatch.setattr(data_paths, "report_build_cache_dir", lambda: tmp_path / "cache" / "report_build")
    monkeypatch.setattr(report_paths, "reports_root", lambda: tmp_path / "reports")

    from data.models import Backtest

    dm = DataManager(ConfigManager(env="backtest"))
    dm._store = DataStore(temp_db_path)
    run_id = dm.store.create_run("ma", "vnpy", 1)
    bt_id = insert_full_backtest(dm.store)
    Backtest.update(run=run_id).where(Backtest.id == bt_id).execute()
    dm.store.replace_clearing_outputs(
        bt_id,
        [
            {
                "backtest_id": bt_id,
                "run_id": run_id,
                "symbol": "DCE.m2509",
                "direction": "long",
                "volume": 1.0,
                "open_time": "2024-01-15 09:00:00",
                "close_time": "2024-01-15 10:00:00",
                "open_price": 100.0,
                "close_price": 110.0,
                "contract_multiplier": 10.0,
                "gross_pnl": 100.0,
                "commission": 0.0,
                "slippage_cost": 0.0,
                "net_pnl": 100.0,
                "exit_reason": "take_profit",
                "mae": 4.0,
                "mfe": 12.0,
                "diagnostics_json": None,
            }
        ],
        [],
        [],
        {},
    )
    dm.store.finish_run(run_id)

    run_data_exports(str(tmp_path / "reports"), run_id, incremental=True, dm=dm)

    diag_path = tmp_path / "reports" / "runs" / f"r{run_id}" / "data" / "clearing_diagnostics.json"
    payload = json.loads(diag_path.read_text(encoding="utf-8"))

    assert len(payload) == 1
    assert payload[0]["symbol"] == "DCE.m2509"
    assert payload[0]["trade_count"] == 1
    assert payload[0]["exit_reason_distribution"] == {"take_profit": 1}
    assert payload[0]["cost_adjusted_win_rate"] == 1.0
