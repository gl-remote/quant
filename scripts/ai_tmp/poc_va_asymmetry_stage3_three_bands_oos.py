"""
三段论 out-of-sample 验证 · 决定是否值得改分类器

假设：多头 skew 三段论
- 段 1 · 极端创新低 (skew ≤ 0.09) · 强反转
- 段 2 · 前低附近拉锯 (0.09-0.19) · 博弈区
- 段 3 · 未及前低 (0.19-0.25) · 甜蜜点（+91.8）
- 段 4 · 稀释区 (0.25-0.35) · 无效

验证维度：
1. Leave-One-Prefix-Out (LOPO)：14 品种逐一留出 · 其他做验证
2. 时间前后半分：前 50% 与后 50% 分别检验
3. 各品种独立看三段论是否成立

判据（决定是否升级分类器）：
- 强稳定：段 3 > 段 2 在 12+/14 品种成立 · 时间前后半分都保持
- 中稳定：8-11/14 · 或时间一维度失效
- 弱：< 8/14
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


def get_bands_mask(df, band_num):
    """获取 4 段 mask · band_num = 1/2/3/4."""
    rk = df["signed_skew_rank_roll"]
    if band_num == 1:
        return rk <= 0.09
    elif band_num == 2:
        return (rk > 0.09) & (rk <= 0.19)
    elif band_num == 3:
        return (rk > 0.19) & (rk <= 0.25)
    elif band_num == 4:
        return (rk > 0.25) & (rk <= 0.35)


def analyze_bands(df, subset_name, ret_col="ret_8h_bps"):
    """分析 4 段 · 返回结果 dict."""
    base = ((df["atr_rank_roll"] <= 0.70) &
            (df["trend_rank_roll"] >= 0.75) &
            (~df["transition_flag"]))
    results = {}
    for band_num in [1, 2, 3, 4]:
        mask = base & get_bands_mask(df, band_num)
        sub = df[mask].dropna(subset=[ret_col, "transition_flag"]).copy()
        sub["event_date"] = pd.to_datetime(sub["event_time"]).dt.date
        if len(sub) < 5:
            results[band_num] = {"n": 0, "mean": np.nan, "hit": np.nan}
            continue
        results[band_num] = {
            "n": len(sub),
            "mean": sub[ret_col].mean(),
            "hit": (sub[ret_col] > 0).mean(),
        }
    return results


def get_prefix(contract):
    """从合约名提取品种前缀."""
    return "".join([c for c in contract if not c.isdigit()])


def main():
    print("=" * 110)
    print("多头三段论 · Out-of-Sample 验证")
    print("=" * 110)

    df = prepare_dataset()
    df = flag_regime_transition(df)
    df["prefix"] = df["contract"].apply(get_prefix)

    # ==============================================
    # 验证 1 · 全池 baseline
    # ==============================================
    print("\n" + "=" * 110)
    print("Baseline · 全 43 合约")
    print("=" * 110)
    full = analyze_bands(df, "全池")
    print(f"\n{'档位':10s} {'n':>5s} {'mean':>10s} {'hit':>8s}")
    for b in [1, 2, 3, 4]:
        r = full[b]
        if r["n"] > 0:
            print(f"段{b}      {r['n']:>5d} {r['mean']:>+10.1f} {r['hit']:>7.1%}")

    # ==============================================
    # 验证 2 · Leave-One-Prefix-Out (LOPO)
    # ==============================================
    print("\n" + "=" * 110)
    print("LOPO 验证 · 每次留出 1 个品种 · 用其他品种看三段论是否稳定")
    print("=" * 110)

    prefixes = sorted(df["prefix"].unique())
    lopo_results = []
    for prefix in prefixes:
        holdout_df = df[df["prefix"] != prefix].copy()
        result = analyze_bands(holdout_df, f"排除 {prefix}")
        row = {
            "held_out": prefix,
            "b1_n": result[1]["n"], "b1_mean": result[1]["mean"],
            "b2_n": result[2]["n"], "b2_mean": result[2]["mean"],
            "b3_n": result[3]["n"], "b3_mean": result[3]["mean"],
            "b4_n": result[4]["n"], "b4_mean": result[4]["mean"],
        }
        # 段 3 是否强于段 2
        row["b3_beats_b2"] = (row["b3_mean"] > row["b2_mean"]) if not np.isnan(row["b3_mean"]) else False
        # 段 1 是否强于段 2
        row["b1_beats_b2"] = (row["b1_mean"] > row["b2_mean"]) if not np.isnan(row["b1_mean"]) else False
        # 段 4 是否弱于段 3
        row["b4_worse_than_b3"] = (row["b4_mean"] < row["b3_mean"]) if not np.isnan(row["b3_mean"]) else False
        # 三段论完整成立
        row["three_bands_hold"] = row["b1_beats_b2"] and row["b3_beats_b2"] and row["b4_worse_than_b3"]
        lopo_results.append(row)

    lopo_df = pd.DataFrame(lopo_results)
    print(f"\n{'排除品种':10s} {'段1 n':>6s} {'段1 mean':>10s} "
          f"{'段2 n':>6s} {'段2 mean':>10s} "
          f"{'段3 n':>6s} {'段3 mean':>10s} "
          f"{'段4 n':>6s} {'段4 mean':>10s} "
          f"{'段3>段2':>8s} {'三段成立':>8s}")
    for _, r in lopo_df.iterrows():
        b3_b2 = "✅" if r["b3_beats_b2"] else "❌"
        three = "✅" if r["three_bands_hold"] else "❌"
        print(f"{r['held_out']:10s} "
              f"{int(r['b1_n']):>6d} {r['b1_mean']:>+10.1f} "
              f"{int(r['b2_n']):>6d} {r['b2_mean']:>+10.1f} "
              f"{int(r['b3_n']):>6d} {r['b3_mean']:>+10.1f} "
              f"{int(r['b4_n']):>6d} {r['b4_mean']:>+10.1f} "
              f"{b3_b2:>8s} {three:>8s}")

    print(f"\n段 3 > 段 2 保留率：{lopo_df['b3_beats_b2'].sum()}/{len(lopo_df)} = "
          f"{lopo_df['b3_beats_b2'].mean():.1%}")
    print(f"三段论完整成立：{lopo_df['three_bands_hold'].sum()}/{len(lopo_df)} = "
          f"{lopo_df['three_bands_hold'].mean():.1%}")

    # ==============================================
    # 验证 3 · 每品种单独看三段论
    # ==============================================
    print("\n" + "=" * 110)
    print("每品种单独 · 三段论是否成立")
    print("=" * 110)

    per_prefix = []
    for prefix in prefixes:
        sub_df = df[df["prefix"] == prefix].copy()
        result = analyze_bands(sub_df, prefix)
        row = {
            "prefix": prefix,
            "n_contracts": sub_df["contract"].nunique(),
            "b1_n": result[1]["n"], "b1_mean": result[1]["mean"],
            "b2_n": result[2]["n"], "b2_mean": result[2]["mean"],
            "b3_n": result[3]["n"], "b3_mean": result[3]["mean"],
            "b4_n": result[4]["n"], "b4_mean": result[4]["mean"],
        }
        row["b3_beats_b2"] = (
            (row["b3_n"] >= 5 and row["b2_n"] >= 5 and row["b3_mean"] > row["b2_mean"])
            if not np.isnan(row["b3_mean"]) and not np.isnan(row["b2_mean"])
            else None
        )
        row["b1_positive"] = (row["b1_n"] >= 3 and row["b1_mean"] > 0) if not np.isnan(row["b1_mean"]) else None
        row["b3_positive"] = (row["b3_n"] >= 3 and row["b3_mean"] > 0) if not np.isnan(row["b3_mean"]) else None
        per_prefix.append(row)

    pp_df = pd.DataFrame(per_prefix)
    print(f"\n{'品种':10s} {'合约':>5s} "
          f"{'段1 n':>6s} {'段1 mean':>10s} "
          f"{'段2 n':>6s} {'段2 mean':>10s} "
          f"{'段3 n':>6s} {'段3 mean':>10s} "
          f"{'段1 正':>8s} {'段3 正':>8s} {'段3>段2':>8s}")
    for _, r in pp_df.iterrows():
        b1p = "✅" if r["b1_positive"] else ("❌" if r["b1_positive"] is False else "?")
        b3p = "✅" if r["b3_positive"] else ("❌" if r["b3_positive"] is False else "?")
        b3b2 = "✅" if r["b3_beats_b2"] else ("❌" if r["b3_beats_b2"] is False else "?")
        b1m = "-" if np.isnan(r["b1_mean"]) else f"{r['b1_mean']:+.1f}"
        b2m = "-" if np.isnan(r["b2_mean"]) else f"{r['b2_mean']:+.1f}"
        b3m = "-" if np.isnan(r["b3_mean"]) else f"{r['b3_mean']:+.1f}"
        print(f"{r['prefix']:10s} {int(r['n_contracts']):>5d} "
              f"{int(r['b1_n']):>6d} {b1m:>10s} "
              f"{int(r['b2_n']):>6d} {b2m:>10s} "
              f"{int(r['b3_n']):>6d} {b3m:>10s} "
              f"{b1p:>8s} {b3p:>8s} {b3b2:>8s}")

    n_valid = pp_df["b3_beats_b2"].notna().sum()
    n_yes = (pp_df["b3_beats_b2"] == True).sum()
    n_b3_pos = (pp_df["b3_positive"] == True).sum()
    n_valid_pos = pp_df["b3_positive"].notna().sum()
    print(f"\n单品种段 3 > 段 2 保留率：{n_yes}/{n_valid} = {n_yes/max(1,n_valid):.1%}")
    print(f"单品种段 3 mean > 0 保留率：{n_b3_pos}/{n_valid_pos} = {n_b3_pos/max(1,n_valid_pos):.1%}")

    # ==============================================
    # 验证 4 · 时间前后半分
    # ==============================================
    print("\n" + "=" * 110)
    print("时间前后半分 · 三段论是否有时效性")
    print("=" * 110)

    df["event_time_dt"] = pd.to_datetime(df["event_time"])
    median_time = df["event_time_dt"].median()
    df_early = df[df["event_time_dt"] < median_time].copy()
    df_late = df[df["event_time_dt"] >= median_time].copy()

    print(f"\n前半样本：{len(df_early)} events · 起止 {df_early['event_time_dt'].min()} ~ {df_early['event_time_dt'].max()}")
    print(f"后半样本：{len(df_late)} events · 起止 {df_late['event_time_dt'].min()} ~ {df_late['event_time_dt'].max()}")

    for tag, sub_df in [("前半", df_early), ("后半", df_late)]:
        r = analyze_bands(sub_df, tag)
        print(f"\n【{tag}】")
        for b in [1, 2, 3, 4]:
            rr = r[b]
            if rr["n"] > 0:
                print(f"  段{b}: n={rr['n']:>4d} · mean={rr['mean']:>+7.1f} · hit={rr['hit']:>5.1%}")

    # ==============================================
    # 保存
    # ==============================================
    LOG_DIR = Path("/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage3")
    lopo_df.to_csv(LOG_DIR / "three_bands_lopo.csv", index=False)
    pp_df.to_csv(LOG_DIR / "three_bands_per_prefix.csv", index=False)

    # ==============================================
    # 判读
    # ==============================================
    print("\n" + "=" * 110)
    print("综合判读")
    print("=" * 110)
    lopo_rate = lopo_df["b3_beats_b2"].mean()
    if lopo_rate >= 0.85:
        print(f"✅ LOPO 段 3>段 2 稳定率 {lopo_rate:.1%} · 强稳定")
    elif lopo_rate >= 0.60:
        print(f"⚠️  LOPO 段 3>段 2 稳定率 {lopo_rate:.1%} · 中稳定")
    else:
        print(f"❌ LOPO 段 3>段 2 稳定率 {lopo_rate:.1%} · 不稳定")


if __name__ == "__main__":
    main()
