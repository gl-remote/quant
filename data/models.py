# -*- coding: utf-8 -*-
"""数据类型定义模块

包含：
1. Pandera DataFrameSchema - 从 common.schemas 导入（全局统一）
2. Pydantic BaseModel - 用于单条记录的验证
3. ORM 模型 - 内部数据库模型（不对外暴露）
"""

from pydantic import BaseModel, field_validator

from peewee import (
    Model, SqliteDatabase,
    CharField, DateField, IntegerField, FloatField, TextField, DateTimeField,
    ForeignKeyField, SQL,
)

# 从 common.schemas 导入 Pandera Schema，供 manager.py 等上层模块引用
# 注：此 import 作为 re-export 供上层模块使用
from common.schemas import KlineSchema  # noqa: F401  # pyright: ignore[reportUnusedImport]

# ==============================================================================
# Pydantic 模型（对外暴露，用于单条记录验证）
# ==============================================================================


class BacktestRecord(BaseModel):
    """回测记录 — 字段与 ORM Backtest 表保持一致"""
    id: int | None = None
    symbol: str
    strategy: str
    strategy_version: str | None = None
    git_hash: str | None = None
    status: str = "success"
    error_message: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    total_days: int | None = None
    initial_capital: float = 0.0
    end_balance: float | None = None
    total_return: float = 0.0
    annual_return: float | None = None
    total_trades: int = 0
    win_trades: int | None = None
    loss_trades: int | None = None
    win_rate: float = 0.0
    max_consecutive_win: int | None = None
    max_consecutive_loss: int | None = None
    avg_win: float | None = None
    avg_loss: float | None = None
    win_loss_ratio: float | None = None
    sharpe_ratio: float | None = None
    max_drawdown: float = 0.0
    max_drawdown_duration: int | None = None
    daily_std: float | None = None
    return_drawdown_ratio: float | None = None
    created_at: str | None = None


class TradeRecord(BaseModel):
    """交易记录"""
    id: int | None = None
    backtest_id: int
    datetime: str
    symbol: str
    direction: str
    offset: str = "open"
    open_price: float
    close_price: float
    quantity: int
    pnl: float = 0.0
    commission: float = 0.0
    created_at: str | None = None

    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v: int) -> int:
        if v <= 0:
            raise ValueError('quantity must be greater than 0')
        return v

    @field_validator('commission')
    @classmethod
    def validate_commission(cls, v: float) -> float:
        if v < 0:
            raise ValueError('commission must be >= 0')
        return v


class SymbolInfo(BaseModel):
    """品种信息"""
    symbol: str
    available: bool
    filepath: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    total_rows: int | None = None
    error: str | None = None


class DataSummary(BaseModel):
    """数据汇总"""
    total_symbols: int
    symbols: list[SymbolInfo]


class DataLoadResult(BaseModel):
    """数据加载结果"""
    success: bool
    symbol: str
    start_date: str | None = None
    end_date: str | None = None
    row_count: int = 0
    message: str


# ==============================================================================
# ORM 模型（内部使用，不对外暴露）
# ==============================================================================

database = SqliteDatabase(None)


class OrmBaseModel(Model):
    """基础模型"""
    class Meta:
        database: SqliteDatabase = database


class ExportMetadata(OrmBaseModel):
    """导出元数据"""
    symbol: CharField = CharField(unique=True)
    filepath: CharField = CharField()
    start_date: DateField = DateField(null=True)
    end_date: DateField = DateField(null=True)
    min_dt: DateField = DateField(null=True)
    max_dt: DateField = DateField(null=True)
    total_rows: IntegerField = IntegerField(default=0)
    created_at: DateTimeField = DateTimeField(constraints=[SQL('DEFAULT CURRENT_TIMESTAMP')])
    updated_at: DateTimeField = DateTimeField(null=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table_name: str = 'export_metadata'


class OperationLog(OrmBaseModel):
    """操作日志"""
    command: CharField = CharField()
    symbol: CharField = CharField(null=True)
    message: TextField = TextField()
    status: CharField = CharField()
    created_at: DateTimeField = DateTimeField(constraints=[SQL('DEFAULT CURRENT_TIMESTAMP')])

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table_name: str = 'operation_logs'


class Backtest(OrmBaseModel):
    """回测记录（与数据库表结构保持一致）"""
    symbol: CharField = CharField()
    strategy: CharField = CharField()
    strategy_version: CharField = CharField(null=True)  # 策略版本号
    git_hash: CharField = CharField(null=True)          # 回测时的 Git 提交哈希
    status: CharField = CharField()
    error_message: TextField = TextField(null=True)
    start_date: CharField = CharField(null=True, max_length=10)
    end_date: CharField = CharField(null=True, max_length=10)
    total_days: IntegerField = IntegerField(null=True)
    initial_capital: FloatField = FloatField()
    commission_rate: FloatField = FloatField(null=True)
    slippage: FloatField = FloatField(null=True)
    price_tick: FloatField = FloatField(null=True)
    contract_size: IntegerField = IntegerField(null=True)
    kline_interval: CharField = CharField(null=True, max_length=8)
    params_json: TextField = TextField(null=True)
    end_balance: FloatField = FloatField(null=True)
    total_return: FloatField = FloatField(null=True)
    annual_return: FloatField = FloatField(null=True)
    total_trades: IntegerField = IntegerField(null=True)
    win_trades: IntegerField = IntegerField(null=True)
    loss_trades: IntegerField = IntegerField(null=True)
    win_rate: FloatField = FloatField(null=True)
    max_consecutive_win: IntegerField = IntegerField(null=True)
    max_consecutive_loss: IntegerField = IntegerField(null=True)
    avg_win: FloatField = FloatField(null=True)
    avg_loss: FloatField = FloatField(null=True)
    win_loss_ratio: FloatField = FloatField(null=True)
    sharpe_ratio: FloatField = FloatField(null=True)
    max_drawdown: FloatField = FloatField(null=True)
    max_drawdown_duration: IntegerField = IntegerField(null=True)
    daily_std: FloatField = FloatField(null=True)
    return_drawdown_ratio: FloatField = FloatField(null=True)
    created_at: DateTimeField = DateTimeField(constraints=[SQL('DEFAULT CURRENT_TIMESTAMP')])
    updated_at: DateTimeField = DateTimeField(constraints=[SQL('DEFAULT CURRENT_TIMESTAMP')])

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table_name: str = 'backtests'


class BacktestTrade(OrmBaseModel):
    """回测交易明细"""
    backtest: ForeignKeyField = ForeignKeyField(Backtest, backref='trades', on_delete='CASCADE')
    datetime: DateTimeField = DateTimeField()
    symbol: CharField = CharField()
    direction: CharField = CharField()
    offset: CharField = CharField()
    open_price: FloatField = FloatField()
    close_price: FloatField = FloatField()
    quantity: IntegerField = IntegerField()
    pnl: FloatField = FloatField()
    commission: FloatField = FloatField()
    created_at: DateTimeField = DateTimeField(constraints=[SQL('DEFAULT CURRENT_TIMESTAMP')])

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table_name: str = 'backtest_trades'


class BacktestDaily(OrmBaseModel):
    """回测每日资金曲线"""
    backtest: ForeignKeyField = ForeignKeyField(Backtest, backref='daily', on_delete='CASCADE')
    date: DateField = DateField()
    equity: FloatField = FloatField()  # 当日资金净值
    daily_return: FloatField = FloatField()  # 当日收益率
    drawdown: FloatField = FloatField()  # 当日回撤
    created_at: DateTimeField = DateTimeField(constraints=[SQL('DEFAULT CURRENT_TIMESTAMP')])

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table_name: str = 'backtest_daily'


def init_database(db_path: str):
    """初始化数据库连接"""
    database.init(db_path)  # pyright: ignore[reportUnknownMemberType]
    database.create_tables([ExportMetadata, OperationLog, Backtest, BacktestTrade, BacktestDaily], safe=True)  # pyright: ignore[reportUnknownMemberType]


def close_database():
    """关闭数据库连接"""
    if not database.is_closed():
        _ = database.close()
