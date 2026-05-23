"""多数据集对比分析模块 - 分析策略在训练/验证/测试集上的表现差异与过拟合风险"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any
import numpy as np

logger = logging.getLogger(__name__)


def compare_datasets(
    train_report: Dict,
    val_report: Dict,
    test_report: Dict,
    symbol: str = "",
) -> Dict[str, Any]:
    """对比三个数据集的回测结果，分析过拟合风险

    分析维度:
      1. 收益递减分析: 训练 -> 验证 -> 测试 的收益率是否递减 (过拟合信号)
      2. 风险递增分析: 回撤是否在测试集上显著增大
      3. 夏普比率变化: 策略在不同数据上的风险调整后收益
      4. 胜率稳定性: 交易信号质量是否稳定
      5. 过拟合风险评估: 综合评分

    Args:
        train_report: 训练集回测报告
        val_report: 验证集回测报告
        test_report: 测试集回测报告

    Returns:
        对比分析结果字典
    """
    tp = train_report.get('performance', {})
    tr = train_report.get('risk', {})
    vp = val_report.get('performance', {})
    vr = val_report.get('risk', {})
    ep = test_report.get('performance', {})
    er = test_report.get('risk', {})

    comparison = {
        'meta': {
            'symbol': symbol,
            'train': _safe_name(train_report),
            'val': _safe_name(val_report),
            'test': _safe_name(test_report),
        },
        'metrics_table': _build_metrics_table(tp, tr, vp, vr, ep, er),
        'return_degradation': _analyze_return_degradation(tp, vp, ep),
        'risk_increase': _analyze_risk_increase(tr, vr, er),
        'stability_analysis': _analyze_stability(tp, tr, vp, vr, ep, er),
        'overfitting_assessment': _assess_overfitting(tp, tr, vp, vr, ep, er),
    }

    return comparison


def _safe_name(report: Dict) -> str:
    if not isinstance(report, dict):
        return 'unknown'
    m = report.get('meta')
    if not isinstance(m, dict):
        return 'unknown'
    return m.get('dataset') or m.get('name') or 'unknown'


def _build_metrics_table(
    tp, tr, vp, vr, ep, er
) -> Dict[str, Dict[str, Any]]:
    """构建三阶段指标对比表"""
    return {
        'total_return': {
            'train': _parse_pct(tp.get('total_return', '0%')),
            'val': _parse_pct(vp.get('total_return', '0%')),
            'test': _parse_pct(ep.get('total_return', '0%')),
        },
        'annual_return': {
            'train': _parse_pct(tp.get('annual_return', '0%')),
            'val': _parse_pct(vp.get('annual_return', '0%')),
            'test': _parse_pct(ep.get('annual_return', '0%')),
        },
        'sharpe_ratio': {
            'train': tp.get('sharpe_ratio', 0),
            'val': vp.get('sharpe_ratio', 0),
            'test': ep.get('sharpe_ratio', 0),
        },
        'max_drawdown': {
            'train': _parse_pct(tr.get('max_drawdown', '0%')),
            'val': _parse_pct(vr.get('max_drawdown', '0%')),
            'test': _parse_pct(er.get('max_drawdown', '0%')),
        },
        'win_rate': {
            'train': _parse_pct(tp.get('win_rate', '0%')),
            'val': _parse_pct(vp.get('win_rate', '0%')),
            'test': _parse_pct(ep.get('win_rate', '0%')),
        },
        'profit_loss_ratio': {
            'train': tp.get('profit_loss_ratio', 0),
            'val': vp.get('profit_loss_ratio', 0),
            'test': ep.get('profit_loss_ratio', 0),
        },
        'total_trades': {
            'train': tp.get('total_trades', 0),
            'val': vp.get('total_trades', 0),
            'test': ep.get('total_trades', 0),
        },
    }


def _parse_pct(value) -> float:
    """将百分比字符串或数值统一转为浮点数"""
    if isinstance(value, str):
        return float(value.rstrip('%')) / 100
    return float(value) if value else 0.0


def _analyze_return_degradation(tp, vp, ep) -> Dict:
    """收益递减分析

    如果 train > val > test 呈明显递减趋势，提示可能存在过拟合
    递减幅度越大，过拟合风险越高
    """
    train_ret = _parse_pct(tp.get('total_return', '0%')) * 100
    val_ret = _parse_pct(vp.get('total_return', '0%')) * 100
    test_ret = _parse_pct(ep.get('total_return', '0%')) * 100

    degradation = {
        'train_to_val': train_ret - val_ret,
        'val_to_test': val_ret - test_ret,
        'train_to_test': train_ret - test_ret,
    }

    # 判断收益方向
    if degradation['train_to_test'] > 20:
        degradation['risk_level'] = 'high'
        degradation['message'] = '收益从训练集到测试集大幅下降(>20%)，强烈提示过拟合'
    elif degradation['train_to_test'] > 10:
        degradation['risk_level'] = 'medium'
        degradation['message'] = '收益从训练集到测试集中等下降(10-20%)，可能存在过拟合'
    elif degradation['train_to_test'] > 0:
        degradation['risk_level'] = 'low'
        degradation['message'] = '收益略有下降，属于正常泛化表现'
    else:
        degradation['risk_level'] = 'none'
        degradation['message'] = '收益未出现下降趋势，策略泛化能力良好'

    return degradation


def _analyze_risk_increase(tr, vr, er) -> Dict:
    """风险递增分析

    如果测试集回撤显著大于训练集，说明策略在未知数据上风险控制能力下降
    """
    train_dd = _parse_pct(tr.get('max_drawdown', '0%')) * 100
    val_dd = _parse_pct(vr.get('max_drawdown', '0%')) * 100
    test_dd = _parse_pct(er.get('max_drawdown', '0%')) * 100

    dd_increase = {
        'train_to_val': val_dd - train_dd,
        'val_to_test': test_dd - val_dd,
        'train_to_test': test_dd - train_dd,
    }

    if dd_increase['train_to_test'] > 10:
        dd_increase['risk_level'] = 'high'
        dd_increase['message'] = '测试集回撤比训练集大超过10%，风险显著上升'
    elif dd_increase['train_to_test'] > 5:
        dd_increase['risk_level'] = 'medium'
        dd_increase['message'] = '测试集回撤略有增加，需关注风险控制'
    else:
        dd_increase['risk_level'] = 'low'
        dd_increase['message'] = '回撤水平稳定，风险控制一致性良好'

    return dd_increase


def _analyze_stability(tp, tr, vp, vr, ep, er) -> Dict:
    """稳定性分析 - 多维度评估策略在不同数据上的表现稳定性

    使用变异系数(CV)衡量各指标在三阶段上的波动程度
    """
    def _cv(*values):
        arr = np.array([v for v in values if v is not None], dtype=float)
        if len(arr) < 2 or arr.mean() == 0:
            return 0.0
        return float(np.std(arr) / abs(arr.mean()))

    metrics = {
        'return_cv': _cv(
            _parse_pct(tp.get('total_return', '0%')),
            _parse_pct(vp.get('total_return', '0%')),
            _parse_pct(ep.get('total_return', '0%')),
        ),
        'sharpe_cv': _cv(
            tp.get('sharpe_ratio', 0),
            vp.get('sharpe_ratio', 0),
            ep.get('sharpe_ratio', 0),
        ),
        'winrate_cv': _cv(
            _parse_pct(tp.get('win_rate', '0%')),
            _parse_pct(vp.get('win_rate', '0%')),
            _parse_pct(ep.get('win_rate', '0%')),
        ),
        'drawdown_cv': _cv(
            _parse_pct(tr.get('max_drawdown', '0%')),
            _parse_pct(vr.get('max_drawdown', '0%')),
            _parse_pct(er.get('max_drawdown', '0%')),
        ),
    }

    avg_cv = np.mean(list(metrics.values()))
    if avg_cv > 1.0:
        metrics['stability'] = 'low'
        metrics['message'] = '各指标波动较大，策略在不同数据集上表现不稳定'
    elif avg_cv > 0.5:
        metrics['stability'] = 'medium'
        metrics['message'] = '策略表现有一定波动，但处于可接受范围'
    else:
        metrics['stability'] = 'high'
        metrics['message'] = '策略在各数据集上表现一致，稳定性好'

    metrics['avg_cv'] = float(avg_cv)
    return metrics


def _assess_overfitting(tp, tr, vp, vr, ep, er) -> Dict:
    """综合过拟合风险评估

    评分体系 (0-100，越高风险越大):
      - 收益递减 >20%: +40分
      - 收益递减 10-20%: +20分
      - 回撤增加 >10%: +30分
      - 回撤增加 5-10%: +15分
      - 夏普下降 >50%: +20分
      - 胜率下降 >30%: +10分
    """
    score = 0

    train_ret = _parse_pct(tp.get('total_return', '0%'))
    test_ret = _parse_pct(ep.get('total_return', '0%'))
    ret_drop = (train_ret - test_ret) / max(abs(train_ret), 1e-9) if train_ret != 0 else 0

    train_dd = _parse_pct(tr.get('max_drawdown', '0%'))
    test_dd = _parse_pct(er.get('max_drawdown', '0%'))
    dd_rise = test_dd - train_dd

    train_sharpe = tp.get('sharpe_ratio', 0)
    test_sharpe = ep.get('sharpe_ratio', 0)
    sharpe_drop = (train_sharpe - test_sharpe) / max(abs(train_sharpe), 1e-9) if train_sharpe != 0 else 0

    train_wr = _parse_pct(tp.get('win_rate', '0%'))
    test_wr = _parse_pct(ep.get('win_rate', '0%'))
    wr_drop = (train_wr - test_wr) / max(abs(train_wr), 1e-9) if train_wr != 0 else 0

    # 评分规则
    if ret_drop > 0.5:
        score += 40
    elif ret_drop > 0.2:
        score += 20

    if dd_rise > 0.1:
        score += 30
    elif dd_rise > 0.05:
        score += 15

    if sharpe_drop > 0.5:
        score += 20

    if wr_drop > 0.3:
        score += 10

    if score >= 60:
        level = 'high'
        advice = '严重过拟合风险！建议简化策略、增加正则化或收集更多数据'
    elif score >= 30:
        level = 'medium'
        advice = '中等过拟合风险，建议调整参数、增加数据量或使用交叉验证'
    elif score >= 10:
        level = 'low'
        advice = '轻微过拟合迹象，可通过参数微调进一步优化'
    else:
        level = 'none'
        advice = '未检测到明显过拟合，策略泛化能力良好'

    return {
        'score': score,
        'level': level,
        'advice': advice,
        'details': {
            'return_degradation': f'{ret_drop:.1%}',
            'drawdown_increase': f'{dd_rise:.1%}',
            'sharpe_decline': f'{sharpe_drop:.1%}',
            'winrate_decline': f'{wr_drop:.1%}',
        },
    }


def format_comparison_report(comparison: Dict) -> str:
    """格式化对比分析报告为控制台文本

    Args:
        comparison: compare_datasets() 的返回结果

    Returns:
        格式化的对比报告字符串
    """
    m = comparison.get('metrics_table', {})
    rd = comparison.get('return_degradation', {})
    ri = comparison.get('risk_increase', {})
    sa = comparison.get('stability_analysis', {})
    oa = comparison.get('overfitting_assessment', {})

    header = ['指标', '训练集', '验证集', '测试集']

    def _row(name, fmt='{:.2f}', unit=''):
        vals = m.get(name, {})
        return f"  {name:<16} " + ' '.join(
            f"{fmt.format(vals.get(k, 0))}{unit:>6}" for k in ['train', 'val', 'test']
        )

    lines = [
        f"{'=' * 80}",
        f"  三数据集回测对比分析报告",
        f"{'=' * 80}",
        "",
        "【指标对比总览】",
        f"  {'指标':<16} {'训练集':>10} {'验证集':>10} {'测试集':>10}",
        f"  {'-' * 48}",
        f"  {'总收益率':<16} {m.get('total_return', {}).get('train', 0):>9.2%} "
        f"{m.get('total_return', {}).get('val', 0):>9.2%} "
        f"{m.get('total_return', {}).get('test', 0):>9.2%}",
        f"  {'年化收益':<16} {m.get('annual_return', {}).get('train', 0):>9.2%} "
        f"{m.get('annual_return', {}).get('val', 0):>9.2%} "
        f"{m.get('annual_return', {}).get('test', 0):>9.2%}",
        f"  {'夏普比率':<16} {m.get('sharpe_ratio', {}).get('train', 0):>10.2f} "
        f"{m.get('sharpe_ratio', {}).get('val', 0):>10.2f} "
        f"{m.get('sharpe_ratio', {}).get('test', 0):>10.2f}",
        f"  {'最大回撤':<16} {m.get('max_drawdown', {}).get('train', 0):>9.2%} "
        f"{m.get('max_drawdown', {}).get('val', 0):>9.2%} "
        f"{m.get('max_drawdown', {}).get('test', 0):>9.2%}",
        f"  {'胜率':<16} {m.get('win_rate', {}).get('train', 0):>9.2%} "
        f"{m.get('win_rate', {}).get('val', 0):>9.2%} "
        f"{m.get('win_rate', {}).get('test', 0):>9.2%}",
        f"  {'盈亏比':<16} {m.get('profit_loss_ratio', {}).get('train', 0):>10.2f} "
        f"{m.get('profit_loss_ratio', {}).get('val', 0):>10.2f} "
        f"{m.get('profit_loss_ratio', {}).get('test', 0):>10.2f}",
        f"  {'交易次数':<16} {m.get('total_trades', {}).get('train', 0):>10.0f} "
        f"{m.get('total_trades', {}).get('val', 0):>10.0f} "
        f"{m.get('total_trades', {}).get('test', 0):>10.0f}",
        "",
        "【收益递减分析】",
        f"  {rd.get('message', 'N/A')}",
        f"  训练→验证: {rd.get('train_to_val', 0):+.1f}%  |  "
        f"验证→测试: {rd.get('val_to_test', 0):+.1f}%  |  "
        f"训练→测试: {rd.get('train_to_test', 0):+.1f}%",
        "",
        "【风险递增分析】",
        f"  {ri.get('message', 'N/A')}",
        f"  训练→测试回撤变化: {ri.get('train_to_test', 0):+.1f}%",
        "",
        "【策略稳定性】",
        f"  {sa.get('message', 'N/A')}",
        f"  平均变异系数: {sa.get('avg_cv', 0):.3f}",
        "",
        "【过拟合综合评估】",
        f"  风险评分: {oa.get('score', 0)}/100  [{oa.get('level', 'N/A').upper()}]",
        f"  收益下降: {oa.get('details', {}).get('return_degradation', 'N/A')}",
        f"  回撤增加: {oa.get('details', {}).get('drawdown_increase', 'N/A')}",
        f"  夏普下降: {oa.get('details', {}).get('sharpe_decline', 'N/A')}",
        f"  胜率下降: {oa.get('details', {}).get('winrate_decline', 'N/A')}",
        f"  >>> {oa.get('advice', '')}",
        f"{'=' * 80}",
    ]
    return '\n'.join(lines)


def generate_merged_report(
    all_results: List[Dict],
    output_dir: str = ".quant_shared_data/reports",
) -> Dict[str, Any]:
    """生成多品种合并回测报告

    将所有品种的对比分析结果汇总，计算整体统计指标，
    支持跨品种横向比较与排名

    Args:
        all_results: 每个品种的 run_full_pipeline 返回结果列表
        output_dir: 报告输出目录

    Returns:
        合并报告字典，包含:
          - meta: 汇总元信息
          - symbols: 各品种关键指标
          - ranking: 各指标排名
          - aggregate: 整体聚合统计
          - overfitting_summary: 过拟合风险汇总
    """
    if not all_results:
        logger.warning("无回测结果，无法生成合并报告")
        return {'meta': {'symbol_count': 0}, 'symbols': [], 'aggregate': {},
                'ranking': {}, 'overfitting_summary': {}}

    symbols_data = []
    for r in all_results:
        if not r.get('success'):
            continue
        comp = r.get('comparison', {})
        mt = comp.get('metrics_table', {})
        oa = comp.get('overfitting_assessment', {})

        test_metrics = {}
        for key in ['total_return', 'sharpe_ratio', 'max_drawdown', 'win_rate',
                     'profit_loss_ratio', 'total_trades']:
            if key in mt:
                test_metrics[key] = mt[key].get('test', 0)

        symbols_data.append({
            'symbol': r.get('symbol', 'unknown'),
            'test_metrics': test_metrics,
            'overfitting_score': oa.get('score', 0),
            'overfitting_level': oa.get('level', 'unknown'),
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
        'overfitting_summary': _build_overfitting_summary(symbols_data),
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
        valid = [s for s in symbols_data if s['test_metrics'].get(key) is not None]
        sorted_items = sorted(valid, key=lambda s: s['test_metrics'].get(key, 0), reverse=reverse)
        return [{'symbol': s['symbol'], 'value': s['test_metrics'].get(key, 0)} for s in sorted_items]

    return {
        'total_return': _rank('total_return'),
        'sharpe_ratio': _rank('sharpe_ratio'),
        'max_drawdown': _rank('max_drawdown', reverse=False),
        'win_rate': _rank('win_rate'),
        'overfitting_risk': sorted(
            symbols_data,
            key=lambda s: s.get('overfitting_score', 0),
            reverse=False,
        ),
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
    of_scores = []

    for s in symbols_data:
        m = s['test_metrics']
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
        of_scores.append(s.get('overfitting_score', 0))

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
        'overfitting_score': _stats(of_scores),
        'profitable_ratio': _stats(returns).get('positive_count', 0) / len(returns) if returns else 0,
    }


def _build_overfitting_summary(symbols_data: List[Dict]) -> Dict:
    """过拟合风险汇总"""
    levels = {'high': 0, 'medium': 0, 'low': 0, 'none': 0}
    high_risk_symbols = []

    for s in symbols_data:
        level = s.get('overfitting_level', 'unknown')
        if level in levels:
            levels[level] += 1
        if level == 'high':
            high_risk_symbols.append(s['symbol'])

    return {
        'distribution': levels,
        'high_risk_symbols': high_risk_symbols,
        'total': sum(levels.values()),
        'high_risk_ratio': levels['high'] / max(sum(levels.values()), 1),
    }


def format_merged_report(merged: Dict) -> str:
    """格式化合并报告为控制台文本"""
    meta = merged.get('meta', {})
    agg = merged.get('aggregate', {})
    ranking = merged.get('ranking', {})
    ofs = merged.get('overfitting_summary', {})

    lines = [
        f"{'=' * 80}",
        f"  多品种合并回测报告",
        f"{'=' * 80}",
        f"  品种数量: {meta.get('symbol_count', 0)}",
        f"  品种列表: {', '.join(meta.get('symbols', []))}",
        f"  生成时间: {meta.get('generated_at', 'N/A')}",
        "",
        "【品种关键指标 (测试集)】",
        f"  {'品种':<18} {'收益率':>8} {'夏普':>7} {'回撤':>7} {'胜率':>7} {'交易':>6} {'过拟合':>6}",
        f"  {'-' * 65}",
    ]

    for s in merged.get('symbols', []):
        m = s['test_metrics']
        ret = f"{float(m.get('total_return', 0)):.2%}"
        sharpe = f"{float(m.get('sharpe_ratio', 0)):.2f}"
        dd = f"{float(m.get('max_drawdown', 0)):.2%}"
        wr = f"{float(m.get('win_rate', 0)):.2%}"
        trades = f"{int(m.get('total_trades', 0))}"
        of = s.get('overfitting_level', 'N/A')
        lines.append(f"  {s['symbol']:<18} {ret:>8} {sharpe:>7} {dd:>7} "
                      f"{wr:>7} {trades:>6} {of:>6}")

    lines += [
        "",
        "【整体聚合统计 (测试集)】",
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
        "【过拟合风险汇总】",
        f"  分布: " + ', '.join(f"{k}={v}" for k, v in ofs.get('distribution', {}).items()),
        f"  高风险品种: {ofs.get('high_risk_symbols', []) or '无'}",
        f"  高风险比例: {ofs.get('high_risk_ratio', 0):.0%}",
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