import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from backtest.aggregator import (
    compute_summary_stats,
    rank_by_key,
    parse_percentage,
    aggregate_walk_forward,
)


# ── compute_summary_stats ─────────────────────────────────

class TestComputeSummaryStats:
    def test_empty_list(self):
        assert compute_summary_stats([]) == {}

    def test_single_value(self):
        s = compute_summary_stats([42.0])
        assert s['mean'] == 42.0
        assert s['median'] == 42.0
        assert s['std'] == 0.0
        assert s['min'] == 42.0
        assert s['max'] == 42.0

    def test_positive_negative_counts(self):
        s = compute_summary_stats([1.0, -2.0, 3.0, -4.0, 0.0])
        assert s['positive_count'] == 2
        assert s['negative_count'] == 2  # 0 is neither

    def test_all_zeros(self):
        # all zeros → positive_count = 0 (special case)
        s = compute_summary_stats([0.0, 0.0, 0.0])
        assert s['positive_count'] == 0
        assert s['negative_count'] == 0
        assert s['mean'] == 0.0

    def test_mixed_values(self):
        s = compute_summary_stats([0.1, 0.2, 0.3, 0.4])
        assert s['mean'] == pytest.approx(0.25)
        assert s['std'] == pytest.approx(0.1 * 1.25**0.5, abs=0.01)
        assert s['positive_count'] == 4

    def test_integer_inputs(self):
        s = compute_summary_stats([1, 2, 3])
        assert isinstance(s['mean'], float)
        assert s['mean'] == 2.0
        assert s['min'] == 1.0
        assert s['max'] == 3.0


# ── rank_by_key ───────────────────────────────────────────

class TestRankByKey:
    def _make_items(self):
        return [
            {'symbol': 'A', 'metrics': {'ret': 0.3, 'dd': 0.05}},
            {'symbol': 'B', 'metrics': {'ret': 0.1, 'dd': 0.15}},
            {'symbol': 'C', 'metrics': {'ret': 0.2, 'dd': 0.08}},
        ]

    def test_descending_default(self):
        ranked = rank_by_key(self._make_items(), 'ret')
        assert [r['symbol'] for r in ranked] == ['A', 'C', 'B']
        assert ranked[0]['value'] == 0.3

    def test_ascending(self):
        ranked = rank_by_key(self._make_items(), 'dd', reverse=False)
        assert [r['symbol'] for r in ranked] == ['A', 'C', 'B']
        assert ranked[0]['value'] == 0.05

    def test_skips_none_value(self):
        items = [
            {'symbol': 'A', 'metrics': {'ret': 0.3}},
            {'symbol': 'B', 'metrics': {'ret': None}},
            {'symbol': 'C', 'metrics': {'ret': 0.1}},
        ]
        ranked = rank_by_key(items, 'ret')
        assert len(ranked) == 2
        assert ranked[0]['symbol'] == 'A'

    def test_empty_list(self):
        assert rank_by_key([], 'ret') == []

    def test_output_structure(self):
        ranked = rank_by_key(self._make_items(), 'ret')
        for r in ranked:
            assert 'symbol' in r
            assert 'value' in r
            assert isinstance(r['value'], (int, float))


# ── parse_percentage ──────────────────────────────────────

class TestParsePercentage:
    def test_string_with_percent(self):
        assert parse_percentage('15.00%') == pytest.approx(0.15)

    def test_string_negative(self):
        assert parse_percentage('-8.50%') == pytest.approx(-0.085)

    def test_float_input(self):
        assert parse_percentage(0.42) == 0.42

    def test_int_input(self):
        assert parse_percentage(1) == 1.0

    def test_zero_string(self):
        assert parse_percentage('0.00%') == 0.0


# ── aggregate_walk_forward ────────────────────────────────

class TestAggregateWalkForward:
    def _make_window(self, ret=0.1, sharpe=1.5, dd=0.08, wr=0.6):
        return {
            'statistics': {
                'total_return': ret,
                'sharpe_ratio': sharpe,
                'max_drawdown': dd,
                'win_rate': wr,
            },
        }

    def test_single_window(self):
        agg = aggregate_walk_forward([self._make_window()])
        assert agg['return_mean'] == 0.1
        assert agg['return_std'] == 0.0
        assert agg['sharpe_mean'] == 1.5
        assert agg['win_rate_mean'] == 0.6
        assert agg['positive_window_ratio'] == 1.0

    def test_multiple_windows(self):
        windows = [
            self._make_window(ret=0.1, sharpe=1.0, dd=0.05, wr=0.6),
            self._make_window(ret=0.3, sharpe=2.0, dd=0.03, wr=0.7),
            self._make_window(ret=-0.05, sharpe=-0.5, dd=0.12, wr=0.4),
        ]
        agg = aggregate_walk_forward(windows)
        assert agg['return_mean'] == pytest.approx(0.1167, abs=0.01)
        assert agg['sharpe_mean'] == pytest.approx(0.833, abs=0.01)
        assert agg['positive_window_ratio'] == pytest.approx(2 / 3)
        assert 0 <= agg['stability_score'] <= 1

    def test_string_percentage_inputs(self):
        """百分比字符串格式的指标也应正确解析"""
        windows = [{
            'statistics': {
                'total_return': '15.00%',
                'sharpe_ratio': 1.2,
                'max_drawdown': '8.00%',
                'win_rate': '60.00%',
            },
        }]
        agg = aggregate_walk_forward(windows)
        assert agg['return_mean'] == pytest.approx(0.15)
        assert agg['max_drawdown_mean'] == pytest.approx(0.08)
        assert agg['win_rate_mean'] == pytest.approx(0.6)

    def test_stability_score_perfect(self):
        """零波动窗口 → 稳定性 = 1.0"""
        windows = [
            self._make_window(ret=0.1),
            self._make_window(ret=0.1),
        ]
        agg = aggregate_walk_forward(windows)
        assert agg['stability_score'] == 1.0

    def test_max_drawdown_worst(self):
        """max_drawdown_worst 取所有窗口中的最大值"""
        windows = [
            self._make_window(dd=0.05),
            self._make_window(dd=0.15),
            self._make_window(dd=0.08),
        ]
        agg = aggregate_walk_forward(windows)
        assert agg['max_drawdown_worst'] == pytest.approx(0.15)

    def test_empty_stats_tolerated(self):
        """空 statistics 的窗口不抛异常，值为 0"""
        agg = aggregate_walk_forward([{'statistics': {}}])
        assert agg['return_mean'] == 0.0
        assert agg['sharpe_mean'] == 0.0
