"""
派生量与工程工具 · μ 敏感性 · K_T 可行区间 · 凯利 · T†

文件级元信息：
- 创建背景：shaping-theory §3.5.1–§3.5.5 沉淀的五个工程导出量。原本只散在 raw-scripts，
  作为下游 workbench 反复调用的公用工具。本模块把它们统一落成纯函数接口。
- 用途：给定塑形容器 + 市场假设，计算 μ 敏感性、K_T 可行区间、凯利仓位、临界离场时限。
- 注意事项：本域只提供闭式或经验闭式，无 barrier trailing 完整 chandelier 实现（v3 规划）。
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from research.fpt import e_gross_infty, e_net_infty

# 类型别名 · 一元实值函数
_FloatFn = Callable[[float], float]


@dataclass
class MuSensitivity:
    """μ 敏感性输出（shaping-theory §3.5.1）。

    Attributes:
        mu_grid: μ 值格点（默认 {-σ, -0.5σ, 0, +0.5σ, +σ}）
        e_net_grid: 对应的 E[net]
        mu_star: 盈亏平衡漂移（E[net]=0 处），若不存在返回 None
        verdict: "robust"（μ*≤0）· "moderate"（0<μ*<0.5σ）· "high_bar"（μ*>0.5σ）·
                 "infeasible"（μ*>σ 或不存在）
    """

    mu_grid: list[float]
    e_net_grid: list[float]
    mu_star: float | None
    verdict: str


def _brentq(
    f: _FloatFn,
    a: float,
    b: float,
    tol: float = 1e-8,
    max_iter: int = 100,
) -> float | None:
    """简易 brentq 求 f(x)=0 · 手写实现避免 scipy 依赖。返回 None 表示区间内无零点。"""
    fa, fb = f(a), f(b)
    if fa * fb > 0:
        return None
    # bisection
    for _ in range(max_iter):
        m = 0.5 * (a + b)
        fm = f(m)
        if abs(fm) < tol or (b - a) / 2 < tol:
            return m
        if fa * fm < 0:
            b, fb = m, fm
        else:
            a, fa = m, fm
    return 0.5 * (a + b)


def mu_sensitivity(k_s: float, k_t: float, sigma: float, c_side: float) -> MuSensitivity:
    """μ 敏感性 · 输出 5 档 E[net] 与 μ* 盈亏平衡漂移。

    公式（shaping-theory §3.5.1）：
        λ(μ) = 2·(μ - σ²/2) / σ²
        E[net](μ) = E[gross](λ(μ)) - 2c

    Args:
        k_s, k_t: barrier 距离
        sigma: 每单位时间波动率
        c_side: 单边成本

    Returns:
        MuSensitivity
    """
    mu_grid = [-sigma, -0.5 * sigma, 0.0, 0.5 * sigma, sigma]

    def _e_net_at(mu: float) -> float:
        nu = mu - 0.5 * sigma**2
        lam = 2.0 * nu / (sigma**2)
        return e_net_infty(lam, k_s, k_t, c_side)

    e_net_grid = [_e_net_at(mu) for mu in mu_grid]

    # 求 μ* · 在 [-2σ, +2σ] 内找零点
    mu_star = _brentq(_e_net_at, -2 * sigma, 2 * sigma)

    if mu_star is None or mu_star > sigma:
        verdict = "infeasible"
    elif mu_star > 0.5 * sigma:
        verdict = "high_bar"
    elif mu_star > 0:
        verdict = "moderate"
    else:
        verdict = "robust"

    return MuSensitivity(mu_grid=mu_grid, e_net_grid=e_net_grid, mu_star=mu_star, verdict=verdict)


@dataclass
class KTFeasibleRange:
    """K_T 可行区间输出（shaping-theory §3.5.2）。

    Attributes:
        k_t_target: 按目标胜率反解（λ=0）= K_S · (1 - P) / P
        k_t_max: 物理可达上限 = k · σ · √T
        ratio: k_t_max / k_t_target
        verdict: "wide"（>3, 强候选）· "narrow"（<1.5, 慎选）· "empty"（>=1.5 <=3 or reversed）
    """

    k_t_target: float
    k_t_max: float
    ratio: float
    verdict: str


def k_t_feasible_range(k_s: float, p_target: float, sigma: float, t_horizon: float, k: float = 2.0) -> KTFeasibleRange:
    """K_T 可行区间反解（shaping-theory §3.5.2）。

    Args:
        k_s: 止损距离
        p_target: 目标胜率 ∈ (0, 1)
        sigma: 每单位时间波动率
        t_horizon: 时间上限
        k: 物理可达倍数（推荐 2 · P=95%）

    Returns:
        KTFeasibleRange
    """
    if not (0.0 < p_target < 1.0):
        raise ValueError(f"p_target must be in (0, 1), got {p_target}")
    if k_s <= 0 or sigma <= 0 or t_horizon <= 0:
        raise ValueError("k_s, sigma, t_horizon must be positive")

    k_t_target = k_s * (1.0 - p_target) / p_target
    k_t_max = k * sigma * math.sqrt(t_horizon)
    ratio = k_t_max / k_t_target if k_t_target > 0 else float("inf")

    if k_t_target > k_t_max:
        verdict = "empty"
    elif ratio > 3.0:
        verdict = "wide"
    elif ratio < 1.5:
        verdict = "narrow"
    else:
        verdict = "moderate"

    return KTFeasibleRange(k_t_target=k_t_target, k_t_max=k_t_max, ratio=ratio, verdict=verdict)


def kelly_position(e_net: float, k_s: float, k_t: float, alpha: float = 0.5, f_max: float = 1.0) -> float:
    """凯利仓位（shaping-theory §3.5.3）。

    公式：
        f* = E[net] / (K_S · K_T)     · 全凯利
        f_kelly = α · f*              · 部分凯利避免破产
        f_final = min(f_kelly, f_max)

    Args:
        e_net: 单笔净期望
        k_s, k_t: barrier 距离
        alpha: 部分凯利系数，推荐 [0.25, 0.5]
        f_max: 单笔仓位硬上限

    Returns:
        最终仓位 f_final ∈ [0, f_max]。若 E[net] ≤ 0 返回 0（不该开仓）。
    """
    if e_net <= 0:
        return 0.0
    if k_s <= 0 or k_t <= 0:
        raise ValueError("k_s, k_t must be positive")
    if not (0.0 < alpha <= 1.0):
        raise ValueError(f"alpha must be in (0, 1], got {alpha}")

    f_star = e_net / (k_s * k_t)
    f_kelly = alpha * f_star
    return min(f_kelly, f_max)


def t_dagger_empirical(t_horizon: float, k_drift: float = 0.5) -> float:
    """T† 临界离场时限经验估计（shaping-theory §3.5.4 · KF-22 经验规则 T† ≈ T/2）。

    Args:
        t_horizon: 总时间上限
        k_drift: 经验系数，默认 0.5（KF-22 实证）

    Returns:
        T† ≈ k_drift · T_horizon

    注意：
        - λ=0 对称 barrier 下 T† 严格不存在（E[X_t | τ > t] ≡ 0）
        - λ > 0 时先升后降，T† ≈ K_T / μ · k_drift 更精确（需 μ 已知）
        - 本函数用 k_drift·T 简化经验规则，适用于快速筛选，精细版需 Fourier v2
    """
    if t_horizon <= 0:
        raise ValueError(f"t_horizon must be positive, got {t_horizon}")
    return k_drift * t_horizon


def e_gross_at_mu(mu: float, sigma: float, k_s: float, k_t: float) -> float:
    """给定 μ 计算 E[gross] · 便捷函数。

    公式：λ = 2·(μ - σ²/2) / σ²，再调 e_gross_infty(λ)
    """
    if sigma <= 0:
        raise ValueError("sigma must be positive")
    nu = mu - 0.5 * sigma**2
    lam = 2.0 * nu / (sigma**2)
    return e_gross_infty(lam, k_s, k_t)
