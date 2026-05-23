"""数据库模块测试"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
import logging
import io
from data.database import Database, DBLogHandler


class TestDatabaseInit:
    def test_init_creates_file(self, temp_db_path):
        db = Database(temp_db_path)
        assert os.path.exists(temp_db_path)

    def test_tables_exist(self, temp_db_path):
        db = Database(temp_db_path)
        import sqlite3
        conn = sqlite3.connect(temp_db_path)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        conn.close()
        assert 'export_metadata' in tables
        assert 'operation_logs' in tables


class TestOperationLogs:
    def test_log_and_retrieve(self, temp_db_path):
        db = Database(temp_db_path)
        db.log('backtest', 'test message', symbol='DCE.m2509', status='INFO')
        logs = db.get_logs(limit=10)
        assert len(logs) == 1
        assert logs[0]['command'] == 'backtest'
        assert logs[0]['symbol'] == 'DCE.m2509'
        assert logs[0]['message'] == 'test message'
        assert logs[0]['status'] == 'INFO'

    def test_log_multiple_entries(self, temp_db_path):
        db = Database(temp_db_path)
        for i in range(5):
            db.log('export', f'message {i}', symbol='TEST')
        logs = db.get_logs(limit=100)
        assert len(logs) == 5

    def test_get_logs_limit(self, temp_db_path):
        db = Database(temp_db_path)
        for i in range(10):
            db.log('cmd', f'msg {i}')
        logs = db.get_logs(limit=3)
        assert len(logs) == 3

    def test_logs_ordered_desc(self, temp_db_path):
        db = Database(temp_db_path)
        db.log('cmd', 'first')
        db.log('cmd', 'second')
        logs = db.get_logs(limit=100)
        assert logs[0]['message'] == 'second'
        assert logs[1]['message'] == 'first'


class TestMetadata:
    def test_get_nonexistent_metadata(self, temp_db_path):
        db = Database(temp_db_path)
        result = db.get_metadata('NONEXIST')
        assert result is None

    def test_upsert_insert(self, temp_db_path):
        db = Database(temp_db_path)
        db.upsert_metadata(
            'DCE.m2509',
            filepath='/data/DCE.m2509.csv',
            start_date='2024-01-01',
            end_date='2024-12-31',
            min_dt='2024-01-02',
            max_dt='2024-12-30',
            total_rows=240,
        )
        meta = db.get_metadata('DCE.m2509')
        assert meta is not None
        assert meta['symbol'] == 'DCE.m2509'
        assert meta['total_rows'] == 240
        assert meta['start_date'] == '2024-01-01'

    def test_upsert_update(self, temp_db_path):
        db = Database(temp_db_path)
        db.upsert_metadata(
            'DCE.m2509',
            filepath='/data/old.csv',
            start_date='2024-01-01',
            end_date='2024-06-30',
            min_dt='2024-01-02',
            max_dt='2024-06-28',
            total_rows=120,
        )
        db.upsert_metadata(
            'DCE.m2509',
            filepath='/data/new.csv',
            start_date='2024-01-01',
            end_date='2024-12-31',
            min_dt='2024-01-02',
            max_dt='2024-12-30',
            total_rows=240,
        )
        meta = db.get_metadata('DCE.m2509')
        assert meta['total_rows'] == 240
        assert meta['filepath'] == '/data/new.csv'


class TestDBLogHandler:
    def test_emit_info_log(self, temp_db_path):
        db = Database(temp_db_path)
        handler = DBLogHandler(db, command='test_cmd', symbol='SYM')
        logger = logging.getLogger('test_logger')
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.info('handler test message')
        logger.removeHandler(handler)

        logs = db.get_logs(limit=1)
        assert len(logs) == 1
        assert logs[0]['command'] == 'test_cmd'
        assert 'handler test message' in logs[0]['message']

    def test_emit_error_log(self, temp_db_path):
        db = Database(temp_db_path)
        handler = DBLogHandler(db, command='error_cmd')
        logger = logging.getLogger('test_error_logger')
        logger.addHandler(handler)
        logger.setLevel(logging.ERROR)
        logger.error('critical failure')
        logger.removeHandler(handler)

        logs = db.get_logs(limit=1)
        assert logs[0]['status'] == 'ERROR'

    def test_emit_debug_maps_to_info(self, temp_db_path):
        db = Database(temp_db_path)
        handler = DBLogHandler(db, command='debug_cmd')
        logger = logging.getLogger('test_debug_logger')
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.debug('debug info')
        logger.removeHandler(handler)

        logs = db.get_logs(limit=1)
        assert logs[0]['status'] == 'INFO'