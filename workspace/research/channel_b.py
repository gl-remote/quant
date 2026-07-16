"""
通道 B 混合期望（DirRandom + 强段公理 + 非对称塑形）

文件级元信息：
- 创建背景：shaping-theory §2.22.2 · KF-26 沉淀了 DirRandom 下的混合期望闭式公式；
  §2.23.6.2 通过小 λ 展开得到 O(x²) 近似 + 盈亏平衡下限 x_min。
  这是通道 B 独立于方向 alpha 的数学根据，也是 strength-factor-screening 主题的核心工具。
- 用途：给定 (x = |ν|/σ, K_S, R, c_side)，输出混合毛期望与盈亏平衡最低强度。
- 注意事项：混合公式假设 |ν|/σ 在段内为常数（用均值近似）。
  x_min 小 λ 展开在 x < 0.15 精度 3-12%；x > 0.20 应用完整 e_gross_mix。
"""

from __future__ import annotations

import math

from research.fpt import p_win_infty


def e_gross_mix(x: float, k_s: float, k_t: float, sigma_bar: float = 1.0) -> float:
    """DirRandom 下的混合毛期望（精确版）。

    公式（shaping-theory §2.22.2）：
        λ_0 = 2·(|ν|/σ) / σ_bar = 2·x / σ_bar
        E_gross_mix = (K_T + K_S) / 2 · [P_win(+λ_0) + P_win(-λ_0)] - K_S

    数学根据：DirRandom 下入场方向 d ∈ {+1, -1} 各以 1/2 概率取值、与 sign(ν) 独立，
    故有效 λ 以 ±2|ν|/σ² 各 1/2 概率取值。

    Args:
        x: |ν|/σ 强度读数（无量纲，非负）
        k_s, k_t: barrier 距离（ATR）
        sigma_bar: 每 bar 波动率（1h=1.0, 15m=0.5, 5m=1/√12）

    Returns:
        混合毛期望（ATR 单位）· R > 1 且 x > 0 时 > 0
    """
    if x < 0:
        raise ValueError(f"x must be non-negative, got {x}")
    if k_s <= 0 or k_t <= 0 or sigma_bar <= 0:
        raise ValueError(f"k_s, k_t, sigma_bar must be positive, got k_s={k_s}, k_t={k_t}, sigma_bar={sigma_bar}")

    lam0 = 2.0 * x / sigma_bar
    p_plus = p_win_infty(+lam0, k_s, k_t)
    p_minus = p_win_infty(-lam0, k_s, k_t)
    return 0.5 * (k_t + k_s) * (p_plus + p_minus) - k_s


def e_gross_mix_smallx(x: float, k_s: float, k_t: float) -> float:
    """DirRandom 混合毛期望（小 x 二阶展开近似，shaping-theory §2.23.6.2）。

    公式：E_gross_mix(x) ≈ x² · K_S³ · R · (R-1) / 3，R = K_T / K_S

    奇数阶项在 DirRandom 下对消，只剩 O(x²) 主项。
    精度：x < 0.15 时误差 3-12%；x > 0.20 应用完整 e_gross_mix。

    Args:
        x: |ν|/σ 强度读数
        k_s, k_t: barrier 距离

    Returns:
        近似混合毛期望
    """
    if x < 0:
        raise ValueError(f"x must be non-negative, got {x}")
    if k_s <= 0 or k_t <= 0:
        raise ValueError(f"k_s, k_t must be positive, got k_s={k_s}, k_t={k_t}")

    r = k_t / k_s
    return (x**2) * (k_s**3) * r * (r - 1.0) / 3.0


def x_min_smallx(c_side: float, k_s: float, k_t: float) -> float:
    """盈亏平衡下限 x_min（小 x 二阶展开反解，shaping-theory §2.23.6.2 (☆)）。

    公式：x_min = √( 6c / (K_S³ · R · (R-1)) )，R = K_T / K_S

    含义：|ν|/σ 若持续低于 x_min，下游塑形容器无法把成本吸收为正 E_net。

    性质：
        R → 1⁺  ⟹  x_min → +∞    （Doob 保守律）
        R < 1   ⟹  x_min 无实数解 （反通道 B 区域，负期望）
        R  ↑    ⟹  x_min ↓
        K_S ↑   ⟹  x_min ↓
        c   ↓   ⟹  x_min ↓（平方根律 · 减半只压 30%）

    Args:
        c_side: 单边成本（ATR）· 双边成本 = 2·c_side
        k_s, k_t: barrier 距离

    Returns:
        盈亏平衡最低强度

    Raises:
        ValueError: R ≤ 1 时（对称或反通道 B，公式定义域外）
    """
    if c_side <= 0:
        raise ValueError(f"c_side must be positive, got {c_side}")
    if k_s <= 0 or k_t <= 0:
        raise ValueError(f"k_s, k_t must be positive, got k_s={k_s}, k_t={k_t}")

    r = k_t / k_s
    if r <= 1.0:
        raise ValueError(
            f"x_min is undefined for R <= 1 (got R={r:.4f}). "
            f"R=1 maps to Doob conservative law (x_min → ∞); R<1 is negative-expectation region."
        )

    return math.sqrt(6.0 * c_side / ((k_s**3) * r * (r - 1.0)))
