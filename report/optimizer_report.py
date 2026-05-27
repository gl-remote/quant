# -*- coding: utf-8 -*-
"""Optuna 优化报告 spec 生成

返回 Plotly JSON spec dict，不再生成 HTML 字符串。
react-plotly.js 直接消费这些 spec dict。
"""

from __future__ import annotations

import logging
from typing import Any

import optuna
from optuna.visualization import (
    plot_optimization_history,
    plot_param_importances,
    plot_parallel_coordinate,
    plot_contour,
)

logger = logging.getLogger(__name__)


def build_optuna_spec(
    study_db_url: str,
    study_name: str,
) -> dict[str, Any]:
    """生成 Optuna 图表 Plotly JSON spec 字典

    Args:
        study_db_url: SQLite storage URL
            (e.g. "sqlite:///path/to/optuna_studies.db")
        study_name: Optuna study 名称

    Returns:
        {
            "optimization_history": {"data": [...], "layout": {...}},
            "param_importances": {"data": [...], "layout": {...}},
            "parallel_coordinate": {"data": [...], "layout": {...}},
            "contour": {"data": [...], "layout": {...}},
            "study_name": "...",
            "best_params": [...],
            "best_value": 0.0,
        }
    """
    study = optuna.load_study(study_name=study_name, storage=study_db_url)

    charts: dict[str, dict | None] = {}
    for plot_func, key in [
        (plot_optimization_history, "optimization_history"),
        (plot_param_importances, "param_importances"),
        (plot_parallel_coordinate, "parallel_coordinate"),
        (plot_contour, "contour"),
    ]:
        try:
            fig = plot_func(study)
            fig.update_layout(
                title=key,
                margin=dict(l=40, r=40, t=50, b=40),
                height=400,
            )
            charts[key] = fig.to_plotly_json()
        except Exception as e:
            logger.warning("Optuna 图表 [%s] 生成失败: %s", key, e)
            charts[key] = None

    best_params = []
    best_value = None
    try:
        best = study.best_params
        best_value = study.best_value
        best_params = [{"name": k, "value": v} for k, v in best.items()]
    except Exception as e:
        logger.warning("最优参数获取失败: %s", e)

    return {
        "study_name": study_name,
        "best_params": best_params,
        "best_value": best_value,
        **charts,
    }