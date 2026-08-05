"""
文件级元信息：
- 创建背景：Stage 4 发现左尾效应主要由 sc（原油）驱动，LOPO ES5 保留率仅 50%。
  Stage 5/6/7 一次性完成：
  5: pre-trend × spike 交互回归（OLS + cluster bootstrap CI）；
  6: 尾部非对称来源（板块/spike 颜色/hour/ATR 档拆分）；
  7: 规格稳健性（阈值网格、lookback N、缩量对照）。
- 用途：决定哪个子结论能保留，哪个需要降级。
"""

from __future__ import annotations

import json
import math
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
Z0_MAIN = 2.0
Z_BASELINE = 0.5
H = 20
MIN_BARS = 420
N_BOOT = 2000
BOOT_SEED = 20260805

# 板块分组（按 prefix）
SECTORS = {
    "agri": {"m", "c", "cs", "p", "a", "b", "y", "jd"},
    "black": {"rb", "i", "hc", "j", "jm"},
    "metal": {"cu", "al", "zn", "ni", "pb", "au", "ag"},
    "energy_chem": {"sc", "TA", "MA", "pp", "v", "eg", "eb", "fg", "sa", "SR", "CF", "fu", "bu"},
}


def sector_of(prefix: str) -> str:
    for s, pset in SECTORS.items():
        if prefix in pset:
            return s
    return "other"


def load_df(path: Path, lookback_n: int = 20) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    h, l, c = df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
    pc = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum.reduce([h - l, np.abs(h - pc), np.abs(l - pc)])
    df["atr"] = pd.Series(tr).rolling(ATR_PERIOD, min_periods=ATR_PERIOD).mean().to_numpy()
    df["lr"] = np.log(df["close"]).diff()
    v = df["volume"]
    hour = df["datetime"].dt.hour
    mu = v.groupby(hour).shift(1).groupby(hour).transform(
        lambda s: s.rolling(lookback_n, min_periods=lookback_n).mean()
    )
    sd = v.groupby(hour).shift(1).groupby(hour).transform(
        lambda s: s.rolling(lookback_n, min_periods=lookback_n).std(ddof=1)
    )
    df["z"] = (v - mu) / sd
    df["session_date"] = df["datetime"].dt.date
    df["hour"] = hour
    return df


def build_events(lookback_n: int = 20, z0: float = Z0_MAIN,
                 abs_baseline: float = Z_BASELINE,
                 include_volume_shrink: bool = False) -> pd.DataFrame:
    recs = []
    for p in sorted(market_csv_dir().glob("*.1h.csv")):
        try:
            head = pd.read_csv(p, usecols=["datetime"])
        except Exception:
            continue
        if len(head) < MIN_BARS:
            continue
        symbol = p.name.split(".tqsdk.1h.csv")[0]
        prefix = extract_contract_prefix(symbol) or ""
        df = load_df(p, lookback_n=lookback_n)
        n = len(df)
        r = df["lr"].to_numpy()
        z = df["z"].to_numpy()
        atr = df["atr"].to_numpy()
        sess = df["session_date"].to_numpy()
        hour = df["hour"].to_numpy()
        for t in range(H, n - H):
            zv = z[t]
            if not math.isfinite(zv):
                continue
            if zv >= z0:
                grp = "spike"
            elif include_volume_shrink and zv <= -z0:
                grp = "shrink"
            elif abs(zv) < abs_baseline:
                grp = "baseline"
            else:
                continue
            a = atr[t]
            if not (math.isfinite(a) and a > 0):
                continue
            pre = r[t - H : t]
            post = r[t + 1 : t + 1 + H]
            if not (np.all(np.isfinite(pre)) and np.all(np.isfinite(post))):
                continue
            cp = np.cumsum(post)
            recs.append({
                "symbol": symbol, "prefix": prefix, "session_date": sess[t],
                "sector": sector_of(prefix), "hour": int(hour[t]),
                "group": grp,
                "spike_ret": float(r[t]),
                "pre_cum": float(pre.sum()),
                "pre_abs": float(np.abs(pre).mean()),
                "post_cum": float(post.sum()),
                "post_abs": float(np.abs(post).mean()),
                "path_disp": float(cp.std(ddof=1)),
                "max_fav": float(cp.max()),
                "max_adv": float(cp.min()),
                "entry_atr": float(a),
                "z": float(zv),
            })
    return pd.DataFrame(recs)


def cid(df: pd.DataFrame) -> np.ndarray:
    keys = sorted({(s, d) for s, d in zip(df["symbol"], df["session_date"])})
    km = {k: i for i, k in enumerate(keys)}
    return np.array([km[(s, d)] for s, d in zip(df["symbol"], df["session_date"])], dtype=np.int32)


def cluster_boot_mean(vals: np.ndarray, c: np.ndarray, seed: int) -> dict[str, float]:
    nc = int(c.max()) + 1
    sums = np.bincount(c, weights=vals, minlength=nc)
    cnt = np.bincount(c, minlength=nc).astype(np.float64)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, nc, size=(N_BOOT, nc), dtype=np.int32)
    boot = sums[idx].sum(axis=1) / cnt[idx].sum(axis=1)
    return {"point": float(vals.mean()),
            "ci_lo": float(np.quantile(boot, 0.025)),
            "ci_hi": float(np.quantile(boot, 0.975))}


# ─────────── Stage 5: 交互回归 ───────────
def stage5_interaction(ev: pd.DataFrame) -> dict[str, Any]:
    """path_disp ~ β0 + β1 spike + β2|pre_cum| + β3 spike×|pre_cum| + β4 pre_abs + β5 atr_pct。
    这里用 OLS + cluster bootstrap 系数 CI。"""
    d = ev.copy()
    d["spike"] = (d.group == "spike").astype(float)
    d["abs_pre"] = d.pre_cum.abs()
    d["interact"] = d.spike * d.abs_pre
    d["atr_pct"] = d.groupby("symbol").entry_atr.rank(pct=True)
    X = np.column_stack([
        np.ones(len(d)), d.spike, d.abs_pre, d.interact, d.pre_abs, d.atr_pct,
    ])
    y = d.path_disp.to_numpy()
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    names = ["const", "spike", "abs_pre", "spike_x_abs_pre", "pre_abs", "atr_pct"]

    # cluster bootstrap：按 (symbol, session_date) 整簇重抽
    c = cid(d)
    nc = int(c.max()) + 1
    rng = np.random.default_rng(BOOT_SEED)
    boot_betas = []
    for _ in range(N_BOOT):
        idx = rng.integers(0, nc, size=nc)
        rows = np.concatenate([np.where(c == i)[0] for i in idx])
        try:
            bb = np.linalg.lstsq(X[rows], y[rows], rcond=None)[0]
            boot_betas.append(bb)
        except np.linalg.LinAlgError:
            continue
    bb = np.array(boot_betas)
    result = {"coef": {}, "n": int(len(d))}
    for i, name in enumerate(names):
        result["coef"][name] = {
            "point": float(beta[i]),
            "ci_lo": float(np.quantile(bb[:, i], 0.025)),
            "ci_hi": float(np.quantile(bb[:, i], 0.975)),
        }

    # 五分位交互验证：按 |pre_cum| 切 5 桶，每桶内 spike vs baseline 的 path_disp Δ
    d["abs_pre_q"] = pd.qcut(d.abs_pre, 5, labels=False, duplicates="drop")
    by_q = []
    for q, sub in d.groupby("abs_pre_q"):
        s = sub[sub.group == "spike"]
        b = sub[sub.group == "baseline"]
        if len(s) < 10 or len(b) < 10:
            continue
        by_q.append({
            "q": int(q),
            "abs_pre_mean": float(sub.abs_pre.mean()),
            "n_spike": int(len(s)),
            "delta_path_disp": float(s.path_disp.mean() - b.path_disp.mean()),
        })
    result["by_abs_pre_quintile"] = by_q
    return result


# ─────────── Stage 6: 尾部非对称来源 ───────────
def stage6_tail_source(ev: pd.DataFrame) -> dict[str, Any]:
    """在不同切片下算 spike vs baseline 的 ES5 差。"""
    def es_diff(sub: pd.DataFrame) -> dict[str, Any]:
        sp = sub[sub.group == "spike"]
        bs = sub[sub.group == "baseline"]
        if len(sp) < 15 or len(bs) < 30:
            return {"n_spike": int(len(sp)), "n_base": int(len(bs))}
        es_s = sp.post_cum.quantile(0.05)
        es_b = bs.post_cum.quantile(0.05)
        es5_s = sp.post_cum[sp.post_cum <= sp.post_cum.quantile(0.05)].mean()
        es5_b = bs.post_cum[bs.post_cum <= bs.post_cum.quantile(0.05)].mean()
        return {
            "n_spike": int(len(sp)), "n_base": int(len(bs)),
            "var5_delta": float(es_s - es_b),
            "es5_delta": float(es5_s - es5_b),
            "mean_delta": float(sp.post_cum.mean() - bs.post_cum.mean()),
        }

    result: dict[str, Any] = {"by_sector": {}, "by_spike_color": {}, "by_hour": {}, "by_atr": {}}
    for sec, sub in ev.groupby("sector"):
        result["by_sector"][sec] = es_diff(sub)
    # spike bar 颜色只在 spike 组内分
    for color, mask in (("spike_up", ev.spike_ret > 0), ("spike_dn", ev.spike_ret < 0)):
        sub = ev[(ev.group == "baseline") | ((ev.group == "spike") & mask)]
        result["by_spike_color"][color] = es_diff(sub)
    # hour：21（夜开）、9（日开）、其他
    def h_bucket(h: int) -> str:
        if h == 21: return "21_night_open"
        if h == 9: return "9_day_open"
        if h in (10, 13, 14): return "intraday"
        return "other"
    ev["h_bkt"] = ev.hour.apply(h_bucket)
    for bkt, sub in ev.groupby("h_bkt"):
        result["by_hour"][bkt] = es_diff(sub)
    # ATR 三分位
    ev["atr_q"] = pd.qcut(ev.entry_atr, 3, labels=["low", "mid", "high"], duplicates="drop")
    for q, sub in ev.groupby("atr_q", observed=True):
        result["by_atr"][str(q)] = es_diff(sub)
    return result


# ─────────── Stage 7: 稳健性 ───────────
def stage7_robustness(ev_default: pd.DataFrame) -> dict[str, Any]:
    result: dict[str, Any] = {}

    # 阈值网格（N=20）
    result["by_threshold"] = {}
    for z0 in (1.5, 2.0, 2.5, 3.0, 4.0):
        e = build_events(lookback_n=20, z0=z0)
        sp = e[e.group == "spike"]
        bs = e[e.group == "baseline"]
        if len(sp) < 20:
            continue
        cs, cb = cid(sp), cid(bs)
        # tail diff via bootstrap
        nc_s, nc_b = int(cs.max()) + 1, int(cb.max()) + 1
        cl_s = [sp.post_cum.to_numpy()[cs == k] for k in range(nc_s)]
        cl_b = [bs.post_cum.to_numpy()[cb == k] for k in range(nc_b)]
        rng = np.random.default_rng(BOOT_SEED + int(z0 * 100))
        is_ = rng.integers(0, nc_s, size=(N_BOOT, nc_s))
        ib = rng.integers(0, nc_b, size=(N_BOOT, nc_b))
        d_es5, d_mean, d_pd = [], [], []
        for i in range(N_BOOT):
            sv = np.concatenate([cl_s[k] for k in is_[i]])
            bv = np.concatenate([cl_b[k] for k in ib[i]])
            qs, qb = np.quantile(sv, 0.05), np.quantile(bv, 0.05)
            d_es5.append(sv[sv <= qs].mean() - bv[bv <= qb].mean())
            d_mean.append(sv.mean() - bv.mean())
        result["by_threshold"][str(z0)] = {
            "n_spike": int(len(sp)),
            "n_base": int(len(bs)),
            "mean_delta": float(np.mean(d_mean)),
            "es5_delta": float(np.mean(d_es5)),
            "es5_ci": [float(np.quantile(d_es5, 0.025)), float(np.quantile(d_es5, 0.975))],
        }

    # lookback N
    result["by_lookback"] = {}
    for N in (20, 60, 120):
        e = build_events(lookback_n=N, z0=Z0_MAIN)
        sp = e[e.group == "spike"]
        bs = e[e.group == "baseline"]
        if len(sp) < 30:
            continue
        es5_s = sp.post_cum[sp.post_cum <= sp.post_cum.quantile(0.05)].mean()
        es5_b = bs.post_cum[bs.post_cum <= bs.post_cum.quantile(0.05)].mean()
        result["by_lookback"][str(N)] = {
            "n_spike": int(len(sp)), "n_base": int(len(bs)),
            "es5_delta": float(es5_s - es5_b),
            "mean_delta": float(sp.post_cum.mean() - bs.post_cum.mean()),
        }

    # 缩量对照
    e = build_events(lookback_n=20, z0=1.0, include_volume_shrink=True)
    shr = e[e.group == "shrink"]
    bs = e[e.group == "baseline"]
    if len(shr) >= 20:
        result["shrink_vs_baseline"] = {
            "n_shrink": int(len(shr)), "n_base": int(len(bs)),
            "mean_delta": float(shr.post_cum.mean() - bs.post_cum.mean()),
            "path_disp_delta": float(shr.path_disp.mean() - bs.path_disp.mean()),
        }
    return result


def main() -> int:
    out_dir = REPO_ROOT / "project_data" / "research" / "volume-spike-regime-shift"
    print("Building events (N=20, z0=2.0)...")
    ev = build_events()
    ev.to_parquet(out_dir / "stage567_events.parquet", index=False)
    print(f"events={len(ev)}")

    print("\n=== Stage 5: interaction regression (path_disp) ===")
    s5 = stage5_interaction(ev)
    for k, v in s5["coef"].items():
        print(f"  {k:<18} β={v['point']:+.6f} CI=[{v['ci_lo']:+.6f},{v['ci_hi']:+.6f}]")
    print("  by |pre_cum| quintile (Δpath_disp spike-base):")
    for q in s5["by_abs_pre_quintile"]:
        print(f"    q{q['q']}: n_s={q['n_spike']} abs_pre={q['abs_pre_mean']:.5f} Δ={q['delta_path_disp']:+.6f}")

    print("\n=== Stage 6: tail asymmetry sources (ES5 Δ spike-base) ===")
    s6 = stage6_tail_source(ev)
    for cat_name, cat in s6.items():
        print(f"  -- {cat_name} --")
        for k, v in cat.items():
            if "es5_delta" in v:
                print(f"    {k:<20} n_s={v['n_spike']:>4} ES5Δ={v['es5_delta']:+.5f} "
                      f"VaR5Δ={v.get('var5_delta',float('nan')):+.5f} meanΔ={v.get('mean_delta',float('nan')):+.5f}")

    print("\n=== Stage 7: robustness ===")
    s7 = stage7_robustness(ev)
    print("  by threshold (N=20):")
    for z0, v in s7["by_threshold"].items():
        print(f"    z0={z0} n_s={v['n_spike']} meanΔ={v['mean_delta']:+.5f} "
              f"ES5Δ={v['es5_delta']:+.5f} CI={v['es5_ci']}")
    print("  by lookback (z0=2):")
    for N, v in s7["by_lookback"].items():
        print(f"    N={N:>3} n_s={v['n_spike']} meanΔ={v['mean_delta']:+.5f} ES5Δ={v['es5_delta']:+.5f}")
    if "shrink_vs_baseline" in s7:
        x = s7["shrink_vs_baseline"]
        print(f"  shrink (Z≤-1, n={x['n_shrink']}) vs baseline: "
              f"meanΔ={x['mean_delta']:+.5f} path_dispΔ={x['path_disp_delta']:+.6f}")

    summary = {"stage5": s5, "stage6": s6, "stage7": s7}
    (out_dir / "stage567_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str)
    )
    print(f"\n[OK] {out_dir / 'stage567_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
