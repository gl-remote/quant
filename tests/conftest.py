"""共享测试 fixtures 和 helper 函数"""

import pytest
import tempfile
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta

import tomli_w

from common.constants import STATUS_SUCCESS


# ==============================================================================
# 回测数据 helper（test_database / test_report 共用）
# ==============================================================================

VNPTY_STATS = {
    'total_trades': 80,
    'win_trades': 45,
    'loss_trades': 35,
    'end_balance': 118000.0,
    'annual_return': 0.18,
    'max_consecutive_win': 6,
    'max_consecutive_loss': 3,
    'average_win': 120.0,
    'average_loss': -55.0,
    'win_loss_ratio': 2.18,
    'sharpe_ratio': 1.35,
    'max_drawdown': 0.12,
    'max_ddpercent_duration': 15,
    'daily_std': 0.018,
    'return_drawdown_ratio': 1.5,
}


def make_trade(dt, sym='DCE.m2509', direction='long', offset='open',
               price=3500.0, quantity=1, pnl=0.0):
    return {
        'datetime': dt,
        'symbol': sym,
        'direction': direction,
        'offset': offset,
        'open_price': price,
        'close_price': price,
        'quantity': quantity,
        'pnl': pnl,
        'commission': 0.0,
    }


def make_daily(dt, equity=100000.0, daily_return=0.0, drawdown=0.0):
    return {
        'datetime': dt,
        'equity': equity,
        'daily_return': daily_return,
        'drawdown': drawdown,
    }


def insert_full_backtest(store, **overrides):
    """插入一条完整回测 (主记录 + 交易 + 每日曲线)，返回 backtest_id"""
    ec = {
        'initial_capital': 100000.0,
        'commission_rate': 0.0003,
        'slippage': 1.0,
        'price_tick': 1.0,
        'contract_size': 10,
        'kline_interval': '1m',
    }
    bt_id = store.insert_backtest_detailed(
        symbol=overrides.get('symbol', 'DCE.m2509'),
        strategy=overrides.get('strategy', 'ma'),
        status=STATUS_SUCCESS,
        error_message=None,
        statistics=VNPTY_STATS,
        engine_config=ec,
        params_json='{"sma_short":5,"sma_long":20}',
        start_date='2024-01-01',
        end_date='2024-12-31',
        strategy_version='1.0',
        git_hash='abc1234',
    )
    trades = [
        make_trade('2024-01-15 10:00:00', direction='long', offset='open', pnl=200.0),
        make_trade('2024-01-20 14:30:00', direction='short', offset='close', pnl=-100.0),
        make_trade('2024-02-01 09:15:00', direction='long', offset='open', pnl=350.0),
    ]
    store.insert_backtest_trades(bt_id, trades)
    daily = [
        make_daily('2024-01-15', 100200.0, 200.0, 0.0),
        make_daily('2024-01-20', 100100.0, -100.0, 0.001),
        make_daily('2024-02-01', 100450.0, 350.0, 0.0),
    ]
    store.insert_backtest_daily(bt_id, daily)
    return bt_id


# ==============================================================================
# pytest fixtures
# ==============================================================================


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
    """基础配置字典（模拟 conf.toml 新格式）"""
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
            'export_dir': '.quant_shared_data/csv',
            'filename_template': '{symbol}.{provider}.{interval}.csv',
        },
        'backtest': {
            'initial_capital': 100000.0,
            'commission_rate': 0.0003,
            'slippage': 1.0,
            'price_tick': 1.0,
            'contract_size': 10,
            'interval': '1m',
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


@pytest.fixture(autouse=True)
def _reset_config_singleton():
    """每个测试前重置 ConfigManager 单例"""
    from config.app_config import ConfigManager
    ConfigManager.reset()
    yield
    ConfigManager.reset()


@pytest.fixture
def temp_config_file(base_config_dict):
    """创建临时 conf.toml"""
    fd, path = tempfile.mkstemp(suffix='.toml')
    with open(fd, 'wb') as f:
        f.write(tomli_w.dumps(base_config_dict).encode('utf-8'))
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
