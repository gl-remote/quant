"""日线 pre-trend 匹配诊断：spike 前 20 天已涨 +1.69%，需排除 post 负收益来自均值回复。"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from daily_volume_spike import build_continuous_by_prefix, build_events  # noqa

frames = build_continuous_by_prefix()
ev = build_events(frames, lookback_n=20, z0=2.0)
sp = ev[ev.group == "spike"].copy()
bs = ev[ev.group == "baseline"].copy()

print(f"spike n={len(sp)}, baseline n={len(bs)}")
print(f"\npre_cum 分布：")
print(f"  spike:    mean={sp.pre_cum.mean():+.4f} median={sp.pre_cum.median():+.4f}")
print(f"  baseline: mean={bs.pre_cum.mean():+.4f} median={bs.pre_cum.median():+.4f}")

# 方法 1：按 pre_cum 十分位分层，每层内 spike vs baseline 的 r20
print("\n=== pre_cum 十分位分层（spike 在该层内 vs 同层 baseline）===")
all_ev = pd.concat([sp, bs])
all_ev["pre_decile"] = pd.qcut(all_ev.pre_cum, 10, labels=False, duplicates="drop")
rows = []
for q, sub in all_ev.groupby("pre_decile"):
    s = sub[sub.group == "spike"]
    b = sub[sub.group == "baseline"]
    if len(s) < 3 or len(b) < 5:
        continue
    rows.append({
        "q": q, "pre_range": f"[{sub.pre_cum.min():+.3f},{sub.pre_cum.max():+.3f}]",
        "n_s": len(s), "n_b": len(b),
        "r20_spike": s.r20.mean(), "r20_base": b.r20.mean(),
        "delta": s.r20.mean() - b.r20.mean(),
    })
dfq = pd.DataFrame(rows)
print(dfq.to_string(index=False, float_format=lambda x: f"{x:+.4f}"))
print(f"\n分层后 spike-base r20 差的均值（跨十分位）：{dfq.delta.mean():+.5f}")
print(f"其中 sign 为负的层数：{(dfq.delta<0).sum()}/{len(dfq)}")

# 方法 2：在 baseline 中为每个 spike 按 pre_cum 最近邻匹配 5 个
print("\n=== pre_cum 最近邻匹配（每个 spike 匹配 5 个 baseline，caliper=0.01）===")
matched_s = []
matched_b = []
for _, srow in sp.iterrows():
    cand = bs[(bs.prefix != srow.prefix)].copy()  # 留同品种外的 baseline
    cand["dist"] = (cand.pre_cum - srow.pre_cum).abs()
    cand = cand[cand.dist < 0.01].nsmallest(5, "dist")
    if len(cand) >= 1:
        matched_s.extend([srow.r20] * len(cand))
        matched_b.extend(cand.r20.tolist())
print(f"匹配对数：{len(matched_s)}")
print(f"  spike r20 mean:  {np.mean(matched_s):+.5f}")
print(f"  matched base:    {np.mean(matched_b):+.5f}")
print(f"  差值:            {np.mean(matched_s)-np.mean(matched_b):+.5f}")
# paired bootstrap diff
s_arr = np.array(matched_s)
b_arr = np.array(matched_b)
diff = s_arr - b_arr
rng = np.random.default_rng(42)
boot = []
for _ in range(3000):
    idx = rng.integers(0, len(diff), len(diff))
    boot.append(diff[idx].mean())
boot = np.array(boot)
print(f"  95% CI: [{np.quantile(boot,0.025):+.5f}, {np.quantile(boot,0.975):+.5f}]")

# 方法 3：只看 pre_cum 接近 0 的（|pre|<0.5%），即没有前期趋势的样本
print("\n=== 限定 |pre_cum|<0.005（无明显前期趋势的子样本）===")
mask_s = sp.pre_cum.abs() < 0.005
mask_b = bs.pre_cum.abs() < 0.005
print(f"  spike n={mask_s.sum()}, base n={mask_b.sum()}")
if mask_s.sum() >= 5 and mask_b.sum() >= 10:
    print(f"  spike r20:  {sp[mask_s].r20.mean():+.5f}")
    print(f"  base r20:   {bs[mask_b].r20.mean():+.5f}")
    print(f"  delta:      {sp[mask_s].r20.mean()-bs[mask_b].r20.mean():+.5f}")

# 方法 4：回归 r20 ~ 1 + spike + pre_cum + spike*pre_cum
print("\n=== 回归 r20 ~ spike + pre_cum + spike×pre_cum（按 prefix cluster bootstrap）===")
import numpy as np
d = pd.concat([sp.assign(spike=1.0), bs.assign(spike=0.0)])
d["interact"] = d.spike * d.pre_cum
X = np.column_stack([np.ones(len(d)), d.spike.values, d.pre_cum.values, d.interact.values])
y = d.r20.values
beta = np.linalg.lstsq(X, y, rcond=None)[0]
print(f"  const = {beta[0]:+.5f}")
print(f"  spike = {beta[1]:+.5f}  (独立于 pre_cum 的 spike 效应)")
print(f"  pre_cum = {beta[2]:+.5f}  (前趋势对 post 的预测)")
print(f"  spike×pre_cum = {beta[3]:+.5f}  (spike 是否改变前趋势的延续性)")
# cluster bootstrap by prefix
keys = sorted(d.prefix.unique())
km = {k:i for i,k in enumerate(keys)}
c = np.array([km[k] for k in d.prefix])
nc = len(keys)
rng = np.random.default_rng(11)
bb = []
for _ in range(2000):
    idx = rng.integers(0, nc, nc)
    rows = np.concatenate([np.where(c==i)[0] for i in idx])
    bb.append(np.linalg.lstsq(X[rows], y[rows], rcond=None)[0])
bb = np.array(bb)
for i, name in enumerate(["const","spike","pre_cum","spike×pre_cum"]):
    lo, hi = np.quantile(bb[:,i], [0.025, 0.975])
    print(f"  {name:<14} β={beta[i]:+.5f}  CI=[{lo:+.5f},{hi:+.5f}]  {'excl0' if lo*hi>0 else 'incls0'}")
