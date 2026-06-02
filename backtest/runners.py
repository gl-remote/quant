# -*- coding: utf-8 -*-
"""
批量回测编排器

提供批量回测的工作流编排，包括数据加载、Walk-Forward 执行等。
不负责持久化，持久化由 CLI 层处理。
"""

from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from common.schemas import KlineDataFrame

from config import ConfigManager
from data import DataManager
from .optimizer import run_param_search, SearchResult

if TYPE_CHECKING:
    from .vnpy_backtest_engine import VnpyBacktestEngine

logger = logging.getLogger(__name__)


def execute_walk_forward(engine: "VnpyBacktestEngine",
                        strategy_name: str, strategy_params: dict[str, Any],
                        capital: float, contract_size: int,
                        datasets: list[tuple[str, KlineDataFrame, str]]) -> tuple[dict[str, Any], str, str]:
    """执行 Walk-Forward 滚动验证

    Args:
        engine: VnpyBacktestEngine 实例
        strategy_name: 策略名称
        strategy_params: 策略参数字典
        capital: 初始资金
        contract_size: 合约乘数
        datasets: 数据集列表

    Returns:
        (wf_result, strategy_name, symbol) 元组，用于 CLI 层持久化
    """
    sym = datasets[0][0]
    df = datasets[0][1]
    wf_result = engine.run_walk_forward(
        data=df, symbol=sym,
        strategy_name=strategy_name, strategy_params=strategy_params,
    )

    return wf_result, strategy_name, sym


def execute_parameter_search(engine: "VnpyBacktestEngine",
                            strategy_name: str, strategy_params: dict[str, Any],
                            capital: float, contract_size: int,
                            datasets: list[tuple[str, KlineDataFrame, str]],
                            n_trials: int, optimizer_cfg: Any, cm: ConfigManager,
                            optimizer_arg: str | None, git_hash: str | None,
                            dm: DataManager, run_id: int ) -> SearchResult | None:
    """执行参数搜索

    Args:
        engine: VnpyBacktestEngine 实例
        strategy_name: 策略名称
        strategy_params: 策略参数字典
        capital: 初始资金
        contract_size: 合约乘数
        datasets: 数据集列表
        n_trials: 试验次数
        optimizer_cfg: Optimizer 配置对象
        cm: ConfigManager 实例
        optimizer_arg: 命令行指定的优化器类型
        git_hash: Git 提交哈希
        dm: DataManager 实例
        run_id: 运行记录 ID

    Returns:
        SearchResult（如果成功执行搜索），否则 None
    """
    run_engine = optimizer_arg or cm.get_optimizer_config().engine or "grid"
    
    # 优先使用策略专属搜索空间 (sc.search_space)，其次使用 optimizer 配置
    sc = cm.get_trading_config(strategy_name)
    search_space = sc.search_space or optimizer_cfg.strategy_spaces.get(strategy_name, {}) or optimizer_cfg.search_space
    
    if not search_space:
        logger.warning("搜索空间为空，跳过参数搜索")
        return None

    if not optimizer_cfg.enabled:
        logger.warning("optimizer.enabled=False，跳过参数搜索")
        dm.store.finish_run(run_id, "skipped")
        return None

    # 准备 study 元数据
    study_name = f"{strategy_name}_{run_engine}_r{run_id}"
    if run_id:
        dm.store.link_study(run_id, study_name)
    optuna_db_url = f"sqlite:///{dm.store.db_path}"

    # 执行搜索（optimizer 只搜索，不持久化）
    result = run_param_search(
        engine=engine,
        datasets=[(s, d) for s, d, _ in datasets],
        strategy_name=strategy_name,
        search_space=search_space,
        strategy_params=strategy_params,
        capital=capital,
        contract_size=contract_size,
        n_trials=n_trials,
        search_type=run_engine,
        study_db_path=optuna_db_url,
        study_name=study_name,
    )

    logger.info("%s 完成: best=%.4f params=%s trials=%d",
                run_engine, result.best_value, result.best_params,
                result.n_trials)

    return result
