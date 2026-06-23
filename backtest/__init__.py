"""
回测模块

模块职责:
  - vnpy_backtest_engine: vn.py 回测引擎 (纯执行器)
  - strategy_factory:     策略工厂与桥接器集成
  - data_utils:           数据转换工具 (df_to_vnpy_datalines, resolve_interval)
  - results:              结果聚合与统计 (Walk-Forward 聚合)
  - walk_forward:         Walk-Forward 窗口划分
  - optimizer:            参数优化引擎 (Optuna 网格/贝叶斯搜索)
  - persister:            背测域持久化服务（阶段 4 新增）

注意: 单标的 TqSdk 回测由 cli/workflows/backtests_run.py:BacktestRunWorkflow._run_tqsdk_single 实现。
     报告生成已迁移至顶层 report/ 包。
     纯函数工具 (metrics/stats/formatting) 已提取至 common/ 模块。
     CSV 扫描/加载已迁移至 data/manager.py (DataManager)。
"""

from .data_utils import df_to_vnpy_datalines, resolve_interval
from .optimizer import OptunaOptimizer, OptunaResult, run_param_search
from .optuna_study import (
    SearchResult,
    create_grid_space,
    get_study,
    link_study,
    make_study_name,
    optuna_result_to_search_result,
)
from .parallel import ParallelBacktestOptimizer, run_param_search_parallel
from .persister import BacktestResultPersister, SearchResultPersister, WalkForwardPersister
from .results import WalkForwardAggregate, aggregate_walk_forward
from .strategy_factory import StrategyFactory, create_strategy_class, load_strategy_and_config
from .vnpy_backtest_engine import VnpyBacktestEngine
from .walk_forward import (
    WindowParams,
    validate_window_params,
    walk_forward_split,
    walk_forward_split_by_ratio,
)

__all__ = [
    "VnpyBacktestEngine",
    "StrategyFactory",
    "create_strategy_class",
    "load_strategy_and_config",
    "df_to_vnpy_datalines",
    "resolve_interval",
    "aggregate_walk_forward",
    "WalkForwardAggregate",
    "walk_forward_split",
    "walk_forward_split_by_ratio",
    "validate_window_params",
    "WindowParams",
    "run_param_search",
    "run_param_search_parallel",
    "ParallelBacktestOptimizer",
    "OptunaOptimizer",
    "OptunaResult",
    "SearchResult",
    "create_grid_space",
    "get_study",
    "link_study",
    "make_study_name",
    "optuna_result_to_search_result",
    "BacktestResultPersister",
    "SearchResultPersister",
    "WalkForwardPersister",
]
