"""KF-26 参数优化器 · 给定 |ν|/σ 分布 D(μ, σ) 反推最优 (K_S, K_T, τ)

框架:
  strength X = |ν|/σ ~ D（用户提供均值 μ_D、标准差 σ_D）
  E_gross(x; K_S, K_T) = (K_T+K_S)/2 · [P_win(+2x) + P_win(-2x)] - K_S
  E_net = ∫_τ^∞ g(x) f(x) dx / P(X≥τ) - 2c
  Sharpe/年 = √N × E_net/σ_trade

假设:
  - X ~ folded normal (|N(μ_0, σ_0)|), 通过矩匹配从 μ_D, σ_D 反推
  - 也支持直接用截断正态或经验分布
  - 用数值积分 scipy.integrate.quad
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy import integrate, optimize, stats


# ---------- FPT 核心 ----------

def p_win(lam: float, K_S: float, K_T: float) -> float:
    if abs(lam) < 1e-9:
        return K_S / (K_S + K_T)
    # 溢出保护：|λ|·max(K_S,K_T) 太大时用极限
    L = lam * K_T
    if L > 50:
        return 1.0
    if L < -50:
        return 0.0
    a = math.exp(L)
    b = math.exp(-lam * K_S)
    denom = a - b
    if abs(denom) < 1e-300:
        return K_S / (K_S + K_T)
    return (a * (1 - b)) / denom


def g_of_x(x: float, K_S: float, K_T: float) -> float:
    """KF-26 混合期望 g(x)"""
    lam = 2 * x
    p_plus = p_win(+lam, K_S, K_T)
    p_minus = p_win(-lam, K_S, K_T)
    p_mix = 0.5 * (p_plus + p_minus)
    return K_T * p_mix - K_S * (1 - p_mix)


def gross_var(x: float, K_S: float, K_T: float) -> float:
    """混合分布单笔 gross 的二阶矩（近似只算 barrier 触达）"""
    lam = 2 * x
    p_plus = p_win(+lam, K_S, K_T)
    p_minus = p_win(-lam, K_S, K_T)
    p_mix = 0.5 * (p_plus + p_minus)
    # E[gross²] = p_mix·K_T² + (1-p_mix)·K_S²
    return p_mix * K_T ** 2 + (1 - p_mix) * K_S ** 2 - g_of_x(x, K_S, K_T) ** 2


# ---------- 分布抽象 ----------

@dataclass
class FoldedNormal:
    """|X|, X ~ N(mu0, sd0). 通过给定均值/方差反推 mu0, sd0"""
    mu_D: float   # 目标均值 E[|X|]
    sd_D: float   # 目标标准差 std(|X|)
    mu0: float = 0.0
    sd0: float = 1.0

    def fit(self):
        # 折叠正态的均值/方差公式
        def moments(params):
            mu0, sd0 = params
            if sd0 <= 0:
                return (1e9, 1e9)
            alpha = mu0 / sd0
            phi = stats.norm.pdf(alpha)
            Phi = stats.norm.cdf(alpha)
            mean = sd0 * math.sqrt(2 / math.pi) * math.exp(-mu0 ** 2 / (2 * sd0 ** 2)) + mu0 * (2 * Phi - 1)
            var = mu0 ** 2 + sd0 ** 2 - mean ** 2
            return (mean - self.mu_D, math.sqrt(max(var, 1e-12)) - self.sd_D)

        sol = optimize.root(moments, x0=[0.05, self.sd_D + 0.05], method="hybr")
        self.mu0, self.sd0 = sol.x

    def pdf(self, x):
        if x < 0:
            return 0.0
        return stats.norm.pdf(x, self.mu0, self.sd0) + stats.norm.pdf(-x, self.mu0, self.sd0)

    def survival(self, tau):
        return integrate.quad(self.pdf, tau, np.inf)[0]

    def E_of_h_given_ge(self, h, tau):
        """E[h(X) | X ≥ τ]，Monte Carlo 积分"""
        num = integrate.quad(lambda x: h(x) * self.pdf(x), tau, np.inf, limit=100)[0]
        den = self.survival(tau)
        return num / max(den, 1e-12)


# ---------- 优化 ----------

def evaluate(K_S: float, K_T: float, tau: float,
             D: FoldedNormal, c_side: float,
             sigma_bar: float, year_hours: float) -> dict:
    p_ge = D.survival(tau)
    default = {"K_S": K_S, "K_T": K_T, "tau": tau,
               "P_ge_tau": p_ge, "n_year": 0.0,
               "E_gross": 0.0, "E_net": 0.0,
               "sigma_trade": 1.0, "sharpe_trade": 0.0,
               "sharpe_year": -1e9, "ann_pct_r1": -1e9,
               "E_tau_hours": 0.0}
    if p_ge < 1e-4:
        return default

    E_gross_cond = D.E_of_h_given_ge(lambda x: g_of_x(x, K_S, K_T), tau)
    E_gross2_cond = D.E_of_h_given_ge(
        lambda x: g_of_x(x, K_S, K_T) ** 2 + gross_var(x, K_S, K_T), tau
    )
    E_net = E_gross_cond - 2 * c_side
    sigma_trade = math.sqrt(max(E_gross2_cond - E_gross_cond ** 2, 0.01))

    # 平均首达时间：无漂移下 E[τ] = K_S·K_T/σ² (§1.3.1)
    E_tau_bars = K_S * K_T / max(sigma_bar ** 2, 1e-6)
    # 每笔占用的时间 = E[τ]，笔数 = 有效时间/E[τ] × P(X≥τ)
    n_year = p_ge * year_hours / max(E_tau_bars, 1.0)

    if n_year <= 0:
        return default

    sharpe_trade = E_net / sigma_trade
    sharpe_year = sharpe_trade * math.sqrt(n_year)
    ann_pct_r1 = (E_net / K_S) * n_year
    return {
        "K_S": K_S, "K_T": K_T, "tau": tau,
        "P_ge_tau": p_ge, "n_year": n_year,
        "E_gross": E_gross_cond, "E_net": E_net,
        "sigma_trade": sigma_trade,
        "sharpe_trade": sharpe_trade,
        "sharpe_year": sharpe_year,
        "ann_pct_r1": ann_pct_r1,
        "E_tau_hours": E_tau_bars,
    }


def optimize_all(D: FoldedNormal, c_side: float, K_S_min: float,
                 K_S_max: float, K_T_max: float,
                 sigma_bar: float, year_hours: float,
                 objective: str = "sharpe_year") -> dict:
    """在 (K_S, RR, τ) 三维网格上搜最优"""
    K_S_grid = np.linspace(K_S_min, min(K_S_max, 5.0), 5)
    RR_grid = [1.0, 1.5, 2.0, 2.5, 3.0]
    tau_grid = np.linspace(0.05, 0.55, 11)

    best = None
    for K_S in K_S_grid:
        for RR in RR_grid:
            K_T = K_S * RR
            if K_T > K_T_max:
                continue
            for tau in tau_grid:
                try:
                    r = evaluate(K_S, K_T, tau, D, c_side,
                                 sigma_bar, year_hours)
                except Exception:
                    continue
                val = r[objective]
                if best is None or val > best["value"]:
                    best = {"value": val, "detail": r}
    return best


def main():
    # 玉米 1h 实测: mean|ν|/σ = 0.198, std ≈ 0.108
    D = FoldedNormal(mu_D=0.198, sd_D=0.108)
    D.fit()
    print(f"[分布拟合] |ν|/σ ~ FoldedNormal(mu0={D.mu0:+.3f}, sd0={D.sd0:.3f})")
    print(f"          目标均值={D.mu_D:.3f}, 目标std={D.sd_D:.3f}")
    print(f"          分位: p50 ≈ {integrate.quad(D.pdf, 0, 0.174)[0]:.2f}"
          " P(X≤0.174), p90 段 X ≈ 0.35+\n")

    c_side = 0.077     # 1h 单边
    K_S_min = 1.0      # 1h 跳空安全下限
    K_S_max = 6.0
    K_T_max = 12.0
    sigma_bar = 1.0    # 1h: σ_bar ≈ 1 ATR/√h (主题标定)
    year_hours = 250 * 6.5

    for obj in ["sharpe_year", "ann_pct_r1", "E_net"]:
        best = optimize_all(D, c_side, K_S_min, K_S_max, K_T_max,
                            sigma_bar, year_hours, objective=obj)
        d = best["detail"]
        print(f"===== 目标: {obj} =====")
        print(f"  K_S*={d['K_S']:.2f}  K_T*={d['K_T']:.2f}  "
              f"RR*={d['K_T']/d['K_S']:.2f}  τ*={d['tau']:.3f}")
        print(f"  P(X≥τ)={d['P_ge_tau']:.3f}  N/年={d['n_year']:.1f}")
        print(f"  E_gross={d['E_gross']:+.3f}  E_net={d['E_net']:+.3f}  "
              f"σ_trade={d['sigma_trade']:.3f}")
        print(f"  Sharpe/trade={d['sharpe_trade']:+.3f}  "
              f"Sharpe/年={d['sharpe_year']:+.2f}  "
              f"年化@r=1%={d['ann_pct_r1']:+.2f}%\n")

    # 敏感性：如果分布方差更大（fat tail），最优参数会怎么变？
    print("===== 敏感性: 分布方差扫描（μ_D 固定 0.198）=====")
    for sd_D in [0.05, 0.08, 0.108, 0.15, 0.25]:
        D2 = FoldedNormal(mu_D=0.198, sd_D=sd_D)
        D2.fit()
        best = optimize_all(D2, c_side, K_S_min, K_S_max, K_T_max,
                            sigma_bar, year_hours, objective="sharpe_year")
        d = best["detail"]
        print(f"  σ_D={sd_D:.3f}: K_S*={d['K_S']:.2f}  K_T*={d['K_T']:.2f}  "
              f"τ*={d['tau']:.3f}  N/年={d['n_year']:.1f}  "
              f"E_net={d['E_net']:+.2f}  Sharpe/年={d['sharpe_year']:+.2f}  "
              f"年化={d['ann_pct_r1']:+.1f}%")


if __name__ == "__main__":
    main()
