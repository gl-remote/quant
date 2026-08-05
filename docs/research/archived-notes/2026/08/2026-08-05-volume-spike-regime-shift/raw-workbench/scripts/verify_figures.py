"""
验证三张图的数字与 conditioner 文档一致。
"""
import sys, math
from pathlib import Path
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))
from workspace.common.symbol_utils import extract_contract_prefix
from workspace.data.output_paths import market_csv_dir

N = 20; H = 100

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

recs=[]
for p in sorted(market_csv_dir().glob("*.1h.csv")):
    try: head=pd.read_csv(p,usecols=["datetime"])
    except: continue
    if len(head)<420: continue
    sym=p.name.split(".tqsdk.1h.csv")[0]
    d=load(p)
    c=d.close; r=d.lr.to_numpy(); z=d.z.to_numpy()
    ma120=c.rolling(120).mean().to_numpy(); c_arr=c.to_numpy(); n=len(d)
    for t in range(N+H+1,n-H):
        zv=z[t]
        if not math.isfinite(zv): continue
        pre=r[t-100:t]
        if not np.all(np.isfinite(pre)): continue
        ssd=pre.std(ddof=1)
        if ssd<=0: continue
        s_pre=pre.mean()/ssd
        if s_pre<0.10: continue
        if not(math.isfinite(ma120[t]) and ma120[t]>0): continue
        madev=float((c_arr[t]-ma120[t])/ma120[t])
        path={}
        for hh in [0,20,40,60,80,100]:
            idx=t+hh
            if idx<n and math.isfinite(ma120[idx]) and ma120[idx]>0:
                path[f"dev{hh}"]=float((c_arr[idx]-ma120[idx])/ma120[idx])
        recs.append(dict(z=float(zv),s_pre=float(s_pre),madev=madev,r100=float(r[t+1:t+101].sum()),**path))

df=pd.DataFrame(recs)
hi=df[df.s_pre>=0.10].copy()
med=hi.madev.median()
hi_hi=hi[hi.madev>=med]
vlow=hi_hi[hi_hi.z<-0.5]
normal=hi_hi[abs(hi_hi.z)<0.5]
spike=hi_hi[hi_hi.z>=1.5]
extreme=hi_hi[hi_hi.z>=2.5]

print("="*70)
print("图表数字验证（median split, 应与 conditioner §5.2 一致）")
print("="*70)
print(f"MADEV median = {med:.4f}")
print(f"n: vlow={len(vlow)}, normal={len(normal)}, spike={len(spike)}, extreme={len(extreme)}")
print()
print(f"{'组':<10} {'mean%':>8} {'std%':>8} {'P(>+3%)':>9} {'P(<-3%)':>9}")
for name,g in [("vlow",vlow),("normal",normal),("spike",spike),("extreme",extreme)]:
    print(f"{name:<10} {g.r100.mean()*100:>+8.3f} {g.r100.std()*100:>8.3f} "
          f"{(g.r100>0.03).mean()*100:>8.1f}% {(g.r100<-0.03).mean()*100:>8.1f}%")

print()
print(f"Δmean (spike - vlow) = {(spike.r100.mean()-vlow.r100.mean())*100:+.2f}%")
print(f"Δstd  (spike - vlow) = {(spike.r100.std()-vlow.r100.std())*100:+.2f}%")
print(f"ratio = {abs((spike.r100.mean()-vlow.r100.mean())/(spike.r100.std()-vlow.r100.std())):.1f}x")

print()
print("回归路径（spike z>=1.5）：")
for h in [0,20,40,60,80,100]:
    vals=spike[f"dev{h}"].dropna()
    vv=vlow[f"dev{h}"].dropna()
    print(f"  t+{h:<3d}: spike={vals.mean()*100:+.2f}%  vlow={vv.mean()*100:+.2f}%")

print()
print("文档声称：")
print("  mean: vlow=+1.84%, spike=-2.33%, Δ=-4.16%")
print("  std:  vlow=3.19%,  spike=3.95%,  Δ=+0.76%")
print("  P(r>+3%): vlow=21.8%, spike=2.8%")
print("  P(r<-3%): vlow=5.7%,  spike=34.8%")
