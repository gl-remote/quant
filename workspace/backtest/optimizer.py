"""基于 Optuna 的参数优化引擎

提供统一的参数优化接口，支持网格搜索和贝叶斯搜索两种模式。

架构设计:
    CLI 层：负责 orchestrate、持久化回测结果
    Optimizer 层：负责参数搜索逻辑，不做持久化
    Engine 层：负责运行单个回测

流程:
    1. 定义搜索空间
    2. 每个 trial 采样参数，创建策略
    3. 调用 engine.run() 运行回测
    4. 聚合多品种夏普比率均值
    5. 返回优化结果（SearchResult），持久化由调用方处理

用法:
    from backtest.optimizer import run_param_search

    result = run_param_search(
        engine=engine,
        datasets=[(symbol, df), ...],
        strategy_name="ma",
        search_space={...},
        strategy_params={...},
        capital=100000,
        contract_size=10,
        n_trials=50,
        search_type="bayesian",  # 或 "grid"
    )
    print(result.best_params)
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import optuna
import pandas as pd
from loguru import logger

MIN_TRADES_PER_RESULT = 10
LOW_ACTIVITY_SCORE = -999.0


def calculate_optimization_score(engine_results: list[Any]) -> float:
    """计算参数优化目标值，低交易活跃度结果直接惩罚。"""
    successful_results = [r for r in engine_results if r.success]
    if not successful_results:
        return LOW_ACTIVITY_SCORE

    if any((r.total_trades or 0) < MIN_TRADES_PER_RESULT for r in successful_results):
        return LOW_ACTIVITY_SCORE

    calmars = [
        (r.annual_return or 0) / abs(r.max_ddpercent or 0.001)
        for r in successful_results
        if (r.max_ddpercent or 0) != 0
    ]
    return float(sum(calmars) / len(calmars)) if calmars else LOW_ACTIVITY_SCORE


@dataclass
class OptunaResult:
    """Optuna 优化结果

    Attributes:
        best_params: 最优参数组合
        best_value: 最优目标值
        trial_data: 全部试验数据 [{search_params, value, engine_results, strategy_params, ...}, ...]
        study: optuna.Study 实例（用于可视化）
        actual_seed: 实际使用的随机种子
    """

    best_params: dict[str, Any] = field(default_factory=dict)
    best_value: float = 0.0
    trial_data: list[dict[str, Any]] = field(default_factory=list)
    study: optuna.Study | None = None
    actual_seed: int = 0


@dataclass
class SearchResult:
    """参数搜索结果摘要

    用于 CLI 层获取搜索结果，不包含持久化相关字段。

    Attributes:
        best_params: 最优参数组合
        best_value: 最优目标值
        n_trials: 试验次数
        study_name: optuna study 名称
        trial_data: 全部试验数据
        actual_seed: 实际使用的随机种子
    """

    best_params: dict[str, Any] = field(default_factory=dict)
    best_value: float = 0.0
    n_trials: int = 0
    study_name: str = ""
    trial_data: list[dict[str, Any]] = field(default_factory=list)
    actual_seed: int = 0


class OptunaOptimizer:
    """基于 Optuna 的参数优化器 (严格单线程)

    支持两种搜索模式：
      1. **Grid Search** (网格)：穷举搜索空间的所有组合
      2. **Bayesian Search** (贝叶斯)：使用 TPESampler 进行智能采样

    注意：本优化器强制单线程执行，因为底层 vnpy BacktestingEngine
    非线程安全，SQLite 也不支持多线程并发写入。

    目标函数：最大化 Calmar 比率平均值（年化收益/最大回撤，取各品种均值）
    """

    def __init__(
        self,
        engine: Any,
        datasets: list[tuple[str, pd.DataFrame]],
        strategy_name: str,
        search_space: dict[str, dict[str, Any]],
        strategy_params: dict[str, Any] | None = None,
        capital: float | None = None,
        contract_size: int | None = None,
        n_trials: int = 50,
        search_type: str = "bayesian",
        study_name: str = "",
        random_seed: int = 42,
        use_fixed_seed: bool = False,
    ) -> None:
        self._engine = engine
        self._datasets = datasets
        self._strategy_name = strategy_name
        self._search_space = search_space
        self._strategy_params = strategy_params or {}
        self._capital = capital
        self._contract_size = contract_size
        self._n_trials = n_trials
        self._search_type = search_type
        self._use_fixed_seed = use_fixed_seed
        # 确定实际使用的种子
        if use_fixed_seed:
            self._actual_seed = random_seed
        else:
            # 生成一个随机种子
            self._actual_seed = random.randint(1, 999999)

        # study 名：自定义 > 自动生成
        if study_name:
            self._study_name = study_name
        else:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._study_name = f"{strategy_name}_{ts}"

    def optimize(self) -> OptunaResult:
        """执行 Optuna 优化（严格单线程）

        Returns:
            OptunaResult 包含最优参数、全部试验数据、study 实例
        """
        result = OptunaResult()
        trial_index: list[dict[str, Any]] = []

        def objective(trial: optuna.trial.Trial) -> float:
            params = self._suggest_params(trial)
            merged_params = {**self._strategy_params, **params}

            pairs = [(sym, df, self._strategy_name, merged_params) for sym, df in self._datasets]
            engine_results = self._engine.run(pairs)
            score = calculate_optimization_score(engine_results)

            trial_index.append(
                {
                    "search_params": params,
                    "value": score,
                    "engine_results": engine_results,
                    "strategy_params": merged_params,
                    "strategy_name": self._strategy_name,
                }
            )

            logger.info(
                "Trial {:3d}/{} | score={:.4f} | {}",
                trial.number + 1,
                n_trials,
                score,
                {k: v for k, v in params.items()},
            )

            return score

        # 抑制 optuna 默认日志
        optuna.logging.set_verbosity(optuna.logging.WARNING)

        # 创建 study（使用 data 层管理的共享数据库）
        from data.optuna_query import get_optuna_url

        from .optuna_study import get_study

        storage = get_optuna_url()
        logger.info("Optuna study 存储: {} ({})", self._study_name, storage)

        # 根据搜索类型选择 sampler
        if self._search_type == "grid":
            from .optuna_study import create_grid_space

            grid_space = create_grid_space(self._search_space)
            sampler = optuna.samplers.GridSampler(grid_space, seed=self._actual_seed)
            if not grid_space:
                n_trials = 0
            else:
                n_combinations = 1
                for values in grid_space.values():
                    n_combinations *= len(values)
                n_trials = min(self._n_trials, n_combinations)
            logger.info("Grid Search: 搜索空间={}, 计划试验={}", grid_space, n_trials)
        else:
            sampler = optuna.samplers.TPESampler(seed=self._actual_seed)  # type: ignore[assignment]
            n_trials = self._n_trials

        study = get_study(
            study_name=self._study_name,
            storage=storage,
            sampler=sampler,
        )

        # 严格单线程：n_jobs=1, show_progress_bar=False
        study.optimize(objective, n_trials=n_trials, n_jobs=1, show_progress_bar=False)

        result.best_params = study.best_params
        result.best_value = study.best_value or 0.0
        result.trial_data = trial_index
        result.study = study
        result.actual_seed = self._actual_seed

        logger.info(
            "Optuna 优化完成: best_value={:.4f} best_params={} study={} seed={}",
            result.best_value,
            result.best_params,
            self._study_name,
            self._actual_seed,
        )
        return result

    @property
    def study_name(self) -> str:
        return self._study_name

    # ── 内部 ────────────────────────────────────────────────

    def _suggest_params(self, trial: optuna.trial.Trial) -> dict[str, Any]:
        """从 search_space 配置生成 Optuna suggest 调用"""
        params: dict[str, Any] = {}
        for name, spec in self._search_space.items():
            stype = spec.get("type", "int")
            if stype == "int":
                params[name] = trial.suggest_int(
                    name,
                    int(spec["low"]),
                    int(spec["high"]),
                    step=int(spec.get("step", 1)),
                )
            elif stype == "float":
                params[name] = trial.suggest_float(
                    name,
                    float(spec["low"]),
                    float(spec["high"]),
                    step=float(spec.get("step", 0.01)) if spec.get("step") else None,
                )
            elif stype == "categorical":
                params[name] = trial.suggest_categorical(
                    name,
                    spec.get("choices", []),
                )
        return params


def run_param_search(
    engine: Any,
    datasets: list[tuple[str, pd.DataFrame]],
    strategy_name: str,
    search_space: dict[str, dict[str, Any]],
    strategy_params: dict[str, Any],
    capital: float,
    contract_size: int,
    n_trials: int,
    search_type: str,
    study_name: str = "",
    random_seed: int = 42,
    use_fixed_seed: bool = False,
) -> SearchResult:
    """执行参数搜索（网格或贝叶斯，严格单线程）

    Optuna 数据库路径由 data 层管理（get_optuna_url），调用方无需关心。

    Args:
        engine: 回测引擎实例
        datasets: [(symbol, DataFrame), ...] 多品种数据
        strategy_name: 策略名称
        search_space: 搜索空间定义
        strategy_params: 策略默认参数
        capital: 初始资金
        contract_size: 合约乘数
        n_trials: 最大试验次数
        search_type: "grid" 或 "bayesian"
        study_name: 自定义 study 名称
        random_seed: 随机种子，用于保证复现性
        use_fixed_seed: 是否使用固定随机种子（默认不使用）

    Returns:
        SearchResult 搜索结果
    """
    optimizer = OptunaOptimizer(
        engine=engine,
        datasets=datasets,
        strategy_name=strategy_name,
        search_space=search_space,
        strategy_params=strategy_params,
        capital=capital,
        contract_size=contract_size,
        n_trials=n_trials,
        search_type=search_type,
        study_name=study_name,
        random_seed=random_seed,
        use_fixed_seed=use_fixed_seed,
    )
    from .optuna_study import optuna_result_to_search_result

    opt_result = optimizer.optimize()

    return optuna_result_to_search_result(opt_result, optimizer.study_name)
