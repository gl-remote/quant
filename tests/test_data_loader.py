"""数据加载与划分模块测试"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from backtest.data_loader import split_datasets, get_dataset_info, parse_symbol_exchange


class TestSplitDatasets:
    def test_split_correct_sizes(self, sample_kline_df):
        train, val, test = split_datasets(
            sample_kline_df,
            train_ratio=0.6, val_ratio=0.2, test_ratio=0.2,
        )
        assert len(train) == 60
        assert len(val) == 20
        assert len(test) == 20
        assert len(train) + len(val) + len(test) == 100

    def test_split_different_ratios(self, sample_kline_df):
        train, val, test = split_datasets(
            sample_kline_df,
            train_ratio=0.5, val_ratio=0.3, test_ratio=0.2,
        )
        assert len(train) == 50
        assert len(val) == 30
        assert len(test) == 20

    def test_split_ratio_not_one(self, sample_kline_df):
        with pytest.raises(ValueError, match="划分比例之和必须为"):
            split_datasets(sample_kline_df, 0.5, 0.3, 0.3)

    def test_split_too_few_data(self):
        df = pd.DataFrame({'datetime': [datetime(2024, 1, 1)] * 5})
        with pytest.raises(ValueError, match="数据量不足"):
            split_datasets(df)

    def test_split_preserves_order_no_shuffle(self, sample_kline_df):
        train, val, test = split_datasets(
            sample_kline_df, shuffle=False, random_seed=42,
        )
        # no shuffle: first N rows go to train
        assert train['datetime'].iloc[-1] <= val['datetime'].iloc[0]
        assert val['datetime'].iloc[-1] <= test['datetime'].iloc[0]

    def test_split_shuffle_seed_reproducible(self, sample_kline_df):
        train1, val1, test1 = split_datasets(
            sample_kline_df, shuffle=True, random_seed=42,
        )
        train2, val2, test2 = split_datasets(
            sample_kline_df, shuffle=True, random_seed=42,
        )
        pd.testing.assert_frame_equal(train1, train2)
        pd.testing.assert_frame_equal(val1, val2)
        pd.testing.assert_frame_equal(test1, test2)

    def test_split_shuffle_different_seeds(self, sample_kline_df):
        train_a, _, _ = split_datasets(
            sample_kline_df, shuffle=True, random_seed=1,
        )
        train_b, _, _ = split_datasets(
            sample_kline_df, shuffle=True, random_seed=42,
        )
        # Different seeds may or may not produce same first element
        # We just verify no crash


class TestGetDatasetInfo:
    def test_get_info_with_data(self, sample_kline_df):
        info = get_dataset_info(sample_kline_df, 'train')
        assert info['name'] == 'train'
        assert info['count'] == 100
        assert 'start_date' in info
        assert 'end_date' in info
        assert info['days'] >= 0
        assert info['price_min'] > 0
        assert info['price_max'] > 0

    def test_get_info_empty_df(self):
        df = pd.DataFrame()
        info = get_dataset_info(df, 'empty')
        assert info['name'] == 'empty'
        assert info['count'] == 0

    def test_get_info_none(self):
        info = get_dataset_info(None, 'none')
        assert info['name'] == 'none'
        assert info['count'] == 0


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