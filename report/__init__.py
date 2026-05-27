# -*- coding: utf-8 -*-
"""报告生成模块 — Jinja2 模板 + 数据查询"""

from pathlib import Path
from typing import Any

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

    # ── BT-INFO 数据/策略信息 ──
    import sqlite3, pandas as pd
    info = _build_info(bt, trades, daily)

    # ── K 线图 (买卖点标注) ──
    kline_div = _build_kline_chart(bt, trades)

    fig = create_figure(bt, daily, trades)
    plotly_div = fig.to_html(full_html=False, include_plotlyjs='cdn')

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
        info=info,
        cards=cards,
        kline_div=kline_div,
        plotly_div=plotly_div,
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
    build_nav(dm.store.db_path, output_dir)

    return str(filepath.resolve())


def _build_info(bt: Any, trades: list, daily: list) -> dict:
    """构建 BT-INFO 数据"""
    import sqlite3
    conn = sqlite3.connect(".quant_shared_data/quant_shared.db")
    params = conn.execute(
        "SELECT param_name, param_value FROM backtest_params WHERE backtest_id=? ORDER BY param_name",
        (bt.id,),
    ).fetchall()
    conn.close()

    days = len(daily) if daily else 0
    dates = [d.get('date', '') for d in daily] if daily else []
    return {
        'symbol': bt.symbol,
        'strategy': bt.strategy,
        'date_range': f"{dates[0]} ~ {dates[-1]}" if dates else "N/A",
        'trading_days': days,
        'interval': getattr(bt, 'kline_interval', '1m') or '1m',
        'initial_capital': f"{float(bt.initial_capital or 0):,.0f}",
        'total_trades': len(trades),
        'params': [{'name': p[0], 'value': f"{float(p[1]):.4g}"} for p in params],
    }


def _build_kline_chart(bt: Any, trades: list) -> str:
    """生成带买卖点标注的 K 线图（每日 OHLC）"""
    from common.constants import TRADE_ACTION_BUY, TRADE_DIRECTION_SHORT
    import pandas as pd, json, os, plotly.graph_objects as go
    from plotly.subplots import make_subplots

    # 加载原始 K 线数据并 resample 到日线
    try:
        import sqlite3
        conn = sqlite3.connect(".quant_shared_data/quant_shared.db")
        row = conn.execute(
            "SELECT filepath FROM export_metadata WHERE symbol=? AND interval=? LIMIT 1",
            (bt.symbol, getattr(bt, 'kline_interval', '1m') or '1m'),
        ).fetchone()
        conn.close()
        if row and os.path.exists(row[0]):
            df = pd.read_csv(row[0])
            df['datetime'] = pd.to_datetime(df['datetime'])
            df['date'] = df['datetime'].dt.date
            ohlc = df.groupby('date').agg(
                open=('open', 'first'), high=('high', 'max'),
                low=('low', 'min'), close=('close', 'last'),
            ).reset_index()
        else:
            return ""
    except Exception:
        return ""

    if ohlc.empty:
        return ""

    fig = make_subplots(rows=1, cols=1)
    dates = ohlc['date'].astype(str).tolist()

    fig.add_trace(go.Candlestick(
        x=dates, open=ohlc['open'], high=ohlc['high'],
        low=ohlc['low'], close=ohlc['close'],
        name='K线', increasing_line_color='#ef4444', decreasing_line_color='#22c55e',
        showlegend=False,
    ))

    # 买卖标记
    buy_dates, buy_prices = [], []
    sell_dates, sell_prices = [], []
    for t in trades:
        if hasattr(t, 'model_dump'):
            td = t.model_dump()
        elif hasattr(t, '__dict__'):
            td = vars(t)
        else:
            td = t
        dt = str(td.get('datetime', ''))[:10]
        price = float(td.get('open_price', td.get('price', 0)))
        direction = str(td.get('direction', ''))
        offset = str(td.get('offset', ''))
        if direction in (TRADE_DIRECTION_SHORT, '空') or (direction == TRADE_ACTION_BUY and offset == 'open'):
            buy_dates.append(dt); buy_prices.append(price)
        else:
            sell_dates.append(dt); sell_prices.append(price)

    if buy_dates:
        fig.add_trace(go.Scatter(x=buy_dates, y=buy_prices, mode='markers',
            marker=dict(symbol='triangle-up', size=10, color='#ef4444', line=dict(width=1, color='white')),
            name='买入', showlegend=True))
    if sell_dates:
        fig.add_trace(go.Scatter(x=sell_dates, y=sell_prices, mode='markers',
            marker=dict(symbol='triangle-down', size=10, color='#22c55e', line=dict(width=1, color='white')),
            name='卖出', showlegend=True))

    fig.update_layout(
        height=500, margin=dict(l=40, r=20, t=10, b=40),
        xaxis_rangeslider_visible=False, hovermode='x unified',
        legend=dict(orientation='h', y=1.02),
    )
    return fig.to_html(full_html=False, include_plotlyjs=False)


__all__ = [
    'format_single_report',
    'format_summary_report',
    'build_report',
    'build_all',
    'build_dashboard',
    'build_nav',
    'build_optimizer_report',
]
