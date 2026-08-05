"""
r2 后续四分析：
1. MADEV vs s_pre 因果分离（正交化）
2. 逐品种一致性深入
3. 组合信号系统（缩量持有+放量空仓）
4. MADEV 均线周期选择 + 回归路径
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

N = 20; H = 100; N_BOOT = 400


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
        if len(head)<600: continue
        sym=p.name.split(".tqsdk.1h.csv")[0]
        pfx=extract_contract_prefix(sym) or ""
        d=load(p)
        c=d.close; r=d.lr.to_numpy(); z=d.z.to_numpy(); ts=d.datetime
        c_arr=c.to_numpy()
        # MA for multiple periods
        mas={L: c.rolling(L).mean().to_numpy() for L in [20,40,60,80,120,200]}
        n=len(d)
        for t in range(200+H+1, n-H):
            zv=z[t]
            if not math.isfinite(zv): continue
            pre=r[t-100:t]
            if not np.all(np.isfinite(pre)): continue
            s_sd=pre.std(ddof=1)
            if s_sd<=0: continue
            s_pre=pre.mean()/s_sd
            rec=dict(sym=sym,pfx=pfx,t=t,ts=ts.iloc[t],z=float(zv),s_pre=float(s_pre),
                     pre_cum=float(pre.sum()),
                     r100=float(r[t+1:t+1+H].sum()))
            for L,ma in mas.items():
                if math.isfinite(ma[t]) and ma[t]>0:
                    rec[f"MADEV{L}"]=float((c_arr[t]-ma[t])/ma[t])
            # path: deviation at intermediate horizons
            for h in [20,40,60,80,100]:
                if t+h < n and math.isfinite(mas[120][t+h]) and mas[120][t+h]>0:
                    rec[f"dev{h}"]=float((c_arr[t+h]-mas[120][t+h])/mas[120][t+h])
            recs.append(rec)
    return pd.DataFrame(recs)


def sp_ic(x,y):
    if len(x)<20 or np.std(x)<1e-10 or np.std(y)<1e-10: return np.nan
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return spearmanr(x,y).correlation


def boot(vals, seed=42):
    rng=np.random.default_rng(seed)
    a=np.asarray(vals,float); a=a[np.isfinite(a)]
    if len(a)<10: return np.nan,np.nan,np.nan
    idx=rng.integers(0,len(a),size=(N_BOOT,len(a)))
    b=a[idx].mean(axis=1)
    return float(a.mean()),float(np.quantile(b,.025)),float(np.quantile(b,.975))


def analysis1_causal(df):
    """MADEV120 vs s_pre vs pre_cum：哪个独立驱动放量回归？"""
    print("\n"+"="*80)
    print("分析 1：MADEV120 vs s_pre vs pre_cum 因果分离")
    print("="*80)
    hi=df[df.s_pre>=0.10].copy()
    sp=hi[hi.z>=1.5].copy()
    print(f"高 s+放量 n={len(sp)}")

    # Correlations
    print(f"\n相关矩阵（spike 内）：")
    cols=["MADEV120","s_pre","pre_cum","r100"]
    print(sp[cols].corr().round(3).to_string())

    # Sequential residualization: does MADEV predict after controlling for s_pre, and vice versa?
    from numpy.linalg import lstsq
    y=sp.r100.to_numpy()
    # Standardize
    def resid(y,x):
        X=np.column_stack([np.ones(len(x)),x])
        b=lstsq(X,y,rcond=None)[0]
        return y-X@b, b

    # Step 1: raw ICs
    for v in ["MADEV120","s_pre","pre_cum"]:
        print(f"  raw IC({v}, r100) = {sp_ic(sp[v],sp.r100):+.3f}")

    # Step 2: MADEV residual on s_pre
    for target, ctrl in [("MADEV120","s_pre"),("s_pre","MADEV120"),
                          ("MADEV120","pre_cum"),("pre_cum","MADEV120"),
                          ("s_pre","pre_cum"),("pre_cum","s_pre")]:
        valid=sp[[target,ctrl,"r100"]].dropna()
        r_target,_=resid(valid[target].to_numpy(), valid[ctrl].to_numpy())
        r_y,_=resid(valid.r100.to_numpy(), valid[ctrl].to_numpy())
        ic=sp_ic(r_target, r_y)
        print(f"  IC({target} | {ctrl}) = {ic:+.3f}")

    # Double sort: MADEV terciles x s_pre terciles within spike
    print(f"\n双排序（spike 内 mean r100）：")
    sp["mq"]=pd.qcut(sp.MADEV120,3,labels=["M低","M中","M高"])
    sp["sq"]=pd.qcut(sp.s_pre,3,labels=["s低","s中","s高"])
    print(sp.groupby(["sq","mq"],observed=True).r100.agg(["mean","count"]).round(4).to_string())

    # Same for vlow
    print(f"\n缩量端双排序（vlow 内 mean r100）：")
    vl=hi[hi.z<-0.5].copy()
    if len(vl)>30:
        vl["mq"]=pd.qcut(vl.MADEV120,3,labels=["M低","M中","M高"])
        vl["sq"]=pd.qcut(vl.s_pre,3,labels=["s低","s中","s高"])
        print(vl.groupby(["sq","mq"],observed=True).r100.agg(["mean","count"]).round(4).to_string())


def analysis2_per_prefix(df):
    """逐品种深入：为什么单品种不一致？"""
    print("\n"+"="*80)
    print("分析 2：逐品种一致性深入")
    print("="*80)
    hi=df[df.s_pre>=0.10].copy()
    print(f"{'pfx':<6} {'n_vl':>5} {'vl_mean':>9} {'vl_IC':>7} {'n_sp':>5} {'sp_mean':>9} {'sp_IC':>7} {'dir_ok':>7} {'contribution':>12}")
    total_sp=0; total_vl=0
    for pfx in sorted(hi.pfx.unique()):
        s=hi[hi.pfx==pfx]
        vl=s[s.z<-0.5]; sp=s[s.z>=1.5]
        if len(vl)<5 or len(sp)<5: continue
        iv=sp_ic(vl.MADEV120,vl.r100) if len(vl)>=15 else np.nan
        isp=sp_ic(sp.MADEV120,sp.r100) if len(sp)>=15 else np.nan
        mv=vl.r100.mean(); ms=sp.r100.mean()
        ok = (not math.isnan(iv)) and (not math.isnan(isp)) and iv>0 and isp<0
        total_sp+=len(sp); total_vl+=len(vl)
        # contribution to total mean
        print(f"{pfx:<6} {len(vl):>5} {mv:>+9.4f} {iv:>+7.3f} {len(sp):>5} {ms:>+9.4f} {isp:>+7.3f} {'✓' if ok else '':>7} {len(sp)*ms:>+12.4f}")

    # Aggregate vs average-of-prefixes
    print(f"\n全样本聚合 IC:  缩量={sp_ic(hi[hi.z<-0.5].MADEV120,hi[hi.z<-0.5].r100):+.3f}  "
          f"放量={sp_ic(hi[hi.z>=1.5].MADEV120,hi[hi.z>=1.5].r100):+.3f}")

    # Is it a timing effect? check if within each prefix the sign is right but weak
    prefix_ics_vl=[]; prefix_ics_sp=[]
    for pfx in hi.pfx.unique():
        s=hi[hi.pfx==pfx]
        vl=s[s.z<-0.5]; sp=s[s.z>=1.5]
        if len(vl)>=15: prefix_ics_vl.append(sp_ic(vl.MADEV120,vl.r100))
        if len(sp)>=15: prefix_ics_sp.append(sp_ic(sp.MADEV120,sp.r100))
    print(f"\n品种平均 IC:  缩量={np.nanmean(prefix_ics_vl):+.3f} (n={len(prefix_ics_vl)}), "
          f"放量={np.nanmean(prefix_ics_sp):+.3f} (n={len(prefix_ics_sp)})")
    print(f"正 IC 比例:  缩量={sum(1 for x in prefix_ics_vl if x>0)}/{len(prefix_ics_vl)}, "
          f"放量={sum(1 for x in prefix_ics_sp if x<0)}/{len(prefix_ics_sp)}")

    # Event-time: is the signal consistent but low power? check mean signs per prefix
    print(f"\n各品种 mean 方向一致性：")
    vl_signs=[]; sp_signs=[]
    for pfx in hi.pfx.unique():
        s=hi[hi.pfx==pfx]
        vl=s[s.z<-0.5]; sp=s[s.z>=1.5]
        if len(vl)>=5: vl_signs.append(vl.r100.mean()>0)
        if len(sp)>=5: sp_signs.append(sp.r100.mean()<0)
    print(f"  缩量 mean>0: {sum(vl_signs)}/{len(vl_signs)}")
    print(f"  放量 mean<0: {sum(sp_signs)}/{len(sp_signs)}")


def analysis3_portfolio(df):
    """组合信号系统：缩量高MADEV持有，放量高MADEV空仓/空，其他基准"""
    print("\n"+"="*80)
    print("分析 3：组合信号系统")
    print("="*80)
    hi=df[df.s_pre>=0.10].copy()
    # Define signals (using MADEV120 top tercile as "high")
    hi["hi_madev"]=hi.MADEV120>=hi.MADEV120.quantile(0.67)

    # Equal-weight per-event returns, but events overlap; treat as indicator on each bar
    # Strategy: when signal is active, take position; overlap handled by averaging active positions
    print(f"信号定义：高 s + MADEV120 前 33%")
    print(f"\n{'状态':<20} {'n':>6} {'mean r100':>10} {'%pos':>6} {'年化近似':>10}")
    for name, mask in [
        ("缩量+高MADEV(做多)", (hi.z<-0.5)&hi.hi_madev),
        ("缩量+全部", hi.z<-0.5),
        ("正常+高MADEV", (abs(hi.z)<0.5)&hi.hi_madev),
        ("放量+高MADEV(空仓)", (hi.z>=1.5)&hi.hi_madev),
        ("极端放量+高MADEV", (hi.z>=2.5)&hi.hi_madev),
        ("全部高s", hi.index==hi.index),
    ]:
        sub=hi[mask]
        if len(sub)<10: continue
        m,l,h=boot(sub.r100)
        # annualized: r100 is ~20 trading days; events overlap heavily, rough
        ann=m*(252/100*5)  # 1h bars: 100 bars = 20 days, 252 days/year
        print(f"{name:<20} {len(sub):>6} {m:>+10.4f} {(sub.r100>0).mean()*100:>5.0f}% {ann:>+10.4f}")

    # Simulate simple strategy per symbol: hold when vlow+high madev, flat when spike+high madev, else hold baseline (always long in high s)
    print(f"\n--- 简易策略模拟（per symbol, 高 s 期间）---")
    strat_returns=[]
    bench_returns=[]
    for sym, s in hi.groupby("sym"):
        s=s.sort_values("t").reset_index(drop=True)
        # For each bar, determine position based on signal at that bar, hold H=100 bars
        # Simplification: use non-overlapping decisions every 100 bars
        for i in range(0, len(s)-100, 100):
            row=s.iloc[i]
            ret=s.iloc[i+100].r100 if i+100<len(s) else np.nan
            if not math.isfinite(ret): continue
            bench_returns.append(ret)
            if row.z<-0.5 and row.hi_madev:
                strat_returns.append(ret)  # long
            elif row.z>=1.5 and row.hi_madev:
                strat_returns.append(0.0)  # flat (avoid drawdown)
            else:
                strat_returns.append(ret)  # hold
    bench=np.array(bench_returns); strat=np.array(strat_returns)
    print(f"  基准（高 s 全程持有）: n={len(bench)} mean={bench.mean():+.4f} sharpe={bench.mean()/bench.std()*math.sqrt(252/20):+.2f}")
    print(f"  策略（缩量持/放量平）: n={len(strat)} mean={strat.mean():+.4f} sharpe={strat.mean()/strat.std()*math.sqrt(252/20):+.2f}")
    print(f"  改善: {(strat.mean()-bench.mean())*100:+.2f}% per 20d")

    # Also short version
    strat_short=[]
    for sym, s in hi.groupby("sym"):
        s=s.sort_values("t").reset_index(drop=True)
        for i in range(0, len(s)-100, 100):
            row=s.iloc[i]
            ret=s.iloc[i+100].r100 if i+100<len(s) else np.nan
            if not math.isfinite(ret): continue
            if row.z<-0.5 and row.hi_madev:
                strat_short.append(ret)
            elif row.z>=1.5 and row.hi_madev:
                strat_short.append(-ret)  # short
            else:
                strat_short.append(ret)
    ss=np.array(strat_short)
    print(f"  策略+放量做空: n={len(ss)} mean={ss.mean():+.4f} sharpe={ss.mean()/ss.std()*math.sqrt(252/20):+.2f}")


def analysis4_ma_period(df):
    """MADEV 周期选择 + 回归路径"""
    print("\n"+"="*80)
    print("分析 4：MADEV 均线周期选择")
    print("="*80)
    hi=df[df.s_pre>=0.10].copy()
    sp=hi[hi.z>=2.5]  # extreme volume (cleaner)
    vl=hi[hi.z<-0.5]
    bs=hi[abs(hi.z)<0.5]
    print(f"极端放量 n={len(sp)}, 缩量 n={len(vl)}, 正常 n={len(bs)}")

    print(f"\n{'MA周期':<8} {'IC(extreme)':>12} {'IC(vlow)':>10} {'IC(base)':>10} {'ΔIC(ext-vl)':>12}")
    for L in [20,40,60,80,120,200]:
        col=f"MADEV{L}"
        if col not in sp or sp[col].notna().sum()<30: continue
        ie=sp_ic(sp[col].dropna(),sp.loc[sp[col].notna(),"r100"])
        iv=sp_ic(vl[col].dropna(),vl.loc[vl[col].notna(),"r100"])
        ib=sp_ic(bs[col].dropna(),bs.loc[bs[col].notna(),"r100"])
        print(f"{L:<8} {ie:>+12.3f} {iv:>+10.3f} {ib:>+10.3f} {ie-iv:>+12.3f}")

    # Regression path: how does dev120 evolve after spike?
    print(f"\n回归路径（MADEV120 随时间变化，极端放量高 MADEV 组）：")
    sp_hi=sp[sp.MADEV120>=sp.MADEV120.quantile(0.67)]
    vl_hi=vl[vl.MADEV120>=vl.MADEV120.quantile(0.67)]
    print(f"{'时点':<8} {'spike_dev':>10} {'vlow_dev':>10} {'差值':>10} {'spike_n':>8}")
    print(f"{'t=0':<8} {sp_hi.MADEV120.mean():>+10.4f} {vl_hi.MADEV120.mean():>+10.4f} {sp_hi.MADEV120.mean()-vl_hi.MADEV120.mean():>+10.4f} {len(sp_hi):>8}")
    for h in [20,40,60,80,100]:
        col=f"dev{h}"
        if col not in sp_hi: continue
        se=sp_hi[col].mean(); ve=vl_hi[col].mean()
        print(f"t+{h:<5} {se:>+10.4f} {ve:>+10.4f} {se-ve:>+10.4f} {sp_hi[col].notna().sum():>8}")

    # Price return path
    print(f"\n收益路径（累计 r）：")
    for h in [20,40,60,80,100]:
        # we only have r100; approximate by using MADEV convergence
        pass
    # Can compute r20,40,60,80 by reloading - skip, use dev as proxy
    print(f"（用 dev 路径代表：放量高 MADEV 从 +{sp_hi.MADEV120.mean()*100:.2f}% 到 t+100 {sp_hi['dev100'].mean()*100:+.2f}%，缩量从 +{vl_hi.MADEV120.mean()*100:.2f}% 到 t+100 {vl_hi['dev100'].mean()*100:+.2f}%）")


if __name__=="__main__":
    out=Path("/Users/gaolei/Documents/src/quant/project_data/research/volume-spike-regime-shift")
    df=build()
    print(f"total events: {len(df)}")
    df.to_csv(out/"r2_deep_analysis.csv",index=False)
    analysis1_causal(df)
    analysis2_per_prefix(df)
    analysis3_portfolio(df)
    analysis4_ma_period(df)
    print(f"\n[OK] {out}/r2_deep_analysis.csv")
