# -*- coding: utf-8 -*-
"""数据模块 - 统一数据访问接口

对外隐藏数据库实现细节，提供简洁的数据存取接口。
所有 DataFrame 交互都经过 Pandera Schema 验证，单条记录都经过 Pydantic 验证。

外部模块只需了解：
  - DataManager: 统一数据管理器（核心接口）
  - Pandera Schema: KlineSchema, TradeRecordSchema, BacktestResultSchema
  - Pydantic Model: BacktestRecord, TradeRecord, SymbolInfo, DataSummary
  - export_csv: 数据导出函数

DataManager 核心方法：
    # 元数据查询
    get_all_symbols()      -> List[str]          # 获取所有可用品种
    search_symbols(pattern) -> List[str]        # 正则搜索品种
    get_symbol_info(symbol) -> SymbolInfo        # 获取品种详细信息
    get_data_summary()      -> DataSummary       # 获取数据汇总
    
    # 数据加载（返回 Pandera 验证的 DataFrame）
    load_kline(symbol, start_date, end_date) -> DataFrame[KlineSchema]
    
    # 回测记录（返回 Pydantic Model）
    save_backtest(record: BacktestRecord) -> int
    query_backtests(symbol, strategy) -> List[BacktestRecord]
    query_trades(backtest_id) -> List[TradeRecord]
"""

import pandera.pandas as pa
from pandera.typing import DataFrame

# Pandera Schema（对外暴露，用于 DataFrame 验证）
from .models import (
    KlineSchema,
    TradeRecordSchema,
    BacktestResultSchema,
)

# 核心数据访问接口
from .manager import DataManager

# Pydantic 模型（对外暴露，用于单条记录验证）
from .models import (
    BacktestRecord,
    TradeRecord,
    SymbolInfo,
    DataSummary,
)

# 数据导出函数
from .exporter import export_csv

# 向后兼容
from .compat import Database, DBLogHandler, setup_db_logging

# 类型别名（向后兼容）
BacktestDict = BacktestRecord
BacktestTradeDict = TradeRecord

__all__ = [
    # Pandera Schema
    'KlineSchema',
    'TradeRecordSchema',
    'BacktestResultSchema',
    
    # DataManager
    'DataManager',
    
    # Pydantic Model
    'BacktestRecord',
    'TradeRecord',
    'SymbolInfo',
    'DataSummary',
    
    # 工具函数
    'export_csv',
    
    # 向后兼容
    'Database',
    'DBLogHandler',
    'setup_db_logging',
    'BacktestDict',
    'BacktestTradeDict',
]
