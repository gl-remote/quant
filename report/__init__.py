# -*- coding: utf-8 -*-
"""报告生成模块 — Jinja2 模板 + 数据查询"""

from pathlib import Path

from data import DataManager
from .reports import format_single_report, format_summary_report
from .charts import create_figure
from .builder import build_all, build_dashboard, build_nav
from .optimizer_report import build_optimizer_report

from jinja2 import Environment, PackageLoader, select_autoescape

_j2 = Environment(
    loader=PackageLoader("report", "templates"),
    autoescape=select_autoescape(["html"]),
)


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

    # 交易明细
    trade_list = []
    for t in trades[:100]:
        if hasattr(t, 'model_dump'):
            td = t.model_dump()
        elif hasattr(t, '__dict__'):
            td = vars(t)
        else:
            td = t
        pnl = float(td.get('pnl', 0))
        trade_list.append({
            'dt': str(td.get('datetime', ''))[:16],
            'dir': str(td.get('direction', '')),
            'offset': str(td.get('offset', '')),
            'price': f"{float(td.get('open_price', td.get('price', 0))):.0f}",
            'vol': int(td.get('quantity', td.get('volume', 0))),
            'pnl': f"{pnl:+.0f}",
            'cls': 'positive' if pnl > 0 else 'negative' if pnl < 0 else '',
        })

    total_trades = len(trades)
    if total_trades > 100:
        total_trades_text = str(total_trades)
    else:
        total_trades_text = ""

    # 指标卡片
    total_return = float(bt.total_return or 0)
    ret_color = '#28A745' if total_return >= 0 else '#DC3545'
    cards = [
        f'<div class="card"><div class="card-label">总收益率</div><div class="card-value" style="color:{ret_color}">{total_return:.2%}</div></div>',
        f'<div class="card"><div class="card-label">夏普比率</div><div class="card-value">{float(bt.sharpe_ratio or 0):.2f}</div></div>',
        f'<div class="card"><div class="card-label">最大回撤</div><div class="card-value" style="color:#DC3545">{float(bt.max_drawdown or 0):.2%}</div></div>',
        f'<div class="card"><div class="card-label">胜率</div><div class="card-value">{float(bt.win_rate or 0):.1%}</div></div>',
        f'<div class="card"><div class="card-label">交易次数</div><div class="card-value">{bt.total_trades or 0}</div></div>',
        f'<div class="card"><div class="card-label">年化收益</div><div class="card-value">{(float(getattr(bt, "annual_return", 0) or 0)):.2%}</div></div>',
        f'<div class="card"><div class="card-label">初始资金</div><div class="card-value">{float(bt.initial_capital or 0):,.0f}</div></div>',
        f'<div class="card"><div class="card-label">最终权益</div><div class="card-value">{(float(getattr(bt, "end_balance", 0) or 0)):,.0f}</div></div>',
    ]

    html = _j2.get_template("single_report.html").render(
        title=f"回测报告 #{bt.id} — {bt.symbol} / {bt.strategy}",
        cards=cards,
        plotly_div=plotly_div,
        trades=trade_list,
        total_trades=total_trades_text,
    )

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
    'build_all',
    'build_dashboard',
    'build_nav',
    'build_optimizer_report',
]
