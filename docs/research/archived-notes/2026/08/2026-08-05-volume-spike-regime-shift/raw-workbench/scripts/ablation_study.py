"""
完整消融实验：
三个核心变量 Z, MADEV, Skew，以及组合：
1. 全样本 baseline
2. 单条件：Z 极端、MADEV 高、Skew 极端
3. 双条件：Z×MADEV、Z×Skew、MADEV×Skew
4. 三条件：Z×MADEV×Skew
对每个切片报告：n, mean r100, % 上涨, IC
同时比较阈值选择（Z=1.5 vs 2.5, Skew ±1σ vs ±0.5σ, MADEV median vs top 33%）
"""
import sys, math
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from itertools import product

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))

out = Path("/Users/gaolei/Documents/src/quant/project_data/research/volume-spike-regime-shift")
df = pd.read_csv(out/"volume_skew_events.csv", parse_dates=["ts"])
print(f"Total events: {len(df)}")

# Standardize
df["madev_s"] = (df.madev - df.madev.mean())/df.madev.std()
df["skew_s"] = (df.vp_skew - df.vp_skew.mean())/df.vp_skew.std()
df["z_s"] = (df.z - df.z.mean())/df.z.std()

def stats(sub):
    if len(sub)<20:
        return dict(n=len(sub), mean=np.nan, pct_pos=np.nan, ic=np.nan)
    ic = spearmanr(sub.madev, sub.r100)[0] if len(sub)>30 else np.nan
    return dict(n=len(sub), mean=sub.r100.mean()*100,
                pct_pos=(sub.r100>0).mean()*100, ic=ic)

def row(label, sub):
    s = stats(sub)
    print(f"{label:<45} n={s['n']:>5}  mean={s['mean']:+7.3f}%  %pos={s['pct_pos']:>4.0f}%  IC={s['ic']:+.3f}")
    return s

# Threshold grids
Z_THRESH = [("z>=1.5", df.z>=1.5), ("z>=2.5", df.z>=2.5), ("z<=-0.5", df.z<=-0.5)]
MADEV_THRESH = [("madev>=median", df.madev>=df.madev.median()),
                ("madev>=q67", df.madev>=df.madev.quantile(0.67))]
SKEW_THRESH = [("skew>=+1σ", df.skew_s>=1), ("skew<=-1σ", df.skew_s<=-1),
               ("skew>=+0.5σ", df.skew_s>=0.5), ("skew<=-0.5σ", df.skew_s<=-0.5)]
S_PRE = [("all", df.index==df.index), ("high_s", df.s_pre>=0.10)]

print("\n"+"="*90)
print("1. BASELINE（无条件）")
print("="*90)
for sn, sm in S_PRE:
    row(f"baseline [{sn}]", df[sm])

print("\n"+"="*90)
print("2. 单条件消融")
print("="*90)
for sn, sm in S_PRE:
    print(f"\n--- {sn} ---")
    d = df[sm]
    row("Z>=1.5", d[d.z>=1.5])
    row("Z>=2.5", d[d.z>=2.5])
    row("Z<=-0.5 (缩量)", d[d.z<=-0.5])
    row("MADEV>=median", d[d.madev>=d.madev.median()])
    row("MADEV>=q67", d[d.madev>=d.madev.quantile(0.67)])
    row("Skew>=+1σ", d[d.skew_s>=1])
    row("Skew<=-1σ", d[d.skew_s<=-1])

print("\n"+"="*90)
print("3. 双条件消融")
print("="*90)
for sn, sm in S_PRE:
    print(f"\n--- {sn} ---")
    d = df[sm]
    med = d.madev.median()
    q67 = d.madev.quantile(0.67)
    # Z × MADEV
    print(" [Z × MADEV]")
    row("Z>=1.5 & MADEV>=med", d[(d.z>=1.5)&(d.madev>=med)])
    row("Z>=2.5 & MADEV>=med", d[(d.z>=2.5)&(d.madev>=med)])
    row("Z>=2.5 & MADEV>=q67", d[(d.z>=2.5)&(d.madev>=q67)])
    row("Z<=-0.5 & MADEV>=med", d[(d.z<=-0.5)&(d.madev>=med)])
    row("Z<=-0.5 & MADEV>=q67", d[(d.z<=-0.5)&(d.madev>=q67)])
    # Z × Skew
    print(" [Z × Skew]")
    row("Z>=2.5 & Skew>=+1σ", d[(d.z>=2.5)&(d.skew_s>=1)])
    row("Z>=2.5 & Skew<=-1σ", d[(d.z>=2.5)&(d.skew_s<=-1)])
    row("Z>=1.5 & Skew>=+1σ", d[(d.z>=1.5)&(d.skew_s>=1)])
    row("Z>=1.5 & Skew<=-1σ", d[(d.z>=1.5)&(d.skew_s<=-1)])
    row("Z<=-0.5 & Skew>=+1σ", d[(d.z<=-0.5)&(d.skew_s>=1)])
    row("Z<=-0.5 & Skew<=-1σ", d[(d.z<=-0.5)&(d.skew_s<=-1)])
    # MADEV × Skew
    print(" [MADEV × Skew]")
    row("MADEV>=med & Skew>=+1σ", d[(d.madev>=med)&(d.skew_s>=1)])
    row("MADEV>=med & Skew<=-1σ", d[(d.madev>=med)&(d.skew_s<=-1)])

print("\n"+"="*90)
print("4. 三条件消融（Z × MADEV × Skew）")
print("="*90)
for sn, sm in S_PRE:
    print(f"\n--- {sn} ---")
    d = df[sm]
    med = d.madev.median()
    q67 = d.madev.quantile(0.67)
    for z_name, z_mask in [("Z>=1.5", d.z>=1.5),("Z>=2.5", d.z>=2.5),("Z<=-0.5", d.z<=-0.5)]:
        for m_name, m_mask in [("MADEV>=med", d.madev>=med),("MADEV>=q67", d.madev>=q67)]:
            for s_name, s_mask in [("Skew>=+1σ", d.skew_s>=1),("Skew<=-1σ", d.skew_s<=-1)]:
                sub = d[z_mask & m_mask & s_mask]
                row(f"{z_name} & {m_name} & {s_name}", sub)

print("\n"+"="*90)
print("5. 回归 R² 消融")
print("="*90)
from numpy.linalg import lstsq
hi = df[df.s_pre>=0.10].copy()
for c in ["z","madev","vp_skew"]:
    hi[c+"_s"]=(hi[c]-hi[c].mean())/hi[c].std()
y = hi.r100.to_numpy()
def r2(X, y):
    b=lstsq(X,y,rcond=None)[0]; pred=X@b
    return 1-((y-pred)**2).sum()/((y-y.mean())**2).sum()
ones=np.ones((len(hi),1))
models = {
    "Z only": np.hstack([ones, hi[["z_s"]].values]),
    "MADEV only": np.hstack([ones, hi[["madev_s"]].values]),
    "Skew only": np.hstack([ones, hi[["skew_s"]].values]),
    "Z+MADEV": np.hstack([ones, hi[["z_s","madev_s"]].values, (hi.z_s*hi.madev_s).values.reshape(-1,1)]),
    "Z+Skew": np.hstack([ones, hi[["z_s","skew_s"]].values, (hi.z_s*hi.skew_s).values.reshape(-1,1)]),
    "MADEV+Skew": np.hstack([ones, hi[["madev_s","skew_s"]].values, (hi.madev_s*hi.skew_s).values.reshape(-1,1)]),
    "Z+MADEV+Skew": np.hstack([ones, hi[["z_s","madev_s","skew_s"]].values,
                               (hi.z_s*hi.madev_s).values.reshape(-1,1),
                               (hi.z_s*hi.skew_s).values.reshape(-1,1),
                               (hi.madev_s*hi.skew_s).values.reshape(-1,1)]),
}
print(f"\n高 s 样本 n={len(hi)}")
for name, X in models.items():
    print(f"  {name:<20} R²={r2(X,y):.4f}")

# Also full sample
print(f"\n全样本 n={len(df)}")
df2=df.copy()
for c in ["z","madev","vp_skew"]:
    df2[c+"_s"]=(df2[c]-df2[c].mean())/df2[c].std()
y2=df2.r100.to_numpy()
for name, cols in [("Z",["z_s"]),("MADEV",["madev_s"]),("Skew",["skew_s"]),
                    ("Z+MADEV",["z_s","madev_s"]),("Z+Skew",["z_s","skew_s"]),
                    ("MADEV+Skew",["madev_s","skew_s"]),
                    ("Z+MADEV+Skew",["z_s","madev_s","skew_s"])]:
    X=np.hstack([np.ones((len(df2),1)), df2[cols].values])
    if "+" in name:
        # add interactions
        if name=="Z+MADEV":
            X=np.hstack([X,(df2.z_s*df2.madev_s).values.reshape(-1,1)])
        elif name=="Z+Skew":
            X=np.hstack([X,(df2.z_s*df2.skew_s).values.reshape(-1,1)])
        elif name=="MADEV+Skew":
            X=np.hstack([X,(df2.madev_s*df2.skew_s).values.reshape(-1,1)])
        else:
            X=np.hstack([X,(df2.z_s*df2.madev_s).values.reshape(-1,1),
                        (df2.z_s*df2.skew_s).values.reshape(-1,1),
                        (df2.madev_s*df2.skew_s).values.reshape(-1,1)])
    print(f"  {name:<20} R²={r2(X,y2):.4f}")

print("\n[OK]")
