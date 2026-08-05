"""
1h volume spike 推荐规格时间 OOS。
主规格：N=80 H=120 z0∈{1.5,2.0}；按合约内 bar 顺序前 70%/后 30% 切。
同时验证：
- 无条件 spike vs baseline Δr^H；
- pre_cum 条件（Q4: pre_cum20 > +1% 或 IS 切点）：IS 上确定 pre_cum 切点，OOS 冻结；
- 跨 prefix sign 一致性；
- 对照 N=120 H=120 z0=2（之前已测全样本，这里切分复现）。
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
MIN_BARS = 500
N_BOOT = 2000

SECTORS = {
    "agri": {"m","c","cs","p","CF","SR"},
    "black": {"rb","i","hc","j","jm"},
    "metal": {"cu","al","zn","ni","pb","au","ag"},
    "energy_chem": {"sc","TA","MA","pp","v","eg","eb","fg","sa","fu","bu"},
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


def build_split_events(N, H, z0, z_base=0.5):
    """返回 IS/OOS 两个 DataFrame（按合约前 70/后 30 切，切点在每合约内独立）。"""
    is_recs, oos_recs = [], []
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
        df["z"] = z_by_hour(df, N)
        cut = int(n * 0.7)
        r = df.lr.to_numpy()
        z = df.z.to_numpy()
        atr = df.atr.to_numpy()
        sess = df.session_date.to_numpy()
        for t in range(N + H + 1, n - H):
            zv = z[t]
            if not math.isfinite(zv):
                continue
            a = atr[t]
            if not (math.isfinite(a) and a > 0):
                continue
            post = r[t+1:t+1+H]
            pre = r[t-20:t]
            if not (np.all(np.isfinite(post)) and np.all(np.isfinite(pre))):
                continue
            if zv >= z0:
                grp = "spike"
            elif abs(zv) < z_base:
                grp = "baseline"
            else:
                continue
            rec = {
                "symbol": symbol, "prefix": prefix, "sector": sector_of(prefix),
                "session_date": str(sess[t]),
                "group": grp, "rH": float(post.sum()),
                "pre_cum20": float(pre.sum()),
                "z": float(zv),
            }
            if t < cut:
                is_recs.append(rec)
            else:
                oos_recs.append(rec)
    return pd.DataFrame(is_recs), pd.DataFrame(oos_recs)


def boot_diff(sp, bs, col="rH", seed=42):
    def cid(d):
        keys = sorted({(s, sd) for s, sd in zip(d.symbol, d.session_date)})
        km = {k: i for i, k in enumerate(keys)}
        return np.array([km[(s, sd)] for s, sd in zip(d.symbol, d.session_date)], dtype=np.int32)
    cs, cb = cid(sp), cid(bs)
    s, b = sp[col].to_numpy(), bs[col].to_numpy()
    def bm(vals, c, rng):
        nc = int(c.max()) + 1
        sums = np.bincount(c, weights=vals, minlength=nc)
        cnt = np.bincount(c, minlength=nc).astype(np.float64)
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
        "n_clusters": int(len(np.unique(cs))),
        "spike_mean": float(s.mean()),
        "spike_pct_neg": float((s < 0).mean()),
        "base_mean": float(b.mean()),
    }


def sign_by_prefix(sp, bs):
    rows = []
    for pfx in sorted(sp.prefix.unique()):
        s = sp[sp.prefix == pfx]
        b = bs[bs.prefix == pfx]
        if len(s) < 3 or len(b) < 5:
            continue
        rows.append({
            "prefix": pfx, "n_spike": len(s),
            "delta": float(s.rH.mean() - b.rH.mean()),
            "spike_mean": float(s.rH.mean()),
            "base_mean": float(b.rH.mean()),
        })
    return pd.DataFrame(rows)


def run_config(N, H, z0, pre_thresh_is=None):
    print(f"\n{'='*64}\n  N={N} H={H} z0={z0}\n{'='*64}")
    is_ev, oos_ev = build_split_events(N, H, z0)
    res = {"config": {"N": N, "H": H, "z0": z0}}

    for split, ev in [("is", is_ev), ("oos", oos_ev)]:
        sp = ev[ev.group == "spike"]
        bs = ev[ev.group == "baseline"]
        d = boot_diff(sp, bs, seed=hash((N, H, z0, split)) % 2**30)
        res[split] = d
        print(f"  [{split:<3}] n_s={d['n_spike']:>4} n_cls={d['n_clusters']:>3}  "
              f"Δ={d['delta']:+.5f} CI=[{d['ci_lo']:+.5f},{d['ci_hi']:+.5f}] p={d['p_two']:.4f}  "
              f"spike%neg={d['spike_pct_neg']:.2f}")

    # prefix sign
    for split, ev in [("is", is_ev), ("oos", oos_ev)]:
        sp = ev[ev.group == "spike"]
        bs = ev[ev.group == "baseline"]
        sdf = sign_by_prefix(sp, bs)
        if len(sdf):
            neg_rate = float((sdf.delta < 0).mean())
            print(f"  [{split}] prefix sign negative: {(sdf.delta<0).sum()}/{len(sdf)} = {neg_rate:.0%}")
            print(sdf.to_string(index=False, float_format=lambda x: f"{x:+.5f}"))
            res[f"prefix_{split}"] = sdf.to_dict("records")
            res[f"prefix_neg_rate_{split}"] = neg_rate

    # pre_cum 条件
    # IS 上确定切点：spike 组 pre_cum20 的 80% 分位（≈Q4 下界），OOS 冻结
    sp_is = is_ev[is_ev.group == "spike"]
    if pre_thresh_is is None:
        pre_thresh = float(sp_is.pre_cum20.quantile(0.80))
    else:
        pre_thresh = pre_thresh_is
    res["pre_thresh_q80_is"] = pre_thresh
    print(f"\n  pre_cum20 IS Q80 切点 = {pre_thresh:+.5f}（≈+{pre_thresh*100:.2f}%）")
    for split, ev in [("is", is_ev), ("oos", oos_ev)]:
        sp = ev[(ev.group == "spike") & (ev.pre_cum20 >= pre_thresh)]
        bs = ev[ev.group == "baseline"]
        if len(sp) < 10:
            print(f"  [{split}] pre_cum condition n_s={len(sp)} too small")
            continue
        d = boot_diff(sp, bs, seed=hash(("pre", N, H, z0, split)) % 2**30)
        res[f"precond_{split}"] = d
        print(f"  [{split} PRE_Q4] n_s={d['n_spike']:>3}  Δ={d['delta']:+.5f} "
              f"CI=[{d['ci_lo']:+.5f},{d['ci_hi']:+.5f}] p={d['p_two']:.4f}  "
              f"spike%neg={d['spike_pct_neg']:.2f}")
    return res


def main():
    out_dir = REPO_ROOT / "project_data/research/volume-spike-regime-shift"
    results = {}
    # 主推荐规格
    results["N80_H120_z1.5"] = run_config(80, 120, 1.5)
    results["N80_H120_z2.0"] = run_config(80, 120, 2.0)
    # 对照：N=120 H=120 z0=2（之前全样本通过 OOS）
    results["N120_H120_z2.0"] = run_config(120, 120, 2.0)
    # 对照：N=60 H=120 z0=2（更短 N 更多样本）
    results["N60_H120_z2.0"] = run_config(60, 120, 2.0)

    (out_dir / "1h_oos_main.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False, default=str))
    print(f"\n[OK] {out_dir / '1h_oos_main.json'}")


if __name__ == "__main__":
    main()
