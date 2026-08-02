"""
Honest stress test: does the R<1 optimal regime survive real-market realism?

Two checks the synthetic-OU model hid:
  (1) Cost breakeven: at the R*<1 operating point, how large is gross edge vs
      realistic round-trip cost (in ATR units)?
  (2) Regime risk: real mean reversion is NOT constant-kappa OU. With probability
      q the process switches to random walk (kappa=0) or trend (kappa<0).
      The R<1 container has a WIDE stop (K_S large) -> "picking up pennies".
      Compute mixture E_gross and loss-tail when the model is wrong.
"""
import numpy as np
from scipy.linalg import solve_banded


def ou_metrics(kappa, K_S, K_T, sigma=1.0, n=8001):
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
    p = solve_banded((1, 1), ab, rhs)
    idx = np.argmin(np.abs(x - (-K_T)))
    return p[idx]


def best_R_for_kappa(kappa, L=2.0):
    Rs = np.concatenate([np.linspace(0.15, 1.0, 40), np.linspace(1.0, 4.0, 31)])
    best = None
    for R in Rs:
        K_S = L/(1+R); K_T = L-K_S
        pw = ou_metrics(kappa, K_S, K_T)
        E = pw*K_T - (1-pw)*K_S
        sd = np.sqrt(pw*(K_T-E)**2 + (1-pw)*(-K_S-E)**2)
        # use per-trade Sharpe as objective (freq comparable within fixed L)
        v = E/sd if sd > 0 else 0
        if best is None or v > best[0]:
            best = (v, R, K_S, K_T, pw, E, sd)
    return best


def mixture_eval(R, K_S, K_T, kappa_good, kappa_bad, q):
    """Strategy chosen assuming kappa_good; realized is good w.p. 1-q else bad."""
    pg = ou_metrics(kappa_good, K_S, K_T)
    pb = ou_metrics(kappa_bad, K_S, K_T)
    p = (1-q)*pg + q*pb
    E = p*K_T - (1-p)*K_S
    # loss probability in the bad regime
    Ploss_bad = 1 - pb
    return pg, pb, p, E, Ploss_bad


def main():
    L = 2.0
    print("="*78)
    print("(1) R* per kappa and cost breakeven (gross edge / 2 = max tolerable 1-side cost)")
    print("="*78)
    print(f"{'kappa':>6} {'R*':>5} {'K_T':>5} {'K_S':>5} {'p':>6} "
          f"{'E_gross':>8} {'c_be(1-side)':>12} {'note':>20}")
    for kappa in [0.5, 1.0, 1.5, 2.0, 3.0, 5.0]:
        v, R, KS, KT, pw, E, sd = best_R_for_kappa(kappa, L)
        c_be = E/2.0
        note = ""
        if kappa >= 1.0:
            note = "<-- R<1 regime"
        print(f"{kappa:>6.2f} {R:>5.2f} {KT:>5.2f} {KS:>5.2f} {pw*100:>5.1f}% "
              f"{E:>+8.3f} {c_be:>12.3f} {note:>20}")
    print()
    print("Realistic 1-side directional cost (commission+slippage, ATR):")
    print("  liquid index futures ~0.03-0.08;  retail commodity ~0.1-0.25;  illiquid ~0.3+")
    print("  => R<1 edge is cost-fragile except at kappa>=2 (very fast reversion).")

    print()
    print("="*78)
    print("(2) Regime risk: choose R* for kappa_good, but realized kappa_bad with prob q")
    print("="*78)
    for kappa_good in [1.0, 2.0, 3.0]:
        v, R, KS, KT, pw, E, sd = best_R_for_kappa(kappa_good, L)
        print(f"\n-- assumed kappa={kappa_good}: R*={R:.2f} (K_T={KT:.2f}, K_S={KS:.2f}), "
              f"good-regime p={pw*100:.1f}% E={E:+.3f} --")
        print(f"{'q(bad)':>7} {'kappa_bad':>10} {'p_mix':>7} {'E_mix':>8} {'P_loss|bad':>10} {'verdict':>20}")
        for q in [0.05, 0.10, 0.20]:
            for kb in [0.0, -0.5]:
                pg, pb, pmix, Emix, Plb = mixture_eval(R, KS, KT, kappa_good, kb, q)
                verdict = "OK" if Emix > 0 else "BLOWS UP"
                print(f"{q:>7.2f} {kb:>10.1f} {pmix*100:>6.1f}% {Emix:>+8.3f} "
                      f"{Plb*100:>9.1f}% {verdict:>20}")


if __name__ == "__main__":
    main()
