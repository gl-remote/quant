"""Optuna 内部表操作层

封装所有 Optuna 内部表（studies, study_directions, trials, trial_values, trial_params, run_studies）
的查询与写入操作，统一放在 data 层管理。

DataManager.get_optuna_data() 委托到此模块。
DataStore 不再包含这些方法。

数据库路径由 data 层管理（通过 models.database），
外部调用方无需关心 DB 位置。
"""

from __future__ import annotations

import os
from typing import Any

from .models import RunStudy, database


def _f(val: Any) -> float:
    """安全转换 → float"""
    return float(val) if val is not None else 0.0


def _query_study_direction(study_name: str) -> list[tuple[Any, ...]]:
    return list(
        database.execute_sql(
            "SELECT direction FROM study_directions WHERE study_id=(SELECT study_id FROM studies WHERE study_name=?)",
            (study_name,),
        )
    )


def _query_trial_stats(study_name: str) -> tuple[list[int], list[float]]:
    rows = list(
        database.execute_sql(
            "SELECT t.number, tv.value FROM trials t "
            "LEFT JOIN trial_values tv ON t.trial_id = tv.trial_id "
            "WHERE t.study_id=(SELECT study_id FROM studies WHERE study_name=?) "
            "AND t.state='COMPLETE' "
            "ORDER BY t.number",
            (study_name,),
        )
    )
    nums = [r[0] for r in rows]
    values = [_f(r[1] or 0) for r in rows]
    return nums, values


def _query_param_rows(study_name: str) -> list[tuple[Any, ...]]:
    return list(
        database.execute_sql(
            "SELECT t.number, tp.param_name, tp.param_value "
            "FROM trials t JOIN trial_params tp ON t.trial_id = tp.trial_id "
            "WHERE t.study_id=(SELECT study_id FROM studies WHERE study_name=?) "
            "AND t.state='COMPLETE' "
            "ORDER BY t.number, tp.param_name",
            (study_name,),
        )
    )


def _query_best_params(study_name: str, agg_func: str) -> list[tuple[Any, ...]]:
    return list(
        database.execute_sql(
            f"""
            SELECT tp.param_name, tp.param_value FROM trial_params tp
            JOIN trial_values tv ON tp.trial_id = tv.trial_id
            JOIN trials t ON t.trial_id = tp.trial_id
            WHERE t.study_id=(SELECT study_id FROM studies WHERE study_name=?)
              AND tv.value=(
                  SELECT {agg_func}(tv2.value) FROM trial_values tv2
                  JOIN trials t2 ON tv2.trial_id=t2.trial_id
                  WHERE t2.study_id=(SELECT study_id FROM studies WHERE study_name=?))
            """,
            (study_name, study_name),
        )
    )


def get_optuna_data(run_id: int) -> dict[str, object] | None:
    """获取 Optuna 优化数据

    Args:
        run_id: 运行记录 ID

    Returns:
        {
            "study_name": "...",
            "trial_count": N,
            "trial_nums": [...],
            "trial_values": [...],
            "best_params": [{"name": ..., "value": ...}],
            "param_scatter": ...,
            "report_file": ...,
        }
        若无关联 study 返回 None
    """
    study_rows = list(RunStudy.select(RunStudy.study_name).where(RunStudy.run_id == run_id).dicts())
    if not study_rows:
        return None

    study_name = study_rows[0]["study_name"]

    direction_row = _query_study_direction(study_name)
    is_maximize = direction_row and direction_row[0][0] == "MAXIMIZE"
    agg_func = "MAX" if is_maximize else "MIN"

    trial_nums, trial_values = _query_trial_stats(study_name)
    params_rows = _query_param_rows(study_name)
    best = _query_best_params(study_name, agg_func)

    param_names = sorted(set(p[1] for p in params_rows))
    param_scatter = None
    if len(param_names) >= 2:
        p1, p2 = param_names[0], param_names[1]
        param_scatter = {
            "x_label": p1,
            "y_label": p2,
            "x_vals": [_f(p[2]) for p in params_rows if p[1] == p1],
            "y_vals": [_f(p[2]) for p in params_rows if p[1] == p2],
            "scores": trial_values,
        }

    return {
        "study_name": study_name,
        "trial_count": len(trial_nums),
        "trial_nums": trial_nums,
        "trial_values": trial_values,
        "best_params": [{"name": p[0], "value": _f(p[1])} for p in best],
        "param_scatter": param_scatter,
        "report_file": f"optimization_{study_name}.html",
    }


def link_study(run_id: int, study_name: str) -> None:
    """关联 run 与 Optuna study"""
    RunStudy.get_or_create(run_id=run_id, study_name=study_name)


def get_optuna_url() -> str:
    """获取 Optuna 数据库的 SQLite 存储 URL

    数据库路径由 data 层内部管理（从已初始化的 peewee database 连接读取），
    调用方无需关心具体路径。

    Returns:
        sqlite:/// 格式的 URL
    """
    db_path = database.database
    if not db_path:
        raise RuntimeError("Optuna storage requires an initialized data environment")
    abs_path = os.path.abspath(str(db_path))
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    return f"sqlite:///{abs_path}"


def get_best_trial_index(run_id: int) -> int:
    """获取最优 trial 的编号（用于 trades.json 导出过滤）"""
    try:
        rows = list(
            database.execute_sql(
                "SELECT t.number FROM trials t "
                "JOIN trial_values tv ON t.trial_id = tv.trial_id "
                "WHERE t.study_id=(SELECT s.study_id FROM studies s "
                "  JOIN run_studies rs ON rs.study_name=s.study_name "
                "  WHERE rs.run_id=?) "
                "AND t.state='COMPLETE' "
                "ORDER BY tv.value DESC LIMIT 1",
                (run_id,),
            )
        )
        if rows:
            return int(rows[0][0])
    except Exception:
        pass
    return 0
