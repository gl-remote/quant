# -*- coding: utf-8 -*-
"""Optuna 优化报告 — ECharts option JSON 生成

输出 ECharts 标准 option 格式，前端 echarts-for-react 直接消费。
不再依赖 optuna.visualization (Plotly)。
"""

from __future__ import annotations

from loguru import logger
from typing import Any

import optuna

def build_optuna_spec(
    study_db_url: str,
    study_name: str,
) -> dict[str, Any]:
    """生成 Optuna 图表 ECharts option JSON

    Args:
        study_db_url: SQLite storage URL
        study_name: Optuna study 名称

    Returns:
        {
            "study_name": "...",
            "best_params": [...],
            "best_value": 0.0,
            "optimization_history": {...},
            "param_importances": {...},
            "parallel_coordinate": {...},
            "contour": {...},
        }
    """
    study = optuna.load_study(study_name=study_name, storage=study_db_url)
    trials = study.trials

    result: dict[str, Any] = {
        "study_name": study_name,
        "best_params": [],
        "best_value": None,
    }

    # --- 最优结果 ---
    try:
        result["best_params"] = [
            {"name": k, "value": v} for k, v in study.best_params.items()
        ]
        result["best_value"] = study.best_value
    except Exception as e:
        logger.warning("最优参数获取失败: %s", e)

    # --- optimization_history ---
    try:
        result["optimization_history"] = _build_history(trials)
    except Exception as e:
        logger.warning("optimization_history 生成失败: %s", e)
        result["optimization_history"] = None

    # --- param_importances ---
    try:
        result["param_importances"] = _build_importances(study)
    except Exception as e:
        logger.warning("param_importances 生成失败: %s", e)
        result["param_importances"] = None

    # --- parallel_coordinate ---
    try:
        result["parallel_coordinate"] = _build_parallel(study, trials)
    except Exception as e:
        logger.warning("parallel_coordinate 生成失败: %s", e)
        result["parallel_coordinate"] = None

    # --- contour ---
    try:
        result["contour"] = _build_contour(study, trials)
    except Exception as e:
        logger.warning("contour 生成失败: %s", e)
        result["contour"] = None

    return result


def _completed_trials(trials: list[optuna.trial.FrozenTrial]) -> list[optuna.trial.FrozenTrial]:
    """筛选状态为 COMPLETE 且有目标值的 trial"""
    return [t for t in trials if t.state == optuna.trial.TrialState.COMPLETE and t.value is not None]


def _param_names(study: optuna.study.Study) -> list[str]:
    """提取所有参数名（按搜索空间顺序）"""
    try:
        return list(study.trials[0].params.keys())
    except Exception:
        return []


def _build_history(trials: list[optuna.trial.FrozenTrial]) -> dict | None:
    """优化历史散点图：X=试验序号, Y=目标值"""
    ct = _completed_trials(trials)
    if not ct:
        return None

    nums = [t.number for t in ct]
    values: list[float] = [t.value for t in ct if t.value is not None]

    best = []
    best_sofar = float("inf")
    for v in values:
        if v < best_sofar:
            best_sofar = v
        best.append(best_sofar)

    return {
        "tooltip": {"trigger": "axis"},
        "legend": {"data": ["目标值", "历史最优"], "bottom": 0},
        "grid": {"left": 60, "right": 30, "top": 20, "bottom": 40},
        "xAxis": {"type": "value", "name": "试验序号", "nameLocation": "center", "nameGap": 25},
        "yAxis": {"type": "value", "name": "目标值"},
        "series": [
            {
                "name": "目标值",
                "type": "scatter",
                "data": [[n, v] for n, v in zip(nums, values)],
                "symbolSize": 6,
            },
            {
                "name": "历史最优",
                "type": "line",
                "data": [[n, b] for n, b in zip(nums, best)],
                "lineStyle": {"color": "#e74c3c", "width": 2},
                "symbol": "none",
            },
        ],
    }


def _build_importances(study: optuna.study.Study) -> dict | None:
    """参数重要性柱状图 (用 fANOVA 计算)"""
    try:
        from optuna.importance import get_param_importances
        importances = get_param_importances(study)
    except Exception:
        return None

    if not importances:
        return None

    items = sorted(importances.items(), key=lambda x: x[1])
    names = [k for k, _ in items]
    vals = [v for _, v in items]

    return {
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "grid": {"left": 100, "right": 30, "top": 20, "bottom": 20},
        "xAxis": {"type": "value", "name": "重要性"},
        "yAxis": {"type": "category", "data": names, "inverse": True,
                  "axisLabel": {"width": 90, "overflow": "truncate"}},
        "series": [{
            "name": "参数重要性",
            "type": "bar",
            "data": vals,
            "itemStyle": {"color": "#5470c6"},
        }],
    }


def _build_parallel(study: optuna.study.Study, trials: list[optuna.trial.FrozenTrial]) -> dict | None:
    """平行坐标图"""
    ct = _completed_trials(trials)
    if not ct:
        return None

    param_names = _param_names(study)
    if not param_names:
        return None

    values_list = [t.value for t in ct]
    params_list = [t.params for t in ct]

    dims: list[dict] = []
    # 每个参数作为维度
    for p in param_names:
        vals_set = set()
        for pl in params_list:
            v = pl.get(p)
            if v is not None:
                vals_set.add(v)

        if len(vals_set) <= 1:
            dims.append({"dim": len(dims), "name": p})
        else:
            dims.append({"dim": len(dims), "name": p, "type": "value"})

    dims.append({"dim": len(dims), "name": "目标值", "type": "value"})

    data = []
    for i, pl in enumerate(params_list):
        row = [pl.get(p, 0) for p in param_names]
        row.append(values_list[i])
        data.append(row)

    return {
        "tooltip": {},
        "parallelAxis": [
            {"dim": i, "name": d["name"], **(d if d.get("type") else {"min": 0, "max": 1})}
            for i, d in enumerate(dims)
        ],
        "parallel": {
            "left": 60, "right": 60, "top": 30, "bottom": 30,
            "parallelAxisDefaultProps": {"nameLocation": "end", "nameGap": 10},
        },
        "series": [{
            "type": "parallel",
            "data": data,
            "lineStyle": {"width": 1, "opacity": 0.5},
        }],
    }


def _build_contour(study: optuna.study.Study, trials: list[optuna.trial.FrozenTrial]) -> dict | None:
    """等高线图（取前两个参数）"""
    ct = _completed_trials(trials)
    param_names = _param_names(study)
    if len(param_names) < 2 or not ct:
        return None

    p1, p2 = param_names[0], param_names[1]
    points = [(t.params.get(p1, 0), t.params.get(p2, 0), t.value) for t in ct]
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    vs: list[float] = [p[2] for p in points if p[2] is not None]

    if not vs:
        return None

    return {
        "tooltip": {},
        "visualMap": {
            "min": min(vs), "max": max(vs),
            "inRange": {"color": ["#313695", "#4575b4", "#74add1", "#abd9e9",
                                  "#fee090", "#fdae61", "#f46d43", "#d73027", "#a50026"]},
            "calculable": True,
            "orient": "horizontal",
            "left": "center",
            "bottom": 0,
        },
        "xAxis": {"type": "value", "name": p1, "nameLocation": "center", "nameGap": 25},
        "yAxis": {"type": "value", "name": p2, "nameLocation": "center", "nameGap": 35},
        "grid": {"left": 70, "right": 30, "top": 20, "bottom": 50},
        "series": [{
            "name": f"{p1} vs {p2}",
            "type": "scatter",
            "data": [[xs[i], ys[i], vs[i]] for i in range(len(points))],
            "symbolSize": 8,
        }],
    }
