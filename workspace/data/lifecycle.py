"""数据库初始化与关闭生命周期。"""

from .connection import bind_database, database, reset_database_binding
from .migrations import run_pending_migrations
from .models import (
    AccountLedgerEntry,
    Backtest,
    BacktestDaily,
    BacktestParam,
    BacktestTrade,
    ExportMetadata,
    OperationLog,
    PositionLedgerEntry,
    Run,
    RunStudy,
    SchemaInfo,
    TradeClearing,
)


def init_database(db_path: str, *, allow_aggressive_schema_migration: bool = False) -> None:
    """初始化数据库连接 + 执行版本化迁移。"""
    bind_database(db_path)
    database.create_tables(
        [
            Run,
            RunStudy,
            ExportMetadata,
            OperationLog,
            Backtest,
            BacktestParam,
            BacktestTrade,
            TradeClearing,
            AccountLedgerEntry,
            PositionLedgerEntry,
            BacktestDaily,
            SchemaInfo,
        ],
        safe=True,
    )  # pyright: ignore[reportUnknownMemberType]
    run_pending_migrations(
        allow_aggressive=allow_aggressive_schema_migration,
    )


def close_database() -> None:
    """关闭数据库连接并重置绑定。"""
    reset_database_binding()
