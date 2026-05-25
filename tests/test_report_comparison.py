"""report 模块 & 数据管道集成测试

覆盖:
    - DataStore.insert_backtest_detailed → 读取完整性
    - DataStore.delete_backtest 端到端 (CASCADE 级联)
    - format_single_report 带真实数据
    - format_summary_report 列表/过滤
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from datetime import datetime

from common.constants import STATUS_SUCCESS, STATUS_FAILED
from data.store import DataStore


# ==============================================================================
# DataStore insert / query / delete 端到端
# ==============================================================================

_vnpy_stats = {
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


def _make_trade(dt, sym='DCE.m2509', direction='long', offset='open',
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


def _make_daily(dt, equity=100000.0, daily_return=0.0, drawdown=0.0):
    return {
        'datetime': dt,  # store.insert_backtest_daily 用 'datetime' 键
        'equity': equity,
        'daily_return': daily_return,
        'drawdown': drawdown,
    }


def _insert_full_backtest(store, **overrides):
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
        statistics=_vnpy_stats,
        engine_config=ec,
        params_json='{"sma_short":5,"sma_long":20}',
        start_date='2024-01-01',
        end_date='2024-12-31',
        strategy_version='1.0',
        git_hash='abc1234',
    )
    # 写入交易明细
    trades = [
        _make_trade('2024-01-15 10:00:00', direction='long', offset='open', pnl=200.0),
        _make_trade('2024-01-20 14:30:00', direction='short', offset='close', pnl=-100.0),
        _make_trade('2024-02-01 09:15:00', direction='long', offset='open', pnl=350.0),
    ]
    store.insert_backtest_trades(bt_id, trades)
    # 写入每日曲线
    daily = [
        _make_daily('2024-01-15', 100200.0, 200.0, 0.0),
        _make_daily('2024-01-20', 100100.0, -100.0, 0.001),
        _make_daily('2024-02-01', 100450.0, 350.0, 0.0),
    ]
    store.insert_backtest_daily(bt_id, daily)
    return bt_id


class TestInsertAndQuery:
    def test_insert_and_get_backtest(self, temp_db_path):
        store = DataStore(temp_db_path)
        bt_id = _insert_full_backtest(store)
        bt = store.get_backtest(bt_id)
        assert bt is not None
        assert bt.symbol == 'DCE.m2509'
        assert bt.strategy == 'ma'
        assert bt.strategy_version == '1.0'
        assert bt.git_hash == 'abc1234'
        assert bt.start_date == '2024-01-01'
        assert bt.status == 'success'
        # 统计字段正确映射
        assert bt.total_trades == 80
        assert bt.win_trades == 45
        assert bt.loss_trades == 35
        assert bt.avg_win == 120.0
        assert bt.avg_loss == -55.0
        assert bt.sharpe_ratio == 1.35
        assert bt.max_drawdown == 0.12
        assert bt.daily_std == 0.018
        assert bt.initial_capital == 100000.0
        assert bt.end_balance == 118000.0
        assert bt.annual_return == 0.18
        assert bt.total_return is not None
        assert bt.win_rate is not None
        store.close()

    def test_query_trades(self, temp_db_path):
        store = DataStore(temp_db_path)
        bt_id = _insert_full_backtest(store)
        trades = store.query_trades(bt_id)
        assert len(trades) == 3
        assert trades[0].symbol == 'DCE.m2509'
        assert trades[1].pnl == -100.0
        store.close()

    def test_query_daily(self, temp_db_path):
        store = DataStore(temp_db_path)
        bt_id = _insert_full_backtest(store)
        daily = store.query_daily(bt_id)
        assert len(daily) == 3
        assert daily[0]['equity'] == 100200.0
        assert daily[1]['daily_return'] == -100.0
        store.close()

    def test_query_backtests_filter(self, temp_db_path):
        store = DataStore(temp_db_path)
        _insert_full_backtest(store, symbol='DCE.m2509')
        _insert_full_backtest(store, symbol='DCE.rb2410', strategy='sma')
        # 全量
        all_bt = store.query_backtests(status='success', limit=50)
        assert len(all_bt) == 2
        # 按品种过滤
        filtered = store.query_backtests(symbol='DCE.m2509', status='success')
        assert len(filtered) == 1
        assert filtered[0].symbol == 'DCE.m2509'
        # 按策略过滤
        filtered = store.query_backtests(strategy='sma', status='success')
        assert len(filtered) == 1
        assert filtered[0].strategy == 'sma'
        # 无匹配
        filtered = store.query_backtests(symbol='NONEXIST', status='success')
        assert len(filtered) == 0
        store.close()

    def test_query_backtests_limit(self, temp_db_path):
        store = DataStore(temp_db_path)
        for i in range(5):
            _insert_full_backtest(store, symbol=f'DCE.sym{i:02d}')
        results = store.query_backtests(status='success', limit=2)
        assert len(results) == 2
        store.close()

    def test_failed_backtest_ignored_by_default(self, temp_db_path):
        store = DataStore(temp_db_path)
        _insert_full_backtest(store, symbol='DCE.good')
        # 直接插入一条失败记录
        store.insert_backtest_detailed(
            symbol='DCE.bad', strategy='ma', status=STATUS_FAILED,
            error_message='test error', statistics={}, engine_config={},
            params_json='{}', start_date=None, end_date=None,
        )
        results = store.query_backtests(status='success')
        assert len(results) == 1
        assert results[0].symbol == 'DCE.good'
        store.close()


class TestDeleteBacktest:
    def test_delete_removes_main_record(self, temp_db_path):
        store = DataStore(temp_db_path)
        bt_id = _insert_full_backtest(store)
        assert store.get_backtest(bt_id) is not None
        ok = store.delete_backtest(bt_id)
        assert ok is True
        assert store.get_backtest(bt_id) is None
        store.close()

    def test_delete_cascades_trades(self, temp_db_path):
        store = DataStore(temp_db_path)
        bt_id = _insert_full_backtest(store)
        assert len(store.query_trades(bt_id)) == 3
        store.delete_backtest(bt_id)
        assert len(store.query_trades(bt_id)) == 0
        store.close()

    def test_delete_cascades_daily(self, temp_db_path):
        store = DataStore(temp_db_path)
        bt_id = _insert_full_backtest(store)
        assert len(store.query_daily(bt_id)) == 3
        store.delete_backtest(bt_id)
        assert len(store.query_daily(bt_id)) == 0
        store.close()

    def test_delete_nonexistent_returns_false(self, temp_db_path):
        store = DataStore(temp_db_path)
        ok = store.delete_backtest(99999)
        assert ok is False
        store.close()

    def test_delete_idempotent(self, temp_db_path):
        store = DataStore(temp_db_path)
        bt_id = _insert_full_backtest(store)
        store.delete_backtest(bt_id)
        # 二次删除不抛异常
        ok = store.delete_backtest(bt_id)
        assert ok is False
        store.close()

    def test_delete_isolated(self, temp_db_path):
        """删除一条不影响其他记录"""
        store = DataStore(temp_db_path)
        id1 = _insert_full_backtest(store, symbol='DCE.m2509')
        id2 = _insert_full_backtest(store, symbol='DCE.rb2410')
        store.delete_backtest(id1)
        assert store.get_backtest(id2) is not None
        assert len(store.query_trades(id2)) == 3
        assert len(store.query_daily(id2)) == 3
        store.close()


# ==============================================================================
# report 格式化集成测试
# ==============================================================================

class TestFormatSingleReport:
    def test_success_report_contains_key_metrics(self, temp_db_path):
        from report import format_single_report
        from data import DataManager
        dm = DataManager()
        dm._init_store = lambda: None  # 注入路径
        dm._store = DataStore(temp_db_path)
        bt_id = _insert_full_backtest(dm._store)

        text = format_single_report(dm, bt_id)
        assert '回测报告 #' in text
        assert 'DCE.m2509' in text
        assert 'ma' in text
        assert '1.0' in text          # strategy_version
        assert 'abc1234' in text      # git_hash
        assert 'success' in text
        assert '2024-01-01' in text   # start_date
        assert '2024-12-31' in text   # end_date
        assert '100,000.00' in text   # initial_capital
        assert '118,000.00' in text   # end_balance
        assert '1.35' in text         # sharpe_ratio
        assert '80' in text           # total_trades
        assert '45' in text           # win_trades
        assert '35' in text           # loss_trades
        assert '120' in text          # avg_win
        # 每日资金曲线
        assert '100,200.00' in text
        assert '100,100.00' in text
        assert '100,450.00' in text
        # 交易明细
        assert '多' in text
        assert '空' in text
        assert '开' in text
        assert '平' in text
        dm.close()

    def test_failed_report_shows_error(self, temp_db_path):
        from report import format_single_report
        from data import DataManager
        dm = DataManager()
        dm._store = DataStore(temp_db_path)
        bt_id = dm._store.insert_backtest_detailed(
            symbol='DCE.bad', strategy='ma', status=STATUS_FAILED,
            error_message='数据不足无法回测', statistics={},
            engine_config={}, params_json='{}',
            start_date=None, end_date=None,
        )
        text = format_single_report(dm, bt_id)
        assert '失败' in text or 'failed' in text
        assert '数据不足无法回测' in text
        dm.close()

    def test_nonexistent_id(self, temp_db_path):
        from report import format_single_report
        from data import DataManager
        dm = DataManager()
        dm._store = DataStore(temp_db_path)
        text = format_single_report(dm, 99999)
        assert '错误' in text or '未找到' in text
        dm.close()

    def test_no_daily_no_crash(self, temp_db_path):
        """无每日曲线时不崩 — 适用于 TqSdk 回测"""
        from report import format_single_report
        from data import DataManager
        dm = DataManager()
        dm._store = DataStore(temp_db_path)
        bt_id = dm._store.insert_backtest_detailed(
            symbol='DCE.m2509', strategy='ma', status=STATUS_SUCCESS,
            error_message=None,
            statistics={'total_trades': 3, 'end_balance': 101000.0},
            engine_config={'initial_capital': 100000.0},
            params_json='{}',
            start_date='2024-01-01', end_date='2024-03-31',
        )
        text = format_single_report(dm, bt_id)
        assert '交易日数:   0 天' in text
        assert '资金曲线' not in text  # 无 daily 不显示此段
        dm.close()


class TestFormatSummaryReport:
    def test_list_success_records(self, temp_db_path):
        from report import format_summary_report
        from data import DataManager
        dm = DataManager()
        dm._store = DataStore(temp_db_path)
        _insert_full_backtest(dm._store, symbol='DCE.m2509')
        _insert_full_backtest(dm._store, symbol='DCE.rb2410')

        text = format_summary_report(dm, limit=10)
        assert '回测汇总' in text
        assert '2 条' in text
        assert 'DCE.m2509' in text
        assert 'DCE.rb2410' in text
        assert 'abc1234' in text              # git_hash
        assert '1.0' in text                 # strategy_version
        assert 'python main.py report --id' in text
        dm.close()

    def test_empty_list(self, temp_db_path):
        from report import format_summary_report
        from data import DataManager
        dm = DataManager()
        dm._store = DataStore(temp_db_path)
        text = format_summary_report(dm)
        assert '未找到' in text
        dm.close()

    def test_filter_by_symbol(self, temp_db_path):
        from report import format_summary_report
        from data import DataManager
        dm = DataManager()
        dm._store = DataStore(temp_db_path)
        _insert_full_backtest(dm._store, symbol='DCE.m2509')
        _insert_full_backtest(dm._store, symbol='DCE.rb2410')

        text = format_summary_report(dm, symbol='DCE.m2509')
        assert 'DCE.m2509' in text
        assert 'DCE.rb2410' not in text
        dm.close()

    def test_filter_by_strategy(self, temp_db_path):
        from report import format_summary_report
        from data import DataManager
        dm = DataManager()
        dm._store = DataStore(temp_db_path)
        _insert_full_backtest(dm._store, symbol='DCE.m2509', strategy='ma')
        _insert_full_backtest(dm._store, symbol='DCE.rb2410', strategy='bband')

        text = format_summary_report(dm, strategy='bband')
        assert 'bband' in text
        assert '1 条' in text             # 只有 1 条
        assert 'DCE.rb2410' in text       # bband 的记录
        assert 'DCE.m2509' not in text    # ma 的记录被过滤掉
        dm.close()


# ==============================================================================
# 公共 API 存在性
# ==============================================================================

class TestReportPublicAPI:
    def test_format_single_report_importable(self):
        from report import format_single_report
        assert callable(format_single_report)

    def test_format_summary_report_importable(self):
        from report import format_summary_report
        assert callable(format_summary_report)


class TestDataDeleteBacktest:
    def test_delete_backtest_exists(self):
        from data import DataManager
        assert hasattr(DataManager, 'delete_backtest')
        assert callable(DataManager.delete_backtest)


# ==============================================================================
# _helpers 工具函数
# ==============================================================================

class TestReportHelpers:
    def test_na_str_none(self):
        from report.reports import _na_str
        assert _na_str(None) == 'N/A'

    def test_na_str_value(self):
        from report.reports import _na_str
        assert _na_str('hello') == 'hello'
        assert _na_str(123) == '123'

    def test_get_attr_dict(self):
        from report.reports import _get_attr
        d = {'a': 1, 'b': 2}
        assert _get_attr(d, 'a') == 1
        assert _get_attr(d, 'c', 'default') == 'default'
        assert _get_attr(d, 'missing') is None

    def test_get_attr_object(self):
        from report.reports import _get_attr
        class Obj:
            a = 10
            b = 20
        o = Obj()
        assert _get_attr(o, 'a') == 10
        assert _get_attr(o, 'c', 99) == 99
