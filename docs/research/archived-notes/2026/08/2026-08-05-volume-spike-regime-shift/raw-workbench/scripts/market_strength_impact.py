"""
直接测量成交量放量如何影响市场强度 s = ν/σ。
- s_pre = mean(r_{t-100:t})/std(r_{t-100:t})
- s_post = mean(r_{t+1:t+101})/std(r_{t+1:t+101})
- 同时分解为 ν_post（漂移）和 σ_post（波动）
- 在高 s_pre（Q4，s>0.11）条件下，比较 spike vs baseline
- 用 N=20 z≥1.5，全品种
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

N = 20; W = 100


def load(p):
    d = pd.read_csv(p)
    d["datetime"] = pd.to_datetime(d["datetime"])
    d = d.sort_values("datetime").reset_index(drop=True)
    d["lr"] = np.log(d.close).diff()
    v, h = d.volume, d.datetime.dt.hour
    mu = v.groupby(h).shift(1).groupby(h).transform(lambda s: s.rolling(N,min_periods=N).mean())
    sd = v.groupby(h).shift(1).groupby(h).transform(lambda s: s.rolling(N,min_periods=N).std(ddof=1))
    d["z"] = (v-mu)/sd
    return d


def s_of(r):
    mu = r.mean(); sd = r.std(ddof=1)
    return mu/sd if sd > 0 else np.nan, mu, sd


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
        for t in range(N+W+1, n-W):
            zv = z[t]
            if not math.isfinite(zv): continue
            pre = r[t-W:t]; post = r[t+1:t+1+W]
            if not (np.all(np.isfinite(pre)) and np.all(np.isfinite(post))): continue
            s_pre, nu_pre, sig_pre = s_of(pre)
            s_post, nu_post, sig_post = s_of(post)
            if not (math.isfinite(s_pre) and math.isfinite(s_post)): continue
            if zv >= 1.5: grp = "spike"
            elif abs(zv) < 0.5: grp = "base"
            else: continue
            recs.append({
                "sym": sym, "pfx": pfx, "t": t, "grp": grp,
                "s_pre": s_pre, "s_post": s_post,
                "nu_pre": nu_pre, "nu_post": nu_post,
                "sig_pre": sig_pre, "sig_post": sig_post,
                "pre_cum": float(pre.sum()), "post_cum": float(post.sum()),
                "z": float(zv),
            })
    return pd.DataFrame(recs)


def cid(df):
    keys = sorted({(s,t) for s,t in zip(df.sym,df.t)})
    km = {k:i for i,k in enumerate(keys)}
    return np.array([km[(s,t)] for s,t in zip(df.sym,df.t)], dtype=np.int32)


def boot_mean(vals, c, seed=42, nboot=1500):
    nc = int(c.max())+1
    sums = np.bincount(c, weights=vals, minlength=nc)
    cnt = np.bincount(c, minlength=nc).astype(np.float64)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0,nc,size=(nboot,nc))
    b = sums[idx].sum(axis=1)/cnt[idx].sum(axis=1)
    return float(vals.mean()), float(np.quantile(b,.025)), float(np.quantile(b,.975))


def compare(sp, bs, col, label):
    cs, cb = cid(sp), cid(bs)
    ms, ls, hs = boot_mean(sp[col].to_numpy(), cs, seed=hash(label)%2**30)
    mb, lb, hb = boot_mean(bs[col].to_numpy(), cb, seed=hash(label+"b")%2**30)
    # diff bootstrap
    def bm(v,c,rng):
        nc=int(c.max())+1
        sums=np.bincount(c,weights=v,minlength=nc)
        cnt=np.bincount(c,minlength=nc).astype(np.float64)
        idx=rng.integers(0,nc,size=(1500,nc))
        return sums[idx].sum(axis=1)/cnt[idx].sum(axis=1)
    rng1=np.random.default_rng(42); rng2=np.random.default_rng(43)
    d = bm(sp[col].to_numpy(),cs,rng1)-bm(bs[col].to_numpy(),cb,rng2)
    p = float(min(1,2*min((d<=0).mean(),(d>=0).mean())))
    print(f"  {label:<12} spike={ms:+.5f} [{ls:+.5f},{hs:+.5f}]  "
          f"base={mb:+.5f}  Δ={ms-mb:+.5f} [{np.quantile(d,.025):+.5f},{np.quantile(d,.975):+.5f}] p={p:.3f}")
    return ms-mb, p


def main():
    df = build()
    print(f"events: {len(df)}, spike={(df.grp=='spike').sum()}, base={(df.grp=='base').sum()}")

    sp = df[df.grp=="spike"].copy()
    bs = df[df.grp=="base"].copy()

    # 分 s_pre 五分位
    sp["sq"] = pd.qcut(sp.s_pre, 5, labels=False, duplicates="drop")
    print(f"\n=== Spike 前 s_pre 五分位的 s 变化（全样本）===")
    print(f"{'sq':>3} {'s_pre':>8} {'n':>5} {'s_pre_mean':>11} {'s_post_mean':>12} {'Δs':>9} {'ν_post':>10} {'σ_post':>10}")
    for q in sorted(sp.sq.dropna().unique()):
        sub = sp[sp.sq==q]
        print(f"{int(q):>3} [{sub.s_pre.min():+.3f},{sub.s_pre.max():+.3f}] {len(sub):>5} "
              f"{sub.s_pre.mean():>+11.4f} {sub.s_post.mean():>+12.4f} "
              f"{sub.s_post.mean()-sub.s_pre.mean():>+9.4f} "
              f"{sub.nu_post.mean():>+10.6f} {sub.sig_post.mean():>10.6f}")

    # 高 s_pre Q4 条件下 spike vs baseline
    print("\n=== 高 s_pre（Q4, s>0.11）条件：spike vs baseline ===")
    q4_lo = sp[sp.sq==4].s_pre.min()
    sp4 = sp[sp.sq==4]
    bs4 = bs[bs.s_pre >= q4_lo]
    print(f"spike n={len(sp4)}, baseline n={len(bs4)} (s_pre≥{q4_lo:.3f})")
    for col, lab in [("s_pre","s_pre"),("s_post","s_post"),
                     ("nu_pre","ν_pre"),("nu_post","ν_post"),
                     ("sig_pre","σ_pre"),("sig_post","σ_post"),
                     ("post_cum","post_cum")]:
        compare(sp4, bs4, col, lab)

    # 跨 s_pre 五分位的 Δs_post（spike - same-s base）
    print("\n=== 各 s_pre 五分位 spike vs 同区间 baseline 的 Δs_post ===")
    print(f"{'sq':>3} {'s_range':>20} {'n_s':>5} {'n_b':>5} {'Δs_post':>10} {'p':>6} {'Δν_post':>10} {'Δσ_post':>10}")
    for q in sorted(sp.sq.dropna().unique()):
        sub_s = sp[sp.sq==q]
        lo, hi = sub_s.s_pre.min(), sub_s.s_pre.max()
        sub_b = bs[(bs.s_pre>=lo)&(bs.s_pre<=hi)]
        if len(sub_s)<10 or len(sub_b)<30: continue
        ds, ps = compare(sub_s, sub_b, "s_post", f"s{q}")
        dn, _ = compare(sub_s, sub_b, "nu_post", f"nu{q}")
        dsg, _ = compare(sub_s, sub_b, "sig_post", f"sg{q}")
        print(f"{int(q):>3} [{lo:+.3f},{hi:+.3f}] {len(sub_s):>5} {len(sub_b):>5} "
              f"{ds:>+10.5f} {ps:>6.3f} {dn:>+10.6f} {dsg:>+10.6f}")

    # 关键：s 的衰减来源——ν 下降还是 σ 上升？
    print("\n=== 高 s_pre spike 的 s_pre→s_post 分解（spike 自身）===")
    s4 = sp[sp.sq==4]
    print(f"  s:   {s4.s_pre.mean():+.4f} → {s4.s_post.mean():+.4f}  Δ={s4.s_post.mean()-s4.s_pre.mean():+.4f}")
    print(f"  ν:   {s4.nu_pre.mean():+.6f} → {s4.nu_post.mean():+.6f}  Δ={s4.nu_post.mean()-s4.nu_pre.mean():+.6f}")
    print(f"  σ:   {s4.sig_pre.mean():.6f} → {s4.sig_post.mean():.6f}  Δ={s4.sig_post.mean()-s4.sig_pre.mean():+.6f}")
    print(f"  cum: {s4.pre_cum.mean():+.4f} → {s4.post_cum.mean():+.4f}")

    # 同 s_pre baseline 的变化
    b4 = bs[bs.s_pre>=q4_lo]
    print(f"\n  baseline（同 s_pre≥{q4_lo:.3f}）:")
    print(f"  s:   {b4.s_pre.mean():+.4f} → {b4.s_post.mean():+.4f}  Δ={b4.s_post.mean()-b4.s_pre.mean():+.4f}")
    print(f"  ν:   {b4.nu_pre.mean():+.6f} → {b4.nu_post.mean():+.6f}  Δ={b4.nu_post.mean()-b4.nu_pre.mean():+.6f}")
    print(f"  σ:   {b4.sig_pre.mean():.6f} → {b4.sig_post.mean():.6f}  Δ={b4.sig_post.mean()-b4.sig_pre.mean():+.6f}")
    print(f"  cum: {b4.pre_cum.mean():+.4f} → {b4.post_cum.mean():+.4f}")


if __name__ == "__main__":
    main()
