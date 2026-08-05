"""
按市场状态分层：spike 后收益在牛市/熊市/震荡市的表现。
用 N=20 H=100 z0=1.5 主规格。
regime 定义：用 spike 前 100 根 bar 的累计收益（pre_cum100）分三档：
  bull: pre_cum100 > +2%
  bear: pre_cum100 < -2%
  range: -2% ~ +2%
同时用全样本 baseline 的市场基准收益验证。
"""
from __future__ import annotations
import sys, math
from pathlib import Path
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).parent))
from full_grid_1h import collect, boot_ci, cid  # noqa

contracts = sorted((REPO_ROOT / "project_data/market_data/csv").glob("*.1h.csv"))
byN = collect(contracts, [20], [100])
df = byN[20].copy()

# 重新加载 lr 以算 pre_cum100
from workspace.common.symbol_utils import extract_contract_prefix
from workspace.data.output_paths import market_csv_dir

# 从已收集的事件里没有 pre_cum100，重新构建
recs = []
H = 100
for p in sorted(market_csv_dir().glob("*.1h.csv")):
    try:
        head = pd.read_csv(p, usecols=["datetime"])
    except Exception:
        continue
    if len(head) < 420:
        continue
    sym = p.name.split(".tqsdk.1h.csv")[0]
    prefix = extract_contract_prefix(sym) or ""
    d = pd.read_csv(p)
    d["datetime"] = pd.to_datetime(d["datetime"])
    d = d.sort_values("datetime").reset_index(drop=True)
    d["lr"] = np.log(d.close).diff()
    v, hour = d.volume, d.datetime.dt.hour
    N = 20
    mu = v.groupby(hour).shift(1).groupby(hour).transform(lambda s: s.rolling(N,min_periods=N).mean())
    sd = v.groupby(hour).shift(1).groupby(hour).transform(lambda s: s.rolling(N,min_periods=N).std(ddof=1))
    d["z"] = (v - mu)/sd
    d["session_date"] = d.datetime.dt.date
    r = d.lr.to_numpy(); z = d.z.to_numpy()
    n = len(d)
    for t in range(N+H+101, n-H):
        zv = z[t]
        if not math.isfinite(zv): continue
        post = r[t+1:t+1+H]
        if not np.all(np.isfinite(post)): continue
        pre100 = r[t-100:t]
        pre20 = r[t-20:t]
        if not (np.all(np.isfinite(pre100)) and np.all(np.isfinite(pre20))): continue
        if zv >= 1.5:
            grp = "spike"
        elif abs(zv) < 0.5:
            grp = "baseline"
        else:
            continue
        recs.append({
            "symbol": sym, "prefix": prefix, "session_date": str(d.session_date.iloc[t]),
            "group": grp, "rH": float(post.sum()),
            "pre100": float(pre100.sum()), "pre20": float(pre20.sum()),
        })

ev = pd.DataFrame(recs)
print(f"events: {len(ev)}, spike={(ev.group=='spike').sum()}, base={(ev.group=='baseline').sum()}")

def regime(x):
    if x > 0.02: return "bull(>+2%)"
    if x < -0.02: return "bear(<-2%)"
    return "range"

ev["regime"] = ev.pre100.apply(regime)

print("\n=== 全品种：按 pre100 市场状态分层 ===")
print(f"{'regime':<14} {'grp':<9} {'n':>5} {'rH_mean':>10} {'%neg':>7}")
for reg in ["bull(>+2%)", "range", "bear(<-2%)"]:
    sub = ev[ev.regime == reg]
    for grp in ["spike", "baseline"]:
        s = sub[sub.group == grp]
        if len(s) < 5: continue
        print(f"{reg:<14} {grp:<9} {len(s):>5} {s.rH.mean():>+10.4f} {(s.rH<0).mean():>7.1%}")
    sp = sub[sub.group=="spike"]; bs = sub[sub.group=="baseline"]
    if len(sp)>=20 and len(bs)>=50:
        cs, cb = cid(sp), cid(bs)
        d, lo, hi, p = boot_ci(sp.rH.to_numpy(), cs, bs.rH.to_numpy(), cb, seed=hash(reg)%2**30)
        print(f"{'':<14} {'Δ(sp-bs)':<9} {len(sp):>5} {d:>+10.4f} CI=[{lo:+.4f},{hi:+.4f}] p={p:.4f}")
    print()

# 逐品种在 bear regime 下的表现
print("=== bear regime 下逐品种 spike vs baseline ===")
bear = ev[ev.regime == "bear(<-2%)"]
rows = []
for pfx in sorted(bear.prefix.unique()):
    sp = bear[(bear.prefix==pfx)&(bear.group=="spike")]
    bs = bear[(bear.prefix==pfx)&(bear.group=="baseline")]
    if len(sp)<5 or len(bs)<5: continue
    rows.append({
        "prefix": pfx, "n_s": len(sp), "n_b": len(bs),
        "spike_rH": sp.rH.mean(), "base_rH": bs.rH.mean(),
        "delta": sp.rH.mean()-bs.rH.mean(),
        "spike_%neg": (sp.rH<0).mean(),
    })
dfb = pd.DataFrame(rows)
print(dfb.to_string(index=False, float_format=lambda x: f"{x:+.4f}"))

# bull regime 逐品种
print("\n=== bull regime 下逐品种 ===")
bull = ev[ev.regime == "bull(>+2%)"]
rows = []
for pfx in sorted(bull.prefix.unique()):
    sp = bull[(bull.prefix==pfx)&(bull.group=="spike")]
    bs = bull[(bull.prefix==pfx)&(bull.group=="baseline")]
    if len(sp)<5 or len(bs)<5: continue
    rows.append({
        "prefix": pfx, "n_s": len(sp), "n_b": len(bs),
        "spike_rH": sp.rH.mean(), "base_rH": bs.rH.mean(),
        "delta": sp.rH.mean()-bs.rH.mean(),
        "spike_%neg": (sp.rH<0).mean(),
    })
print(pd.DataFrame(rows).to_string(index=False, float_format=lambda x: f"{x:+.4f}"))
