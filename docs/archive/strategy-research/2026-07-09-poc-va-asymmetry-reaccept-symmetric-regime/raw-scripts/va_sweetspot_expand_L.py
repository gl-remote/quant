#!/usr/bin/env python3
"""
B区顺势L扩样
============
目标：B区（sk_xsym × tr_unstable × atr_hi）中顺势L（uptrend × L）仅 n=40，
      CI 太宽无法判断。通过逐步放宽 atr 和 trend 条件，看能否扩大样本量
      至 CI 足以判断方向。

扩样策略（逐级放宽）：
  E0: atr_hi (0.67, 1.01]        ← 基线（当前 B区定义）
  E1: atr_lo=0.50  (midhi+hi)     ← 第一步
  E2: atr_lo=0.33  (mid+midhi+hi) ← 第二步
  E3: atr_hi + trend 放宽到 |rank-0.5|>0.15
  E4: atr_lo=0.50 + trend 放宽到 |rank-0.5|>0.15
  E5: atr_lo=0.33 + trend 放宽到 |rank-0.5|>0.15
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workspace"))

import numpy as np
import pandas as pd
from common.contract_specs import CONTRACT_SPECS

DATASET_PATH = Path("project_data/logs/poc_va_asymmetry_stage4/dataset_full.parquet")
OUT_DIR = Path("project_data/ai_tmp")
N_BOOT = 1000
SEED = 20260709
FLAT_COST_ATR = 0.05
HOLD_TAGS = ["H2", "H4", "H8"]

# 扩样方案
EXPANSIONS = {
    "E0": {"desc": "atr_hi 基线 (atr>0.67)",
           "atr_lo": 0.67, "atr_hi": 1.01,
           "trend_op": "outside", "trend_lo": 0.35, "trend_hi": 0.65},
    "E1": {"desc": "atr_midhi+hi (atr>0.50)",
           "atr_lo": 0.50, "atr_hi": 1.01,
           "trend_op": "outside", "trend_lo": 0.35, "trend_hi": 0.65},
    "E2": {"desc": "atr_mid+midhi+hi (atr>0.33)",
           "atr_lo": 0.33, "atr_hi": 1.01,
           "trend_op": "outside", "trend_lo": 0.35, "trend_hi": 0.65},
    "E3": {"desc": "atr_hi + trend_|rank-0.5|>0.15",
           "atr_lo": 0.67, "atr_hi": 1.01,
           "trend_op": "dev15", "trend_lo": 0.15, "trend_hi": None},
    "E4": {"desc": "atr>0.50 + trend_|rank-0.5|>0.15",
           "atr_lo": 0.50, "atr_hi": 1.01,
           "trend_op": "dev15", "trend_lo": 0.15, "trend_hi": None},
    "E5": {"desc": "atr>0.33 + trend_|rank-0.5|>0.15",
           "atr_lo": 0.33, "atr_hi": 1.01,
           "trend_op": "dev15", "trend_lo": 0.15, "trend_hi": None},
}

# 进一步宽松：sk_xsym → sk_xsym + sk_mild
EXPANSIONS_WIDE = {
    "W0": {"desc": "sk_xsym+sk_mild + atr_hi",
           "skew_lo": 0.00, "skew_hi": 0.20,
           "atr_lo": 0.67, "atr_hi": 1.01,
           "trend_op": "outside", "trend_lo": 0.35, "trend_hi": 0.65},
    "W1": {"desc": "sk_xsym+sk_mild + atr>0.50",
           "skew_lo": 0.00, "skew_hi": 0.20,
           "atr_lo": 0.50, "atr_hi": 1.01,
           "trend_op": "outside", "trend_lo": 0.35, "trend_hi": 0.65},
    "W2": {"desc": "sk_xsym+sk_mild + atr_hi + trend_|rank-0.5|>0.15",
           "skew_lo": 0.00, "skew_hi": 0.20,
           "atr_lo": 0.67, "atr_hi": 1.01,
           "trend_op": "dev15", "trend_lo": 0.15, "trend_hi": None},
}


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
    cL = df["rank20"].notna() & df["close_diff"].notna() & (df["rank20"] <= 0.20) & (df["close_diff"] > 0)
    cS = df["rank20"].notna() & df["close_diff"].notna() & (df["rank20"] >= 0.80) & (df["close_diff"] < 0)
    df["trigger_side"] = np.where(cL, "L", np.where(cS, "S", None))
    df["is_trigger"] = df["trigger_side"].notna()

    # real cost
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

    r4 = df["ret_4h"].values
    df["ret_4h_bps"] = r4 * 10000 if np.nanmean(np.abs(r4)) < 0.1 else r4
    df["ret_2h_bps"] = df["ret_4h_bps"] / 2.0

    # 方向 PnL（做多/做空各自的净值）
    for h, rc in zip(HOLD_TAGS, ["ret_2h_bps", "ret_4h_bps", "ret_8h_bps"]):
        L = np.where(df["trigger_side"] == "L", df[rc] - df["cost_real_bps"], np.nan)
        S = np.where(df["trigger_side"] == "S", -df[rc] - df["cost_real_bps"], np.nan)
        df[f"pnl_{h}_L"] = L
        df[f"pnl_{h}_S"] = S

    # trend_dir
    df["trend_dir"] = np.where(df["trend_ret_10d"] > 0, "up",
                               np.where(df["trend_ret_10d"] < 0, "down", "flat"))
    return df


def apply_exp_mask(df, exp):
    """Apply expansion mask on top of sk_xsym filter"""
    skew_lo = exp.get("skew_lo", 0.00)
    skew_hi = exp.get("skew_hi", 0.10)
    m = df["abs_skew"].between(skew_lo, skew_hi, inclusive="left")
    m &= df["atr_rank_roll"].between(exp["atr_lo"], exp["atr_hi"], inclusive="right")
    if exp["trend_op"] == "outside":
        m &= ~df["trend_rank_roll"].between(exp["trend_lo"], exp["trend_hi"], inclusive="both")
    elif exp["trend_op"] == "dev15":
        m &= (df["trend_rank_roll"] - 0.5).abs() > exp["trend_lo"]
    return m


def cluster_boot_mean(values, contracts, dates, n_boot, rng):
    df_tmp = pd.DataFrame({"v": values, "c": contracts, "d": dates}).dropna(subset=["v"])
    if len(df_tmp) == 0:
        return None, None, None
    clusters = df_tmp.groupby(["c", "d"]).indices
    keys = list(clusters.keys())
    n = len(keys)
    arr = df_tmp["v"].values
    boot = np.empty(n_boot)
    for b in range(n_boot):
        sampled = rng.choice(n, size=n, replace=True)
        idx = []
        for k in sampled:
            idx.extend(clusters[keys[k]])
        boot[b] = np.nanmean(arr[idx])
    return float(np.nanmean(arr)), float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))


def run_expansion(df, label, exp, rng):
    print(f"\n{'─' * 76}")
    print(f"[{label}] {exp['desc']}")
    print(f"{'─' * 76}")

    mask = apply_exp_mask(df, exp)
    sub = df.loc[mask].copy()
    n_total = len(sub)

    # 触发事件统计
    trig_sub = sub[sub["is_trigger"]]
    n_trig = len(trig_sub)
    n_L = trig_sub["trigger_side"].eq("L").sum()
    n_S = trig_sub["trigger_side"].eq("S").sum()
    n_contracts = sub["contract"].nunique()

    # 顺势L (uptrend × L)
    L_up = trig_sub[(trig_sub["trend_dir"] == "up") & (trig_sub["trigger_side"] == "L")]
    n_L_up = len(L_up)

    # 顺势S (downtrend × S)
    S_down = trig_sub[(trig_sub["trend_dir"] == "down") & (trig_sub["trigger_side"] == "S")]
    n_S_down = len(S_down)

    print(f"  总样本 {n_total:,} | 触发 {n_trig} (L={n_L}, S={n_S}) | 合约 {n_contracts}")
    print(f"  顺势L n={n_L_up} | 顺势S n={n_S_down}")

    # 只对顺势L做 bootstrap（本脚本聚焦目标）
    if n_L_up < 5:
        print(f"  顺势L 样本太少 (n={n_L_up})，跳过")
        return None

    row = {"label": label, "desc": exp["desc"],
           "n_total": n_total, "n_L": n_L, "n_S": n_S,
           "n_contracts": n_contracts,
           "n_L_up": n_L_up, "n_S_down": n_S_down}

    for h in HOLD_TAGS:
        col = f"pnl_{h}_L"
        m, lo, hi = cluster_boot_mean(
            L_up[col].values, L_up["contract"].values,
            L_up["event_date"].values, N_BOOT, rng)
        row[f"{h}_mean"] = m if m is not None else 0.0
        row[f"{h}_ci_lo"] = lo if lo is not None else 0.0
        row[f"{h}_ci_hi"] = hi if hi is not None else 0.0
        if m is not None:
            verdict = "✅" if lo and lo > 0 else "❌"
            print(f"  顺势L {h:>3s}: mean={m:+8.2f}  CI=[{lo:+8.2f}, {hi:+8.2f}]  {verdict}")

    # 也报告顺势S 作为基准对照
    if n_S_down >= 5:
        for h in HOLD_TAGS:
            col = f"pnl_{h}_S"
            m, lo, hi = cluster_boot_mean(
                S_down[col].values, S_down["contract"].values,
                S_down["event_date"].values, N_BOOT, rng)
            row[f"顺势S_{h}_mean"] = m if m is not None else 0.0
            row[f"顺势S_{h}_ci_lo"] = lo if lo is not None else 0.0
            if m is not None:
                verdict = "✅" if lo and lo > 0 else "❌"
                print(f"  顺势S {h:>3s}: mean={m:+8.2f}  CI=[{lo:+8.2f}, {hi:+8.2f}]  {verdict}")

    return row


def main():
    t0 = time.time()
    print("=" * 76)
    print("B区顺势L扩样 · B=1000 cluster bootstrap · real 成本")
    print("=" * 76)
    df = pd.read_parquet(DATASET_PATH)
    df = preprocess(df)
    print(f"[preprocess] {len(df)} rows, elapsed={time.time()-t0:.1f}s")

    rng = np.random.RandomState(SEED)

    # 第1组：atr 边界放宽（sk_xsym 不变）
    print(f"\n{'=' * 76}")
    print("第1组 · atr 边界放宽（sk_xsym [0.00,0.10) 不变）")
    print("=" * 76)
    results_1 = []
    for label, exp in EXPANSIONS.items():
        r = run_expansion(df, label, exp, rng)
        if r:
            results_1.append(r)

    # 第2组：skew 放宽到 sk_mild
    print(f"\n{'=' * 76}")
    print("第2组 · skew 放宽到 sk_xsym+sk_mild [0.00,0.20)")
    print("=" * 76)
    results_2 = []
    for label, exp in EXPANSIONS_WIDE.items():
        r = run_expansion(df, label, exp, rng)
        if r:
            results_2.append(r)

    # 汇总表
    print(f"\n{'=' * 76}")
    print("扩样汇总 · 顺势L H4 real")
    print("=" * 76)
    print(f"{'方案':<6s} {'n_L_up':>6s} {'n_total':>8s} {'n_contracts':>11s} "
          f"{'H4_mean':>10s} {'CI_lo':>10s} {'CI_hi':>10s}  verdict")
    for r in results_1:
        v = "✅" if r["H4_ci_lo"] > 0 else "❌"
        print(f"{r['label']:<6s} {r['n_L_up']:>6d} {r['n_total']:>8d} {r['n_contracts']:>11d} "
              f"{r['H4_mean']:>+10.2f} {r['H4_ci_lo']:>+10.2f} {r['H4_ci_hi']:>+10.2f}  {v}")
    print()
    print(f"{'方案':<6s} {'n_L_up':>6s} {'n_total':>8s} {'n_contracts':>11s} "
          f"{'H4_mean':>10s} {'CI_lo':>10s} {'CI_hi':>10s}  verdict")
    for r in results_2:
        v = "✅" if r["H4_ci_lo"] > 0 else "❌"
        print(f"{r['label']:<6s} {r['n_L_up']:>6d} {r['n_total']:>8d} {r['n_contracts']:>11d} "
              f"{r['H4_mean']:>+10.2f} {r['H4_ci_lo']:>+10.2f} {r['H4_ci_hi']:>+10.2f}  {v}")

    print(f"\n[total] elapsed = {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
