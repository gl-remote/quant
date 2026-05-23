"""多数据集对比分析模块 - 分析策略在训练/验证/测试集上的表现差异与过拟合风险"""

import logging
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