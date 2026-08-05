"""
检验：放量是否增加不确定性（收益绝对值/方差/IQR）？
同时区分一阶矩（均值回归）和二阶矩（不确定性）效应。

检验内容：
1. 按 z 分组，看 |r100|、r100^2、IQR、std
2. 回归 |r100| ~ z + MADEV120 + z*MADEV120 + s_pre，在各 s 层
3. 回归 r100^2 同上
4. 比较 z 对 mean vs |r| 的解释力
5. 按 MADEV 高/低分组，看放量后分布：
   - MADEV 高：均值回归（mean shift）
   - MADEV 低：是否仍有方差放大？
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


def build():
    recs=[]
    for p in sorted(market_csv_dir().glob("*.1h.csv")):
        try: head=pd.read_csv(p,usecols=["datetime"])
        except: continue
        if len(head)<420: continue
        sym=p.name.split(".tqsdk.1h.csv")[0]
        pfx=extract_contract_prefix(sym) or ""
        d=load(p)
        c=d.close; r=d.lr.to_numpy(); z=d.z.to_numpy(); n=len(d)
        ma120=c.rolling(120).mean().to_numpy()
        for t in range(N+H+1,n-H):
            zv=z[t]
            if not math.isfinite(zv): continue
            pre=r[t-100:t]
            if not np.all(np.isfinite(pre)): continue
            s_sd=pre.std(ddof=1)
            if s_sd<=0: continue
            s_pre=pre.mean()/s_sd
            if not math.isfinite(ma120[t]) or ma120[t]<=0: continue
            madev=float((c.to_numpy()[t]-ma120[t])/ma120[t])
            fut=r[t+1:t+1+H]
            r100=float(fut.sum())
            recs.append(dict(sym=sym,pfx=pfx,z=float(zv),s_pre=float(s_pre),
                madev=madev, r100=r100, abs_r=abs(r100), r2=r100*r100))
    return pd.DataFrame(recs)


def boot_mean(vals, seed=42, nb=500):
    rng=np.random.default_rng(seed)
    a=np.asarray(vals,float); a=a[np.isfinite(a)]
    if len(a)<10: return np.nan,np.nan,np.nan
    idx=rng.integers(0,len(a),size=(nb,len(a)))
    b=a[idx].mean(axis=1)
    return float(a.mean()),float(np.quantile(b,.025)),float(np.quantile(b,.975))


def boot_std(vals, seed=42, nb=500):
    rng=np.random.default_rng(seed)
    a=np.asarray(vals,float); a=a[np.isfinite(a)]
    if len(a)<10: return np.nan,np.nan,np.nan
    idx=rng.integers(0,len(a),size=(nb,len(a)))
    b=a[idx].std(axis=1,ddof=1)
    return float(a.std(ddof=1)),float(np.quantile(b,.025)),float(np.quantile(b,.975))


def analysis1_descriptive(df):
    """按 z 分组的描述统计：mean, std, |r|, IQR。"""
    print("\n"+"="*80)
    print("1. 描述统计：按 z 分组（高 s 层）")
    print("="*80)
    hi=df[df.s_pre>=0.10].copy()
    hi["vg"]=pd.cut(hi.z,bins=[-np.inf,-0.5,0.5,1.5,2.5,np.inf],
                   labels=["缩量","正常","mid","放量","极端"])
    print(f"{'组':<8} {'n':>6} {'mean':>9} {'std':>9} {'|r|mean':>9} {'r2mean':>10} {'IQR':>9} {'%large(>2%)':>11}")
    for g in ["缩量","正常","mid","放量","极端"]:
        s=hi[hi.vg==g]
        if len(s)<10: continue
        iqr=s.r100.quantile(.75)-s.r100.quantile(.25)
        large=(s.r100.abs()>0.02).mean()*100
        print(f"{g:<8} {len(s):>6} {s.r100.mean():>+9.4f} {s.r100.std():>9.4f} "
              f"{s.abs_r.mean():>9.4f} {s.r2.mean():>10.6f} {iqr:>9.4f} {large:>10.0f}%")

    print(f"\n所有 s 层：")
    df["vg"]=pd.cut(df.z,bins=[-np.inf,-0.5,0.5,1.5,2.5,np.inf],
                   labels=["缩量","正常","mid","放量","极端"])
    df["sl"]=pd.cut(df.s_pre,bins=[-np.inf,-0.10,0.10,np.inf],labels=["低s","中s","高s"])
    for sl in ["高s","中s","低s"]:
        print(f"\n  {sl}:")
        print(f"  {'组':<8} {'n':>6} {'mean':>9} {'std':>9} {'|r|':>9}")
        for g in ["缩量","正常","放量","极端"]:
            s=df[(df.sl==sl)&(df.vg==g)]
            if len(s)<10: continue
            print(f"  {g:<8} {len(s):>6} {s.r100.mean():>+9.4f} {s.r100.std():>9.4f} {s.abs_r.mean():>9.4f}")


def analysis2_regression(df):
    """回归：|r| 和 r2 对 z, MADEV, z*MADEV。"""
    print("\n"+"="*80)
    print("2. 回归：z 是否预测 |r100|（不确定性）？")
    print("="*80)
    from numpy.linalg import lstsq
    for sl_name, sl_mask in [("高 s", df.s_pre>=0.10),("中 s",(df.s_pre>-0.10)&(df.s_pre<0.10)),("低 s",df.s_pre<=-0.10)]:
        sub=df[sl_mask].dropna(subset=["madev","r100","z","abs_r"]).copy()
        if len(sub)<50: continue
        # standardize
        for col in ["z","madev","s_pre"]:
            sub[col+"_s"]=(sub[col]-sub[col].mean())/sub[col].std()
        print(f"\n--- {sl_name} (n={len(sub)}) ---")
        for target,label in [("r100","一阶矩: r100"),("abs_r","二阶矩: |r100|"),("r2","二阶矩: r100^2")]:
            X=np.column_stack([np.ones(len(sub)),
                               sub.z_s, sub.madev_s,
                               sub.z_s*sub.madev_s, sub.s_pre_s])
            y=sub[target].to_numpy()
            # remove non-finite
            m=np.all(np.isfinite(X),axis=1)&np.isfinite(y)
            X,y=X[m],y[m]
            beta=lstsq(X,y,rcond=None)[0]
            # bootstrap
            rng=np.random.default_rng(hash((sl_name,target))%2**30)
            B=[]
            for _ in range(300):
                idx=rng.integers(0,len(y),len(y))
                B.append(lstsq(X[idx],y[idx],rcond=None)[0])
            B=np.array(B)
            lo=np.quantile(B,.025,axis=0); hi=np.quantile(B,.975,axis=0)
            print(f"  {label:<18} β_z={beta[1]:+.5f}[{lo[1]:+.4f},{hi[1]:+.4f}]"
                  f"  β_madev={beta[2]:+.5f}[{lo[2]:+.4f},{hi[2]:+.4f}]"
                  f"  β_z×madev={beta[3]:+.5f}[{lo[3]:+.4f},{hi[3]:+.4f}]"
                  f"  {'*z' if lo[1]*hi[1]>0 else '   '}"
                  f"{'*int' if lo[3]*hi[3]>0 else ''}")


def analysis3_decomposition(df):
    """比较 z 对 mean vs |r| 的解释力（R²）。"""
    print("\n"+"="*80)
    print("3. 方差分解：z 解释 mean 还是 |r| 更多？")
    print("="*80)
    from numpy.linalg import lstsq
    hi=df[df.s_pre>=0.10].dropna(subset=["madev","r100","z","abs_r"]).copy()
    for col in ["z","madev","s_pre"]:
        hi[col+"_s"]=(hi[col]-hi[col].mean())/hi[col].std()

    # model 1: only z
    # model 2: z + madev
    # model 3: z + madev + interaction
    def r2(X,y):
        b=lstsq(X,y,rcond=None)[0]
        pred=X@b
        ss_res=((y-pred)**2).sum(); ss_tot=((y-y.mean())**2).sum()
        return 1-ss_res/ss_tot

    z=hi.z_s.to_numpy().reshape(-1,1); m=hi.madev_s.to_numpy().reshape(-1,1)
    ones=np.ones((len(hi),1))
    Xz=np.hstack([ones,z]); Xzm=np.hstack([ones,z,m])
    Xfull=np.hstack([ones,z,m,z*m,hi.s_pre_s.to_numpy().reshape(-1,1)])

    for target,label in [("r100","mean return (一阶)"),("abs_r","|return| (二阶)")]:
        y=hi[target].to_numpy()
        print(f"\n  {label}:")
        print(f"    仅 z:        R²={r2(Xz,y):.4f}")
        print(f"    z+MADEV:     R²={r2(Xzm,y):.4f}")
        print(f"    z+MADEV+交互: R²={r2(Xfull,y):.4f}")


def analysis4_double_sort(df):
    """MADEV 高/低 × z 高/低：mean 和 std 分别看。"""
    print("\n"+"="*80)
    print("4. 双排序：MADEV × z 对 mean 和 std 的影响（高 s 层）")
    print("="*80)
    hi=df[df.s_pre>=0.10].copy()
    hi["mq"]=pd.qcut(hi.madev,2,labels=["MADEV低","MADEV高"])
    hi["zq"]=pd.qcut(hi.z,2,labels=["z低","z高"])
    print(f"\n{'':>12} {'z低 mean':>10} {'z高 mean':>10} {'Δmean':>9} {'z低 std':>9} {'z高 std':>9} {'Δstd':>9} {'n':>5}")
    for mq in ["MADEV低","MADEV高"]:
        row=f"{mq:>12}"
        for stat_name,stat_func,fmt in [("mean",lambda x:x.mean(),"{:+.4f}"),("std",lambda x:x.std(),"{:.4f}")]:
            pass
        zl=hi[(hi.mq==mq)&(hi.zq=="z低")]
        zh=hi[(hi.mq==mq)&(hi.zq=="z高")]
        row += f" {zl.r100.mean():>+10.4f} {zh.r100.mean():>+10.4f} {zh.r100.mean()-zl.r100.mean():>+9.4f}"
        row += f" {zl.r100.std():>9.4f} {zh.r100.std():>9.4f} {zh.r100.std()-zl.r100.std():>+9.4f}"
        row += f" {len(zl)+len(zh):>5}"
        print(row)

    # Also |r|
    print(f"\n|r100| 均值：")
    print(f"{'':>12} {'z低 |r|':>10} {'z高 |r|':>10} {'Δ':>9}")
    for mq in ["MADEV低","MADEV高"]:
        zl=hi[(hi.mq==mq)&(hi.zq=="z低")]
        zh=hi[(hi.mq==mq)&(hi.zq=="z高")]
        print(f"{mq:>12} {zl.abs_r.mean():>10.4f} {zh.abs_r.mean():>10.4f} {zh.abs_r.mean()-zl.abs_r.mean():>+9.4f}")

    # Median and IQR for robustness
    print(f"\nIQR（更稳健的分布宽度）：")
    print(f"{'':>12} {'z低 IQR':>10} {'z高 IQR':>10} {'Δ':>9}")
    for mq in ["MADEV低","MADEV高"]:
        zl=hi[(hi.mq==mq)&(hi.zq=="z低")]
        zh=hi[(hi.mq==mq)&(hi.zq=="z高")]
        iqr_l=zl.r100.quantile(.75)-zl.r100.quantile(.25)
        iqr_h=zh.r100.quantile(.75)-zh.r100.quantile(.25)
        print(f"{mq:>12} {iqr_l:>10.4f} {iqr_h:>10.4f} {iqr_h-iqr_l:>+9.4f}")


def analysis5_tail(df):
    """尾部概率：放量后极端收益（|r|>3%, >5%）的概率。"""
    print("\n"+"="*80)
    print("5. 尾部概率：放量是否增加极端收益概率？")
    print("="*80)
    hi=df[df.s_pre>=0.10].copy()
    hi["vg"]=pd.cut(hi.z,bins=[-np.inf,-0.5,0.5,1.5,2.5,np.inf],
                   labels=["缩量","正常","mid","放量","极端"])
    print(f"{'组':<8} {'P(r>+3%)':>10} {'P(r<-3%)':>10} {'P(|r|>3%)':>11} {'P(|r|>5%)':>11}")
    for g in ["缩量","正常","mid","放量","极端"]:
        s=hi[hi.vg==g]
        if len(s)<10: continue
        p_up=(s.r100>0.03).mean()*100
        p_dn=(s.r100<-0.03).mean()*100
        p_abs3=(s.r100.abs()>0.03).mean()*100
        p_abs5=(s.r100.abs()>0.05).mean()*100
        print(f"{g:<8} {p_up:>9.1f}% {p_dn:>9.1f}% {p_abs3:>10.1f}% {p_abs5:>10.1f}%")


if __name__=="__main__":
    df=build()
    print(f"total events: {len(df)}")
    analysis1_descriptive(df)
    analysis2_regression(df)
    analysis3_decomposition(df)
    analysis4_double_sort(df)
    analysis5_tail(df)
