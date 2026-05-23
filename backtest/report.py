"""报告生成模块 - 为回测结果生成详细的交易报告"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)


def generate_dataset_report(
    statistics: Dict[str, Any],
    daily_results: Optional[List[Dict]] = None,
    dataset_name: str = "unknown",
    symbol: str = "",
    initial_capital: float = 100000.0,
    output_dir: str = ".quant_shared_data/reports",
    save_trades: bool = True,
    save_equity: bool = True,
) -> Dict[str, Any]:
    """为单个数据集的回测结果生成详细报告

    Args:
        statistics: vn.py 回测统计结果字典 (engine.calculate_statistics())
        daily_results: 每日回测结果列表
        dataset_name: 数据集名称 (train/val/test)
        symbol: 合约代码
        initial_capital: 初始资金
        output_dir: 报告输出目录
        save_trades: 是否保存交易记录
        save_equity: 是否保存资金曲线数据

    Returns:
        报告字典
    """
    report = {
        'meta': {
            'dataset': dataset_name,
            'symbol': symbol,
            'generated_at': datetime.now().isoformat(),
            'initial_capital': initial_capital,
        },
        'performance': _extract_performance_metrics(statistics, initial_capital),
        'risk': _extract_risk_metrics(statistics),
        'trades': _extract_trade_summary(statistics),
    }

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 保存JSON报告
    report_file = output_path / f"{symbol}_{dataset_name}_report.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    logger.info(f"报告已保存: {report_file}")

    # 保存交易记录
    if save_trades and daily_results:
        trades_file = output_path / f"{symbol}_{dataset_name}_trades.json"
        _save_trade_records(daily_results, trades_file)

    # 保存资金曲线
    if save_equity and daily_results:
        equity_file = output_path / f"{symbol}_{dataset_name}_equity.json"
        _save_equity_curve(daily_results, equity_file, initial_capital)

    return report


def _extract_performance_metrics(statistics: Dict, initial_capital: float) -> Dict:
    if not isinstance(statistics, dict) or not statistics:
        logger.warning("回测统计数据为空，返回默认绩效指标")
        return {
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
            'sharpe_ratio': 0,
            'annual_return': '0.00%',
            'annual_return_abs': 0,
        }
    final_balance = statistics.get('end_balance', initial_capital)
    total_return = (final_balance - initial_capital) / initial_capital if initial_capital > 0 else 0

    return {
        'initial_capital': initial_capital,
        'final_equity': final_balance,
        'total_return': f"{total_return:.2%}",
        'total_return_abs': final_balance - initial_capital,
        'total_trades': statistics.get('total_trades', 0),
        'winning_trades': statistics.get('win_trades', 0),
        'losing_trades': statistics.get('loss_trades', 0),
        'win_rate': f"{statistics.get('win_trades', 0) / max(statistics.get('total_trades', 1), 1):.2%}",
        'win_rate_abs': statistics.get('win_trades', 0) / max(statistics.get('total_trades', 1), 1),
        'avg_profit': statistics.get('average_win', 0),
        'avg_loss': statistics.get('average_loss', 0),
        'profit_loss_ratio': statistics.get('win_loss_ratio', 0),
        'sharpe_ratio': statistics.get('sharpe_ratio', 0),
        'annual_return': f"{statistics.get('annual_return', 0):.2%}",
        'annual_return_abs': statistics.get('annual_return', 0),
    }


def _extract_risk_metrics(statistics: Dict) -> Dict:
    """提取风险指标"""
    return {
        'max_drawdown': f"{statistics.get('max_drawdown', 0):.2%}",
        'max_drawdown_abs': statistics.get('max_drawdown', 0),
        'max_drawdown_duration': statistics.get('max_ddpercent_duration', 0),
        'daily_std': statistics.get('daily_std', 0),
        'return_drawdown_ratio': statistics.get('return_drawdown_ratio', 0),
    }


def _extract_trade_summary(statistics: Dict) -> Dict:
    """提取交易统计摘要"""
    return {
        'total_trades': statistics.get('total_trades', 0),
        'start_date': str(statistics.get('start_date', '')),
        'end_date': str(statistics.get('end_date', '')),
        'total_days': statistics.get('total_days', 0),
        'avg_trades_per_day': (
            statistics.get('total_trades', 0) / max(statistics.get('total_days', 1), 1)
        ),
        'max_consecutive_win': statistics.get('max_consecutive_win', 0),
        'max_consecutive_loss': statistics.get('max_consecutive_loss', 0),
    }


def _save_trade_records(daily_results: List[Dict], filepath: Path):
    """保存详细交易记录"""
    trades = []
    for day in daily_results:
        if 'trades' in day:
            trades.extend(day.get('trades', []))
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(trades, f, ensure_ascii=False, indent=2, default=str)
    logger.info(f"交易记录已保存: {filepath}")


def _save_equity_curve(daily_results: List[Dict], filepath: Path,
                       initial_capital: float):
    """保存资金曲线数据"""
    curve = []
    equity = initial_capital
    for day in daily_results:
        day_return = day.get('net_pnl', 0) if isinstance(day, dict) else 0
        equity += day_return
        curve.append({
            'date': str(day.get('datetime', '')),
            'equity': equity,
            'daily_return': day_return,
            'drawdown': day.get('drawdown', 0) if isinstance(day, dict) else 0,
        })
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(curve, f, ensure_ascii=False, indent=2)
    logger.info(f"资金曲线已保存: {filepath}")


def format_console_report(
    report: Dict,
    dataset_name: str,
) -> str:
    """格式化控制台报告文本

    Args:
        report: 报告字典
        dataset_name: 数据集显示名称

    Returns:
        格式化的报告字符串
    """
    p = report.get('performance', {})
    r = report.get('risk', {})
    t = report.get('trades', {})

    lines = [
        f"{'=' * 60}",
        f"  {dataset_name} 数据集回测报告",
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