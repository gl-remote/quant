#!/usr/bin/env python3
"""
甜蜜区假设验证：适度倾斜 + 平稳趋势 是否构成 VA reaccept 甜蜜区
==============================================================
用户假设（先验）：
  - "适度倾斜"（|skew - 0.5| 在中等范围）提供回归动能
  - "平稳趋势"（trend_rank 在中间）提供不被打脸的环境
  - 两者交互形成 VA reaccept 甜蜜区
  - 完全对称（|skew - 0.5| ≈ 0）反而无动能 → 弱
  - 过度倾斜（|skew - 0.5| 大）反而趋势延续 → 弱

设计：把 skew 抽象为 "abs_skew" = |signed_skew_rank_roll - 0.5|
  - abs_skew ∈ [0.00, 0.10)   : 极对称（xneu 核心）
  - abs_skew ∈ [0.10, 0.20)   : 适度倾斜（wneg/wpos 主体）
  - abs_skew ∈ [0.20, 0.50]   : 强倾斜（wneg 外缘 / mpos 主体 / 更极端）

trend 抽象为二分：
  - stable: trend_rank ∈ [0.35, 0.65]  (中间 30% · 平稳趋势)
  - unstable: 外面（趋势明显）

atr 保留 3 档：mid/midhi/hi

共 3 × 2 × 3 = 18 组 · 每组样本较原设计大 3-5 倍 · CI 更稳
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workspace"))

import numpy as np
import pandas as pd
from common.contract_specs import CONTRACT_SPECS

DATASET_PATH = Path("project_data/logs/poc_va_asymmetry_stage4/dataset_full.parquet")
OUT_DIR = Path("project_data/ai_tmp")

# 分档定义（对齐用户假设）
ABS_SKEW_BINS = [
    ("sk_xsym",  0.00, 0.10),  # 极对称
    ("sk_mild",  0.10, 0.20),  # 适度倾斜 ← 甜蜜区候选
    ("sk_strong",0.20, 0.51),  # 强倾斜
]
TREND_BINS = [
    ("tr_stable",   0.35, 0.65),  # 平稳趋势 ← 甜蜜区候选
    ("tr_unstable", -1.00, 0.35),  # 用 -1 表示"或"边界，实际取 < 0.35 OR > 0.65
]
ATR_BINS = [
    ("atr_mid",   0.33, 0.50),
    ("atr_midhi", 0.50, 0.67),
    ("atr_hi",    0.67, 1.01),
]
HOLD_TAGS = ["H2", "H4", "H8"]

N_BOOTSTRAP = 500  # 提精度（相比 60 组扫描的 200）
SEED = 20260709
MIN_PAIRS = 30     # 提门槛：粗分档后每组应有更多样本
FLAT_COST_ATR = 0.05


def preprocess(df):
    df = df.copy()
    df["event_time"] = pd.to_datetime(df["event_time"])
    df["event_date"] = pd.to_datetime(df["event_date"]).dt.date
    df = df.sort_values(["contract", "event_time"]).reset_index(drop=True)
    df["abs_skew"] = (df["signed_skew_rank_roll"] - 0.5).abs()
    df["rank20"] = df.groupby("contract")["close_t"].transform(
        lambda s: s.rolling(20, min_periods=10).rank(pct=True)
    )
    df["close_diff"] = df.groupby("contract")["close_t"].diff(1)
    df["close_diff_atr"] = (
        df["close_diff"] / df["close_t"].replace(0, np.nan) * 10000
        / df["daily_atr_10_bps"].replace(0, np.nan)
    )
    cond_L = df["rank20"].notna() & df["close_diff"].notna() & (df["rank20"] <= 0.20) & (df["close_diff"] > 0)
    cond_S = df["rank20"].notna() & df["close_diff"].notna() & (df["rank20"] >= 0.80) & (df["close_diff"] < 0)
    df["trigger_side"] = np.where(cond_L, "L", np.where(cond_S, "S", None))
    df["is_trigger"] = df["trigger_side"].notna()

    df["cost_flat_bps"] = df["daily_atr_10_bps"] * FLAT_COST_ATR
    # 真实成本
    out = np.full(len(df), np.nan)
    for c in df["contract"].unique():
        spec = CONTRACT_SPECS.get_symbol(c)
        if spec is None:
            continue
        m = (df["contract"] == c).values
        p = df.loc[m, "close_t"].values
        size = spec.size
        if hasattr(spec, "total_commission_np"):
            comm = spec.total_commission_np(p, 1)
        else:
            comm = np.array([spec.total_commission(price=float(x), lots=1) for x in p])
        slip = spec.slippage(lots=1)
        out[m] = 2 * (comm + slip) / (p * size) * 10000
    df["cost_real_bps"] = out

    r4_raw = df["ret_4h"].values
    df["ret_4h_bps"] = r4_raw * 10000 if np.nanmean(np.abs(r4_raw)) < 0.1 else r4_raw
    df["ret_2h_bps"] = df["ret_4h_bps"] / 2.0

    sign = np.where(df["trigger_side"] == "L", 1.0, np.where(df["trigger_side"] == "S", -1.0, np.nan))
    df["_sign"] = sign
    for h, rc in zip(HOLD_TAGS, ["ret_2h_bps", "ret_4h_bps", "ret_8h_bps"]):
        df[f"pnl_trig_{h}_flat"] = sign * df[rc] - df["cost_flat_bps"]
        df[f"pnl_trig_{h}_real"] = sign * df[rc] - df["cost_real_bps"]
    return df


def trend_mask(df, tr_tag, lo, hi):
    if tr_tag == "tr_stable":
        return df["trend_rank_roll"].between(lo, hi, inclusive="both")
    else:
        return ~df["trend_rank_roll"].between(0.35, 0.65, inclusive="both")


def scan_cell(df, sk_lo, sk_hi, tr_tag, tr_lo, tr_hi, at_lo, at_hi, rng):
    mask = (
        df["abs_skew"].between(sk_lo, sk_hi, inclusive="left")
        & trend_mask(df, tr_tag, tr_lo, tr_hi)
        & df["atr_rank_roll"].between(at_lo, at_hi, inclusive="right")
    )
    sub = df.loc[mask]
    trig = sub[sub["is_trigger"]]
    no_trig = sub[~sub["is_trigger"]]
    if len(trig) < MIN_PAIRS or len(no_trig) < MIN_PAIRS:
        return {"n_sub": len(sub), "n_trig": len(trig), "n_pairs": 0}

    pairs_data = []
    for contract in trig["contract"].dropna().unique():
        nt_c = no_trig[no_trig["contract"] == contract]
        if len(nt_c) == 0:
            continue
        for side in ["L", "S"]:
            t_c = trig[(trig["contract"] == contract) & (trig["trigger_side"] == side)]
            if len(t_c) == 0 or len(nt_c) < len(t_c):
                continue
            nt_avail = nt_c["close_diff_atr"].values
            nt_index = nt_c.index.values
            used = np.zeros(len(nt_avail), dtype=bool)
            sign = 1.0 if side == "L" else -1.0
            for _, row in t_c.iterrows():
                x = row["close_diff_atr"]
                if pd.isna(x):
                    continue
                d = np.abs(nt_avail - x)
                d[used] = np.inf
                pick = int(np.argmin(d))
                if not np.isfinite(d[pick]):
                    continue
                used[pick] = True
                nt_row = df.loc[nt_index[pick]]
                pairs_data.append({
                    "contract": contract,
                    "event_date": row["event_date"],
                    **{f"trig_{h}_{ct}": row[f"pnl_trig_{h}_{ct}"]
                       for h in HOLD_TAGS for ct in ["flat", "real"]},
                    **{f"nt_{h}_{ct}": sign * nt_row[f"ret_{'2h' if h=='H2' else ('4h' if h=='H4' else '8h')}_bps"] - nt_row[f"cost_{ct}_bps"]
                       for h in HOLD_TAGS for ct in ["flat", "real"]},
                })
    if not pairs_data:
        return {"n_sub": len(sub), "n_trig": len(trig), "n_pairs": 0}
    pdf = pd.DataFrame(pairs_data)
    for h in HOLD_TAGS:
        for ct in ["flat", "real"]:
            pdf[f"diff_{h}_{ct}"] = pdf[f"trig_{h}_{ct}"] - pdf[f"nt_{h}_{ct}"]
    if len(pdf) < MIN_PAIRS:
        return {"n_sub": len(sub), "n_trig": len(trig), "n_pairs": len(pdf)}

    clusters = pdf.groupby(["contract", "event_date"]).indices
    cluster_keys = list(clusters.keys())
    n_clusters = len(cluster_keys)
    diff_cols = [f"diff_{h}_{ct}" for h in HOLD_TAGS for ct in ["flat", "real"]]
    diff_arr = pdf[diff_cols].values
    boot = np.empty((N_BOOTSTRAP, len(diff_cols)))
    for b in range(N_BOOTSTRAP):
        sampled = rng.choice(n_clusters, size=n_clusters, replace=True)
        idx = []
        for k in sampled:
            idx.extend(clusters[cluster_keys[k]])
        boot[b] = np.nanmean(diff_arr[idx], axis=0)
    obs = np.nanmean(diff_arr, axis=0)
    ci_lo = np.nanquantile(boot, 0.025, axis=0)
    ci_hi = np.nanquantile(boot, 0.975, axis=0)
    per_c = pdf.groupby("contract")
    result = {"n_sub": len(sub), "n_trig": len(trig), "n_pairs": len(pdf), "n_clusters": n_clusters,
              "n_contracts": pdf["contract"].nunique()}
    for i, col in enumerate(diff_cols):
        result[f"{col}_mean"] = float(obs[i])
        result[f"{col}_ci_lo"] = float(ci_lo[i])
        result[f"{col}_ci_hi"] = float(ci_hi[i])
        pc = per_c[col].mean()
        result[f"{col}_sym_ret"] = float((pc > 0).mean())
    return result


def main():
    t0 = time.time()
    print("=" * 76)
    print("甜蜜区假设验证：适度倾斜 + 平稳趋势")
    print("=" * 76)
    df = pd.read_parquet(DATASET_PATH)
    df = preprocess(df)
    print(f"[preprocess] {len(df)} rows, {df['contract'].nunique()} contracts, "
          f"triggers: L={(df['trigger_side']=='L').sum()}, S={(df['trigger_side']=='S').sum()}")

    # abs_skew 分布检查
    print("\n[abs_skew 分布]")
    for tag, lo, hi in ABS_SKEW_BINS:
        n = df["abs_skew"].between(lo, hi, inclusive="left").sum()
        print(f"  {tag} [{lo:.2f},{hi:.2f}): n={n} ({n/len(df)*100:.1f}%)")
    print("[trend_stable 分布]")
    for tag, lo, hi in TREND_BINS:
        n = trend_mask(df, tag, lo, hi).sum()
        print(f"  {tag}: n={n} ({n/len(df)*100:.1f}%)")

    rng = np.random.RandomState(SEED)
    rows = []
    for sk_tag, sk_lo, sk_hi in ABS_SKEW_BINS:
        for tr_tag, tr_lo, tr_hi in TREND_BINS:
            for at_tag, at_lo, at_hi in ATR_BINS:
                t_c = time.time()
                res = scan_cell(df, sk_lo, sk_hi, tr_tag, tr_lo, tr_hi, at_lo, at_hi, rng)
                res.update({"abs_skew": sk_tag, "trend": tr_tag, "atr": at_tag})
                rows.append(res)
                tag = "SKIP" if res["n_pairs"] < MIN_PAIRS else "OK"
                print(f"  {sk_tag:>10s} × {tr_tag:>12s} × {at_tag:>10s} "
                      f"n_sub={res.get('n_sub',0):>4d} n_pairs={res.get('n_pairs',0):>4d} "
                      f"H4_real={res.get('diff_H4_real_mean', float('nan')):+7.2f} "
                      f"CI=[{res.get('diff_H4_real_ci_lo', float('nan')):+.1f},{res.get('diff_H4_real_ci_hi', float('nan')):+.1f}] "
                      f"· {tag} ({time.time()-t_c:.1f}s)")

    out_df = pd.DataFrame(rows)
    out_df.to_csv(OUT_DIR / "va_sweetspot_scan_summary.csv", index=False)
    print(f"\n[save] {OUT_DIR / 'va_sweetspot_scan_summary.csv'}")

    valid = out_df[out_df["n_pairs"] >= MIN_PAIRS].copy()
    print(f"\n有效子组：{len(valid)}/18")

    # 交叉表打印（H4 real mean）
    print("\n" + "=" * 76)
    print("[交叉表 · H4 real mean bps] (行=abs_skew, 列=trend×atr)")
    print("=" * 76)
    pivot = valid.pivot_table(index="abs_skew", columns=["trend", "atr"],
                              values="diff_H4_real_mean", aggfunc="mean")
    print(pivot.round(1).to_string())

    print("\n[交叉表 · CI95_lo H4 real] (>0 才显著)")
    pivot_ci = valid.pivot_table(index="abs_skew", columns=["trend", "atr"],
                                  values="diff_H4_real_ci_lo", aggfunc="mean")
    print(pivot_ci.round(1).to_string())

    print("\n[交叉表 · symbol_retention H4 real]")
    pivot_sr = valid.pivot_table(index="abs_skew", columns=["trend", "atr"],
                                  values="diff_H4_real_sym_ret", aggfunc="mean")
    print(pivot_sr.round(2).to_string())

    # 关键对比 · 甜蜜区 vs 对照
    print("\n" + "=" * 76)
    print("甜蜜区假设 · 关键对比")
    print("=" * 76)
    sweet = valid[(valid["abs_skew"] == "sk_mild") & (valid["trend"] == "tr_stable")]
    print(f"\n甜蜜区 (sk_mild × tr_stable · 3 atr 档):")
    print(sweet[["atr", "n_pairs", "diff_H4_real_mean", "diff_H4_real_ci_lo",
                 "diff_H4_real_ci_hi", "diff_H4_real_sym_ret"]].round(2).to_string(index=False))

    print(f"\n对照 · 极对称 × 平稳 (sk_xsym × tr_stable):")
    ctrl1 = valid[(valid["abs_skew"] == "sk_xsym") & (valid["trend"] == "tr_stable")]
    print(ctrl1[["atr", "n_pairs", "diff_H4_real_mean", "diff_H4_real_ci_lo",
                 "diff_H4_real_ci_hi", "diff_H4_real_sym_ret"]].round(2).to_string(index=False))

    print(f"\n对照 · 强倾斜 × 平稳 (sk_strong × tr_stable):")
    ctrl2 = valid[(valid["abs_skew"] == "sk_strong") & (valid["trend"] == "tr_stable")]
    print(ctrl2[["atr", "n_pairs", "diff_H4_real_mean", "diff_H4_real_ci_lo",
                 "diff_H4_real_ci_hi", "diff_H4_real_sym_ret"]].round(2).to_string(index=False))

    print(f"\n对照 · 适度倾斜 × 非平稳 (sk_mild × tr_unstable):")
    ctrl3 = valid[(valid["abs_skew"] == "sk_mild") & (valid["trend"] == "tr_unstable")]
    print(ctrl3[["atr", "n_pairs", "diff_H4_real_mean", "diff_H4_real_ci_lo",
                 "diff_H4_real_ci_hi", "diff_H4_real_sym_ret"]].round(2).to_string(index=False))

    # 判决
    print("\n" + "=" * 76)
    print("甜蜜区假设判决")
    print("=" * 76)
    if len(sweet) == 0:
        print("❌ 甜蜜区无有效数据")
        return
    sweet_ok = (sweet["diff_H4_real_ci_lo"] > 0).any()
    sweet_mean = sweet["diff_H4_real_mean"].mean()
    ctrl1_mean = ctrl1["diff_H4_real_mean"].mean() if len(ctrl1) > 0 else np.nan
    ctrl2_mean = ctrl2["diff_H4_real_mean"].mean() if len(ctrl2) > 0 else np.nan
    ctrl3_mean = ctrl3["diff_H4_real_mean"].mean() if len(ctrl3) > 0 else np.nan
    print(f"甜蜜区均值 (avg over atr): {sweet_mean:+.2f} bps")
    print(f"极对称 × 平稳:            {ctrl1_mean:+.2f} bps")
    print(f"强倾斜 × 平稳:            {ctrl2_mean:+.2f} bps")
    print(f"适度倾斜 × 非平稳:        {ctrl3_mean:+.2f} bps")
    print()
    print(f"甜蜜区是否严格 > 极对称: {sweet_mean > ctrl1_mean if not np.isnan(ctrl1_mean) else '?'}")
    print(f"甜蜜区是否严格 > 强倾斜: {sweet_mean > ctrl2_mean if not np.isnan(ctrl2_mean) else '?'}")
    print(f"甜蜜区是否严格 > 非平稳: {sweet_mean > ctrl3_mean if not np.isnan(ctrl3_mean) else '?'}")
    print(f"甜蜜区至少 1 atr 档 CI 排 0: {sweet_ok}")

    print(f"\n[total] elapsed = {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
