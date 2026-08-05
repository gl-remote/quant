"""
用塑形理论的市场强度 s = ν/σ 替代绝对涨幅 pre100，检验哪个才是放量反转的真正驱动。
- s_pre = mean(pre100 lr) / std(pre100 lr)（前 100 根 bar per-bar Sharpe）
- 同时扫描 s_pre 和 pre100 两个维度的分位，对比：
  1) 固定 s 分位变 pre100
  2) 固定 pre100 分位变 s
- 算 spike vs baseline 的 Δr^100
- N=20 H=100 z0=1.5，全品种
- baseline: |z|<0.5 且与 spike 处于同 s/pre 分位桶
"""
from __future__ import annotations
import sys, math
from pathlib import Path
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))
from workspace.common.symbol_utils import extract_contract_prefix
from workspace.data.output_paths import market_csv_dir

N = 20; H = 100; LOOKBACK = 100
N_BOOT = 1500


def load(p):
    d = pd.read_csv(p)
    d["datetime"] = pd.to_datetime(d["datetime"])
    d = d.sort_values("datetime").reset_index(drop=True)
    d["lr"] = np.log(d.close).diff()
    v, h = d.volume, d.datetime.dt.hour
    mu = v.groupby(h).shift(1).groupby(h).transform(lambda s: s.rolling(N,min_periods=N).mean())
    sd = v.groupby(h).shift(1).groupby(h).transform(lambda s: s.rolling(N,min_periods=N).std(ddof=1))
    d["z"] = (v - mu)/sd
    return d


def build():
    recs = []
    for p in sorted(market_csv_dir().glob("*.1h.csv")):
        try: head = pd.read_csv(p, usecols=["datetime"])
        except: continue
        if len(head) < 420: continue
        sym = p.name.split(".tqsdk.1h.csv")[0]
        pfx = extract_contract_prefix(sym) or ""
        d = load(p)
        r = d.lr.to_numpy(); z = d.z.to_numpy(); n = len(d)
        for t in range(N+H+LOOKBACK+1, n-H):
            zv = z[t]
            if not math.isfinite(zv): continue
            pre = r[t-LOOKBACK:t]
            post = r[t+1:t+1+H]
            if not (np.all(np.isfinite(pre)) and np.all(np.isfinite(post))): continue
            mu = pre.mean()
            sd = pre.std(ddof=1)
            s_pre = mu / sd if sd > 0 else np.nan
            if not math.isfinite(s_pre): continue
            if zv >= 1.5: grp = "spike"
            elif abs(zv) < 0.5: grp = "base"
            else: continue
            recs.append({
                "sym": sym, "pfx": pfx, "t": t,
                "z": float(zv), "grp": grp,
                "pre_cum": float(pre.sum()),
                "pre_mu": float(mu), "pre_sigma": float(sd),
                "s_pre": float(s_pre),
                "rH": float(post.sum()),
            })
    return pd.DataFrame(recs)


def cid(df):
    keys = sorted({(s,t) for s,t in zip(df.sym,df.t)})
    km = {k:i for i,k in enumerate(keys)}
    return np.array([km[(s,t)] for s,t in zip(df.sym,df.t)], dtype=np.int32)


def boot(sp, bs, seed=42):
    def bm(v,c,rng):
        nc=int(c.max())+1
        sums=np.bincount(c,weights=v,minlength=nc)
        cnt=np.bincount(c,minlength=nc).astype(np.float64)
        idx=rng.integers(0,nc,size=(N_BOOT,nc))
        return sums[idx].sum(axis=1)/cnt[idx].sum(axis=1)
    cs,cb=cid(sp),cid(bs)
    rng1=np.random.default_rng(seed); rng2=np.random.default_rng(seed+1)
    d=bm(sp.rH.to_numpy(),cs,rng1)-bm(bs.rH.to_numpy(),cb,rng2)
    p=float(min(1,2*min((d<=0).mean(),(d>=0).mean())))
    return float(sp.rH.mean()-bs.rH.mean()), float(np.quantile(d,.025)), float(np.quantile(d,.975)), p, len(sp)


def main():
    out = Path("/Users/gaolei/Documents/src/quant/project_data/research/volume-spike-regime-shift")
    df = build()
    print(f"events: {len(df)}, spike={(df.grp=='spike').sum()}, base={(df.grp=='base').sum()}")

    # 全样本 s_pre / pre_cum 分位切点（基于 spike 组，也用于 base）
    sp = df[df.grp=="spike"].copy()
    bs = df[df.grp=="base"].copy()
    print(f"\ns_pre: spike mean={sp.s_pre.mean():+.4f} median={sp.s_pre.median():+.4f}")
    print(f"pre_cum: spike mean={sp.pre_cum.mean():+.4f} median={sp.pre_cum.median():+.4f}")
    print(f"corr(s_pre, pre_cum) in spike: {sp.s_pre.corr(sp.pre_cum):.3f}")

    # ---- 按 s_pre 五分位 ----
    print("\n=== 按 s_pre 五分位（市场强度） ===")
    print(f"{'s_q':>4} {'s_range':>20} {'n_s':>5} {'ΔrH':>9} {'CI':>22} {'p':>6} {'%neg':>6}")
    sp["s_q"] = pd.qcut(sp.s_pre, 5, labels=False, duplicates="drop")
    for q in sorted(sp.s_q.dropna().unique()):
        sub = sp[sp.s_q==q]
        # baseline 同 s 桶：用整个 df 在该 s 范围内的 base
        lo, hi = sub.s_pre.min(), sub.s_pre.max()
        bsub = bs[(bs.s_pre>=lo)&(bs.s_pre<=hi)]
        if len(sub)<10 or len(bsub)<30: continue
        d,lo_,hi_,p,_ = boot(sub, bsub, seed=100+int(q))
        print(f"{int(q):>4} [{lo:+.3f},{hi:+.3f}] {len(sub):>5} {d:>+9.4f} [{lo_:+.4f},{hi_:+.4f}] {p:>6.3f} {(sub.rH<0).mean():>6.1%}")

    # ---- 按 pre_cum 五分位 ----
    print("\n=== 按 pre_cum 五分位（绝对涨幅）===")
    print(f"{'p_q':>4} {'pre_range':>20} {'n_s':>5} {'ΔrH':>9} {'CI':>22} {'p':>6} {'%neg':>6}")
    sp["p_q"] = pd.qcut(sp.pre_cum, 5, labels=False, duplicates="drop")
    for q in sorted(sp.p_q.dropna().unique()):
        sub = sp[sp.p_q==q]
        lo, hi = sub.pre_cum.min(), sub.pre_cum.max()
        bsub = bs[(bs.pre_cum>=lo)&(bs.pre_cum<=hi)]
        if len(sub)<10 or len(bsub)<30: continue
        d,lo_,hi_,p,_ = boot(sub, bsub, seed=200+int(q))
        print(f"{int(q):>4} [{lo*100:+.1f}%,{hi*100:+.1f}%] {len(sub):>5} {d:>+9.4f} [{lo_:+.4f},{hi_:+.4f}] {p:>6.3f} {(sub.rH<0).mean():>6.1%}")

    # ---- 二维：s_pre 三分位 × pre_cum 三分位 ----
    print("\n=== 二维 s_pre × pre_cum 三分位（ΔrH）===")
    sp["s3"] = pd.qcut(sp.s_pre, 3, labels=["S-","S0","S+"], duplicates="drop")
    sp["p3"] = pd.qcut(sp.pre_cum, 3, labels=["P-","P0","P+"], duplicates="drop")
    bs["s3"] = pd.qcut(bs.s_pre, 3, labels=["S-","S0","S+"], duplicates="drop")
    bs["p3"] = pd.qcut(bs.pre_cum, 3, labels=["P-","P0","P+"], duplicates="drop")
    grid = []
    print(f"{'':>6}", end="")
    for pl in ["P-","P0","P+"]: print(f" {pl:>20}", end="")
    print()
    for sl in ["S-","S0","S+"]:
        print(f"{sl:>6}", end="")
        for pl in ["P-","P0","P+"]:
            sub = sp[(sp.s3==sl)&(sp.p3==pl)]
            bsub = bs[(bs.s3==sl)&(bs.p3==pl)]
            if len(sub)<10 or len(bsub)<30:
                print(f" {'n='+str(len(sub)):>20}", end=""); continue
            d,lo_,hi_,p,n = boot(sub, bsub, seed=hash((sl,pl))%2**30)
            sig = "*" if p<0.05 else " "
            print(f" {d:+.4f}{sig} (n={n})".ljust(22), end="")
        print()

    # ---- 偏相关：rH ~ spike + s_pre + pre_cum + spike×s + spike×pre ----
    print("\n=== 回归 rH ~ spike + s_pre + pre_cum + spike×s_pre + spike×pre_cum ===")
    alld = pd.concat([sp.assign(spike=1), bs.assign(spike=0)])
    X = np.column_stack([
        np.ones(len(alld)),
        alld.spike, alld.s_pre, alld.pre_cum,
        alld.spike*alld.s_pre, alld.spike*alld.pre_cum,
    ])
    y = alld.rH.to_numpy()
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    names = ["const","spike","s_pre","pre_cum","spike×s_pre","spike×pre_cum"]
    # cluster bootstrap
    c = cid(alld)
    nc = int(c.max())+1
    rng = np.random.default_rng(42)
    bb = []
    for _ in range(1000):
        idx = rng.integers(0,nc,nc)
        rows = np.concatenate([np.where(c==i)[0] for i in idx])
        bb.append(np.linalg.lstsq(X[rows],y[rows],rcond=None)[0])
    bb = np.array(bb)
    for i,nm in enumerate(names):
        lo,hi = np.quantile(bb[:,i],[.025,.975])
        print(f"  {nm:<16} β={beta[i]:+.5f}  CI=[{lo:+.5f},{hi:+.5f}]  {'excl0' if lo*hi>0 else ''}")

    print("\n[OK]")


if __name__ == "__main__":
    main()
