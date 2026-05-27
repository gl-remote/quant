# -*- coding: utf-8 -*-
"""Optuna 数据查询"""

import sqlite3
from typing import Any


def get_optuna_data(db_path: str, run_id: int) -> dict[str, Any] | None:
    """获取 Optuna 优化数据"""
    conn = sqlite3.connect(db_path)
    study_rows = conn.execute(
        "SELECT study_name FROM run_studies WHERE run_id=?", (run_id,)
    ).fetchall()
    if not study_rows:
        conn.close()
        return None

    study_name = study_rows[0][0]
    study = conn.execute(
        "SELECT study_id FROM studies WHERE study_name=? LIMIT 1", (study_name,)
    ).fetchone()
    if not study:
        conn.close()
        return None

    study_id = study[0]

    trials = conn.execute("""
        SELECT t.number, tv.value FROM trials t
        LEFT JOIN trial_values tv ON t.trial_id = tv.trial_id
        WHERE t.study_id=? AND t.state='COMPLETE'
        ORDER BY t.number
    """, (study_id,)).fetchall()

    params_rows = conn.execute("""
        SELECT t.number, tp.param_name, tp.param_value
        FROM trials t JOIN trial_params tp ON t.trial_id = tp.trial_id
        WHERE t.study_id=? AND t.state='COMPLETE'
        ORDER BY t.number, tp.param_name
    """, (study_id,)).fetchall()

    best = conn.execute("""
        SELECT tp.param_name, tp.param_value FROM trial_params tp
        JOIN trial_values tv ON tp.trial_id = tv.trial_id
        JOIN trials t ON t.trial_id = tp.trial_id
        WHERE t.study_id=? AND tv.value=(
            SELECT MIN(tv2.value) FROM trial_values tv2
            JOIN trials t2 ON tv2.trial_id=t2.trial_id WHERE t2.study_id=?)
    """, (study_id, study_id)).fetchall()

    conn.close()

    trial_nums = [t[0] for t in trials]
    trial_values = [float(t[1] or 0) for t in trials]

    param_names = sorted(set(p[1] for p in params_rows))
    param_scatter = None
    if len(param_names) >= 2:
        p1, p2 = param_names[0], param_names[1]
        param_scatter = {
            'x_label': p1, 'y_label': p2,
            'x_vals': [float(p[2]) for p in params_rows if p[1] == p1],
            'y_vals': [float(p[2]) for p in params_rows if p[1] == p2],
            'scores': trial_values,
        }

    return {
        'study_name': study_name,
        'trial_count': len(trials),
        'trial_nums': trial_nums,
        'trial_values': trial_values,
        'best_params': [{'name': p[0], 'value': float(p[1])} for p in best],
        'param_scatter': param_scatter,
    }
