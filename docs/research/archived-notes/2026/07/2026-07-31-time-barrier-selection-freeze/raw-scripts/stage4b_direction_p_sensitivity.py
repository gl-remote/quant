"""Stage 4b: KF-27 优化器 + 方向概率 p 敏感性.

在 KF-26 混合期望上加入方向命中率 p ∈ [0.5, 1.0]:
  E[gross | x, p] = p * g(+2x) + (1-p) * g(-2x)
其中 g(λ) = K_T * P_win(λ) - K_S * (1 - P_win(λ)).

p=0.5 还原 DirRandom (KF-26 通道 B);
p>0.5 引入方向 edge (KF-19 通道 A 混合).

用扩网格 (K_S 到 6, RR 到 5, tau 到 0.02) 避免边界解.
以玉米 1h (μ_D=0.072, σ_D=0.100) 为基准, 扫 p ∈ {0.50, 0.55, 0.60, 0.65, 0.70}.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
import numpy as np
from scipy import integrate, optimize as sp_optimize, stats


# ---------- FPT ----------
def p_win(lam, K_S, K_T):
    if abs(lam) < 1e-9:
        return K_S / (K_S + K_T)
    L = lam * K_T
    if L > 50: return 1.0
    if L < -50: return 0.0
    a = math.exp(L)
    b = math.exp(-lam * K_S)
    denom = a - b
    if abs(denom) < 1e-300:
        return K_S / (K_S + K_T)
    return (a * (1 - b)) / denom


def g_of_x_p(x, K_S, K_T, p):
    """带方向概率 p 的混合期望 gross."""
    lam = 2 * x
    p_plus = p_win(+lam, K_S, K_T)
    p_minus = p_win(-lam, K_S, K_T)
    # p 概率方向对 (+λ), (1-p) 概率方向错 (-λ)
    p_mix = p * p_plus + (1 - p) * p_minus
    return K_T * p_mix - K_S * (1 - p_mix)


def gross_var_p(x, K_S, K_T, p):
    lam = 2 * x
    p_plus = p_win(+lam, K_S, K_T)
    p_minus = p_win(-lam, K_S, K_T)
    p_mix = p * p_plus + (1 - p) * p_minus
    g = g_of_x_p(x, K_S, K_T, p)
    return p_mix * K_T ** 2 + (1 - p_mix) * K_S ** 2 - g ** 2


# ---------- 分布 (复用 KF-27 FoldedNormal) ----------
@dataclass
class FoldedNormal:
    mu_D: float
    sd_D: float
    mu0: float = 0.0
    sd0: float = 1.0

    def fit(self):
        def moments(params):
            mu0, sd0 = params
            if sd0 <= 0:
                return (1e9, 1e9)
            alpha = mu0 / sd0
            phi = stats.norm.pdf(alpha)
            Phi = stats.norm.cdf(alpha)
            mean = sd0 * math.sqrt(2/math.pi) * math.exp(-mu0**2/(2*sd0**2)) + mu0 * (2*Phi - 1)
            var = mu0**2 + sd0**2 - mean**2
            return (mean - self.mu_D, math.sqrt(max(var, 1e-12)) - self.sd_D)
        sol = sp_optimize.root(moments, x0=[0.05, self.sd_D + 0.05], method="hybr")
        self.mu0, self.sd0 = sol.x

    def pdf(self, x):
        if x < 0: return 0.0
        return stats.norm.pdf(x, self.mu0, self.sd0) + stats.norm.pdf(-x, self.mu0, self.sd0)

    def survival(self, tau):
        return integrate.quad(self.pdf, tau, np.inf)[0]

    def E_cond(self, h, tau):
        num = integrate.quad(lambda x: h(x) * self.pdf(x), tau, np.inf, limit=50)[0]
        den = self.survival(tau)
        return num / max(den, 1e-12)


def evaluate(K_S, K_T, tau, D, p, c_side, sigma_bar, year_bars):
    p_ge = D.survival(tau)
    default = dict(K_S=K_S, K_T=K_T, tau=tau, P_ge=p_ge, n_year=0,
                   E_gross=0, E_net=0, sigma_trade=1, sharpe_year=-1e9, ann=-1e9)
    if p_ge < 1e-4:
        return default
    E_g = D.E_cond(lambda x: g_of_x_p(x, K_S, K_T, p), tau)
    E_g2 = D.E_cond(lambda x: g_of_x_p(x, K_S, K_T, p)**2 + gross_var_p(x, K_S, K_T, p), tau)
    E_net = E_g - 2 * c_side
    sigma_trade = math.sqrt(max(E_g2 - E_g**2, 0.01))
    E_tau_bars = K_S * K_T / max(sigma_bar**2, 1e-6)
    n_year = p_ge * year_bars / max(E_tau_bars, 1.0)
    if n_year <= 0:
        return default
    sharpe_year = (E_net / sigma_trade) * math.sqrt(n_year)
    ann = (E_net / K_S) * n_year
    return dict(K_S=K_S, K_T=K_T, tau=tau, P_ge=p_ge, n_year=n_year,
                E_gross=E_g, E_net=E_net, sigma_trade=sigma_trade,
                sharpe_year=sharpe_year, ann=ann)


def optimize(D, p, c_side, sigma_bar, year_bars,
             K_S_max=6.0, RR_max=5.0, K_T_max=18.0):
    """扩网格: K_S ∈ [0.5, 6] step 1.0, RR ∈ [1,5] step 0.5, tau ∈ [0.02, 0.5] step 12."""
    K_S_grid = np.arange(0.5, K_S_max + 0.01, 1.0)
    RR_grid = np.arange(1.0, RR_max + 0.01, 0.5)
    tau_grid = np.linspace(0.02, 0.50, 12)
    best = None
    for K_S in K_S_grid:
        for RR in RR_grid:
            K_T = K_S * RR
            if K_T > K_T_max:
                continue
            for tau in tau_grid:
                try:
                    r = evaluate(K_S, K_T, tau, D, p, c_side, sigma_bar, year_bars)
                except Exception:
                    continue
                if best is None or r["sharpe_year"] > best["sharpe_year"]:
                    best = r
    return best

def main():
    # 玉米 1h W=80
    D = FoldedNormal(mu_D=0.072, sd_D=0.100)
    D.fit()
    print(f"[分布] c/1h W=80: mu_D={D.mu_D}, sd_D={D.sd_D}, "
          f"反推 mu0={D.mu0:+.3f}, sd0={D.sd0:.3f}\n")

    c_side = 0.077
    sigma_bar = 1.0
    year_bars = 1625

    print(f"{'p':>5} {'K_S*':>5} {'K_T*':>5} {'RR*':>4} {'tau*':>5} "
          f"{'P(ge)':>6} {'N/yr':>6} {'E_gross':>8} {'E_net':>7} "
          f"{'Sharpe/yr':>10} {'年化%':>7}")
    print("-" * 90)
    rows = []
    for p in [0.50, 0.55, 0.60, 0.65, 0.70, 0.80]:
        b = optimize(D, p, c_side, sigma_bar, year_bars)
        RR = b["K_T"] / b["K_S"]
        print(f"{p:5.2f} {b['K_S']:5.1f} {b['K_T']:5.1f} {RR:4.1f} {b['tau']:5.2f} "
              f"{b['P_ge']:6.3f} {b['n_year']:6.1f} {b['E_gross']:+8.3f} {b['E_net']:+7.3f} "
              f"{b['sharpe_year']:+10.2f} {b['ann']:+7.1f}")
        rows.append(dict(p=p, **b))

    print()
    print("=== 解读 ===")
    print("p=0.50: DirRandom 基线 (无方向 edge), 通道 B")
    print("p=0.55: KF-19 实测 EMA aligned 量级 (玉米 1h 真实可达)")
    print("p=0.60+: 强方向信号 (需较好的趋势过滤器)")
    print()
    print("关键观察: 随 p 上升, K_S* 应减小, RR* 应降低, tau* 应提高")


if __name__ == "__main__":
    main()
