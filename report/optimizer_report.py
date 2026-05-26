# -*- coding: utf-8 -*-
"""Optuna 优化报告看板

从 Optuna study 生成 HTML 可视化报告，嵌入优化历史、参数重要性、
等高线图到统一模板中。

用法:
    from report.optimizer_report import build_optimizer_report

    html = build_optimizer_report(study_db_url, study_name)
    with open("optimization_report.html", "w") as f:
        f.write(html)
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def build_optimizer_report(
    study_db_url: str,
    study_name: str,
    best_params: dict[str, Any] | None = None,
    best_value: float | None = None,
    backtest_ids: list[int] | None = None,
) -> str:
    """生成 Optuna 优化报告 HTML

    Args:
        study_db_url: SQLite storage URL (e.g. "sqlite:///path/to/optuna_studies.db")
        study_name: Optuna study 名称
        best_params: 最优参数
        best_value: 最优目标值
        backtest_ids: 关联的回测 ID 列表

    Returns:
        完整 HTML 字符串
    """
    import optuna  # pyright: ignore[reportMissingImports]
    from optuna.visualization import (  # pyright: ignore[reportMissingImports]
        plot_optimization_history,
        plot_param_importances,
        plot_parallel_coordinate,
        plot_contour,
    )

    study = optuna.load_study(study_name=study_name, storage=study_db_url)

    figures: list[str] = []
    for plot_func, label in [
        (plot_optimization_history, "优化历史"),
        (plot_param_importances, "参数重要性"),
        (plot_parallel_coordinate, "平行坐标"),
        (plot_contour, "等高线图"),
    ]:
        try:
            fig = plot_func(study)
            fig.update_layout(
                title=label,
                margin=dict(l=40, r=40, t=50, b=40),
                height=400,
            )
            figures.append(
                f'<div class="chart"><h3 class="chart-title">{label}</h3>'
                f'{fig.to_html(full_html=False, include_plotlyjs=False)}</div>'
            )
        except Exception as e:
            logger.warning("Optuna 图表生成失败 [%s]: %s", label, e)
            figures.append(
                f'<div class="chart"><h3 class="chart-title">{label}</h3>'
                f'<p style="color:#999; padding:20px; text-align:center;">'
                f'无法生成（{e}）</p></div>'
            )

    params_html = ""
    if best_params:
        items = "".join(
            f'<div class="card"><div class="card-label">{k}</div>'
            f'<div class="card-value" style="color:#28A745;">{v}</div></div>'
            for k, v in best_params.items()
        )
        params_html = f'<div class="metrics">{items}</div>'

    ids_info = ""
    if backtest_ids:
        ids_str = ", ".join(str(i) for i in backtest_ids[:20])
        ids_info = (
            f'<p style="color:#666; margin:8px 0;">'
            f'关联回测ID: {ids_str}'
            f'{"..." if len(backtest_ids) > 20 else ""}</p>'
        )

    score_color = '#28A745' if (best_value or 0) >= 0 else '#DC3545'
    return _OPT_TEMPLATE.format(
        title=f"Optuna 优化报告 — {study_name}",
        score=f"{best_value:.4f}" if best_value is not None else "N/A",
        score_color=score_color,
        params_html=params_html,
        ids_info=ids_info,
        figures="\n".join(figures),
    )


_OPT_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, "Noto Sans SC", sans-serif;
    background: #f5f6fa;
    color: #333;
    padding: 20px;
}}
.container {{ max-width: 1200px; margin: 0 auto; }}
.header {{
    text-align: center;
    padding: 24px 0 8px;
}}
.header h1 {{
    font-size: 24px;
    font-weight: 600;
    color: #1a1a2e;
}}
.header .score {{
    font-size: 36px;
    font-weight: 700;
    margin: 12px 0 4px;
}}
.header .score-label {{
    font-size: 14px;
    color: #888;
}}
.metrics {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 10px;
    margin: 16px 0;
}}
.card {{
    background: #fff;
    border-radius: 8px;
    padding: 14px;
    text-align: center;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}}
.card-label {{
    font-size: 11px;
    color: #888;
    margin-bottom: 4px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
.card-value {{
    font-size: 18px;
    font-weight: 700;
}}
.chart {{
    background: #fff;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}}
.chart-title {{
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 8px;
    color: #555;
}}
.footer {{
    text-align: center;
    padding: 16px;
    font-size: 12px;
    color: #aaa;
}}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>{title}</h1>
        <div class="score" style="color:{score_color}">{score}</div>
        <div class="score-label">最优得分 (mean sharpe)</div>
    </div>
    {params_html}
    {ids_info}
    {figures}
    <div class="footer">
        Generated by quant v0.2.0 &middot; Powered by Optuna + Plotly
    </div>
</div>
</body>
</html>"""
