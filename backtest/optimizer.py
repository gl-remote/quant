# -*- coding: utf-8 -*-
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

import io
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

import optuna
from common.constants import DEFAULT_N_JOBS

logger = logging.getLogger(__name__)


# ==================== 并发日志缓冲 ====================

class _TrialLogHandler(logging.Handler):
    """线程私有日志缓冲：每个 trial 独立缓冲，结束后一次性输出。

    解决 multi-thread 回测时日志交错混乱的问题：
    - 全局添加一次 handler
    - 每个线程调 start_trial/end_trial 控制缓冲区间
    - end_trial 时原子输出该 trial 的完整日志块
    """

    def __init__(self, fmt: str | None = None) -> None:
        super().__init__()
        self.setFormatter(logging.Formatter(
            fmt or '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        self._local = threading.local()

    def start_trial(self, trial_number: int) -> None:
        self._local.buffer = io.StringIO()
        self._local.trial_number = trial_number

    def end_trial(self) -> None:
        buf: io.StringIO | None = getattr(self._local, 'buffer', None)
        num: int | None = getattr(self._local, 'trial_number', None)
        if buf is not None:
            logs = buf.getvalue()
            self._local.buffer = None  # type: ignore[attr-defined]
            self._local.trial_number = None  # type: ignore[attr-defined]
            if logs:
                print(f"\n{'='*60}\n[Trial {num}] Logs:\n{'='*60}\n{logs}", end='')

    def emit(self, record: logging.LogRecord) -> None:
        buf: io.StringIO | None = getattr(self._local, 'buffer', None)
        if buf is not None:
            buf.write(self.format(record) + '\n')


@dataclass
class OptunaResult:
    """Optuna 优化结果

    Attributes:
        best_params: 最优参数组合
        best_value: 最优目标值
        trial_data: 全部试验数据 [{search_params, value, engine_results, strategy_params, ...}, ...]
        study: optuna.Study 实例（用于可视化）
    """

    best_params: dict[str, Any] = field(default_factory=dict)
    best_value: float = 0.0
    trial_data: list[dict[str, Any]] = field(default_factory=list)
    study: optuna.Study | None = None


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
    """

    best_params: dict[str, Any] = field(default_factory=dict)
    best_value: float = 0.0
    n_trials: int = 0
    study_name: str = ""
    trial_data: list[dict[str, Any]] = field(default_factory=list)


class OptunaOptimizer:
    """基于 Optuna 的参数优化器

    支持两种搜索模式：
      1. **Grid Search** (网格)：穷举搜索空间的所有组合
      2. **Bayesian Search** (贝叶斯)：使用 TPESampler 进行智能采样

    核心功能：
      - 定义搜索空间并通过 Optuna suggest API 采样
      - 每个 trial 创建策略，调用 engine.run，聚合多品种得分
      - 管理 trial 间数据流向
      - 支持 SQLite 持久化 study（便于恢复和可视化）

    目标函数：最大化夏普比率平均值（取各品种夏普的均值）

    不负责：
      - 持久化回测结果到数据库（由 CLI 层处理）
      - 生成可视化报告（由 report/ 模块处理）
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
        n_jobs: int = DEFAULT_N_JOBS,
        study_db_path: str = "",
        search_type: str = "bayesian",
        study_name: str = "",
    ) -> None:
        """
        Args:
            engine: VnpyBacktestEngine 实例
            datasets: [(symbol, DataFrame), ...] 多品种数据
            strategy_name: 策略名称 (e.g. "ma")
            search_space: Optuna 搜索空间定义
            strategy_params: 非搜索字段的默认值
            capital: 初始资金
            contract_size: 合约乘数
            n_trials: 最大试验次数
            n_jobs: 并行 trial 数，>1 使用 threading 并发
            study_db_path: Optuna study SQLite 存储路径，为空则仅内存
            search_type: 搜索类型："bayesian" (TPESampler) 或 "grid" (GridSampler)
            study_name: 自定义 study 名称，为空则自动生成
        """
        self._engine = engine
        self._datasets = datasets
        self._strategy_name = strategy_name
        self._search_space = search_space
        self._strategy_params = strategy_params or {}
        self._capital = capital
        self._contract_size = contract_size
        self._n_trials = n_trials
        self._n_jobs = n_jobs
        self._study_db_path = study_db_path
        self._search_type = search_type

        # study 名：自定义 > 自动生成
        if study_name:
            self._study_name = study_name
        else:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._study_name = f"{strategy_name}_{ts}"

    def _create_grid_space(self) -> dict[str, list[Any]]:
        """将 search_space 转换为 GridSampler 格式"""
        grid_space = {}
        for param_name, config in self._search_space.items():
            ptype = config.get("type", "int")
            low = config.get("low", 0)
            high = config.get("high", 10)
            step = config.get("step", 1)
            
            if ptype == "categorical":
                grid_space[param_name] = config.get("choices", [])
            else:
                # 生成数值序列
                values = []
                current = low
                while current <= high:
                    values.append(current)
                    current += step
                grid_space[param_name] = values
        return grid_space

    def optimize(self) -> OptunaResult:
        """执行 Optuna 优化

        Returns:
            OptunaResult 包含最优参数、全部试验数据、study 实例
        """
        result = OptunaResult()
        trial_index: list[dict[str, Any]] = []
        trial_index_lock = threading.Lock()

        def objective(trial: optuna.trial.Trial) -> float:
            _trial_handler.start_trial(trial.number)
            try:
                params = self._suggest_params(trial)
                merged_params = {**self._strategy_params, **params}

                pairs = [(sym, df, self._strategy_name, merged_params) for sym, df in self._datasets]
                engine_results = self._engine.run(pairs)

                sharpes = [
                    r.sharpe_ratio or 0
                    for r in engine_results if r.success
                ]
                if not sharpes:
                    score = -999.0
                else:
                    score = float(sum(sharpes) / len(sharpes))

                with trial_index_lock:
                    trial_index.append({
                        'search_params': params,
                        'value': score,
                        'engine_results': engine_results,
                        'strategy_params': merged_params,
                        'strategy_name': self._strategy_name,
                    })

                logger.info(
                    "Trial %3d | score=%.4f | %s",
                    trial.number, score,
                    {k: v for k, v in params.items()},
                )
                return score
            finally:
                _trial_handler.end_trial()

        # 抑制 optuna 默认日志（INFO → WARNING）
        optuna.logging.set_verbosity(optuna.logging.WARNING)

        # 创建 study（持久化 → SQLite，否则仅内存）
        # 支持两种格式：
        #   1. 文件路径: "optuna_studies.db" → 转换为 sqlite:///optuna_studies.db
        #   2. SQLite URL: "sqlite:///path/to/db.db"
        storage: str | None = None
        if self._study_db_path:
            if self._study_db_path.startswith('sqlite:///'):
                storage = self._study_db_path
            else:
                db_path = os.path.abspath(self._study_db_path)
                db_dir = os.path.dirname(db_path)
                if db_dir:
                    os.makedirs(db_dir, exist_ok=True)
                storage = f"sqlite:///{db_path}"
            logger.info("Optuna study 存储: %s (%s)", self._study_name, storage)

        # 根据搜索类型选择 sampler
        if self._search_type == "grid":
            grid_space = self._create_grid_space()
            sampler = optuna.samplers.GridSampler(grid_space)
            # 网格搜索的 trial 数等于组合数
            if not grid_space:
                n_trials = 0
            else:
                n_combinations = 1
                for values in grid_space.values():
                    n_combinations *= len(values)
                n_trials = min(self._n_trials, n_combinations)
            logger.info("Grid Search: 搜索空间=%s, 计划试验=%d", grid_space, n_trials)
        else:
            sampler = optuna.samplers.TPESampler()  # type: ignore[assignment]
            n_trials = self._n_trials

        study = optuna.create_study(
            study_name=self._study_name,
            direction="maximize",
            storage=storage,
            sampler=sampler,
            load_if_exists=True,
        )

        # 安装线程私有日志缓冲 handler（并发回测时避免日志交错）
        _trial_handler = _TrialLogHandler()
        _target_loggers = [
            logging.getLogger('backtest'),
            logging.getLogger('strategies'),
        ]
        for lg in _target_loggers:
            lg.addHandler(_trial_handler)

        try:
            study.optimize(objective, n_trials=n_trials, n_jobs=self._n_jobs, show_progress_bar=True)
        finally:
            for lg in _target_loggers:
                lg.removeHandler(_trial_handler)

        result.best_params = study.best_params
        result.best_value = study.best_value or 0.0
        result.trial_data = trial_index
        result.study = study

        logger.info(
            "Optuna 优化完成: best_value=%.4f best_params=%s study=%s",
            result.best_value, result.best_params, self._study_name,
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
                    name, int(spec["low"]), int(spec["high"]),
                    step=int(spec.get("step", 1)),
                )
            elif stype == "float":
                params[name] = trial.suggest_float(
                    name, float(spec["low"]), float(spec["high"]),
                    step=float(spec.get("step", 0.01)) if spec.get("step") else None,
                )
            elif stype == "categorical":
                params[name] = trial.suggest_categorical(
                    name, spec.get("choices", []),
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
    n_jobs: int = DEFAULT_N_JOBS,
    study_db_path: str = "",
    study_name: str = "",
) -> SearchResult:
    """执行参数搜索（网格或贝叶斯）

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
        study_db_path: Optuna study 存储路径
        study_name: 自定义 study 名称

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
        n_jobs=n_jobs,
        study_db_path=study_db_path,
        search_type=search_type,
        study_name=study_name,
    )
    opt_result = optimizer.optimize()

    return SearchResult(
        best_params=opt_result.best_params,
        best_value=opt_result.best_value,
        n_trials=len(opt_result.trial_data),
        study_name=optimizer.study_name,
        trial_data=opt_result.trial_data,
    )
