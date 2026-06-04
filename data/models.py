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
    run: int | None = None   # peewee FK 字段名是 run，存的是 run_id 值
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
    win_rate: float | None = None
    max_consecutive_win: int | None = None
    max_consecutive_loss: int | None = None
    avg_win: float | None = None
    avg_loss: float | None = None
    win_loss_ratio: float | None = None
    sharpe_ratio: float | None = None
    max_drawdown: float | None = None
    max_drawdown_duration: int | None = None
    daily_std: float | None = None
    return_drawdown_ratio: float | None = None
    created_at: str | None = None
    data_src: str | None = None


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
    quantity: float
    pnl: float = 0.0
    commission: float = 0.0
    created_at: str | None = None

    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v: float) -> float:
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
    """导出元数据 — 联合唯一键 (symbol, provider, interval)"""
    symbol: CharField = CharField()
    provider: CharField = CharField()        # 数据源: tqsdk / akshare
    interval: CharField = CharField()        # K线周期: 1m / 5m / 1d / ...
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
        indexes = (
            (('symbol', 'provider', 'interval'), True),  # 联合唯一约束
        )


class OperationLog(OrmBaseModel):
    """操作日志"""
    command: CharField = CharField()
    symbol: CharField = CharField(null=True)
    message: TextField = TextField()
    status: CharField = CharField()
    created_at: DateTimeField = DateTimeField(constraints=[SQL('DEFAULT CURRENT_TIMESTAMP')])

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table_name: str = 'operation_logs'


class Run(OrmBaseModel):
    """批量回测运行记录 — 每次跑回测一条"""
    strategy: CharField = CharField()
    engine: CharField = CharField(default="grid")
    symbols: IntegerField = IntegerField(default=0)
    status: CharField = CharField(default="running")
    use_fixed_seed: IntegerField = IntegerField(default=0)  # 0=false, 1=true
    random_seed: IntegerField = IntegerField(null=True)
    created_at: DateTimeField = DateTimeField(constraints=[SQL('DEFAULT CURRENT_TIMESTAMP')])

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table_name: str = 'runs'


class RunStudy(OrmBaseModel):
    """关联 runs 与 Optuna studies"""
    run: ForeignKeyField = ForeignKeyField(Run, backref='studies', on_delete='CASCADE')
    study_name: CharField = CharField(unique=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table_name: str = 'run_studies'


class Backtest(OrmBaseModel):
    """回测记录（与数据库表结构保持一致）"""
    run: ForeignKeyField = ForeignKeyField(Run, backref='backtests', null=True, on_delete='SET NULL')
    symbol: CharField = CharField()
    strategy: CharField = CharField()
    strategy_version: CharField = CharField(null=True)
    git_hash: CharField = CharField(null=True)
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
    engine_config: TextField = TextField(null=True)  # JSON: 引擎类型、优化器、study名等元数据
    created_at: DateTimeField = DateTimeField(constraints=[SQL('DEFAULT CURRENT_TIMESTAMP')])
    updated_at: DateTimeField = DateTimeField(constraints=[SQL('DEFAULT CURRENT_TIMESTAMP')])
    data_src: TextField = TextField(null=True)

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table_name: str = 'backtests'


class BacktestParam(OrmBaseModel):
    """回测参数 — 每个参数一行，与 backtest_id 关联"""
    backtest: ForeignKeyField = ForeignKeyField(Backtest, backref='params', on_delete='CASCADE')
    param_name: CharField = CharField()
    param_value: FloatField = FloatField()

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table_name: str = 'backtest_params'


class BacktestTrade(OrmBaseModel):
    """回测交易明细（逐笔成交记录）

    注意: vnpy 的 TradeData 代表单笔成交(fill)，不是完整交易(trade)。
    单笔成交中 open_price 和 close_price 取同一值 price。
    完整交易的开仓价/平仓价需要策略层按 offset=open/close 配对组装。
    """
    backtest: ForeignKeyField = ForeignKeyField(Backtest, backref='trades', on_delete='CASCADE')
    datetime: DateTimeField = DateTimeField()
    symbol: CharField = CharField()
    direction: CharField = CharField()
    offset: CharField = CharField()
    open_price: FloatField = FloatField()  # 成交价（开仓时=入场价，平仓时=出场价）
    close_price: FloatField = FloatField()  # 同上，单笔成交时与 open_price 相同
    quantity: FloatField = FloatField()
    pnl: FloatField = FloatField()
    commission: FloatField = FloatField()
    reason: CharField = CharField(max_length=32, default='')
    created_at: DateTimeField = DateTimeField(constraints=[SQL('DEFAULT CURRENT_TIMESTAMP')])

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table_name: str = 'backtest_trades'


class BacktestDaily(OrmBaseModel):
    """回测每日资金曲线

    注意: daily_return 字段实际存储的是当日净盈亏金额(net_pnl)，
    而非百分比收益率。字段名保留 historical compatibility。
    """
    backtest: ForeignKeyField = ForeignKeyField(Backtest, backref='daily', on_delete='CASCADE')
    date: DateField = DateField()
    equity: FloatField = FloatField()  # 当日权益
    daily_return: FloatField = FloatField()  # 当日净盈亏(金额)，非百分比
    drawdown: FloatField = FloatField()  # 当日回撤
    created_at: DateTimeField = DateTimeField(constraints=[SQL('DEFAULT CURRENT_TIMESTAMP')])

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        table_name: str = 'backtest_daily'


def init_database(db_path: str) -> None:
    """初始化数据库连接"""
    database.init(db_path)  # pyright: ignore[reportUnknownMemberType]
    database.create_tables([Run, RunStudy, ExportMetadata, OperationLog, Backtest, BacktestParam, BacktestTrade, BacktestDaily], safe=True)  # pyright: ignore[reportUnknownMemberType]


def close_database() -> None:
    """关闭数据库连接"""
    if not database.is_closed():
        _ = database.close()
