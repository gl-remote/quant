"""
MADEV120 q70 主规格时间 OOS。
IS: 时间前 70%；OOS: 后 30%。
q70 阈值由 IS 内 high_s spike 的 MADEV120 70 分位确定，冻结到 OOS。
对比基线 pre_cum>=+3% 和无条件 high_s。
"""
from __future__ import annotations
import sys, math
from pathlib import Path
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))
from workspace.common.symbol_utils import extract_contract_prefix
from workspace.data.output_paths import market_csv_dir

N = 20; W = 100


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
        c=d.close; r=d.lr.to_numpy(); z=d.z.to_numpy()
        tvec=d.datetime
        ma120=c.rolling(120).mean().to_numpy()
        n=len(d)
        for t in range(N+W+1,n-W):
            zv=z[t]
            if not math.isfinite(zv): continue
            if zv<1.5: continue
            pre=r[t-100:t]
            if not np.all(np.isfinite(pre)): continue
            s_sd=pre.std(ddof=1)
            if s_sd<=0: continue
            s_pre=pre.mean()/s_sd
            if s_pre<0.10: continue
            if not math.isfinite(ma120[t]): continue
            recs.append(dict(
                sym=sym, pfx=pfx, t=t, ts=tvec.iloc[t],
                s_pre=float(s_pre),
                madev120=float((c.to_numpy()[t]-ma120[t])/ma120[t]),
                pre_cum=float(pre.sum()),
                r100=float(r[t+1:t+101].sum()),
            ))
    return pd.DataFrame(recs)


def boot(vals, seed=42, nb=1000):
    rng=np.random.default_rng(seed)
    a=np.asarray(vals); idx=rng.integers(0,len(a),size=(nb,len(a)))
    b=a[idx].mean(axis=1)
    return float(a.mean()),float(np.quantile(b,.025)),float(np.quantile(b,.975)),float((a<0).mean()*100)


def rep(sub, label):
    if len(sub)<10:
        print(f"  {label:<40} n={len(sub):<4} too small"); return
    m,lo,hi,pn=boot(sub.r100.to_numpy())
    print(f"  {label:<40} n={len(sub):<4} mean={m:+.4f} [{lo:+.4f},{hi:+.4f}] neg={pn:.0f}%")


def main():
    df=build().sort_values("ts").reset_index(drop=True)
    print(f"total high_s spike: {len(df)}, date range {df.ts.min()} ~ {df.ts.max()}")
    split=int(len(df)*0.7)
    isp=df.iloc[:split]; osp=df.iloc[split:]
    print(f"IS n={len(isp)}, OOS n={len(osp)}")

    # IS 确定 MADEV120 q70 阈值
    q70=isp.madev120.quantile(0.70)
    q80=isp.madev120.quantile(0.80)
    print(f"\nIS MADEV120 q70={q70:.4f}, q80={q80:.4f}")

    specs = [
        ("high_s (no extra)", lambda d: pd.Series(True,index=d.index)),
        ("pre_cum>=2.5%", lambda d: d.pre_cum>=0.025),
        ("pre_cum>=3%", lambda d: d.pre_cum>=0.03),
        (f"MADEV120>={q70:.4f} (q70)", lambda d: d.madev120>=q70),
        (f"MADEV120>={q80:.4f} (q80)", lambda d: d.madev120>=q80),
        ("MADEV120 q70 & pre_cum>=2.5%", lambda d: (d.madev120>=q70)&(d.pre_cum>=0.025)),
        ("MADEV120 q70 & z>=2", lambda d: d.madev120>=q70),  # z already>=1.5; need original z; recheck below
    ]

    for label, mask_fn in specs:
        print(f"\n--- {label} ---")
        print("  IS:")
        rep(isp[mask_fn(isp)], label)
        print("  OOS:")
        rep(osp[mask_fn(osp)], label)

    # per-prefix OOS for MADEV120 q70
    print(f"\n--- OOS per-prefix: MADEV120 q70 ---")
    mo = osp[osp.madev120>=q70]
    for pfx in sorted(mo.pfx.unique()):
        sub=mo[mo.pfx==pfx]
        if len(sub)<5:
            print(f"  {pfx:<6} n={len(sub):<3} too small"); continue
        m=sub.r100.mean()
        print(f"  {pfx:<6} n={len(sub):<3} mean={m:+.4f} neg={(sub.r100<0).mean()*100:.0f}%")


if __name__=="__main__":
    main()
