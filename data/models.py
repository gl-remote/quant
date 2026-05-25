# -*- coding: utf-8 -*-
"""数据类型定义模块

包含：
1. Pandera DataFrameSchema - 用于 DataFrame 级别的数据验证
2. Pydantic BaseModel - 用于单条记录的验证
3. ORM 模型 - 内部数据库模型（不对外暴露）
"""

import pandas as pd
import pandera.pandas as pa
from pandera.typing import Series
from pydantic import BaseModel, field_validator, model_validator
from typing import Optional, List, Dict
from peewee import *

# ==============================================================================
# Pandera DataFrame Schema（对外暴露，用于数据验证）
# ==============================================================================

class KlineSchema(pa.DataFrameModel):
    """K线数据验证Schema
    
    用于验证从 CSV 加载的 K线数据，确保数据质量和一致性。
    """
    datetime: Series[pd.DatetimeTZDtype] = pa.Field(unique=True)
    open: Series[float] = pa.Field(ge=0.0)
    high: Series[float] = pa.Field(ge=0.0)
    low: Series[float] = pa.Field(ge=0.0)
    close: Series[float] = pa.Field(ge=0.0)
    volume: Series[int] = pa.Field(ge=0)
    
    @pa.dataframe_check
    def check_high_greater_than_open_close(cls, df: pd.DataFrame) -> bool:
        """验证最高价 >= 开盘价和收盘价"""
        return (df['high'] >= df[['open', 'close']].max(axis=1)).all()
    
    @pa.dataframe_check
    def check_low_less_than_open_close(cls, df: pd.DataFrame) -> bool:
        """验证最低价 <= 开盘价和收盘价"""
        return (df['low'] <= df[['open', 'close']].min(axis=1)).all()
    
    @pa.dataframe_check
    def check_price_range_valid(cls, df: pd.DataFrame) -> bool:
        """验证价格区间有效性：low <= close <= high"""
        return (df['low'] <= df['close']).all() & (df['close'] <= df['high']).all()
    
    class Config:
        coerce = True


class TradeRecordSchema(pa.DataFrameModel):
    """交易记录验证Schema"""
    datetime: Series[pd.DatetimeTZDtype] = pa.Field()
    symbol: Series[str] = pa.Field()
    direction: Series[str] = pa.Field(isin=['long', 'short'])
    open_price: Series[float] = pa.Field(ge=0.0)
    close_price: Series[float] = pa.Field(ge=0.0)
    quantity: Series[int] = pa.Field(gt=0)
    pnl: Series[float] = pa.Field()
    commission: Series[float] = pa.Field(ge=0.0)
    
    class Config:
        coerce = True


class BacktestResultSchema(pa.DataFrameModel):
    """回测结果验证Schema"""
    datetime: Series[pd.DatetimeTZDtype] = pa.Field(unique=True)
    equity: Series[float] = pa.Field(ge=0.0)
    cash: Series[float] = pa.Field(ge=0.0)
    position: Series[int] = pa.Field()
    pnl: Series[float] = pa.Field()
    drawdown: Series[float] = pa.Field(ge=0.0)
    
    class Config:
        coerce = True


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
    """回测记录"""
    symbol = CharField()
    strategy = CharField()
    status = CharField()
    start_date = DateField(null=True)
    end_date = DateField(null=True)
    error_message = TextField(null=True)
    
    total_return = FloatField(null=True)
    max_drawdown = FloatField(null=True)
    win_rate = FloatField(null=True)
    profit_factor = FloatField(null=True)
    sharpe_ratio = FloatField(null=True)
    sortino_ratio = FloatField(null=True)
    total_trades = IntegerField(null=True)
    profit_trades = IntegerField(null=True)
    loss_trades = IntegerField(null=True)
    avg_profit = FloatField(null=True)
    avg_loss = FloatField(null=True)
    
    engine_config = TextField(null=True)
    params_json = TextField(null=True)
    
    created_at = DateTimeField(constraints=[SQL('DEFAULT CURRENT_TIMESTAMP')])
    updated_at = DateTimeField(null=True)
    
    class Meta:
        table_name = 'backtest'


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
        table_name = 'backtest_trade'


def init_database(db_path: str):
    """初始化数据库连接"""
    database.init(db_path)
    database.create_tables([ExportMetadata, OperationLog, Backtest, BacktestTrade], safe=True)


def close_database():
    """关闭数据库连接"""
    if not database.is_closed():
        database.close()
