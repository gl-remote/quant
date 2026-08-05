"""
1h 强信号稳健性验证：calibrate_1h 发现 z_by_hour N=120 H=120 和 pctrank N=60 H=60 有强负漂移。
本脚本：
1. 对两个强口径做时间 OOS（每合约前 70% / 后 30%）；
2. LOPO prefix sign 保留率；
3. pre-trend 匹配（排除前趋势驱动）；
4. 价格条件（spike bar 涨/跌）拆分。
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
MIN_BARS = 420
N_BOOT = 2000


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


def build_events(kind: str, N: int, H: int, thresh: float,
                 split: str | None = None) -> pd.DataFrame:
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
        df = load_df(p)
        n = len(df)
        if n < N + H + 50:
            continue
        v = df.volume
        hour = df.hour
        if kind == "z_by_hour":
            mu = v.groupby(hour).shift(1).groupby(hour).transform(
                lambda s: s.rolling(N, min_periods=N).mean())
            sd = v.groupby(hour).shift(1).groupby(hour).transform(
                lambda s: s.rolling(N, min_periods=N).std(ddof=1))
            df["f"] = (v - mu) / sd
        elif kind == "pctrank_by_hour":
            def pr(s):
                return s.rolling(N, min_periods=N).apply(
                    lambda x: (x[-1] >= x).mean(), raw=False)
            df["f"] = v.groupby(hour).shift(1).groupby(hour).transform(pr)
        r = df.lr.to_numpy()
        f = df.f.to_numpy()
        atr = df.atr.to_numpy()
        sess = df.session_date.to_numpy()
        cut = int(n * 0.7)
        rng = range(N + H + 1, n - H)
        if split == "is":
            rng = range(N + H + 1, min(cut, n - H))
        elif split == "oos":
            rng = range(max(N + H + 1, cut), n - H)
        for t in rng:
            fv = f[t]
            if not math.isfinite(fv):
                continue
            a = atr[t]
            if not (math.isfinite(a) and a > 0):
                continue
            pre = r[t - H:t]
            post = r[t + 1:t + 1 + H]
            if not (np.all(np.isfinite(pre)) and np.all(np.isfinite(post))):
                continue
            is_spike = fv >= thresh
            is_base = abs(fv) < 0.5 if kind.startswith("z") else (0.4 < fv < 0.6)
            if not (is_spike or is_base):
                continue
            recs.append({
                "symbol": symbol, "prefix": prefix,
                "session_date": str(sess[t]), "t": t,
                "group": "spike" if is_spike else "baseline",
                "rH": float(post.sum()),
                "pre_cum": float(pre.sum()),
                "pre_abs": float(np.abs(pre).mean()),
                "spike_ret": float(r[t]),
                "spike_bar_atr": float(abs(r[t]) / a),
            })
    return pd.DataFrame(recs)


def boot_diff(sp, bs, col="rH", seed=42):
    def cluster_arr(d):
        keys = sorted({(s, sd) for s, sd in zip(d.symbol, d.session_date)})
        km = {k: i for i, k in enumerate(keys)}
        return np.array([km[(s, sd)] for s, sd in zip(d.symbol, d.session_date)], dtype=np.int32)
    cs, cb = cluster_arr(sp), cluster_arr(bs)
    s, b = sp[col].to_numpy(), bs[col].to_numpy()

    def bm(vals, cid, rng):
        nc = int(cid.max()) + 1
        sums = np.bincount(cid, weights=vals, minlength=nc)
        cnt = np.bincount(cid, minlength=nc).astype(np.float64)
        idx = rng.integers(0, nc, size=(N_BOOT, nc))
        return sums[idx].sum(axis=1) / cnt[idx].sum(axis=1)
    rng1 = np.random.default_rng(seed)
    rng2 = np.random.default_rng(seed + 1)
    diff = bm(s, cs, rng1) - bm(b, cb, rng2)
    p = float(min(1, 2 * min((diff <= 0).mean(), (diff >= 0).mean())))
    return {
        "delta": float(s.mean() - b.mean()),
        "ci_lo": float(np.quantile(diff, 0.025)),
        "ci_hi": float(np.quantile(diff, 0.975)),
        "p_two": p,
        "n_spike": int(len(sp)), "n_base": int(len(bs)),
    }


def lopo_sign(ev):
    prefixes = sorted(ev.prefix.unique())
    rows = []
    for hold in prefixes:
        is_ev = ev[ev.prefix != hold]
        oos_ev = ev[ev.prefix == hold]
        is_sp = is_ev[is_ev.group == "spike"]
        is_bs = is_ev[is_ev.group == "baseline"]
        oos_sp = oos_ev[oos_ev.group == "spike"]
        oos_bs = oos_ev[oos_ev.group == "baseline"]
        if len(oos_sp) < 3 or len(oos_bs) < 5:
            continue
        rows.append({
            "prefix": hold, "n_spike": len(oos_sp),
            "is_delta": float(is_sp.rH.mean() - is_bs.rH.mean()),
            "oos_delta": float(oos_sp.rH.mean() - oos_bs.rH.mean()),
        })
    df = pd.DataFrame(rows)
    same = (np.sign(df.is_delta) == np.sign(df.oos_delta)).sum()
    return df, same / len(df) if len(df) else float("nan")


def pretrend_match(sp, bs):
    """pre_cum 最近邻匹配 1:5。"""
    sv, bv = [], []
    for _, r in sp.iterrows():
        cand = bs[bs.prefix != r.prefix].copy()
        cand["d"] = (cand.pre_cum - r.pre_cum).abs()
        cand = cand[cand.d < 0.02].nsmallest(5, "d")
        if len(cand):
            sv.extend([r.rH] * len(cand))
            bv.extend(cand.rH.tolist())
    s, b = np.array(sv), np.array(bv)
    diff = s - b
    rng = np.random.default_rng(99)
    boot = [diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(N_BOOT)]
    return {
        "n_pairs": int(len(diff)),
        "delta": float(diff.mean()),
        "ci_lo": float(np.quantile(boot, 0.025)),
        "ci_hi": float(np.quantile(boot, 0.975)),
    }


def run_config(kind, N, H, thresh, label):
    print(f"\n{'='*60}")
    print(f"  {label}: {kind} N={N} H={H} thresh={thresh}")
    print('='*60)
    res = {"config": {"kind": kind, "N": N, "H": H, "thresh": thresh}}

    # full
    ev = build_events(kind, N, H, thresh, split=None)
    sp = ev[ev.group == "spike"]
    bs = ev[ev.group == "baseline"]
    full = boot_diff(sp, bs, seed=1)
    print(f"  full:    n_s={full['n_spike']} Δ={full['delta']:+.5f} "
          f"CI=[{full['ci_lo']:+.5f},{full['ci_hi']:+.5f}] p={full['p_two']:.4f}")
    res["full"] = full

    # time OOS
    oos_rows = {}
    for split in ("is", "oos"):
        e = build_events(kind, N, H, thresh, split=split)
        s, b = e[e.group == "spike"], e[e.group == "baseline"]
        if len(s) >= 10 and len(b) >= 30:
            d = boot_diff(s, b, seed=10 + hash(split) % 100)
            oos_rows[split] = d
            print(f"  {split:<5}: n_s={d['n_spike']} Δ={d['delta']:+.5f} "
                  f"CI=[{d['ci_lo']:+.5f},{d['ci_hi']:+.5f}] p={d['p_two']:.4f}")
    res["time_oos"] = oos_rows

    # LOPO
    lopo_df, retention = lopo_sign(ev)
    print(f"  LOPO sign retention: {retention:.0%}")
    print(lopo_df.to_string(index=False, float_format=lambda x: f"{x:+.5f}"))
    res["lopo_retention"] = float(retention)
    res["lopo"] = lopo_df.to_dict("records")

    # pretrend match
    pm = pretrend_match(sp, bs)
    print(f"  pretrend match: n_pairs={pm['n_pairs']} Δ={pm['delta']:+.5f} "
          f"CI=[{pm['ci_lo']:+.5f},{pm['ci_hi']:+.5f}]")
    res["pretrend_match"] = pm

    # spike bar 颜色拆分
    for cond, label2 in [
        ((sp.spike_ret > 0), "spike_up"),
        ((sp.spike_ret < 0), "spike_dn"),
        ((sp.spike_bar_atr >= 0.5), "big_bar(>=0.5ATR)"),
        ((sp.spike_bar_atr < 0.5), "small_bar(<0.5ATR)"),
    ]:
        sub = sp[cond]
        if len(sub) < 10:
            continue
        d = boot_diff(sub, bs, seed=hash(label2) % 2**30)
        print(f"    {label2:<20} n_s={d['n_spike']:>4} Δ={d['delta']:+.5f} p={d['p_two']:.3f}")
        res[f"cond_{label2}"] = d

    return res


def main():
    out_dir = REPO_ROOT / "project_data/research/volume-spike-regime-shift"
    results = {}
    results["z_N120_H120"] = run_config("z_by_hour", 120, 120, 2.0, "z_by_hour N=120 H=120")
    results["z_N60_H60"] = run_config("z_by_hour", 60, 60, 2.0, "z_by_hour N=60 H=60")
    results["pct_N60_H60"] = run_config("pctrank_by_hour", 60, 60, 0.95, "pctrank N=60 H=60 ≥0.95")

    (out_dir / "1h_strong_signal.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False, default=str))
    print(f"\n[OK] {out_dir / '1h_strong_signal.json'}")


if __name__ == "__main__":
    main()
