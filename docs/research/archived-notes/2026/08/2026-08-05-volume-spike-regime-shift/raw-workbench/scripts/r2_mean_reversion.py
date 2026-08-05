"""
从"放量均值回归、缩量趋势延续"角度直接验证。
核心检验：
1. 不再用 30 个因子 IC，直接看 MADEV120（价格偏离均线）在三个成交量组下的未来收益
   - 放量：MADEV 越大未来越跌（均值回归）
   - 缩量：MADEV 越大未来越涨（趋势延续）
   - 正常量：无关系
2. 这是一个 2×3 的交互：MADEV 分位 × 成交量组
3. 在不同 s 层、市场状态、年度下验证
4. 直接检验"MADEV 是否预测回归到均线"：后窗收益是否与 -MADEV 成正比
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

N = 20; H = 100; N_BOOT = 500


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
        ma20=c.rolling(20).mean().to_numpy()
        madev=((c.to_numpy()-ma120)/ma120)
        madev20=((c.to_numpy()-ma20)/ma20)
        # future return to MA: did price converge to moving average?
        n=len(d)
        for t in range(N+H+1,n-H):
            zv=z[t]
            if not math.isfinite(zv): continue
            pre=r[t-100:t]
            if not np.all(np.isfinite(pre)): continue
            s_sd=pre.std(ddof=1)
            if s_sd<=0: continue
            s_pre=pre.mean()/s_sd
            if not math.isfinite(madev[t]): continue
            future_c = c.to_numpy()[t+H]
            future_ma = ma120[t+H] if math.isfinite(ma120[t+H]) else np.nan
            recs.append(dict(
                sym=sym,pfx=pfx,t=t,ts=ts.iloc[t],z=float(zv),
                s_pre=float(s_pre), madev=float(madev[t]), madev20=float(madev20[t]),
                pre_cum=float(pre.sum()),
                r100=float(r[t+1:t+1+H].sum()),
                # convergence: future close relative to future MA120
                future_dev=float((future_c-future_ma)/future_ma) if math.isfinite(future_ma) else np.nan,
            ))
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


def main():
    out=Path("/Users/gaolei/Documents/src/quant/project_data/research/volume-spike-regime-shift")
    df=build()
    print(f"total events: {len(df)}")

    # Define volume groups
    df["vg"]=pd.cut(df.z,bins=[-np.inf,-0.5,0.5,1.5,np.inf],
                   labels=["缩量","正常","放量","极端"])
    # MADEV terciles (pooled)
    df["mq"]=pd.qcut(df.madev,3,labels=["低MADEV","中MADEV","高MADEV"])

    # ========== 1. 全 s 层的 3×3 表 ==========
    print("\n"+"="*80)
    print("检验 1：MADEV × 成交量 → 未来 r100（全样本，不分 s 层）")
    print("="*80)
    print(f"{'':>10}", end="")
    for vg in ["缩量","正常","放量","极端"]: print(f" {vg:>12}", end="")
    print("   | IC(MADEV,r100)")
    for mq in ["低MADEV","中MADEV","高MADEV"]:
        print(f"{mq:>10}", end="")
        for vg in ["缩量","正常","放量","极端"]:
            sub=df[(df.vg==vg)&(df.mq==mq)]
            m=sub.r100.mean() if len(sub)>10 else np.nan
            print(f" {m:>+12.4f}", end="")
        print()
    print(f"\n{'IC':>10}", end="")
    for vg in ["缩量","正常","放量","极端"]:
        sub=df[df.vg==vg]
        ic=sp_ic(sub.madev,sub.r100)
        print(f" {ic:>+12.3f}", end="")
    print()
    print("  正IC=趋势延续（MADEV大继续涨），负IC=均值回归（MADEV大反而跌）")

    # ========== 2. 按 s 层 ==========
    print("\n"+"="*80)
    print("检验 2：按 s_pre 分层（高/中/低）")
    print("="*80)
    df["sl"]=pd.cut(df.s_pre,bins=[-np.inf,-0.10,0.10,np.inf],labels=["低s(下跌)","中s(震荡)","高s(上涨)"])
    for sl in ["高s(上涨)","中s(震荡)","低s(下跌)"]:
        sub=df[df.sl==sl]
        print(f"\n--- {sl} (n={len(sub)}) ---")
        print(f"{'':>10}", end="")
        for vg in ["缩量","正常","放量","极端"]: print(f" {vg:>12}", end="")
        print(f" {'n_缩':>6}{'n_放':>6}")
        for mq in ["低MADEV","中MADEV","高MADEV"]:
            print(f"{mq:>10}", end="")
            for vg in ["缩量","正常","放量","极端"]:
                s=sub[(sub.vg==vg)&(sub.mq==mq)]
                m=s.r100.mean() if len(s)>5 else np.nan
                print(f" {m:>+12.4f}", end="")
            ns=len(sub[(sub.vg=="缩量")&(sub.mq==mq)]); nf=len(sub[(sub.vg=="放量")&(sub.mq==mq)])
            print(f" {ns:>6}{nf:>6}")
        print(f"{'IC':>10}", end="")
        for vg in ["缩量","正常","放量","极端"]:
            s=sub[sub.vg==vg]
            ic=sp_ic(s.madev,s.r100) if len(s)>20 else np.nan
            print(f" {ic:>+12.3f}", end="")
        print()

    # ========== 3. 核心：高s层，缩量高MADEV vs 放量高MADEV 的直接对比 ==========
    print("\n"+"="*80)
    print("检验 3：核心对比（高 s 层）")
    print("="*80)
    hi=df[df.sl=="高s(上涨)"]
    for vg in ["缩量","正常","放量","极端"]:
        s=hi[hi.vg==vg]
        m,l,h=boot(s.r100,seed=hash(vg)%2**30)
        ic=sp_ic(s.madev,s.r100)
        # high MADEV only
        hm=s[s.mq=="高MADEV"]
        m2,l2,h2=boot(hm.r100,seed=hash(vg+"h")%2**30)
        print(f"  {vg:<6} n={len(s):<4} all mean={m:+.4f} [{l:+.4f},{h:+.4f}]  IC(madev)={ic:+.3f}  | 高MADEV n={len(hm):<3} mean={m2:+.4f} [{l2:+.4f},{h2:+.4f}] neg={(hm.r100<0).mean()*100:.0f}%")

    # 直接多空：缩量高MADEV 做多 vs 放量高MADEV 做空
    print(f"\n--- 多空组合（高 s 层，高 MADEV 组）---")
    vlow_hi=hi[(hi.vg=="缩量")&(hi.mq=="高MADEV")]
    spike_hi=hi[(hi.vg.isin(["放量","极端"]))&(hi.mq=="高MADEV")]
    normal_hi=hi[(hi.vg=="正常")&(hi.mq=="高MADEV")]
    for name,s in [("缩量+高MADEV(做多)",vlow_hi),("正常+高MADEV",normal_hi),("放量+高MADEV(做空)",spike_hi)]:
        m,l,h=boot(s.r100)
        print(f"  {name:<22} n={len(s):<4} mean={m:+.4f} [{l:+.4f},{h:+.4f}]")
    if len(vlow_hi)>10 and len(spike_hi)>10:
        diff=vlow_hi.r100.mean()-spike_hi.r100.mean()
        print(f"\n  多空差（缩量高MADEV − 放量高MADEV）= {diff:+.4f}")

    # ========== 4. 均值回归的直接检验：future_dev ==========
    print("\n"+"="*80)
    print("检验 4：价格是否回归到 MA120？（future_dev = (close[t+H]-MA[t+H])/MA[t+H]）")
    print("="*80)
    hi2=hi.dropna(subset=["future_dev"])
    print(f"高 s 层有 future_dev 的事件: {len(hi2)}")
    for vg in ["缩量","正常","放量","极端"]:
        s=hi2[hi2.vg==vg]
        # 当前偏离 vs 未来偏离
        curr_dev=s.madev.mean()
        fut_dev=s.future_dev.mean()
        conv=curr_dev-fut_dev  # 收敛幅度
        ic=sp_ic(s.madev,s.future_dev)
        print(f"  {vg:<6} n={len(s):<4} 当前MADEV={curr_dev:+.4f} H后偏离={fut_dev:+.4f} 收敛={conv:+.4f} IC(madev→future_dev)={ic:+.3f}")
    print("  收敛>0 = 价格向均线回归；IC负 = 偏离越大未来越接近均线")

    # ========== 5. 时变性 ==========
    print("\n"+"="*80)
    print("检验 5：年度稳定性（高 s 层 IC）")
    print("="*80)
    hi["year"]=hi.ts.dt.year
    for yr in sorted(hi.year.unique()):
        s=hi[hi.year==yr]
        print(f"\n  {yr} (n={len(s)}):")
        for vg in ["缩量","正常","放量","极端"]:
            ss=s[s.vg==vg]
            ic=sp_ic(ss.madev,ss.r100) if len(ss)>20 else np.nan
            m=ss.r100.mean() if len(ss)>10 else np.nan
            print(f"    {vg:<6} n={len(ss):<4} IC={ic:+.3f} mean={m:+.4f}")

    # ========== 6. 逐品种 ==========
    print("\n"+"="*80)
    print("检验 6：逐品种（高 s 层，缩量 vs 放量 的 MADEV IC）")
    print("="*80)
    print(f"{'pfx':<6} {'n_vlow':>7} {'IC_vlow':>9} {'mean_vlow':>10} {'n_spike':>8} {'IC_spike':>10} {'mean_spike':>11} {'一致?':>6}")
    for pfx in sorted(hi.pfx.unique()):
        s=hi[hi.pfx==pfx]
        vl=s[s.vg=="缩量"]; sp=s[s.vg.isin(["放量","极端"])]
        if len(vl)<10 or len(sp)<10: continue
        iv=sp_ic(vl.madev,vl.r100); isp=sp_ic(sp.madev,sp.r100)
        consistent = (iv>0 and isp<0)
        print(f"{pfx:<6} {len(vl):>7} {iv:>+9.3f} {vl.r100.mean():>+10.4f} {len(sp):>8} {isp:>+10.3f} {sp.r100.mean():>+11.4f} {'✓' if consistent else '':>6}")

    df.to_csv(out/"r2_mean_reversion_test.csv",index=False)
    print(f"\n[OK] {out}/r2_mean_reversion_test.csv")


if __name__=="__main__":
    main()
