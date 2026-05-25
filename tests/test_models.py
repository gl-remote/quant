"""测试 data/models.py — Pydantic 模型与 ORM 模型"""

import pytest
from datetime import datetime

from data.models import (
    BacktestRecord,
    TradeRecord,
    SymbolInfo,
    DataSummary,
    DataLoadResult,
    init_database,
    close_database,
    ExportMetadata,
    OperationLog,
    Backtest,
    BacktestTrade,
    BacktestDaily,
)


# ==============================================================================
# BacktestRecord (Pydantic)
# ==============================================================================

class TestBacktestRecord:
    def test_create_minimal(self):
        """最少字段创建"""
        r = BacktestRecord(symbol='m2509', strategy='ma')
        assert r.symbol == 'm2509'
        assert r.strategy == 'ma'
        assert r.status == 'success'
        assert r.total_return == 0.0

    def test_create_full(self):
        r = BacktestRecord(
            symbol='rb2410',
            strategy='ma',
            total_return=0.15,
            max_drawdown=0.08,
            win_rate=0.45,
            profit_factor=1.8,
            total_trades=100,
            profit_trades=45,
            loss_trades=55,
            avg_profit=50.0,
            avg_loss=-30.0,
        )
        assert r.win_rate == 0.45
        assert r.profit_factor == 1.8

    def test_to_dict_excludes_none(self):
        """to_dict 排除 None 值"""
        r = BacktestRecord(symbol='m2509', strategy='ma')
        d = r.to_dict()
        assert 'symbol' in d
        assert 'sharpe_ratio' not in d  # None, 应被排除

    def test_to_dict_includes_explicit_values(self):
        r = BacktestRecord(symbol='m2509', strategy='ma', sharpe_ratio=1.5)
        d = r.to_dict()
        assert d['sharpe_ratio'] == 1.5

    def test_from_dict(self):
        d = {
            'symbol': 'm2509',
            'strategy': 'ma',
            'total_return': 0.2,
            'total_trades': 50,
        }
        r = BacktestRecord.from_dict(d)
        assert r.symbol == 'm2509'
        assert r.total_return == 0.2
        assert r.total_trades == 50

    def test_default_values(self):
        r = BacktestRecord(symbol='m2509', strategy='ma')
        assert r.status == 'success'
        assert r.total_return == 0.0
        assert r.max_drawdown == 0.0
        assert r.win_rate == 0.0
        assert r.profit_factor == 0.0
        assert r.total_trades == 0
        assert r.profit_trades == 0
        assert r.loss_trades == 0


# ==============================================================================
# TradeRecord (Pydantic)
# ==============================================================================

class TestTradeRecord:
    def test_create_valid(self):
        t = TradeRecord(
            backtest_id=1,
            datetime='2024-01-15 10:00:00',
            symbol='m2509',
            direction='long',
            offset='open',
            open_price=3500.0,
            close_price=3550.0,
            quantity=5,
            pnl=250.0,
        )
        assert t.direction == 'long'
        assert t.quantity == 5

    def test_invalid_quantity_zero(self):
        with pytest.raises(ValueError, match='quantity must be greater than 0'):
            TradeRecord(
                backtest_id=1,
                datetime='2024-01-15',
                symbol='m2509',
                direction='long',
                open_price=3500.0,
                close_price=3550.0,
                quantity=0,
                pnl=0.0,
            )

    def test_invalid_quantity_negative(self):
        with pytest.raises(ValueError, match='quantity must be greater than 0'):
            TradeRecord(
                backtest_id=1,
                datetime='2024-01-15',
                symbol='m2509',
                direction='long',
                open_price=3500.0,
                close_price=3550.0,
                quantity=-1,
                pnl=0.0,
            )

    def test_invalid_commission_negative(self):
        with pytest.raises(ValueError, match='commission must be >= 0'):
            TradeRecord(
                backtest_id=1,
                datetime='2024-01-15',
                symbol='m2509',
                direction='long',
                open_price=3500.0,
                close_price=3550.0,
                quantity=5,
                pnl=0.0,
                commission=-0.1,
            )

    def test_commission_zero_is_valid(self):
        t = TradeRecord(
            backtest_id=1,
            datetime='2024-01-15',
            symbol='m2509',
            direction='long',
            open_price=3500.0,
            close_price=3550.0,
            quantity=5,
            pnl=0.0,
            commission=0.0,
        )
        assert t.commission == 0.0

    def test_to_dict(self):
        t = TradeRecord(
            backtest_id=1,
            datetime='2024-01-15',
            symbol='m2509',
            direction='long',
            open_price=3500.0,
            close_price=3550.0,
            quantity=5,
        )
        d = t.to_dict()
        assert d['symbol'] == 'm2509'
        assert d['quantity'] == 5
        assert 'pnl' in d
        assert d['pnl'] == 0.0  # default

    def test_from_dict(self):
        d = {
            'backtest_id': 2,
            'datetime': '2024-02-01',
            'symbol': 'rb2410',
            'direction': 'short',
            'open_price': 4000.0,
            'close_price': 3900.0,
            'quantity': 3,
            'pnl': 300.0,
        }
        t = TradeRecord.from_dict(d)
        assert t.symbol == 'rb2410'
        assert t.pnl == 300.0
        assert t.offset == 'open'  # default


# ==============================================================================
# SymbolInfo / DataSummary / DataLoadResult (Pydantic)
# ==============================================================================

class TestSymbolInfo:
    def test_create(self):
        s = SymbolInfo(symbol='m2509', available=True)
        assert s.symbol == 'm2509'
        assert s.available is True

    def test_unavailable_with_error(self):
        s = SymbolInfo(symbol='invalid', available=False, error='File not found')
        assert s.available is False
        assert s.error == 'File not found'


class TestDataSummary:
    def test_create(self):
        symbols = [
            SymbolInfo(symbol='m2509', available=True),
            SymbolInfo(symbol='rb2410', available=True),
        ]
        ds = DataSummary(total_symbols=2, symbols=symbols)
        assert ds.total_symbols == 2
        assert len(ds.symbols) == 2


class TestDataLoadResult:
    def test_success(self):
        r = DataLoadResult(
            success=True,
            symbol='m2509',
            start_date='2024-01-01',
            end_date='2024-12-31',
            row_count=5000,
            message='OK',
        )
        assert r.success is True
        assert r.row_count == 5000

    def test_failed(self):
        r = DataLoadResult(success=False, symbol='invalid', message='No data')
        assert r.success is False
        assert r.row_count == 0
        assert r.start_date is None


# ==============================================================================
# ORM 模型 (数据库依赖，仅测试基础属性)
# ==============================================================================

class TestOrmModels:
    """ORM 模型基本属性测试 (不依赖数据库连接)"""

    def test_export_metadata_table_name(self):
        assert ExportMetadata._meta.table_name == 'export_metadata'

    def test_operation_log_table_name(self):
        assert OperationLog._meta.table_name == 'operation_logs'

    def test_backtest_table_name(self):
        assert Backtest._meta.table_name == 'backtests'

    def test_backtest_trade_table_name(self):
        assert BacktestTrade._meta.table_name == 'backtest_trades'

    def test_backtest_daily_table_name(self):
        assert BacktestDaily._meta.table_name == 'backtest_daily'

    def test_backtest_trade_foreign_key(self):
        """BacktestTrade 有外键关联 Backtest"""
        fk_field = BacktestTrade.backtest
        assert fk_field.rel_model == Backtest


# ==============================================================================
# init_database / close_database
# ==============================================================================

class TestDatabaseInit:
    """数据库初始化测试"""

    def test_init_and_close(self, temp_db_path):
        """创建和关闭数据库"""
        init_database(temp_db_path)
        try:
            # 验证表已创建 (peewee SqliteDatabase.get_tables 返回字符串列表)
            tables = ExportMetadata._meta.database.get_tables()
            assert 'export_metadata' in tables
            assert 'operation_logs' in tables
            assert 'backtests' in tables
            assert 'backtest_trades' in tables
            assert 'backtest_daily' in tables
        finally:
            close_database()

    def test_double_close_safe(self, temp_db_path):
        """重复 close 不报错"""
        init_database(temp_db_path)
        close_database()
        close_database()  # 不应抛出异常

    def test_init_twice_safe(self, temp_db_path):
        """重复 init 不报错 (safe=True)"""
        init_database(temp_db_path)
        try:
            init_database(temp_db_path)  # safe=True 下安全
        finally:
            close_database()
