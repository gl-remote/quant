"""
首达定理（First Passage Theorem）无限时间精确解

文件级元信息：
- 创建背景：shaping-theory §1.3.1 / §1.4 / §1.5 定义了 barrier 停时问题的核心公式。
  多个 raw-scripts 里重复实现了同一套 P_win / E[gross] / E[τ] / T*，
  抽出稳定实现供本业务域统一调用。
- 用途：给定 (K_S, K_T, ν, σ, c)，输出零漂移或带漂移下的 barrier 首达概率与期望。
- 注意事项：本模块仅实现 T=∞ 极限解；有限 T 精确解见 research.fourier。
  数值稳定性处理：|λ| < 1e-6 走 λ=0 分支避免 e^(λK)-1 除零精度损失；
  |λ·max(K_S,K_T)| > 50 返回极限值 (P_win → 1 或 0)。
"""

from __future__ import annotations

import math

# 数值稳定性阈值
_LAMBDA_ZERO_TOL = 1e-6
_LAMBDA_SATURATE_TOL = 50.0


def p_win_infty(lam: float, k_s: float, k_t: float) -> float:
    """首达止盈概率（T=∞）。

    公式（shaping-theory §1.3.1）：
        λ ≠ 0:  P_win = e^(λ·K_T) · (1 - e^(-λ·K_S)) / (e^(λ·K_T) - e^(-λ·K_S))
        λ = 0:  P_win = K_S / (K_S + K_T) = 1/(1+R)

    Args:
        lam: 无量纲漂移比 λ = 2ν/σ²
        k_s: 止损距离（ATR 单位，> 0）
        k_t: 止盈距离（ATR 单位，> 0）

    Returns:
        首达止盈概率 ∈ [0, 1]

    数值边界：
        |λ| < 1e-6 → 走 λ=0 分支
        |λ·max(K_S,K_T)| > 50 → 返回极限值
    """
    if k_s <= 0 or k_t <= 0:
        raise ValueError(f"k_s and k_t must be positive, got k_s={k_s}, k_t={k_t}")

    if abs(lam) < _LAMBDA_ZERO_TOL:
        return k_s / (k_s + k_t)

    scale = lam * max(k_s, k_t)
    if scale > _LAMBDA_SATURATE_TOL:
        return 1.0
    if scale < -_LAMBDA_SATURATE_TOL:
        return 0.0

    e_lam_kt = math.exp(lam * k_t)
    e_neg_lam_ks = math.exp(-lam * k_s)
    denom = e_lam_kt - e_neg_lam_ks
    return (e_lam_kt * (1.0 - e_neg_lam_ks)) / denom


def e_gross_infty(lam: float, k_s: float, k_t: float) -> float:
    """毛期望（T=∞）。

    公式：E[gross] = P_win · K_T - (1 - P_win) · K_S
    λ=0 时 E[gross] ≡ 0（Doob 停时定理 · shaping-theory §1.4）。
    """
    p = p_win_infty(lam, k_s, k_t)
    return p * k_t - (1.0 - p) * k_s


def e_net_infty(lam: float, k_s: float, k_t: float, c_side: float) -> float:
    """净期望（T=∞）。

    公式：E[net] = E[gross] - 2·c_side
    λ=0 时 E[net] ≡ -2c（数学必输）。

    Args:
        c_side: 单边成本（ATR 单位）
    """
    return e_gross_infty(lam, k_s, k_t) - 2.0 * c_side


def t_star(k_s: float, k_t: float, sigma: float) -> float:
    """短期/长期分界。

    公式（shaping-theory §1.5）：T* := [max(K_S, K_T)]² / σ²
    T* 是"无漂移下平均触达 barrier 所需时间"的量级。

    Args:
        sigma: 每单位时间波动率（ATR·time^-1/2）

    Returns:
        T* 时间量级。T/T* > 3 短期区，1..3 过渡区，< 0.5 长期区。
    """
    if sigma <= 0:
        raise ValueError(f"sigma must be positive, got {sigma}")
    return max(k_s, k_t) ** 2 / (sigma**2)


def e_tau_infty(lam: float, k_s: float, k_t: float, sigma: float, nu: float | None = None) -> float:
    """平均首达时间 E[τ]（T=∞）。

    公式（shaping-theory §1.5 / §4.3）：
        λ = 0:  E[τ] = K_S · K_T / σ²                （零漂移简化式）
        λ ≠ 0:  E[τ] = (K_S · P_loss - K_T · P_win) / (-ν)

    Args:
        lam: 无量纲漂移比
        sigma: 每单位时间波动率
        nu: 对数漂移率 ν = μ - σ²/2；lam=0 时可省略

    Returns:
        平均首达时间（与 sigma 时间单位一致）
    """
    if sigma <= 0:
        raise ValueError(f"sigma must be positive, got {sigma}")

    if abs(lam) < _LAMBDA_ZERO_TOL:
        return k_s * k_t / (sigma**2)

    if nu is None:
        raise ValueError("nu is required for lam != 0")
    if nu == 0.0:
        raise ValueError("nu must be nonzero when lam != 0")

    p_win = p_win_infty(lam, k_s, k_t)
    p_loss = 1.0 - p_win
    return (k_s * p_loss - k_t * p_win) / (-nu)
