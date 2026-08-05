"""
1h volume spike 参数敏感性定量分析。
在 z_by_hour 主口径上系统扫描：
  - N (lookback): {20, 40, 60, 80, 120, 180}
  - H (horizon):  {20, 40, 60, 80, 120, 180}
  - z0 (threshold): {1.5, 2.0, 2.5, 3.0}
固定 baseline |Z|<0.5。

对每个 (N, H, z0) 组合计算：
  - n_spike, n_clusters
  - spike vs baseline 的 r^H 差（Δ）+ cluster bootstrap CI/p
  - spike 组自己的 r^H 均值/中位数/%负
  - 跨 prefix sign 一致率

另外做：
  - N=120 H=120 z0=2 主规格的 pre-trend 分层（pre_cum 五分位）
  - spike bar 颜色/振幅分层
  - ATR 档分层
  - 板块分层
  - 事件独立性：cluster size、事件密度
"""
from __future__ import annotations
import sys, math, json, itertools
from pathlib import Path
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))
from workspace.common.symbol_utils import extract_contract_prefix  # noqa
from workspace.data.output_paths import market_csv_dir  # noqa

ATR_PERIOD = 14
MIN_BARS = 500  # 需要容纳 N=180 + H=180
N_BOOT = 2000

SECTORS = {
    "agri": {"m", "c", "cs", "p", "CF", "SR"},
    "black": {"rb", "i", "hc", "j", "jm"},
    "metal": {"cu", "al", "zn", "ni", "pb", "au", "ag"},
    "energy_chem": {"sc", "TA", "MA", "pp", "v", "eg", "eb", "fg", "sa", "fu", "bu"},
}


def sector_of(p):
    for s, ps in SECTORS.items():
        if p in ps:
            return s
    return "other"


def load_df(p):
    df = pd.read_csv(p)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    hi, lo, cl = df.high.to_numpy(), df.low.to_numpy(), df.close.to_numpy()
    pcl = np.concatenate([[cl[0]], cl[:-1]])
    tr = np.maximum.reduce([hi - lo, np.abs(hi - pcl), np.abs(lo - pcl)])
    df["atr"] = pd.Series(tr).rolling(ATR_PERIOD, min_periods=ATR_PERIOD).mean().to_numpy()
    df["lr"] = np.log(df.close).diff()
    df["session_date"] = df.datetime.dt.date
    df["hour"] = df.datetime.dt.hour
    return df


def precompute_z(df, N):
    """对给定 N 预计算同时段 z（返回 Series）。"""
    v, hour = df.volume, df.hour
    mu = (v.groupby(hour).shift(1).groupby(hour)
            .transform(lambda s: s.rolling(N, min_periods=N).mean()))
    sd = (v.groupby(hour).shift(1).groupby(hour)
            .transform(lambda s: s.rolling(N, min_periods=N).std(ddof=1)))
    return (v - mu) / sd


def collect_all(contracts, N_grid, H_grid, z0_grid):
    """预加载所有合约，对每个 N 预计算 z；事件在 (N,H,z0) 上重用。
    返回 dict[N] -> DataFrame[每行一个候选 bar 的 r^H 等字段（多列 H）]。
    """
    frames = {}
    for p in contracts:
        symbol = p.name.split(".tqsdk.1h.csv")[0]
        prefix = extract_contract_prefix(symbol) or ""
        df = load_df(p)
        if len(df) < MIN_BARS:
            continue
        df["prefix"] = prefix
        df["sector"] = sector_of(prefix)
        # 预计算多个 H 的后窗收益：直接存 lr 和 atr，运行时切片
        frames[symbol] = df
    print(f"loaded {len(frames)} contracts")

    out = {}
    for N in N_grid:
        recs = []
        for sym, df in frames.items():
            z = precompute_z(df, N).to_numpy()
            r = df.lr.to_numpy()
            atr = df.atr.to_numpy()
            sess = df.session_date.to_numpy()
            hour = df.hour.to_numpy()
            n = len(df)
            maxH = max(H_grid)
            for t in range(N + maxH + 1, n - maxH):
                zv = z[t]
                if not math.isfinite(zv):
                    continue
                a = atr[t]
                if not (math.isfinite(a) and a > 0):
                    continue
                # 为所有 H 算 r^H
                rh = {}
                post_all = r[t+1:t+1+maxH]
                if not np.all(np.isfinite(post_all)):
                    continue
                cum = np.cumsum(post_all)
                for H in H_grid:
                    rh[f"r{H}"] = float(cum[H-1])
                # pre 窗用 H=20 的（用于 pre-trend 匹配/分层）
                pre20 = r[t-20:t]
                rec = {
                    "symbol": sym, "prefix": df.prefix.iloc[t], "sector": df.sector.iloc[t],
                    "session_date": str(sess[t]), "hour": int(hour[t]),
                    "z": float(zv), "spike_ret": float(r[t]),
                    "spike_bar_atr": float(abs(r[t]) / a),
                    "pre_cum20": float(pre20.sum()),
                    "pre_abs20": float(np.abs(pre20).mean()),
                    "atr": float(a),
                }
                rec.update(rh)
                recs.append(rec)
        d = pd.DataFrame(recs)
        out[N] = d
        print(f"  N={N}: {len(d)} candidate bars, z range [{d.z.min():.2f},{d.z.max():.2f}]" if len(d) else f"  N={N}: 0")
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
    return {
        "delta": float(sp_vals.mean() - bs_vals.mean()),
        "ci_lo": float(np.quantile(diff, 0.025)),
        "ci_hi": float(np.quantile(diff, 0.975)),
        "p_two": p,
        "spike_mean": float(sp_vals.mean()),
        "spike_median": float(np.median(sp_vals)),
        "spike_pct_neg": float((sp_vals < 0).mean()),
        "base_mean": float(bs_vals.mean()),
    }


def cluster_ids(df):
    keys = sorted({(s, d) for s, d in zip(df.symbol, df.session_date)})
    km = {k: i for i, k in enumerate(keys)}
    return np.array([km[(s, d)] for s, d in zip(df.symbol, df.session_date)], dtype=np.int32)


def grid_scan(byN, N_grid, H_grid, z0_grid, z_base=0.5):
    rows = []
    for N in N_grid:
        df = byN[N]
        if df.empty or "z" not in df.columns:
            continue
        for z0 in z0_grid:
            sp = df[df.z >= z0]
            bs = df[df.z.abs() < z_base]
            if len(sp) < 20 or len(bs) < 50:
                continue
            cs = cluster_ids(sp)
            cb = cluster_ids(bs)
            # 跨 prefix sign
            pfx_signs = []
            for pfx, sub in sp.groupby("prefix"):
                bsub = bs[bs.prefix == pfx]
                if len(sub) >= 3 and len(bsub) >= 5:
                    # 用 H=120 的列做 sign（若存在）
                    col = "r120" if "r120" in df.columns else f"r{max(H_grid)}"
                    pfx_signs.append(np.sign(sub[col].mean() - bsub[col].mean()))
            sign_rate = float(np.mean([s < 0 for s in pfx_signs])) if pfx_signs else float("nan")
            for H in H_grid:
                col = f"r{H}"
                d = boot_ci(sp[col].to_numpy(), cs, bs[col].to_numpy(), cb,
                            seed=hash((N, H, z0)) % 2**30)
                d.update({
                    "N": N, "H": H, "z0": z0,
                    "n_spike": int(len(sp)), "n_base": int(len(bs)),
                    "n_clusters": int(len(np.unique(cs))),
                    "sign_consistency_neg": sign_rate,
                })
                rows.append(d)
    return pd.DataFrame(rows)


def stratify_main(byN, N=120, H=120, z0=2.0):
    df = byN[N]
    col = f"r{H}"
    sp = df[df.z >= z0].copy()
    bs = df[df.z.abs() < 0.5]
    cs, cb = cluster_ids(sp), cluster_ids(bs)
    out = {}

    # 1. pre_cum20 五分位（在 spike 内切）
    q = pd.qcut(sp.pre_cum20, 5, labels=False, duplicates="drop")
    sp["pre_q"] = q
    rows = []
    for qk, sub in sp.groupby("pre_q"):
        d = boot_ci(sub[col].to_numpy(), cluster_ids(sub),
                    bs[col].to_numpy(), cb, seed=100 + int(qk))
        d["n_spike"] = len(sub)
        d["pre_range"] = [float(sub.pre_cum20.min()), float(sub.pre_cum20.max())]
        rows.append(d)
    out["pre_cum_quintile"] = rows

    # 2. spike bar 颜色 / 振幅
    rows = []
    for label, mask in [
        ("spike_up", sp.spike_ret > 0),
        ("spike_dn", sp.spike_ret < 0),
        ("big_bar_>=1ATR", sp.spike_bar_atr >= 1.0),
        ("mid_bar_0.5-1ATR", (sp.spike_bar_atr >= 0.5) & (sp.spike_bar_atr < 1.0)),
        ("small_bar_<0.5ATR", sp.spike_bar_atr < 0.5),
    ]:
        sub = sp[mask]
        if len(sub) < 10:
            continue
        d = boot_ci(sub[col].to_numpy(), cluster_ids(sub),
                    bs[col].to_numpy(), cb, seed=hash(label) % 2**30)
        d["n_spike"] = len(sub)
        d["label"] = label
        rows.append(d)
    out["spike_bar_split"] = rows

    # 3. ATR 档（全样本三分位）
    df["atr_q"] = pd.qcut(df.atr, 3, labels=["low", "mid", "high"], duplicates="drop")
    sp2 = df[(df.z >= z0)]
    rows = []
    for qk in ["low", "mid", "high"]:
        sub = sp2[sp2.atr_q == qk]
        bsub = df[(df.z.abs() < 0.5) & (df.atr_q == qk)]
        if len(sub) < 10 or len(bsub) < 20:
            continue
        d = boot_ci(sub[col].to_numpy(), cluster_ids(sub),
                    bsub[col].to_numpy(), cluster_ids(bsub), seed=200 + hash(qk) % 100)
        d["n_spike"] = len(sub)
        d["label"] = qk
        rows.append(d)
    out["atr_split"] = rows

    # 4. 板块
    rows = []
    for sec in sorted(df.sector.unique()):
        sub = sp2[sp2.sector == sec]
        bsub = df[(df.z.abs() < 0.5) & (df.sector == sec)]
        if len(sub) < 10 or len(bsub) < 20:
            continue
        d = boot_ci(sub[col].to_numpy(), cluster_ids(sub),
                    bsub[col].to_numpy(), cluster_ids(bsub), seed=300 + hash(sec) % 100)
        d["n_spike"] = len(sub)
        d["label"] = sec
        rows.append(d)
    out["sector_split"] = rows

    # 5. hour-of-spike
    rows = []
    def hbkt(h):
        if h == 21: return "21_night_open"
        if h == 9: return "9_day_open"
        if h in (10, 13, 14): return "intraday"
        if h == 11: return "11_morning_close"
        return "other"
    sp2 = sp2.copy()
    sp2["h_bkt"] = sp2.hour.apply(hbkt)
    df2 = df.copy()
    df2["h_bkt"] = df2.hour.apply(hbkt)
    for b in sorted(sp2.h_bkt.unique()):
        sub = sp2[sp2.h_bkt == b]
        bsub = df2[(df2.z.abs() < 0.5) & (df2.h_bkt == b)]
        if len(sub) < 10 or len(bsub) < 20:
            continue
        d = boot_ci(sub[col].to_numpy(), cluster_ids(sub),
                    bsub[col].to_numpy(), cluster_ids(bsub), seed=400 + hash(b) % 100)
        d["n_spike"] = len(sub)
        d["label"] = b
        rows.append(d)
    out["hour_split"] = rows

    return out


def main():
    out_dir = REPO_ROOT / "project_data/research/volume-spike-regime-shift"
    contracts = [p for p in sorted(market_csv_dir().glob("*.1h.csv"))]

    N_grid = [20, 40, 60, 80, 120, 180]
    H_grid = [20, 40, 60, 80, 120, 180]
    z0_grid = [1.5, 2.0, 2.5, 3.0]

    print("Precomputing events across N grid...")
    byN = collect_all(contracts, N_grid, H_grid, z0_grid)

    print("\n=== N × H × z0 grid scan ===")
    grid = grid_scan(byN, N_grid, H_grid, z0_grid)
    grid.to_csv(out_dir / "1h_param_grid.csv", index=False)

    # 打印主表（z0=2.0）
    print("\nz0=2.0, Δ(spike-base) r^H:")
    pivot = grid[grid.z0 == 2.0].pivot(index="N", columns="H", values="delta")
    print(pivot.to_string(float_format=lambda x: f"{x:+.4f}"))
    print("\np-values:")
    pivot_p = grid[grid.z0 == 2.0].pivot(index="N", columns="H", values="p_two")
    print(pivot_p.to_string(float_format=lambda x: f"{x:.3f}"))
    print("\nn_spike:")
    pivot_n = grid[grid.z0 == 2.0].pivot(index="N", columns="H", values="n_spike")
    print(pivot_n.to_string())

    for z0 in z0_grid:
        print(f"\n--- z0={z0} ---")
        sub = grid[grid.z0 == z0]
        print(sub[sub.H == 120][["N", "delta", "ci_lo", "ci_hi", "p_two", "n_spike", "sign_consistency_neg"]]
              .to_string(index=False, float_format=lambda x: f"{x:+.4f}" if abs(x) < 10 else f"{x:.0f}"))

    print("\n=== Stratification at N=120 H=120 z0=2 ===")
    strat = stratify_main(byN, N=120, H=120, z0=2.0)
    for cat, rows in strat.items():
        print(f"\n-- {cat} --")
        for r in rows:
            label = r.get("label", f"q{r.get('pre_range','')}")
            print(f"  {str(label):<22} n={r['n_spike']:>4} Δ={r['delta']:+.5f} "
                  f"CI=[{r['ci_lo']:+.5f},{r['ci_hi']:+.5f}] p={r['p_two']:.3f} "
                  f"spike%neg={r.get('spike_pct_neg',float('nan')):.2f}")

    (out_dir / "1h_stratification.json").write_text(
        json.dumps(strat, indent=2, ensure_ascii=False, default=str))
    print(f"\n[OK] {out_dir}/1h_param_grid.csv, 1h_stratification.json")


if __name__ == "__main__":
    main()
