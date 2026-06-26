"""测试 backtest/vnpy_backtest_engine.py — 爆仓统计重算"""

from types import SimpleNamespace

import pandas as pd
import pytest
from backtest.vnpy_backtest_engine import VnpyBacktestEngine, _override_blown_up_stats


def _make_daily(net_pnls: list[float]) -> pd.DataFrame:
    """构造 calculate_result() 形态的逐日 DataFrame"""
    n = len(net_pnls)
    return pd.DataFrame(
        {
            "net_pnl": net_pnls,
            "commission": [100.0] * n,
            "slippage": [50.0] * n,
            "turnover": [1_000_000.0] * n,
            "trade_count": [10] * n,
        }
    )


def test_parse_trades_records_commission_on_each_fill():
    engine = SimpleNamespace(
        trades={
            "BACKTESTING.1": SimpleNamespace(
                datetime=pd.Timestamp("2024-01-01 09:00").to_pydatetime(),
                direction=SimpleNamespace(value="多"),
                offset=SimpleNamespace(value="开"),
                price=100.0,
                volume=2.0,
            ),
            "BACKTESTING.2": SimpleNamespace(
                datetime=pd.Timestamp("2024-01-01 10:00").to_pydatetime(),
                direction=SimpleNamespace(value="空"),
                offset=SimpleNamespace(value="平"),
                price=110.0,
                volume=2.0,
            ),
        }
    )

    trades = VnpyBacktestEngine._parse_trades(None, engine, "DCE.m2509", rate=0.001, size=10)

    assert trades[0]["commission"] == pytest.approx(2.0)
    assert trades[1]["commission"] == pytest.approx(2.2)
    assert sum(t["commission"] for t in trades) == pytest.approx(4.2)


def test_blown_up_balance_crosses_zero_yields_negative_sharpe():
    """回归：账户净值穿越零点进入负值时，Sharpe 必须为负

    旧实现用几何收益 log(balance_t / balance_{t-1})，在 balance 由正穿越到负
    （负÷负=正 ratio）时算出错误的正收益，导致巨亏爆仓账户得到正 Sharpe，
    前端据此误标绿色。改用以初始资金为基数的算术日收益后符号恒正确。
    """
    capital = 100_000.0
    # 持续巨亏：累计净值 7w -> 3w -> -1w -> -4.25w（穿越 0）
    daily = _make_daily([-30000, -40000, -40000, -32525])

    stats: dict = {}
    _override_blown_up_stats(stats, daily, capital)

    assert stats["end_balance"] < 0, "爆仓终值应为负"
    assert stats["total_return"] < 0, "巨亏总收益应为负"
    assert stats["sharpe_ratio"] < 0, "巨亏爆仓的 Sharpe 必须为负"


def test_blown_up_partial_loss_keeps_positive_balance():
    """对照：亏损但未穿越零点时，统计字段被正常覆盖且终值仍为正"""
    capital = 100_000.0
    daily = _make_daily([-10000, -5000, -8000, -7000])

    stats: dict = {}
    _override_blown_up_stats(stats, daily, capital)

    assert stats["end_balance"] == 70_000.0
    assert stats["total_return"] < 0
    assert stats["loss_days"] == 4


def test_all_profit_sequence_keeps_positive_signs_and_day_counts():
    capital = 100_000.0
    daily = _make_daily([10_000, 5_000, 8_000, 7_000])

    stats: dict = {}
    _override_blown_up_stats(stats, daily, capital)

    assert stats["end_balance"] == 130_000.0
    assert stats["total_return"] == pytest.approx(30.0)
    assert stats["annual_return"] > 0
    assert stats["profit_days"] == 4
    assert stats["loss_days"] == 0
    assert stats["max_drawdown"] == 0.0
    assert stats["max_ddpercent"] == 0.0
    assert stats["return_drawdown_ratio"] == 0.0


def test_all_loss_sequence_keeps_negative_signs_and_day_counts():
    capital = 100_000.0
    daily = _make_daily([-10_000, -5_000, -8_000, -7_000])

    stats: dict = {}
    _override_blown_up_stats(stats, daily, capital)

    assert stats["end_balance"] == 70_000.0
    assert stats["total_return"] == pytest.approx(-30.0)
    assert stats["annual_return"] < 0
    assert stats["profit_days"] == 0
    assert stats["loss_days"] == 4
    assert stats["max_drawdown"] < 0
    assert stats["max_ddpercent"] < 0
    assert stats["return_drawdown_ratio"] < 0


def test_cost_totals_are_reported_without_increasing_net_pnl():
    capital = 100_000.0
    low_cost = _make_daily([1_000, 1_000])
    high_cost = _make_daily([900, 900])
    high_cost["commission"] = [150.0, 150.0]
    high_cost["slippage"] = [100.0, 100.0]

    low_stats: dict = {}
    high_stats: dict = {}
    _override_blown_up_stats(low_stats, low_cost, capital)
    _override_blown_up_stats(high_stats, high_cost, capital)

    assert high_stats["total_commission"] > low_stats["total_commission"]
    assert high_stats["total_slippage"] > low_stats["total_slippage"]
    assert high_stats["total_net_pnl"] < low_stats["total_net_pnl"]
    assert high_stats["end_balance"] < low_stats["end_balance"]
    assert high_stats["total_return"] < low_stats["total_return"]


def test_empty_daily_does_not_create_synthetic_positive_stats():
    stats = {"end_balance": 0.0, "total_return": 0.0, "profit_days": 0}

    _override_blown_up_stats(stats, pd.DataFrame(), 100_000.0)

    assert stats == {"end_balance": 0.0, "total_return": 0.0, "profit_days": 0}


def test_daily_missing_required_columns_does_not_create_synthetic_positive_stats():
    stats = {"end_balance": 0.0, "total_return": 0.0, "profit_days": 0}

    _override_blown_up_stats(stats, pd.DataFrame({"net_pnl": [1_000.0]}), 100_000.0)

    assert stats == {"end_balance": 0.0, "total_return": 0.0, "profit_days": 0}
