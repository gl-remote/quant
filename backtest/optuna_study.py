"""Optuna 业务域契约

集中封装 Optuna study 生命周期相关工具函数，消除 optimizer.py 和 parallel.py
之间的重复代码。

功能：
  - make_study_name:    study 名称生成
  - create_grid_space:  search_space → grid 字典（替代两处重复）
  - get_study:          统一 optuna.create_study 调用（替代两处独立调用）
  - link_study:         关联 run 与 study name（委托到 data 层）
  - optuna_result_to_search_result: 统一 OptunaResult → SearchResult 转换
"""

from __future__ import annotations

from typing import Any

import optuna
from loguru import logger

from .optimizer import OptunaResult, SearchResult


def make_study_name(strategy: str, engine: str, run_id: int) -> str:
    """生成 Optuna study 名称

    格式: {strategy}_{engine}_r{run_id}
    例如: ma_bayesian_r42
    """
    return f"{strategy}_{engine}_r{run_id}"


def create_grid_space(search_space: dict[str, dict[str, Any]]) -> dict[str, list[Any]]:
    """将 search_space 配置转换为 Optuna GridSampler 格式

    例如: {"fast_ma": {"type": "int", "low": 5, "high": 25, "step": 5}}
      → {"fast_ma": [5, 10, 15, 20, 25]}

    Args:
        search_space: search space 配置

    Returns:
        {"param_name": [values, ...], ...}
    """
    grid: dict[str, list[Any]] = {}
    for name, config in search_space.items():
        ptype = config.get("type", "int")
        if ptype == "categorical":
            grid[name] = list(config.get("choices", []))
        else:
            low = config.get("low", 0)
            high = config.get("high", 10)
            step = config.get("step", 1)
            values: list[Any] = []
            current = low
            while current <= high:
                values.append(current)
                current += step
            grid[name] = values
    return grid


def get_study(
    study_name: str,
    storage: str | None,
    sampler: optuna.samplers.BaseSampler,
    direction: str = "maximize",
) -> optuna.Study:
    """统一创建或加载 Optuna study

    Args:
        study_name: study 名称
        storage: SQLite storage URL 或 None（内存模式）
        sampler: Optuna sampler 实例
        direction: 优化方向

    Returns:
        optuna.Study 实例
    """
    if storage:
        logger.info("Optuna study 存储: {} ({})", study_name, storage)

    study = optuna.create_study(
        study_name=study_name,
        direction=direction,
        storage=storage,
        sampler=sampler,
        load_if_exists=True,
    )
    return study


def link_study(run_id: int, study_name: str) -> None:
    """关联 run 与 Optuna study（委托到 data 层）

    Args:
        run_id: 运行记录 ID
        study_name: Optuna study 名称
    """
    from data.optuna_query import link_study as _link_study

    _link_study(run_id, study_name)


def optuna_result_to_search_result(
    opt_result: OptunaResult,
    study_name: str,
) -> SearchResult:
    """统一 OptunaResult → SearchResult 转换"""
    return SearchResult(
        best_params=opt_result.best_params,
        best_value=opt_result.best_value,
        n_trials=len(opt_result.trial_data),
        study_name=study_name,
        trial_data=opt_result.trial_data,
        actual_seed=opt_result.actual_seed,
    )
