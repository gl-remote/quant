"""数据集报告生成模块 — 构建结构化报告字典，供控制台格式化输出"""

import logging
from datetime import datetime
from typing import Any, Optional

from common.constants import DEFAULT_INITIAL_CAPITAL
from common.formulas import total_return as calc_total_return, win_rate as calc_win_rate, avg_trades_per_day

logger = logging.getLogger(__name__)


def generate_dataset_report(
    statistics: dict[str, Any],
    daily_results: list[dict] | None = None,
    dataset_name: str = "unknown",
    symbol: str = "",
    backtest_id: Optional[int] = None,
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
) -> dict[str, Any]:
    """为单个回测结果生成结构化报告字典

    Args:
        statistics: vn.py 回测统计结果字典 (engine.calculate_statistics())
        daily_results: 每日回测结果列表 (可选，保留兼容)
        dataset_name: 数据集名称
        symbol: 合约代码
        backtest_id: 回测 ID (对应数据库记录)
        initial_capital: 初始资金

    Returns:
        报告字典，供 format_console_report() 格式化控制台输出

    Note:
        交易明细和资金曲线数据已通过 CLI 存入 SQLite 数据库，
        可通过 sql_reporter.py 查询，不再额外导出一份 JSON 文件。
    """
    return {
        'meta': {
            'backtest_id': backtest_id,
            'dataset': dataset_name,
            'symbol': symbol,
            'generated_at': datetime.now().isoformat(),
            'initial_capital': initial_capital,
        },
        'performance': _extract_performance_metrics(statistics, initial_capital),
        'risk': _extract_risk_metrics(statistics),
        'trades': _extract_trade_summary(statistics),
    }


def _extract_performance_metrics(statistics: dict, initial_capital: float) -> dict:
    """提取绩效指标。当 statistics 为空或无交易时返回安全默认值，避免 vnpy 的垃圾数据污染报告。"""
    _ZERO_RETURN = {
        'initial_capital': initial_capital,
        'final_equity': initial_capital,
        'total_return': '0.00%',
        'total_return_abs': 0.0,
        'total_trades': 0,
        'winning_trades': 0,
        'losing_trades': 0,
        'win_rate': '0.00%',
        'win_rate_abs': 0.0,
        'avg_profit': 0,
        'avg_loss': 0,
        'profit_loss_ratio': 0,
        'sharpe_ratio': 0.0,
        'annual_return': '0.00%',
        'annual_return_ratio': 0.0,
    }

    if not isinstance(statistics, dict) or not statistics:
        logger.warning("回测统计数据为空，返回默认绩效指标")
        return _ZERO_RETURN

    total_trades = statistics.get('total_trades', 0)
    if total_trades == 0:
        logger.warning("总交易次数为 0，vnpy 统计值不可信，使用安全默认值")
        return _ZERO_RETURN

    final_balance = statistics.get('end_balance', initial_capital)
    total_return = calc_total_return(initial_capital, final_balance,
                                     total_trades=total_trades)

    return {
        'initial_capital': initial_capital,
        'final_equity': final_balance,
        'total_return': f"{total_return:.2%}",
        'total_return_abs': final_balance - initial_capital,
        'total_trades': total_trades,
        'winning_trades': statistics.get('win_trades', 0),
        'losing_trades': statistics.get('loss_trades', 0),
        'win_rate': f"{calc_win_rate(statistics.get('win_trades', 0), total_trades):.2%}",
        'win_rate_abs': calc_win_rate(statistics.get('win_trades', 0), total_trades),
        'avg_profit': statistics.get('average_win', 0),
        'avg_loss': statistics.get('average_loss', 0),
        'profit_loss_ratio': statistics.get('win_loss_ratio', 0),
        'sharpe_ratio': statistics.get('sharpe_ratio', 0),
        'annual_return': f"{statistics.get('annual_return', 0):.2%}",
        'annual_return_ratio': statistics.get('annual_return', 0),
    }


def _extract_risk_metrics(statistics: dict) -> dict:
    """提取风险指标。0 交易时 vnpy 回撤/波动率等不可信，返回安全默认值。"""
    total_trades = statistics.get('total_trades', 0) if isinstance(statistics, dict) else 0
    if total_trades == 0:
        return {
            'max_drawdown': '0.00%',
            'max_drawdown_abs': 0.0,
            'max_drawdown_duration': 0,
            'daily_std': 0.0,
            'return_drawdown_ratio': 0.0,
        }
    return {
        'max_drawdown': f"{statistics.get('max_drawdown', 0):.2%}",
        'max_drawdown_abs': statistics.get('max_drawdown', 0),
        'max_drawdown_duration': statistics.get('max_ddpercent_duration', 0),
        'daily_std': statistics.get('daily_std', 0),
        'return_drawdown_ratio': statistics.get('return_drawdown_ratio', 0),
    }


def _extract_trade_summary(statistics: dict) -> dict:
    """提取交易统计摘要"""
    return {
        'total_trades': statistics.get('total_trades', 0),
        'start_date': str(statistics.get('start_date', '')),
        'end_date': str(statistics.get('end_date', '')),
        'total_days': statistics.get('total_days', 0),
        'avg_trades_per_day': avg_trades_per_day(
            statistics.get('total_trades', 0),
            statistics.get('total_days', 1),
        ),
        'max_consecutive_win': statistics.get('max_consecutive_win', 0),
        'max_consecutive_loss': statistics.get('max_consecutive_loss', 0),
    }


def format_console_report(
    report: dict,
    title: str,
) -> str:
    """格式化控制台报告文本

    Args:
        report: 报告字典
        title: 报告标题

    Returns:
        格式化的报告字符串
    """
    p = report.get('performance', {})
    r = report.get('risk', {})
    t = report.get('trades', {})

    lines = [
        f"{'=' * 60}",
        f"  {title} 回测报告",
        f"{'=' * 60}",
        "",
        "【资金概况】",
        f"  初始资金:   {p.get('initial_capital', 0):>15,.2f}",
        f"  最终权益:   {p.get('final_equity', 0):>15,.2f}",
        f"  总收益率:   {p.get('total_return', 'N/A'):>15}",
        f"  年化收益:   {p.get('annual_return', 'N/A'):>15}",
        "",
        "【交易统计】",
        f"  总交易次数: {p.get('total_trades', 0):>10}",
        f"  盈利交易:   {p.get('winning_trades', 0):>10}  ({p.get('win_rate', 'N/A')})",
        f"  亏损交易:   {p.get('losing_trades', 0):>10}",
        f"  平均盈利:   {p.get('avg_profit', 0):>15,.2f}",
        f"  平均亏损:   {p.get('avg_loss', 0):>15,.2f}",
        f"  盈亏比:     {p.get('profit_loss_ratio', 0):>15.2f}",
        "",
        "【风险评估】",
        f"  最大回撤:   {r.get('max_drawdown', 'N/A'):>15}",
        f"  夏普比率:   {p.get('sharpe_ratio', 0):>15.2f}",
        f"  日波动率:   {r.get('daily_std', 0):>15.4f}",
        f"  收益回撤比: {r.get('return_drawdown_ratio', 0):>15.2f}",
        "",
        f"  时间范围:   {t.get('start_date', 'N/A')} ~ {t.get('end_date', 'N/A')}",
        f"  交易天数:   {t.get('total_days', 0)}",
        f"{'=' * 60}",
    ]
    return '\n'.join(lines)
