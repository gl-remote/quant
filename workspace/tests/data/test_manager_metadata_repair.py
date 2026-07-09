from __future__ import annotations

from pathlib import Path

import pandas as pd
import tomli_w
from config import ConfigManager
from data import DataManager


def test_load_kline_repairs_missing_metadata_from_csv(tmp_path: Path) -> None:
    csv_dir = tmp_path / "csv"
    csv_dir.mkdir()
    db_path = tmp_path / "quant.db"
    symbol = "DCE.m2509"
    csv_path = csv_dir / f"{symbol}.tqsdk.5m.csv"
    pd.DataFrame(
        {
            "datetime": pd.date_range("2024-01-01", periods=3, freq="5min"),
            "open": [1.0, 2.0, 3.0],
            "high": [1.5, 2.5, 3.5],
            "low": [0.5, 1.5, 2.5],
            "close": [1.2, 2.2, 3.2],
            "volume": [10, 20, 30],
        }
    ).to_csv(csv_path, index=False)

    config_path = tmp_path / "conf.toml"
    config_path.write_bytes(
        tomli_w.dumps(
            {
                "data": {
                    "environment": "test",
                    "database_path": str(db_path),
                    "export_dir": str(csv_dir),
                    "filename_template": "{symbol}.{provider}.{interval}.csv",
                },
                "backtest": {
                    "provider": "tqsdk",
                    "interval": "5m",
                },
            }
        ).encode("utf-8")
    )

    dm = DataManager(ConfigManager(config_file=str(config_path)))
    loaded = dm.load_kline([symbol], interval="5m")

    assert loaded[0][0] == symbol
    assert loaded[0][2] == str(csv_path)
    meta = dm.store.get_metadata(symbol, provider="tqsdk", interval="5m")
    assert meta is not None
    assert meta["filepath"] == str(csv_path)
    assert meta["total_rows"] == 3
