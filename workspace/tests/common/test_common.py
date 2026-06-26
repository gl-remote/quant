"""common/ 通用纯函数模块测试

覆盖:
    - common/metrics.py: 最大回撤、夏普比率
    - common/stats.py: 统计聚合、排序
    - common/formatting.py: 安全格式化
    - common/formulas.py: 当前仍被业务代码引用的量化公式
"""

import pytest
from common.formatting import ensure_float, format_float, format_pct, parse_percentage
from common.formulas import calculate_fifo_profit, position_size, profitable_ratio, total_return, win_rate
from common.metrics import calc_max_drawdown, calc_sharpe_ratio
from common.stats import compute_summary_stats, rank_by_key

# ═══════════════════════════════════════════════════════════
# common/metrics.py — 绩效指标
# ═══════════════════════════════════════════════════════════


class TestCalcMaxDrawdown:
    def test_empty_list(self):
        assert calc_max_drawdown([]) == 0.0

    def test_single_value(self):
        assert calc_max_drawdown([100.0]) == 0.0

    def test_increasing_no_drawdown(self):
        assert calc_max_drawdown([100.0, 105.0, 110.0, 120.0]) == 0.0

    def test_decreasing_full_drawdown(self):
        dd = calc_max_drawdown([100.0, 90.0, 80.0, 70.0])
        assert pytest.approx(dd) == 0.3

    def test_mixed_equity_curve(self):
        dd = calc_max_drawdown([100.0, 120.0, 90.0, 110.0])
        assert pytest.approx(dd) == 0.25

    def test_peak_not_first(self):
        dd = calc_max_drawdown([100.0, 95.0, 110.0, 105.0, 90.0])
        assert pytest.approx(dd) == pytest.approx((110 - 90) / 110)

    def test_zero_peak(self):
        assert calc_max_drawdown([0.0, 0.0]) == 0.0

    def test_negative_peak_safe(self):
        result = calc_max_drawdown([-100.0, -90.0, -120.0])
        assert isinstance(result, float)
        assert result >= 0.0


class TestCalcSharpeRatio:
    def test_empty_list(self):
        assert calc_sharpe_ratio([]) == 0.0

    def test_single_value(self):
        assert calc_sharpe_ratio([100.0]) == 0.0

    def test_increasing_positive_sharpe(self):
        sr = calc_sharpe_ratio([100.0, 101.0, 102.0, 103.0, 104.0])
        assert sr > 0

    def test_decreasing_negative_sharpe(self):
        sr = calc_sharpe_ratio([100.0, 99.0, 98.0, 97.0])
        assert sr < 0

    def test_zero_variance_positive_returns(self):
        # 零方差（恒定增长）无法计算夏普，应返回 0
        sr = calc_sharpe_ratio([100.0, 200.0, 400.0])
        assert sr == 0.0

    def test_zero_variance_negative_returns_noise(self):
        sr = calc_sharpe_ratio([100.0, 99.99, 99.98, 99.97, 99.96])
        assert sr < 0

    def test_custom_annual_factor(self):
        sr_daily = calc_sharpe_ratio([100.0, 101.0, 102.0, 103.0], annual_factor=252)
        sr_hourly = calc_sharpe_ratio([100.0, 101.0, 102.0, 103.0], annual_factor=252 * 24)
        assert sr_hourly > sr_daily

    def test_integer_inputs(self):
        sr = calc_sharpe_ratio([100, 101, 102])
        assert isinstance(sr, float)


# ═══════════════════════════════════════════════════════════
# common/stats.py — 统计聚合
# ═══════════════════════════════════════════════════════════


class TestComputeSummaryStats:
    def test_empty_list(self):
        assert compute_summary_stats([]) == {}

    def test_single_value(self):
        s = compute_summary_stats([42.0])
        assert s["mean"] == 42.0
        assert s["median"] == 42.0
        assert s["std"] == 0.0
        assert s["count"] == 1

    def test_positive_negative_counts(self):
        s = compute_summary_stats([1.0, -2.0, 3.0, -4.0, 0.0])
        assert s["positive_count"] == 2
        assert s["negative_count"] == 2
        assert s["count"] == 5

    def test_all_zeros(self):
        s = compute_summary_stats([0.0, 0.0, 0.0])
        assert s["positive_count"] == 0
        assert s["negative_count"] == 0
        assert s["mean"] == 0.0

    def test_mixed_values(self):
        s = compute_summary_stats([0.1, 0.2, 0.3, 0.4])
        assert s["mean"] == pytest.approx(0.25)
        assert s["count"] == 4


class TestRankByKeyFlat:
    def test_descending_default(self):
        items = [{"id": "A", "ret": 0.3}, {"id": "B", "ret": 0.1}, {"id": "C", "ret": 0.2}]
        ranked = rank_by_key(items, "ret")
        assert [r["id"] for r in ranked] == ["A", "C", "B"]

    def test_ascending(self):
        items = [{"id": "A", "dd": 0.05}, {"id": "B", "dd": 0.15}, {"id": "C", "dd": 0.08}]
        ranked = rank_by_key(items, "dd", reverse=False)
        assert [r["id"] for r in ranked] == ["A", "C", "B"]

    def test_skips_none_value(self):
        items = [{"id": "A", "ret": 0.3}, {"id": "B", "ret": None}, {"id": "C", "ret": 0.1}]
        ranked = rank_by_key(items, "ret")
        assert len(ranked) == 2
        assert ranked[0]["id"] == "A"

    def test_empty_list(self):
        assert rank_by_key([], "any") == []

    def test_missing_key(self):
        items = [{"id": "A", "ret": 0.3}, {"id": "B"}]
        ranked = rank_by_key(items, "ret")
        assert len(ranked) == 1
        assert ranked[0]["id"] == "A"

    def test_returns_original_objects(self):
        item = {"id": "X", "val": 42}
        ranked = rank_by_key([item], "val")
        assert ranked[0] is item


# ═══════════════════════════════════════════════════════════
# common/formatting.py — 安全格式化
# ═══════════════════════════════════════════════════════════


class TestFormatPct:
    def test_none(self):
        assert format_pct(None) == "N/A"

    def test_ratio(self):
        assert format_pct(0.15) == "15.00%"
        assert format_pct(0.0) == "0.00%"

    def test_percentage_value_normalized(self):
        assert format_pct(0.15) == "15.00%"

    def test_large_percentage(self):
        assert format_pct(1.5) == "150.00%"

    def test_negative_ratio(self):
        assert format_pct(-0.08) == "-8.00%"

    def test_negative_percentage(self):
        assert format_pct(-0.08) == "-8.00%"

    def test_edge_at_one(self):
        assert format_pct(1.0) == "100.00%"

    def test_edge_at_negative_one(self):
        assert format_pct(-1.0) == "-100.00%"

    def test_zero(self):
        assert format_pct(0.0) == "0.00%"


class TestFormatFloat:
    def test_none(self):
        assert format_float(None) == "N/A"

    def test_default_fmt(self):
        assert format_float(0.15) == "0.15"
        assert format_float(1.0) == "1.00"

    def test_custom_fmt(self):
        assert format_float(0.15, ".4f") == "0.1500"

    def test_integer_input(self):
        assert format_float(3, ".2f") == "3.00"

    def test_large_number_with_comma(self):
        assert format_float(15000, ",.0f") == "15,000"

    def test_negative_value(self):
        assert format_float(-3.5, ".1f") == "-3.5"


class TestEnsureFloat:
    def test_none_returns_default(self):
        assert ensure_float(None) == 0.0
        assert ensure_float(None, default=-1.0) == -1.0

    def test_float_passthrough(self):
        assert ensure_float(0.15) == 0.15

    def test_int_conversion(self):
        assert ensure_float(42) == 42.0

    def test_string_conversion(self):
        assert ensure_float("3.14") == 3.14

    def test_string_int(self):
        assert ensure_float("100") == 100.0


class TestParsePercentage:
    def test_string_with_percent(self):
        assert parse_percentage("15.00%") == pytest.approx(0.15)

    def test_string_negative(self):
        assert parse_percentage("-8.50%") == pytest.approx(-0.085)

    def test_float_input(self):
        assert parse_percentage(0.42) == 0.42

    def test_int_input(self):
        assert parse_percentage(1) == 1.0

    def test_zero_string(self):
        assert parse_percentage("0.00%") == 0.0


# ═══════════════════════════════════════════════════════════
# common/formulas.py — 量化公式
# ═══════════════════════════════════════════════════════════


class TestCalculateFifoProfit:
    def _make_fill(self, action: str, price: float, volume: int) -> dict:
        return {"action": action, "price": price, "volume": volume}

    def test_one_buy_one_sell_profit(self):
        fills = [
            self._make_fill("buy", 10.0, 100),
            self._make_fill("sell", 12.0, 100),
        ]
        assert calculate_fifo_profit(fills) == 200.0

    def test_one_buy_one_sell_loss(self):
        fills = [
            self._make_fill("buy", 10.0, 100),
            self._make_fill("sell", 8.0, 100),
        ]
        assert calculate_fifo_profit(fills) == -200.0

    def test_two_buys_one_sell_partial_match(self):
        fills = [
            self._make_fill("buy", 10.0, 50),
            self._make_fill("buy", 11.0, 50),
            self._make_fill("sell", 12.0, 80),
        ]
        expected = (12 - 10) * 50 + (12 - 11) * 30
        assert calculate_fifo_profit(fills) == pytest.approx(expected)

    def test_two_buys_two_sells(self):
        fills = [
            self._make_fill("buy", 10.0, 50),
            self._make_fill("buy", 11.0, 50),
            self._make_fill("sell", 12.0, 50),
            self._make_fill("sell", 13.0, 50),
        ]
        assert calculate_fifo_profit(fills) == 200.0

    def test_no_trades(self):
        assert calculate_fifo_profit([]) == 0.0

    def test_sells_before_buys(self):
        fills = [
            self._make_fill("sell", 12.0, 50),
            self._make_fill("buy", 10.0, 100),
            self._make_fill("sell", 13.0, 50),
        ]
        assert calculate_fifo_profit(fills) == 250.0

    def test_only_buys(self):
        fills = [self._make_fill("buy", 10.0, 100)]
        assert calculate_fifo_profit(fills) == 0.0

    def test_only_sells(self):
        fills = [self._make_fill("sell", 10.0, 100)]
        assert calculate_fifo_profit(fills) == 0.0

    def test_break_even(self):
        fills = [
            self._make_fill("buy", 10.0, 100),
            self._make_fill("sell", 10.0, 100),
        ]
        assert calculate_fifo_profit(fills) == 0.0


class TestTotalReturn:
    def test_positive_return(self):
        assert total_return(100000.0, 110000.0) == pytest.approx(0.1)

    def test_negative_return(self):
        assert total_return(100000.0, 90000.0) == pytest.approx(-0.1)

    def test_break_even(self):
        assert total_return(100000.0, 100000.0) == 0.0

    def test_zero_capital(self):
        assert total_return(0.0, 100000.0) == 0.0

    def test_negative_capital(self):
        assert total_return(-100000.0, 110000.0) == 0.0

    def test_below_min_trades(self):
        assert total_return(100000.0, 110000.0, min_trades=5, total_trades=3) == 0.0

    def test_meets_min_trades(self):
        assert total_return(100000.0, 110000.0, min_trades=5, total_trades=5) == pytest.approx(0.1)

    def test_zero_total_trades(self):
        assert total_return(100000.0, 110000.0, min_trades=1, total_trades=0) == 0.0


class TestWinRate:
    def test_half_wins(self):
        assert win_rate(5, 10) == 0.5

    def test_all_wins(self):
        assert win_rate(10, 10) == 1.0

    def test_all_losses(self):
        assert win_rate(0, 10) == 0.0

    def test_zero_trades(self):
        assert win_rate(0, 0) == 0.0

    def test_negative_total_trades(self):
        assert win_rate(5, -1) == 0.0


class TestPositionSize:
    def test_normal_case(self):
        assert position_size(100000.0, 0.1, 100.0, 10) == 10

    def test_fractional_truncated(self):
        assert position_size(100000.0, 0.1, 105.0, 10) == 9

    def test_minimum_one_lot(self):
        assert position_size(100000.0, 0.01, 5000.0, 100) == 0

    def test_zero_price(self):
        assert position_size(100000.0, 0.1, 0.0, 10) == 0

    def test_zero_contract_size(self):
        assert position_size(100000.0, 0.1, 100.0, 0) == 0

    def test_negative_price(self):
        assert position_size(100000.0, 0.1, -100.0, 10) == 0

    def test_margin_increases_lots(self):
        assert position_size(100000.0, 0.3, 2900.0, 10, 0.07) == 14

    def test_margin_close_to_one(self):
        assert position_size(100000.0, 0.1, 100.0, 10, 1.0) == 10

    def test_margin_zero_fails(self):
        assert position_size(100000.0, 0.1, 100.0, 10, 0.0) == 0

    def test_margin_negative_fails(self):
        assert position_size(100000.0, 0.1, 100.0, 10, -0.1) == 0


class TestProfitableRatio:
    def test_half_profitable(self):
        assert profitable_ratio(5, 10) == 0.5

    def test_all_profitable(self):
        assert profitable_ratio(10, 10) == 1.0

    def test_none_profitable(self):
        assert profitable_ratio(0, 10) == 0.0

    def test_zero_total(self):
        assert profitable_ratio(0, 0) == 0.0

    def test_negative_total(self):
        assert profitable_ratio(5, -1) == 0.0
