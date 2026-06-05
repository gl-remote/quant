"""共享测试 fixtures 和 helper 函数"""

import sys
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
import tempfile
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta

import tomli_w

from common.constants import STATUS_SUCCESS
from common.types import BacktestResult


# ==============================================================================
# 回测数据 helper（test_database / test_report 共用）
# ==============================================================================

VNPTY_STATS = {
    # 基础统计
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
    # 2026-06-06 新增 vnpy 统计字段
    'max_ddpercent': 12.5,            # 最大回撤百分比
    'total_net_pnl': 18000.0,          # 总净盈亏金额
    'daily_net_pnl': 49.32,            # 日均净盈亏
    'total_commission': 1200.5,        # 总手续费
    'daily_commission': 3.29,          # 日均手续费
    'total_slippage': 800.0,           # 总滑点成本
    'daily_slippage': 2.19,           # 日均滑点
    'total_turnover': 4000000.0,       # 总成交金额
    'daily_turnover': 10958.9,        # 日均成交额
    'profit_days': 195,                # 盈利交易日数
    'loss_days': 170,                  # 亏损交易日数
    'daily_trade_count': 0.22,         # 日均成交笔数
    'daily_return_pct': 0.049,         # 日均收益率%
    'ewm_sharpe': 1.42,               # EWM夏普比率
    'rgr_ratio': 1.65,                # RGR比率
}


def make_trade(dt, sym='DCE.m2509', direction='long', offset='open',
               price=3500.0, quantity=1, pnl=0.0, commission=10.5):
    return {
        'datetime': dt,
        'symbol': sym,
        'direction': direction,
        'offset': offset,
        'open_price': price,
        'close_price': price,
        'quantity': quantity,
        'pnl': pnl,
        'commission': commission,  # 2026-06-06: 改为真实手续费
    }


def make_daily(dt, equity=100000.0, daily_return=0.0, drawdown=0.0):
    return {
        'datetime': dt,
        'equity': equity,
        'daily_return': daily_return,
        'drawdown': drawdown,
    }


def insert_full_backtest(store, **overrides):
    """插入一条完整回测 (主记录 + 交易 + 每日曲线)，返回 backtest_id

    通过 BacktestResult 对象调用 insert_backtest_detailed，与实际回测流程一致。
    """
    s = VNPTY_STATS
    result = BacktestResult(
        symbol=overrides.get('symbol', 'DCE.m2509'),
        strategy=overrides.get('strategy', 'ma'),
        status=STATUS_SUCCESS,
        start_date='2024-01-01',
        end_date='2024-12-31',
        total_days=365,
        initial_capital=100000.0,
        commission_rate=0.0003,
        slippage=1.0,
        price_tick=1.0,
        contract_size=10,
        kline_interval='1m',
        end_balance=s['end_balance'],
        total_return=s['end_balance'] - 100000.0,
        annual_return=s['annual_return'],
        total_trades=s['total_trades'],
        win_trades=s['win_trades'],
        loss_trades=s['loss_trades'],
        max_consecutive_win=s['max_consecutive_win'],
        max_consecutive_loss=s['max_consecutive_loss'],
        avg_win=s['average_win'],
        avg_loss=s['average_loss'],
        win_loss_ratio=s['win_loss_ratio'],
        sharpe_ratio=s['sharpe_ratio'],
        max_drawdown=s['max_drawdown'],
        max_ddpercent=s['max_ddpercent'],                    # 2026-06-06新增
        max_drawdown_duration=s['max_ddpercent_duration'],
        daily_std=s['daily_std'],
        return_drawdown_ratio=s['return_drawdown_ratio'],
        # 盈亏汇总 [vnpy] (2026-06-06新增)
        total_net_pnl=s['total_net_pnl'],
        daily_net_pnl=s['daily_net_pnl'],
        total_commission=s['total_commission'],
        daily_commission=s['daily_commission'],
        total_slippage=s['total_slippage'],
        daily_slippage=s['daily_slippage'],
        total_turnover=s['total_turnover'],
        daily_turnover=s['daily_turnover'],
        # 交易日统计 [vnpy]
        profit_days=s['profit_days'],
        loss_days=s['loss_days'],
        daily_trade_count=s['daily_trade_count'],
        daily_return_pct=s['daily_return_pct'],
        # 进阶指标 [vnpy]
        ewm_sharpe=s['ewm_sharpe'],
        rgr_ratio=s['rgr_ratio'],
        win_rate=s['win_trades'] / (s['win_trades'] + s['loss_trades']),
        strategy_params={'sma_short': 5, 'sma_long': 20},
        strategy_version='1.0',
        git_hash='abc1234',
    )
    bt_id = store.insert_backtest_detailed(result)
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
        'position_ratio': 0.3,
        'sma_short': 10,
        'sma_long': 40,
        'kline_period': 5,
        'atr_period': 14,
        'atr_stop_loss_multiplier': 2.0,
        'atr_take_profit_multiplier': 3.0,
    }


@pytest.fixture
def base_config_dict():
    """基础配置字典（模拟 conf.toml 新格式）"""
    return {
        'strategies': [
            {
                'name': 'ma',
                'sma_short': 10,
                'sma_long': 40,
                'stop_loss_ratio': 0.03,
                'take_profit_ratio': 0.05,
                'position_ratio': 0.3,
                'kline_period': 5,
                'atr_period': 14,
                'atr_stop_loss_multiplier': 2.0,
                'atr_take_profit_multiplier': 3.0,
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
