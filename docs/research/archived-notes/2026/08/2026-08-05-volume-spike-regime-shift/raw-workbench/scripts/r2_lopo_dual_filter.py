"""
r2 后续验证：
1. 缩量端 LOPO（leave-one-prefix-out）
2. MADEV120 + VWAP_DEV20 双因子模型 vs 单因子
3. 市场状态过滤器：整体市场 s_pre 作为开关
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

N = 20; H = 100; N_BOOT = 300


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
        pfx=extract_contract_prefix(sym) or ""
        d=load(p)
        c=d.close; r=d.lr.to_numpy(); z=d.z.to_numpy(); ts=d.datetime
        ma120=c.rolling(120).mean().to_numpy()
        vwap=((c*d.volume).rolling(20).sum()/d.volume.rolling(20).sum()).to_numpy()
        madev120=((c.to_numpy()-ma120)/ma120)
        vdev=((c.to_numpy()-vwap)/vwap)
        mret50=c.pct_change(50).to_numpy()
        mret100=c.pct_change(100).to_numpy()
        n=len(d)
        for t in range(N+H+1,n-H):
            zv=z[t]
            if not math.isfinite(zv): continue
            pre=r[t-100:t]
            if not np.all(np.isfinite(pre)): continue
            s_sd=pre.std(ddof=1)
            if s_sd<=0: continue
            s_pre=pre.mean()/s_sd
            if s_pre<0.10: continue
            if not(math.isfinite(madev120[t]) and math.isfinite(vdev[t])): continue
            recs.append(dict(sym=sym,pfx=pfx,t=t,ts=ts.iloc[t],z=float(zv),s_pre=float(s_pre),
                pre_cum=float(pre.sum()),
                MADEV120=float(madev120[t]), VWAP_DEV20=float(vdev[t]),
                MRET50=float(mret50[t]) if math.isfinite(mret50[t]) else np.nan,
                MRET100=float(mret100[t]) if math.isfinite(mret100[t]) else np.nan,
                r100=float(r[t+1:t+1+H].sum())))
    return pd.DataFrame(recs)


def sp_ic(x,y):
    if len(x)<20 or np.std(x)<1e-10 or np.std(y)<1e-10: return np.nan
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return spearmanr(x,y).correlation


def boot_mean(vals, seed=42):
    rng=np.random.default_rng(seed)
    a=np.asarray(vals); idx=rng.integers(0,len(a),size=(N_BOOT,len(a)))
    b=a[idx].mean(axis=1)
    return float(a.mean()),float(np.quantile(b,.025)),float(np.quantile(b,.975)),float((a<0).mean()*100)


def h1_lopo(df):
    """缩量端 LOPO。"""
    print("="*80); print("H1 LOPO：缩量端动量留一品种验证"); print("="*80)
    vlow=df[df.z<-0.5].copy()
    base=df[abs(df.z)<0.5].copy()
    print(f"vlow total n={len(vlow)}, base n={len(base)}")

    # per-prefix IC
    print(f"\n{'pfx':<6} {'n_vlow':>7} {'IC_MRET50':>10} {'IC_MADEV':>10} {'mean_r':>9} {'%neg':>6}")
    pfx_list=sorted(vlow.pfx.unique())
    for pfx in pfx_list:
        sv=vlow[vlow.pfx==pfx]
        if len(sv)<10:
            print(f"{pfx:<6} {len(sv):>7}   (too few)"); continue
        ic50=sp_ic(sv.MRET50,sv.r100)
        icm=sp_ic(sv.MADEV120,sv.r100)
        print(f"{pfx:<6} {len(sv):>7} {ic50:>+10.3f} {icm:>+10.3f} {sv.r100.mean():>+9.4f} {(sv.r100<0).mean()*100:>5.0f}%")

    # LOPO: leave one prefix out, compute IC on rest
    print(f"\n--- LOPO（留一品种）IC 稳定性 ---")
    print(f"{'held_out':<10} {'IC_vlow_MRET50':>15} {'IC_vlow_MADEV':>15} {'n':>6}")
    all_ic50=[]; all_icm=[]
    for pfx in pfx_list:
        rest=vlow[vlow.pfx!=pfx]
        if len(rest)<30: continue
        ic50=sp_ic(rest.MRET50,rest.r100)
        icm=sp_ic(rest.MADEV120,rest.r100)
        all_ic50.append(ic50); all_icm.append(icm)
        print(f"{pfx:<10} {ic50:>+15.3f} {icm:>+15.3f} {len(rest):>6}")
    if all_ic50:
        print(f"{'mean':<10} {np.mean(all_ic50):>+15.3f} {np.mean(all_icm):>+15.3f}")
        print(f"{'min':<10} {np.min(all_ic50):>+15.3f} {np.min(all_icm):>+15.3f}")
        print(f"{'sign_consistent':<10} {sum(1 for x in all_ic50 if x>0)}/{len(all_ic50):>13} {sum(1 for x in all_icm if x>0)}/{len(all_icm):>13}")

    # Compare vlow vs base in each prefix
    print(f"\n--- 逐品种：缩量 vs 正常量 mean r100 ---")
    print(f"{'pfx':<6} {'vlow_mean':>10} {'base_mean':>10} {'Δ':>10} {'vlow_n':>7} {'base_n':>7}")
    for pfx in pfx_list:
        sv=vlow[vlow.pfx==pfx]; sb=base[base.pfx==pfx]
        if len(sv)<10 or len(sb)<10: continue
        print(f"{pfx:<6} {sv.r100.mean():>+10.4f} {sb.r100.mean():>+10.4f} {sv.r100.mean()-sb.r100.mean():>+10.4f} {len(sv):>7} {len(sb):>7}")


def h4_dual_factor(df):
    """MADEV120 + VWAP_DEV20 双因子模型。"""
    print("\n"+"="*80); print("H4：MADEV120 + VWAP_DEV20 双因子模型"); print("="*80)
    sp=df[df.z>=1.5].copy()  # spike
    bs=df[abs(df.z)<0.5].copy()
    print(f"spike n={len(sp)}, base n={len(bs)}")

    # Single factor ICs
    print(f"\n{'factor':<15} {'IC_spike':>10} {'IC_base':>10} {'ΔIC':>10}")
    for fc in ["MADEV120","VWAP_DEV20","MRET50","MRET100"]:
        ics=sp_ic(sp[fc],sp.r100); icb=sp_ic(bs[fc],bs.r100)
        print(f"{fc:<15} {ics:>+10.3f} {icb:>+10.3f} {ics-icb:>+10.3f}")

    # Composite: equal-weight rank average
    for d in [sp,bs]:
        d["comp_rank"]=(d.MADEV120.rank()+d.VWAP_DEV20.rank())/2
    print(f"\n{'composite':<15} {sp_ic(sp.comp_rank,sp.r100):>+10.3f} {sp_ic(bs.comp_rank,bs.r100):>+10.3f} "
          f"{sp_ic(sp.comp_rank,sp.r100)-sp_ic(bs.comp_rank,bs.r100):>+10.3f}")

    # Residual VWAP on MADEV: does residual add info?
    from numpy.linalg import lstsq
    X=np.column_stack([np.ones(len(sp)),sp.MADEV120.to_numpy()])
    b=lstsq(X,sp.VWAP_DEV20.to_numpy(),rcond=None)[0]
    sp["vdev_resid"]=sp.VWAP_DEV20-X@b
    Xb=np.column_stack([np.ones(len(bs)),bs.MADEV120.to_numpy()])
    bb=lstsq(Xb,bs.VWAP_DEV20.to_numpy(),rcond=None)[0]
    bs["vdev_resid"]=bs.VWAP_DEV20-Xb@bb
    print(f"{'vdev_resid':<15} {sp_ic(sp.vdev_resid,sp.r100):>+10.3f} {sp_ic(bs.vdev_resid,bs.r100):>+10.3f}")

    # Double sort: MADEV terciles × VWAP terciles within spike
    print(f"\n--- spike 内双排序 mean r100 ---")
    sp["mq"]=pd.qcut(sp.MADEV120,3,labels=["M_lo","M_md","M_hi"])
    sp["vq"]=pd.qcut(sp.VWAP_DEV20,3,labels=["V_lo","V_md","V_hi"])
    tab=sp.groupby(["mq","vq"],observed=True).r100.agg(["mean","count"]).unstack()
    print(tab.round(4))

    # Best combo: high MADEV120 AND high VWAP_DEV20
    hi=sp[(sp.MADEV120>=sp.MADEV120.quantile(0.7))&(sp.VWAP_DEV20>=sp.VWAP_DEV20.quantile(0.7))]
    lo=sp[(sp.MADEV120<=sp.MADEV120.quantile(0.3))&(sp.VWAP_DEV20<=sp.VWAP_DEV20.quantile(0.3))]
    print(f"\n高 MADEV+高 VWAP: n={len(hi)} mean={hi.r100.mean():+.4f} neg={(hi.r100<0).mean()*100:.0f}%")
    print(f"低 MADEV+低 VWAP: n={len(lo)} mean={lo.r100.mean():+.4f} neg={(lo.r100<0).mean()*100:.0f}%")
    if len(hi)>10:
        m,l,h,pn=boot_mean(hi.r100.to_numpy())
        print(f"  95% CI [{l:+.4f},{h:+.4f}]")


def h5_market_filter(df):
    """市场状态过滤器。"""
    print("\n"+"="*80); print("H5：市场整体状态过滤器"); print("="*80)
    d=df.sort_values("ts").copy()
    # market-wide s_pre: cross-sectional mean per timestamp
    d["date"]=d.ts.dt.date
    mkt=d.groupby("date").s_pre.mean().rename("mkt_s")
    d=d.merge(mkt,on="date",how="left")
    d["mkt_q"]=pd.qcut(d.mkt_s,3,labels=["weak","mid","strong"])

    sp=d[d.z>=1.5]
    bs=d[abs(d.z)<0.5]
    print(f"\n{'market':<10} {'sp_n':>6} {'sp_mean':>10} {'sp_IC':>8} {'bs_n':>6} {'bs_mean':>10} {'bs_IC':>8} {'ΔIC':>8}")
    for mq in ["weak","mid","strong"]:
        s=sp[sp.mkt_q==mq]; b=bs[bs.mkt_q==mq]
        if len(s)<20 or len(b)<30: continue
        ics=sp_ic(s.MADEV120,s.r100); icb=sp_ic(b.MADEV120,b.r100)
        print(f"{mq:<10} {len(s):>6} {s.r100.mean():>+10.4f} {ics:>+8.3f} {len(b):>6} {b.r100.mean():>+10.4f} {icb:>+8.3f} {ics-icb:>+8.3f}")

    # Also for vlow
    vl=d[d.z<-0.5]
    print(f"\n缩量端按市场状态：")
    print(f"{'market':<10} {'vlow_n':>7} {'vlow_mean':>10} {'vlow_IC':>8} {'base_mean':>10} {'Δ':>10}")
    for mq in ["weak","mid","strong"]:
        s=vl[vl.mkt_q==mq]; b=bs[bs.mkt_q==mq]
        if len(s)<20 or len(b)<30: continue
        ics=sp_ic(s.MRET50,s.r100);
        print(f"{mq:<10} {len(s):>7} {s.r100.mean():>+10.4f} {ics:>+8.3f} {b.r100.mean():>+10.4f} {s.r100.mean()-b.r100.mean():>+10.4f}")

    # Conditional specification: use spike only when market is mid/strong
    print(f"\n--- 过滤后规格表现 ---")
    # unfiltered
    s_all=sp
    m_all,l_all,h_all,_=boot_mean(s_all.r100.to_numpy())
    print(f"放量（无过滤）: n={len(s_all)} mean={m_all:+.4f} CI[{l_all:+.4f},{h_all:+.4f}] neg={(s_all.r100<0).mean()*100:.0f}%")
    # filtered
    s_f=sp[sp.mkt_q!="weak"]
    m_f,l_f,h_f,_=boot_mean(s_f.r100.to_numpy())
    print(f"放量（排除弱市场）: n={len(s_f)} mean={m_f:+.4f} CI[{l_f:+.4f},{h_f:+.4f}] neg={(s_f.r100<0).mean()*100:.0f}%")
    # strong only
    s_s=sp[sp.mkt_q=="strong"]
    m_s,l_s,h_s,_=boot_mean(s_s.r100.to_numpy())
    print(f"放量（仅强市场）: n={len(s_s)} mean={m_s:+.4f} CI[{l_s:+.4f},{h_s:+.4f}] neg={(s_s.r100<0).mean()*100:.0f}%")

    # vlow filtered
    v_all=vl; v_f=vl[vl.mkt_q!="weak"]
    m_a,_,_,_=boot_mean(v_all.r100.to_numpy(),seed=1)
    m_ff,_,_,_=boot_mean(v_f.r100.to_numpy(),seed=2)
    print(f"\n缩量（无过滤）: n={len(v_all)} mean={m_a:+.4f} neg={(v_all.r100>0).mean()*100:.0f}%")
    print(f"缩量（排除弱市场）: n={len(v_f)} mean={m_ff:+.4f} neg={(v_f.r100>0).mean()*100:.0f}%")


if __name__=="__main__":
    out=Path("/Users/gaolei/Documents/src/quant/project_data/research/volume-spike-regime-shift")
    df=build()
    print(f"high_s events: {len(df)}")
    df.to_csv(out/"r2_main_dataset.csv",index=False)
    h1_lopo(df)
    h4_dual_factor(df)
    h5_market_filter(df)
    print(f"\n[OK] dataset saved to {out}/r2_main_dataset.csv")
