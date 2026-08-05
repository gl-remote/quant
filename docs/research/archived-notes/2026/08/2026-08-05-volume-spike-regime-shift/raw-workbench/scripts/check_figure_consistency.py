"""
检查 conditioner 文档中所有图表数据与文字描述的一致性。
对比：
1. 文档文字里的数字（来自 r2_uncertainty_test.py 用 median split）
2. 图表里的数据（来自 r2_make_figures.py 用 top third split）
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

def build():
    recs=[]
    for p in sorted(market_csv_dir().glob("*.1h.csv")):
        try: head=pd.read_csv(p,usecols=["datetime"])
        except: continue
        if len(head)<420: continue
        sym=p.name.split(".tqsdk.1h.csv")[0]
        d=load(p)
        c=d.close; r=d.lr.to_numpy(); z=d.z.to_numpy()
        ma120=c.rolling(120).mean().to_numpy()
        c_arr=c.to_numpy(); n=len(d)
        for t in range(N+H+1,n-H):
            zv=z[t]
            if not math.isfinite(zv): continue
            pre=r[t-100:t]
            if not np.all(np.isfinite(pre)): continue
            s_sd=pre.std(ddof=1)
            if s_sd<=0: continue
            s_pre=pre.mean()/s_sd
            if s_pre<0.10: continue
            if not(math.isfinite(ma120[t]) and ma120[t]>0): continue
            madev=float((c_arr[t]-ma120[t])/ma120[t])
            path={}
            for h in [0,20,40,60,80,100]:
                idx=t+h
                if idx<n and math.isfinite(ma120[idx]) and ma120[idx]>0:
                    path[f"dev{h}"]=float((c_arr[idx]-ma120[idx])/ma120[idx])
            recs.append(dict(z=float(zv),s_pre=float(s_pre),madev=madev,r100=float(r[t+1:t+101].sum()),**path))
    return pd.DataFrame(recs)

df=build()
hi=df[df.s_pre>=0.10].copy()
print(f"Total high_s events: {len(hi)}")
print()

# Compare different MADEV splits
print("="*80)
print("样本切分对比：median split vs top third")
print("="*80)
med = hi.madev.median()
q67 = hi.madev.quantile(0.67)
print(f"MADEV median={med:.4f}, q67={q67:.4f}")

for split_name, mask in [
    ("median split (high = top 50%)", hi.madev >= med),
    ("top third (high = top 33%)", hi.madev >= q67),
]:
    sub = hi[mask]
    print(f"\n--- {split_name} (n={len(sub)}) ---")
    vlow = sub[sub.z<-0.5]
    normal = sub[abs(sub.z)<0.5]
    spike = sub[sub.z>=1.5]
    extreme = sub[sub.z>=2.5]
    for name, g in [("vlow",vlow),("normal",normal),("spike",spike),("extreme",extreme)]:
        if len(g)>5:
            print(f"  {name:<10} n={len(g):<4} mean={g.r100.mean()*100:+.3f}% std={g.r100.std()*100:.3f}% "
                  f"P(>+3%)={(g.r100>0.03).mean()*100:.1f}% P(<-3%)={(g.r100<-0.03).mean()*100:.1f}%")

# Check path numbers
print("\n"+"="*80)
print("回归路径对比（文档说 +9%→-3%）")
print("="*80)
for split_name, mask in [
    ("median split", hi.madev >= med),
    ("top third", hi.madev >= q67),
]:
    sub=hi[mask]
    print(f"\n--- {split_name} ---")
    for vol_name, vol_mask in [("spike z>=1.5", sub.z>=1.5),("extreme z>=2.5", sub.z>=2.5)]:
        g=sub[vol_mask]
        if len(g)<5: continue
        print(f"  {vol_name} (n={len(g)}):")
        for h in [0,20,40,60,80,100]:
            vals=g[f"dev{h}"].dropna()
            if len(vals)>5:
                print(f"    t+{h:<3} dev={vals.mean()*100:+.2f}%")

# What does the document actually say?
print("\n"+"="*80)
print("文档文字声称的数字 vs 实际")
print("="*80)
print("""
文档 §5.2 表格（声称来自 r2_uncertainty_test.py）:
  高MADEV z低:  mean=+0.57%  std=3.17%  IQR=3.28%  |r|=2.34%
  高MADEV z高:  mean=-1.97%  std=3.88%  IQR=4.63%  |r|=3.18%
  Δmean=-2.54%  Δstd=+0.71%

文档 §5.2 路径:
  "极端放量时高 MADEV 后偏离在 40-60 根 bar 内从 +9% 降到 -3%"

文档 §5.2 尾部概率:
  "极端放量把下行尾部从 4% 推高到 25%，上行尾部从 15% 压缩到 5%"
  （这些数字来自全样本，不是高MADEV子集）
""")
