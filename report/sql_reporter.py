"""基于 SQLite 数据库的回测报告生成器 (强类型)

完全解耦：仅依赖 data.manager.DataManager (只读查询) + common (纯函数工具)，
不 import backtest / strategies / data.exporter 等业务模块。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from data import DataManager, BacktestRecord, TradeRecord
from common.stats import compute_summary_stats, rank_by_key
from common.formatting import format_pct, format_float, ensure_float
from common.constants import (
    TRADE_DIRECTION_LONG,
    TRADE_DIRECTION_SHORT,
    TRADE_OFFSET_OPEN,
    TRADE_OFFSET_CLOSE,
    STATUS_SUCCESS,
    STATUS_FAILED,
)

logger = logging.getLogger(__name__)


def _na_str(v) -> str:
    """将可能为 None 的值转为展示字符串"""
    return 'N/A' if v is None else str(v)


def _get_attr(obj, key, default=None):
    """获取对象属性值（支持 dict 或 Pydantic model）"""
    if hasattr(obj, key):
        return getattr(obj, key, default)
    return obj.get(key, default) if isinstance(obj, dict) else default


def format_single_report(db_path: str, backtest_id: int) -> str:
    """生成单次回测的完整文本报告

    Args:
        db_path: 数据库路径
        backtest_id: 回测记录 ID

    Returns:
        格式化的控制台报告字符串
    """
    dm = DataManager()
    bt = dm.get_backtest(backtest_id)
    
    if not bt:
        return f"错误: 未找到回测记录 id={backtest_id}"

    trades = dm.query_trades(backtest_id)

    trade_days: list[str] = sorted(set(
        str(_get_attr(t, 'datetime'))[:10] for t in trades if _get_attr(t, 'datetime')
    ))
    buy_count: int = sum(
        1 for t in trades 
        if _get_attr(t, 'direction') == TRADE_DIRECTION_LONG and _get_attr(t, 'offset') == TRADE_OFFSET_OPEN
    )
    sell_count: int = sum(
        1 for t in trades 
        if _get_attr(t, 'direction') == TRADE_DIRECTION_SHORT and _get_attr(t, 'offset') == TRADE_OFFSET_CLOSE
    )

    symbol = bt.symbol
    strategy = bt.strategy
    status = bt.status

    lines: list[str] = [
        f"{'=' * 70}",
        f"  回测报告 #{backtest_id}",
        f"{'=' * 70}",
        "",
        "【基本信息】",
        f"  品种:       {symbol}",
        f"  策略:       {strategy}",
        f"  状态:       {status}",
        f"  运行时间:   {_get_attr(bt, 'created_at')}",
    ]

    if status == STATUS_FAILED:
        error_msg = _get_attr(bt, 'error_message') or 'N/A'
        lines.append(f"  错误信息:   {error_msg}")
        lines.append(f"{'=' * 70}")
        return '\n'.join(lines)

    lines += [
        "",
        "【数据范围】",
        f"  数据区间:   {_na_str(_get_attr(bt, 'start_date'))} ~ {_na_str(_get_attr(bt, 'end_date'))}",
        f"  交易日数:   {_na_str(None)}",
        "",
        "【资金概况】",
        f"  总收益率:   {format_pct(_get_attr(bt, 'total_return'))}",
        "",
        "【交易统计】",
        f"  总交易次数: {_get_attr(bt, 'total_trades', 0) or 0}",
        f"  盈利交易:   {_get_attr(bt, 'profit_trades', 0) or 0}  ({format_pct(_get_attr(bt, 'win_rate'))})",
        f"  亏损交易:   {_get_attr(bt, 'loss_trades', 0) or 0}",
        f"  平均盈利:   {format_float(_get_attr(bt, 'avg_profit'), ',.0f')}",
        f"  平均亏损:   {format_float(_get_attr(bt, 'avg_loss'), ',.0f')}",
        "",
        "【风险评估】",
        f"  夏普比率:   {format_float(_get_attr(bt, 'sharpe_ratio'))}",
        f"  最大回撤:   {format_pct(_get_attr(bt, 'max_drawdown'))}",
        "",
        "【交易明细】",
        f"  成交笔数:   {len(trades)} (开仓{buy_count} / 平仓{sell_count})",
        f"  交易日期:   {len(trade_days)} 天",
    ]

    if trades:
        lines += [
            "",
            f"  {'时间':<20} {'标的':<16} {'方向':>5} {'开平':>4} {'价格':>9} {'手数':>4}",
            f"  {'-' * 63}",
        ]
        for t in trades[-20:]:
            d_tag: str = '多' if _get_attr(t, 'direction') == TRADE_DIRECTION_LONG else '空'
            o_tag: str = '开' if _get_attr(t, 'offset') == TRADE_OFFSET_OPEN else '平'
            price = _get_attr(t, 'close_price') or _get_attr(t, 'open_price', 0)
            qty = _get_attr(t, 'quantity', 0)
            lines.append(
                f"  {_get_attr(t, 'datetime'):<20} "
                f"{_get_attr(t, 'symbol'):<16} "
                f"{d_tag:>5} {o_tag:>4} "
                f"{ensure_float(price):>9.2f} "
                f"{qty:>4}"
            )

    lines.append(f"{'=' * 70}")
    return '\n'.join(lines)


def format_comparison_report(
    db_path: str,
    backtest_ids: list[int],
    save_json: bool = False,
    output_dir: str = ".quant_shared_data/reports",
) -> str:
    """比较多条回测记录并生成排名报告

    Args:
        db_path: 数据库路径
        backtest_ids: 要对比的回测 ID 列表
        save_json: 是否保存 JSON 文件
        output_dir: JSON 输出目录

    Returns:
        格式化的对比报告字符串
    """
    dm = DataManager()
    records: list[BacktestRecord] = []
    for bid in backtest_ids:
        bt = dm.get_backtest(bid)
        if bt and bt.status == STATUS_SUCCESS:
            records.append(bt)

    if not records:
        return "错误: 没有找到有效的回测记录"

    symbols_data: list[dict] = []
    for bt in records:
        sym: str = bt.symbol or 'N/A'
        strat: str = bt.strategy or 'N/A'
        symbols_data.append({
            'id': bt.id,
            'symbol': sym,
            'strategy': strat,
            'total_return': ensure_float(bt.total_return),
            'annual_return': 0.0,
            'sharpe_ratio': ensure_float(bt.sharpe_ratio),
            'max_drawdown': ensure_float(bt.max_drawdown),
            'win_rate': ensure_float(bt.win_rate),
            'win_loss_ratio': bt.avg_profit / abs(bt.avg_loss) if bt.avg_loss else 0,
            'total_trades': bt.total_trades or 0,
            'created_at': bt.created_at or '',
        })

    returns: list[float] = [s['total_return'] for s in symbols_data]
    sharpes: list[float] = [s['sharpe_ratio'] for s in symbols_data]
    drawdowns: list[float] = [s['max_drawdown'] for s in symbols_data]
    win_rates: list[float] = [s['win_rate'] for s in symbols_data]

    agg: dict = {
        'total_return': compute_summary_stats(returns),
        'sharpe_ratio': compute_summary_stats(sharpes),
        'max_drawdown': compute_summary_stats(drawdowns),
        'win_rate': compute_summary_stats(win_rates),
        'total_trades': sum(s.get('total_trades', 0) for s in symbols_data),
        'symbol_count': len(symbols_data),
        'profitable_ratio': (sum(1 for v in returns if v > 0) / len(returns)) if returns else 0,
    }

    ranking: dict = {
        'total_return': rank_by_key(symbols_data, 'total_return'),
        'sharpe_ratio': rank_by_key(symbols_data, 'sharpe_ratio'),
        'max_drawdown': rank_by_key(symbols_data, 'max_drawdown', reverse=False),
        'win_rate': rank_by_key(symbols_data, 'win_rate'),
    }

    if save_json:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        merged: dict = {
            'meta': {
                'backtest_ids': backtest_ids,
                'symbol_count': len(symbols_data),
                'generated_at': datetime.now().isoformat(),
            },
            'symbols': symbols_data,
            'ranking': ranking,
            'aggregate': agg,
        }
        merged_path = out_dir / "comparison_report.json"
        with open(merged_path, 'w', encoding='utf-8') as f:
            json.dump(merged, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"对比报告已保存: {merged_path}")

    lines: list[str] = [
        f"{'=' * 80}",
        f"  多品种 / 多次回测对比报告",
        f"{'=' * 80}",
        f"  对比数: {len(symbols_data)}  |  总交易次数: {agg['total_trades']}",
        f"  盈利比: {float(agg['profitable_ratio']):.0%}",
        "",
        "【品种关键指标】",
        f"  {'#':>4} {'品种':<18} {'收益率':>8} {'夏普':>7} {'回撤':>7} {'胜率':>7} {'交易':>6}",
        f"  {'-' * 65}",
    ]

    for s in symbols_data:
        lines.append(
            f"  {s['id']:>4} {s['symbol']:<18} "
            f"{format_pct(s['total_return']):>8} "
            f"{format_float(s['sharpe_ratio']):>7} "
            f"{format_pct(s['max_drawdown']):>7} "
            f"{format_pct(s['win_rate']):>7} "
            f"{s['total_trades']:>6}"
        )

    lines += [
        "",
        "【整体聚合统计】",
    ]

    _stat_formatters: list[tuple] = [
        ('total_return', '总收益率', '.2%'),
        ('sharpe_ratio', '夏普比率', '.2f'),
        ('max_drawdown', '最大回撤', '.2%'),
        ('win_rate', '胜率', '.2%'),
    ]

    for metric_name, label, fmt in _stat_formatters:
        s = agg.get(metric_name, {})
        if isinstance(s, dict) and fmt.startswith('.2%'):
            lines.append(
                f"  {label}: 均值={format_pct(s.get('mean'))}  "
                f"中位数={format_pct(s.get('median'))}  "
                f"范围=[{format_pct(s.get('min'))}, {format_pct(s.get('max'))}]"
            )
        elif isinstance(s, dict):
            lines.append(
                f"  {label}: 均值={format_float(s.get('mean'))}  "
                f"中位数={format_float(s.get('median'))}  "
                f"范围=[{format_float(s.get('min'))}, {format_float(s.get('max'))}]"
            )

    lines += [
        "",
        "【各指标排名 TOP 3】",
    ]

    _metric_labels: list[tuple] = [
        ('total_return', '收益率'),
        ('sharpe_ratio', '夏普比率'),
        ('max_drawdown', '回撤(低)'),
        ('win_rate', '胜率'),
    ]

    for metric, label in _metric_labels:
        items = ranking.get(metric, [])[:3]
        names: list[str] = []
        for it in items:
            val = it.get(metric)
            if isinstance(val, (int, float)):
                fmt_val: str = f"{val:.2%}" if abs(val) <= 1 else f"{val / 100:.2%}"
            else:
                fmt_val = 'N/A'
            sym = it.get('symbol', '?')
            names.append(f"{sym}({fmt_val})")
        lines.append(f"  {label}: {' > '.join(names) if names else 'N/A'}")

    lines.append(f"{'=' * 80}")
    return '\n'.join(lines)


def format_summary_report(
    db_path: str,
    symbol: Optional[str] = None,
    strategy: Optional[str] = None,
    limit: int = 20,
) -> str:
    """生成最近回测的汇总列表

    Args:
        db_path: 数据库路径
        symbol: 品种过滤
        strategy: 策略过滤
        limit: 最大条数

    Returns:
        格式化的汇总表格
    """
    dm = DataManager()
    records = dm.query_backtests(
        symbol=symbol,
        strategy=strategy,
        status=STATUS_SUCCESS,
        limit=limit,
    )

    if not records:
        filters: list[str] = []
        if symbol:
            filters.append(f"品种={symbol}")
        if strategy:
            filters.append(f"策略={strategy}")
        fstr: str = ', '.join(filters) if filters else '全部'
        return f"未找到符合条件的回测记录 ({fstr})"

    lines: list[str] = [
        f"{'=' * 90}",
        f"  回测汇总 ({len(records)} 条)",
        f"{'=' * 90}",
        f"  {'#':>5} {'品种':<18} {'策略':<6} {'收益率':>8} {'夏普':>7} {'回撤':>7} {'胜率':>7} {'交易':>5} {'时间':<16}",
        f"  {'-' * 80}",
    ]

    for bt in records:
        sym: str = bt.symbol or 'N/A'
        strat: str = bt.strategy or 'N/A'
        created: str = str(bt.created_at or '')[:16]
        lines.append(
            f"  {bt.id:>5} "
            f"{sym:<18} "
            f"{strat:<6} "
            f"{format_pct(bt.total_return):>8} "
            f"{format_float(bt.sharpe_ratio):>7} "
            f"{format_pct(bt.max_drawdown):>7}  "
            f"{format_pct(bt.win_rate):>7} "
            f"{bt.total_trades or 0:>5} "
            f"{created:<16}"
        )

    lines.append(f"{'=' * 90}")
    lines.append(f"  使用 'python main.py report --id <ID>' 查看完整报告")
    return '\n'.join(lines)
