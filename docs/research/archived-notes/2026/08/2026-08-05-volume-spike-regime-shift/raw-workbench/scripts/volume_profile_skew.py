"""
Volume Profile Skew 指标：
对每个 1h 放量/缩量事件：
1. 取该 1h bar + 之前 14h（共 15h）的 1m 数据
2. 对每个 1m bar，把成交量均匀分配到 low-high 价格区间（按 tick 分桶）
3. 构建 volume-at-price 直方图
4. 计算 VWAP 和成交量加权偏度：
   skew = sum(vol_i * ((p_i - vwap)/std)^3) / sum(vol_i)
5. 与 MADEV、z、未来 r100 联合分析

业界标准：Volume Profile Skew / VWAP Skew
正偏 = 成交量集中在低位、高位长尾（上方阻力重，看跌）
负偏 = 成交量集中在高位、低位长尾（下方支撑重，看涨）
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
WINDOW_HOURS = 15  # 1h spike bar + 14 previous hours
# 1m bar count per window (approximately, depends on session but ~55-60 per hour)
# We'll use time-based alignment rather than bar count


def load_1h(p):
    d = pd.read_csv(p)
    d["datetime"] = pd.to_datetime(d["datetime"])
    d = d.sort_values("datetime").reset_index(drop=True)
    d["lr"] = np.log(d.close).diff()
    v, h = d.volume, d.datetime.dt.hour
    mu = v.groupby(h).shift(1).groupby(h).transform(lambda s: s.rolling(N,min_periods=N).mean())
    sd = v.groupby(h).shift(1).groupby(h).transform(lambda s: s.rolling(N,min_periods=N).std(ddof=1))
    d["z"] = (v-mu)/sd
    return d


def load_1m(p):
    d = pd.read_csv(p)
    d["datetime"] = pd.to_datetime(d["datetime"])
    return d.sort_values("datetime").reset_index(drop=True)


def compute_volume_profile_skew(m1_window, n_bins=50):
    """
    Given a DataFrame of 1m bars with open/high/low/close/volume,
    build volume-at-price distribution and return skew metrics.

    For each 1m bar: distribute its volume uniformly across n_price_bins
    price levels between low and high.
    """
    if len(m1_window) < 100:
        return None
    # Overall price range
    pmin = m1_window.low.min()
    pmax = m1_window.high.max()
    if pmax <= pmin or not math.isfinite(pmin) or not math.isfinite(pmax):
        return None
    # Price bins
    bin_edges = np.linspace(pmin, pmax, n_bins+1)
    bin_centers = (bin_edges[:-1] + bin_edges[1:])/2
    vol_profile = np.zeros(n_bins)
    for _, row in m1_window.iterrows():
        lo, hi, vol = row.low, row.high, row.volume
        if not (math.isfinite(lo) and math.isfinite(hi) and math.isfinite(vol) and vol>0):
            continue
        if hi <= lo:
            # single price
            idx = min(n_bins-1, max(0, int((lo-pmin)/(pmax-pmin)*n_bins)))
            vol_profile[idx] += vol
        else:
            # uniform distribute across bins in [lo,hi]
            lo_idx = max(0, int((lo-pmin)/(pmax-pmin)*n_bins))
            hi_idx = min(n_bins-1, int((hi-pmin)/(pmax-pmin)*n_bins))
            n_levels = hi_idx - lo_idx + 1
            if n_levels > 0:
                vol_profile[lo_idx:hi_idx+1] += vol / n_levels
    total_vol = vol_profile.sum()
    if total_vol <= 0:
        return None
    # VWAP (volume weighted average price)
    vwap = np.sum(bin_centers * vol_profile) / total_vol
    # Volume-weighted variance and skewness
    dev = bin_centers - vwap
    var = np.sum(vol_profile * dev**2) / total_vol
    std = math.sqrt(var) if var > 0 else 0
    if std <= 0:
        return None
    vp_skew = np.sum(vol_profile * (dev/std)**3) / total_vol
    # Also compute POC (point of control = price with max volume)
    poc = bin_centers[np.argmax(vol_profile)]
    # Value area: 70% volume around POC
    sorted_idx = np.argsort(-vol_profile)
    cum_vol = 0; va_mask = np.zeros(n_bins, dtype=bool)
    for idx in sorted_idx:
        va_mask[idx] = True
        cum_vol += vol_profile[idx]
        if cum_vol >= 0.7*total_vol: break
    va_high = bin_centers[va_mask].max()
    va_low = bin_centers[va_mask].min()
    # Balance: (volume above vwap - volume below vwap) / total
    above = vol_profile[bin_centers > vwap].sum()
    below = vol_profile[bin_centers < vwap].sum()
    balance = (above - below) / total_vol  # positive = more volume above (bearish)
    return dict(vwap=vwap, vp_skew=vp_skew, poc=poc, std=std,
                va_high=va_high, va_low=va_low, balance=balance,
                dev_close=(m1_window.iloc[-1].close - vwap)/vwap if vwap>0 else np.nan)


def main():
    out = Path("/Users/gaolei/Documents/src/quant/project_data/research/volume-spike-regime-shift")
    out.mkdir(parents=True, exist_ok=True)

    # Build mapping: 1h symbol -> 1m symbol (same contract month if possible)
    files_1h = {p.name.split(".tqsdk.1h.csv")[0]: p
                for p in sorted(market_csv_dir().glob("*.1h.csv"))}
    files_1m = {p.name.split(".tqsdk.1m.csv")[0]: p
                for p in sorted(market_csv_dir().glob("*.1m.csv"))}

    # Find matching pairs (same exact contract)
    matched = []
    for sym_1h, p1h in files_1h.items():
        if sym_1h in files_1m:
            matched.append((sym_1h, p1h, files_1m[sym_1h]))
    print(f"Matched 1h<->1m contracts: {len(matched)}")
    for s,_,_ in matched[:10]:
        print(f"  {s}")

    results = []
    for sym, p1h, p1m in matched:
        pfx = extract_contract_prefix(sym) or sym
        print(f"\nProcessing {sym} ({pfx})...")
        dh = load_1h(p1h)
        dm = load_1m(p1m)
        dm_idx = dm.set_index("datetime")
        # For each 1h bar that has z computed and enough history
        c_arr = dh.close.to_numpy()
        ma120 = dh.close.rolling(120).mean().to_numpy()
        r = dh.lr.to_numpy(); z_arr = dh.z.to_numpy(); ts = dh.datetime
        n = len(dh)
        for t in range(max(N+H+1, 120), n-H):
            zv = z_arr[t]
            if not math.isfinite(zv): continue
            pre = r[t-100:t]
            if not np.all(np.isfinite(pre)): continue
            ssd = pre.std(ddof=1)
            if ssd<=0: continue
            s_pre = pre.mean()/ssd
            if not math.isfinite(ma120[t]) or ma120[t]<=0: continue
            madev = (c_arr[t]-ma120[t])/ma120[t]
            # 1m window: from (t-14)h start to t end
            t_end = ts.iloc[t]
            t_start = t_end - pd.Timedelta(hours=WINDOW_HOURS-1)
            t_start = t_start.replace(minute=0, second=0)
            # Get 1m bars
            mask = (dm.datetime >= t_start) & (dm.datetime <= t_end + pd.Timedelta(hours=1))
            m1_win = dm[mask]
            if len(m1_win) < 200:  # need enough 1m bars (~15h * 55 = 825)
                continue
            vp = compute_volume_profile_skew(m1_win)
            if vp is None: continue
            results.append(dict(
                sym=sym, pfx=pfx, t=t, ts=ts.iloc[t],
                z=float(zv), s_pre=float(s_pre), madev=float(madev),
                r100=float(r[t+1:t+1+H].sum()),
                close=float(c_arr[t]),
                **vp
            ))
    df = pd.DataFrame(results)
    print(f"\nTotal events with skew: {len(df)}")
    if len(df)==0:
        print("No events!"); return

    df.to_csv(out/"volume_skew_events.csv", index=False)
    print(f"Saved to {out}/volume_skew_events.csv")

    # ========== Analysis ==========
    print("\n" + "="*80)
    print("Volume Profile Skew 分析")
    print("="*80)

    # High s events
    hi = df[df.s_pre>=0.10].copy()
    print(f"\n高 s 事件: {len(hi)}")
    if len(hi) < 30:
        print("样本不足，使用全样本")
        hi = df.copy()

    # Skew distribution by volume group
    hi["vg"] = pd.cut(hi.z, bins=[-np.inf,-0.5,0.5,1.5,np.inf],
                      labels=["缩量","正常","放量","极端"])
    print(f"\n--- skew 描述统计（按成交量组）---")
    print(f"{'组':<8} {'n':>5} {'skew_mean':>10} {'skew_std':>9} {'balance':>9} {'dev_close':>10}")
    for g in ["缩量","正常","放量","极端"]:
        s = hi[hi.vg==g]
        if len(s)<5: continue
        print(f"{g:<8} {len(s):>5} {s.vp_skew.mean():>+10.3f} {s.vp_skew.std():>9.3f} "
              f"{s.balance.mean():>+9.3f} {s.dev_close.mean():>+10.4f}")

    # Does skew predict r100?
    print(f"\n--- skew 对未来 r100 的预测力 ---")
    for g in ["缩量","正常","放量","极端"]:
        s = hi[hi.vg==g]
        if len(s)<20: continue
        ic, p = spearmanr(s.vp_skew, s.r100)
        ic_b, _ = spearmanr(s.balance, s.r100)
        ic_d, _ = spearmanr(s.dev_close, s.r100)
        print(f"  {g:<6} n={len(s):<4} IC(skew)={ic:+.3f}  IC(balance)={ic_b:+.3f}  IC(dev_close)={ic_d:+.3f}")

    # MADEV × Skew double sort (within high volume)
    print(f"\n--- 放量/极端组内：MADEV × skew 双排序 ---")
    spike = hi[hi.z>=1.5].copy()
    if len(spike) >= 40:
        spike["mq"] = pd.qcut(spike.madev, 2, labels=["MADEV低","MADEV高"])
        spike["sq"] = pd.qcut(spike.vp_skew, 2, labels=["skew低(负偏)","skew高(正偏)"])
        print(spike.groupby(["mq","sq"], observed=True).r100.agg(["mean","count"]).round(4))

        # Also for vlow
        vlow = hi[hi.z<-0.5].copy()
        if len(vlow)>=20:
            vlow["mq"] = pd.qcut(vlow.madev, 2, labels=["MADEV低","MADEV高"])
            vlow["sq"] = pd.qcut(vlow.vp_skew, 2, labels=["skew低","skew高"])
            print(f"\n缩量组内：MADEV × skew 双排序")
            print(vlow.groupby(["mq","sq"], observed=True).r100.agg(["mean","count"]).round(4))
    else:
        print(f"  放量样本仅 {len(spike)}，不足双排序")

    # Incremental value: does skew add info beyond MADEV and z?
    print(f"\n--- skew 增量信息（控制 madev 后）---")
    from numpy.linalg import lstsq
    valid = hi.dropna(subset=["madev","vp_skew","r100","z"]).copy()
    if len(valid)>=50:
        for col in ["madev","vp_skew","z","balance","dev_close"]:
            valid[col+"_s"] = (valid[col]-valid[col].mean())/valid[col].std()
        # Model 1: madev + z
        X1 = np.column_stack([np.ones(len(valid)), valid.madev_s, valid.z_s, valid.madev_s*valid.z_s])
        y = valid.r100.to_numpy()
        b1 = lstsq(X1, y, rcond=None)[0]
        pred1 = X1@b1; r2_1 = 1-((y-pred1)**2).sum()/((y-y.mean())**2).sum()
        # Model 2: + skew + interactions
        X2 = np.column_stack([X1, valid.vp_skew_s, valid.vp_skew_s*valid.z_s, valid.vp_skew_s*valid.madev_s])
        b2 = lstsq(X2, y, rcond=None)[0]
        pred2 = X2@b2; r2_2 = 1-((y-pred2)**2).sum()/((y-y.mean())**2).sum()
        print(f"  madev+z model:          R²={r2_1:.4f}")
        print(f"  madev+z+skew model:     R²={r2_2:.4f}  (ΔR²={r2_2-r2_1:+.4f})")
        print(f"  skew 主效应 β={b2[4]:+.5f}, skew×z β={b2[5]:+.5f}, skew×madev β={b2[6]:+.5f}")

    print(f"\n[OK] Analysis complete.")


if __name__ == "__main__":
    main()
