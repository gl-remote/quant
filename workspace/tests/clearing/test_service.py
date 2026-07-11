"""Clearing service 单元测试。"""

from __future__ import annotations

import json
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
    decision_payload_json: str | None = None,
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
        decision_payload_json=decision_payload_json,
    )


def _payload(**diagnostics: dict[str, object]) -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "source": "strategy",
            "event_type": "strategy_signal",
            "diagnostics": {
                "strategy": {},
                "aspects": {},
                "alpha": diagnostics.get("alpha", {}),
                "risk": diagnostics.get("risk", {}),
                "execution": diagnostics.get("execution", {}),
            },
        },
        ensure_ascii=False,
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
    # 新成本模型: m 品种 commission=1.51(交易所基准) ×(1+broker_markup=2.0)=4.53/手
    # 该行(开2手+平2手)= 4.53×2×2 = 18.12; net = 200(gross) − 18.12 − 20(slip) = 161.88
    assert rows[0]["commission"] == pytest.approx(18.12)
    assert rows[0]["slippage_cost"] == pytest.approx(20.0)
    assert rows[0]["net_pnl"] == pytest.approx(161.88)
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


def test_clearing_transparently_carries_diagnostics_and_derives_excursion(tmp_path: Path) -> None:
    bars_path = tmp_path / "bars.csv"
    pd.DataFrame(
        {
            "datetime": ["2024-01-01 09:00:00", "2024-01-01 09:30:00", "2024-01-01 10:00:00"],
            "open": [100.0, 103.0, 108.0],
            "high": [101.0, 112.0, 110.0],
            "low": [96.0, 102.0, 107.0],
            "close": [100.0, 108.0, 110.0],
        }
    ).to_csv(bars_path, index=False)
    dm = FakeDataManager(
        [
            _trade(
                1,
                "2024-01-01 09:00:00",
                "long",
                "open",
                100.0,
                1.0,
                reason="entry",
                decision_payload_json=_payload(
                    alpha={"direction_hypothesis": "long", "strict_failure_boundary": 95.0},
                    risk={"strict_failure_distance": 5.0, "raw_account_r_multiple": 2.0},
                ),
            ),
            _trade(
                2,
                "2024-01-01 10:00:00",
                "short",
                "close",
                110.0,
                1.0,
                reason="exit",
                decision_payload_json=_payload(execution={"exit_reason": "take_profit"}),
            ),
        ]
    )

    BacktestClearingService(dm).clear_backtest(_backtest(str(bars_path)))

    _, rows, _, _, _ = dm.replaced[0]
    row = rows[0]
    assert row["exit_reason"] == "take_profit"
    # long 持仓：MFE 向上（112-100），MAE 向下（100-96）
    assert row["mfe"] == pytest.approx(12.0)
    assert row["mae"] == pytest.approx(4.0)
    assert row["holding_bars"] == 3
    diagnostics = json.loads(row["diagnostics_json"])
    assert diagnostics["alpha"]["strict_failure_boundary"] == 95.0
    assert diagnostics["risk"]["raw_account_r_multiple"] == 2.0
    assert diagnostics["execution"]["exit_reason"] == "take_profit"


def test_clearing_warns_when_recommended_fields_missing() -> None:
    from loguru import logger

    dm = FakeDataManager(
        [
            _trade(
                1,
                "2024-01-01 09:00:00",
                "long",
                "open",
                100.0,
                1.0,
                decision_payload_json=_payload(alpha={"placeholder": True}, risk={"placeholder": True}),
            ),
            _trade(2, "2024-01-01 10:00:00", "short", "close", 110.0, 1.0),
        ]
    )

    messages: list[str] = []
    sink_id = logger.add(lambda m: messages.append(m), level="WARNING")
    try:
        BacktestClearingService(dm).clear_backtest(_backtest())
    finally:
        logger.remove(sink_id)

    warnings = "".join(messages)
    assert "缺 alpha 诊断" in warnings
    assert "缺 risk 诊断" in warnings
    _, rows, _, _, _ = dm.replaced[0]
    # 占位被视为非真实填充，不写入 diagnostics_json
    assert rows[0]["diagnostics_json"] is None
    assert rows[0]["exit_reason"] is None


def test_clearing_derives_short_excursion_direction(tmp_path: Path) -> None:
    bars_path = tmp_path / "bars.csv"
    pd.DataFrame(
        {
            "datetime": ["2024-01-01 09:00:00", "2024-01-01 09:30:00", "2024-01-01 10:00:00"],
            "open": [100.0, 95.0, 92.0],
            "high": [104.0, 96.0, 93.0],
            "low": [99.0, 90.0, 88.0],
            "close": [100.0, 92.0, 90.0],
        }
    ).to_csv(bars_path, index=False)
    dm = FakeDataManager(
        [
            _trade(1, "2024-01-01 09:00:00", "short", "open", 100.0, 1.0, reason="entry"),
            _trade(2, "2024-01-01 10:00:00", "long", "close", 90.0, 1.0, reason="exit"),
        ]
    )

    BacktestClearingService(dm).clear_backtest(_backtest(str(bars_path)))

    _, rows, _, _, _ = dm.replaced[0]
    row = rows[0]
    # short 持仓：有利方向向下（100-88=12），不利方向向上（104-100=4）
    assert row["mfe"] == pytest.approx(12.0)
    assert row["mae"] == pytest.approx(4.0)
    assert row["holding_bars"] == 3


def test_clearing_forced_close_sets_forced_exit_reason(tmp_path: Path) -> None:
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
    # 只有开仓、无平仓 → 在回测结束时被强平
    dm = FakeDataManager(
        [
            _trade(1, "2024-01-01 09:00:00", "long", "open", 100.0, 1.0),
        ]
    )

    BacktestClearingService(dm).clear_backtest(_backtest(str(bars_path)))

    _, rows, _, _, _ = dm.replaced[0]
    assert len(rows) == 1
    assert rows[0]["is_forced_close"] is True
    assert rows[0]["exit_reason"] == "forced_close"


def test_clearing_ignores_invalid_decision_payload_json(tmp_path: Path) -> None:
    dm = FakeDataManager(
        [
            _trade(
                1,
                "2024-01-01 09:00:00",
                "long",
                "open",
                100.0,
                1.0,
                decision_payload_json="{not-valid-json",
            ),
            _trade(2, "2024-01-01 10:00:00", "short", "close", 110.0, 1.0),
        ]
    )

    BacktestClearingService(dm).clear_backtest(_backtest())

    _, rows, _, _, _ = dm.replaced[0]
    # 无效 JSON 解析为 None，诊断为空，不应抛错
    assert rows[0]["diagnostics_json"] is None


def test_clearing_warns_missing_recommended_when_alpha_real_but_incomplete() -> None:
    from loguru import logger

    dm = FakeDataManager(
        [
            _trade(
                1,
                "2024-01-01 09:00:00",
                "long",
                "open",
                100.0,
                1.0,
                decision_payload_json=_payload(
                    alpha={"direction_hypothesis": "long"},  # 真实填充但缺推荐字段
                    risk={"account_equity": 100000.0},
                ),
            ),
            _trade(2, "2024-01-01 10:00:00", "short", "close", 110.0, 1.0),
        ]
    )

    messages: list[str] = []
    sink_id = logger.add(lambda m: messages.append(m), level="WARNING")
    try:
        BacktestClearingService(dm).clear_backtest(_backtest())
    finally:
        logger.remove(sink_id)

    warnings = "".join(messages)
    assert "alpha 诊断缺推荐字段" in warnings
    assert "risk 诊断缺推荐字段" in warnings
    _, rows, _, _, _ = dm.replaced[0]
    # 真实填充仍透传
    diagnostics = json.loads(rows[0]["diagnostics_json"])
    assert diagnostics["alpha"]["direction_hypothesis"] == "long"
