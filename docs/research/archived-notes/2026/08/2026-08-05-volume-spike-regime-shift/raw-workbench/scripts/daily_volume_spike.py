"""
文件级元信息：
- 创建背景：1h 周期的 volume spike 研究因 lookback 敏感 + 时段污染证伪。
  本脚本在日线周期上重做核心检验，验证结论是否是 1h 粒度特有的 artefact。
- 数据构造：
  * 每个 1h CSV 按交易日（夜盘算次日，与 gatekeeper session_date 一致）聚合成日线 OHLCV；
  * 按品种 prefix 把连续合约拼接成主力连续日线（按时间排序，合约重叠时取成交量最大的）；
  * 对数收益用日线收盘。
- 检验（直接复用 1h 阶段的核心问题）：
  1) 事件定义：Z_t = (V_t - μ_t) / ς_t，μ/ς 用不含当根的 N 根 rolling；
     N ∈ {20, 60, 120}（对应 1/3/6 个月），阈值 z0 ∈ {1.5, 2.0, 3.0}；
  2) spike vs baseline (|Z|<0.5) 后 H ∈ {1,3,5,10,20} 交易日的：
     - 累计收益 r^(h)（方向）
     - 已实现波动 σ_h、|r|_h
     - VaR5 / ES5（左尾，pooled across events）
     - path_disp（cumsum std）
  3) pre/post 事件研究：对称 H 窗，DiD against baseline；
  4) N 敏感性：直接对比 N=20/60/120；
  5) 跨品种 sign 保留率（prefix-level bootstrap）。
- 注意事项：日线 cluster = prefix（每个品种一条连续线），cluster 数只有 12，
  bootstrap 精度有限，重点看跨品种 sign 一致性而非 p 值。
"""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workspace.common.symbol_utils import extract_contract_prefix  # noqa: E402
from workspace.data.output_paths import market_csv_dir  # noqa: E402

ATR_PERIOD = 14
N_GRID = (20, 60, 120)
Z0_GRID = (1.5, 2.0, 3.0)
Z0_MAIN = 2.0
Z_BASELINE = 0.5
H_GRID = (1, 3, 5, 10, 20)
MIN_DAILY_BARS = 140  # 至少 7 个月日线（覆盖 N=20/60 主规格）
N_BOOT = 3000
BOOT_SEED = 20260805

SECTORS = {
    "agri": {"m", "c", "cs", "p", "a", "b", "y", "jd", "CF", "SR"},
    "black": {"rb", "i", "hc", "j", "jm"},
    "metal": {"cu", "al", "zn", "ni", "pb", "au", "ag"},
    "energy_chem": {"sc", "TA", "MA", "pp", "v", "eg", "eb", "fg", "sa", "fu", "bu"},
}


def sector_of(prefix: str) -> str:
    for s, pset in SECTORS.items():
        if prefix in pset:
            return s
    return "other"


# ───────── 日线聚合与连续拼接 ─────────
def _session_date(dt: pd.Series) -> pd.Series:
    """夜盘（hour>=20 或 hour<3）算次日交易日，与 gatekeeper 一致。"""
    d = dt.dt.date.copy()
    night = (dt.dt.hour >= 20) | (dt.dt.hour < 3)
    # 夜盘日期 +1 天
    next_day = (dt + pd.Timedelta(days=1)).dt.date
    return pd.Series(np.where(night, next_day, d), index=dt.index)


def aggregate_daily(hourly_path: Path) -> pd.DataFrame:
    df = pd.read_csv(hourly_path)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    df["session_date"] = _session_date(df["datetime"])
    g = df.groupby("session_date", sort=True)
    daily = pd.DataFrame({
        "open": g["open"].first(),
        "high": g["high"].max(),
        "low": g["low"].min(),
        "close": g["close"].last(),
        "volume": g["volume"].sum(),
    }).reset_index()
    daily["session_date"] = pd.to_datetime(daily["session_date"])
    return daily


def build_continuous_by_prefix() -> dict[str, pd.DataFrame]:
    """每个 prefix 把其全部合约的日线拼成一条主力连续线。
    重叠日取成交量大的合约；无重叠时直接拼接。
    """
    files = sorted(market_csv_dir().glob("*.1h.csv"))
    by_prefix: dict[str, list[tuple[pd.Timestamp, pd.Timestamp, Path]]] = {}
    for f in files:
        try:
            head = pd.read_csv(f, usecols=["datetime"])
        except Exception:
            continue
        if len(head) < 100:  # 太短的合约不参与
            continue
        # 文件名形如 DCE.m2601.tqsdk.1h.csv
        sym = f.name.split(".tqsdk")[0]
        prefix = extract_contract_prefix(sym) or sym.split(".")[-1].rstrip("0123456789")
        d0 = pd.to_datetime(head.datetime.iloc[0])
        d1 = pd.to_datetime(head.datetime.iloc[-1])
        by_prefix.setdefault(prefix, []).append((d0, d1, f))

    out: dict[str, pd.DataFrame] = {}
    for prefix, flist in by_prefix.items():
        dailies = []
        for _, _, f in sorted(flist, key=lambda x: x[0]):
            d = aggregate_daily(f)
            dailies.append(d)
        if not dailies:
            continue
        # 合并：按 session_date，同一日若有多合约，取 volume 最大者
        merged = pd.concat(dailies, ignore_index=True)
        merged = merged.sort_values(["session_date", "volume"])
        merged = merged.drop_duplicates("session_date", keep="last").reset_index(drop=True)
        merged = merged.sort_values("session_date").reset_index(drop=True)
        if len(merged) < MIN_DAILY_BARS:
            continue
        merged["lr"] = np.log(merged.close).diff()
        h, l, c = merged.high.to_numpy(), merged.low.to_numpy(), merged.close.to_numpy()
        pc = np.concatenate([[c[0]], c[:-1]])
        tr = np.maximum.reduce([h - l, np.abs(h - pc), np.abs(l - pc)])
        merged["atr"] = pd.Series(tr).rolling(ATR_PERIOD, min_periods=ATR_PERIOD).mean().to_numpy()
        merged["prefix"] = prefix
        merged["sector"] = sector_of(prefix)
        out[prefix] = merged
    return out


# ───────── 事件构建 ─────────
def build_events(frames: dict[str, pd.DataFrame], lookback_n: int, z0: float,
                 h_max: int = 20) -> pd.DataFrame:
    recs = []
    for prefix, df in frames.items():
        v = df.volume
        mu = v.shift(1).rolling(lookback_n, min_periods=lookback_n).mean()
        sd = v.shift(1).rolling(lookback_n, min_periods=lookback_n).std(ddof=1)
        df = df.assign(z=(v - mu) / sd)
        r = df.lr.to_numpy()
        z = df.z.to_numpy()
        atr = df.atr.to_numpy()
        n = len(df)
        for t in range(max(h_max, lookback_n + 1), n - h_max):
            zv = z[t]
            if not math.isfinite(zv):
                continue
            if zv >= z0:
                grp = "spike"
            elif abs(zv) < Z_BASELINE:
                grp = "baseline"
            else:
                continue
            a = atr[t]
            if not (math.isfinite(a) and a > 0):
                continue
            pre = r[t - h_max : t]
            post_all = r[t + 1 : t + 1 + h_max]
            if not (np.all(np.isfinite(pre)) and np.all(np.isfinite(post_all))):
                continue
            rec = {
                "prefix": prefix, "sector": df.sector.iloc[t], "date": df.session_date.iloc[t],
                "group": grp, "z": float(zv),
                "spike_ret": float(r[t]),
                "pre_cum": float(pre.sum()),
                "pre_abs": float(np.abs(pre).mean()),
                "entry_atr": float(a),
            }
            for h in H_GRID:
                post = post_all[:h]
                rec[f"r{h}"] = float(post.sum())
                rec[f"abs{h}"] = float(np.abs(post).mean())
                rec[f"sig{h}"] = float(post.std(ddof=1)) if h > 1 else float("nan")
            cp = np.cumsum(post_all)
            rec["path_disp20"] = float(cp.std(ddof=1))
            rec["max_fav20"] = float(cp.max())
            rec["max_adv20"] = float(cp.min())
            recs.append(rec)
    return pd.DataFrame(recs)


# ───────── bootstrap（cluster = prefix） ─────────
def boot_cluster(vals: np.ndarray, clusters: np.ndarray, seed: int) -> dict[str, float]:
    keys = np.unique(clusters)
    nc = len(keys)
    # 每 cluster 内预聚合 sum/cnt
    cmap = {k: i for i, k in enumerate(keys)}
    cid = np.array([cmap[c] for c in clusters], dtype=np.int32)
    sums = np.bincount(cid, weights=vals, minlength=nc)
    cnt = np.bincount(cid, minlength=nc).astype(np.float64)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, nc, size=(N_BOOT, nc), dtype=np.int32)
    boot = sums[idx].sum(axis=1) / cnt[idx].sum(axis=1)
    return {
        "point": float(vals.mean()),
        "ci_lo": float(np.quantile(boot, 0.025)),
        "ci_hi": float(np.quantile(boot, 0.975)),
        "n": int(len(vals)),
        "n_clusters": int(nc),
    }


def boot_diff(s: np.DataFrame, b: pd.DataFrame, col: str, seed: int) -> dict[str, float]:
    """prefix-level 两样本均值差 bootstrap（独立重抽）。"""
    sv, sc = s[col].to_numpy(), s.prefix.to_numpy()
    bv, bc = b[col].to_numpy(), b.prefix.to_numpy()
    keys_s = np.unique(sc)
    keys_b = np.unique(bc)
    cmap_s = {k: i for i, k in enumerate(keys_s)}
    cmap_b = {k: i for i, k in enumerate(keys_b)}
    cid_s = np.array([cmap_s[c] for c in sc], dtype=np.int32)
    cid_b = np.array([cmap_b[c] for c in bc], dtype=np.int32)
    sums_s = np.bincount(cid_s, weights=sv, minlength=len(keys_s))
    cnt_s = np.bincount(cid_s, minlength=len(keys_s)).astype(np.float64)
    sums_b = np.bincount(cid_b, weights=bv, minlength=len(keys_b))
    cnt_b = np.bincount(cid_b, minlength=len(keys_b)).astype(np.float64)
    rng = np.random.default_rng(seed)
    is_ = rng.integers(0, len(keys_s), size=(N_BOOT, len(keys_s)), dtype=np.int32)
    ib = rng.integers(0, len(keys_b), size=(N_BOOT, len(keys_b)), dtype=np.int32)
    diff = (sums_s[is_].sum(axis=1) / cnt_s[is_].sum(axis=1)) - (
        sums_b[ib].sum(axis=1) / cnt_b[ib].sum(axis=1)
    )
    p = float(min(1.0, 2 * min((diff <= 0).mean(), (diff >= 0).mean())))
    return {
        "delta": float(sv.mean() - bv.mean()),
        "ci_lo": float(np.quantile(diff, 0.025)),
        "ci_hi": float(np.quantile(diff, 0.975)),
        "p_two": p,
    }


def tail_boot(df: pd.DataFrame, col: str, seed: int) -> dict[str, Any]:
    """pooled VaR5/ES5 的 cluster bootstrap（按 prefix 整簇重抽后合并）。"""
    keys = sorted(df.prefix.unique())
    clusters = [df[df.prefix == k][col].to_numpy() for k in keys]
    rng = np.random.default_rng(seed)
    nc = len(keys)
    var5, es5, means = [], [], []
    for _ in range(N_BOOT):
        idx = rng.integers(0, nc, size=nc)
        sample = np.concatenate([clusters[i] for i in idx])
        q5 = np.quantile(sample, 0.05)
        var5.append(q5)
        es5.append(sample[sample <= q5].mean())
        means.append(sample.mean())
    vals = df[col].to_numpy()
    q5p = float(np.quantile(vals, 0.05))
    return {
        "mean_point": float(vals.mean()),
        "mean_ci": [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))],
        "var5_point": q5p,
        "var5_ci": [float(np.quantile(var5, 0.025)), float(np.quantile(var5, 0.975))],
        "es5_point": float(vals[vals <= q5p].mean()),
        "es5_ci": [float(np.quantile(es5, 0.025)), float(np.quantile(es5, 0.975))],
        "n": int(len(vals)),
        "n_clusters": nc,
    }


# ───────── 主分析 ─────────
def run_main(frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    out: dict[str, Any] = {"meta": {"prefixes": list(frames.keys()),
                                     "n_prefix": len(frames)}}

    # ---- 主规格 N=20, z0=2 ----
    print("Building events (N=20, z0=2)...")
    ev = build_events(frames, lookback_n=20, z0=Z0_MAIN)
    ev.to_parquet(REPO_ROOT / "project_data/research/volume-spike-regime-shift/daily_events.parquet", index=False)
    sp = ev[ev.group == "spike"]
    bs = ev[ev.group == "baseline"]
    print(f"  events={len(ev)}  spike={len(sp)}  base={len(bs)}")

    print("\n=== 日线 spike vs baseline: H 维度（N=20, z0=2）===")
    horizon = {}
    for h in H_GRID:
        row = {"n_spike": int(len(sp)), "n_base": int(len(bs))}
        for col, label in [(f"r{h}", "mean"), (f"abs{h}", "abs"), (f"sig{h}", "sigma")]:
            if col not in sp.columns:
                continue
            d = boot_diff(sp, bs, col, seed=100 + h + hash(label) % 1000)
            row[label] = d
            print(f"  h={h:>2} {label:<5} Δ={d['delta']:+.6f} CI=[{d['ci_lo']:+.6f},{d['ci_hi']:+.6f}] p={d['p_two']:.3f}")
        horizon[str(h)] = row

    print("\n=== 日线尾部（h=20, N=20, z0=2）===")
    t20 = {
        "spike": tail_boot(sp, "r20", seed=200),
        "baseline": tail_boot(bs, "r20", seed=201),
    }
    for g in ("spike", "baseline"):
        x = t20[g]
        print(f"  {g:<9}: mean={x['mean_point']:+.5f}{x['mean_ci']}  "
              f"VaR5={x['var5_point']:+.5f}{x['var5_ci']}  ES5={x['es5_point']:+.5f}{x['es5_ci']}")
    # ES5 diff
    es_diff = sp.r20[sp.r20 <= sp.r20.quantile(0.05)].mean() - bs.r20[bs.r20 <= bs.r20.quantile(0.05)].mean()
    print(f"  ES5 Δ(spike-base) = {es_diff:+.5f}")

    print("\n=== 日线 pre/post DiD（H=20, N=20）===")
    # pre/post 对称：spike 的 pre_cum vs r20；baseline 同；DiD
    d_pre_s = boot_cluster(sp.pre_cum.to_numpy(), sp.prefix.to_numpy(), 300)
    d_post_s = boot_cluster(sp.r20.to_numpy(), sp.prefix.to_numpy(), 301)
    d_pre_b = boot_cluster(bs.pre_cum.to_numpy(), bs.prefix.to_numpy(), 302)
    d_post_b = boot_cluster(bs.r20.to_numpy(), bs.prefix.to_numpy(), 303)
    diff_s = d_post_s["point"] - d_pre_s["point"]
    diff_b = d_post_b["point"] - d_pre_b["point"]
    did = diff_s - diff_b
    print(f"  spike  pre={d_pre_s['point']:+.5f} post={d_post_s['point']:+.5f} diff={diff_s:+.5f}")
    print(f"  base   pre={d_pre_b['point']:+.5f} post={d_post_b['point']:+.5f} diff={diff_b:+.5f}")
    print(f"  DiD = {did:+.5f}")
    prepost = {"spike_pre": d_pre_s, "spike_post": d_post_s,
               "base_pre": d_pre_b, "base_post": d_post_b, "did": did}

    # ---- N 敏感性 ----
    print("\n=== N 敏感性（z0=2, h=20）===")
    n_sens = {}
    for N in N_GRID:
        e = build_events(frames, lookback_n=N, z0=Z0_MAIN)
        s = e[e.group == "spike"]
        b = e[e.group == "baseline"]
        if len(s) < 20:
            continue
        m = boot_diff(s, b, "r20", seed=400 + N)
        a = boot_diff(s, b, "abs20", seed=500 + N)
        # ES5
        es_s = s.r20[s.r20 <= s.r20.quantile(0.05)].mean()
        es_b = b.r20[b.r20 <= b.r20.quantile(0.05)].mean()
        row = {"n_spike": int(len(s)), "n_base": int(len(b)),
               "r20": m, "abs20": a, "es5_delta": float(es_s - es_b)}
        n_sens[str(N)] = row
        print(f"  N={N:>3} n_s={len(s):>4} meanΔ={m['delta']:+.6f} p={m['p_two']:.3f}  "
              f"absΔ={a['delta']:+.6f} p={a['p_two']:.3f}  ES5Δ={es_s - es_b:+.5f}")

    # ---- 阈值敏感性 ----
    print("\n=== z0 敏感性（N=20, h=20）===")
    z_sens = {}
    for z0 in Z0_GRID:
        e = build_events(frames, lookback_n=20, z0=z0)
        s = e[e.group == "spike"]
        b = e[e.group == "baseline"]
        if len(s) < 15:
            continue
        m = boot_diff(s, b, "r20", seed=600 + int(z0 * 10))
        a = boot_diff(s, b, "abs20", seed=700 + int(z0 * 10))
        es_s = s.r20[s.r20 <= s.r20.quantile(0.05)].mean()
        es_b = b.r20[b.r20 <= b.r20.quantile(0.05)].mean()
        z_sens[str(z0)] = {"n_spike": int(len(s)), "r20": m, "abs20": a,
                            "es5_delta": float(es_s - es_b)}
        print(f"  z0={z0} n_s={len(s):>4} meanΔ={m['delta']:+.6f} p={m['p_two']:.3f}  "
              f"absΔ={a['delta']:+.6f}  ES5Δ={es_s - es_b:+.5f}")

    # ---- 跨品种 sign 一致性（用 N=20, z0=2 的主规格） ----
    print("\n=== 跨品种 sign（N=20, z0=2, h=20）===")
    by_pfx = {}
    for pfx, sub in sp.groupby("prefix"):
        bsub = bs[bs.prefix == pfx]
        if len(sub) < 5 or len(bsub) < 5:
            continue
        by_pfx[pfx] = {
            "sector": sub.sector.iloc[0],
            "n_spike": int(len(sub)),
            "mean_delta": float(sub.r20.mean() - bsub.r20.mean()),
            "abs_delta": float(sub.abs20.mean() - bsub.abs20.mean()),
        }
        print(f"  {pfx:>4} ({by_pfx[pfx]['sector']:<11}) n_s={len(sub):>3} "
              f"meanΔ={by_pfx[pfx]['mean_delta']:+.5f}  absΔ={by_pfx[pfx]['abs_delta']:+.6f}")
    if by_pfx:
        mean_sign = np.mean([np.sign(v["mean_delta"]) for v in by_pfx.values()])
        abs_sign = np.mean([np.sign(v["abs_delta"]) for v in by_pfx.values()])
        print(f"  sign retention (mean): {sum(1 for v in by_pfx.values() if v['mean_delta']>0)}/{len(by_pfx)}")
        print(f"  sign retention (abs) : {sum(1 for v in by_pfx.values() if v['abs_delta']>0)}/{len(by_pfx)}")

    out.update({
        "horizon": horizon, "tail_h20": t20, "prepost": prepost,
        "n_sensitivity": n_sens, "z_sensitivity": z_sens, "by_prefix": by_pfx,
    })
    return out


def main() -> int:
    out_dir = REPO_ROOT / "project_data" / "research" / "volume-spike-regime-shift"
    out_dir.mkdir(parents=True, exist_ok=True)
    print("Building daily continuous series from 1h CSV...")
    frames = build_continuous_by_prefix()
    for pfx, df in frames.items():
        print(f"  {pfx:>4}: {len(df)} daily bars  {df.session_date.iloc[0].date()} -> {df.session_date.iloc[-1].date()}")
    if len(frames) < 5:
        print(f"[ABORT] only {len(frames)} prefixes with ≥{MIN_DAILY_BARS} daily bars")
        return 1
    summary = run_main(frames)
    (out_dir / "daily_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str)
    )
    print(f"\n[OK] {out_dir / 'daily_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
