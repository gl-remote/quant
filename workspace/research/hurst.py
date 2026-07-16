"""
Hurst 指数 R/S 分析

文件级元信息：
- 创建背景：shaping-theory §2.12.4 / KF-16 沉淀——20 合约 × 3 周期实测发现
  1h 上 19/20 合约 H > 0.55（趋势凝聚），Hurst 是通道 B 的**候选强度识别因子**之一。
- 用途：给定时间序列，输出 Hurst 指数估计。H > 0.5 趋势凝聚，H < 0.5 均值回归。
- 注意事项：R/S 方法在短序列上有偏差，建议 n ≥ 100；
  本实现按经典 Mandelbrot & Wallis 的 rescaled range，未做 correction。
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def hurst_rs(series: Sequence[float], min_window: int = 8, max_window: int | None = None) -> float:
    """Hurst 指数（R/S 分析）。

    方法：
        1. 对每个窗口大小 n（从 min_window 到 max_window，按 2 的幂）：
           a. 计算 rescaled range R/S（每窗口的极差 / 标准差）
           b. 对该 n 下所有子序列取平均
        2. log(R/S) vs log(n) 线性回归，斜率即 Hurst 指数 H

    Args:
        series: 时间序列（如对数收益、价格）
        min_window: 最小窗口，默认 8
        max_window: 最大窗口，默认 len(series) // 4

    Returns:
        Hurst 指数估计
            H = 0.5  纯随机漫步
            H > 0.5  趋势凝聚（超随机漫步的持续性）
            H < 0.5  均值回归

    Raises:
        ValueError: 序列长度不足
    """
    n = len(series)
    if max_window is None:
        max_window = n // 4
    if max_window < min_window * 2:
        raise ValueError(
            f"Series too short for Hurst estimation: len={n}, need max_window ({max_window}) >= "
            f"min_window ({min_window}) × 2"
        )

    # 生成窗口序列（等比 2 倍增）
    windows: list[int] = []
    w = min_window
    while w <= max_window:
        windows.append(w)
        w *= 2

    if len(windows) < 2:
        raise ValueError(f"Need at least 2 window sizes, got {len(windows)}")

    x_vals: list[float] = []
    y_vals: list[float] = []

    for win_size in windows:
        rs_vals: list[float] = []
        for start in range(0, n - win_size + 1, win_size):
            sub = list(series[start : start + win_size])
            mean_sub = sum(sub) / win_size
            deviations = [s - mean_sub for s in sub]
            cumulative: list[float] = []
            acc = 0.0
            for d in deviations:
                acc += d
                cumulative.append(acc)
            r = max(cumulative) - min(cumulative)
            std = math.sqrt(sum(d * d for d in deviations) / win_size)
            if std > 0 and r > 0:
                rs_vals.append(r / std)

        if rs_vals:
            avg_rs = sum(rs_vals) / len(rs_vals)
            x_vals.append(math.log(win_size))
            y_vals.append(math.log(avg_rs))

    if len(x_vals) < 2:
        raise ValueError("Not enough valid R/S points for regression")

    # 简单最小二乘拟合 y = H·x + b
    x_mean = sum(x_vals) / len(x_vals)
    y_mean = sum(y_vals) / len(y_vals)
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, y_vals, strict=True))
    den = sum((x - x_mean) ** 2 for x in x_vals)
    if den == 0:
        raise ValueError("Regression denominator is zero (all window sizes identical?)")
    return num / den
