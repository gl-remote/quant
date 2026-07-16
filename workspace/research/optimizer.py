"""
KF-27 参数优化器：|ν|/σ 分布输入 → 最优 (K_S*, K_T*, τ*)

文件级元信息：
- 创建背景：shaping-theory §2.23 KF-27 是主题的核心工程成果——把 27 个 KF 收敛为
  一个直接可调用的参数优化器接口。玉米 1h 输入 (μ_D=0.198, σ_D=0.108, c=0.077, σ_bar=1.0)
  输出 K_S*=3, K_T*=9, RR*=3, τ*=前 65% 段，Sharpe/年 +1.66，年化 +20.2%。
- 用途：给定品种/周期的强度分布 D + 市场参数，反解最优塑形容器。
- 注意事项：本实现是网格搜索版本，与 shaping-theory §2.23.2 数值对齐至 3% 精度。
  分布拟合误差（FoldedNormal 只用两阶矩）是主误差源，任何品种上线前必做
  σ_D ±30% 敏感性核对（shaping-theory §2.23.4）。

数学接口：三条 FOC（内点极值必要条件）：
  1. ∂Sharpe/∂τ = 0：门槛 τ* 落在"边际 g(τ*) 等于超阈条件均值"处
  2. ∂Sharpe/∂K_T = 0：K_T* 让 P⁺(2x) 在分布支撑区上刚接近饱和
  3. ∂Sharpe/∂K_S = 0：K_S 通常紧贴 KF-23 跳空下限
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from research.channel_b import e_gross_mix
from research.distribution import FoldedNormal
from research.fpt import e_tau_infty

Objective = Literal["sharpe_year", "annual_pct", "e_net_per_trade"]


@dataclass
class KF27Params:
    """KF-27 参数优化器输入。

    Attributes:
        distribution: |ν|/σ 分布对象（已 fit）
        c_side: 单边成本（ATR）
        sigma_bar: 每 bar 波动率
        year_hours: 年交易小时数（默认 1625 = 250 交易日 × 6.5h）
        k_s_min: K_S 下限（KF-23 跳空约束 · 1h ≥ 1.0, 5m ≥ 2.6）
        k_s_max: K_S 上限（网格搜索范围）
        k_t_max: K_T 上限
        rr_grid: 盈亏比候选（默认 R=2/3/4，R=3 通常最优）
        tau_grid: 择时门槛候选（前 τ 分位）· 前 τ ∈ (0, 1)
    """

    distribution: FoldedNormal
    c_side: float
    sigma_bar: float = 1.0
    year_hours: float = 1625.0
    k_s_min: float = 1.0
    k_s_max: float = 6.0
    k_t_max: float = 12.0
    rr_grid: tuple[float, ...] = (2.0, 2.5, 3.0, 3.5, 4.0)
    tau_grid: tuple[float, ...] = (
        0.05,
        0.10,
        0.15,
        0.20,
        0.30,
        0.40,
        0.50,
        0.60,
        0.70,
        0.80,
        0.90,
    )
    k_s_step: float = 0.25


@dataclass
class KF27Result:
    """KF-27 参数优化器输出。

    Attributes:
        k_s: 最优止损（ATR）
        k_t: 最优止盈（ATR）
        rr: K_T / K_S 最优盈亏比
        tau: 最优择时门槛（前 τ 分位）
        x_star: 门槛对应的 x 值 = Q_D(1 - τ)
        p_ge_tau: P(X ≥ τ) = τ（分位定义）
        n_year: 年入场次数（裸口径：单合约）
        e_tau_hours: 平均首达时间（小时）
        e_gross: 每笔毛期望（在 x = 分位均值下）
        e_net: 每笔净期望
        sigma_trade: 单笔标准差
        sharpe_trade: 单笔 Sharpe
        sharpe_year: 年化 Sharpe = √N · Sharpe/trade
        ann_pct_r1: 年化收益率 @ r=1% 单笔仓位
    """

    k_s: float
    k_t: float
    rr: float
    tau: float
    x_star: float
    p_ge_tau: float
    n_year: float
    e_tau_hours: float
    e_gross: float
    e_net: float
    sigma_trade: float
    sharpe_trade: float
    sharpe_year: float
    ann_pct_r1: float


def _x_slice_mean(distribution: FoldedNormal, tau: float, n_grid: int = 100) -> float:
    """条件均值 E[X | X ≥ x_star]（用于替代 KF-26 单点均值近似）。

    在 [x_star, +∞) 上做梯形积分，n_grid 默认 100 精度足够。
    """
    x_star = distribution.quantile_at_top(tau)
    # 积分上限取 icdf(0.999)（保留 0.1% 尾部）
    x_upper = distribution.icdf(0.999)
    if x_upper <= x_star:
        return x_star

    step = (x_upper - x_star) / n_grid
    xs = [x_star + i * step for i in range(n_grid + 1)]
    # p_ge_tau = τ（分位定义）
    # 数值积分 ∫ x · f(x) dx 在 [x_star, x_upper] · f 由 CDF 差分逼近
    total_mass = 0.0
    total_moment = 0.0
    for i in range(n_grid):
        mid = 0.5 * (xs[i] + xs[i + 1])
        mass = distribution.cdf(xs[i + 1]) - distribution.cdf(xs[i])
        total_mass += mass
        total_moment += mid * mass
    if total_mass <= 0:
        return x_star
    return total_moment / total_mass


def _evaluate(params: KF27Params, k_s: float, k_t: float, tau: float) -> KF27Result | None:
    """给定 (K_S, K_T, τ) 三元组，评估综合指标。"""
    if k_t <= k_s or k_t > params.k_t_max:
        return None

    d = params.distribution
    x_star = d.quantile_at_top(tau)
    p_ge_tau = tau  # 分位定义
    x_mean = _x_slice_mean(d, tau)

    # 用条件均值代入 KF-26 混合期望
    e_gross = e_gross_mix(x_mean, k_s, k_t, params.sigma_bar)
    e_net = e_gross - 2.0 * params.c_side

    # 单笔标准差 · 二项分布近似 σ_trade = √(P·(1-P))·(K_T+K_S)
    # 此处用 gross 幅度做 barrier width 近似
    barrier_width = k_t + k_s
    # 用 x_mean 对应 λ 算 P_win（DirRandom 混合）
    lam0 = 2.0 * x_mean / params.sigma_bar
    from research.fpt import p_win_infty  # noqa: PLC0415  内部循环调用不 hoist

    p_plus = p_win_infty(+lam0, k_s, k_t)
    p_minus = p_win_infty(-lam0, k_s, k_t)
    p_mix = 0.5 * (p_plus + p_minus)
    sigma_trade = math.sqrt(max(1e-9, p_mix * (1.0 - p_mix))) * barrier_width

    if sigma_trade <= 0:
        return None

    sharpe_trade = e_net / sigma_trade

    # 年入场次数（裸口径 · 单合约）
    e_tau_hours = e_tau_infty(0.0, k_s, k_t, params.sigma_bar)  # 用零漂移平均首达
    if e_tau_hours <= 0:
        return None
    n_year = p_ge_tau * params.year_hours / e_tau_hours
    sharpe_year = math.sqrt(max(0.0, n_year)) * sharpe_trade

    # 年化收益率 @ r=1% 单笔仓位（每笔挪 K_S ATR 的仓位）
    ann_pct_r1 = (e_net / k_s) * n_year * 0.01

    return KF27Result(
        k_s=k_s,
        k_t=k_t,
        rr=k_t / k_s,
        tau=tau,
        x_star=x_star,
        p_ge_tau=p_ge_tau,
        n_year=n_year,
        e_tau_hours=e_tau_hours,
        e_gross=e_gross,
        e_net=e_net,
        sigma_trade=sigma_trade,
        sharpe_trade=sharpe_trade,
        sharpe_year=sharpe_year,
        ann_pct_r1=ann_pct_r1,
    )


def optimize_kf27(params: KF27Params, objective: Objective = "sharpe_year") -> KF27Result:
    """KF-27 参数优化：网格搜索 (K_S, RR, τ)。

    Args:
        params: 输入参数（分布 + 市场参数 + 网格）
        objective: 优化目标 · sharpe_year（推荐）· annual_pct · e_net_per_trade

    Returns:
        最优 KF27Result

    Raises:
        RuntimeError: 若网格范围内所有配置的 e_net ≤ 0（分布过弱 or 成本过高）
    """
    if not params.distribution._fitted:
        params.distribution.fit()

    best: KF27Result | None = None
    best_value = -math.inf

    k_s = params.k_s_min
    while k_s <= params.k_s_max + 1e-9:
        for rr in params.rr_grid:
            k_t = k_s * rr
            for tau in params.tau_grid:
                res = _evaluate(params, k_s, k_t, tau)
                if res is None or res.e_net <= 0:
                    continue

                if objective == "sharpe_year":
                    value = res.sharpe_year
                elif objective == "annual_pct":
                    value = res.ann_pct_r1
                elif objective == "e_net_per_trade":
                    value = res.e_net
                else:
                    raise ValueError(f"Unknown objective: {objective}")

                if value > best_value:
                    best_value = value
                    best = res
        k_s += params.k_s_step

    if best is None:
        raise RuntimeError(
            f"No feasible (K_S, K_T, τ) found under objective={objective}. "
            f"Distribution may be too weak or c_side={params.c_side} too high."
        )
    return best
