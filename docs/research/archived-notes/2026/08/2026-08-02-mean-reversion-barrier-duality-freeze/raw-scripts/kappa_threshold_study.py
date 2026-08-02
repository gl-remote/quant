"""
Pin down: at what mean-reversion strength kappa does optimal R cross below 1?
Uses per-time Kelly log-growth and annualized Sharpe objectives.
Finer R grid + larger kappa range. Also includes fixed-tight-stop regime.
"""
import numpy as np
from scipy.linalg import solve_banded


def ou_metrics(kappa, K_S, K_T, sigma=1.0, n=8001):
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


def kelly_g_ann(p, K_S, K_T, tau):
    edge = p*K_T-(1-p)*K_S
    if edge <= 0: return 0.0
    f = min(edge/(K_T*K_S), 0.99/K_T, 0.99/K_S)
    g = p*np.log(1+f*K_T)+(1-p)*np.log(1-f*K_S)
    return g/max(tau,1e-9)


def best_R(kappa, objective, L=2.0):
    Rs = np.concatenate([np.linspace(0.15,1.0,35), np.linspace(1.0,4.0,31)])
    best=None
    for R in Rs:
        K_S=L/(1+R); K_T=L-K_S
        p,tau=ou_metrics(kappa,K_S,K_T)
        E=p*K_T-(1-p)*K_S
        sd=np.sqrt(p*(K_T-E)**2+(1-p)*(-K_S-E)**2)
        if objective=="sharpe_ann":
            v = E/sd/np.sqrt(tau)
        elif objective=="kelly_ann":
            v = kelly_g_ann(p,K_S,K_T,tau)
        elif objective=="sharpe_trade":
            v = E/sd
        if best is None or v>best[1]:
            best=(R,v,p,K_S,K_T,tau)
    return best


def main():
    print("Fixed container L=2.0. R* that maximizes each objective, vs kappa:")
    print(f"{'kappa':>6} {'R*_Sh/t':>9} {'p':>6} {'R*_ShAnn':>9} {'p':>6} {'R*_Kelly':>9} {'p':>6}")
    for kappa in [0.1,0.25,0.5,1.0,1.5,2.0,3.0,5.0,8.0]:
        b1=best_R(kappa,"sharpe_trade")
        b2=best_R(kappa,"sharpe_ann")
        b3=best_R(kappa,"kelly_ann")
        print(f"{kappa:>6.2f} {b1[0]:>9.2f} {b1[2]*100:>5.1f}% {b2[0]:>9.2f} {b2[2]*100:>5.1f}% {b3[0]:>9.2f} {b3[2]*100:>5.1f}%")

    print()
    print("Interpretation:")
    print(" - Weak mean reversion (small kappa): large R* (let winners run, low winrate),")
    print("   because the pull toward equilibrium is slow; you need wide TP to be paid for waiting.")
    print(" - Strong mean reversion (large kappa): R* < 1 (fast snap-back, high winrate),")
    print("   because equilibrium is reached quickly; wide TP just adds adverse-excursion risk.")


if __name__=="__main__":
    main()
