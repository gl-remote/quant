"""回测记录汇总列表

从数据库查询回测记录列表，生成表格形式的控制台文本。
"""

from __future__ import annotations

from typing import Optional

from data import DataManager
from common.formatting import format_pct, format_float
from common.constants import STATUS_SUCCESS


def format_summary_report(
    dm: DataManager,
    symbol: Optional[str] = None,
    strategy: Optional[str] = None,
    limit: int = 20,
) -> str:
    """生成最近回测的汇总列表

    Args:
        dm: DataManager 实例
        symbol: 品种过滤
        strategy: 策略过滤
        limit: 最大条数

    Returns:
        格式化的汇总表格字符串
    """
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
        f"{'=' * 110}",
        f"  回测汇总 ({len(records)} 条)",
        f"{'=' * 110}",
        f"  {'#':>4} {'品种':<14} {'策略':<6} {'版本':<8} {'Git':<8} "
        f"{'收益率':>8} {'夏普':>7} {'回撤':>7} {'胜率':>7} {'交易':>5} {'时间':<16}",
        f"  {'-' * 100}",
    ]

    for bt in records:
        sym: str = bt.symbol or 'N/A'
        strat: str = bt.strategy or 'N/A'
        version: str = getattr(bt, 'strategy_version', None) or 'N/A'
        git: str = getattr(bt, 'git_hash', None) or 'N/A'
        created: str = str(bt.created_at or '')[:16]
        lines.append(
            f"  {bt.id:>4} "
            f"{sym:<14} "
            f"{strat:<6} "
            f"{version:<8} "
            f"{git:<8} "
            f"{format_pct(bt.total_return):>8} "
            f"{format_float(bt.sharpe_ratio):>7} "
            f"{format_pct(bt.max_drawdown):>7}  "
            f"{format_pct(bt.win_rate):>7} "
            f"{bt.total_trades or 0:>5} "
            f"{created:<16}"
        )

    lines.append(f"{'=' * 110}")
    lines.append(f"  使用 'python main.py report --id <ID>' 查看完整报告")
    return '\n'.join(lines)
