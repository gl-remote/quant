"""多品种合并报告模块 — 横向比较多品种回测表现并排名"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np

from common.stats import SymbolSummary, compute_summary_stats, rank_by_key

logger = logging.getLogger(__name__)


def generate_merged_report(
    all_results: list[dict],
    output_dir: str = ".quant_shared_data/reports",
) -> dict:
    """生成多品种合并回测报告

    将所有品种的回测结果汇总，计算整体统计指标，
    支持跨品种横向比较与排名。

    Args:
        all_results: 每个品种的 run_full_pipeline 返回结果列表，
                     每个元素包含 {success, symbol, report: {performance, risk, trades}}
        output_dir: 报告输出目录

    Returns:
        合并报告字典，包含:
          - meta: 汇总元信息
          - symbols: 各品种关键指标
          - ranking: 各指标排名
          - aggregate: 整体聚合统计
    """
    if not all_results:
        logger.warning("无回测结果，无法生成合并报告")
        return {'meta': {'symbol_count': 0}, 'symbols': [], 'aggregate': {},
                'ranking': {}}

    symbols_data: list[SymbolSummary] = []
    for r in all_results:
        if not r.get('success'):
            continue
        report = r.get('report', {})
        perf = report.get('performance', {})
        risk = report.get('risk', {})

        symbols_data.append({
            'symbol': r.get('symbol', 'unknown'),
            'total_return': float(perf.get('total_return_abs', 0)),
            'annual_return': float(perf.get('annual_return_ratio', 0)),
            'sharpe_ratio': float(perf.get('sharpe_ratio', 0)),
            'max_drawdown': float(risk.get('max_drawdown_abs', 0)),
            'win_rate': float(perf.get('win_rate_abs', 0)),
            'profit_loss_ratio': float(perf.get('profit_loss_ratio', 0)),
            'total_trades': int(perf.get('total_trades', 0)),
        })

    ranking = _build_ranking(symbols_data)
    aggregate = _build_aggregate(symbols_data)

    merged = {
        'meta': {
            'symbol_count': len(symbols_data),
            'symbols': [s['symbol'] for s in symbols_data],
            'generated_at': str(np.datetime64('now')),
        },
        'symbols': symbols_data,
        'ranking': ranking,
        'aggregate': aggregate,
    }

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    merged_path = out_dir / "merged_report.json"
    with open(merged_path, 'w', encoding='utf-8') as f:
        json.dump(merged, f, ensure_ascii=False, indent=2, default=str)
    logger.info(f"合并报告已保存: {merged_path}")

    console_report = format_merged_report(merged)
    print(console_report)

    return merged


def _build_ranking(symbols_data: list[SymbolSummary]) -> dict[str, list[dict]]:
    """构建各指标排名"""
    if not symbols_data:
        return {}
    return {
        'total_return': rank_by_key(symbols_data, 'total_return'),  # type: ignore[arg-type]
        'sharpe_ratio': rank_by_key(symbols_data, 'sharpe_ratio'),  # type: ignore[arg-type]
        'max_drawdown': rank_by_key(symbols_data, 'max_drawdown', reverse=False),  # type: ignore[arg-type]
        'win_rate': rank_by_key(symbols_data, 'win_rate'),  # type: ignore[arg-type]
    }


def _build_aggregate(symbols_data: list[SymbolSummary]) -> dict:
    """计算整体聚合统计"""
    if not symbols_data:
        return {}

    returns: list[float] = []
    sharpes: list[float] = []
    drawdowns: list[float] = []
    win_rates: list[float] = []
    trades_list: list[int] = []

    for s in symbols_data:
        if s.get('total_return') is not None:
            returns.append(float(s['total_return']))
        if s.get('sharpe_ratio') is not None:
            sharpes.append(float(s['sharpe_ratio']))
        if s.get('max_drawdown') is not None:
            drawdowns.append(float(s['max_drawdown']))
        if s.get('win_rate') is not None:
            win_rates.append(float(s['win_rate']))
        if s.get('total_trades') is not None:
            trades_list.append(int(s['total_trades']))

    return_stats = compute_summary_stats(returns)
    return {
        'total_return': compute_summary_stats(returns),
        'sharpe_ratio': compute_summary_stats(sharpes),
        'max_drawdown': compute_summary_stats(drawdowns),
        'win_rate': compute_summary_stats(win_rates),
        'total_trades': {
            'total': int(sum(trades_list)),
            'avg': int(np.mean(trades_list)) if trades_list else 0,
            'count': len(trades_list),
        },
        'profitable_ratio': return_stats.get('positive_count', 0) / len(returns) if returns else 0,
    }


def format_merged_report(merged: dict) -> str:
    """格式化合并报告为控制台文本"""
    meta = merged.get('meta', {})
    agg = merged.get('aggregate', {})
    ranking = merged.get('ranking', {})

    lines = [
        f"{'=' * 80}",
        f"  多品种合并回测报告",
        f"{'=' * 80}",
        f"  品种数量: {meta.get('symbol_count', 0)}",
        f"  品种列表: {', '.join(meta.get('symbols', []))}",
        f"  生成时间: {meta.get('generated_at', 'N/A')}",
        "",
        "【品种关键指标】",
        f"  {'品种':<18} {'收益率':>8} {'夏普':>7} {'回撤':>7} {'胜率':>7} {'交易':>6}",
        f"  {'-' * 59}",
    ]

    for s in merged.get('symbols', []):
        ret = f"{float(s.get('total_return', 0)):.2%}"
        sharpe = f"{float(s.get('sharpe_ratio', 0)):.2f}"
        dd_val = float(s.get('max_drawdown', 0))
        # 归一化: >1 视为百分比值 (如 15.0=15%), 转换为比值
        if abs(dd_val) > 1:
            dd_val = dd_val / 100.0
        dd = f"{dd_val:.2%}"
        wr = f"{float(s.get('win_rate', 0)):.2%}"
        trades = f"{int(s.get('total_trades', 0))}"
        lines.append(f"  {s['symbol']:<18} {ret:>8} {sharpe:>7} {dd:>7} "
                      f"{wr:>7} {trades:>6}")

    lines += [
        "",
        "【整体聚合统计】",
    ]

    for metric_name, label, fmt in [('total_return', '总收益率', '.2%'),
                                     ('sharpe_ratio', '夏普比率', '.2f'),
                                     ('max_drawdown', '最大回撤', '.2%'),
                                     ('win_rate', '胜率', '.2%')]:
        s = agg.get(metric_name, {})
        if s:
            lines.append(f"  {label}: 均值={s.get('mean', 0):{fmt}}  "
                          f"中位数={s.get('median', 0):{fmt}}  "
                          f"范围=[{s.get('min', 0):{fmt}}, {s.get('max', 0):{fmt}}]")

    lines += [
        f"  盈利品种比例: {agg.get('profitable_ratio', 0):.0%}",
        f"  总交易次数: {agg.get('total_trades', {}).get('total', 0)}",
        "",
        "【各指标排名 TOP 3】",
    ]

    for metric, label in [('total_return', '收益率'), ('sharpe_ratio', '夏普比率'),
                           ('max_drawdown', '回撤(低)'), ('win_rate', '胜率')]:
        items = ranking.get(metric, [])[:3]
        names = [f"{i['symbol']}({i[metric]:.2%})" for i in items]
        lines.append(f"  {label}: {' > '.join(names) if names else 'N/A'}")

    lines += [
        f"{'=' * 80}",
    ]
    return '\n'.join(lines)
