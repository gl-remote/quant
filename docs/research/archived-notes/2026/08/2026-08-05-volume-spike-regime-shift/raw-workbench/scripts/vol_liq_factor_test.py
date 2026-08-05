"""
波动率 + 流动性类因子 × volume spike 交互检验。
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

N = 20; H_GRID = [100]; N_BOOT = 300


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
    c, hh, ll, r, v = d.close, d.high, d.low, d.lr, d.volume
    f = pd.DataFrame(index=d.index)
    # 已实现波动
    for L in [20, 60]:
        f[f"RVOL{L}"] = r.rolling(L).std(ddof=1)
    # ATR
    tr = pd.concat([(hh-ll), (hh-c.shift()).abs(), (ll-c.shift()).abs()], axis=1).max(axis=1)
    for L in [14, 60]:
        f[f"ATR{L}"] = tr.rolling(L).mean()
    # 振幅
    f["RANGE1"] = (hh-ll)/c
    f["RANGE20"] = f["RANGE1"].rolling(20).mean()
    # 波动率变化
    f["VOL_RATIO"] = r.rolling(20).std(ddof=1) / r.rolling(60).std(ddof=1)
    # 偏度峰度
    f["SKEW20"] = r.rolling(20).skew()
    f["KURT20"] = r.rolling(20).kurt()
    # Parkinson vol
    log_hl = np.log(hh/ll)
    f["PARK20"] = np.sqrt((log_hl**2).rolling(20).mean() / (4*math.log(2)))
    # 下行波动占比
    neg = r.where(r<0, 0)
    f["DOWN_VOL20"] = neg.rolling(20).std(ddof=1) / r.rolling(20).std(ddof=1).replace(0, np.nan)
    # === 流动性 ===
    # Amihud
    notional = v * c
    f["AMIHUD20"] = (r.abs()/notional.replace(0, np.nan)).rolling(20).mean()
    # Kyle lambda approx
    f["KYLE20"] = r.abs()/np.sqrt(v.replace(0, np.nan))
    # spread proxy (Corwin-Schultz simplified)
    beta = (np.log(hh/ll)**2).rolling(2).mean()
    gamma = (np.log(hh.combine(c.shift(), max) / ll.combine(c.shift(), min))**2).rolling(2).mean()
    alpha = (np.sqrt(2*beta)-np.sqrt(beta))/(3-2*np.sqrt(2)) - np.sqrt(gamma/(3-2*np.sqrt(2)))
    f["SPREAD20"] = (2*(np.exp(alpha)-1)/(1+np.exp(alpha))).rolling(20).mean()
    # volume kurtosis (spikiness of volume)
    f["VOL_KURT20"] = v.rolling(20).kurt()
    # turnover concentration
    f["AMIHUD5"] = (r.abs()/notional.replace(0,np.nan)).rolling(5).mean()
    return f


def build():
    recs = []
    for p in sorted(market_csv_dir().glob("*.1h.csv")):
        try: head = pd.read_csv(p, usecols=["datetime"])
        except: continue
        if len(head) < 420: continue
        sym = p.name.split(".tqsdk.1h.csv")[0]
        d = load(p); fac = factors(d)
        r = d.lr.to_numpy(); z = d.z.to_numpy()
        cols = list(fac.columns); arr = fac.to_numpy(); n=len(d)
        for t in range(N+101, n-100):
            zv = z[t]
            if not math.isfinite(zv): continue
            if zv >= 1.5: grp="spike"
            elif abs(zv)<0.5: grp="base"
            else: continue
            pre = r[t-100:t]
            if not np.all(np.isfinite(pre)): continue
            s_sd = pre.std(ddof=1)
            if s_sd<=0: continue
            s_pre = pre.mean()/s_sd
            fv = arr[t]
            if not np.all(np.isfinite(fv)): continue
            rec = dict(sym=sym, grp=grp, s_pre=float(s_pre))
            for ci,cn in enumerate(cols): rec[cn]=float(fv[ci])
            rec["r100"] = float(r[t+1:t+101].sum())
            recs.append(rec)
    return pd.DataFrame(recs), cols


def s_layer(s):
    if s>=0.10: return "high_s"
    if s<=-0.10: return "low_s"
    return "mid_s"


def sp_ic(x,y):
    if len(x)<10 or np.std(x)<1e-10 or np.std(y)<1e-10: return np.nan
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return spearmanr(x,y).correlation


def boot(sp,bs,fc,rc,seed):
    rng=np.random.default_rng(seed)
    fs,rs=sp[fc].to_numpy(),sp[rc].to_numpy()
    fb,rb=bs[fc].to_numpy(),bs[rc].to_numpy()
    ns,nb=len(fs),len(fb); d=[]
    for _ in range(N_BOOT):
        i=rng.integers(0,ns,ns); j=rng.integers(0,nb,nb)
        a=sp_ic(fs[i],rs[i]); b=sp_ic(fb[j],rb[j])
        if not(math.isnan(a) or math.isnan(b)): d.append(a-b)
    if not d: return np.nan,np.nan,np.nan
    return float(np.mean(d)),float(np.quantile(d,.025)),float(np.quantile(d,.975))


def main():
    out = Path("/Users/gaolei/Documents/src/quant/project_data/research/volume-spike-regime-shift")
    df,fcols = build()
    df["slayer"]=df.s_pre.apply(s_layer)
    print(f"events={len(df)} factors={len(fcols)}")
    rows=[]
    for sl in ["high_s","mid_s","low_s"]:
        sub=df[df.slayer==sl]
        sp=sub[sub.grp=="spike"]; bs=sub[sub.grp=="base"]
        if len(sp)<30 or len(bs)<50: continue
        print(f"\n=== {sl}: n_spike={len(sp)} n_base={len(bs)} ===")
        print(f"{'factor':<12} {'ICsp':>7} {'ICbs':>7} {'ΔIC':>7} {'CI':>20}")
        for fc in fcols:
            if sp[fc].nunique()<10: continue
            ics=sp_ic(sp[fc].to_numpy(),sp.r100.to_numpy())
            icb=sp_ic(bs[fc].to_numpy(),bs.r100.to_numpy())
            if math.isnan(ics) or math.isnan(icb): continue
            d,lo,hi=boot(sp,bs,fc,"r100",hash((sl,fc))%2**30)
            sig="*" if not math.isnan(lo) and lo*hi>0 else " "
            rows.append(dict(slayer=sl,factor=fc,ic_sp=ics,ic_bs=icb,d_ic=d,lo=lo,hi=hi,sig=sig))
            print(f"{fc:<12} {ics:>+7.3f} {icb:>+7.3f} {d:>+7.3f} [{lo:+.3f},{hi:+.3f}]{sig}")
    pd.DataFrame(rows).to_csv(out/"vol_liq_factor_interaction.csv", index=False)
    print(f"\n[OK] {out}/vol_liq_factor_interaction.csv")


if __name__=="__main__":
    main()
