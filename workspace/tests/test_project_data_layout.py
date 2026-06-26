"""project_data 目录布局回归测试。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pandas as pd


def test_project_data_path_layout() -> None:
    from data.output_paths import (
        coverage_dir,
        database_environment_dir,
        database_path,
        database_root,
        datafeed_cache_dir,
        kline_json_cache_dir,
        market_csv_dir,
        profiles_dir,
        project_data_root,
        report_build_cache_dir,
        reports_root,
    )
    from report.output_paths import logs_json_path, nav_json_path, run_data_dir, run_log_path, workers_dir

    root = project_data_root()
    assert root.name == "project_data"
    assert market_csv_dir() == root / "market_data" / "csv"
    assert database_root() == root / "database"
    assert database_environment_dir("backtest") == root / "database" / "backtest"
    assert database_path("backtest") == root / "database" / "backtest" / "quant.db"
    assert database_path("test") == root / "database" / "test" / "quant.db"
    assert database_path("live") == root / "database" / "live" / "quant.db"
    assert database_path("backtest") != root / "database" / "quant_shared.db"
    assert reports_root() == root / "reports"
    assert nav_json_path() == root / "reports" / "data" / "nav.json"
    assert run_data_dir(7) == root / "reports" / "runs" / "r7" / "data"
    assert logs_json_path(7) == root / "reports" / "runs" / "r7" / "data" / "logs.json"
    assert run_log_path(7) == root / "logs" / "runs" / "r7" / "run.log"
    assert workers_dir(7) == root / "logs" / "runs" / "r7" / "workers"
    assert report_build_cache_dir() == root / "cache" / "report_build"
    assert kline_json_cache_dir() == root / "cache" / "kline_json"
    assert datafeed_cache_dir() == root / "cache" / "datafeed"
    assert profiles_dir() == root / "profiles"
    assert coverage_dir() == root / "coverage"


def test_default_config_uses_project_data() -> None:
    from config.manager import ProjectConfig
    from data.output_paths import database_path, market_csv_dir, project_data_root

    ProjectConfig.reset()
    cfg = ProjectConfig.load(env="backtest")
    assert Path(cfg.data.base_dir) == project_data_root()
    assert Path(cfg.data.export_dir) == market_csv_dir()
    assert cfg.data.environment == "backtest"
    assert Path(cfg.data.database_path) == database_path("backtest")


def test_entry_html_keeps_frontend_data_keys(tmp_path: Path) -> None:
    from report.builder.entry_html import _build_preload_script

    (tmp_path / "data").mkdir(parents=True)
    (tmp_path / "data" / "nav.json").write_text(json.dumps([{"id": 1}]), encoding="utf-8")
    run_data = tmp_path / "runs" / "r1" / "data"
    run_data.mkdir(parents=True)
    (run_data / "run.json").write_text(json.dumps({"id": 1}), encoding="utf-8")

    script = _build_preload_script(str(tmp_path))
    assert '"data/nav.json"' in script
    assert '"r1/data/run.json"' in script


def test_data_manager_load_kline_uses_export_metadata(tmp_path: Path) -> None:
    from config import ConfigManager
    from data.manager import DataManager

    csv_path = tmp_path / "DCE.m2601.tqsdk.5m.csv"
    pd.DataFrame(
        [
            {
                "datetime": "2026-01-01 09:00:00",
                "open": 1.0,
                "high": 2.0,
                "low": 0.5,
                "close": 1.5,
                "volume": 10,
            }
        ]
    ).to_csv(csv_path, index=False)

    dm = DataManager(ConfigManager(env="backtest"))
    dm._store = SimpleNamespace(get_metadata=lambda symbol, provider, interval: {"filepath": str(csv_path)})
    dm._get_default_interval = lambda: "5m"  # type: ignore[method-assign]
    dm._get_default_provider = lambda: "tqsdk"  # type: ignore[method-assign]

    rows = dm.load_kline(["DCE.m2601"])
    assert rows[0][0] == "DCE.m2601"
    assert rows[0][2] == str(csv_path)


def test_no_old_path_strings_in_report_json(tmp_path: Path) -> None:
    report_root = tmp_path / "reports"
    data_dir = report_root / "runs" / "r1" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "kline_DCE.m2601.5m.json").write_text(
        json.dumps({"symbol": "DCE.m2601", "csv_source": "project_data/market_data/csv/DCE.m2601.csv"}),
        encoding="utf-8",
    )

    old_tokens = [".quant_shared_data", "output/r", "output/data/nav.json"]
    for artifact in report_root.rglob("*.json"):
        content = artifact.read_text(encoding="utf-8")
        assert not any(token in content for token in old_tokens)


def test_db_old_path_scan_detects_text_fields(tmp_path: Path) -> None:
    db_path = tmp_path / "scan.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, path TEXT, payload TEXT)")
    conn.execute("INSERT INTO sample(path, payload) VALUES (?, ?)", ("project_data/market_data/csv/a.csv", "{}"))
    conn.commit()

    rows = list(_scan_db_for_old_paths(conn, [".quant_shared_data", "output/"]))
    conn.close()
    assert rows == []


def _scan_db_for_old_paths(conn: sqlite3.Connection, tokens: list[str]) -> list[tuple[str, str, str]]:
    findings: list[tuple[str, str, str]] = []
    tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    for table in tables:
        columns = [row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')]
        for column in columns:
            try:
                rows = conn.execute(f'SELECT "{column}" FROM "{table}" WHERE "{column}" IS NOT NULL').fetchall()
            except sqlite3.Error:
                continue
            for (value,) in rows:
                if isinstance(value, str) and any(token in value for token in tokens):
                    findings.append((table, column, value))
    return findings
