"""
Study R-optimality under OU mean reversion:
  - Exact small-kappa expansion: p_win = K_S/L + kappa * K_T K_S(2K_T+K_S)/(3 sigma^2 L)
  - E_gross per trade = kappa * K_T K_S (2K_T+K_S)/(3 sigma^2)  (always > 0)
  - The R<1 question: which R maximizes (a) Sharpe-per-trade, (b) annualized Sharpe
    accounting for trade frequency ~ 1/E[tau]?
  - Verify with ODE numerics across a grid of R (holding K_S+K_T fixed = container width L).
"""
import numpy as np
from scipy.linalg import solve_banded


def p_win_ode(kappa, K_S, K_T, sigma=1.0, n=6001):
    a = K_T + K_S
    lo, hi = -a, 0.0
    x = np.linspace(lo, hi, n)
    dx = x[1] - x[0]
    ab = np.zeros((3, n))
    rhs = np.zeros(n)
    for i in range(1, n - 1):
        ab[0, i + 1] = sigma**2 / (2 * dx**2) - kappa * x[i] / (2 * dx)
        ab[1, i] = -sigma**2 / dx**2
        ab[2, i - 1] = sigma**2 / (2 * dx**2) + kappa * x[i] / (2 * dx)
    ab[1, 0] = 1.0
    ab[1, -1] = 1.0
    rhs[-1] = 1.0
    p = solve_banded((1, 1), ab, rhs)
    idx = np.argmin(np.abs(x - (-K_T)))
    # also mean exit time via ODE  L m = -1 : (sigma^2/2)m'' - kappa x m' = -1, m=0 at boundaries
    ab2 = np.zeros((3, n))
    rhs2 = np.full(n, -1.0)
    for i in range(1, n - 1):
        ab2[0, i + 1] = sigma**2 / (2 * dx**2) - kappa * x[i] / (2 * dx)
        ab2[1, i] = -sigma**2 / dx**2
        ab2[2, i - 1] = sigma**2 / (2 * dx**2) + kappa * x[i] / (2 * dx)
    ab2[1, 0] = 1.0
    ab2[1, -1] = 1.0
    rhs2[0] = 0.0
    rhs2[-1] = 0.0
    m = solve_banded((1, 1), ab2, rhs2)
    return p[idx], m[idx]


def p_small_kappa(kappa, K_S, K_T, sigma=1.0):
    L = K_S + K_T
    p0 = K_S / L
    p1 = K_T * K_S * (2 * K_T + K_S) / (3 * sigma**2 * L)
    return p0 + kappa * p1


def metrics(kappa, K_S, K_T, sigma=1.0, c=0.0):
    """Compute per-trade and annualized metrics via ODE."""
    p, tau = p_win_ode(kappa, K_S, K_T, sigma)
    E_gross = p * K_T - (1 - p) * K_S
    E_net = E_gross - 2 * c
    var = p * (K_T - E_gross) ** 2 + (1 - p) * (-K_S - E_gross) ** 2
    sd = np.sqrt(var)
    sharpe_trade = E_net / sd if sd > 0 else 0.0
    freq = 1.0 / max(tau, 1e-9)
    # annualized: N trades/year; with T_year in same time units as tau
    sharpe_ann = E_net / sd * np.sqrt(freq) if sd > 0 else 0.0
    return p, E_gross, E_net, sd, sharpe_trade, tau, freq, sharpe_ann


def main():
    kappa = 0.5
    sigma = 1.0
    L = 2.0  # fixed total container width
    print(f"=== Fixed container width L=K_S+K_T={L}, kappa={kappa}, sigma={sigma} ===")
    print("Vary R=K_T/K_S from 0.2 to 5:")
    print(f"{'R':>5} {'K_S':>5} {'K_T':>5} {'p_win':>7} {'E_gross':>9} {'sd':>7} "
          f"{'Sharpe/t':>9} {'tau':>7} {'freq':>7} {'Sharpe_ann':>11}")
    for R in [0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.25, 1.5, 2.0, 3.0, 5.0]:
        # K_T + K_S = L, K_T/K_S = R => K_S = L/(1+R), K_T = LR/(1+R)
        K_S = L / (1 + R)
        K_T = L - K_S
        p, Eg, En, sd, st, tau, fr, sa = metrics(kappa, K_S, K_T, sigma)
        print(f"{R:>5.2f} {K_S:>5.2f} {K_T:>5.2f} {p*100:>6.2f}% {Eg:>+9.4f} {sd:>7.3f} "
              f"{st:>+9.4f} {tau:>7.3f} {fr:>7.3f} {sa:>+11.4f}")

    print()
    print("=== Same but with per-trade cost c=0.02 (two sides = 0.04) ===")
    print(f"{'R':>5} {'K_S':>5} {'K_T':>5} {'p_win':>7} {'E_net':>9} {'Sharpe/t':>9} {'Sharpe_ann':>11}")
    for R in [0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.25, 1.5, 2.0, 3.0, 5.0]:
        K_S = L / (1 + R)
        K_T = L - K_S
        p, Eg, En, sd, st, tau, fr, sa = metrics(kappa, K_S, K_T, sigma, c=0.02)
        print(f"{R:>5.2f} {K_S:>5.2f} {K_T:>5.2f} {p*100:>6.2f}% {En:>+9.4f} {st:>+9.4f} {sa:>+11.4f}")

    print()
    print("=== Verify small-kappa expansion against ODE at kappa=0.1 ===")
    for K_S, K_T in [(1.0, 0.5), (2.0, 0.5), (1.0, 0.3)]:
        p_ode, _ = p_win_ode(0.1, K_S, K_T)
        p_ap = p_small_kappa(0.1, K_S, K_T)
        print(f"  K_T={K_T} K_S={K_S}: p_ode={p_ode*100:.3f}%  p_approx={p_ap*100:.3f}%")


if __name__ == "__main__":
    main()
