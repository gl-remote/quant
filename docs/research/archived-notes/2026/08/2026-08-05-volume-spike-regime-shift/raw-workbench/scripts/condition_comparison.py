"""
比较 MADEV120 增强条件 vs pre_cum 基线条件。
基线：z>=1.5, s_pre>=0.10（高 s 层）
候选 A：z>=1.5, MADEV120 >= 阈值（在高 s 层内）
候选 B：z>=1.5, MADEV60 >= 阈值
候选 C：z>=1.5, MRET100 >= 阈值
候选 D：z>=1.5, MADEV120 高 50% + pre_cum 高 50%（双高）
对每个条件计算 spike 后 100 bar 均值、%neg、cluster bootstrap CI。
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


def build():
    recs = []
    for p in sorted(market_csv_dir().glob("*.1h.csv")):
        try: head = pd.read_csv(p, usecols=["datetime"])
        except: continue
        if len(head) < 420: continue
        sym = p.name.split(".tqsdk.1h.csv")[0]
        pfx = extract_contract_prefix(sym) or ""
        d = load(p)
        c = d.close; r = d.lr.to_numpy(); z = d.z.to_numpy()
        ma120 = c.rolling(120).mean().to_numpy()
        ma60 = c.rolling(60).mean().to_numpy()
        n = len(d)
        for t in range(N+W+1, n-W):
            zv = z[t]
            if not math.isfinite(zv): continue
            if zv < 1.5: continue
            pre = r[t-100:t]
            if not np.all(np.isfinite(pre)): continue
            s_mu, s_sd = pre.mean(), pre.std(ddof=1)
            if s_sd <= 0: continue
            s_pre = s_mu/s_sd
            if not math.isfinite(ma120[t]) or not math.isfinite(ma60[t]): continue
            madev120 = (c.to_numpy()[t] - ma120[t]) / ma120[t]
            madev60 = (c.to_numpy()[t] - ma60[t]) / ma60[t]
            mret100 = c.to_numpy()[t]/c.to_numpy()[t-100]-1
            pre_cum = float(pre.sum())
            recs.append(dict(
                sym=sym, pfx=pfx, t=t, z=float(zv),
                s_pre=float(s_pre), pre_cum=pre_cum,
                madev120=float(madev120), madev60=float(madev60), mret100=float(mret100),
                r100=float(r[t+1:t+1+W].sum()),
            ))
    return pd.DataFrame(recs)


def boot_mean(vals, seed=42, nboot=1000):
    rng = np.random.default_rng(seed)
    arr = np.asarray(vals)
    idx = rng.integers(0, len(arr), size=(nboot, len(arr)))
    b = arr[idx].mean(axis=1)
    return float(arr.mean()), float(np.quantile(b,.025)), float(np.quantile(b,.975))


def evaluate(df, mask, label):
    sub = df[mask]
    if len(sub) < 20:
        print(f"{label:<35} n={len(sub):<4}  too small")
        return None
    m, lo, hi = boot_mean(sub.r100.to_numpy())
    pct_neg = (sub.r100 < 0).mean()*100
    print(f"{label:<35} n={len(sub):<4} mean={m:+.4f} [{lo:+.4f},{hi:+.4f}] neg={pct_neg:.0f}%")
    return dict(label=label, n=len(sub), mean=m, lo=lo, hi=hi, pct_neg=pct_neg)


def main():
    df = build()
    print(f"total spike(z>=1.5): {len(df)}")
    hi = df.s_pre >= 0.10
    print(f"\nhigh_s (s_pre>=0.10): {hi.sum()}")

    results = []
    # 基线：高 s
    results.append(evaluate(df, hi, "baseline high_s"))
    # pre_cum 条件
    for th in [0.025, 0.03, 0.05]:
        results.append(evaluate(df, hi & (df.pre_cum>=th), f"high_s + pre_cum>={th}"))
    # MADEV120 条件
    for q in [0.5, 0.7, 0.8, 0.9]:
        th = df.loc[hi,"madev120"].quantile(q)
        results.append(evaluate(df, hi & (df.madev120>=th), f"high_s + MADEV120 q{int(q*100)} (={th:.3f})"))
    # MADEV60
    for q in [0.5, 0.7, 0.8]:
        th = df.loc[hi,"madev60"].quantile(q)
        results.append(evaluate(df, hi & (df.madev60>=th), f"high_s + MADEV60 q{int(q*100)} (={th:.3f})"))
    # MRET100
    for q in [0.5, 0.7, 0.8]:
        th = df.loc[hi,"mret100"].quantile(q)
        results.append(evaluate(df, hi & (df.mret100>=th), f"high_s + MRET100 q{int(q*100)} (={th:.3f})"))
    # 双高
    q1, q2 = df.loc[hi,"madev120"].quantile(.5), df.loc[hi,"pre_cum"].quantile(.5)
    results.append(evaluate(df, hi & (df.madev120>=q1) & (df.pre_cum>=q2), "high_s + MADEV120&pre_cum 双高50"))
    q1, q2 = df.loc[hi,"madev120"].quantile(.7), df.loc[hi,"pre_cum"].quantile(.7)
    results.append(evaluate(df, hi & (df.madev120>=q1) & (df.pre_cum>=q2), "high_s + MADEV120&pre_cum 双高70"))
    # 三因子
    results.append(evaluate(df, hi & (df.madev120>=df.loc[hi,'madev120'].quantile(.7)) &
                            (df.pre_cum>=df.loc[hi,'pre_cum'].quantile(.7)) &
                            (df.z>=2.0), "high_s + 三因子 z>=2"))
    # 极端
    results.append(evaluate(df, hi & (df.madev120>=df.loc[hi,'madev120'].quantile(.9)) &
                            (df.pre_cum>=df.loc[hi,'pre_cum'].quantile(.9)),
                            "high_s + 双高 90"))

    out = Path("/Users/gaolei/Documents/src/quant/project_data/research/volume-spike-regime-shift")
    pd.DataFrame([r for r in results if r]).to_csv(out/"condition_comparison.csv", index=False)
    print(f"\n[OK] {out}/condition_comparison.csv")


if __name__ == "__main__":
    main()
