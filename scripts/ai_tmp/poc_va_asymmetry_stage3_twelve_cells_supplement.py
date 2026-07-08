"""
12 格深度诊断的关键补充：
1. 段 3 · ATR 低（最强稳定格子）· 分品种独立 CI · 确认不是靠 DCE.m
2. 空头对称分析 · 4 分位 × 3 ATR × trend≤0.20 · 稳定期 4h horizon
   验证空头是否也有类似的"分位 × 制度"细结构
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/scripts/ai_tmp")
from poc_va_asymmetry_stage2_grid_search import prepare_dataset  # noqa: E402
from poc_va_asymmetry_stage3_task3_regime_transition import flag_regime_transition  # noqa: E402
from poc_va_asymmetry_stage3_classifier_strict_bootstrap import (  # noqa: E402
    cluster_bootstrap_by_date,
)


LONG_BANDS = [
    ("段1", 0.00, 0.09),
    ("段2", 0.09, 0.19),
    ("段3", 0.19, 0.25),
    ("段4", 0.25, 0.30),
]

# 空头对称：从 skew 高端往低端切
SHORT_BANDS = [
    ("段1", 0.91, 1.01),  # 极端创新高
    ("段2", 0.81, 0.91),  # 前高拉锯
    ("段3", 0.75, 0.81),  # 未及前高
    ("段4", 0.70, 0.75),  # 弱顶厚（稀释区）
]

ATR_REGIMES = [
    ("低", 0.00, 0.33),
    ("中", 0.33, 0.67),
    ("高", 0.67, 1.00),
]

LOG_DIR = Path("/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage3")


def get_prefix(contract):
    return "".join([c for c in contract if not c.isdigit()])


def long_cell_mask(df, band_lo, band_hi, atr_lo, atr_hi):
    return (
        (df["signed_skew_rank_roll"] > band_lo) &
        (df["signed_skew_rank_roll"] <= band_hi) &
        (df["atr_rank_roll"] > atr_lo) &
        (df["atr_rank_roll"] <= atr_hi) &
        (df["trend_rank_roll"] >= 0.75) &
        (~df["transition_flag"])
    )


def short_cell_mask(df, band_lo, band_hi, atr_lo, atr_hi):
    """空头方向 · trend≤0.20"""
    return (
        (df["signed_skew_rank_roll"] >= band_lo) &
        (df["signed_skew_rank_roll"] < band_hi) &
        (df["atr_rank_roll"] > atr_lo) &
        (df["atr_rank_roll"] <= atr_hi) &
        (df["trend_rank_roll"] <= 0.20) &
        (~df["transition_flag"])
    )


def cell_summary(df, mask, ret_col):
    sub = df[mask].dropna(subset=[ret_col]).copy()
    if len(sub) < 3:
        return None
    sub["event_date"] = pd.to_datetime(sub["event_time"]).dt.date
    sub["prefix"] = sub["contract"].apply(get_prefix)

    n = len(sub)
    prefix_stats = sub.groupby("prefix")[ret_col].agg(["count", "mean"])
    prefix_stats = prefix_stats[prefix_stats["count"] >= 3]

    return {
        "n": n,
        "n_days": sub["event_date"].nunique(),
        "n_prefix_valid": len(prefix_stats),
        "n_positive": (prefix_stats["mean"] > 0).sum() if len(prefix_stats) > 0 else 0,
        "mean": sub[ret_col].mean(),
        "hit": (sub[ret_col] > 0).mean(),
    }


def main():
    print("=" * 120)
    print("补充验证 · 段3·ATR低 分品种 + 空头对称 12 格")
    print("=" * 120)

    df = prepare_dataset()
    df = flag_regime_transition(df)

    # ============================================
    # 补充 1 · 段 3 · ATR 低 分品种独立 CI
    # ============================================
    print("\n" + "=" * 120)
    print("补充 1 · 段3·ATR低（最强格子 mean +85 · hit 83%）· 分品种独立看")
    print("=" * 120)

    mask_seg3_low = long_cell_mask(df, 0.19, 0.25, 0.00, 0.33)
    sub = df[mask_seg3_low].dropna(subset=["ret_8h_bps"]).copy()
    sub["prefix"] = sub["contract"].apply(get_prefix)

    print(f"\n{'品种':10s} {'n':>4s} {'mean':>8s} {'hit':>7s} {'std':>7s}")
    print("-" * 60)
    prefix_group = sub.groupby("prefix")
    prefix_result = []
    for prefix, g in prefix_group:
        if len(g) < 2:
            continue
        r = g["ret_8h_bps"].values
        prefix_result.append({
            "prefix": prefix,
            "n": len(r),
            "mean": r.mean(),
            "hit": (r > 0).mean(),
            "std": r.std() if len(r) > 1 else 0,
        })
    prefix_df = pd.DataFrame(prefix_result).sort_values("n", ascending=False)
    for _, r in prefix_df.iterrows():
        print(f"{r['prefix']:10s} {int(r['n']):>4d} {r['mean']:>+8.1f} {r['hit']:>6.1%} {r['std']:>7.1f}")

    n_positive = (prefix_df["mean"] > 0).sum()
    n_total = len(prefix_df)
    print(f"\n品种保留率：{n_positive}/{n_total} = {n_positive/max(1,n_total):.1%}")

    # 移除主导品种（DCE.m）后重算
    print("\n【移除 DCE.m 后 · 是否还成立】")
    sub_no_m = sub[sub["prefix"] != "DCE.m"]
    if len(sub_no_m) > 0:
        r = sub_no_m["ret_8h_bps"].values
        print(f"  剩余 n={len(sub_no_m)} · mean={r.mean():+.1f} · hit={(r>0).mean():.1%}")

    # ============================================
    # 补充 2 · 空头对称 12 格
    # ============================================
    print("\n" + "=" * 120)
    print("补充 2 · 空头对称 12 格 · trend≤0.20 · 稳定期 · 4h horizon")
    print("=" * 120)

    print(f"\n{'格子':30s} {'n':>4s} {'mean':>8s} {'hit':>7s} {'n_prefix≥3':>11s} {'品种保留':>10s} {'主导品种':>10s}")
    print("-" * 120)

    short_result = {}
    for band_name, band_lo, band_hi in SHORT_BANDS:
        for atr_name, atr_lo, atr_hi in ATR_REGIMES:
            key = f"{band_name}·ATR{atr_name}"
            mask = short_cell_mask(df, band_lo, band_hi, atr_lo, atr_hi)
            s = cell_summary(df, mask, "short_pnl_4h_bps")
            short_result[key] = s
            if s is None:
                print(f"{key:30s} {'-':>4s} {'-':>8s} {'-':>7s} {'-':>11s} {'-':>10s} {'-':>10s}")
                continue

            sub = df[mask].dropna(subset=["short_pnl_4h_bps"]).copy()
            sub["prefix"] = sub["contract"].apply(get_prefix)
            top_pfx = "-"
            if len(sub) > 0:
                pfx_counts = sub.groupby("prefix").size()
                if len(pfx_counts) > 0:
                    top_pfx = pfx_counts.idxmax()
            retain = s["n_positive"] / max(1, s["n_prefix_valid"])
            print(f"{key:30s} {s['n']:>4d} {s['mean']:>+8.1f} {s['hit']:>6.1%} "
                  f"{s['n_prefix_valid']:>11d} {retain:>9.1%} {top_pfx:>10s}")

    # 空头 ATR 制度一致性
    print("\n" + "=" * 120)
    print("空头 · ATR 制度一致性 · 每分位段的 mean 曲线")
    print("=" * 120)
    print(f"\n{'分位段':10s} {'ATR低':>10s} {'ATR中':>10s} {'ATR高':>10s} {'峰值 ATR':>10s}")
    print("-" * 60)
    for band_name, _, _ in SHORT_BANDS:
        vals = []
        for atr_name, _, _ in ATR_REGIMES:
            key = f"{band_name}·ATR{atr_name}"
            s = short_result.get(key)
            if s and s["n"] >= 5:
                vals.append(s["mean"])
            else:
                vals.append(np.nan)
        if not any(np.isnan(vals)):
            peak = ["低", "中", "高"][int(np.argmax(vals))]
        else:
            peak = "-"
        print(f"{band_name:10s} " +
              " ".join([f"{v:>+10.1f}" if not np.isnan(v) else f"{'-':>10s}" for v in vals]) +
              f" {peak:>10s}")

    print("\n" + "=" * 120)
    print("综合判读")
    print("=" * 120)
    print("""
1. 段3·ATR低 · 分品种是否稳固？
   - 若 DCE.m 移除后 mean 仍显著 > 0 → 稳固 · 段3甜蜜点得以确认
   - 若 DCE.m 移除后 mean 塌陷 → 是 DCE.m 特殊现象 · 不是普适规律

2. 空头对称性：
   - 若空头 12 格显示"高 ATR 是甜蜜点" → 对称成立
   - 若空头 12 格显示"低 ATR 也有信号" → 空头结构与多头不同
""")


if __name__ == "__main__":
    main()
