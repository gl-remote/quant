"""
绩效指标计算工具 (纯函数)

接受权益曲线或收益率序列，返回标量指标。
供 VnpyBacktestEngine、report 等模块共用。
"""

from __future__ import annotations

import numpy as np


def calc_max_drawdown(equity_curve: list[float]) -> float:
    """从权益曲线计算最大回撤

    Args:
        equity_curve: 权益曲线序列

    Returns:
        最大回撤率 (0.0 ~ 1.0)
    """
    if len(equity_curve) < 2:
        return 0.0
    peak: float = equity_curve[0]
    max_dd: float = 0.0
    for equity in equity_curve[1:]:
        if equity > peak:
            peak = equity
        dd: float = (peak - equity) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return max_dd


def calc_sharpe_ratio(equity_curve: list[float], annual_factor: int = 252) -> float:
    """从权益曲线计算年化夏普比率

    Args:
        equity_curve: 权益曲线序列
        annual_factor: 年化因子 (日线=252, 分钟线需换算)

    Returns:
        年化夏普比率，除零或无效数据返回 0
    """
    if len(equity_curve) < 2:
        return 0.0
    arr = np.array(equity_curve, dtype=float)
    prev = arr[:-1]
    # 避免除零：权益为零的位置跳过
    mask = prev != 0
    if not np.any(mask):
        return 0.0
    diff = np.diff(arr)
    returns = np.divide(diff[mask], prev[mask], out=np.full_like(diff[mask], 0.0), where=prev[mask] != 0)
    returns = returns[~np.isnan(returns) & ~np.isinf(returns)]
    if len(returns) == 0:
        return 0.0
    std: float = float(np.std(returns, ddof=1))
    if std == 0:
        return 0.0
    return float(np.mean(returns) / std * np.sqrt(annual_factor))
