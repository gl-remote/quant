"""data/ 数据存储层测试

覆盖:
    - DataStore: 初始化、建表、操作日志、元数据
    - 操作日志自动清理 (pruning)
    - 回测记录完整 CRUD: 插入、查询、过滤、删除、级联
    - DataManager 基本接口
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from data import DataManager  # noqa: E402
from data.store import DataStore  # noqa: E402
from common.constants import STATUS_FAILED  # noqa: E402
from conftest import insert_full_backtest  # noqa: E402


# ═══════════════════════════════════════════════════════════
# DataStore 初始化 & 建表
# ═══════════════════════════════════════════════════════════

class TestDataStoreInit:
    def test_init_creates_file(self, temp_db_path):
        store = DataStore(temp_db_path)
        assert os.path.exists(temp_db_path)
        store.close()

    def test_tables_exist(self, temp_db_path):
        store = DataStore(temp_db_path)
        import sqlite3
        conn = sqlite3.connect(temp_db_path)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        conn.close()
        store.close()
        assert 'export_metadata' in tables
        assert 'operation_logs' in tables


# ═══════════════════════════════════════════════════════════
# 操作日志 & 元数据
# ═══════════════════════════════════════════════════════════

class TestOperationLogs:
    def test_log_and_retrieve(self, temp_db_path):
        store = DataStore(temp_db_path)
        store.log('backtest', 'test message', symbol='DCE.m2509', status='INFO')
        logs = store.get_logs(limit=10)
        assert len(logs) == 1
        assert logs[0]['command'] == 'backtest'
        assert logs[0]['symbol'] == 'DCE.m2509'
        assert logs[0]['message'] == 'test message'
        assert logs[0]['status'] == 'INFO'
        store.close()

    def test_log_multiple_entries(self, temp_db_path):
        store = DataStore(temp_db_path)
        for i in range(5):
            store.log('export', f'message {i}', symbol='TEST')
        logs = store.get_logs(limit=100)
        assert len(logs) == 5
        store.close()

    def test_get_logs_limit(self, temp_db_path):
        store = DataStore(temp_db_path)
        for i in range(10):
            store.log('cmd', f'msg {i}')
        logs = store.get_logs(limit=3)
        assert len(logs) == 3
        store.close()

    def test_logs_ordered_desc(self, temp_db_path):
        store = DataStore(temp_db_path)
        store.log('cmd', 'first')
        store.log('cmd', 'second')
        logs = store.get_logs(limit=100)
        assert logs[0]['message'] == 'second'
        assert logs[1]['message'] == 'first'
        store.close()


class TestMetadata:
    def test_get_nonexistent_metadata(self, temp_db_path):
        store = DataStore(temp_db_path)
        result = store.get_metadata('NONEXIST')
        assert result is None
        store.close()

    def test_upsert_insert(self, temp_db_path):
        store = DataStore(temp_db_path)
        store.upsert_metadata(
            'DCE.m2509',
            provider='tqsdk',
            interval='1m',
            filepath='/data/DCE.m2509.csv',
            start_date='2024-01-01',
            end_date='2024-12-31',
            min_dt='2024-01-02',
            max_dt='2024-12-30',
            total_rows=240,
        )
        meta = store.get_metadata('DCE.m2509')
        assert meta is not None
        assert meta['symbol'] == 'DCE.m2509'
        assert meta['provider'] == 'tqsdk'
        assert meta['interval'] == '1m'
        assert meta['total_rows'] == 240
        store.close()

    def test_upsert_update(self, temp_db_path):
        store = DataStore(temp_db_path)
        store.upsert_metadata(
            'DCE.m2509',
            provider='tqsdk',
            interval='1m',
            filepath='/data/old.csv',
            start_date='2024-01-01',
            end_date='2024-06-30',
            min_dt='2024-01-02',
            max_dt='2024-06-28',
            total_rows=120,
        )
        # 同 symbol+provider+interval → 更新
        store.upsert_metadata(
            'DCE.m2509',
            provider='tqsdk',
            interval='1m',
            filepath='/data/new.csv',
            start_date='2024-01-01',
            end_date='2024-12-31',
            min_dt='2024-01-02',
            max_dt='2024-12-30',
            total_rows=240,
        )
        meta = store.get_metadata('DCE.m2509')
        assert meta['total_rows'] == 240
        assert meta['filepath'] == '/data/new.csv'
        store.close()

    def test_upsert_different_providers(self, temp_db_path):
        """不同 provider 应共存"""
        store = DataStore(temp_db_path)
        store.upsert_metadata(
            'DCE.m2509', provider='tqsdk', interval='1m',
            filepath='/data/tqsdk_1m.csv',
            start_date='2024-01-01', end_date='2024-12-31',
            min_dt='2024-01-02', max_dt='2024-12-30', total_rows=10000,
        )
        store.upsert_metadata(
            'DCE.m2509', provider='akshare', interval='1m',
            filepath='/data/akshare_1m.csv',
            start_date='2024-01-01', end_date='2024-12-31',
            min_dt='2024-01-02', max_dt='2024-12-30', total_rows=5000,
        )
        # 查最新一条（不限 provider）
        meta = store.get_metadata('DCE.m2509')
        assert meta['provider'] == 'akshare'  # 后插入的
        # 按 provider 过滤
        meta_tq = store.get_metadata('DCE.m2509', provider='tqsdk')
        assert meta_tq['total_rows'] == 10000
        meta_ak = store.get_metadata('DCE.m2509', provider='akshare')
        assert meta_ak['total_rows'] == 5000
        store.close()


# ═══════════════════════════════════════════════════════════
# 操作日志清理
# ═══════════════════════════════════════════════════════════

class TestLogPruning:
    def test_no_prune_below_threshold(self, temp_db_path, monkeypatch):
        monkeypatch.setattr('common.constants.MAX_OPERATION_LOG_ROWS', 100)
        monkeypatch.setattr('common.constants.PRUNE_CHECK_INTERVAL', 1)
        store = DataStore(temp_db_path)
        for i in range(10):
            store.log('test', f'message {i}')
        logs = store.get_logs(limit=200)
        assert len(logs) == 10
        store.close()

    def test_prune_triggers_above_threshold(self, temp_db_path, monkeypatch):
        monkeypatch.setattr('common.constants.MAX_OPERATION_LOG_ROWS', 10)
        monkeypatch.setattr('common.constants.PRUNE_CHECK_INTERVAL', 1)
        store = DataStore(temp_db_path)
        for i in range(20):
            store.log('test', f'message {i}')
        logs = store.get_logs(limit=200)
        assert len(logs) < 20
        assert len(logs) <= 10
        assert 'message 19' in logs[0]['message']
        store.close()

    def test_multiple_prune_cycles(self, temp_db_path, monkeypatch):
        monkeypatch.setattr('common.constants.MAX_OPERATION_LOG_ROWS', 10)
        monkeypatch.setattr('common.constants.PRUNE_CHECK_INTERVAL', 1)
        store = DataStore(temp_db_path)
        for i in range(50):
            store.log('test', f'message {i}')
        logs = store.get_logs(limit=200)
        assert len(logs) <= 10
        assert 'message 49' in logs[0]['message']
        store.close()

    def test_prune_idempotent(self, temp_db_path, monkeypatch):
        monkeypatch.setattr('common.constants.MAX_OPERATION_LOG_ROWS', 10)
        store = DataStore(temp_db_path)
        for i in range(5):
            store.log('test', f'message {i}')
        assert store._prune_old_logs() >= 0
        assert store._prune_old_logs() >= 0
        store.close()


# ═══════════════════════════════════════════════════════════
# DataStore 回测 CRUD
# ═══════════════════════════════════════════════════════════

class TestInsertAndQuery:
    def test_insert_and_get_backtest(self, temp_db_path):
        store = DataStore(temp_db_path)
        bt_id = insert_full_backtest(store)
        bt = store.get_backtest(bt_id)
        assert bt is not None
        assert bt.symbol == 'DCE.m2509'
        assert bt.strategy == 'ma'
        assert bt.strategy_version == '1.0'
        assert bt.git_hash == 'abc1234'
        assert bt.start_date == '2024-01-01'
        assert bt.status == 'success'
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
        bt_id = insert_full_backtest(store)
        trades = store.query_trades(bt_id)
        assert len(trades) == 3
        assert trades[0].symbol == 'DCE.m2509'
        assert trades[1].pnl == -100.0
        store.close()

    def test_query_daily(self, temp_db_path):
        store = DataStore(temp_db_path)
        bt_id = insert_full_backtest(store)
        daily = store.query_daily(bt_id)
        assert len(daily) == 3
        assert daily[0]['equity'] == 100200.0
        assert daily[1]['daily_return'] == -100.0
        store.close()

    def test_query_backtests_filter(self, temp_db_path):
        store = DataStore(temp_db_path)
        insert_full_backtest(store, symbol='DCE.m2509')
        insert_full_backtest(store, symbol='DCE.rb2410', strategy='sma')
        all_bt = store.query_backtests(status='success', limit=50)
        assert len(all_bt) == 2
        filtered = store.query_backtests(symbol='DCE.m2509', status='success')
        assert len(filtered) == 1
        assert filtered[0].symbol == 'DCE.m2509'
        filtered = store.query_backtests(strategy='sma', status='success')
        assert len(filtered) == 1
        assert filtered[0].strategy == 'sma'
        filtered = store.query_backtests(symbol='NONEXIST', status='success')
        assert len(filtered) == 0
        store.close()

    def test_query_backtests_limit(self, temp_db_path):
        store = DataStore(temp_db_path)
        for i in range(5):
            insert_full_backtest(store, symbol=f'DCE.sym{i:02d}')
        results = store.query_backtests(status='success', limit=2)
        assert len(results) == 2
        store.close()

    def test_failed_backtest_ignored_by_default(self, temp_db_path):
        store = DataStore(temp_db_path)
        insert_full_backtest(store, symbol='DCE.good')
        store.insert_backtest_detailed(
            symbol='DCE.bad', strategy='ma', status=STATUS_FAILED,
            error_message='test error', statistics={}, engine_config={},
            params_json='{}', start_date=None, end_date=None,
        )
        results = store.query_backtests(status='success')
        assert len(results) == 1
        assert results[0].symbol == 'DCE.good'
        store.close()


# ═══════════════════════════════════════════════════════════
# DataStore 删除 & 级联
# ═══════════════════════════════════════════════════════════

class TestDeleteBacktest:
    def test_delete_removes_main_record(self, temp_db_path):
        store = DataStore(temp_db_path)
        bt_id = insert_full_backtest(store)
        assert store.get_backtest(bt_id) is not None
        ok = store.delete_backtest(bt_id)
        assert ok is True
        assert store.get_backtest(bt_id) is None
        store.close()

    def test_delete_cascades_trades(self, temp_db_path):
        store = DataStore(temp_db_path)
        bt_id = insert_full_backtest(store)
        assert len(store.query_trades(bt_id)) == 3
        store.delete_backtest(bt_id)
        assert len(store.query_trades(bt_id)) == 0
        store.close()

    def test_delete_cascades_daily(self, temp_db_path):
        store = DataStore(temp_db_path)
        bt_id = insert_full_backtest(store)
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
        bt_id = insert_full_backtest(store)
        store.delete_backtest(bt_id)
        ok = store.delete_backtest(bt_id)
        assert ok is False
        store.close()

    def test_delete_isolated(self, temp_db_path):
        store = DataStore(temp_db_path)
        id1 = insert_full_backtest(store, symbol='DCE.m2509')
        id2 = insert_full_backtest(store, symbol='DCE.rb2410')
        store.delete_backtest(id1)
        assert store.get_backtest(id2) is not None
        assert len(store.query_trades(id2)) == 3
        assert len(store.query_daily(id2)) == 3
        store.close()


# ═══════════════════════════════════════════════════════════
# DataManager 基本接口
# ═══════════════════════════════════════════════════════════

class TestDataManager:
    def test_get_symbol_info_not_found(self, temp_db_path):
        dm = DataManager()
        info = dm.get_symbol_info('NONEXISTENT')
        assert info.available is False
        dm.close()

    def test_delete_backtest_exists(self):
        assert hasattr(DataManager, 'delete_backtest')
        assert callable(DataManager.delete_backtest)
