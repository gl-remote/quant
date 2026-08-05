"""
极端 z × regime 阈值二维扫描。
- z0 ∈ {1.5, 2.0, 2.5, 3.0, 4.0, 5.0}
- pre100 阈值 ∈ {+1%, +2%, +3%, +5%, +8%}（牛市 exhaustion）
- N=20, H=100（全品种）
- 每个 (z0, pre) 组合报告：
  n_spike, Δr100 (spike vs baseline | same regime), p, CI, spike%neg
- baseline 取 |z|<0.5 且同样满足 pre100>=阈值（同 regime baseline）
- 同时对熊市侧（pre100 < -1%, -2%, -3%, -5%）做对称扫描
"""
from __future__ import annotations
import sys, math, json
from pathlib import Path
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))
from workspace.common.symbol_utils import extract_contract_prefix
from workspace.data.output_paths import market_csv_dir

ATR = 14
N = 20
H = 100
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
        r = d.lr.to_numpy(); z = d.z.to_numpy()
        sess = d.datetime.dt.date.to_numpy()
        n = len(d)
        for t in range(N+H+101, n-H):
            zv = z[t]
            if not math.isfinite(zv): continue
            pre100 = r[t-100:t]
            post = r[t+1:t+1+H]
            if not (np.all(np.isfinite(pre100)) and np.all(np.isfinite(post))): continue
            recs.append({
                "symbol": sym, "prefix": pfx, "session": str(sess[t]),
                "z": float(zv), "pre100": float(pre100.sum()),
                "rH": float(post.sum()),
            })
    return pd.DataFrame(recs)


def cid(df):
    keys = sorted({(s,d) for s,d in zip(df.symbol,df.session)})
    km = {k:i for i,k in enumerate(keys)}
    return np.array([km[(s,d)] for s,d in zip(df.symbol,df.session)], dtype=np.int32)


def boot_diff(sp, bs, seed):
    def bm(v,c,rng):
        nc=int(c.max())+1
        sums=np.bincount(c,weights=v,minlength=nc)
        cnt=np.bincount(c,minlength=nc).astype(np.float64)
        idx=rng.integers(0,nc,size=(N_BOOT,nc))
        return sums[idx].sum(axis=1)/cnt[idx].sum(axis=1)
    cs, cb = cid(sp), cid(bs)
    rng1 = np.random.default_rng(seed); rng2 = np.random.default_rng(seed+1)
    diff = bm(sp.rH.to_numpy(),cs,rng1) - bm(bs.rH.to_numpy(),cb,rng2)
    p = float(min(1, 2*min((diff<=0).mean(),(diff>=0).mean())))
    return {
        "delta": float(sp.rH.mean()-bs.rH.mean()),
        "ci_lo": float(np.quantile(diff,.025)),
        "ci_hi": float(np.quantile(diff,.975)),
        "p": p,
        "n_spike": int(len(sp)), "n_base": int(len(bs)),
        "spike_mean": float(sp.rH.mean()),
        "spike_pct_neg": float((sp.rH<0).mean()),
        "base_mean": float(bs.rH.mean()),
    }


def main():
    out = Path("/Users/gaolei/Documents/src/quant/project_data/research/volume-spike-regime-shift")
    df = build()
    print(f"events: {len(df)}")

    z_grid = [1.5, 2.0, 2.5, 3.0, 4.0, 5.0]
    bull_grid = [0.01, 0.02, 0.03, 0.05, 0.08]
    bear_grid = [-0.01, -0.02, -0.03, -0.05]

    print("\n=== BULL exhaustion: P(spike | pre100 > X) vs baseline (same regime) ===")
    print(f"{'pre100>':>8} {'z0':>5} {'n_s':>5} {'n_b':>6} {'ΔrH':>9} {'CI':>22} {'p':>6} {'%neg':>6} {'spike_mean':>11}")
    bull_results = []
    for pre in bull_grid:
        for z0 in z_grid:
            sp = df[(df.z >= z0) & (df.pre100 >= pre)]
            bs = df[(df.z.abs() < 0.5) & (df.pre100 >= pre)]
            if len(sp) < 10 or len(bs) < 30:
                print(f"{pre*100:>7.0f}% {z0:>5.1f} {len(sp):>5} {len(bs):>6}   (too few)")
                continue
            r = boot_diff(sp, bs, seed=hash(("bull",pre,z0))%2**30)
            r["pre_thresh"] = pre; r["z0"] = z0
            bull_results.append(r)
            print(f"{pre*100:>7.0f}% {z0:>5.1f} {r['n_spike']:>5} {r['n_base']:>6} "
                  f"{r['delta']:>+9.4f} [{r['ci_lo']:+.4f},{r['ci_hi']:+.4f}] {r['p']:>6.3f} "
                  f"{r['spike_pct_neg']:>6.1%} {r['spike_mean']:>+11.4f}")
        print()

    print("\n=== BEAR rebound: P(spike | pre100 < X) vs baseline (same regime) ===")
    print(f"{'pre100<':>8} {'z0':>5} {'n_s':>5} {'n_b':>6} {'ΔrH':>9} {'CI':>22} {'p':>6} {'%up':>6} {'spike_mean':>11}")
    bear_results = []
    for pre in bear_grid:
        for z0 in z_grid:
            sp = df[(df.z >= z0) & (df.pre100 <= pre)]
            bs = df[(df.z.abs() < 0.5) & (df.pre100 <= pre)]
            if len(sp) < 10 or len(bs) < 30:
                print(f"{pre*100:>7.0f}% {z0:>5.1f} {len(sp):>5} {len(bs):>6}   (too few)")
                continue
            r = boot_diff(sp, bs, seed=hash(("bear",pre,z0))%2**30)
            r["pre_thresh"] = pre; r["z0"] = z0
            bear_results.append(r)
            print(f"{pre*100:>7.0f}% {z0:>5.1f} {r['n_spike']:>5} {r['n_base']:>6} "
                  f"{r['delta']:>+9.4f} [{r['ci_lo']:+.4f},{r['ci_hi']:+.4f}] {r['p']:>6.3f} "
                  f"{1-r['spike_pct_neg']:>6.1%} {r['spike_mean']:>+11.4f}")
        print()

    (out / "extreme_threshold_scan.json").write_text(
        json.dumps({"bull": bull_results, "bear": bear_results}, indent=2, default=str))
    print(f"[OK] {out/'extreme_threshold_scan.json'}")


if __name__ == "__main__":
    main()
