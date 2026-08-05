"""
动量类因子 × volume spike 交互检验。
因子：
  MRET_L: 过去 L 根 bar 累计收益，L∈{20,50,100,200}
  S_PRE: 市场强度 mean/std over 100
  MADEV_L: (close - MA_L)/MA_L
  HH_L: (close - min_L)/(max_L - min_L) 区间位置
  STREWN: 连续阳线比例（过去 20 根中阳线占比）
  PATHEFF_L: |P_t-P_{t-L}| / sum|r_i| 路径效率
检验：
  - 在高 s / 中 s / 低 s 三层内，spike vs baseline 的因子 IC (Spearman)
  - 多空 Q5-Q1 收益
  - 交互回归 β3
  - H∈{20,60,100}
N=20 z≥1.5 spike; |z|<0.5 baseline; 全品种
"""
from __future__ import annotations
import sys, math, json, warnings
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
    """预计算所有因子列。"""
    c = d.close
    r = d.lr
    f = pd.DataFrame(index=d.index)
    # MRET
    for L in [20, 50, 100, 200]:
        f[f"MRET{L}"] = c.pct_change(L)  # 简单收益（对数也可）
    # S_PRE over 100
    mu = r.rolling(100).mean()
    sd = r.rolling(100).std(ddof=1)
    f["S_PRE"] = mu / sd
    # MADEV
    for L in [20, 60, 120]:
        ma = c.rolling(L).mean()
        f[f"MADEV{L}"] = (c - ma) / ma
    # HH range position over L=100,200
    for L in [100, 200]:
        mn = c.rolling(L).min(); mx = c.rolling(L).max()
        f[f"HH{L}"] = (c - mn) / (mx - mn)
    # 连续阳线比例
    up = (r > 0).astype(float)
    f["STREAK20"] = up.rolling(20).mean()
    # 路径效率
    for L in [50, 100]:
        cum_abs = r.abs().rolling(L).sum()
        net = (c / c.shift(L) - 1).abs()
        f[f"PATEFF{L}"] = net / cum_abs.replace(0, np.nan)
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
        sess = d.datetime.dt.date.to_numpy()
        cols = list(fac.columns)
        fac_arr = fac.to_numpy()
        n = len(d)
        maxH = max(H_GRID)
        for t in range(N+maxH+1, n-maxH):
            zv = z[t]
            if not math.isfinite(zv): continue
            if zv >= 1.5: grp = "spike"
            elif abs(zv) < 0.5: grp = "base"
            else: continue
            # s_pre over 100
            pre = r[t-100:t]
            if not np.all(np.isfinite(pre)): continue
            s_mu, s_sd = pre.mean(), pre.std(ddof=1)
            s_pre = s_mu/s_sd if s_sd > 0 else np.nan
            if not math.isfinite(s_pre): continue
            # factor values at t
            fv = fac_arr[t]
            if not np.all(np.isfinite(fv)): continue
            rec = {
                "sym": sym, "pfx": pfx, "t": t,
                "sess": str(sess[t]), "grp": grp, "z": float(zv),
                "s_pre": float(s_pre),
            }
            for ci, cn in enumerate(cols):
                rec[cn] = float(fv[ci])
            for H in H_GRID:
                rec[f"r{H}"] = float(r[t+1:t+1+H].sum())
            recs.append(rec)
    df = pd.DataFrame(recs)
    print(f"events: {len(df)}  spike={(df.grp=='spike').sum()}  base={(df.grp=='base').sum()}")
    return df, cols


def s_layer(s):
    if s >= 0.10: return "high_s"
    if s <= -0.10: return "low_s"
    return "mid_s"


def spearman_ic(x, y):
    if len(x) < 10 or np.std(x) < 1e-10 or np.std(y) < 1e-10:
        return np.nan
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return spearmanr(x, y).correlation


def boot_ic_diff(sp, bs, fcol, rcol, seed=42):
    """IC 差异 bootstrap：按事件行重采样（快速近似）。"""
    rng = np.random.default_rng(seed)
    n_s, n_b = len(sp), len(bs)
    fv_s, rv_s = sp[fcol].to_numpy(), sp[rcol].to_numpy()
    fv_b, rv_b = bs[fcol].to_numpy(), bs[rcol].to_numpy()
    diffs = []
    for _ in range(N_BOOT):
        is_ = rng.integers(0, n_s, n_s)
        ib_ = rng.integers(0, n_b, n_b)
        ic_s = spearman_ic(fv_s[is_], rv_s[is_])
        ic_b = spearman_ic(fv_b[ib_], rv_b[ib_])
        if not (math.isnan(ic_s) or math.isnan(ic_b)):
            diffs.append(ic_s - ic_b)
    if not diffs: return np.nan, np.nan, np.nan
    return float(np.mean(diffs)), float(np.quantile(diffs,.025)), float(np.quantile(diffs,.975))


def boot_ls_diff(sp, bs, fcol, rcol, seed=42):
    rng = np.random.default_rng(seed)
    n_s, n_b = len(sp), len(bs)
    fv_s, rv_s = sp[fcol].to_numpy(), sp[rcol].to_numpy()
    fv_b, rv_b = bs[fcol].to_numpy(), bs[rcol].to_numpy()
    def ls(fv, rv):
        # rank based quintile
        order = np.argsort(fv)
        k = len(fv)//5
        if k < 5: return np.nan
        q1 = rv[order[:k]].mean()
        q5 = rv[order[-k:]].mean()
        return q5 - q1
    diffs = []
    for _ in range(N_BOOT):
        is_ = rng.integers(0, n_s, n_s)
        ib_ = rng.integers(0, n_b, n_b)
        a = ls(fv_s[is_], rv_s[is_]); b = ls(fv_b[ib_], rv_b[ib_])
        if not (math.isnan(a) or math.isnan(b)):
            diffs.append(a-b)
    if not diffs: return np.nan, np.nan, np.nan
    return float(np.mean(diffs)), float(np.quantile(diffs,.025)), float(np.quantile(diffs,.975))


def main():
    out = Path("/Users/gaolei/Documents/src/quant/project_data/research/volume-spike-regime-shift")
    df, fcols = build()
    df["slayer"] = df.s_pre.apply(s_layer)
    print(f"s_pre layers: {df.slayer.value_counts().to_dict()}")

    rows = []
    for sl in ["high_s", "mid_s", "low_s"]:
        sub = df[df.slayer==sl]
        sp = sub[sub.grp=="spike"]; bs = sub[sub.grp=="base"]
        if len(sp)<30 or len(bs)<50:
            print(f"  skip {sl}: n_spike={len(sp)} n_base={len(bs)}")
            continue
        print(f"\n=== {sl}: n_spike={len(sp)} n_base={len(bs)} ===")
        print(f"{'factor':<12} {'H':>4} {'IC_sp':>8} {'IC_bs':>8} {'ΔIC':>8} {'ΔCI':>16} {'LS_sp':>8} {'LS_bs':>8} {'ΔLS':>8}")
        for fcol in fcols:
            for H in H_GRID:
                rcol = f"r{H}"
                # skip if factor too constant
                if sp[fcol].nunique() < 10: continue
                ic_s = spearman_ic(sp[fcol].to_numpy(), sp[rcol].to_numpy())
                ic_b = spearman_ic(bs[fcol].to_numpy(), bs[rcol].to_numpy())
                if math.isnan(ic_s) or math.isnan(ic_b): continue
                d_ic, lo, hi = boot_ic_diff(sp, bs, fcol, rcol, seed=hash((sl,fcol,H))%2**30)
                # LS
                qs_s = pd.qcut(sp[fcol], 5, labels=False, duplicates="drop")
                qs_b = pd.qcut(bs[fcol], 5, labels=False, duplicates="drop")
                if qs_s.nunique()>=5 and qs_b.nunique()>=5:
                    ls_s = sp.groupby(qs_s)[rcol].mean().iloc[-1] - sp.groupby(qs_s)[rcol].mean().iloc[0]
                    ls_b = bs.groupby(qs_b)[rcol].mean().iloc[-1] - bs.groupby(qs_b)[rcol].mean().iloc[0]
                    d_ls, _, _ = boot_ls_diff(sp, bs, fcol, rcol, seed=hash(('ls',sl,fcol,H))%2**30)
                else:
                    ls_s = ls_b = d_ls = np.nan
                sig = "*" if (not math.isnan(lo)) and lo*hi>0 else " "
                rows.append({
                    "slayer": sl, "factor": fcol, "H": H,
                    "ic_spike": ic_s, "ic_base": ic_b, "delta_ic": d_ic,
                    "ic_lo": lo, "ic_hi": hi, "sig": sig,
                    "ls_spike": ls_s, "ls_base": ls_b, "delta_ls": d_ls,
                    "n_spike": len(sp),
                })
                if H == 100:  # only print H=100 for brevity
                    print(f"{fcol:<12} {H:>4} {ic_s:>+8.3f} {ic_b:>+8.3f} {d_ic:>+8.3f} "
                          f"[{lo:+.3f},{hi:+.3f}]{sig} {ls_s:>+8.4f} {ls_b:>+8.4f} {d_ls:>+8.4f}")

    res = pd.DataFrame(rows)
    res.to_csv(out / "momentum_factor_interaction.csv", index=False)

    # 交互回归（pooled, high_s only, H=100）
    print("\n=== 交互回归（pooled, H=100）===")
    print(f"{'factor':<12} {'β1(f)':>10} {'β2(spk)':>10} {'β3(f×spk)':>12} {'β3_CI':>22} {'flip?':>6}")
    reg_rows = []
    for sl in ["high_s","mid_s","low_s"]:
        sub = df[(df.slayer==sl)].copy()
        sub["spike"] = (sub.grp=="spike").astype(float)
        for fcol in fcols:
            if sub[fcol].nunique()<10: continue
            for H in [100]:
                rcol = f"r{H}"
                X = np.column_stack([
                    np.ones(len(sub)),
                    sub[fcol].to_numpy(),
                    sub.spike.to_numpy(),
                    sub[fcol].to_numpy()*sub.spike.to_numpy(),
                    sub.s_pre.to_numpy(),
                ])
                y = sub[rcol].to_numpy()
                # drop nan
                m = np.all(np.isfinite(X), axis=1) & np.isfinite(y)
                X, y = X[m], y[m]
                # standardize factor for comparable β
                X[:,1] = (X[:,1]-X[:,1].mean())/(X[:,1].std()+1e-12)
                try:
                    beta = np.linalg.lstsq(X, y, rcond=None)[0]
                except: continue
                # bootstrap β3
                rng = np.random.default_rng(hash((sl,fcol))%2**30)
                b3 = []
                for _ in range(200):
                    idx = rng.choice(len(y), len(y), replace=True)
                    try:
                        b = np.linalg.lstsq(X[idx], y[idx], rcond=None)[0]
                        b3.append(b[3])
                    except: pass
                lo, hi = np.quantile(b3,[.025,.975]) if b3 else (np.nan,np.nan)
                flip = "FLIP" if (lo*hi>0 and beta[1]*beta[3]<0) else ("enha" if lo*hi>0 else "")
                if sl=="high_s":
                    print(f"{fcol:<12} {beta[1]:>+10.5f} {beta[2]:>+10.5f} {beta[3]:>+12.5f} "
                          f"[{lo:+.5f},{hi:+.5f}] {flip:>6}")
                reg_rows.append({"slayer":sl,"factor":fcol,"H":H,
                                 "b1":beta[1],"b2":beta[2],"b3":beta[3],
                                 "b3_lo":lo,"b3_hi":hi,"flip":flip})
    pd.DataFrame(reg_rows).to_csv(out / "momentum_factor_regression.csv", index=False)
    print(f"\n[OK] {out}/momentum_factor_interaction.csv, momentum_factor_regression.csv")


if __name__ == "__main__":
    main()
