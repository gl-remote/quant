# -*- coding: utf-8 -*-
"""参数网格搜索模块

提供穷举网格搜索：从 param_grid 笛卡尔积生成 N 个策略变体。

用法:
    from optimizer import GridOptimizer

    opt = GridOptimizer(
        engine=engine, datasets=datasets,
        strategy_name="ma", param_grid={...},
        strategy_params={...}, capital=100000, contract_size=10,
    )
    result = opt.run()  # 跑 engine + 返回全部 results
"""

from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from strategies.core import load_strategy

logger = logging.getLogger(__name__)


@dataclass
class GridResult:
    """网格搜索结果"""

    engine_results: list[dict[str, Any]] = field(default_factory=list)
    strategies: list[Any] = field(default_factory=list)


class GridOptimizer:
    """网格搜索调度器 — 与 OptunaOptimizer 保持一致的接口

    负责穷举 param_grid 的所有组合、生成策略、调度 engine.run()。
    """

    def __init__(
        self,
        engine: Any,
        datasets: list[tuple[str, pd.DataFrame]],
        strategy_name: str,
        param_grid: dict[str, list[Any]],
        strategy_params: dict[str, Any] | None = None,
        capital: float | None = None,
        contract_size: int | None = None,
    ) -> None:
        self._engine = engine
        self._datasets = datasets
        self._strategy_name = strategy_name
        self._param_grid = param_grid
        self._strategy_params = strategy_params or {}
        self._capital = capital
        self._contract_size = contract_size

    def run(self) -> GridResult:
        """执行网格搜索回测

        Returns:
            GridResult，含 engine_results + strategies 列表
        """
        strategies = self._generate_strategies()
        pairs = [
            (sym, df, s)
            for (sym, df), s in itertools.product(self._datasets, strategies)
        ]
        engine_results = self._engine.run(pairs)
        return GridResult(
            engine_results=engine_results,
            strategies=strategies,
        )

    def _generate_strategies(self) -> list[Any]:
        """从 param_grid 生成全部策略变体"""
        if not self._param_grid:
            logger.warning("param_grid 为空，生成单策略实例")
            return [load_strategy(
                self._strategy_name,
                strategy_params=self._strategy_params,
                capital=self._capital,
                contract_size=self._contract_size,
            )]

        keys = list(self._param_grid.keys())
        values = list(self._param_grid.values())
        combinations = list(itertools.product(*values))

        strategies: list[Any] = []
        for combo in combinations:
            params = dict(self._strategy_params)
            params.update(dict(zip(keys, combo)))
            s = load_strategy(
                self._strategy_name,
                strategy_params=params,
                capital=self._capital,
                contract_size=self._contract_size,
            )
            strategies.append(s)

        logger.info(
            "Grid Search: %d 组合, 维度=%s",
            len(combinations), keys,
        )
        return strategies


# 向后兼容：保留原函数接口
def generate_param_combinations(
    strategy_name: str,
    param_grid: dict[str, list[Any]],
    strategy_params: dict[str, Any] | None = None,
    capital: float | None = None,
    contract_size: int | None = None,
) -> list[Any]:
    """根据参数网格生成所有策略变体实例 (向后兼容)

    Args:
        strategy_name: 策略名称 (e.g. "ma")
        param_grid: 参数网格 {param_name: [val1, val2, ...]}
        strategy_params: 基础策略参数字典（非搜索字段的默认值）
        capital: 初始资金
        contract_size: 合约乘数

    Returns:
        list[Strategy]: 所有参数组合的策略实例列表
    """
    opt = GridOptimizer(
        engine=None,  # type: ignore[arg-type]  # 兼容旧接口，不需要 engine
        datasets=[],
        strategy_name=strategy_name,
        param_grid=param_grid,
        strategy_params=strategy_params,
        capital=capital,
        contract_size=contract_size,
    )
    return opt._generate_strategies()
