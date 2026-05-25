# -*- coding: utf-8 -*-
"""全局统一的 Pandera Schema 定义

集中管理所有 DataFrame 验证规则，供整个项目复用。
所有 Schema 都继承自 pandera.DataFrameModel，提供运行时验证能力。
"""

import pandas as pd
import pandera.pandas as pa
from pandera.typing import Series
from pandera.typing import DataFrame


class KlineSchema(pa.DataFrameModel):
    """K线数据验证Schema
    
    用于验证从 CSV 加载的 K线数据，确保数据质量和一致性。
    字段说明：
        datetime: 时间戳（唯一）
        open: 开盘价
        high: 最高价
        low: 最低价
        close: 收盘价
        volume: 成交量
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
    """交易记录验证Schema
    
    用于验证单笔交易记录的数据格式。
    字段说明：
        datetime: 交易时间
        symbol: 品种代码
        direction: 交易方向（long/short）
        open_price: 开仓价格
        close_price: 平仓价格
        quantity: 交易数量
        pnl: 盈亏
        commission: 手续费
    """
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
    """回测结果验证Schema
    
    用于验证回测过程中的权益曲线数据。
    字段说明：
        datetime: 时间戳（唯一）
        equity: 权益总值
        cash: 现金
        position: 持仓数量
        pnl: 盈亏
        drawdown: 回撤
    """
    datetime: Series[pd.DatetimeTZDtype] = pa.Field(unique=True)
    equity: Series[float] = pa.Field(ge=0.0)
    cash: Series[float] = pa.Field(ge=0.0)
    position: Series[int] = pa.Field()
    pnl: Series[float] = pa.Field()
    drawdown: Series[float] = pa.Field(ge=0.0)
    
    class Config:
        coerce = True


class DailyReturnSchema(pa.DataFrameModel):
    """日收益率验证Schema
    
    用于验证每日收益率数据。
    字段说明：
        date: 日期（唯一）
        return: 收益率
        equity: 权益值
    """
    date: Series[pd.DatetimeTZDtype] = pa.Field(unique=True)
    return_: Series[float] = pa.Field(alias='return')
    equity: Series[float] = pa.Field(ge=0.0)
    
    class Config:
        coerce = True
        extra = 'allow'


# 类型别名，方便使用
KlineDataFrame = DataFrame[KlineSchema]
TradeDataFrame = DataFrame[TradeRecordSchema]
BacktestDataFrame = DataFrame[BacktestResultSchema]
DailyReturnDataFrame = DataFrame[DailyReturnSchema]