"""
OI × 成交量放量：稳健性深入分析（修正版）

稳健性口径：
- cluster bootstrap：按 symbol × year-month 聚类，解决事件重叠
- weekly sample：每周每品种最多 1 个同方向信号，模拟低频执行
- 所有阈值在分析子集内重新计算，避免 z≥1.5 与 z≥2.5 混用

分析：
1. cluster bootstrap + weekly 下，OI 减仓/增仓差异是否仍存在
2. 阈值矩阵：z ∈ {1.5,2.0,2.5} × MADEV top {1/3,20%} × OI {±0.5,±1.0}
3. 年度稳定性
4. 板块稳定性
5. OI 窗口敏感性 5/20/60
6. 低 s_pre 镜像
7. OOS 时间切分
"""
from __future__ import annotations

import json
import math
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT))

from oi_volume_study import build_events  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent.parent / "outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SECTOR = {
    "i": "black", "j": "black", "jm": "black", "rb": "black", "hc": "black", "ss": "black",
    "sc": "energy", "fu": "energy", "lu": "energy", "pg": "energy", "eg": "energy",
    "eb": "energy", "pp": "energy", "v": "energy", "l": "energy", "ma": "energy", "ta": "energy",
    "nr": "energy", "oi": "energy",
    "m": "agri", "c": "agri", "cs": "agri", "p": "agri", "y": "agri",
    "sr": "agri", "cf": "agri", "rm": "agri", "fg": "agri", "sa": "agri",
    "cu": "metals", "al": "metals", "zn": "metals", "ni": "metals", "au": "metals", "ag": "metals",
}


def cboot(values: np.ndarray, clusters: np.ndarray, n_boot: int = 1000, seed: int = 42) -> tuple[float, float, float]:
    """聚类 bootstrap：按 cluster id 整簇重采样。"""
    a = np.asarray(values, float)
    c = np.asarray(clusters)
    mask = np.isfinite(a)
    a, c = a[mask], c[mask]
    if len(a) < 10:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    uc = np.unique(c)
    by = {k: a[c == k] for k in uc}
    means = np.empty(n_boot)
    for b in range(n_boot):
        pick = rng.choice(uc, size=len(uc), replace=True)
        sample = np.concatenate([by[k] for k in pick])
        means[b] = sample.mean()
    return float(a.mean()), float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def stat(sub: pd.DataFrame) -> dict:
    if len(sub) == 0:
        return {"n": 0}
    clusters = (sub.sym.astype(str) + "_" + pd.to_datetime(sub.ts).dt.strftime("%Y%m")).to_numpy()
    m, lo, hi = cboot(sub.r100.to_numpy(), clusters)
    return {
        "n": int(len(sub)),
        "mean": m,
        "ci_lo": lo,
        "ci_hi": hi,
        "pct_pos": float((sub.r100 > 0).mean()),
        "median": float(sub.r100.median()),
    }


def ps(title: str, sub: pd.DataFrame) -> dict:
    s = stat(sub)
    if s["n"] == 0:
        print(f"  {title:<34} n=0")
        return s
    print(
        f"  {title:<34} n={s['n']:>4} mean={s['mean']*100:+6.2f}% "
        f"CI=[{s['ci_lo']*100:+5.2f}%,{s['ci_hi']*100:+5.2f}%] "
        f"%pos={s['pct_pos']*100:5.1f}% med={s['median']*100:+6.2f}%"
    )
    return s


def weekly_sample(df: pd.DataFrame) -> pd.DataFrame:
    """每 sym × ISO week 只保留该周内最强信号（高 s 取 madev 最大；低 s 取 madev 最小）。"""
    d = df.copy()
    d["week"] = pd.to_datetime(d.ts).dt.isocalendar().year.astype(str) + "-" + pd.to_datetime(d.ts).dt.isocalendar().week.astype(str)
    if (d.s_pre >= 0).all():
        idx = d.groupby(["sym", "week"])["madev"].idxmax()
    elif (d.s_pre <= 0).all():
        idx = d.groupby(["sym", "week"])["madev"].idxmin()
    else:
        idx = d.groupby(["sym", "week"])["t"].idxmin()
    return d.loc[idx].sort_values(["sym", "t"]).reset_index(drop=True)


def oi_split3(sub: pd.DataFrame, col: str = "doi_z") -> pd.DataFrame:
    s = sub.dropna(subset=[col]).copy()
    if len(s) < 15:
        s["oi_g"] = pd.NA
        return s
    s["oi_g"] = pd.qcut(s[col], 3, labels=["OI减仓", "OI中性", "OI增仓"])
    return s


def add_oi_windows(df: pd.DataFrame) -> pd.DataFrame:
    from workspace.data.output_paths import market_csv_dir
    csv_dir = market_csv_dir()
    vals = {i: {} for i in df.index}
    for sym, g in df.groupby("sym"):
        p = csv_dir / f"{sym}.tqsdk.1h.csv"
        d = pd.read_csv(p)
        d = d.sort_values("datetime").reset_index(drop=True)
        oi = d.close_oi.astype(float)
        doi = d.close_oi.astype(float) - d.open_oi.astype(float)
        h = pd.to_datetime(d.datetime).dt.hour
        series = {}
        for w in (5, 20, 60):
            series[f"oi_cum_{w}"] = (oi - oi.shift(w)) / oi.shift(w)
            mu = doi.groupby(h).shift(1).groupby(h).transform(lambda s: s.rolling(w, min_periods=max(3, w//2)).mean())
            sd = doi.groupby(h).shift(1).groupby(h).transform(lambda s: s.rolling(w, min_periods=max(3, w//2)).std(ddof=1))
            series[f"doi_z_{w}"] = (doi - mu) / sd
        for ridx, row in g.iterrows():
            t = int(row.t)
            for k, s in series.items():
                vals[ridx][k] = float(s.iloc[t])
    for k in ["oi_cum_5", "oi_cum_20", "oi_cum_60", "doi_z_5", "doi_z_20", "doi_z_60"]:
        df[k] = [vals[i][k] for i in df.index]
    return df


def main() -> None:
    df = build_events()
    df["year"] = pd.to_datetime(df.ts).dt.year
    df["sector"] = df.pfx.map(SECTOR).fillna("other")
    print(f"events: {len(df)}, symbols: {df.sym.nunique()}, {df.ts.min()} ~ {df.ts.max()}")
    out: dict = {"n": len(df), "sections": {}}

    high = df[df.s_pre >= 0.10].copy()
    low = df[df.s_pre <= -0.10].copy()

    # ---------- 1. cluster bootstrap 主表 ----------
    print("\n" + "=" * 92)
    print("1. 高 s_pre + z>=1.5，cluster bootstrap by symbol-month")
    print("=" * 92)
    h15 = high[high.z >= 1.5].copy()
    h15["mq"] = pd.qcut(h15.madev, 3, labels=["低", "中", "高"])
    h15 = oi_split3(h15)
    sec1 = {}
    for mq in ["低", "中", "高"]:
        sec1[mq] = {}
        print(f"\n MADEV={mq}")
        for og in ["OI减仓", "OI中性", "OI增仓"]:
            sec1[mq][og] = ps(og, h15[(h15.mq == mq) & (h15.oi_g == og)])
    out["sections"]["1_cluster_main"] = sec1

    print("\n  weekly sample:")
    w15 = weekly_sample(h15)
    w15 = oi_split3(w15)
    sec1w = {}
    for og in ["OI减仓", "OI中性", "OI增仓"]:
        sec1w[og] = ps(og, w15[w15.oi_g == og])
    out["sections"]["1_weekly"] = sec1w

    # ---------- 2. 阈值矩阵 ----------
    print("\n" + "=" * 92)
    print("2. 阈值矩阵（高 s_pre，cluster bootstrap）")
    print("=" * 92)
    sec2 = {}
    for zth in [1.5, 2.0, 2.5]:
        for mq_p in [2/3, 0.8]:
            sub = high[high.z >= zth].copy()
            if len(sub) < 30:
                continue
            mq_cut = sub.madev.quantile(mq_p)
            sub = sub[sub.madev >= mq_cut]
            label = f"z>={zth}, MADEV top {int((1-mq_p)*100)}%"
            print(f"\n {label}, base n={len(sub)}")
            row = {"base": ps("全部", sub)}
            for oi_th in [-0.5, -1.0]:
                row[f"OI<{oi_th}"] = ps(f"OI减仓<{oi_th}", sub[sub.doi_z < oi_th])
            for oi_th in [0.5, 1.0]:
                row[f"OI>{oi_th}"] = ps(f"OI增仓>{oi_th}", sub[sub.doi_z > oi_th])
            # weekly
            wsub = weekly_sample(sub)
            row["weekly_base"] = ps("weekly全部", wsub)
            row["weekly_OI<-0.5"] = ps("weekly OI<-0.5", wsub[wsub.doi_z < -0.5])
            row["weekly_OI>+0.5"] = ps("weekly OI>+0.5", wsub[wsub.doi_z > 0.5])
            sec2[label] = row
    out["sections"]["2_threshold_matrix"] = sec2

    # ---------- 3. 年度 ----------
    print("\n" + "=" * 92)
    print("3. 年度稳定性（z>=1.5 + 高MADEV）")
    print("=" * 92)
    base = h15[h15.mq == "高"].copy()
    sec3 = {}
    for year in sorted(base.year.unique()):
        ys = base[base.year == year].copy()
        if len(ys) < 20:
            print(f"  {year}: n={len(ys)} 太少")
            continue
        print(f"\n {year}, n={len(ys)}")
        ys = oi_split3(ys)
        yres = {}
        for og in ["OI减仓", "OI中性", "OI增仓"]:
            yres[og] = ps(og, ys[ys.oi_g == og])
        sec3[str(int(year))] = yres
    out["sections"]["3_year"] = sec3

    # ---------- 4. 板块 ----------
    print("\n" + "=" * 92)
    print("4. 板块稳定性（z>=1.5 + 高MADEV）")
    print("=" * 92)
    sec4 = {}
    for sector, ss in base.groupby("sector"):
        if len(ss) < 20:
            print(f"  {sector}: n={len(ss)} 太少")
            continue
        print(f"\n {sector}, n={len(ss)}")
        ss = oi_split3(ss)
        sres = {}
        for og in ["OI减仓", "OI中性", "OI增仓"]:
            sres[og] = ps(og, ss[ss.oi_g == og])
        sec4[sector] = sres
    out["sections"]["4_sector"] = sec4

    # ---------- 5. OI 窗口 ----------
    print("\n" + "=" * 92)
    print("5. OI 窗口敏感性（z>=2.0 + MADEV top 1/3）")
    print("=" * 92)
    sub5 = high[high.z >= 2.0].copy()
    sub5 = sub5[sub5.madev >= sub5.madev.quantile(2/3)]
    sub5 = add_oi_windows(sub5)
    sec5 = {}
    for w in (5, 20, 60):
        col = f"doi_z_{w}"
        print(f"\n window={w}, n={len(sub5)}")
        ss = sub5.dropna(subset=[col]).copy()
        if len(ss) >= 20:
            ss["oi_g"] = pd.qcut(ss[col], 3, labels=["OI减仓", "OI中性", "OI增仓"])
            wres = {}
            for og in ["OI减仓", "OI中性", "OI增仓"]:
                wres[og] = ps(og, ss[ss.oi_g == og])
            sec5[str(w)] = wres
    out["sections"]["5_window"] = sec5

    # ---------- 6. 低 s_pre 镜像 ----------
    print("\n" + "=" * 92)
    print("6. 低 s_pre 镜像（z>=1.5 + 低MADEV）")
    print("=" * 92)
    l15 = low[low.z >= 1.5].copy()
    if len(l15) >= 30:
        l15["mq"] = pd.qcut(l15.madev, 3, labels=["低", "中", "高"])
        llow = l15[l15.mq == "低"].copy()
        llow = oi_split3(llow)
        sec6 = {}
        for og in ["OI减仓", "OI中性", "OI增仓"]:
            sec6[og] = ps(og, llow[llow.oi_g == og])
        wlow = weekly_sample(llow)
        wlow = oi_split3(wlow)
        sec6w = {}
        print("\n weekly:")
        for og in ["OI减仓", "OI中性", "OI增仓"]:
            sec6w[og] = ps(og, wlow[wlow.oi_g == og])
        out["sections"]["6_low_mirror"] = {"cluster": sec6, "weekly": sec6w}

    # ---------- 7. OOS ----------
    print("\n" + "=" * 92)
    print("7. OOS 时间切分（z>=1.5 + 高MADEV）")
    print("=" * 92)
    oos_base = base.sort_values("ts")
    cut = int(len(oos_base) * 0.7)
    is_df = oos_base.iloc[:cut].copy()
    oos_df = oos_base.iloc[cut:].copy()
    print(f"IS: {is_df.ts.min()} ~ {is_df.ts.max()}, n={len(is_df)}")
    print(f"OOS: {oos_df.ts.min()} ~ {oos_df.ts.max()}, n={len(oos_df)}")
    sec7 = {}
    for name, part in [("IS", is_df), ("OOS", oos_df)]:
        part = oi_split3(part)
        print(f"\n {name}")
        r = {}
        for og in ["OI减仓", "OI中性", "OI增仓"]:
            r[og] = ps(og, part[part.oi_g == og])
        sec7[name] = r
    out["sections"]["7_oos"] = sec7

    # ---------- 8. IC ----------
    print("\n" + "=" * 92)
    print("8. Spearman IC（高 s_pre + z>=1.5）")
    print("=" * 92)
    sec8 = {}
    for var in ["z", "madev", "doi_z", "oi_cum", "oi_slope"]:
        if var in h15.columns and h15[var].notna().sum() > 20:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                ic = spearmanr(h15[var], h15.r100, nan_policy="omit").correlation
            print(f"  {var:>10}: {ic:+.4f}")
            sec8[var] = float(ic)
    out["sections"]["8_ic"] = sec8

    with open(OUT_DIR / "oi_deep_results.json", "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n保存: {OUT_DIR / 'oi_deep_results.json'}")


if __name__ == "__main__":
    main()
