"""
r2 H1 + H4 + H5:
H1: 缩量端动量信号验证（z<−0.5 的 IC、OOS、剂量反应、持续性）
H4: 因子正交化——PCA + 多元 LASSO 交互，找出独立维度
H5: 滚动 IC 时变性 + 市场状态依赖
用 1h 数据，高 s 层。
"""
from __future__ import annotations
import sys, math, warnings, json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))
from workspace.common.symbol_utils import extract_contract_prefix
from workspace.data.output_paths import market_csv_dir

N = 20; H = 100
N_BOOT = 300


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


def all_factors(d):
    c, hh, ll, r, v = d.close, d.high, d.low, d.lr, d.volume
    f = pd.DataFrame(index=d.index)
    for L in [20,50,100,200]: f[f"MRET{L}"] = c.pct_change(L)
    f["S_PRE"] = r.rolling(100).mean()/r.rolling(100).std(ddof=1)
    for L in [20,60,120]: f[f"MADEV{L}"] = (c-c.rolling(L).mean())/c.rolling(L).mean()
    for L in [100,200]:
        mn=c.rolling(L).min(); mx=c.rolling(L).max()
        f[f"HH{L}"] = (c-mn)/(mx-mn)
    f["STREAK20"] = (r>0).astype(float).rolling(20).mean()
    for L in [50,100]:
        f[f"PATEFF{L}"] = (c/c.shift(L)-1).abs()/r.abs().rolling(L).sum().replace(0,np.nan)
    f["REV20"] = -c.pct_change(20)
    for L in [14,30]:
        delta=c.diff(); gain=delta.clip(lower=0).rolling(L).mean()
        loss=(-delta.clip(upper=0)).rolling(L).mean()
        f[f"RSI{L}"] = 100-100/(1+gain/loss.replace(0,np.nan))
    for L in [20,60]:
        ma=c.rolling(L).mean(); sd=c.rolling(L).std(ddof=1)
        f[f"BB{L}"] = (c-ma)/(2*sd)
    f["RVOL20"] = r.rolling(20).std(ddof=1)
    f["RVOL60"] = r.rolling(60).std(ddof=1)
    tr=pd.concat([(hh-ll),(hh-c.shift()).abs(),(ll-c.shift()).abs()],axis=1).max(axis=1)
    f["ATR14"] = tr.rolling(14).mean()
    f["RANGE20"] = ((hh-ll)/c).rolling(20).mean()
    f["SKEW20"] = r.rolling(20).skew()
    f["KURT20"] = r.rolling(20).kurt()
    f["VWAP_DEV20"] = (c-(c*v).rolling(20).sum()/v.rolling(20).sum())/((c*v).rolling(20).sum()/v.rolling(20).sum())
    notional=v*c
    f["AMIHUD20"] = (r.abs()/notional.replace(0,np.nan)).rolling(20).mean()
    f["VOL_KURT20"] = v.rolling(20).kurt()
    f["VP_CORR20"] = r.rolling(20).corr(v.pct_change())
    return f


def build():
    recs=[]
    for p in sorted(market_csv_dir().glob("*.1h.csv")):
        try: head=pd.read_csv(p,usecols=["datetime"])
        except: continue
        if len(head)<420: continue
        sym=p.name.split(".tqsdk.1h.csv")[0]
        pfx=extract_contract_prefix(sym) or ""
        d=load(p); fac=all_factors(d)
        r=d.lr.to_numpy(); z=d.z.to_numpy(); ts=d.datetime
        cols=list(fac.columns); arr=fac.to_numpy(); n=len(d)
        for t in range(N+H+1,n-H):
            zv=z[t]
            if not math.isfinite(zv): continue
            pre=r[t-100:t]
            if not np.all(np.isfinite(pre)): continue
            s_sd=pre.std(ddof=1)
            if s_sd<=0: continue
            s_pre=pre.mean()/s_sd
            if s_pre<0.10: continue  # high_s only for main analysis
            fv=arr[t]
            if not np.all(np.isfinite(fv)): continue
            rec=dict(sym=sym,pfx=pfx,t=t,ts=ts.iloc[t],z=float(zv),s_pre=float(s_pre),
                     pre_cum=float(pre.sum()),r100=float(r[t+1:t+1+H].sum()))
            for ci,cn in enumerate(cols): rec[cn]=float(fv[ci])
            recs.append(rec)
    return pd.DataFrame(recs), cols


def sp_ic(x,y):
    if len(x)<20 or np.std(x)<1e-10 or np.std(y)<1e-10: return np.nan
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return spearmanr(x,y).correlation


def boot_ic(sub, fc, rc="r100", seed=42):
    rng=np.random.default_rng(seed)
    fv=sub[fc].to_numpy(); rv=sub[rc].to_numpy(); n=len(fv)
    ics=[]
    for _ in range(N_BOOT):
        idx=rng.integers(0,n,n)
        ic=sp_ic(fv[idx],rv[idx])
        if not math.isnan(ic): ics.append(ic)
    if not ics: return np.nan,np.nan,np.nan
    return float(np.mean(ics)),float(np.quantile(ics,.025)),float(np.quantile(ics,.975))


def h1_low_volume(df, fcols):
    """H1: 缩量端动量信号。"""
    print("\n"+"="*80)
    print("H1: 缩量端动量信号验证")
    print("="*80)
    # Define volume groups
    df["vgrp"] = pd.cut(df.z, bins=[-np.inf,-1.5,-0.5,0.5,1.5,2.5,np.inf],
                        labels=["vlow2","vlow","base","mid","spike","extreme"])
    print(f"\n{'factor':<12} {'vlow2':>8} {'vlow':>8} {'base':>8} {'mid':>8} {'spike':>8} {'extreme':>8} {'vlow-base':>10}")
    focus = ["MRET20","MRET50","MRET100","MRET200","MADEV60","MADEV120","S_PRE",
             "RVOL20","VWAP_DEV20","PATEFF100","HH200"]
    h1_rows=[]
    for fc in focus:
        ics={}
        for grp in ["vlow2","vlow","base","mid","spike","extreme"]:
            sub=df[df.vgrp==grp]
            if len(sub)<20: ics[grp]=np.nan; continue
            ics[grp]=sp_ic(sub[fc].to_numpy(),sub.r100.to_numpy())
        diff = ics["vlow"]-ics["base"] if not(math.isnan(ics["vlow"]) or math.isnan(ics["base"])) else np.nan
        print(f"{fc:<12} {ics['vlow2']:>+8.3f} {ics['vlow']:>+8.3f} {ics['base']:>+8.3f} "
              f"{ics['mid']:>+8.3f} {ics['spike']:>+8.3f} {ics['extreme']:>+8.3f} {diff:>+10.3f}")
        h1_rows.append(dict(factor=fc, **{k:v for k,v in ics.items()}, diff=diff))

    # Dose-response: z quintiles
    print(f"\n--- z 五分位 IC（高 s 层）---")
    df["zq"]=pd.qcut(df.z,5,labels=["Q1","Q2","Q3","Q4","Q5"])
    print(f"{'factor':<12}", end="")
    for q in ["Q1","Q2","Q3","Q4","Q5"]: print(f" {q:>8}", end="")
    print()
    for fc in focus:
        print(f"{fc:<12}", end="")
        for q in ["Q1","Q2","Q3","Q4","Q5"]:
            sub=df[df.zq==q]
            ic=sp_ic(sub[fc].to_numpy(),sub.r100.to_numpy()) if len(sub)>=20 else np.nan
            print(f" {ic:>+8.3f}", end="")
        print()

    # OOS for low volume momentum
    print(f"\n--- H1 时间 OOS（缩量 vlow z<−0.5）---")
    dfs=df.sort_values("ts").reset_index(drop=True)
    split=int(len(dfs)*0.7)
    isp=dfs.iloc[:split]; osp=dfs.iloc[split:]
    print(f"IS n={len(isp)}, OOS n={len(osp)}")
    vlow_is=isp[isp.z<-0.5]; vlow_os=osp[osp.z<-0.5]
    base_is=isp[abs(isp.z)<0.5]; base_os=osp[abs(osp.z)<0.5]
    print(f"vlow IS={len(vlow_is)}, OOS={len(vlow_os)}; base IS={len(base_is)}, OOS={len(base_os)}")
    print(f"{'factor':<12} {'ICv_IS':>8} {'ICb_IS':>8} {'Δ_IS':>8} {'ICv_OS':>8} {'ICb_OS':>8} {'Δ_OS':>8}")
    for fc in ["MRET20","MRET50","MRET100","MADEV60","MADEV120","S_PRE","RVOL20"]:
        icv_i=sp_ic(vlow_is[fc],vlow_is.r100); icb_i=sp_ic(base_is[fc],base_is.r100)
        icv_o=sp_ic(vlow_os[fc],vlow_os.r100); icb_o=sp_ic(base_os[fc],base_os.r100)
        print(f"{fc:<12} {icv_i:>+8.3f} {icb_i:>+8.3f} {icv_i-icb_i:>+8.3f} "
              f"{icv_o:>+8.3f} {icb_o:>+8.3f} {icv_o-icb_o:>+8.3f}")

    # Absolute returns of vlow group (not just IC)
    print(f"\n--- 缩量组绝对收益（高 s 层）---")
    for grp in ["vlow2","vlow","base","mid","spike","extreme"]:
        sub=df[df.vgrp==grp]
        if len(sub)<20: continue
        m=sub.r100.mean(); pn=(sub.r100<0).mean()*100
        print(f"  {grp:<10} n={len(sub):<4} mean r100={m:+.4f} neg={pn:.0f}%")

    # Persistence: consecutive low volume
    print(f"\n--- 连续缩量天数效应（z<−0.5 连续 K 根）---")
    # need per-symbol count
    df["is_vlow"]=(df.z<-0.5).astype(int)
    df["vlow_streak"]=df.groupby("sym")["is_vlow"].transform(
        lambda x: x[::-1].groupby((x!=x.shift()).cumsum()[::-1]).cumcount()[::-1]+1 if False else
        x.groupby((x!=x.shift()).cumsum()).cumcount()+1)
    # simpler: rolling count
    df["vlow_cnt5"]=df.groupby("sym")["is_vlow"].transform(lambda x: x.rolling(5,min_periods=1).sum())
    for k in [0,1,2,3]:
        sub=df[(df.z<-0.5)&(df.vlow_cnt5>=k+1)]
        if len(sub)<20: continue
        ic=sp_ic(sub["MRET50"].to_numpy(),sub.r100.to_numpy())
        print(f"  过去5根缩量>={k+1}根: n={len(sub):<4} MRET50 IC={ic:+.3f} mean r100={sub.r100.mean():+.4f}")

    return pd.DataFrame(h1_rows)


def h4_orthogonalize(df, fcols):
    """H4: PCA + multivariate interaction to find independent dimensions."""
    print("\n"+"="*80)
    print("H4: 因子正交化与增量信息")
    print("="*80)
    from numpy.linalg import lstsq, svd

    # 1. Factor correlation
    F=df[fcols].copy()
    # standardize
    Fs=(F-F.mean())/F.std()
    corr=Fs.corr()
    print(f"\n因子相关矩阵（>0.7 的高相关对）：")
    pairs=[]
    for i,a in enumerate(fcols):
        for b in fcols[i+1:]:
            if abs(corr.loc[a,b])>0.7:
                pairs.append((a,b,corr.loc[a,b]))
    pairs.sort(key=lambda x:-abs(x[2]))
    for a,b,c in pairs[:20]:
        print(f"  {a:<12} ~ {b:<12}: {c:+.3f}")

    # 2. PCA
    print(f"\n--- PCA（{len(fcols)} 个因子）---")
    X=Fs.fillna(0).to_numpy()
    U,S,Vt=svd(X,full_matrices=False)
    var=S**2/(S**2).sum()
    print(f"{'PC':>4} {'var%':>8} {'cum%':>8}  top loadings")
    for i in range(min(10,len(S))):
        load=Vt[i]
        top=np.argsort(-np.abs(load))[:4]
        tops=", ".join(f"{fcols[j]}({load[j]:+.2f})" for j in top)
        print(f"PC{i+1:>2} {var[i]*100:>7.1f}% {var[:i+1].sum()*100:>7.1f}%  {tops}")

    # 3. Multivariate interaction: r = b0 + b1 f + b2 z + b3 f*z
    # Use standardized factors and z
    print(f"\n--- 多元交互回归（控制所有因子后看 f×z）---")
    d=df[["z","r100"]+fcols].dropna().copy()
    zs=(d.z-d.z.mean())/d.z.std()
    ys=d.r100.to_numpy()
    # Build factor matrix standardized
    Fm=(d[fcols]-d[fcols].mean())/d[fcols].std()
    # interactions
    Int=Fm.multiply(zs,axis=0)
    Xmat=np.column_stack([np.ones(len(d)),Fm.to_numpy(),zs.to_numpy().reshape(-1,1),Int.to_numpy()])
    # label columns
    labels=["const"]+fcols+["z"]+[f"{f}×z" for f in fcols]
    # drop nan
    m=np.all(np.isfinite(Xmat),axis=1)&np.isfinite(ys)
    Xmat,ys=Xmat[m],ys[m]
    beta=lstsq(Xmat,ys,rcond=None)[0]
    # bootstrap
    rng=np.random.default_rng(42)
    B=[]
    for _ in range(200):
        idx=rng.integers(0,len(ys),len(ys))
        B.append(lstsq(Xmat[idx],ys[idx],rcond=None)[0])
    B=np.array(B)
    lo=np.quantile(B,.025,axis=0); hi=np.quantile(B,.975,axis=0)
    # Print interaction terms sorted by |beta|
    interactions=[]
    for i,lab in enumerate(labels):
        if "×z" in lab:
            sig=(lo[i]*hi[i]>0)
            interactions.append((lab,beta[i],lo[i],hi[i],sig))
    interactions.sort(key=lambda x:-abs(x[1]))
    print(f"{'interaction':<20} {'β':>10} {'CI_lo':>10} {'CI_hi':>10} {'sig':>4}")
    for lab,b,l,h,sig in interactions:
        print(f"{lab:<20} {b:>+10.6f} {l:>+10.6f} {h:>+10.6f} {'*' if sig else ''}")

    # Main effects
    print(f"\n--- 因子主效应（控制其他因子和 z 后）---")
    mains=[]
    for i,lab in enumerate(labels):
        if lab in fcols:
            sig=(lo[i]*hi[i]>0)
            mains.append((lab,beta[i],lo[i],hi[i],sig))
    mains.sort(key=lambda x:-abs(x[1]))
    for lab,b,l,h,sig in mains[:15]:
        print(f"{lab:<20} {b:>+10.6f} {l:>+10.6f} {h:>+10.6f} {'*' if sig else ''}")

    # 4. Residual IC: after controlling MADEV120, does MRET50 still interact?
    print(f"\n--- 增量检验：控制 MADEV120 后各因子交互是否还显著 ---")
    # For each factor, partial out MADEV120
    madev120=Fs["MADEV120"].to_numpy()
    for target in ["MRET20","MRET50","MRET100","MRET200","S_PRE","VWAP_DEV20","RVOL20","PATEFF100"]:
        ft=Fs[target].to_numpy()
        # residualize target on madev120
        valid=np.isfinite(ft)&np.isfinite(madev120)
        Xr=np.column_stack([np.ones(valid.sum()),madev120[valid]])
        b,_,_,_=np.linalg.lstsq(Xr,ft[valid],rcond=None)
        resid=ft[valid]-Xr@b
        # interaction residualized × z
        zr=(df.z.to_numpy()[valid]-df.z.to_numpy()[valid].mean())/df.z.to_numpy()[valid].std()
        yr=df.r100.to_numpy()[valid]
        Xi=np.column_stack([np.ones(len(yr)),resid,zr,resid*zr])
        beta2=np.linalg.lstsq(Xi,yr,rcond=None)[0]
        # bootstrap b3
        rng2=np.random.default_rng(hash(target)%2**30)
        b3s=[]
        for _ in range(200):
            idx=rng2.integers(0,len(yr),len(yr))
            b3s.append(np.linalg.lstsq(Xi[idx],yr[idx],rcond=None)[0][3])
        l,h=np.quantile(b3s,[.025,.975])
        print(f"  {target:<12} residual×z β={beta2[3]:+.6f} [{l:+.6f},{h:+.6f}] {'*' if l*h>0 else ''}")


def h5_time_varying(df):
    """H5: rolling IC and market state."""
    print("\n"+"="*80)
    print("H5: 时变性与市场状态")
    print("="*80)
    d=df.sort_values("ts").reset_index(drop=True)
    # rolling 250-event IC
    print(f"\n--- 滚动 250 事件 IC（MRET50, MADEV120）---")
    win=250
    ics_m=[]; ics_v=[]; ics_s=[]
    for i in range(win,len(d),20):
        sub=d.iloc[i-win:i]
        sp=sub[sub.z>=1.5]; bs=sub[abs(sub.z)<0.5]
        if len(sp)>30 and len(bs)>50:
            ic_s=sp_ic(sp["MRET50"],sp.r100)
            ic_b=sp_ic(bs["MRET50"],bs.r100)
            ics_m.append((sub.ts.iloc[-1],ic_s,ic_b,ic_s-ic_b))
    print(f"{'date':>12} {'IC_spike':>10} {'IC_base':>10} {'ΔIC':>10}")
    for ts,ics,icb,diff in ics_m:
        print(f"{str(ts)[:10]:>12} {ics:>+10.3f} {icb:>+10.3f} {diff:>+10.3f}")

    # By calendar year / market regime
    print(f"\n--- 按时间段拆分 ---")
    d["year"]=d.ts.dt.year
    for yr in sorted(d.year.unique()):
        sub=d[d.year==yr]
        sp=sub[sub.z>=1.5]; bs=sub[abs(sub.z)<0.5]
        if len(sp)<20 or len(bs)<30: continue
        ics=sp_ic(sp["MADEV120"],sp.r100); icb=sp_ic(bs["MADEV120"],bs.r100)
        print(f"  {yr}: spike n={len(sp):<4} IC={ics:+.3f}  base n={len(bs):<4} IC={icb:+.3f}  Δ={ics-icb:+.3f}  "
              f"spike mean={sp.r100.mean():+.4f} base mean={bs.r100.mean():+.4f}")

    # Market state: by cross-sectional average s_pre (market-wide trend)
    print(f"\n--- 按市场整体 s_pre 分组（所有品种均值）---")
    daily_s=d.groupby(d.ts.dt.date).s_pre.mean()
    d["mkt_s"]=d.ts.dt.date.map(daily_s)
    d["mkt_q"]=pd.qcut(d.mkt_s,3,labels=["weak_mkt","mid_mkt","strong_mkt"])
    for mq in ["weak_mkt","mid_mkt","strong_mkt"]:
        sub=d[d.mkt_q==mq]
        sp=sub[sub.z>=1.5]; bs=sub[abs(sub.z)<0.5]
        if len(sp)<20 or len(bs)<30: continue
        ics=sp_ic(sp["MADEV120"],sp.r100); icb=sp_ic(bs["MADEV120"],bs.r100)
        print(f"  {mq:<12} spike n={len(sp):<4} IC={ics:+.3f} mean={sp.r100.mean():+.4f}  "
              f"base n={len(bs):<4} IC={icb:+.3f} mean={bs.r100.mean():+.4f}  ΔIC={ics-icb:+.3f}")

    # Per-prefix
    print(f"\n--- 逐品种 spike IC（MADEV120, 高 s 层）---")
    for pfx in sorted(d.pfx.unique()):
        sp=d[(d.pfx==pfx)&(d.z>=1.5)]
        bs=d[(d.pfx==pfx)&(abs(d.z)<0.5)]
        if len(sp)<20 or len(bs)<30: continue
        ics=sp_ic(sp["MADEV120"],sp.r100); icb=sp_ic(bs["MADEV120"],bs.r100)
        print(f"  {pfx:<6} spike n={len(sp):<4} IC={ics:+.3f} mean={sp.r100.mean():+.4f} neg={(sp.r100<0).mean()*100:.0f}%  "
              f"base IC={icb:+.3f} mean={bs.r100.mean():+.4f}")


def main():
    out=Path("/Users/gaolei/Documents/src/quant/project_data/research/volume-spike-regime-shift")
    df,fcols=build()
    print(f"high_s events: {len(df)}, factors: {len(fcols)}")
    h1_rows=h1_low_volume(df,fcols)
    h1_rows.to_csv(out/"r2_h1_low_volume.csv",index=False)
    h4_orthogonalize(df,fcols)
    h5_time_varying(df)
    print(f"\n[OK] {out}/r2_h1_low_volume.csv")


if __name__=="__main__":
    main()
