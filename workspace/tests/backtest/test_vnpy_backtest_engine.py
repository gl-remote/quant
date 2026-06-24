"""测试 backtest/vnpy_backtest_engine.py — 爆仓统计重算"""

import pandas as pd
from backtest.vnpy_backtest_engine import _override_blown_up_stats


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
