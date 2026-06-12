"""
文字报告格式化模块

提供两种文本报告：
  - format_single_report: 单次回测完整详情
  - format_summary_report: 回测记录汇总表格
"""

from __future__ import annotations

from common.constants import (
    STATUS_FAILED,
    STATUS_SUCCESS,
    TRADE_DIRECTION_LONG,
    TRADE_DIRECTION_SHORT,
    TRADE_OFFSET_CLOSE,
    TRADE_OFFSET_OPEN,
)
from common.formatting import ensure_float, format_float, format_pct

# 导入数据管理和格式化工具
from data import DataManager

# ── 内部工具函数 ──────────────────────────────────────────────────


def _na_str(v: object | None) -> str:
    """
    将可能为 None 的值转为展示字符串

    Args:
        v: 可能为 None 的值

    Returns:
        转换后的字符串，None 返回 'N/A'
    """
    return "N/A" if v is None else str(v)


def _get_attr(obj: object, key: str, default: object = None) -> object:
    """
    获取对象属性值（兼容 dict 和 ORM model）

    Args:
        obj: 目标对象
        key: 属性名
        default: 默认值

    Returns:
        属性值或默认值
    """
    if hasattr(obj, key):
        return getattr(obj, key, default)
    return obj.get(key, default) if isinstance(obj, dict) else default


# ── 公开 API ──────────────────────────────────────────────────


def format_single_report(dm: DataManager, backtest_id: int) -> str:
    """
    生成单次回测的完整文本报告

    Args:
        dm: DataManager 实例，用于查询回测数据
        backtest_id: 回测记录 ID

    Returns:
        格式化的控制台报告字符串
    """
    # 获取回测记录
    bt = dm.get_backtest(backtest_id)

    # 检查回测记录是否存在
    if not bt:
        return f"错误: 未找到回测记录 id={backtest_id}"

    # 查询交易记录和每日数据
    trades = dm.query_trades(backtest_id)
    daily = dm.query_daily(backtest_id)

    # 统计交易天数（去重）
    trade_days: list[str] = sorted(set(str(_get_attr(t, "datetime"))[:10] for t in trades if _get_attr(t, "datetime")))
    # 统计开多和平空次数
    buy_count: int = sum(
        1
        for t in trades
        if _get_attr(t, "direction") == TRADE_DIRECTION_LONG and _get_attr(t, "offset") == TRADE_OFFSET_OPEN
    )
    sell_count: int = sum(
        1
        for t in trades
        if _get_attr(t, "direction") == TRADE_DIRECTION_SHORT and _get_attr(t, "offset") == TRADE_OFFSET_CLOSE
    )

    # 提取基本信息
    symbol = bt.symbol
    strategy = bt.strategy
    status = bt.status
    strategy_version = _get_attr(bt, "strategy_version")
    git_hash = _get_attr(bt, "git_hash")

    # 构建报告头部
    lines: list[str] = [
        f"{'=' * 70}",
        f"  回测报告 #{backtest_id}",
        f"{'=' * 70}",
        "",
        "【基本信息】",
        f"  品种:       {symbol}",
        f"  策略:       {strategy}",
        f"  策略版本:   {strategy_version or 'N/A'}",
        f"  Git哈希:    {git_hash or 'N/A'}",
        f"  状态:       {status}",
        f"  运行时间:   {_get_attr(bt, 'created_at')}",
    ]

    # 如果回测失败，显示错误信息
    if status == STATUS_FAILED:
        error_msg = _get_attr(bt, "error_message") or "N/A"
        lines.append(f"  错误信息:   {error_msg}")
        lines.append(f"{'=' * 70}")
        return "\n".join(lines)

    # 提取数据范围
    date_start = bt.start_date
    date_end = bt.end_date

    # 添加更多报告内容
    lines += [
        "",
        "【数据范围】",
        f"  数据区间:   {_na_str(date_start)} ~ {_na_str(date_end)}",
        f"  交易日数:   {len(daily)} 天",
        "",
        "【资金概况】",
        f"  初始资金:   {bt.initial_capital:,.2f}",
        f"  最终权益:   {_get_attr(bt, 'end_balance', 0):,.2f}",
        # total_return/annual_return 是 vnpy 输出的百分比（已乘100），直接显示
        f"  总收益率:   {bt.total_return:.2f}%",
        f"  年化收益:   {_get_attr(bt, 'annual_return') or 0:.2f}%",  # type: ignore[arg-type]
        "",
        "【盈亏汇总 [vnpy]】",  # 2026-06-06新增
        f"  总净盈亏:   {_get_attr(bt, 'total_net_pnl', 0) or 0:,.2f}",
        f"  日均净盈亏: {_get_attr(bt, 'daily_net_pnl', 0) or 0:,.2f}",
        f"  总手续费:   {_get_attr(bt, 'total_commission', 0) or 0:,.2f} ({format_pct((_get_attr(bt, 'total_commission') or 0) / (bt.initial_capital or 1))})",
        f"  日均手续费: {_get_attr(bt, 'daily_commission', 0) or 0:,.2f}",
        f"  总滑点成本: {_get_attr(bt, 'total_slippage', 0) or 0:,.2f}",
        f"  日均滑点:   {_get_attr(bt, 'daily_slippage', 0) or 0:,.2f}",
        f"  总成交金额: {_get_attr(bt, 'total_turnover', 0) or 0:,.2f}",
        "",
        "【交易统计】",
        f"  总交易次数: {bt.total_trades or 0}",
        # win_rate 是比值(0~1)，用 format_pct 正确
        f"  盈利交易:   {_get_attr(bt, 'win_trades', 0) or 0} ({format_pct(bt.win_rate)})",
        f"  亏损交易:   {_get_attr(bt, 'loss_trades', 0) or 0}",
        f"  平均盈利:   {format_float(bt.avg_win, ',.0f')}",
        f"  平均亏损:   {format_float(bt.avg_loss, ',.0f')}",
        "",
        "【交易日统计 [vnpy]】",  # 2026-06-06新增
        f"  盈利天数:   {_get_attr(bt, 'profit_days', 0) or 0} 天",
        f"  亏损天数:   {_get_attr(bt, 'loss_days', 0) or 0} 天",
        f"  日均成交笔数: {_get_attr(bt, 'daily_trade_count', 0) or 0:.1f}",
        # daily_return_pct 是百分比数值（如 0.5 表示 0.5%），追加 % 符号显示
        f"  日均收益率: {_get_attr(bt, 'daily_return_pct') or 0:.2f}%",  # type: ignore[arg-type]
        "",
        "【风险评估】",
        f"  夏普比率:   {format_float(bt.sharpe_ratio)}",
        # max_drawdown 是绝对金额(元)，max_ddpercent 是百分比
        f"  最大回撤:   {bt.max_drawdown:,.2f}元 ({_get_attr(bt, 'max_ddpercent', 0) or 0:.2f}%)",
        f"  EWM夏普:    {format_float(_get_attr(bt, 'ewm_sharpe'))}",  # type: ignore[arg-type]
        f"  RGR比率:    {format_float(_get_attr(bt, 'rgr_ratio'))}",  # type: ignore[arg-type]
        f"  收益回撤比: {format_float(_get_attr(bt, 'return_drawdown_ratio'))}",  # type: ignore[arg-type]
        f"  日均波动率: {format_float(_get_attr(bt, 'daily_std'))}",  # type: ignore[arg-type]
        "",
        "【交易明细】",
        f"  成交笔数:   {len(trades)} (开仓{buy_count} / 平仓{sell_count})",
        f"  交易日期:   {len(trade_days)} 天",
    ]

    # 如果有每日数据，显示最近10天的资金曲线
    if daily:
        lines += [
            "",
            "【资金曲线（最近10天）】",
            f"  {'日期':<12} {'权益':>12} {'日收益':>10} {'回撤':>8}",
            f"  {'-' * 50}",
        ]
        for d in daily[-10:]:
            equity = d.get("equity", 0)
            daily_return = d.get("daily_return", 0)
            drawdown = d.get("drawdown", 0)
            lines.append(f"  {d.get('date', ''):<12} {equity:>12,.2f} {daily_return:>+10,.2f} {drawdown:>8.2%}")

    # 如果有交易记录，显示最近20笔交易
    if trades:
        lines += [
            "",
            f"  {'时间':<20} {'标的':<16} {'方向':>5} {'开平':>4} {'价格':>9} {'手数':>4}",
            f"  {'-' * 63}",
        ]
        for t in trades[-20:]:
            d_tag: str = "多" if _get_attr(t, "direction") == TRADE_DIRECTION_LONG else "空"
            o_tag: str = "开" if _get_attr(t, "offset") == TRADE_OFFSET_OPEN else "平"
            price = _get_attr(t, "close_price") or _get_attr(t, "open_price", 0)
            qty = _get_attr(t, "quantity", 0)
            lines.append(
                f"  {_get_attr(t, 'datetime'):<20} "
                f"{_get_attr(t, 'symbol'):<16} "
                f"{d_tag:>5} {o_tag:>4} "
                f"{ensure_float(price):>9.2f} "  # type: ignore[arg-type]
                f"{qty:>4}"
            )

    # 添加报告结尾
    lines.append(f"{'=' * 70}")
    return "\n".join(lines)


def format_summary_report(
    dm: DataManager,
    symbol: str | None = None,
    strategy: str | None = None,
    limit: int = 20,
) -> str:
    """
    生成最近回测的汇总列表

    Args:
        dm: DataManager 实例
        symbol: 品种过滤（可选）
        strategy: 策略过滤（可选）
        limit: 最大显示条数

    Returns:
        格式化的汇总表格字符串
    """
    # 查询符合条件的回测记录
    records = dm.query_backtests(
        symbol=symbol,
        strategy=strategy,
        status=STATUS_SUCCESS,
        limit=limit,
    )

    # 检查是否有记录
    if not records:
        filters: list[str] = []
        if symbol:
            filters.append(f"品种={symbol}")
        if strategy:
            filters.append(f"策略={strategy}")
        fstr: str = ", ".join(filters) if filters else "全部"
        return f"未找到符合条件的回测记录 ({fstr})"

    # 构建汇总表格头部
    lines: list[str] = [
        f"{'=' * 110}",
        f"  回测汇总 ({len(records)} 条)",
        f"{'=' * 110}",
        f"  {'#':>4} {'品种':<14} {'策略':<6} {'版本':<8} {'Git':<8} "
        f"{'收益率%':>9} {'夏普':>7} {'回撤(元)':>10} {'胜率':>7} {'交易':>5} {'时间':<16}",
        f"  {'-' * 100}",
    ]

    # 遍历回测记录添加到表格
    for bt in records:
        sym: str = bt.symbol or "N/A"
        strat: str = bt.strategy or "N/A"
        version: str = getattr(bt, "strategy_version", None) or "N/A"
        git: str = getattr(bt, "git_hash", None) or "N/A"
        created: str = str(bt.created_at or "")[:16]
        lines.append(
            f"  {bt.id:>4} "
            f"{sym:<14} "
            f"{strat:<6} "
            f"{version:<8} "
            f"{git:<8} "
            # total_return 是 vnpy 百分比，直接显示
            f"{bt.total_return:>7.2f}% "
            f"{format_float(bt.sharpe_ratio):>7} "
            # max_drawdown 是绝对金额(元)
            f"{bt.max_drawdown:>10,.0f} "
            # win_rate 是比值(0~1)，用 format_pct 正确
            f"{format_pct(bt.win_rate):>7} "
            f"{bt.total_trades or 0:>5} "
            f"{created:<16}"
        )

    # 添加表格结尾和提示
    lines.append(f"{'=' * 110}")
    lines.append("  使用 'python main.py report --id <ID>' 查看完整报告")
    return "\n".join(lines)
