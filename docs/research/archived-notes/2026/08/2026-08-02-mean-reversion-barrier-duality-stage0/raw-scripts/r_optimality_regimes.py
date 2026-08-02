"""
Study when R<1 is strictly optimal (not just viable) under mean reversion.

Three constraint regimes that push optimum toward R<1:
  (A) Fixed structural stop K_S, vary take-profit K_T (reversion target).
  (B) Per-unit-TIME holding cost (financing/inventory) rather than per-trade cost.
  (C) fBm anti-persistence H<1/2: short-interval returns negatively correlated,
      so small tp (fast mean reversion) is hit before adverse excursion compounds.

We use OU ODE solver for (A) and (B), and a Monte Carlo fBm simulator for (C).
"""
import numpy as np
from scipy.linalg import solve_banded


def ou_metrics(kappa, K_S, K_T, sigma=1.0, c_per_trade=0.0, c_per_time=0.0, n=6001):
    """Returns p_win, E_net, sd, Sharpe/trade, E[tau], Sharpe_ann under OU.
    c_per_time is a cost rate per unit time (e.g. financing) charged on notional."""
    a = K_T + K_S
    lo, hi = -a, 0.0
    x = np.linspace(lo, hi, n)
    dx = x[1] - x[0]
    ab = np.zeros((3, n)); rhs = np.zeros(n)
    for i in range(1, n - 1):
        ab[0, i+1] = sigma**2/(2*dx**2) - kappa*x[i]/(2*dx)
        ab[1, i] = -sigma**2/dx**2
        ab[2, i-1] = sigma**2/(2*dx**2) + kappa*x[i]/(2*dx)
    ab[1, 0] = 1.0; ab[1, -1] = 1.0; rhs[-1] = 1.0
    p = solve_banded((1,1), ab, rhs)
    # mean exit time
    ab2 = np.zeros((3, n)); rhs2 = np.full(n, -1.0)
    for i in range(1, n - 1):
        ab2[0, i+1] = sigma**2/(2*dx**2) - kappa*x[i]/(2*dx)
        ab2[1, i] = -sigma**2/dx**2
        ab2[2, i-1] = sigma**2/(2*dx**2) + kappa*x[i]/(2*dx)
    ab2[1, 0] = 1.0; ab2[1, -1] = 1.0; rhs2[0] = 0.0; rhs2[-1] = 0.0
    m = solve_banded((1,1), ab2, rhs2)
    idx = np.argmin(np.abs(x - (-K_T)))
    pw = p[idx]; tau = m[idx]
    E_gross = pw*K_T - (1-pw)*K_S
    E_net = E_gross - 2*c_per_trade - c_per_time*tau
    var = pw*(K_T-E_gross)**2 + (1-pw)*(-K_S-E_gross)**2
    sd = np.sqrt(var)
    st = E_net/sd if sd > 0 else 0.0
    sa = E_net/sd*np.sqrt(1.0/max(tau,1e-9)) if sd>0 else 0.0
    return pw, E_net, sd, st, tau, sa


def study_fixed_stop():
    print("="*70)
    print("(A) FIXED STRUCTURAL STOP K_S=1.5, vary K_T (take-profit = reversion distance)")
    print("="*70)
    kappa = 0.5
    print(f"{'R':>5} {'K_S':>5} {'K_T':>5} {'p_win':>7} {'E_net':>8} {'sd':>6} "
          f"{'Sh/trade':>9} {'tau':>6} {'Sh_ann':>8}")
    for K_T in [0.3, 0.4, 0.5, 0.7, 0.9, 1.2, 1.5, 2.0, 3.0]:
        K_S = 1.5
        R = K_T/K_S
        pw, En, sd, st, tau, sa = ou_metrics(kappa, K_S, K_T)
        print(f"{R:>5.2f} {K_S:>5.2f} {K_T:>5.2f} {pw*100:>6.2f}% {En:>+8.4f} {sd:>6.3f} "
              f"{st:>+9.4f} {tau:>6.3f} {sa:>+8.4f}")


def study_time_cost():
    print()
    print("="*70)
    print("(B) PER-TIME HOLDING COST c_per_time=0.15 (financing/inventory), fixed L=2")
    print("="*70)
    kappa = 0.5
    L = 2.0
    print(f"{'R':>5} {'K_S':>5} {'K_T':>5} {'p_win':>7} {'E_net':>8} "
          f"{'Sh/trade':>9} {'tau':>6} {'cost_t':>7} {'Sh_ann':>8}")
    for R in [0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.25, 1.5, 2.0, 3.0, 5.0]:
        K_S = L/(1+R); K_T = L-K_S
        pw, En, sd, st, tau, sa = ou_metrics(kappa, K_S, K_T, c_per_time=0.15)
        print(f"{R:>5.2f} {K_S:>5.2f} {K_T:>5.2f} {pw*100:>6.2f}% {En:>+8.4f} "
              f"{st:>+9.4f} {tau:>6.3f} {0.15*tau:>7.4f} {sa:>+8.4f}")


def study_fbm_antipersistent():
    print()
    print("="*70)
    print("(C) fBm ANTI-PERSISTENT H<1/2: short-interval negative autocorrelation")
    print("Entry at deviation, tp toward center, sl away. Compare H=0.3 vs H=0.5 vs H=0.7.")
    print("="*70)
    try:
        from fbm import fgn
    except ImportError:
        print("(fbm package not available; simulating via AR(1) proxy)")
        return study_ar1_proxy()
    L = 2.0
    n_paths = 50000
    n_steps = 2000
    dt = 0.005
    for H in [0.3, 0.5, 0.7]:
        print(f"\n--- H={H} ---")
        print(f"{'R':>5} {'K_S':>5} {'K_T':>5} {'p_win':>7} {'E_gross':>9} {'sd':>6} {'Sh/trade':>9}")
        for R in [0.3, 0.5, 0.8, 1.0, 1.5, 2.0, 3.0]:
            K_S = L/(1+R); K_T = L-K_S
            # generate fBm increments (scaled so per-step sd=1*sqrt(dt) equivalent)
            inc = fgn(n=n_steps, hurst=H, length=1.0) * np.sqrt(n_steps)
            # simulate
            rng = np.random.default_rng(0)
            wins = 0; losses = 0; payoffs = []
            for _ in range(n_paths):
                x = -K_T
                # use a random segment shift of increments (stationary-ish approximation)
                shift = rng.integers(0, n_steps-1)
                for k in range(n_steps):
                    dW = inc[(shift+k) % n_steps] * np.sqrt(dt)
                    x = x + dW  # fBm increment (mean-zero; anti-persistence in increments)
                    if x >= 0:
                        wins += 1; payoffs.append(K_T); break
                    if x <= -(K_T+K_S):
                        losses += 1; payoffs.append(-K_S); break
                else:
                    payoffs.append(x + K_T)
            pw = wins/n_paths
            arr = np.array(payoffs)
            E = arr.mean(); sd = arr.std()
            print(f"{R:>5.2f} {K_S:>5.2f} {K_T:>5.2f} {pw*100:>6.2f}% {E:>+9.4f} {sd:>6.3f} {E/sd:>+9.4f}")


def study_ar1_proxy():
    """AR(1) proxy for anti-persistence: increment dX = -phi*X_prev + noise (mean-reverting).
    Actually that's OU. For fBm H<1/2 proxy use negatively-correlated increments."""
    print("Using AR(1) negatively-correlated increments as H<1/2 proxy.")
    L = 2.0
    n_paths = 100000
    n_steps = 2000
    dt = 0.005
    for rho in [-0.3, 0.0, 0.3]:
        print(f"\n--- increment AR(1) rho={rho} (rho<0 ~ H<1/2 anti-persistent) ---")
        print(f"{'R':>5} {'K_S':>5} {'K_T':>5} {'p_win':>7} {'E_gross':>9} {'Sh/trade':>9}")
        for R in [0.3, 0.5, 0.8, 1.0, 1.5, 2.0, 3.0]:
            K_S = L/(1+R); K_T = L-K_S
            rng = np.random.default_rng(0)
            x = np.full(n_paths, -K_T)
            alive = np.ones(n_paths, dtype=bool)
            win = np.zeros(n_paths, dtype=bool)
            prev_inc = np.zeros(n_paths)
            for k in range(n_steps):
                idx = np.where(alive)[0]
                if len(idx)==0: break
                z = rng.standard_normal(len(idx))*np.sqrt(dt)
                inc = rho*prev_inc[idx] + np.sqrt(1-rho**2)*z
                prev_inc[idx] = inc
                xi = x[idx] + inc
                x[idx] = xi
                wt = xi >= 0; ls = xi <= -(K_T+K_S)
                wi = idx[wt]; li = idx[ls]
                win[wi]=True; alive[wi]=False; alive[li]=False
            pw = win.mean()
            # payoff
            payoff = np.where(win, K_T, np.where(~alive, -K_S, x+K_T))
            E = payoff.mean(); sd = payoff.std()
            print(f"{R:>5.2f} {K_S:>5.2f} {K_T:>5.2f} {pw*100:>6.2f}% {E:>+9.4f} {E/sd:>+9.4f}")


if __name__ == "__main__":
    study_fixed_stop()
    study_time_cost()
    study_fbm_antipersistent()
