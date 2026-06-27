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
