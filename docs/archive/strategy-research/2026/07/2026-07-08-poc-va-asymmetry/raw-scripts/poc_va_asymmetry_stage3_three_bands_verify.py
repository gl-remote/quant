"""
验证多头三段论 · 经济逻辑对应 skew 阈值分档

假设（用户经济解读）：
- 段 1 · 极端创新低（skew ≤ 0.09）：恐慌抛售 · 底厚最厚 → 强反转
- 段 2 · 前低附近拉锯（0.09 < skew ≤ 0.19）：多空博弈 · 未突破也未拉起 → 弱信号
- 段 3 · 不及前低（0.19 < skew ≤ 0.25）：前底成支撑 → 强反转

验证：
1. 分段独立算 mean/hit/CI (只用稳定期 · atr≤0.70 · trend≥0.75)
2. 看是否呈"极高 - 中间弱 - 高"的三段
3. 若成立 · 阶段 4 可以只用段 1 + 段 3 · 避开段 2

同时也验证空头：
- 段 1 · 极端创新高（skew ≥ 0.90）
- 段 2 · 前高附近（0.70 ≤ skew < 0.90）
- 段 3 · 广义顶厚（0.60 ≤ skew < 0.70）
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
    cluster_bootstrap_by_date, BONF_ALPHA,
)


def analyze_band(df, band_name, mask, ret_col):
    sub = df[mask].dropna(subset=[ret_col, "transition_flag"]).copy()
    sub["event_date"] = pd.to_datetime(sub["event_time"]).dt.date
    if len(sub) < 20:
        return None
    b = cluster_bootstrap_by_date(sub[ret_col], sub["contract"], sub["event_date"], n_boot=3000)

    daily = sub.groupby("event_date")[ret_col].sum()
    idx = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
    daily_full = daily.reindex(idx, fill_value=0.0)
    sharpe = (daily_full.mean() / daily_full.std() * np.sqrt(252)
              if daily_full.std() > 0 else 0)

    return {
        "band": band_name,
        "n_events": b["n_events"],
        "n_dates": b["n_clusters_date"],
        "mean_bps": b["mean"],
        "hit": (sub[ret_col] > 0).mean(),
        "ci_lo": b["ci_lo_95"],
        "ci_hi": b["ci_hi_95"],
        "p_two": b["p_two"],
        "sharpe": sharpe,
        "ir_per_trade": sub[ret_col].mean() / sub[ret_col].std() if sub[ret_col].std() > 0 else 0,
        "pass_bonf": b["p_two"] < BONF_ALPHA,
    }


def main():
    print("=" * 110)
    print("三段论验证 · 多头 skew 三档 vs 空头 skew 三档")
    print("=" * 110)

    df = prepare_dataset()
    df = flag_regime_transition(df)
    df_stable = df[~df["transition_flag"]].copy()

    print(f"\n数据（仅稳定期）：{len(df_stable)} events\n")

    # ==============================================
    # 多头三段（atr≤0.70 · trend≥0.75 · 8h）
    # ==============================================
    print("=" * 110)
    print("多头三段论验证 · atr≤0.70 · trend≥0.75 · 稳定期 · 8h")
    print("=" * 110)

    long_base = ((df_stable["atr_rank_roll"] <= 0.70) &
                 (df_stable["trend_rank_roll"] >= 0.75))

    long_bands = [
        ("段1 · 极端创新低（skew≤0.09）", df_stable["signed_skew_rank_roll"] <= 0.09),
        ("段2 · 前低附近拉锯（0.09<skew≤0.19）",
         (df_stable["signed_skew_rank_roll"] > 0.09) & (df_stable["signed_skew_rank_roll"] <= 0.19)),
        ("段3 · 不及前低（0.19<skew≤0.25）",
         (df_stable["signed_skew_rank_roll"] > 0.19) & (df_stable["signed_skew_rank_roll"] <= 0.25)),
        ("段4 · 稀释区（0.25<skew≤0.35）",
         (df_stable["signed_skew_rank_roll"] > 0.25) & (df_stable["signed_skew_rank_roll"] <= 0.35)),
    ]

    print(f"\n{'档位':40s} {'n':>5s} {'n_days':>7s} {'mean':>8s} {'hit':>6s} "
          f"{'95% CI':>22s} {'p':>10s} {'Sharpe':>8s} {'IR':>7s} {'Bonf':>6s}")
    print("-" * 130)
    for name, band_mask in long_bands:
        r = analyze_band(df_stable, name, long_base & band_mask, "ret_8h_bps")
        if r is None:
            continue
        ci = f"[{r['ci_lo']:>+6.1f},{r['ci_hi']:>+6.1f}]"
        bonf = "✅" if r["pass_bonf"] else "❌"
        print(f"{name:40s} {int(r['n_events']):>5d} {int(r['n_dates']):>7d} "
              f"{r['mean_bps']:>+8.1f} {r['hit']:>5.1%} {ci:>22s} "
              f"{r['p_two']:>10.4f} {r['sharpe']:>+8.2f} "
              f"{r['ir_per_trade']:>+7.3f} {bonf}")

    # ==============================================
    # 空头三段（atr>0.67 · trend≤0.20 · 4h）
    # ==============================================
    print("\n" + "=" * 110)
    print("空头三段论验证 · atr>0.67 · trend≤0.20 · 稳定期 · 4h")
    print("=" * 110)

    short_base = ((df_stable["atr_rank_roll"] > 0.67) &
                  (df_stable["trend_rank_roll"] <= 0.20))

    short_bands = [
        ("段1 · 极端创新高（skew≥0.91）", df_stable["signed_skew_rank_roll"] >= 0.91),
        ("段2 · 前高附近（0.81≤skew<0.91）",
         (df_stable["signed_skew_rank_roll"] >= 0.81) & (df_stable["signed_skew_rank_roll"] < 0.91)),
        ("段3 · 广义顶厚（0.70≤skew<0.81）",
         (df_stable["signed_skew_rank_roll"] >= 0.70) & (df_stable["signed_skew_rank_roll"] < 0.81)),
        ("段4 · 弱顶厚（0.60≤skew<0.70）",
         (df_stable["signed_skew_rank_roll"] >= 0.60) & (df_stable["signed_skew_rank_roll"] < 0.70)),
    ]

    print(f"\n{'档位':40s} {'n':>5s} {'n_days':>7s} {'mean':>8s} {'hit':>6s} "
          f"{'95% CI':>22s} {'p':>10s} {'Sharpe':>8s} {'IR':>7s} {'Bonf':>6s}")
    print("-" * 130)
    for name, band_mask in short_bands:
        r = analyze_band(df_stable, name, short_base & band_mask, "short_pnl_4h_bps")
        if r is None:
            continue
        ci = f"[{r['ci_lo']:>+6.1f},{r['ci_hi']:>+6.1f}]"
        bonf = "✅" if r["pass_bonf"] else "❌"
        print(f"{name:40s} {int(r['n_events']):>5d} {int(r['n_dates']):>7d} "
              f"{r['mean_bps']:>+8.1f} {r['hit']:>5.1%} {ci:>22s} "
              f"{r['p_two']:>10.4f} {r['sharpe']:>+8.2f} "
              f"{r['ir_per_trade']:>+7.3f} {bonf}")

    # ==============================================
    # 判读
    # ==============================================
    print("\n" + "=" * 110)
    print("经济解读验证")
    print("=" * 110)

    print("\n**多头**：若段 1 和段 3 强 · 段 2 弱 → 三段论成立")
    print("**空头**：若三段强度相近 · 广义顶厚就够 → 单调宽松成立")


if __name__ == "__main__":
    main()
