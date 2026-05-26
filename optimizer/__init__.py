# -*- coding: utf-8 -*-
"""参数优化模块

提供网格搜索和 Optuna 贝叶斯优化能力，产出策略变体或直接调度 engine 回测。

  - GridOptimizer:    穷举 param_grid 的所有组合
  - OptunaOptimizer:  贝叶斯优化，自动探索连续/离散搜索空间
"""

from .grid_search import GridOptimizer, GridResult, generate_param_combinations
from .optuna_search import OptunaOptimizer, OptunaResult

__all__ = [
    "GridOptimizer",
    "GridResult",
    "OptunaOptimizer",
    "OptunaResult",
    "generate_param_combinations",
]
