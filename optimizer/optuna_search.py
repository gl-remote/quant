# -*- coding: utf-8 -*-
"""Optuna 贝叶斯优化调度器

替代 grid_search 的穷举 + CLI 调度模式。OptunaOptimizer 持有 engine 和 datasets，
每个 trial 自动创建策略 → 跑 engine → 聚合多品种得分 → 持久化结果。

用法:
    from optimizer import OptunaOptimizer

    opt = OptunaOptimizer(
        engine=engine,
        datasets=[(symbol, df), ...],
        strategy_name="ma",
        search_space={...},
        strategy_params={...},
        capital=100000,
        contract_size=10,
        n_trials=50,
    )
    result = opt.optimize()
    print(result.best_params)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

from strategies.core import load_strategy
from strategies.core import serialize_strategy_params

logger = logging.getLogger(__name__)


@dataclass
class OptunaResult:
    """Optuna 优化结果

    Attributes:
        best_params: 最优参数组合
        best_value: 最优目标值
        trial_data: 全部试验数据 [{params, value, backtest_ids, status}, ...]
        study: optuna.Study 实例（用于可视化）
        backtest_ids: 所有试验生成的 backtest ID 列表
    """

    best_params: dict[str, Any] = field(default_factory=dict)
    best_value: float = 0.0
    trial_data: list[dict[str, Any]] = field(default_factory=list)
    study: Any = None
    backtest_ids: list[int] = field(default_factory=list)


class OptunaOptimizer:
    """Optuna 贝叶斯优化调度器

    负责：
      1. 定义搜索空间 → Optuna suggest API
      2. 每个 trial 创建策略 → 调 engine.run → 聚合得分
      3. 管理 trial 间数据流向：从 engine 结果提取 score

    不负责：
      - 持久化到数据库（由调用方 CLI 处理）
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
        study_db_path: str = "",
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
            study_db_path: Optuna study SQLite 存储路径，为空则仅内存
        """
        self._engine = engine
        self._datasets = datasets
        self._strategy_name = strategy_name
        self._search_space = search_space
        self._strategy_params = strategy_params or {}
        self._capital = capital
        self._contract_size = contract_size
        self._n_trials = n_trials
        self._study_db_path = study_db_path

        # 生成唯一 study 名
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._study_name = f"{strategy_name}_{ts}"

    def optimize(self) -> OptunaResult:
        """执行 Optuna 优化

        Returns:
            OptunaResult 包含最优参数、全部试验数据、study 实例
        """
        import optuna  # pyright: ignore[reportMissingImports]

        result = OptunaResult()
        trial_index: list[dict[str, Any]] = []

        def objective(trial: optuna.Trial) -> float:
            params = self._suggest_params(trial)
            strategy = load_strategy(
                self._strategy_name,
                strategy_params={**self._strategy_params, **params},
                capital=self._capital,
                contract_size=self._contract_size,
            )

            # 对全部品种跑回测
            pairs = [(sym, df, strategy) for sym, df in self._datasets]
            engine_results = self._engine.run(pairs)

            # 聚合得分：取各品种夏普均值
            sharpes = [
                r['statistics'].get('sharpe_ratio', 0)
                for r in engine_results if r.get('success')
            ]
            if not sharpes:
                score = -999.0
            else:
                score = float(sum(sharpes) / len(sharpes))

            trial_index.append({
                'params': params,
                'value': score,
                'engine_results': engine_results,
                'params_json': serialize_strategy_params(strategy),
                'strategy_name': type(strategy).__name__,
                'strategy_version': getattr(strategy, 'VERSION', None),
            })

            logger.info(
                "Trial %3d | score=%.4f | %s",
                trial.number, score,
                {k: v for k, v in params.items()},
            )
            return score

        # 抑制 optuna 默认日志（INFO → WARNING）
        optuna.logging.set_verbosity(optuna.logging.WARNING)

        # 创建 study（持久化 → SQLite，否则仅内存）
        storage: str | None = None
        if self._study_db_path:
            db_dir = os.path.dirname(self._study_db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            storage = f"sqlite:///{self._study_db_path}"
            logger.info("Optuna study 存储: %s (%s)", self._study_name, storage)

        study = optuna.create_study(
            study_name=self._study_name,
            direction="maximize",
            storage=storage,
            load_if_exists=True,
        )
        study.optimize(objective, n_trials=self._n_trials, show_progress_bar=True)

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

    def _suggest_params(self, trial: Any) -> dict[str, Any]:
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
