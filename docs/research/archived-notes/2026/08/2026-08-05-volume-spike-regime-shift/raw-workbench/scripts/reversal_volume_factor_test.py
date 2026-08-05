"""
反转类 + 成交量类因子 × volume spike 交互检验。
复用 momentum_factor_test 的框架。
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

N = 20
H_GRID = [20, 60, 100]
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


def factors(d):
    c, hh, ll, r, v = d.close, d.high, d.low, d.lr, d.volume
    f = pd.DataFrame(index=d.index)
    # === 反转类 ===
    # RSI 14, 30
    for L in [14, 30]:
        delta = c.diff()
        gain = delta.clip(lower=0).rolling(L).mean()
        loss = (-delta.clip(upper=0)).rolling(L).mean()
        rs = gain / loss.replace(0, np.nan)
        f[f"RSI{L}"] = 100 - 100/(1+rs)
    # 布林带位置
    for L in [20, 60]:
        ma = c.rolling(L).mean(); sd = c.rolling(L).std(ddof=1)
        f[f"BB{L}"] = (c - ma) / (2*sd)
    # 短期反转（负的过去收益）
    for L in [5, 20]:
        f[f"REV{L}"] = -c.pct_change(L)
    # K线形态：上影线/实体，下影线/实体
    body = (c - d.open).abs()
    rng = (hh - ll).replace(0, np.nan)
    f["UPPER_WICK"] = (hh - c.combine(d.open, max)) / rng
    f["LOWER_WICK"] = (c.combine(d.open, min) - ll) / rng
    f["BODY_RATIO"] = body / rng
    # 长上影看跌
    f["BEAR_WICK"] = f["UPPER_WICK"] * (c < d.open).astype(float)

    # === 成交量类 ===
    # volume ratio vs median
    for L in [20, 60]:
        med = v.rolling(L).median()
        f[f"VRATIO{L}"] = v / med
    # volume percentile (non-param)
    for L in [20, 60]:
        f[f"VPCT{L}"] = v.rolling(L).rank(pct=True)
    # 量价相关（过去20根 corr(r, v)）
    f["VP_CORR20"] = r.rolling(20).corr(v.pct_change())
    # OBV slope
    obv = (np.sign(r) * v).fillna(0).cumsum()
    f["OBV_SLOPE20"] = obv.diff(20)
    # ADL accumulation/distribution
    clv = ((c - ll) - (hh - c)) / rng
    f["ADL_SLOPE20"] = (clv * v).fillna(0).rolling(20).sum()
    # VWAP deviation
    vwap = (c*v).rolling(20).sum() / v.rolling(20).sum()
    f["VWAP_DEV20"] = (c - vwap) / vwap
    # volume autocorrelation
    f["VOL_AR1"] = v.rolling(20).apply(lambda x: pd.Series(x).autocorr(1), raw=False)
    # volume concentration: max/sum
    f["VOL_CONC20"] = v.rolling(20).max() / v.rolling(20).sum()
    return f


def build():
    recs = []
    for p in sorted(market_csv_dir().glob("*.1h.csv")):
        try: head = pd.read_csv(p, usecols=["datetime"])
        except: continue
        if len(head) < 420: continue
        sym = p.name.split(".tqsdk.1h.csv")[0]
        pfx = extract_contract_prefix(sym) or ""
        d = load(p)
        fac = factors(d)
        r = d.lr.to_numpy(); z = d.z.to_numpy()
        cols = list(fac.columns)
        fac_arr = fac.to_numpy()
        n = len(d); maxH = max(H_GRID)
        for t in range(N+maxH+1, n-maxH):
            zv = z[t]
            if not math.isfinite(zv): continue
            if zv >= 1.5: grp = "spike"
            elif abs(zv) < 0.5: grp = "base"
            else: continue
            pre = r[t-100:t]
            if not np.all(np.isfinite(pre)): continue
            s_mu, s_sd = pre.mean(), pre.std(ddof=1)
            s_pre = s_mu/s_sd if s_sd > 0 else np.nan
            if not math.isfinite(s_pre): continue
            fv = fac_arr[t]
            if not np.all(np.isfinite(fv)): continue
            rec = {"sym":sym,"pfx":pfx,"t":t,"grp":grp,"z":float(zv),"s_pre":float(s_pre)}
            for ci, cn in enumerate(cols): rec[cn] = float(fv[ci])
            for H in H_GRID: rec[f"r{H}"] = float(r[t+1:t+1+H].sum())
            recs.append(rec)
    df = pd.DataFrame(recs)
    print(f"events: {len(df)} spike={(df.grp=='spike').sum()} base={(df.grp=='base').sum()}")
    print(f"factors: {list(df.columns)}")
    return df, cols


def s_layer(s):
    if s >= 0.10: return "high_s"
    if s <= -0.10: return "low_s"
    return "mid_s"


def sp_ic(x, y):
    if len(x)<10 or np.std(x)<1e-10 or np.std(y)<1e-10: return np.nan
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return spearmanr(x, y).correlation


def boot_ic(sp, bs, fcol, rcol, seed):
    rng = np.random.default_rng(seed)
    fs, rs = sp[fcol].to_numpy(), sp[rcol].to_numpy()
    fb, rb = bs[fcol].to_numpy(), bs[rcol].to_numpy()
    ns, nb = len(fs), len(fb)
    diffs = []
    for _ in range(N_BOOT):
        i = rng.integers(0,ns,ns); j = rng.integers(0,nb,nb)
        a = sp_ic(fs[i],rs[i]); b = sp_ic(fb[j],rb[j])
        if not (math.isnan(a) or math.isnan(b)): diffs.append(a-b)
    if not diffs: return np.nan,np.nan,np.nan
    return float(np.mean(diffs)), float(np.quantile(diffs,.025)), float(np.quantile(diffs,.975))


def boot_ls(sp, bs, fcol, rcol, seed):
    rng = np.random.default_rng(seed)
    fs, rs = sp[fcol].to_numpy(), sp[rcol].to_numpy()
    fb, rb = bs[fcol].to_numpy(), bs[rcol].to_numpy()
    ns, nb = len(fs), len(fb)
    def ls(fv, rv):
        o = np.argsort(fv); k = len(fv)//5
        if k<5: return np.nan
        return rv[o[-k:]].mean()-rv[o[:k]].mean()
    diffs=[]
    for _ in range(N_BOOT):
        i=rng.integers(0,ns,ns); j=rng.integers(0,nb,nb)
        a=ls(fs[i],rs[i]); b=ls(fb[j],rb[j])
        if not(math.isnan(a) or math.isnan(b)): diffs.append(a-b)
    if not diffs: return np.nan,np.nan,np.nan
    return float(np.mean(diffs)),float(np.quantile(diffs,.025)),float(np.quantile(diffs,.975))


def main():
    out = Path("/Users/gaolei/Documents/src/quant/project_data/research/volume-spike-regime-shift")
    df, fcols = build()
    df["slayer"] = df.s_pre.apply(s_layer)
    rows = []
    for sl in ["high_s","mid_s","low_s"]:
        sub = df[df.slayer==sl]
        sp = sub[sub.grp=="spike"]; bs = sub[sub.grp=="base"]
        if len(sp)<30 or len(bs)<50:
            print(f"skip {sl}: n_s={len(sp)} n_b={len(bs)}"); continue
        print(f"\n=== {sl}: n_spike={len(sp)} n_base={len(bs)} ===")
        print(f"{'factor':<14} {'ICsp':>7} {'ICbs':>7} {'ΔIC':>7} {'CI':>18} {'LSsp':>8} {'LSbs':>8}")
        for fcol in fcols:
            if sp[fcol].nunique()<10: continue
            for H in [100]:
                rc=f"r{H}"
                ics=sp_ic(sp[fcol].to_numpy(),sp[rc].to_numpy())
                icb=sp_ic(bs[fcol].to_numpy(),bs[rc].to_numpy())
                if math.isnan(ics) or math.isnan(icb): continue
                d,lo,hi=boot_ic(sp,bs,fcol,rc,hash((sl,fcol,H))%2**30)
                # LS
                os_=np.argsort(sp[fcol].to_numpy()); ob=np.argsort(bs[fcol].to_numpy())
                ks=len(sp)//5; kb=len(bs)//5
                ls_s=sp[rc].to_numpy()[os_[-ks:]].mean()-sp[rc].to_numpy()[os_[:ks]].mean()
                ls_b=bs[rc].to_numpy()[ob[-kb:]].mean()-bs[rc].to_numpy()[ob[:kb]].mean()
                dls,_,_=boot_ls(sp,bs,fcol,rc,hash(('l',sl,fcol))%2**30)
                sig="*" if not math.isnan(lo) and lo*hi>0 else " "
                rows.append(dict(slayer=sl,factor=fcol,H=H,ic_sp=ics,ic_bs=icb,d_ic=d,lo=lo,hi=hi,sig=sig,
                                 ls_sp=ls_s,ls_bs=ls_b,d_ls=dls,n_sp=len(sp)))
                print(f"{fcol:<14} {ics:>+7.3f} {icb:>+7.3f} {d:>+7.3f} [{lo:+.3f},{hi:+.3f}]{sig} {ls_s:>+8.4f} {ls_b:>+8.4f}")
    res=pd.DataFrame(rows)
    res.to_csv(out/"reversal_volume_factor_interaction.csv", index=False)
    print(f"\n[OK] {out}/reversal_volume_factor_interaction.csv")


if __name__=="__main__":
    main()
