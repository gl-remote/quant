"""
Verify the mathematical statement: 'reversion faster than noise reaches stop'.

Two timescales:
  T_rev ~ 1/kappa
  T_diff ~ K_S^2/sigma^2
Dimensionless group Pe = kappa*K_S^2/sigma^2.

Exact loss probability from OU hitting ODE:
  1 - p_win = int_{-K_T}^{0} e^{k u^2/s^2} du / int_{-L}^{0} e^{k u^2/s^2} du,  L=K_T+K_S

Large-kappa Laplace endpoint asymptotic:
  1-p ~ (L/K_T) * exp(-kappa*(L^2 - K_T^2)/sigma^2)
      = (L/K_T) * exp(-kappa*K_S*(2K_T+K_S)/sigma^2)
"""
import numpy as np
from scipy.linalg import solve_banded


def pwin_ode(kappa, K_S, K_T, sigma=1.0, n=8001):
    a = K_T + K_S
    lo, hi = -a, 0.0
    x = np.linspace(lo, hi, n)
    dx = x[1] - x[0]
    ab = np.zeros((3, n)); rhs = np.zeros(n)
    for i in range(1, n-1):
        ab[0, i+1] = sigma**2/(2*dx**2) - kappa*x[i]/(2*dx)
        ab[1, i]   = -sigma**2/dx**2
        ab[2, i-1] = sigma**2/(2*dx**2) + kappa*x[i]/(2*dx)
    ab[1, 0] = 1; ab[1, -1] = 1; rhs[-1] = 1
    p = solve_banded((1,1), ab, rhs)
    idx = np.argmin(np.abs(x - (-K_T)))
    return p[idx]


def loss_asym(kappa, K_S, K_T, sigma=1.0):
    L = K_T + K_S
    return (L/K_T) * np.exp(-kappa*(L**2 - K_T**2)/sigma**2)


def main():
    print("Verify Pe = kappa*K_S^2/sigma^2 controls p_win->1")
    print(f"{'kappa':>6} {'K_S':>5} {'K_T':>5} {'R':>5} {'Pe':>6} "
          f"{'p_win(ode)':>11} {'1-p':>10} {'1-p(asym)':>11}")
    # R=0.5, K_S=1.0, K_T=0.5, L=1.5
    K_S, K_T = 1.0, 0.5
    for kappa in [0.1, 0.25, 0.5, 1.0, 2.0, 4.0]:
        pw = pwin_ode(kappa, K_S, K_T)
        Pe = kappa*K_S**2
        loss_exact = 1-pw
        loss_a = loss_asym(kappa, K_S, K_T)
        print(f"{kappa:>6.2f} {K_S:>5.2f} {K_T:>5.2f} {K_T/K_S:>5.2f} {Pe:>6.2f} "
              f"{pw*100:>10.3f}% {loss_exact:>10.5f} {loss_a:>11.5f}")

    print()
    print("Interpretation:")
    print("  Pe << 1: noise dominates, p_win ~ martingale baseline K_S/L (no reversion edge)")
    print("  Pe ~ 1:  crossover, drift starts to matter")
    print("  Pe >> 1: drift dominates, loss prob decays ~ exp(-kappa*K_S*(2K_T+K_S)/sigma^2)")
    print()
    print("At R*<1 operating points (sigma=1):")
    print(f"{'kappa':>6} {'R*':>5} {'K_S':>5} {'Pe':>6} {'p_win':>7} {'half-life':>10} {'T_diff':>8}")
    for kappa, R in [(0.5, 1.10), (1.0, 0.42), (1.5, 0.30), (2.0, 0.25), (3.0, 0.20)]:
        L = 2.0
        KS = L/(1+R); KT = L-KS
        pw = pwin_ode(kappa, KS, KT)
        Pe = kappa*KS**2
        T_rev = 1/kappa
        T_diff = KS**2
        print(f"{kappa:>6.2f} {R:>5.2f} {KS:>5.2f} {Pe:>6.2f} {pw*100:>6.1f}% "
              f"{T_rev:>10.2f} {T_diff:>8.2f}")


if __name__ == "__main__":
    main()
