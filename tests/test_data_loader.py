"""数据加载与划分模块测试"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timedelta
from backtest.data_loader import parse_symbol_exchange, scan_csv_files, filter_dataframe_by_date


class TestParseSymbolExchange:
    def test_standard_dce_symbol(self):
        pure, exchange = parse_symbol_exchange("DCE.m2509")
        assert pure == "m2509"

    def test_standard_czce_symbol(self):
        pure, exchange = parse_symbol_exchange("CZCE.TA509")
        assert pure == "TA509"

    def test_no_dot_symbol(self):
        pure, exchange = parse_symbol_exchange("m2509")
        assert pure == "m2509"

    def test_multi_dot_symbol(self):
        pure, exchange = parse_symbol_exchange("A.B.c123")
        assert pure == "c123"


class TestScanCsvFiles:
    def test_empty_dir(self, tmp_path):
        result = scan_csv_files(str(tmp_path))
        assert result == []

    def test_no_csv_files(self, tmp_path):
        (tmp_path / "readme.txt").write_text("hello")
        result = scan_csv_files(str(tmp_path))
        assert result == []

    def test_single_file(self, tmp_path):
        (tmp_path / "DCE.m2509.csv").write_text("datetime,close\n2024-01-01,100")
        result = scan_csv_files(str(tmp_path))
        assert len(result) == 1
        assert result[0][0] == "DCE.m2509"

    def test_qilib_filename(self, tmp_path):
        (tmp_path / "DCE.m2509_qlib.csv").write_text("datetime,close\n2024-01-01,100")
        result = scan_csv_files(str(tmp_path))
        assert len(result) == 1
        assert result[0][0] == "DCE.m2509"

    def test_multiple_files(self, tmp_path):
        (tmp_path / "DCE.m2509.csv").write_text("d")
        (tmp_path / "CZCE.TA509.csv").write_text("d")
        (tmp_path / "SHFE.rb2410_qlib.csv").write_text("d")
        result = scan_csv_files(str(tmp_path))
        assert len(result) == 3
        symbols = {s for s, _ in result}
        assert symbols == {"DCE.m2509", "CZCE.TA509", "SHFE.rb2410"}

    def test_pattern_filter(self, tmp_path):
        (tmp_path / "DCE.m2509.csv").write_text("d")
        (tmp_path / "DCE.m2601.csv").write_text("d")
        (tmp_path / "CZCE.TA509.csv").write_text("d")
        result = scan_csv_files(str(tmp_path), pattern=r"DCE\.m")
        assert len(result) == 2

    def test_pattern_no_match(self, tmp_path):
        (tmp_path / "DCE.m2509.csv").write_text("d")
        result = scan_csv_files(str(tmp_path), pattern=r"XXX")
        assert result == []

    def test_dedup_qilib_variant(self, tmp_path):
        (tmp_path / "DCE.m2509.csv").write_text("d")
        (tmp_path / "DCE.m2509_qlib.csv").write_text("d")
        result = scan_csv_files(str(tmp_path))
        assert len(result) == 1
        assert result[0][0] == "DCE.m2509"

    def test_nonexistent_dir(self):
        result = scan_csv_files("/nonexistent/path")
        assert result == []


class TestFilterDataframeByDate:
    def test_no_filter_returns_copy(self, sample_kline_df):
        result = filter_dataframe_by_date(sample_kline_df)
        assert len(result) == len(sample_kline_df)
        # must be a reindexed copy, not same object
        assert result.index[0] == 0

    def test_start_date_only(self, sample_kline_df):
        mid_date = sample_kline_df['datetime'].iloc[50]
        result = filter_dataframe_by_date(sample_kline_df, start_date=str(mid_date)[:10])
        assert len(result) <= 50
        assert (result['datetime'] >= mid_date).all()

    def test_end_date_only(self, sample_kline_df):
        mid_date = sample_kline_df['datetime'].iloc[49]
        result = filter_dataframe_by_date(sample_kline_df, end_date=str(mid_date)[:10])
        assert len(result) <= 50
        assert (result['datetime'] <= mid_date).all()

    def test_both_dates(self, sample_kline_df):
        start = sample_kline_df['datetime'].iloc[20]
        end = sample_kline_df['datetime'].iloc[60]
        result = filter_dataframe_by_date(sample_kline_df, start_date=str(start)[:10], end_date=str(end)[:10])
        assert len(result) >= 0
        assert (result['datetime'] >= start).all()
        assert (result['datetime'] <= end).all()

    def test_out_of_range_start_returns_empty(self, sample_kline_df):
        far_future = (sample_kline_df['datetime'].max() + timedelta(days=1000)).strftime('%Y-%m-%d')
        result = filter_dataframe_by_date(sample_kline_df, start_date=far_future)
        assert result.empty

    def test_resets_index(self, sample_kline_df):
        result = filter_dataframe_by_date(sample_kline_df)
        assert result.index.is_monotonic_increasing
        assert result.index[0] == 0
