"""测试 backtest/walk_forward.py — Walk-Forward 划分与数据工具"""

import pandas as pd
import pytest
from pathlib import Path
from datetime import datetime, timedelta

from backtest.walk_forward import (
    parse_symbol_exchange,
    filter_dataframe_by_date,
    walk_forward_split,
    walk_forward_split_by_ratio,
)


# ==============================================================================
# 辅助函数
# ==============================================================================

def _make_kline_df(n_rows: int = 100, start_date: str = '2024-01-01') -> pd.DataFrame:
    """生成模拟 K 线 DataFrame"""
    dates = pd.date_range(start=start_date, periods=n_rows, freq='D')
    close = 3000.0 + pd.Series(range(n_rows)) * 2.0
    return pd.DataFrame({
        'datetime': dates,
        'open': close - 1.0,
        'high': close + 2.0,
        'low': close - 2.0,
        'close': close,
        'volume': 10000,
    })


# ==============================================================================
# parse_symbol_exchange
# ==============================================================================

class TestParseSymbolExchange:
    def test_with_exchange(self):
        pure, exchange = parse_symbol_exchange('DCE.m2509')
        assert pure == 'm2509'
        assert exchange == 'DCE'

    def test_no_exchange_defaults_to_cffex(self):
        pure, exchange = parse_symbol_exchange('m2509')
        assert pure == 'm2509'
        assert exchange == 'CFFEX'

    def test_multi_dot(self):
        """含多个 '.' 取第一个为交易所，最后一个为纯代码"""
        pure, exchange = parse_symbol_exchange('CZCE.SA.UR405')
        assert pure == 'UR405'
        assert exchange == 'CZCE'

    def test_single_dot(self):
        pure, exchange = parse_symbol_exchange('DCE.m2509')
        assert pure == 'm2509'
        assert exchange == 'DCE'


# ==============================================================================
# filter_dataframe_by_date
# ==============================================================================

class TestFilterDataframeByDate:
    def test_no_filter(self):
        df = _make_kline_df(10)
        result = filter_dataframe_by_date(df)
        assert len(result) == 10

    def test_start_date(self):
        df = _make_kline_df(10, '2024-01-01')
        result = filter_dataframe_by_date(df, start_date='2024-01-05')
        assert len(result) == 6

    def test_end_date(self):
        df = _make_kline_df(10, '2024-01-01')
        result = filter_dataframe_by_date(df, end_date='2024-01-05')
        assert len(result) == 5

    def test_both_dates(self):
        df = _make_kline_df(10, '2024-01-01')
        result = filter_dataframe_by_date(df,
                                          start_date='2024-01-03',
                                          end_date='2024-01-07')
        assert len(result) == 5

    def test_does_not_modify_original(self):
        df = _make_kline_df(10)
        original_len = len(df)
        filter_dataframe_by_date(df, start_date='2024-01-05')
        assert len(df) == original_len

    def test_reset_index(self):
        df = _make_kline_df(10)
        result = filter_dataframe_by_date(df, start_date='2024-01-05')
        assert result.index[0] == 0


# ==============================================================================
# walk_forward_split
# ==============================================================================

class TestWalkForwardSplit:
    def test_basic_split(self):
        df = _make_kline_df(100)
        windows = walk_forward_split(df, train_size=40, val_size=10, test_size=10, step=10)
        assert len(windows) > 0
        for train, val, test in windows:
            assert len(train) == 40
            assert len(val) == 10
            assert len(test) == 10

    def test_insufficient_data(self):
        """数据量不足 — 抛出 ValueError"""
        df = _make_kline_df(10)
        with pytest.raises(ValueError, match='数据量不足'):
            walk_forward_split(df, train_size=20, val_size=10, test_size=10, step=5)

    def test_step_one(self):
        """step=1 产生最大窗口数"""
        df = _make_kline_df(60)
        windows = walk_forward_split(df, train_size=30, val_size=10, test_size=10, step=1)
        assert len(windows) == 11

    def test_single_window(self):
        """刚好一个窗口"""
        df = _make_kline_df(60)
        windows = walk_forward_split(df, train_size=40, val_size=10, test_size=10, step=60)
        assert len(windows) == 1

    def test_no_overlap(self):
        """滚动窗口按 step 滑动"""
        df = _make_kline_df(300)
        windows = walk_forward_split(df, train_size=100, val_size=20, test_size=20, step=20)
        assert len(windows) >= 2
        train0_start = windows[0][0]['datetime'].min()
        train1_start = windows[1][0]['datetime'].min()
        assert train1_start > train0_start


# ==============================================================================
# walk_forward_split_by_ratio
# ==============================================================================

class TestWalkForwardSplitByRatio:
    def test_basic(self):
        df = _make_kline_df(200)
        windows = walk_forward_split_by_ratio(
            df, train_ratio=0.6, val_ratio=0.2, test_ratio=0.2,
            step_ratio=0.1, min_windows=3,
        )
        assert len(windows) >= 1
        for train, val, test in windows:
            assert len(train) > 0
            assert len(val) > 0
            assert len(test) > 0

    def test_ratio_sum_not_one(self):
        df = _make_kline_df(100)
        with pytest.raises(ValueError, match='比例之和必须为 1.0'):
            walk_forward_split_by_ratio(
                df, train_ratio=0.5, val_ratio=0.2, test_ratio=0.2,
            )

    def test_empty_dataframe(self):
        df = pd.DataFrame({'datetime': []})
        with pytest.raises(ValueError, match='数据量为 0'):
            walk_forward_split_by_ratio(df)

    def test_min_windows_met(self):
        """大数据集应满足 min_windows"""
        df = _make_kline_df(500)
        windows = walk_forward_split_by_ratio(
            df, train_ratio=0.6, val_ratio=0.2, test_ratio=0.2,
            step_ratio=0.1, min_windows=3,
        )
        assert len(windows) >= 3

    def test_train_val_test_cover_all_data(self):
        """验证 train+val+test 比例正确"""
        df = _make_kline_df(300)
        windows = walk_forward_split_by_ratio(
            df, train_ratio=0.6, val_ratio=0.2, test_ratio=0.2,
            step_ratio=0.1, min_windows=3,
        )
        for train, val, test in windows:
            total = len(train) + len(val) + len(test)
            assert abs(len(train) / total - 0.6) < 0.15
