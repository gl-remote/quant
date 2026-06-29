"""Clearing service 单元测试。"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pandas as pd
import pytest
from clearing.service import BacktestClearingService
from data.models import TradeRecord


class FakeDataManager:
    backtests: ClassVar[list[dict[str, object]]] = []

    def __init__(self, trades: list[TradeRecord]) -> None:
        self.trades = trades
        self.replaced: list[
            tuple[int, list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], dict[str, object]]
        ] = []

    def get_backtests_for_clearing(self, run_id: int) -> list[dict[str, object]]:
        return [bt for bt in self.backtests if bt.get("run") == run_id]

    def query_trades(self, backtest_id: int) -> list[TradeRecord]:
        return self.trades

    def replace_clearing_outputs(
        self,
        backtest_id: int,
        clearing_rows: list[dict[str, object]],
        account_ledger_rows: list[dict[str, object]],
        position_ledger_rows: list[dict[str, object]],
        summary_fields: dict[str, object],
    ) -> None:
        self.replaced.append((backtest_id, clearing_rows, account_ledger_rows, position_ledger_rows, summary_fields))


def _trade(
    trade_id: int,
    dt: str,
    direction: str,
    offset: str,
    price: float,
    quantity: float,
    reason: str = "",
) -> TradeRecord:
    return TradeRecord(
        id=trade_id,
        backtest_id=1,
        datetime=dt,
        symbol="DCE.m2601",
        direction=direction,
        offset=offset,
        price=price,
        open_price=price,
        close_price=price,
        quantity=quantity,
        reason=reason,
    )


def _backtest(data_src: str | None = None) -> dict[str, object]:
    return {
        "id": 1,
        "run": 10,
        "symbol": "DCE.m2601",
        "initial_capital": 100_000.0,
        "contract_size": 10,
        "price_tick": 1.0,
        "data_src": data_src,
    }


def test_clear_backtest_pairs_fifo_and_updates_summary() -> None:
    dm = FakeDataManager(
        [
            _trade(1, "2024-01-01 09:00:00", "long", "open", 100.0, 2.0, "entry-a"),
            _trade(2, "2024-01-01 09:05:00", "long", "open", 101.0, 1.0, "entry-b"),
            _trade(3, "2024-01-01 10:00:00", "short", "close", 110.0, 3.0, "exit"),
        ]
    )

    BacktestClearingService(dm).clear_backtest(_backtest())

    assert len(dm.replaced) == 1
    backtest_id, rows, account_rows, position_rows, summary = dm.replaced[0]
    assert backtest_id == 1
    assert len(rows) == 2
    assert account_rows[0]["event_type"] == "initial_balance"
    assert account_rows[-1]["equity"] == pytest.approx(summary["end_balance"])
    assert [row["event_type"] for row in position_rows] == [
        "open_fill",
        "open_fill",
        "close_fifo_consumption",
        "close_fifo_consumption",
    ]
    assert rows[0]["open_trade_id"] == 1
    assert rows[0]["close_trade_id"] == 3
    assert rows[0]["volume"] == 2.0
    assert rows[0]["gross_pnl"] == pytest.approx(200.0)
    assert rows[1]["open_trade_id"] == 2
    assert rows[1]["volume"] == 1.0
    assert rows[1]["gross_pnl"] == pytest.approx(90.0)
    assert summary["win_trades"] == 2
    assert summary["loss_trades"] == 0
    assert summary["total_net_pnl"] < 290.0
    assert summary["total_commission"] > 0.0
    assert summary["total_slippage"] > 0.0


def test_clear_backtest_handles_partial_close_and_forced_close(tmp_path: Path) -> None:
    bars_path = tmp_path / "bars.csv"
    pd.DataFrame(
        {
            "datetime": ["2024-01-01 09:00:00", "2024-01-01 15:00:00"],
            "open": [100.0, 105.0],
            "high": [101.0, 106.0],
            "low": [99.0, 104.0],
            "close": [100.0, 105.0],
        }
    ).to_csv(bars_path, index=False)
    dm = FakeDataManager(
        [
            _trade(1, "2024-01-01 09:00:00", "long", "open", 100.0, 3.0),
            _trade(2, "2024-01-01 10:00:00", "short", "close", 110.0, 1.0),
        ]
    )

    BacktestClearingService(dm).clear_backtest(_backtest(str(bars_path)))

    _, rows, _, position_rows, _ = dm.replaced[0]
    assert len(rows) == 2
    assert rows[0]["volume"] == 1.0
    assert rows[0]["is_forced_close"] is False
    assert rows[1]["volume"] == 2.0
    assert rows[1]["close_price"] == 105.0
    assert rows[1]["is_forced_close"] is True
    assert rows[1]["forced_close_reason"] == "forced_close_at_backtest_end"
    assert position_rows[-1]["event_type"] == "forced_close_fifo_consumption"
    assert position_rows[-1]["position_volume"] == 0.0


def test_clear_run_uses_backtests_from_data_manager() -> None:
    dm = FakeDataManager([_trade(1, "2024-01-01 09:00:00", "long", "open", 100.0, 1.0)])
    dm.backtests = [_backtest()]

    BacktestClearingService(dm).clear_run(10)

    assert len(dm.replaced) == 1
    assert dm.replaced[0][0] == 1
