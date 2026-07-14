"""
common — 通用纯函数工具层

零 I/O、零副作用、不依赖业务模块（backtest/report/strategies/data）。
供 backtest、report、live、optimize 等所有上层模块共用。

子模块:
  - formulas:      量化计算公式 (total_return, win_rate, FIFO PnL)
  - metrics:       绩效指标计算 (max_drawdown, sharpe_ratio)
  - stats:         统计聚合工具 (compute_summary_stats, rank_by_key)
  - formatting:    安全格式化 (format_pct, format_float, ensure_float)
  - schemas:       Pandera Schema 定义 (KlineSchema, DailyReturnSchema)
  - symbol_utils:  合约代码解析 & 默认日期范围推算
  - types:         全局类型别名 (TradeAction, PositionDirection)
"""

from .filename_parser import FilenameTemplateParser
from .formatting import ensure_float, format_float, format_pct
from .formulas import calculate_fifo_profit
from .metrics import calc_max_drawdown, calc_sharpe_ratio
from .schemas import (
    DailyReturnDataFrame,
    DailyReturnSchema,
    KlineDataFrame,
    KlineSchema,
)
from .stats import compute_summary_stats, rank_by_key
from .symbol_utils import parse_contract, resolve_date_range
from .types import (
    BacktestResult,
    IndicatorCalcMode,
    IndicatorFuncInfo,
    IndicatorFunction,
    PositionDirection,
    TradeAction,
)

__all__ = [
    "calculate_fifo_profit",
    "calc_max_drawdown",
    "calc_sharpe_ratio",
    "compute_summary_stats",
    "rank_by_key",
    "format_pct",
    "format_float",
    "ensure_float",
    # 文件名解析
    "FilenameTemplateParser",
    # Schema 定义
    "KlineSchema",
    "DailyReturnSchema",
    # DataFrame 类型别名
    "KlineDataFrame",
    "DailyReturnDataFrame",
    # 合约工具
    "parse_contract",
    "resolve_date_range",
    # 类型别名
    "TradeAction",
    "PositionDirection",
    "IndicatorCalcMode",
    # 数据结构
    "BacktestResult",
    "IndicatorFuncInfo",
    "IndicatorFunction",
]
