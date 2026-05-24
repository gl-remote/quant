"""多品种合并报告模块 — 横向比较多品种回测表现并排名"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any
import numpy as np

logger = logging.getLogger(__name__)


def generate_merged_report(
    all_results: List[Dict],
    output_dir: str = ".quant_shared_data/reports",
) -> Dict[str, Any]:
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

    symbols_data = []
    for r in all_results:
        if not r.get('success'):
            continue
        report = r.get('report', {})
        perf = report.get('performance', {})
        risk = report.get('risk', {})

        symbols_data.append({
            'symbol': r.get('symbol', 'unknown'),
            'metrics': {
                'total_return': perf.get('total_return_abs', 0),
                'annual_return': perf.get('annual_return_abs', 0),
                'sharpe_ratio': perf.get('sharpe_ratio', 0),
                'max_drawdown': risk.get('max_drawdown_abs', 0),
                'win_rate': perf.get('win_rate_abs', 0),
                'profit_loss_ratio': perf.get('profit_loss_ratio', 0),
                'total_trades': perf.get('total_trades', 0),
            },
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


def _build_ranking(symbols_data: List[Dict]) -> Dict[str, List[Dict]]:
    """构建各指标排名"""
    if not symbols_data:
        return {}

    def _rank(key, reverse=True):
        valid = [s for s in symbols_data if s['metrics'].get(key) is not None]
        sorted_items = sorted(valid, key=lambda s: s['metrics'].get(key, 0), reverse=reverse)
        return [{'symbol': s['symbol'], 'value': s['metrics'].get(key, 0)} for s in sorted_items]

    return {
        'total_return': _rank('total_return'),
        'sharpe_ratio': _rank('sharpe_ratio'),
        'max_drawdown': _rank('max_drawdown', reverse=False),
        'win_rate': _rank('win_rate'),
    }


def _build_aggregate(symbols_data: List[Dict]) -> Dict:
    """计算整体聚合统计"""
    if not symbols_data:
        return {}

    returns = []
    sharpes = []
    drawdowns = []
    win_rates = []
    trades_list = []

    for s in symbols_data:
        m = s['metrics']
        if m.get('total_return') is not None:
            returns.append(float(m['total_return']))
        if m.get('sharpe_ratio') is not None:
            sharpes.append(float(m['sharpe_ratio']))
        if m.get('max_drawdown') is not None:
            drawdowns.append(float(m['max_drawdown']))
        if m.get('win_rate') is not None:
            win_rates.append(float(m['win_rate']))
        if m.get('total_trades') is not None:
            trades_list.append(int(m['total_trades']))

    def _stats(values):
        if not values:
            return {}
        arr = np.array(values, dtype=float)
        return {
            'mean': float(np.mean(arr)),
            'median': float(np.median(arr)),
            'std': float(np.std(arr)),
            'min': float(np.min(arr)),
            'max': float(np.max(arr)),
            'positive_count': int(np.sum(arr > 0)) if any(v != 0 for v in arr) else 0,
            'negative_count': int(np.sum(arr < 0)),
        }

    return {
        'total_return': _stats(returns),
        'sharpe_ratio': _stats(sharpes),
        'max_drawdown': _stats(drawdowns),
        'win_rate': _stats(win_rates),
        'total_trades': {
            'total': int(sum(trades_list)),
            'avg': int(np.mean(trades_list)) if trades_list else 0,
            'count': len(trades_list),
        },
        'profitable_ratio': _stats(returns).get('positive_count', 0) / len(returns) if returns else 0,
    }


def format_merged_report(merged: Dict) -> str:
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
        m = s['metrics']
        ret = f"{float(m.get('total_return', 0)):.2%}"
        sharpe = f"{float(m.get('sharpe_ratio', 0)):.2f}"
        dd = f"{float(m.get('max_drawdown', 0)):.2%}"
        wr = f"{float(m.get('win_rate', 0)):.2%}"
        trades = f"{int(m.get('total_trades', 0))}"
        lines.append(f"  {s['symbol']:<18} {ret:>8} {sharpe:>7} {dd:>7} "
                      f"{wr:>7} {trades:>6}")

    lines += [
        "",
        "【整体聚合统计】",
    ]

    for metric_name, label in [('total_return', '总收益率'), ('sharpe_ratio', '夏普比率'),
                                ('max_drawdown', '最大回撤'), ('win_rate', '胜率')]:
        s = agg.get(metric_name, {})
        if s:
            lines.append(f"  {label}: 均值={s.get('mean', 0):.2%}  "
                          f"中位数={s.get('median', 0):.2%}  "
                          f"范围=[{s.get('min', 0):.2%}, {s.get('max', 0):.2%}]")

    lines += [
        f"  盈利品种比例: {agg.get('profitable_ratio', 0):.0%}",
        f"  总交易次数: {agg.get('total_trades', {}).get('total', 0)}",
        "",
        "【各指标排名 TOP 3】",
    ]

    for metric, label in [('total_return', '收益率'), ('sharpe_ratio', '夏普比率'),
                           ('max_drawdown', '回撤(低)'), ('win_rate', '胜率')]:
        items = ranking.get(metric, [])[:3]
        names = [f"{i['symbol']}({i['value']:.2%})" for i in items]
        lines.append(f"  {label}: {' > '.join(names) if names else 'N/A'}")

    lines += [
        f"{'=' * 80}",
    ]
    return '\n'.join(lines)
