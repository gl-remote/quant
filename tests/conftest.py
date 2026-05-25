"""共享测试 fixtures"""

import pytest
import tempfile
import pandas as pd
import numpy as np
import yaml
import os
from pathlib import Path
from datetime import datetime, timedelta


@pytest.fixture
def sample_closes():
    """生成模拟的收盘价序列"""
    base = 100.0
    return [base + i * 0.5 + np.random.normal(0, 0.2) for i in range(50)]


@pytest.fixture
def trading_config_dict():
    """基础交易配置"""
    return {
        'stop_loss_ratio': 0.03,
        'take_profit_ratio': 0.05,
        'position_ratio': 0.1,
        'sma_short': 5,
        'sma_long': 20,
        'kline_period': 5,
    }


@pytest.fixture
def base_config_dict():
    """基础配置字典（模拟 conf.yaml 新格式）"""
    return {
        'strategies': [
            {
                'name': 'ma',
                'sma_short': 5,
                'sma_long': 20,
                'stop_loss_ratio': 0.03,
                'take_profit_ratio': 0.05,
                'position_ratio': 0.1,
                'kline_period': 5,
            },
        ],
        'data': {
            'base_dir': '.quant_shared_data',
            'db_path': '.quant_shared_data/quant_shared.db',
        },
        'export': {
            'default_dir': '.quant_shared_data/csv',
            'filename_template': '{symbol}.{interval}.csv',
        },
        'backtest': {
            'initial_capital': 100000.0,
            'commission_rate': 0.0003,
            'slippage': 1.0,
            'price_tick': 1.0,
            'contract_size': 10,
            'interval': '1m',
            'report': {
                'output_dir': '.quant_shared_data/reports',
                'save_trade_records': True,
                'save_equity_curve': True,
            },
        },
        'system': {
            'logging': {
                'level': 'INFO',
            },
        },
    }


@pytest.fixture
def sample_kline_df():
    """生成模拟K线DataFrame"""
    np.random.seed(42)
    dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(100)]
    close = 3000.0 + np.cumsum(np.random.normal(0, 10, 100))
    df = pd.DataFrame({
        'datetime': dates,
        'open': close - np.random.uniform(0, 5, 100),
        'high': close + np.random.uniform(0, 10, 100),
        'low': close - np.random.uniform(0, 10, 100),
        'close': close,
        'volume': np.random.randint(1000, 50000, 100),
    })
    return df


@pytest.fixture
def temp_config_file(base_config_dict):
    """创建临时 conf.yaml"""
    fd, path = tempfile.mkstemp(suffix='.yaml')
    with open(fd, 'w', encoding='utf-8') as f:
        yaml.dump(base_config_dict, f)
    yield path
    os.unlink(path)


@pytest.fixture
def temp_db_path():
    """创建临时数据库路径"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    os.unlink(path)
    yield path
    if os.path.exists(path):
        os.unlink(path)
    # clean up WAL/SHM files
    for suffix in ['-wal', '-shm']:
        p = path + suffix
        if os.path.exists(p):
            os.unlink(p)