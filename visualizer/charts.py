# -*- coding: utf-8 -*-
"""
Plotly 图表生成

基于 BacktestRecord + daily 数据 + trade 数据生成多子图交互式图表。
"""

from __future__ import annotations

from typing import Dict, List, Optional
from datetime import datetime

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from common.constants import (
    TRADE_DIRECTION_LONG,
    TRADE_OFFSET_OPEN,
    TRADE_OFFSET_CLOSE,
    STATUS_FAILED,
)
from data.models import BacktestRecord


def create_figure(
    bt: BacktestRecord,
    daily: List[Dict],
    trades: List,
) -> go.Figure:
    """生成回测可视化图表

    布局:
        Row 1: 资金曲线 + 买卖信号标注
        Row 2: 回撤曲线（填充区域）
        Row 3: 日收益柱状图

    Args:
        bt: 回测记录
        daily: 每日资金曲线数据列表
        trades: 交易明细列表

    Returns:
        plotly Figure 对象
    """
    if bt.status == STATUS_FAILED or not daily:
        return _empty_figure(bt)

    dates: List[str] = [d.get('date', '') for d in daily]
    equities: List[float] = [d.get('equity', 0) for d in daily]
    drawdowns: List[float] = [d.get('drawdown', 0) for d in daily]
    daily_returns: List[float] = [d.get('daily_return', 0) for d in daily]

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        row_heights=[0.5, 0.25, 0.25],
        subplot_titles=('资金曲线', '回撤', '日收益'),
    )

    # ── Row 1: 资金曲线 ──
    fig.add_trace(
        go.Scatter(
            x=dates, y=equities,
            mode='lines',
            name='权益',
            line=dict(color='#2962FF', width=2),
            hovertemplate='%{x}<br>权益: %{y:,.0f}<extra></extra>',
        ),
        row=1, col=1,
    )

    # 初始资金参考线
    if bt.initial_capital:
        fig.add_hline(
            y=bt.initial_capital,
            line_dash='dash',
            line_color='gray',
            opacity=0.5,
            row=1, col=1,
        )

    # 买卖信号标注
    _add_trade_markers(fig, trades, dates, equities, row=1, col=1)

    # ── Row 2: 回撤 ──
    fig.add_trace(
        go.Scatter(
            x=dates, y=drawdowns,
            mode='lines',
            name='回撤',
            fill='tozeroy',
            fillcolor='rgba(220, 53, 69, 0.15)',
            line=dict(color='#DC3545', width=1.5),
            hovertemplate='%{x}<br>回撤: %{y:.2%}<extra></extra>',
        ),
        row=2, col=1,
    )

    # ── Row 3: 日收益 ──
    colors = ['#DC3545' if r < 0 else '#28A745' for r in daily_returns]
    fig.add_trace(
        go.Bar(
            x=dates, y=daily_returns,
            name='日收益',
            marker_color=colors,
            hovertemplate='%{x}<br>日收益: %{y:+,.0f}<extra></extra>',
        ),
        row=3, col=1,
    )

    # ── 全局布局 ──
    fig.update_layout(
        height=800,
        hovermode='x unified',
        showlegend=False,
        margin=dict(l=40, r=20, t=40, b=40),
        paper_bgcolor='white',
        plot_bgcolor='white',
        font=dict(family='Arial, sans-serif', size=12, color='#333'),
    )

    fig.update_xaxes(showgrid=True, gridcolor='#eee', zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor='#eee', zeroline=False)

    # y 轴格式化
    fig.update_yaxes(title_text='权益', row=1, col=1)
    fig.update_yaxes(title_text='回撤', tickformat='.1%', row=2, col=1)
    fig.update_yaxes(title_text='收益', row=3, col=1)

    # 隐藏 row 1/2 的 x 轴标签（共享 row 3）
    fig.update_xaxes(showticklabels=False, row=1, col=1)
    fig.update_xaxes(showticklabels=False, row=2, col=1)

    return fig


def _add_trade_markers(
    fig: go.Figure,
    trades: List,
    dates: List[str],
    equities: List[float],
    row: int,
    col: int,
) -> None:
    """在资金曲线上标注买卖信号"""
    if not trades:
        return

    # 建立日期 → 权益的索引
    date_to_equity: Dict[str, float] = {}
    for i, d in enumerate(dates):
        if i < len(equities):
            date_to_equity[d] = equities[i]
    if not date_to_equity:
        return

    buy_x, buy_y, buy_text = [], [], []
    sell_x, sell_y, sell_text = [], [], []

    for t in trades:
        dt = _get_str(t, 'datetime', '')[:10]  # 取日期部分
        price = _get_float(t, 'close_price') or _get_float(t, 'open_price', 0)
        direction = str(_get_str(t, 'direction', '')).lower()
        offset = str(_get_str(t, 'offset', '')).lower()
        pnl = _get_float(t, 'pnl', 0)

        equity_val = date_to_equity.get(dt)
        if equity_val is None:
            continue

        if direction == TRADE_DIRECTION_LONG and offset == TRADE_OFFSET_OPEN:
            buy_x.append(dt)
            buy_y.append(equity_val)
            buy_text.append(f'买入 @ {price}')
        elif offset == TRADE_OFFSET_CLOSE:
            sell_x.append(dt)
            sell_y.append(equity_val)
            label = '卖出' if direction == TRADE_DIRECTION_LONG else '买入'
            sell_text.append(f'{label} @ {price} | PnL: {pnl:+,.0f}')

    if buy_x:
        fig.add_trace(
            go.Scatter(
                x=buy_x, y=buy_y,
                mode='markers',
                name='开仓',
                marker=dict(symbol='triangle-up', size=10, color='#28A745'),
                text=buy_text,
                hovertemplate='%{text}<extra></extra>',
            ),
            row=row, col=col,
        )

    if sell_x:
        fig.add_trace(
            go.Scatter(
                x=sell_x, y=sell_y,
                mode='markers',
                name='平仓',
                marker=dict(symbol='triangle-down', size=10, color='#DC3545'),
                text=sell_text,
                hovertemplate='%{text}<extra></extra>',
            ),
            row=row, col=col,
        )


def _empty_figure(bt: BacktestRecord) -> go.Figure:
    """回测失败或无数据时的占位图"""
    fig = go.Figure()
    fig.add_annotation(
        text=f"回测 #{bt.id}<br>{bt.status}",
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=18, color='#999'),
    )
    fig.update_layout(
        height=400,
        paper_bgcolor='white',
        plot_bgcolor='white',
        margin=dict(l=20, r=20, t=20, b=20),
    )
    return fig


def _get_str(obj, attr: str, default: str = '') -> str:
    val = getattr(obj, attr, default)
    return str(val) if val is not None else default


def _get_float(obj, attr: str, default: float = 0.0) -> float:
    val = getattr(obj, attr, default)
    try:
        return float(val)
    except (TypeError, ValueError):
        return default
