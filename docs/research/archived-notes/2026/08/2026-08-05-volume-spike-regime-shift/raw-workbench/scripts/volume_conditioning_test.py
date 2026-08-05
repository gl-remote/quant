"""
验证：按成交量切分后，因子预测力是否在每个子组都增强（而非"翻转"）？
1. 全样本 IC vs spike IC vs baseline IC vs 中间区 IC
2. 按 z 分五分位，看 IC 是否连续变化
3. 用连续交互回归而非二值 spike
"""
from __future__ import annotations
import sys, math, warnings
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

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


def factors(d):
    c, r = d.close, d.lr
    f = pd.DataFrame(index=d.index)
    for L in [20,50,100,200]: f[f"MRET{L}"] = c.pct_change(L)
    f["REV20"] = -c.pct_change(20)
    for L in [20,60,120]:
        f[f"MADEV{L}"] = (c - c.rolling(L).mean())/c.rolling(L).mean()
    ma=c.rolling(20).mean(); sd=c.rolling(20).std(ddof=1)
    f["BB20"] = (c-ma)/(2*sd)
    f["RVOL20"] = r.rolling(20).std(ddof=1)
    f["VWAP_DEV20"] = (c - (c*d.volume).rolling(20).sum()/d.volume.rolling(20).sum()) / ((c*d.volume).rolling(20).sum()/d.volume.rolling(20).sum())
    return f


def build():
    recs=[]
    for p in sorted(market_csv_dir().glob("*.1h.csv")):
        try: head=pd.read_csv(p,usecols=["datetime"])
        except: continue
        if len(head)<420: continue
        sym=p.name.split(".tqsdk.1h.csv")[0]
        d=load(p); fac=factors(d)
        r=d.lr.to_numpy(); z=d.z.to_numpy()
        cols=list(fac.columns); arr=fac.to_numpy(); n=len(d)
        for t in range(N+H+1,n-H):
            zv=z[t]
            if not math.isfinite(zv): continue
            pre=r[t-100:t]
            if not np.all(np.isfinite(pre)): continue
            s_sd=pre.std(ddof=1)
            if s_sd<=0: continue
            s_pre=pre.mean()/s_sd
            fv=arr[t]
            if not np.all(np.isfinite(fv)): continue
            rec=dict(sym=sym,z=float(zv),s_pre=float(s_pre),r100=float(r[t+1:t+1+H].sum()))
            for ci,cn in enumerate(cols): rec[cn]=float(fv[ci])
            recs.append(rec)
    return pd.DataFrame(recs), cols


def sp_ic(x,y):
    if len(x)<20 or np.std(x)<1e-10 or np.std(y)<1e-10: return np.nan
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return spearmanr(x,y).correlation


def main():
    df,fcols=build()
    # high_s only (where the effect exists)
    df=df[df.s_pre>=0.10].copy()
    print(f"high_s events: {len(df)}")

    # Define volume groups
    df["vgrp"] = pd.cut(df.z, bins=[-np.inf,-0.5,0.5,1.5,2.5,np.inf],
                        labels=["very_low","base","mid","spike","extreme"])

    print("\n=== 全样本 vs 成交量分组 IC（高 s 层，H=100）===")
    print(f"{'factor':<12} {'ALL':>7} {'vlow':>7} {'base':>7} {'mid':>7} {'spike':>7} {'extreme':>8} {'|base|+|spk|':>12} {'|ALL|':>7}")
    for fc in fcols:
        ics=[]
        for grp in ["ALL","very_low","base","mid","spike","extreme"]:
            if grp=="ALL": sub=df
            else: sub=df[df.vgrp==grp]
            if len(sub)<20:
                ics.append(np.nan); continue
            ics.append(sp_ic(sub[fc].to_numpy(), sub.r100.to_numpy()))
        ic_all, ic_vl, ic_b, ic_m, ic_s, ic_e = ics
        gain = abs(ic_b)+abs(ic_s) if not(math.isnan(ic_b) or math.isnan(ic_s)) else np.nan
        print(f"{fc:<12} {ic_all:>+7.3f} {ic_vl:>+7.3f} {ic_b:>+7.3f} {ic_m:>+7.3f} {ic_s:>+7.3f} {ic_e:>+8.3f} {gain:>12.3f} {abs(ic_all):>7.3f}")

    # Continuous z quintile IC
    print("\n=== z 五分位 IC（高 s 层）===")
    df["zq"] = pd.qcut(df.z, 5, labels=["Q1(low)","Q2","Q3","Q4","Q5(high)"])
    print(f"{'factor':<12}", end="")
    for q in ["Q1(low)","Q2","Q3","Q4","Q5(high)"]: print(f" {q:>10}", end="")
    print()
    for fc in fcols:
        print(f"{fc:<12}", end="")
        for q in ["Q1(low)","Q2","Q3","Q4","Q5(high)"]:
            sub=df[df.zq==q]
            ic=sp_ic(sub[fc].to_numpy(),sub.r100.to_numpy()) if len(sub)>=20 else np.nan
            print(f" {ic:>+10.3f}", end="")
        print()

    # 连续交互：IC as function of z (rank correlation of f with r, within z bands)
    # Also pooled regression with continuous z
    print("\n=== 连续交互回归 r100 ~ f + z + f×z（标准化，高 s 层）===")
    print(f"{'factor':<12} {'β1(f)':>10} {'β2(z)':>10} {'β3(f×z)':>10} {'β3_CI':>22}")
    for fc in fcols:
        sub=df[[fc,"z","r100"]].dropna()
        if len(sub)<50: continue
        X=np.column_stack([np.ones(len(sub)),
                           (sub[fc]-sub[fc].mean())/sub[fc].std(),
                           (sub.z-sub.z.mean())/sub.z.std(),
                           ((sub[fc]-sub[fc].mean())/sub[fc].std())*((sub.z-sub.z.mean())/sub.z.std())])
        y=sub.r100.to_numpy()
        beta=np.linalg.lstsq(X,y,rcond=None)[0]
        rng=np.random.default_rng(hash(fc)%2**30)
        b3=[]
        for _ in range(300):
            idx=rng.integers(0,len(y),len(y))
            b=np.linalg.lstsq(X[idx],y[idx],rcond=None)[0]
            b3.append(b[3])
        lo,hi=np.quantile(b3,[.025,.975])
        sig="*" if lo*hi>0 else " "
        print(f"{fc:<12} {beta[1]:>+10.5f} {beta[2]:>+10.5f} {beta[3]:>+10.5f} [{lo:+.5f},{hi:+.5f}]{sig}")


if __name__=="__main__":
    main()
