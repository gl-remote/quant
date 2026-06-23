"""
data — 统一数据访问模块

对外仅暴露以下接口，隐藏数据库实现细节：

核心接口：
  - DataManager:      统一数据访问入口（推荐使用）
  - KlineSchema:      K线数据验证Schema
  - BacktestRecord:   回测记录模型（Pydantic）
  - TradeRecord:      交易记录模型（Pydantic）
  - SymbolInfo:       品种信息模型（Pydantic）
  - DataSummary:      数据汇总模型（Pydantic）
  - export_csv:       数据导出函数
  - get_data_source:  数据源工厂函数
  - list_sources:     列出可用数据源

设计原则：
  1. 隐藏数据库概念，外部仅通过 DataManager 交互
  2. DataFrame 数据自动通过 Pandera Schema 验证
  3. 单条记录使用 Pydantic 进行运行时验证
  4. 所有数据类型约定清晰，无需关心内部实现
"""

# 从 common.schemas 导入全局统一的 Pandera Schema
from common.schemas import (
    DailyReturnDataFrame,
    DailyReturnSchema,
    KlineDataFrame,
    KlineSchema,
)

from .datasource import get_data_source, list_sources
from .exporter import export_csv
from .manager import DataManager
from .models import (
    BacktestRecord,
    DataSummary,
    SymbolInfo,
    TradeRecord,
)
from .output_paths import output_root

__all__ = [
    # 核心管理器
    "DataManager",
    # Pandera Schema（全局统一）
    "KlineSchema",
    "DailyReturnSchema",
    # DataFrame 类型别名
    "KlineDataFrame",
    "DailyReturnDataFrame",
    # Pydantic 模型
    "BacktestRecord",
    "TradeRecord",
    "SymbolInfo",
    "DataSummary",
    # 导出函数
    "export_csv",
    # 数据源工厂
    "get_data_source",
    "list_sources",
    # 输出路径
    "output_root",
]
