"""测试 data/models.py — Pydantic 模型与 ORM 模型"""

import pytest
from data.models import (
    Backtest,
    BacktestDaily,
    BacktestRecord,
    BacktestTrade,
    DataLoadResult,
    DataSummary,
    ExportMetadata,
    OperationLog,
    RealtimeSession,
    RealtimeTrade,
    SymbolInfo,
    TradeRecord,
    close_database,
    get_live_session_model,
    get_live_trade_model,
    init_database,
)

# ==============================================================================
# BacktestRecord (Pydantic)
# ==============================================================================


class TestBacktestRecord:
    def test_create_minimal(self):
        """最少字段创建"""
        r = BacktestRecord(symbol="m2509", strategy="ma")
        assert r.symbol == "m2509"
        assert r.strategy == "ma"
        assert r.status == "success"
        assert r.total_return == 0.0

    def test_create_full(self):
        r = BacktestRecord(
            symbol="rb2410",
            strategy="ma",
            total_return=0.15,
            max_drawdown=0.08,
            win_rate=0.45,
            total_trades=100,
            win_trades=45,
            loss_trades=55,
            avg_win=50.0,
            avg_loss=-30.0,
        )
        assert r.win_rate == 0.45
        assert r.win_trades == 45
        assert r.avg_win == 50.0
        assert r.avg_loss == -30.0

    def test_to_dict_excludes_none(self):
        """model_dump 排除 None 值"""
        r = BacktestRecord(symbol="m2509", strategy="ma")
        d = r.model_dump(exclude_none=True)
        assert "symbol" in d
        assert "sharpe_ratio" not in d  # None, 应被排除

    def test_to_dict_includes_explicit_values(self):
        r = BacktestRecord(symbol="m2509", strategy="ma", sharpe_ratio=1.5)
        d = r.model_dump(exclude_none=True)
        assert d["sharpe_ratio"] == 1.5

    def test_from_dict(self):
        d = {
            "symbol": "m2509",
            "strategy": "ma",
            "total_return": 0.2,
            "total_trades": 50,
        }
        r = BacktestRecord.model_validate(d)
        assert r.symbol == "m2509"
        assert r.total_return == 0.2
        assert r.total_trades == 50

    def test_default_values(self):
        r = BacktestRecord(symbol="m2509", strategy="ma")
        assert r.status == "success"
        assert r.total_return == 0.0
        assert r.max_drawdown is None
        assert r.win_rate is None
        assert r.total_trades == 0
        assert r.win_trades is None
        assert r.loss_trades is None
        assert r.avg_win is None
        assert r.avg_loss is None

    def test_from_dict_maps_all_fields(self):
        """from_dict 正确映射 ORM 全部字段（含 2026-06-06 新增 15 个 vnpy 统计字段）"""
        orm_data = {
            "id": 1,
            "symbol": "DCE.m2509",
            "strategy": "ma",
            "status": "success",
            "total_return": 0.15,
            "win_rate": 0.6,
            "total_trades": 50,
            "win_trades": 30,
            "loss_trades": 20,
            "avg_win": 100.0,
            "avg_loss": -50.0,
            # 风险指标
            "sharpe_ratio": 1.2,
            "max_drawdown": 0.08,
            "max_ddpercent": 8.5,  # 2026-06-06新增
            "max_drawdown_duration": 15,
            "daily_std": 0.02,
            "return_drawdown_ratio": 1.5,
            # 盈亏汇总 [vnpy] (2026-06-06新增)
            "total_net_pnl": 15000.0,
            "daily_net_pnl": 41.1,
            "total_commission": 800.5,
            "daily_commission": 2.19,
            "total_slippage": 500.0,
            "daily_slippage": 1.37,
            "total_turnover": 2500000.0,
            "daily_turnover": 6849.32,
            # 交易日统计 [vnpy] (2026-06-06新增)
            "profit_days": 180,
            "loss_days": 170,
            "daily_trade_count": 0.14,
            "daily_return_pct": 0.041,
            # 进阶指标 [vnpy] (2026-06-06新增)
            "ewm_sharpe": 1.35,
            "rgr_ratio": 1.88,
            # 时间范围
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000.0,
            "end_balance": 115000.0,
            "annual_return": 0.15,
            "strategy_version": "1.0",
            "git_hash": "abc1234",
            "error_message": None,
            "created_at": "2024-06-01 10:00:00",
        }
        r = BacktestRecord.model_validate(orm_data)

        assert r.id == 1
        assert r.symbol == "DCE.m2509"
        assert r.total_return == 0.15
        assert r.win_rate == 0.6
        assert r.total_trades == 50
        assert r.win_trades == 30
        assert r.loss_trades == 20
        assert r.avg_win == 100.0
        assert r.avg_loss == -50.0
        assert r.sharpe_ratio == 1.2
        assert r.max_drawdown == 0.08
        # 2026-06-06 新增字段断言
        assert r.max_ddpercent == 8.5
        assert r.total_net_pnl == 15000.0
        assert r.daily_net_pnl == 41.1
        assert r.total_commission == 800.5
        assert r.daily_commission == 2.19
        assert r.total_slippage == 500.0
        assert r.daily_slippage == 1.37
        assert r.total_turnover == 2500000.0
        assert r.daily_turnover == 6849.32
        assert r.profit_days == 180
        assert r.loss_days == 170
        assert r.daily_trade_count == 0.14
        assert r.daily_return_pct == 0.041
        assert r.ewm_sharpe == 1.35
        assert r.rgr_ratio == 1.88
        assert r.start_date == "2024-01-01"
        assert r.end_date == "2024-12-31"
        assert r.initial_capital == 100000.0
        assert r.end_balance == 115000.0
        assert r.annual_return == 0.15
        assert r.daily_std == 0.02
        assert r.strategy_version == "1.0"
        assert r.git_hash == "abc1234"
        assert r.error_message is None


# ==============================================================================
# TradeRecord (Pydantic)
# ==============================================================================


class TestTradeRecord:
    def test_create_valid(self):
        t = TradeRecord(
            backtest_id=1,
            datetime="2024-01-15 10:00:00",
            symbol="m2509",
            direction="long",
            offset="open",
            open_price=3500.0,
            close_price=3550.0,
            price=3550.0,
            quantity=5,
            pnl=250.0,
        )
        assert t.direction == "long"
        assert t.quantity == 5

    def test_invalid_quantity_zero(self):
        with pytest.raises(ValueError, match="quantity must be greater than 0"):
            TradeRecord(
                backtest_id=1,
                datetime="2024-01-15",
                symbol="m2509",
                direction="long",
                open_price=3500.0,
                close_price=3550.0,
                price=3550.0,
                quantity=0,
                pnl=0.0,
            )

    def test_invalid_quantity_negative(self):
        with pytest.raises(ValueError, match="quantity must be greater than 0"):
            TradeRecord(
                backtest_id=1,
                datetime="2024-01-15",
                symbol="m2509",
                direction="long",
                open_price=3500.0,
                close_price=3550.0,
                price=3550.0,
                quantity=-1,
                pnl=0.0,
            )

    def test_invalid_commission_negative(self):
        with pytest.raises(ValueError, match="commission must be >= 0"):
            TradeRecord(
                backtest_id=1,
                datetime="2024-01-15",
                symbol="m2509",
                direction="long",
                open_price=3500.0,
                close_price=3550.0,
                price=3550.0,
                quantity=5,
                pnl=0.0,
                commission=-0.1,
            )

    def test_commission_zero_is_valid(self):
        t = TradeRecord(
            backtest_id=1,
            datetime="2024-01-15",
            symbol="m2509",
            direction="long",
            open_price=3500.0,
            close_price=3550.0,
            price=3550.0,
            quantity=5,
        )
        assert t.commission == 0.0

    def test_to_dict(self):
        t = TradeRecord(
            backtest_id=1,
            datetime="2024-01-15",
            symbol="m2509",
            direction="long",
            open_price=3500.0,
            close_price=3550.0,
            price=3550.0,
            quantity=5,
        )
        d = t.model_dump(exclude_none=True)
        assert d["symbol"] == "m2509"
        assert d["quantity"] == 5
        assert "pnl" in d
        assert d["pnl"] == 0.0  # default

    def test_from_dict(self):
        d = {
            "backtest_id": 2,
            "datetime": "2024-02-01",
            "symbol": "rb2410",
            "direction": "short",
            "open_price": 4000.0,
            "close_price": 3900.0,
            "price": 3900.0,
            "quantity": 3,
            "pnl": 300.0,
        }
        t = TradeRecord.model_validate(d)
        assert t.symbol == "rb2410"
        assert t.pnl == 300.0
        assert t.offset == "open"  # default


# ==============================================================================
# SymbolInfo / DataSummary / DataLoadResult (Pydantic)
# ==============================================================================


class TestSymbolInfo:
    def test_create(self):
        s = SymbolInfo(symbol="m2509", available=True)
        assert s.symbol == "m2509"
        assert s.available is True

    def test_unavailable_with_error(self):
        s = SymbolInfo(symbol="invalid", available=False, error="File not found")
        assert s.available is False
        assert s.error == "File not found"


class TestDataSummary:
    def test_create(self):
        symbols = [
            SymbolInfo(symbol="m2509", available=True),
            SymbolInfo(symbol="rb2410", available=True),
        ]
        ds = DataSummary(total_symbols=2, symbols=symbols)
        assert ds.total_symbols == 2
        assert len(ds.symbols) == 2


class TestDataLoadResult:
    def test_success(self):
        r = DataLoadResult(
            success=True,
            symbol="m2509",
            start_date="2024-01-01",
            end_date="2024-12-31",
            row_count=5000,
            message="OK",
        )
        assert r.success is True
        assert r.row_count == 5000

    def test_failed(self):
        r = DataLoadResult(success=False, symbol="invalid", message="No data")
        assert r.success is False
        assert r.row_count == 0
        assert r.start_date is None


# ==============================================================================
# ORM 模型 (数据库依赖，仅测试基础属性)
# ==============================================================================


class TestOrmModels:
    """ORM 模型基本属性测试 (不依赖数据库连接)"""

    def test_export_metadata_table_name(self):
        assert ExportMetadata._meta.table_name == "export_metadata"

    def test_operation_log_table_name(self):
        assert OperationLog._meta.table_name == "operation_logs"

    def test_backtest_table_name(self):
        assert Backtest._meta.table_name == "backtests"

    def test_backtest_trade_table_name(self):
        assert BacktestTrade._meta.table_name == "backtest_trades"

    def test_backtest_daily_table_name(self):
        assert BacktestDaily._meta.table_name == "backtest_daily"

    def test_realtime_table_names(self):
        assert RealtimeSession._meta.table_name == "realtime_sessions"
        assert RealtimeTrade._meta.table_name == "realtime_trades"

    def test_legacy_realtime_model_factories_return_unified_models(self):
        assert get_live_session_model("test_sessions") is RealtimeSession
        assert get_live_session_model("live_sessions") is RealtimeSession
        assert get_live_trade_model("test_trades") is RealtimeTrade
        assert get_live_trade_model("live_trades") is RealtimeTrade

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
            assert "export_metadata" in tables
            assert "operation_logs" in tables
            assert "backtests" in tables
            assert "backtest_trades" in tables
            assert "backtest_daily" in tables
        finally:
            close_database()

    def test_realtime_models_create_unified_tables(self, temp_db_path):
        """实时链路在不同环境 DB 内使用统一 realtime 表名。"""
        init_database(temp_db_path)
        try:
            RealtimeSession._meta.database.create_tables([RealtimeSession, RealtimeTrade], safe=True)
            tables = RealtimeSession._meta.database.get_tables()
            assert "realtime_sessions" in tables
            assert "realtime_trades" in tables
            assert "test_sessions" not in tables
            assert "live_sessions" not in tables
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
