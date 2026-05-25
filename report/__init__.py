# -*- coding: utf-8 -*-
"""
报告生成模块

从数据库读取回测数据，生成文字报告和交互式 HTML 可视化。

  - single.py:  单次回测文字报告 (format_single_report)
  - summary.py: 回测记录汇总 (format_summary_report)
  - charts.py:  plotly 图表生成
  - _html.py:   HTML 模板渲染
"""

from pathlib import Path
from typing import Optional

from data import DataManager
from .single import format_single_report
from .summary import format_summary_report
from .charts import create_figure
from ._html import render_html


def build_report(
    dm: DataManager,
    backtest_id: int,
    output_dir: str = "output",
) -> Optional[str]:
    """生成回测可视化 HTML 报告

    Args:
        dm: DataManager 实例
        backtest_id: 回测记录 ID
        output_dir: 输出目录，默认为 output/

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

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    filepath = out_path / f"backtest_{backtest_id}.html"
    filepath.write_text(html, encoding='utf-8')

    return str(filepath.resolve())


__all__ = [
    'format_single_report',
    'format_summary_report',
    'build_report',
]
