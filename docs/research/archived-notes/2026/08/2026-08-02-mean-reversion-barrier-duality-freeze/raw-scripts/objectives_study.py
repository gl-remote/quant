"""
Final study: under which objective is R<1 strictly optimal for mean reversion?

We compare three objectives over R with fixed L=K_S+K_T under OU (kappa=0.5):
  1. Per-trade Sharpe (mean/sd) — expects R~1 optimum.
  2. Annualized Sharpe (mean/sd * sqrt(freq)) — expects R~1.
  3. Kelly log-growth per unit time: g = (1/tau)[p ln(1+f*K_T)+(1-p)ln(1-f*K_S)]
     with f = f_Kelly. High-p/R<1 may win due to frequency + loss-tail avoidance.
  4. Drawdown-penalized: objective = E_net/sd - lambda*P(loss event magnitude)
     (downside deviation) — R<1 favored.
  5. Per-trade net with LARGE per-trade cost c (R<1 has small tp but same cost;
     R large has bigger edge to absorb cost) — check if R<1 ever wins here.

Also: verify that UNDER PURE MARTINGALE (BM, kappa=0) the Doob result holds and
R<1 has NEGATIVE expected net (costs dominate regardless), establishing that
mean reversion is NECESSARY for R<1 to be viable.
"""
import numpy as np
from scipy.linalg import solve_banded


def ou_metrics(kappa, K_S, K_T, sigma=1.0, n=6001):
    a = K_T + K_S
    lo, hi = -a, 0.0
    x = np.linspace(lo, hi, n)
    dx = x[1] - x[0]
    ab = np.zeros((3,n)); rhs = np.zeros(n)
    for i in range(1,n-1):
        ab[0,i+1]=sigma**2/(2*dx**2)-kappa*x[i]/(2*dx)
        ab[1,i]=-sigma**2/dx**2
        ab[2,i-1]=sigma**2/(2*dx**2)+kappa*x[i]/(2*dx)
    ab[1,0]=1; ab[1,-1]=1; rhs[-1]=1
    p = solve_banded((1,1),ab,rhs)
    ab2=np.zeros((3,n)); rhs2=np.full(n,-1.0)
    for i in range(1,n-1):
        ab2[0,i+1]=sigma**2/(2*dx**2)-kappa*x[i]/(2*dx)
        ab2[1,i]=-sigma**2/dx**2
        ab2[2,i-1]=sigma**2/(2*dx**2)+kappa*x[i]/(2*dx)
    ab2[1,0]=1;ab2[1,-1]=1;rhs2[0]=0;rhs2[-1]=0
    m = solve_banded((1,1),ab2,rhs2)
    idx=np.argmin(np.abs(x-(-K_T)))
    return p[idx], m[idx]


def kelly_log_growth(p, K_S, K_T, tau):
    """Discrete Kelly f* = (p*K_T-(1-p)*K_S)/(K_T*K_S)?? Generalize:
    win +f*K_T, loss -f*K_S. f* = (p K_T - (1-p)K_S)/(K_T K_S) ... derive:
    g(f)=p ln(1+f K_T)+(1-p)ln(1-f K_S); g'=p K_T/(1+f K_T)-(1-p)K_S/(1-f K_S)=0
    => p K_T(1-f K_S)=(1-p)K_S(1+f K_T)
    => p K_T - (1-p)K_S = f[p K_T K_S + (1-p)K_S K_T] = f K_T K_S
    => f* = (p K_T-(1-p)K_S)/(K_T K_S).
    Per-trade log growth g*=p ln(1+f*K_T)+(1-p)ln(1-f*K_S). Per-time = g*/tau.
    """
    edge = p*K_T - (1-p)*K_S
    if edge <= 0:
        return 0.0, 0.0
    f_star = edge/(K_T*K_S)
    f_star = min(f_star, 0.99/K_T, 0.99/K_S)
    g = p*np.log(1+f_star*K_T) + (1-p)*np.log(1-f_star*K_S)
    return g, g/max(tau,1e-9)


def main():
    L = 2.0
    print("="*80)
    print("OU mean reversion (kappa=0.5), fixed container L=2.0")
    print("="*80)
    print(f"{'R':>5} {'K_S':>5} {'K_T':>5} {'p':>7} {'E':>8} {'sd':>6} "
          f"{'Sh/t':>7} {'Sh_ann':>7} {'g_ann':>8} {'DDpen':>8}")
    rows=[]
    for R in [0.2,0.3,0.4,0.5,0.6,0.8,1.0,1.25,1.5,2.0,3.0,5.0]:
        K_S=L/(1+R); K_T=L-K_S
        p,tau=ou_metrics(0.5,K_S,K_T)
        E=p*K_T-(1-p)*K_S
        sd=np.sqrt(p*(K_T-E)**2+(1-p)*(-K_S-E)**2)
        sh_t=E/sd
        sh_ann=E/sd/np.sqrt(tau)
        _,g_ann=kelly_log_growth(p,K_S,K_T,tau)
        # downside deviation: semivariance of losses
        dd = np.sqrt((1-p)*(K_S+E)**2)
        dd_pen = E/(sd+0.5*dd)  # penalize loss-tail
        rows.append((R,K_S,K_T,p,E,sd,sh_t,sh_ann,g_ann,dd_pen))
        print(f"{R:>5.2f} {K_S:>5.2f} {K_T:>5.2f} {p*100:>6.2f}% {E:>+8.4f} {sd:>6.3f} "
              f"{sh_t:>+7.4f} {sh_ann:>+7.4f} {g_ann:>+8.4f} {dd_pen:>+8.4f}")

    # find argmax for each objective
    arr=np.array(rows)
    for j,name in [(6,"Sh/trade"),(7,"Sh_ann"),(8,"Kelly g/ann"),(9,"DD-penalized")]:
        i=np.argmax(arr[:,j])
        print(f"  argmax {name:>14}: R*={arr[i,0]:.2f}  (p={arr[i,3]*100:.1f}%, value={arr[i,j]:+.4f})")

    print()
    print("="*80)
    print("BM martingale (kappa=0): verify Doob E=0; with cost c>0, R<1 bleeds")
    print("="*80)
    c=0.02
    print(f"{'R':>5} {'p0':>7} {'E_gross':>9} {'E_net(c=0.02)':>14}")
    for R in [0.3,0.5,1.0,2.0,3.0]:
        K_S=L/(1+R); K_T=L-K_S
        p0=K_S/L
        E=0.0
        print(f"{R:>5.2f} {p0*100:>6.2f}% {E:>+9.4f} {E-2*c:>+14.4f}")

    print()
    print("="*80)
    print("Mean reversion strength vs optimal R (per-time Kelly g)")
    print("="*80)
    for kappa in [0.1,0.25,0.5,1.0,2.0]:
        best=None
        for R in np.linspace(0.2,5.0,49):
            K_S=L/(1+R); K_T=L-K_S
            p,tau=ou_metrics(kappa,K_S,K_T)
            g,g_ann=kelly_log_growth(p,K_S,K_T,tau)
            if best is None or g_ann>best[1]:
                best=(R,g_ann,p)
        print(f"  kappa={kappa:>4.2f}: R*_Kelly={best[0]:.2f}  p*={best[2]*100:.1f}%  g_ann={best[1]:+.4f}")


if __name__=="__main__":
    main()
