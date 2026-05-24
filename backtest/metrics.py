# -*- coding: utf-8 -*-
"""
绩效指标计算工具

纯函数，接受权益曲线或收益率序列，返回标量指标。
TQBacktestEngine 和 VnpyBacktestEngine 均可用。
"""

from typing import List
import numpy as np


def calc_max_drawdown(equity_curve: List[float]) -> float:
    """从权益曲线计算最大回撤

    Args:
        equity_curve: 权益曲线序列

    Returns:
        最大回撤率 (0.0 ~ 1.0)
    """
    if len(equity_curve) < 2:
        return 0.0
    peak = equity_curve[0]
    max_dd = 0.0
    for equity in equity_curve[1:]:
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak if peak != 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return max_dd


def calc_sharpe_ratio(equity_curve: List[float], annual_factor: int = 252) -> float:
    """从权益曲线计算年化夏普比率

    Args:
        equity_curve: 权益曲线序列
        annual_factor: 年化因子 (日线=252, 分钟线需换算)

    Returns:
        年化夏普比率
    """
    if len(equity_curve) < 2:
        return 0.0
    returns = np.diff(equity_curve) / np.array(equity_curve[:-1])
    if len(returns) == 0:
        return 0.0
    std = np.std(returns)
    return 0.0 if std == 0 else (np.mean(returns) / std) * np.sqrt(annual_factor)
