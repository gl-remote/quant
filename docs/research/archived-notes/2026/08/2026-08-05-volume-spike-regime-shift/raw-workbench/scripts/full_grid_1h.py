"""
全品种 N×H 矩阵扫描，寻找参数鲁棒高原。
- 用全部 26 个 1h 合约（MIN_BARS=420）；
- N ∈ {20, 30, 40, 60, 80, 120}
- H ∈ {20, 40, 60, 80, 100, 120, 150, 180}
- z0 ∈ {1.5, 2.0}
- 每个 (N,H,z0) 报告：Δ、p、n_s、sign_consistency（跨 prefix 负向比例）
- 识别"显著且 sign 一致"的稳定区。
"""
from __future__ import annotations
import sys, math, json
from pathlib import Path
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))
from workspace.common.symbol_utils import extract_contract_prefix  # noqa
from workspace.data.output_paths import market_csv_dir  # noqa

ATR_PERIOD = 14
MIN_BARS = 420  # 纳入全部合约
N_BOOT = 1500

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
    v, hour = df.volume, df.hour
    mu = (v.groupby(hour).shift(1).groupby(hour)
            .transform(lambda s: s.rolling(N, min_periods=N).mean()))
    sd = (v.groupby(hour).shift(1).groupby(hour)
            .transform(lambda s: s.rolling(N, min_periods=N).std(ddof=1)))
    return (v - mu) / sd


def collect(contracts, N_grid, H_grid):
    """对每个 N 预计算 z，为每个候选 bar 记录多 H 的 r^H 与 prefix。"""
    frames = {}
    for p in contracts:
        try:
            head = pd.read_csv(p, usecols=["datetime"])
        except Exception:
            continue
        if len(head) < MIN_BARS:
            continue
        sym = p.name.split(".tqsdk.1h.csv")[0]
        prefix = extract_contract_prefix(sym) or ""
        df = load_df(p)
        df["prefix"] = prefix
        df["sector"] = sector_of(prefix)
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
            for t in range(N + maxH + 1, n - maxH):
                zv = z[t]
                if not math.isfinite(zv):
                    continue
                post_all = r[t+1:t+1+maxH]
                if not np.all(np.isfinite(post_all)):
                    continue
                cum = np.cumsum(post_all)
                rec = {
                    "symbol": sym, "prefix": df.prefix.iloc[t], "sector": df.sector.iloc[t],
                    "session_date": str(sess[t]), "z": float(zv),
                }
                for H in H_grid:
                    rec[f"r{H}"] = float(cum[H-1])
                recs.append(rec)
        d = pd.DataFrame(recs)
        out[N] = d
        print(f"  N={N}: {len(d)} candidates, prefixes={d.prefix.nunique()}, z∈[{d.z.min():.2f},{d.z.max():.2f}]")
    return out


def boot_ci(sp_vals, sp_cid, bs_vals, bs_cid, seed=42):
    def bm(vals, cid, rng):
        nc = int(cid.max()) + 1
        sums = np.bincount(cid, weights=vals, minlength=nc)
        cnt = np.bincount(cid, minlength=nc).astype(np.float64)
        idx = rng.integers(0, nc, size=(N_BOOT, nc))
        return sums[idx].sum(axis=1) / cnt[idx].sum(axis=1)
    rng1 = np.random.default_rng(seed)
    rng2 = np.random.default_rng(seed + 1)
    diff = bm(sp_vals, sp_cid, rng1) - bm(bs_vals, bs_cid, rng2)
    p = float(min(1, 2 * min((diff <= 0).mean(), (diff >= 0).mean())))
    return (float(sp_vals.mean() - bs_vals.mean()),
            float(np.quantile(diff, 0.025)),
            float(np.quantile(diff, 0.975)), p)


def cid(df):
    keys = sorted({(s, d) for s, d in zip(df.symbol, df.session_date)})
    km = {k: i for i, k in enumerate(keys)}
    return np.array([km[(s,d)] for s,d in zip(df.symbol, df.session_date)], dtype=np.int32)


def main():
    out_dir = REPO_ROOT / "project_data/research/volume-spike-regime-shift"
    contracts = sorted(market_csv_dir().glob("*.1h.csv"))
    N_grid = [20, 30, 40, 60, 80, 120]
    H_grid = [20, 40, 60, 80, 100, 120, 150, 180]
    z0_grid = [1.5, 2.0]

    byN = collect(contracts, N_grid, H_grid)

    rows = []
    for z0 in z0_grid:
        for N in N_grid:
            df = byN[N]
            if df.empty: continue
            sp = df[df.z >= z0]
            bs = df[df.z.abs() < 0.5]
            if len(sp) < 20 or len(bs) < 50:
                continue
            cs, cb = cid(sp), cid(bs)
            # prefix sign consistency（用 H=120 列）
            sign_col = "r120" if "r120" in df.columns else f"r{max(H_grid)}"
            pfx_signs = []
            for pfx, sub in sp.groupby("prefix"):
                bsub = bs[bs.prefix == pfx]
                if len(sub) >= 5 and len(bsub) >= 10:
                    pfx_signs.append(np.sign(sub[sign_col].mean() - bsub[sign_col].mean()))
            sign_rate = float(np.mean([s < 0 for s in pfx_signs])) if pfx_signs else float("nan")
            for H in H_grid:
                d, lo, hi, p = boot_ci(
                    sp[f"r{H}"].to_numpy(), cs,
                    bs[f"r{H}"].to_numpy(), cb,
                    seed=hash((N,H,z0)) % 2**30)
                rows.append({
                    "z0": z0, "N": N, "H": H,
                    "delta": d, "ci_lo": lo, "ci_hi": hi, "p": p,
                    "n_spike": len(sp), "n_base": len(bs),
                    "n_prefix": sp.prefix.nunique(),
                    "sign_neg_rate": sign_rate,
                    "sig": (p < 0.05) and (hi < 0),
                })
    grid = pd.DataFrame(rows)
    grid.to_csv(out_dir / "1h_full_grid.csv", index=False)

    for z0 in z0_grid:
        print(f"\n{'='*70}\nz0={z0}\n{'='*70}")
        sub = grid[grid.z0 == z0]
        print("\nΔ(spike-base) r^H:")
        print(sub.pivot(index="N", columns="H", values="delta").to_string(float_format=lambda x: f"{x:+.4f}"))
        print("\np-value:")
        print(sub.pivot(index="N", columns="H", values="p").to_string(float_format=lambda x: f"{x:.3f}"))
        print("\nsignificant (p<0.05 & CI<0):")
        print(sub.pivot(index="N", columns="H", values="sig").to_string())
        print("\nn_spike:")
        print(sub.pivot(index="N", columns="H", values="n_spike").to_string())
        print("\nprefix sign-negative rate:")
        print(sub.pivot(index="N", columns="H", values="sign_neg_rate").to_string(float_format=lambda x: f"{x:.2f}"))

    # 稳定区识别：p<0.05, sign_neg_rate>=0.7, Δ<=−0.005
    stable = grid[(grid.p < 0.05) & (grid.sign_neg_rate >= 0.7) & (grid.delta <= -0.005)]
    print("\n=== 稳定区（p<0.05 & sign_neg>=70% & Δ<=-0.5%）===")
    print(stable[["z0","N","H","delta","p","n_spike","n_prefix","sign_neg_rate"]]
          .sort_values(["z0","N","H"]).to_string(index=False, float_format=lambda x: f"{x:+.4f}"))

    (out_dir / "1h_stable_zone.json").write_text(
        stable.to_json(orient="records", indent=2))
    print(f"\n[OK] {out_dir/'1h_full_grid.csv'}")


if __name__ == "__main__":
    main()
