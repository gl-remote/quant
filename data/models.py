# -*- coding: utf-8 -*-
"""数据类型定义模块

包含：
1. Pandera DataFrameSchema - 从 common.schemas 导入（全局统一）
2. Pydantic BaseModel - 用于单条记录的验证
3. ORM 模型 - 内部数据库模型（不对外暴露）
"""

from pydantic import BaseModel, field_validator
from typing import Optional, List, Dict
from peewee import *

# 从 common.schemas 导入全局统一的 Pandera Schema
from common.schemas import (
    KlineSchema,
    TradeRecordSchema,
    BacktestResultSchema,
)

# ==============================================================================
# Pydantic 模型（对外暴露，用于单条记录验证）
# ==============================================================================

class BacktestRecord(BaseModel):
    """回测记录"""
    id: Optional[int] = None
    symbol: str
    strategy: str
    status: str = "success"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    total_return: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    total_trades: int = 0
    profit_trades: int = 0
    loss_trades: int = 0
    avg_profit: float = 0.0
    avg_loss: float = 0.0
    created_at: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return self.model_dump(exclude_none=True)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "BacktestRecord":
        """从字典创建"""
        return cls(**data)


class TradeRecord(BaseModel):
    """交易记录"""
    id: Optional[int] = None
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
    created_at: Optional[str] = None
    
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
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return self.model_dump(exclude_none=True)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "TradeRecord":
        """从字典创建"""
        return cls(**data)


class SymbolInfo(BaseModel):
    """品种信息"""
    symbol: str
    available: bool
    filepath: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    total_rows: Optional[int] = None
    error: Optional[str] = None


class DataSummary(BaseModel):
    """数据汇总"""
    total_symbols: int
    symbols: List[SymbolInfo]


class DataLoadResult(BaseModel):
    """数据加载结果"""
    success: bool
    symbol: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    row_count: int = 0
    message: str


# ==============================================================================
# ORM 模型（内部使用，不对外暴露）
# ==============================================================================

database = SqliteDatabase(None)


class BaseModel(Model):
    """基础模型"""
    class Meta:
        database = database


class ExportMetadata(BaseModel):
    """导出元数据"""
    symbol = CharField(unique=True)
    filepath = CharField()
    start_date = DateField(null=True)
    end_date = DateField(null=True)
    min_dt = DateField(null=True)
    max_dt = DateField(null=True)
    total_rows = IntegerField(default=0)
    created_at = DateTimeField(constraints=[SQL('DEFAULT CURRENT_TIMESTAMP')])
    updated_at = DateTimeField(null=True)
    
    class Meta:
        table_name = 'export_metadata'


class OperationLog(BaseModel):
    """操作日志"""
    command = CharField()
    symbol = CharField(null=True)
    message = TextField()
    status = CharField()
    created_at = DateTimeField(constraints=[SQL('DEFAULT CURRENT_TIMESTAMP')])
    
    class Meta:
        table_name = 'operation_logs'


class Backtest(BaseModel):
    """回测记录（与数据库表结构保持一致）"""
    symbol = CharField()
    strategy = CharField()
    status = CharField()
    error_message = TextField(null=True)
    data_start_date = CharField(null=True, max_length=10)
    data_end_date = CharField(null=True, max_length=10)
    start_date = CharField(null=True, max_length=10)
    end_date = CharField(null=True, max_length=10)
    total_days = IntegerField(null=True)
    initial_capital = FloatField()
    commission_rate = FloatField(null=True)
    slippage = FloatField(null=True)
    price_tick = FloatField(null=True)
    contract_size = IntegerField(null=True)
    kline_interval = CharField(null=True, max_length=8)
    params_json = TextField(null=True)
    end_balance = FloatField(null=True)
    total_return = FloatField(null=True)
    annual_return = FloatField(null=True)
    total_trades = IntegerField(null=True)
    win_trades = IntegerField(null=True)
    loss_trades = IntegerField(null=True)
    win_rate = FloatField(null=True)
    max_consecutive_win = IntegerField(null=True)
    max_consecutive_loss = IntegerField(null=True)
    average_win = FloatField(null=True)
    average_loss = FloatField(null=True)
    win_loss_ratio = FloatField(null=True)
    sharpe_ratio = FloatField(null=True)
    max_drawdown = FloatField(null=True)
    max_drawdown_duration = IntegerField(null=True)
    daily_std = FloatField(null=True)
    return_drawdown_ratio = FloatField(null=True)
    created_at = DateTimeField(constraints=[SQL('DEFAULT CURRENT_TIMESTAMP')])
    updated_at = DateTimeField(constraints=[SQL('DEFAULT CURRENT_TIMESTAMP')])
    
    class Meta:
        table_name = 'backtests'


class BacktestTrade(BaseModel):
    """回测交易明细"""
    backtest = ForeignKeyField(Backtest, backref='trades', on_delete='CASCADE')
    datetime = DateTimeField()
    symbol = CharField()
    direction = CharField()
    offset = CharField()
    open_price = FloatField()
    close_price = FloatField()
    quantity = IntegerField()
    pnl = FloatField()
    commission = FloatField()
    created_at = DateTimeField(constraints=[SQL('DEFAULT CURRENT_TIMESTAMP')])
    
    class Meta:
        table_name = 'backtest_trades'


def init_database(db_path: str):
    """初始化数据库连接"""
    database.init(db_path)
    database.create_tables([ExportMetadata, OperationLog, Backtest, BacktestTrade], safe=True)


def close_database():
    """关闭数据库连接"""
    if not database.is_closed():
        database.close()