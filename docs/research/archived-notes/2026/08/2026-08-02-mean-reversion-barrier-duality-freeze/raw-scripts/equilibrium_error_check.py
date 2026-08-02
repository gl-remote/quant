"""
The real killer: equilibrium estimation error.

The OU model assumes equilibrium 0 is KNOWN. In reality you estimate theta (VWAP/MA/POC),
and it's wrong by epsilon. The strategy enters at x0=-KTP believing eq=0, but true eq
is offset by delta (delta>0 means true eq is ABOVE 0, favorable; delta<0 means below,
you're catching a falling knife / the "reversion target" doesn't exist).

Also: bad-regime DRAWDOWN profile. Even if mixture E>0, the rare wide-stop losses
produce steamroller drawdowns. Compute loss distribution + Kelly growth.
"""
import numpy as np
from scipy.linalg import solve_banded


def pwin(kappa, K_S, K_T, x0_factor=1.0, sigma=1.0, eq_offset=0.0, n=8001):
    """OU dX=-kappa(X-eq_offset)dt + sigma dW. Container: win at eq_offset,
    loss at eq_offset-(K_T+K_S). Entry at x0 = -K_T*x0_factor + eq_offset.
    Shift coordinates Y=X-eq_offset -> dY=-kappa Y dt + sigma dW, same as before.
    But entry is at Y0 = -K_T*x0_factor (misestimated: you TARGET K_T but actually
    entered at a different deviation).
    """
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
    Y0 = -K_T * x0_factor
    idx = np.argmin(np.abs(x - Y0))
    return p[idx]


def main():
    L = 2.0
    print("="*80)
    print("Equilibrium / entry misestimation: choose R* for kappa, but true entry")
    print("deviation differs from K_T (you think tp is K_T away, actually not).")
    print("x0_factor<1 means you entered CLOSER to eq than thought (smaller actual tp);")
    print("x0_factor>1 means FARTHER (price kept moving away: falling knife).")
    print("="*80)
    for kappa in [1.0, 2.0]:
        # R* for this kappa (per-trade Sharpe)
        Rs = np.concatenate([np.linspace(0.2, 1.0, 41), np.linspace(1.0, 3.0, 21)])
        best = None
        for R in Rs:
            KS = L/(1+R); KT = L-KS
            pw = pwin(kappa, KS, KT)
            E = pw*KT-(1-pw)*KS
            sd = np.sqrt(pw*(KT-E)**2+(1-pw)*(-KS-E)**2)
            v = E/sd
            if best is None or v > best[0]:
                best = (v, R, KS, KT)
        _, R, KS, KT = best
        print(f"\n-- kappa={kappa}, R*={R:.2f} (K_T={KT:.2f}, K_S={KS:.2f}) --")
        print(f"{'x0_factor':>10} {'actual_dev':>11} {'p_win':>7} {'E_gross':>9} {'verdict':>12}")
        for f in [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]:
            pw = pwin(kappa, KS, KT, x0_factor=f)
            E = pw*KT-(1-pw)*KS
            verdict = "edge" if E > 0 else "BREAKS"
            print(f"{f:>10.2f} {-KT*f:>11.2f} {pw*100:>6.1f}% {E:>+9.3f} {verdict:>12}")

    print()
    print("="*80)
    print("Steamroller profile: good kappa=2 with R*=0.61, q=10% bad (kappa=0).")
    print("Per-trade distribution and Kelly log-growth under the mixture.")
    print("="*80)
    kappa, R, KS, KT = 2.0, 0.61, 1.24, 0.76
    pg = pwin(kappa, KS, KT)
    pb = pwin(0.0, KS, KT)
    q = 0.10
    print(f"Good regime: P_win={pg*100:.1f}%, win +{KT}, loss -{KS}")
    print(f"Bad regime:  P_win={pb*100:.1f}%, win +{KT}, loss -{KS}")
    # mixture outcomes
    p_win_g = (1-q)*pg
    p_win_b = q*pb
    p_loss_g = (1-q)*(1-pg)
    p_loss_b = q*(1-pb)
    print(f"\nMixture (q={q}):")
    print(f"  P(win in good) = {p_win_g*100:.2f}%   +{KT}")
    print(f"  P(win in bad)  = {p_win_b*100:.2f}%   +{KT}")
    print(f"  P(loss in good)= {p_loss_g*100:.2f}%   -{KS}")
    print(f"  P(loss in bad) = {p_loss_b*100:.2f}%   -{KS}  <-- steamroller")
    E = p_win_g*KT + p_win_b*KT - p_loss_g*KS - p_loss_b*KS
    print(f"  E_gross = {E:+.3f}")
    # Kelly: outcomes +f*KT (prob pw) or -f*KS (prob pl)
    pw = p_win_g + p_win_b
    pl = 1 - pw
    f_kelly = (pw*KT - pl*KS)/(KT*KS)
    print(f"  Kelly f* = {f_kelly:.3f}  (edge={pw*KT-pl*KS:+.3f})")
    if f_kelly > 0:
        g = pw*np.log(1+f_kelly*KT) + pl*np.log(1-f_kelly*KS)
        print(f"  log-growth/trade at f* = {g:+.4f}")
        # half Kelly for robustness
        fh = f_kelly/2
        gh = pw*np.log(1+fh*KT) + pl*np.log(1-fh*KS)
        print(f"  half-Kelly log-growth = {gh:+.4f}")


if __name__ == "__main__":
    main()
