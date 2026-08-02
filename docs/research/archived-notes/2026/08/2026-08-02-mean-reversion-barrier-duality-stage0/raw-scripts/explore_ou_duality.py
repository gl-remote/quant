"""
Numerical exploration: when is low-payoff/high-winrate (R<1) optimal?

Key insight (vs when-barrier-shaping channel B):
  - Channel B (trend, persistent, unknown drift sign): entry at center x=0,
    process escapes to +/-theta; asymmetric container with R>1 captures tails.
    E_mix ~ x^2 K_S^3 R(R-1) > 0 only for R>1.
  - DUAL channel (mean reversion, anti-persistent): entry at a DEVIATION,
    equilibrium pulls toward center; place the CLOSE barrier (small distance)
    toward equilibrium (take-profit) and the FAR barrier (large distance)
    against it (stop). Then R = K_T/K_S < 1 and high win rate.

We model OU starting at a displaced entry x0 = -d (long after a dip), equilibrium 0.
  dX = -kappa X dt + sigma dW
  Take-profit at 0 (distance d = K_T), stop at -d-K_S (distance K_S), R=K_T/K_S<1.
Compare with BM (no mean reversion) where Doob gives E=0.
Also compare the SYMMETRIC MIX of long/short entries (both at deviations) to
mirror channel B's direction-agnostic structure.
"""
import numpy as np


def simulate_ou_entry(K_S, K_T, kappa, sigma=1.0, direction=+1,
                      T=10.0, n_paths=200_000, dt=0.0025, seed=0):
    """Enter at deviation. direction=+1 long (price below eq): x0=-K_T, tp=0, sl=-K_T-K_S.
    direction=-1 short is mirror. OU dX=-kappa X dt + sigma dW, equilibrium 0."""
    rng = np.random.default_rng(seed)
    # coordinates: long case. tp at 0 (dist K_T), sl at -(K_T+K_S) (dist K_S)
    x = np.full(n_paths, -K_T, dtype=float)
    if direction == -1:
        x = -x  # start at +K_T, tp=0, sl=K_T+K_S
    alive = np.ones(n_paths, dtype=bool)
    win = np.zeros(n_paths, dtype=bool)
    loss = np.zeros(n_paths, dtype=bool)
    term = np.zeros(n_paths, dtype=float)
    n_steps = int(T / dt)
    for _ in range(n_steps):
        idx = np.where(alive)[0]
        if len(idx) == 0:
            break
        xi = x[idx]
        dW = rng.standard_normal(len(idx)) * np.sqrt(dt)
        xi = xi + (-kappa * xi) * dt + sigma * dW
        x[idx] = xi
        if direction == +1:
            hit_tp = xi >= 0.0
            hit_sl = xi <= -(K_T + K_S)
        else:
            hit_tp = xi <= 0.0
            hit_sl = xi >= (K_T + K_S)
        wi = idx[hit_tp]
        li = idx[hit_sl]
        win[wi] = True
        loss[li] = True
        alive[wi] = False
        alive[li] = False
        term[alive] = x[alive]
    P_win = win.mean()
    P_loss = loss.mean()
    P_time = 1 - P_win - P_loss
    # payoff: win +K_T, loss -K_S, time exit at terminal value (for long, x+K_T relative to entry -K_T?)
    # Use log-price coordinate relative to entry: payoff = x - x0 for long
    x0 = -K_T if direction == +1 else K_T
    payoff = np.where(win, K_T, np.where(loss, -K_S, (x - x0) * direction))
    return P_win, P_loss, P_time, payoff.mean()


def main():
    print("=== OU mean-reversion entry at deviation (long+short mixed) ===")
    print(f"{'K_S':>5} {'K_T':>5} {'R':>5} {'kappa':>6} "
          f"{'P_win':>7} {'P_loss':>7} {'P_time':>7} {'E_gross':>9}")
    # R<1 cases: K_T (tp distance, toward eq) small, K_S (sl, away) large
    for K_S, K_T in [(2.0, 0.5), (1.5, 0.5), (1.0, 0.5), (0.5, 0.5),
                     (0.5, 1.0), (0.5, 1.5), (0.5, 2.0)]:
        for kappa in [0.0, 2.0]:
            pw_l, pl_l, pt_l, e_l = simulate_ou_entry(
                K_S, K_T, kappa, direction=+1, n_paths=200_000)
            pw_s, pl_s, pt_s, e_s = simulate_ou_entry(
                K_S, K_T, kappa, direction=-1, n_paths=200_000, seed=1)
            P_win = 0.5 * (pw_l + pw_s)
            P_loss = 0.5 * (pl_l + pl_s)
            P_time = 0.5 * (pt_l + pt_s)
            E = 0.5 * (e_l + e_s)
            proc = "BM" if kappa == 0.0 else "OU"
            print(f"{K_S:>5.1f} {K_T:>5.1f} {K_T/K_S:>5.2f} {kappa:>6.1f} "
                  f"{P_win*100:>6.2f}% {P_loss*100:>6.2f}% {P_time*100:>6.2f}% {E:>+9.4f}  {proc}")
        print()

    print("=== R=0.5 (K_T=0.5 tp toward eq, K_S=1.0 sl away), varying kappa ===")
    for kappa in [0.0, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0]:
        pw_l, pl_l, pt_l, e_l = simulate_ou_entry(
            1.0, 0.5, kappa, direction=+1, n_paths=100_000)
        pw_s, pl_s, pt_s, e_s = simulate_ou_entry(
            1.0, 0.5, kappa, direction=-1, n_paths=100_000, seed=1)
        P_win = 0.5 * (pw_l + pw_s)
        E = 0.5 * (e_l + e_s)
        print(f"kappa={kappa:>5.2f}  P_win={P_win*100:>6.2f}%  E_gross={E:>+8.4f}")


if __name__ == "__main__":
    main()
