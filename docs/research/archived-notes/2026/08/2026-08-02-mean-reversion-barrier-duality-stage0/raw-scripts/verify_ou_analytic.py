"""
Verify the analytic OU hitting probability and its small-kappa expansion.

Setup (long at deviation):
  OU process dX = -kappa X dt + sigma dW, equilibrium 0.
  Enter at x0 = -K_T (price below equilibrium by K_T).
  Take-profit at 0 (distance K_T, "win"), stop at -(K_T+K_S) (distance K_S, "loss").
  R = K_T/K_S < 1 is the low-payoff/high-winrate regime.

We compute p_win via:
  (1) Monte Carlo
  (2) Numerical solution of the ODE  (sigma^2/2) p'' - kappa x p' = 0, p(-K_T-K_S)=0, p(0)=1
  (3) Small-kappa closed-form:
        p_win = K_S/(K_T+K_S) + (kappa/sigma^2) K_T K_S + O(kappa^2)
      and E_gross = (kappa K_T K_S / sigma^2)(K_T+K_S) + O(kappa^2)
"""
import numpy as np
from scipy.linalg import solve_banded


def p_win_ode(kappa, K_S, K_T, sigma=1.0, n=4001):
    """Solve OU hitting probability ODE on [-(K_T+K_S), 0] via finite differences (tridiagonal)."""
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
    return p[idx]


def p_win_small_kappa(kappa, K_S, K_T, sigma=1.0):
    p0 = K_S / (K_T + K_S)
    return p0 + (kappa / sigma**2) * K_T * K_S


def e_gross(p_win, K_S, K_T):
    return p_win * K_T - (1 - p_win) * K_S


def simulate(kappa, K_S, K_T, sigma=1.0, n_paths=80_000, dt=0.002, T=20.0, seed=0):
    rng = np.random.default_rng(seed)
    x = np.full(n_paths, -K_T, dtype=float)
    alive = np.ones(n_paths, dtype=bool)
    win = np.zeros(n_paths, dtype=bool)
    for _ in range(int(T / dt)):
        idx = np.where(alive)[0]
        if len(idx) == 0:
            break
        xi = x[idx]
        xi = xi + (-kappa * xi) * dt + sigma * rng.standard_normal(len(idx)) * np.sqrt(dt)
        x[idx] = xi
        hit_tp = xi >= 0.0
        hit_sl = xi <= -(K_T + K_S)
        wi = idx[hit_tp]
        li = idx[hit_sl]
        win[wi] = True
        alive[wi] = False
        alive[li] = False
    return win.mean()


def main():
    print(f"{'K_T':>5} {'K_S':>5} {'R':>5} {'kappa':>6} "
          f"{'p0':>6} {'p_mc':>7} {'p_ode':>7} {'p_approx':>9} {'E_approx':>9}")
    for K_S, K_T in [(1.0, 0.5), (2.0, 0.5), (1.0, 0.3)]:
        for kappa in [0.1, 0.25, 0.5, 1.0]:
            p0 = K_S / (K_T + K_S)
            p_mc = simulate(kappa, K_S, K_T, n_paths=80_000)
            p_ode = p_win_ode(kappa, K_S, K_T)
            p_ap = p_win_small_kappa(kappa, K_S, K_T)
            e_ap = e_gross(p_ap, K_S, K_T)
            print(f"{K_T:>5.2f} {K_S:>5.2f} {K_T/K_S:>5.2f} {kappa:>6.2f} "
                  f"{p0:>6.3f} {p_mc*100:>6.2f}% {p_ode*100:>6.2f}% {p_ap*100:>8.2f}% {e_ap:>+9.4f}")
        print()

    # Show E_gross ~ (kappa/sigma^2) K_T K_S (K_T+K_S), the dual of channel B's R(R-1)
    print("=== Duality: E_gross coefficient vs (K_T, K_S) at kappa=0.5, sigma=1 ===")
    print("Channel B (persistent, entry center): E ~ (x^2/3) K_S^3 R(R-1),  >0 needs R>1")
    print("Channel C (mean-rev, entry deviation): E ~ kappa K_T K_S (K_T+K_S), >0 needs R<1+tp-sl geometry")
    for K_S, K_T in [(1.0, 0.5), (2.0, 0.5), (0.5, 0.5), (0.5, 1.0)]:
        p_ode = p_win_ode(0.5, K_S, K_T)
        E = e_gross(p_ode, K_S, K_T)
        print(f"  K_T={K_T:.2f} K_S={K_S:.2f} R={K_T/K_S:.2f}  p_win={p_ode*100:6.2f}%  E_gross={E:+.4f}")


if __name__ == "__main__":
    main()
