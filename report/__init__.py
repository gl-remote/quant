# -*- coding: utf-8 -*-
"""
报告生成模块

从数据库读取回测数据，生成文字报告和交互式 HTML 可视化。

  - single.py:          单次回测文字报告 (format_single_report)
  - summary.py:         回测记录汇总 (format_summary_report)
  - charts.py:          plotly 图表生成
  - _html.py:           HTML 模板渲染
  - optimizer_report.py: Optuna 优化看板 (build_optimizer_report)
"""

from pathlib import Path

from data import DataManager
from .reports import format_single_report, format_summary_report
from .charts import create_figure
from ._html import render_html
from .optimizer_report import build_optimizer_report


def build_report(
    dm: DataManager,
    backtest_id: int,
    output_dir: str = "output",
) -> str | None:
    """生成回测可视化 HTML 报告

    若有 run_id，报告自动归入 output/r{run_id}/。
    生成后自动刷新 index.html 导航页。

    Args:
        dm: DataManager 实例
        backtest_id: 回测记录 ID
        output_dir: 输出根目录，默认为 output/

    Returns:
        生成的 HTML 文件路径，若回测不存在则返回 None
    """
    bt = dm.get_backtest(backtest_id)
    if not bt:
        return None

    trades = dm.query_trades(backtest_id)
    daily = dm.query_daily(backtest_id)

    fig = create_figure(bt, daily, trades)
    plotly_div = fig.to_html(full_html=False, include_plotlyjs='cdn')

    html = render_html(bt, plotly_div)

    # 如果有 run，归入 output/r{run}/
    if bt.run:
        out_path = Path(output_dir) / f"r{bt.run}"
    else:
        out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    filepath = out_path / f"backtest_{backtest_id}.html"
    filepath.write_text(html, encoding='utf-8')

    # 刷新导航页
    from .dashboard import build_nav
    build_nav(dm.store.db_path, output_dir)

    return str(filepath.resolve())


__all__ = [
    'format_single_report',
    'format_summary_report',
    'build_report',
    'build_optimizer_report',
]
