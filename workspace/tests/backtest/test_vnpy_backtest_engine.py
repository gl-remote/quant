"""测试 backtest/vnpy_backtest_engine.py — 爆仓统计重算"""

import json
from types import SimpleNamespace

import pandas as pd
import pytest
from backtest.data_utils import append_synthetic_liquidation_bar
from backtest.vnpy_backtest_engine import VnpyBacktestEngine, _override_blown_up_stats


def _trade(dt: str, direction: str, offset: str, price: float, volume: float):
    return SimpleNamespace(
        datetime=pd.Timestamp(dt).to_pydatetime(),
        direction=SimpleNamespace(value=direction),
        offset=SimpleNamespace(value=offset),
        price=price,
        volume=volume,
    )


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


def test_append_synthetic_liquidation_bar_uses_last_close_price():
    from vnpy.trader.constant import Exchange, Interval
    from vnpy.trader.object import BarData

    bars = [
        BarData(
            symbol="m2509",
            exchange=Exchange.DCE,
            datetime=pd.Timestamp("2024-01-01 09:00").to_pydatetime(),
            interval=Interval.MINUTE,
            open_price=100.0,
            high_price=105.0,
            low_price=99.0,
            close_price=103.0,
            volume=10,
            gateway_name="CSV",
        )
    ]

    result = append_synthetic_liquidation_bar(bars)

    assert len(result) == 2
    assert result[0] is bars[0]
    assert result[1].datetime == pd.Timestamp("2024-01-01 09:01").to_pydatetime()
    assert result[1].open_price == pytest.approx(103.0)
    assert result[1].high_price == pytest.approx(103.0)
    assert result[1].low_price == pytest.approx(103.0)
    assert result[1].close_price == pytest.approx(103.0)
    assert result[1].volume == 0
    assert result[1].is_synthetic_liquidation is True  # type: ignore[attr-defined]


def test_parse_trades_records_raw_fills_without_commission():
    decision_payload = {
        "schema_version": 1,
        "source": "vnpy_backtest_bridge",
        "event_type": "system_forced_flat",
        "diagnostics": {
            "strategy": {},
            "aspects": {},
            "alpha": {},
            "risk": {},
            "execution": {
                "trigger": "backtest_end",
                "policy": "synthetic_liquidation_bar",
            },
        },
    }
    engine = SimpleNamespace(
        trades={
            "BACKTESTING.1": SimpleNamespace(
                datetime=pd.Timestamp("2024-01-01 09:00").to_pydatetime(),
                direction=SimpleNamespace(value="多"),
                offset=SimpleNamespace(value="开"),
                price=100.0,
                volume=2.0,
                decision_payload_json=json.dumps(decision_payload, ensure_ascii=False),
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

    trades = VnpyBacktestEngine._parse_trades(None, engine, "DCE.m2509")

    assert trades[0]["price"] == pytest.approx(100.0)
    assert trades[1]["price"] == pytest.approx(110.0)
    assert trades[0]["commission"] == 0.0
    assert trades[1]["commission"] == 0.0
    assert json.loads(trades[0]["decision_payload_json"])["diagnostics"]["execution"] == {
        "trigger": "backtest_end",
        "policy": "synthetic_liquidation_bar",
    }


def test_calculate_trade_stats_ignores_open_and_flat_trades_for_loss_streak():
    stats: dict = {}
    trades = [
        {"offset": "open", "pnl": 0.0},
        {"offset": "close", "pnl": -10.0},
        {"offset": "close", "pnl": 0.0},
        {"offset": "open", "pnl": 0.0},
        {"offset": "close", "pnl": -20.0},
        {"offset": "close", "pnl": -30.0},
        {"offset": "close", "pnl": 40.0},
    ]

    VnpyBacktestEngine._calculate_trade_stats(stats, trades)

    assert stats["loss_trades"] == 3
    assert stats["win_trades"] == 1
    assert stats["max_consecutive_loss"] == 2
    assert stats["max_consecutive_win"] == 1


def test_parse_trades_keeps_close_fill_as_raw_record(caplog):
    engine = SimpleNamespace(
        trades={
            "BACKTESTING.1": _trade("2024-01-01 09:00", "多", "开", 100.0, 2.0),
            "BACKTESTING.2": _trade("2024-01-01 10:00", "空", "平", 110.0, 2.0),
        }
    )

    trades = VnpyBacktestEngine._parse_trades(None, engine, "DCE.m2509")

    assert "平仓有余量未配对" not in caplog.text
    assert trades[1]["price"] == 110.0
    assert trades[1]["open_price"] == 110.0
    assert trades[1]["pnl"] == 0.0


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


def test_rgr_ratio_sanitized_when_no_drawdown():
    """vnpy calc_rgr_ratio 在 max_ddpercent==0 时会返回上万量级的假值，
    _override_blown_up_stats 应将其归零，与 return_drawdown_ratio 行为一致。"""
    capital = 100_000.0
    daily = _make_daily([10_000, 5_000, 8_000, 7_000])
    stats: dict = {"rgr_ratio": 74240.66}  # 模拟 vnpy 返回的爆炸值

    _override_blown_up_stats(stats, daily, capital)

    assert stats["max_ddpercent"] == 0.0
    assert stats["rgr_ratio"] == 0.0


def test_sanitize_no_drawdown_ratios_zeroes_both_ratios():
    """无回撤路径下 rgr_ratio 与 return_drawdown_ratio 都要归零。"""
    from backtest.vnpy_backtest_engine import _sanitize_no_drawdown_ratios

    stats: dict = {
        "max_ddpercent": 0.0,
        "rgr_ratio": 173634.14,  # 现实 sweep 中观察到的爆炸值
        "return_drawdown_ratio": 999.0,
    }
    _sanitize_no_drawdown_ratios(stats)
    assert stats["rgr_ratio"] == 0.0
    assert stats["return_drawdown_ratio"] == 0.0

    stats = {"max_ddpercent": None, "rgr_ratio": 5.0, "return_drawdown_ratio": 3.0}
    _sanitize_no_drawdown_ratios(stats)
    assert stats["rgr_ratio"] == 0.0
    assert stats["return_drawdown_ratio"] == 0.0

    # 有回撤时不动
    stats = {"max_ddpercent": -5.5, "rgr_ratio": 1.8, "return_drawdown_ratio": 2.1}
    _sanitize_no_drawdown_ratios(stats)
    assert stats["rgr_ratio"] == 1.8
    assert stats["return_drawdown_ratio"] == 2.1


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
