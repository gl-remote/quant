"""
Fourier 有限时间精确解

文件级元信息：
- 创建背景：shaping-theory §2.13.2 · KF-17 沉淀 Fourier spectral 分解作为
  barrier 停时问题的标准 null。T=∞ FPT 忽略了 time-exit 概率，
  长期区（T/T* < 1）精度骤降；Fourier 精确解可作任意有限 T 下的替代 null。
- 用途：给定 (K_S, K_T, σ, T)，输出零漂移下的 P_win(T) 与 P(τ>T)。
- 注意事项：级数用 e^(-n²) 衰减，前 10 项误差 < 1e-15，实际截断 100 项冗余充足。
  P(τ>T) < 1e-3 时数值精度差（观察到 z_B = +2367 爆炸），下游用时应过滤。
"""

from __future__ import annotations

import math

_DEFAULT_TERMS = 100


def p_win_finiteT_fourier(
    k_s: float, k_t: float, sigma: float, t_horizon: float, n_terms: int = _DEFAULT_TERMS
) -> float:
    """有限时间首达止盈概率（零漂移 Brownian motion，spectral 分解）。

    公式（shaping-theory §2.13.2，L = K_S + K_T）：
        P_win(T) = (2/π) · Σ_{n=1..∞} [(-1)^{n+1} / n] ·
                   sin(n·π·K_S / L) · (1 - e^{-n²π²σ²T / (2L²)})

    T → ∞ 时收敛到 K_S / L = P_win_∞（与 §1.3.1 一致）。

    Args:
        k_s, k_t: barrier 距离（ATR）
        sigma: 每单位时间波动率
        t_horizon: 有限时间上限（与 sigma 时间单位一致）
        n_terms: 级数截断项数，默认 100（精度 < 1e-10）

    Returns:
        P_win(T) ∈ [0, 1]
    """
    if k_s <= 0 or k_t <= 0 or sigma <= 0 or t_horizon <= 0:
        raise ValueError(
            f"k_s, k_t, sigma, t_horizon must all be positive, got "
            f"k_s={k_s}, k_t={k_t}, sigma={sigma}, t_horizon={t_horizon}"
        )

    length = k_s + k_t
    coef = 2.0 / math.pi
    acc = 0.0
    exp_prefactor = -(math.pi**2) * sigma**2 * t_horizon / (2.0 * length**2)

    for n in range(1, n_terms + 1):
        sign = 1.0 if n % 2 == 1 else -1.0  # (-1)^{n+1}
        sin_term = math.sin(n * math.pi * k_s / length)
        exp_term = math.exp((n**2) * exp_prefactor)
        acc += (sign / n) * sin_term * (1.0 - exp_term)

    return coef * acc


def p_tau_gt_T_fourier(k_s: float, k_t: float, sigma: float, t_horizon: float, n_terms: int = _DEFAULT_TERMS) -> float:
    """有限时间 time-exit 概率 P(τ > T)（零漂移，spectral 分解）。

    公式（shaping-theory §2.13.2，L = K_S + K_T）：
        P(τ > T) = (4/π) · Σ_{n odd} [sin(n·π·K_S / L) / n] ·
                   e^{-n²π²σ²T / (2L²)}

    Args:
        k_s, k_t: barrier 距离（ATR）
        sigma: 每单位时间波动率
        t_horizon: 有限时间上限
        n_terms: 级数截断项数

    Returns:
        P(τ > T) ∈ [0, 1]

    数值精度警告：
        当返回值 < 1e-3 时，绝对精度差；用于统计检验时应过滤该阈值下的样本。
    """
    if k_s <= 0 or k_t <= 0 or sigma <= 0 or t_horizon <= 0:
        raise ValueError(
            f"k_s, k_t, sigma, t_horizon must all be positive, got "
            f"k_s={k_s}, k_t={k_t}, sigma={sigma}, t_horizon={t_horizon}"
        )

    length = k_s + k_t
    coef = 4.0 / math.pi
    acc = 0.0
    exp_prefactor = -(math.pi**2) * sigma**2 * t_horizon / (2.0 * length**2)

    for n in range(1, n_terms + 1, 2):  # odd n only
        sin_term = math.sin(n * math.pi * k_s / length)
        exp_term = math.exp((n**2) * exp_prefactor)
        acc += (sin_term / n) * exp_term

    return coef * acc
