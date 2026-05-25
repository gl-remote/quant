"""数据模块测试 - 测试 DataManager 和 DataStore"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
import logging
from data import DataManager
from data.store import DataStore
from common.constants import MAX_OPERATION_LOG_ROWS, PRUNE_CHECK_INTERVAL


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
        assert meta['total_rows'] == 240
        assert meta['start_date'] == '2024-01-01'
        store.close()

    def test_upsert_update(self, temp_db_path):
        store = DataStore(temp_db_path)
        store.upsert_metadata(
            'DCE.m2509',
            filepath='/data/old.csv',
            start_date='2024-01-01',
            end_date='2024-06-30',
            min_dt='2024-01-02',
            max_dt='2024-06-28',
            total_rows=120,
        )
        store.upsert_metadata(
            'DCE.m2509',
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


class TestLogPruning:
    """日志自动清理测试"""

    def test_no_prune_below_threshold(self, temp_db_path, monkeypatch):
        """未超过阈值时不触发清理"""
        monkeypatch.setattr('common.constants.MAX_OPERATION_LOG_ROWS', 100)
        monkeypatch.setattr('common.constants.PRUNE_CHECK_INTERVAL', 1)
        store = DataStore(temp_db_path)
        for i in range(10):
            store.log('test', f'message {i}')
        logs = store.get_logs(limit=200)
        assert len(logs) == 10
        store.close()

    def test_prune_triggers_above_threshold(self, temp_db_path, monkeypatch):
        """超过阈值后自动清理旧记录，总量被限制"""
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
        """多次清理周期后总量始终受控"""
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
        """手动多次调用 _prune_old_logs 不抛异常"""
        monkeypatch.setattr('common.constants.MAX_OPERATION_LOG_ROWS', 10)
        store = DataStore(temp_db_path)
        for i in range(5):
            store.log('test', f'message {i}')
        assert store._prune_old_logs() >= 0
        assert store._prune_old_logs() >= 0
        store.close()


class TestDataManager:
    """DataManager 测试"""

    def test_get_symbol_info_not_found(self, temp_db_path):
        """测试获取不存在的品种信息"""
        dm = DataManager()
        info = dm.get_symbol_info('NONEXISTENT')
        assert info.available is False
        dm.close()