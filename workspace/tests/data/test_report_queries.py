"""report_queries 结构诊断聚合测试。"""

from __future__ import annotations

import json
from datetime import datetime

from config import ConfigManager
from data import DataManager
from data.report_queries import build_clearing_diagnostics, build_exit_policy_diff
from data.store import DataStore
from tests.helpers.backtest_records import insert_full_backtest


def _clearing_row(
    backtest_id: int,
    net_pnl: float,
    exit_reason: str,
    *,
    raw_account_r: float | None = None,
    mae: float | None = None,
    mfe: float | None = None,
) -> dict[str, object]:
    diagnostics: dict[str, object] = {}
    if raw_account_r is not None:
        diagnostics["risk"] = {"raw_account_r_multiple": raw_account_r}
    return {
        "backtest_id": backtest_id,
        "run_id": None,
        "symbol": "DCE.m2509",
        "direction": "long",
        "volume": 1.0,
        "open_time": datetime(2024, 1, 1, 9, 0, 0),
        "close_time": datetime(2024, 1, 1, 10, 0, 0),
        "open_price": 100.0,
        "close_price": 110.0,
        "contract_multiplier": 10.0,
        "gross_pnl": net_pnl,
        "commission": 0.0,
        "slippage_cost": 0.0,
        "net_pnl": net_pnl,
        "exit_reason": exit_reason,
        "mae": mae,
        "mfe": mfe,
        "diagnostics_json": json.dumps(diagnostics, ensure_ascii=False) if diagnostics else None,
        "created_at": datetime.now(),
    }


def _setup(temp_db_path: str) -> tuple[DataManager, int]:
    dm = DataManager(ConfigManager(env="backtest"))
    dm._store = DataStore(temp_db_path)
    bt_id = insert_full_backtest(dm.store)
    return dm, bt_id


def test_build_clearing_diagnostics_aggregates_cost_adjusted_metrics(temp_db_path) -> None:
    dm, bt_id = _setup(temp_db_path)
    dm.store.replace_clearing_outputs(
        bt_id,
        [
            _clearing_row(bt_id, 200.0, "take_profit", raw_account_r=2.0, mae=4.0, mfe=12.0),
            _clearing_row(bt_id, -100.0, "strict_failure", raw_account_r=-1.0, mae=10.0, mfe=2.0),
            _clearing_row(bt_id, 150.0, "take_profit", raw_account_r=1.5),
        ],
        [],
        [],
        {},
    )

    result = build_clearing_diagnostics(bt_id)

    assert result["trade_count"] == 3
    assert result["cost_adjusted_win_rate"] == 2 / 3
    assert result["total_net_pnl"] == 250.0
    assert result["max_single_loss"] == -100.0
    assert result["exit_reason_distribution"] == {"take_profit": 2, "strict_failure": 1}
    assert result["raw_account_r_multiples"] == [2.0, -1.0, 1.5]
    assert result["mae_values"] == [4.0, 10.0]
    # 盈亏平衡胜率 = avg_loss / (avg_win + avg_loss) = 100 / (175 + 100)
    assert result["breakeven_win_rate"] == 100.0 / 275.0


def test_build_clearing_diagnostics_empty_when_no_clearings(temp_db_path) -> None:
    dm, bt_id = _setup(temp_db_path)
    result = build_clearing_diagnostics(bt_id)
    assert result == {"backtest_id": bt_id, "trade_count": 0}


def test_build_exit_policy_diff_reports_deltas(temp_db_path) -> None:
    dm, bt_a = _setup(temp_db_path)
    bt_b = insert_full_backtest(dm.store, symbol="DCE.m2601")
    dm.store.replace_clearing_outputs(
        bt_a,
        [_clearing_row(bt_a, 100.0, "strict_failure"), _clearing_row(bt_a, -50.0, "strict_failure")],
        [],
        [],
        {},
    )
    dm.store.replace_clearing_outputs(
        bt_b,
        [_clearing_row(bt_b, 80.0, "take_profit"), _clearing_row(bt_b, 60.0, "take_profit")],
        [],
        [],
        {},
    )

    diff = build_exit_policy_diff(bt_a, bt_b)

    assert diff["backtest_id_a"] == bt_a
    assert diff["backtest_id_b"] == bt_b
    delta = diff["delta"]
    assert isinstance(delta, dict)
    # b 全胜，胜率从 0.5 提升到 1.0
    assert delta["cost_adjusted_win_rate"] == 0.5


def test_build_clearing_diagnostics_for_run_aggregates_each_symbol(temp_db_path) -> None:
    from data.report_queries import build_clearing_diagnostics_for_run

    dm = DataManager(ConfigManager(env="backtest"))
    dm._store = DataStore(temp_db_path)
    run_id = dm.store.create_run("ma", "vnpy", 2)
    bt_a = insert_full_backtest(dm.store, symbol="DCE.m2509")
    bt_b = insert_full_backtest(dm.store, symbol="DCE.m2601")
    # 绑定到同一 run
    from data.models import Backtest

    Backtest.update(run=run_id).where(Backtest.id.in_([bt_a, bt_b])).execute()
    dm.store.replace_clearing_outputs(bt_a, [_clearing_row(bt_a, 100.0, "take_profit")], [], [], {})
    dm.store.replace_clearing_outputs(bt_b, [_clearing_row(bt_b, -50.0, "strict_failure")], [], [], {})
    dm.store.finish_run(run_id)

    result = build_clearing_diagnostics_for_run(dm.store, run_id)

    by_symbol = {r["symbol"]: r for r in result}
    assert set(by_symbol) == {"DCE.m2509", "DCE.m2601"}
    assert by_symbol["DCE.m2509"]["trade_count"] == 1
    assert by_symbol["DCE.m2509"]["cost_adjusted_win_rate"] == 1.0
    assert by_symbol["DCE.m2601"]["cost_adjusted_win_rate"] == 0.0


def test_manager_exposes_clearing_diagnostics_and_diff(temp_db_path) -> None:
    dm = DataManager(ConfigManager(env="backtest"))
    dm._store = DataStore(temp_db_path)
    run_id = dm.store.create_run("ma", "vnpy", 1)
    bt_id = insert_full_backtest(dm.store)
    from data.models import Backtest

    Backtest.update(run=run_id).where(Backtest.id == bt_id).execute()
    dm.store.replace_clearing_outputs(
        bt_id,
        [_clearing_row(bt_id, 120.0, "take_profit"), _clearing_row(bt_id, -40.0, "strict_failure")],
        [],
        [],
        {},
    )
    dm.store.finish_run(run_id)

    run_diag = dm.get_clearing_diagnostics_for_run(run_id)
    assert len(run_diag) == 1
    assert run_diag[0]["trade_count"] == 2

    diff = dm.get_exit_policy_diff(bt_id, bt_id)
    # 与自身对比，所有 delta 为 0
    delta = diff["delta"]
    assert isinstance(delta, dict)
    assert all(v == 0 for v in delta.values())
