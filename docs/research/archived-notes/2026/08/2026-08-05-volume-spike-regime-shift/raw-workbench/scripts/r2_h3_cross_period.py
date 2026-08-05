"""
r2 H3: 跨周期验证（5m）。
- 用 5m 同时段 z，N=120（约一周），H=600（约一周，对应 1h H=100 ~ 50 小时）
- 也测 5m 不同 H
- 因子简化为 MRET50/100/200, MADEV60/120, RVOL20
- 高 s_pre 层
另外：从 1h 聚合成日线，做日线因子 IC 分组
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

N = 60  # 5m lookback (about 1 trading day; 5m has too few samples per time-of-day for longer)

def load_5m(p):
    d = pd.read_csv(p)
    d["datetime"] = pd.to_datetime(d["datetime"])
    d = d.sort_values("datetime").reset_index(drop=True)
    d["lr"] = np.log(d.close).diff()
    v = d.volume
    # 5m has too few samples per time-of-day for by-tod rolling N=60; use simple rolling
    mu = v.shift(1).rolling(N, min_periods=N).mean()
    sd = v.shift(1).rolling(N, min_periods=N).std(ddof=1)
    d["z"] = (v-mu)/sd
    return d


def sp_ic(x,y):
    if len(x)<20 or np.std(x)<1e-10 or np.std(y)<1e-10: return np.nan
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return spearmanr(x,y).correlation


def run_5m():
    print("="*80)
    print("H3a: 5m 周期验证")
    print("="*80)
    recs=[]
    files = sorted(market_csv_dir().glob("*.5m.csv"))
    # limit to files with enough bars
    valid=[]
    for p in files:
        try:
            head = pd.read_csv(p, usecols=["datetime"])
            if len(head) >= N+600+200: valid.append(p)
        except: pass
    print(f"5m files with enough bars: {len(valid)}")
    # pick longest file per prefix to avoid duplicate contracts
    by_pfx={}
    for p in valid:
        sym=p.name.split(".tqsdk.5m.csv")[0]
        pfx=extract_contract_prefix(sym) or sym
        try: n=sum(1 for _ in open(p))-1
        except: continue
        if pfx not in by_pfx or n>by_pfx[pfx][1]: by_pfx[pfx]=(p,n)
    valid=[v[0] for v in by_pfx.values()]
    print(f"using {len(valid)} files (one per prefix)")

    H_GRID = [120, 240, 480, 600]  # 10h, 20h, 40h, 50h (5m bars)
    s_win = 600  # pre window for s

    for p in valid:  # use all valid files but subsample events
        sym = p.name.split(".tqsdk.5m.csv")[0]
        pfx = extract_contract_prefix(sym) or ""
        d = load_5m(p)
        c = d.close; r = d.lr.to_numpy(); z = d.z.to_numpy(); n = len(d)
        mret100 = c.pct_change(100).to_numpy()  # ~1 day
        mret200 = c.pct_change(200).to_numpy()  # ~2 days
        madev120 = ((c - c.rolling(120).mean())/c.rolling(120).mean()).to_numpy()
        rvol20 = d.lr.rolling(20).std(ddof=1).to_numpy()
        for t in range(max(N,s_win)+1, n-max(H_GRID), 3):  # subsample every 3 bars
            zv = z[t]
            if not math.isfinite(zv): continue
            if not (zv>=1.5 or abs(zv)<0.5): continue
            pre = r[t-s_win:t]
            if not np.all(np.isfinite(pre)): continue
            s_sd = pre.std(ddof=1)
            if s_sd<=0: continue
            s_pre = pre.mean()/s_sd
            if s_pre < 0.02: continue  # 5m threshold lower (per-bar Sharpe scales with sqrt(time))
            fv = (mret100[t], mret200[t], madev120[t], rvol20[t])
            if not all(math.isfinite(v) for v in fv): continue
            rec = dict(sym=sym, pfx=pfx, t=t, z=float(zv), s_pre=float(s_pre),
                       MRET100=fv[0], MRET200=fv[1], MADEV120=fv[2], RVOL20=fv[3])
            for H in H_GRID:
                rec[f"r{H}"] = float(r[t+1:t+1+H].sum())
            recs.append(rec)
    df = pd.DataFrame(recs)
    print(f"5m high_s events: {len(df)}")
    if len(df) < 50:
        print("too few 5m events"); return

    # z groups
    df["vgrp"] = pd.cut(df.z, bins=[-np.inf,-0.5,0.5,1.5,np.inf],
                       labels=["vlow","base","spike","extreme"])
    print(f"\n--- 5m IC 按成交量分组 ---")
    for H in [240, 480, 600]:
        print(f"\nH={H} ({H*5/60:.0f}h ≈ {H*5/60/5:.0f} 交易日):")
        print(f"{'factor':<12} {'vlow':>8} {'base':>8} {'spike':>8} {'extreme':>8} {'Δ(sp-base)':>11}")
        for fc in ["MRET100","MRET200","MADEV120","RVOL20"]:
            ics={}
            for g in ["vlow","base","spike","extreme"]:
                sub=df[df.vgrp==g]
                if len(sub)<20: ics[g]=np.nan; continue
                ics[g]=sp_ic(sub[fc],sub[f"r{H}"])
            diff = ics["spike"]-ics["base"] if not(math.isnan(ics["spike"]) or math.isnan(ics["base"])) else np.nan
            print(f"{fc:<12} {ics['vlow']:>+8.3f} {ics['base']:>+8.3f} {ics['spike']:>+8.3f} {ics['extreme']:>+8.3f} {diff:>+11.3f}")

    # absolute returns
    print(f"\n--- 5m 绝对收益（H=600）---")
    for g in ["vlow","base","spike","extreme"]:
        sub=df[df.vgrp==g]
        if len(sub)<20: continue
        print(f"  {g:<10} n={len(sub):<5} mean r600={sub.r600.mean():+.5f} neg={(sub.r600<0).mean()*100:.0f}%")


def run_daily():
    """从 1h 聚合成日线，做日线因子 IC 分组。"""
    print("\n"+"="*80)
    print("H3b: 日线（从 1h 聚合）")
    print("="*80)
    recs=[]
    for p in sorted(market_csv_dir().glob("*.1h.csv")):
        try: head=pd.read_csv(p,usecols=["datetime"])
        except: continue
        if len(head)<500: continue
        sym=p.name.split(".tqsdk.1h.csv")[0]
        pfx=extract_contract_prefix(sym) or ""
        d=pd.read_csv(p, parse_dates=["datetime"]).sort_values("datetime").reset_index(drop=True)
        # 交易日：夜盘算次日（简单用 date）
        d["date"]=d.datetime.dt.date
        daily=d.groupby("date").agg(open=("open","first"),high=("high","max"),
                                     low=("low","min"),close=("close","last"),
                                     volume=("volume","sum")).reset_index()
        daily["lr"]=np.log(daily.close).diff()
        v=daily.volume
        mu=v.shift(1).rolling(20,min_periods=20).mean()
        sd=v.shift(1).rolling(20,min_periods=20).std(ddof=1)
        daily["z"]=(v-mu)/sd
        c=daily.close; r=daily.lr.to_numpy(); z=daily.z.to_numpy(); n=len(daily)
        mret10=c.pct_change(10).to_numpy()
        mret20=c.pct_change(20).to_numpy()
        madev20=((c-c.rolling(20).mean())/c.rolling(20).mean()).to_numpy()
        for t in range(41, n-21):
            zv=z[t]
            if not math.isfinite(zv): continue
            pre=r[t-20:t]
            if not np.all(np.isfinite(pre)): continue
            s_sd=pre.std(ddof=1)
            if s_sd<=0: continue
            s_pre=pre.mean()/s_sd
            if s_pre<0.10: continue
            if not(math.isfinite(mret10[t]) and math.isfinite(madev20[t])): continue
            recs.append(dict(sym=sym,pfx=pfx,z=float(zv),s_pre=float(s_pre),
                             MRET10=mret10[t],MRET20=mret20[t],MADEV20=madev20[t],
                             r20=float(r[t+1:t+21].sum())))
    df=pd.DataFrame(recs)
    print(f"daily high_s events: {len(df)}")
    df["vgrp"]=pd.cut(df.z,bins=[-np.inf,-0.5,0.5,1.5,np.inf],
                      labels=["vlow","base","spike","extreme"])
    print(f"\n--- 日线 IC 按成交量分组（H=20）---")
    print(f"{'factor':<12} {'vlow':>8} {'base':>8} {'spike':>8} {'extreme':>8} {'Δ':>8}")
    for fc in ["MRET10","MRET20","MADEV20"]:
        ics={}
        for g in ["vlow","base","spike","extreme"]:
            sub=df[df.vgrp==g]
            ics[g]=sp_ic(sub[fc],sub.r20) if len(sub)>=20 else np.nan
        diff=ics["spike"]-ics["base"] if not(math.isnan(ics["spike"]) or math.isnan(ics["base"])) else np.nan
        print(f"{fc:<12} {ics['vlow']:>+8.3f} {ics['base']:>+8.3f} {ics['spike']:>+8.3f} {ics['extreme']:>+8.3f} {diff:>+8.3f}")
    print(f"\n--- 日线绝对收益 ---")
    for g in ["vlow","base","spike","extreme"]:
        sub=df[df.vgrp==g]
        if len(sub)<20: continue
        print(f"  {g:<10} n={len(sub):<4} mean r20={sub.r20.mean():+.5f} neg={(sub.r20<0).mean()*100:.0f}%")


if __name__=="__main__":
    run_5m()
    run_daily()
