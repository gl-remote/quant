"""
熊市 regime 下的参数扫描：效应是否需要更长 H、或表现为底部震荡而非方向。
- 在 spike 前 100 根 bar 累计收益 < -2% 的 bear regime 内；
- N∈{20,40,60,80,120}, H∈{20,40,60,80,100,120,150,180,240}；
- 对每个 (N,H) 算 spike vs baseline：
  * rH 方向差
  * |r| per bar（波动）
  * path_disp（cumsum std，路径发散）
  * max_adv / max_fav（后窗最大逆向/有利偏移）
  * 方向命中率（post 上涨比例）
- 同时做 bull regime 对照。
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

ATR_PERIOD = 14
MIN_BARS = 600  # 需要容纳 H=240

SECTORS = {
    "agri": {"m","c","cs","p","CF","SR"},
    "black": {"rb","i","hc","j","jm"},
    "metal": {"cu","al","zn","ni","pb","au","ag"},
    "energy_chem": {"sc","TA","MA","pp","v","eg","eb","fg","sa","fu","bu"},
}
def sector_of(p):
    for s, ps in SECTORS.items():
        if p in ps: return s
    return "other"


def load_df(p):
    df = pd.read_csv(p)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    hi, lo, cl = df.high.to_numpy(), df.low.to_numpy(), df.close.to_numpy()
    pcl = np.concatenate([[cl[0]], cl[:-1]])
    tr = np.maximum.reduce([hi-lo, np.abs(hi-pcl), np.abs(lo-pcl)])
    df["atr"] = pd.Series(tr).rolling(ATR_PERIOD, min_periods=ATR_PERIOD).mean().to_numpy()
    df["lr"] = np.log(df.close).diff()
    df["session_date"] = df.datetime.dt.date
    df["hour"] = df.datetime.dt.hour
    return df


def z_by_hour(df, N):
    v, h = df.volume, df.hour
    mu = v.groupby(h).shift(1).groupby(h).transform(lambda s: s.rolling(N,min_periods=N).mean())
    sd = v.groupby(h).shift(1).groupby(h).transform(lambda s: s.rolling(N,min_periods=N).std(ddof=1))
    return (v - mu)/sd


def build(contracts, N_grid, H_grid):
    frames = {}
    for p in contracts:
        try: head = pd.read_csv(p, usecols=["datetime"])
        except: continue
        if len(head) < MIN_BARS: continue
        sym = p.name.split(".tqsdk.1h.csv")[0]
        prefix = extract_contract_prefix(sym) or ""
        df = load_df(p)
        df["prefix"] = prefix
        frames[sym] = df
    print(f"loaded {len(frames)} contracts")

    out = {}
    for N in N_grid:
        recs = []
        for sym, df in frames.items():
            z = z_by_hour(df, N).to_numpy()
            r = df.lr.to_numpy()
            sess = df.session_date.to_numpy()
            n = len(df)
            maxH = max(H_grid)
            for t in range(N + maxH + 101, n - maxH):
                zv = z[t]
                if not math.isfinite(zv): continue
                pre100 = r[t-100:t]
                if not np.all(np.isfinite(pre100)): continue
                pre100_sum = float(pre100.sum())
                post_all = r[t+1:t+1+maxH]
                if not np.all(np.isfinite(post_all)): continue
                cp = np.cumsum(post_all)
                rec = {
                    "symbol": sym, "prefix": df.prefix.iloc[t],
                    "session_date": str(sess[t]),
                    "z": float(zv), "pre100": pre100_sum,
                }
                for H in H_grid:
                    post = post_all[:H]
                    rec[f"r{H}"] = float(cp[H-1])
                    rec[f"abs{H}"] = float(np.abs(post).mean())
                    rec[f"pd{H}"] = float(cp[:H].std(ddof=1))
                    rec[f"mf{H}"] = float(cp[:H].max())  # max favorable (for long)
                    rec[f"ma{H}"] = float(cp[:H].min())  # max adverse
                recs.append(rec)
        d = pd.DataFrame(recs)
        out[N] = d
        print(f"  N={N}: {len(d)} candidates, prefixes={d.prefix.nunique()}")
    return out


def boot(vals, cid, seed):
    nc = int(cid.max())+1
    sums = np.bincount(cid, weights=vals, minlength=nc)
    cnt = np.bincount(cid, minlength=nc).astype(np.float64)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, nc, size=(1500, nc))
    b = sums[idx].sum(axis=1)/cnt[idx].sum(axis=1)
    return float(vals.mean()), float(np.quantile(b,0.025)), float(np.quantile(b,0.975))


def cid(df):
    keys = sorted({(s,d) for s,d in zip(df.symbol, df.session_date)})
    km = {k:i for i,k in enumerate(keys)}
    return np.array([km[(s,d)] for s,d in zip(df.symbol,df.session_date)], dtype=np.int32)


def diff_boot(sp, bs, col, seed):
    cs, cb = cid(sp), cid(bs)
    ms, ls, hs = boot(sp[col].to_numpy(), cs, seed)
    mb, lb, hb = boot(bs[col].to_numpy(), cb, seed+1)
    # paired diff via independent bootstrap
    def bm(v,c,rng):
        nc=int(c.max())+1
        sums=np.bincount(c,weights=v,minlength=nc)
        cnt=np.bincount(c,minlength=nc).astype(np.float64)
        idx=rng.integers(0,nc,size=(1500,nc))
        return sums[idx].sum(axis=1)/cnt[idx].sum(axis=1)
    rng1=np.random.default_rng(seed); rng2=np.random.default_rng(seed+1)
    d = bm(sp[col].to_numpy(),cs,rng1) - bm(bs[col].to_numpy(),cb,rng2)
    p = float(min(1, 2*min((d<=0).mean(),(d>=0).mean())))
    return {"delta": float(d.mean()), "ci_lo": float(np.quantile(d,.025)),
            "ci_hi": float(np.quantile(d,.975)), "p": p,
            "spike_mean": ms, "base_mean": mb, "n_spike": len(sp)}


def main():
    contracts = sorted(market_csv_dir().glob("*.1h.csv"))
    N_grid = [20, 40, 60, 80]
    H_grid = [20, 40, 60, 80, 100, 120, 150, 180, 240]
    byN = build(contracts, N_grid, H_grid)

    results = []
    for regime, mask_fn in [
        ("bear", lambda d: d.pre100 < -0.02),
        ("bull", lambda d: d.pre100 > 0.02),
        ("range", lambda d: (d.pre100 >= -0.02) & (d.pre100 <= 0.02)),
    ]:
        print(f"\n{'='*70}\n  {regime.upper()} regime\n{'='*70}")
        for N in N_grid:
            d = byN[N]
            if d.empty: continue
            sub = d[mask_fn(d)]
            sp = sub[sub.z >= 1.5]
            bs = sub[sub.z.abs() < 0.5]
            if len(sp) < 15 or len(bs) < 30:
                print(f"  N={N}: n_s={len(sp)} too small"); continue
            print(f"\n  N={N}  n_spike={len(sp)}  n_base={len(bs)}  prefixes={sp.prefix.nunique()}")
            for H in H_grid:
                row = {"regime": regime, "N": N, "H": H, "n_spike": len(sp)}
                for metric, col in [("r","r"),("abs","abs"),("path_disp","pd"),
                                     ("max_fav","mf"),("max_adv","ma")]:
                    r = diff_boot(sp, bs, f"{col}{H}", seed=hash((regime,N,H,metric))%2**30)
                    row[metric] = r["delta"]
                    row[f"{metric}_p"] = r["p"]
                    row[f"{metric}_spike"] = r["spike_mean"]
                    row[f"{metric}_base"] = r["base_mean"]
                # 上涨比例
                row["pct_up_spike"] = float((sp[f"r{H}"]>0).mean())
                row["pct_up_base"] = float((bs[f"r{H}"]>0).mean())
                results.append(row)
            # 打印关键列
            print(f"    {'H':>4} {'Δr':>9} {'p':>6} {'Δ|r|':>9} {'Δpd':>9} {'Δmf':>9} {'Δma':>9} {'%up_s':>7} {'%up_b':>7}")
            for H in H_grid:
                r = next(x for x in results if x["regime"]==regime and x["N"]==N and x["H"]==H)
                sig = "*" if r["r_p"]<0.05 else " "
                print(f"    {H:>4} {r['r']:>+9.4f}{sig}{r['r_p']:>5.2f} "
                      f"{r['abs']:>+9.5f} {r['path_disp']:>+9.5f} "
                      f"{r['max_fav']:>+9.4f} {r['max_adv']:>+9.4f} "
                      f"{r['pct_up_spike']:>7.1%} {r['pct_up_base']:>7.1%}")

    out = Path("/Users/gaolei/Documents/src/quant/project_data/research/volume-spike-regime-shift/bear_regime_scan.json")
    pd.DataFrame(results).to_csv(out.parent / "bear_regime_scan.csv", index=False)
    print(f"\n[OK] {out.parent/'bear_regime_scan.csv'}")


if __name__ == "__main__":
    main()
