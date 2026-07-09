"""
文件级元信息：
- 创建背景：验证"降级合并版" · 6 类合并 vs 144 tier 精细化
- 用途：把 144 tier 的通过区域合并为 6 大类 · 跑严格验证 · 看合并后 CI/p 是否更好
- 注意事项：临时脚本 · 复用 stage4 验证函数
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/scripts/ai_tmp")
from poc_va_asymmetry_stage4_data_full import prepare_dataset_full  # noqa: E402
from poc_va_asymmetry_stage3_task3_regime_transition import flag_regime_transition  # noqa: E402
from poc_va_asymmetry_stage4_step2_seven_layer import (  # noqa: E402
    cluster_bootstrap_by_date, counterfactual_test,
    symbol_retention, time_stability, per_trade_ir,
)

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage4"
)

# 6 类合并（基于 144 tier 通过区域的合并）
CLASSES = [
    # (name, direction, ret_col, skew_lo, skew_hi, atr_lo, atr_hi, trend_lo, trend_hi)
    # 多头 3 类
    ("L_seg3_lowmid_up",  "long",  "ret_8h_bps",       0.09, 0.30,  0.00, 0.67,  0.75, 1.01),  # 段2/3 低中ATR 涨
    ("L_seg12_high_up",   "long",  "ret_8h_bps",       0.00, 0.19,  0.67, 1.01,  0.75, 1.01),  # 段1/2 高ATR 涨
    ("L_seg2_low_flat",   "long",  "ret_8h_bps",       0.09, 0.19,  0.00, 0.33,  0.20, 0.75),  # 段2 低ATR 平稳
    # 空头 3 类
    ("S_seg12_high_dn",   "short", "short_pnl_4h_bps", 0.81, 1.00,  0.67, 1.01,  0.00, 0.20),  # 段1/2 高ATR 跌
    ("S_seg34_high_dn",   "short", "short_pnl_4h_bps", 0.60, 0.81,  0.67, 1.01,  0.00, 0.20),  # 段3/4 高ATR 跌
    ("S_seg2_mid_dn",     "short", "short_pnl_4h_bps", 0.81, 0.91,  0.33, 0.67,  0.00, 0.20),  # 段2 中ATR 跌
]

BOOT_N = 5000
CF_N = 5000
FDR_ALPHA = 0.05
BONF_FAMILY = 6                       # 6 类
BONF_ALPHA = 0.05 / BONF_FAMILY       # 0.00833
CF_ALPHA = 0.001
TIME_STAB_LINE = 0.50


def make_mask(df, sk_lo, sk_hi, at_lo, at_hi, tr_lo, tr_hi):
    m = (df["signed_skew_rank_roll"] >= sk_lo) & (df["signed_skew_rank_roll"] <= sk_hi)
    m &= (df["atr_rank_roll"] >= at_lo) & (df["atr_rank_roll"] <= at_hi)
    m &= (df["trend_rank_roll"] >= tr_lo) & (df["trend_rank_roll"] <= tr_hi)
    return m


def verify_class(df, name, direction, ret_col, sk_lo, sk_hi, at_lo, at_hi, tr_lo, tr_hi):
    mask = make_mask(df, sk_lo, sk_hi, at_lo, at_hi, tr_lo, tr_hi)
    sub = df[mask].dropna(subset=[ret_col, "transition_flag"]).copy()
    sub["event_date"] = pd.to_datetime(sub["event_time"]).dt.date
    all_ret = df[ret_col].dropna()

    rows = []
    for period, seg in [
        ("full", sub),
        ("stable", sub[~sub["transition_flag"]]),
        ("trans", sub[sub["transition_flag"]]),
    ]:
        n = len(seg)
        n_days = seg["event_date"].nunique() if n else 0
        if n < 15 or n_days < 5:
            rows.append({"class": name, "direction": direction, "period": period, "n": n, "n_days": n_days, "skipped": True})
            continue
        boot = cluster_bootstrap_by_date(seg[ret_col], seg["contract"], seg["event_date"], n_boot=BOOT_N)
        cf = counterfactual_test(seg[ret_col].values, all_ret.values, n=CF_N)
        sr = symbol_retention(seg, ret_col)
        ir = per_trade_ir(seg[ret_col].values)
        ts = time_stability(seg, ret_col)
        rows.append({
            "class": name, "direction": direction, "period": period,
            "n": n, "n_days": n_days,
            "mean_bps": boot["mean"], "ci_lo": boot["ci_lo_95"], "ci_hi": boot["ci_hi_95"],
            "p_boot": boot["p_two"], "p_cf": cf["p_cf"],
            "symbol_retain": sr, "ir": ir, "time_stab": ts,
            "skipped": False,
        })
    return rows


def bh_correct(pvals: list[float], alpha: float) -> float:
    """返回 BH 阈值 · p ≤ threshold 通过."""
    arr = np.array(sorted(pvals))
    n = len(arr)
    ranks = np.arange(1, n + 1)
    thr = ranks / n * alpha
    valid = arr[arr <= thr]
    return valid.max() if len(valid) > 0 else 0.0


def main():
    print("=" * 100)
    print("6 类合并版严格验证（vs 144 tier 精细化对比）")
    print("=" * 100)

    df = prepare_dataset_full()
    df = flag_regime_transition(df)
    print(f"\n数据规模：{len(df)} events · {df['contract'].nunique()} 品种")

    all_rows = []
    for cfg in CLASSES:
        all_rows.extend(verify_class(df, *cfg))

    out_df = pd.DataFrame(all_rows)
    out_path = LOG_DIR / "stage4_6class_merged_verification.csv"
    out_df.to_csv(out_path, index=False)

    # FDR + Bonferroni 校正
    active = out_df[~out_df["skipped"].fillna(False)].copy()
    bh_thr = bh_correct(active["p_boot"].tolist(), FDR_ALPHA)
    active["L1"] = True
    active["L2"] = (active["ci_lo"] > 0) | (active["ci_hi"] < 0)
    active["L3_fdr"] = active["p_boot"] <= bh_thr
    active["L3_bonf6"] = active["p_boot"] < BONF_ALPHA
    active["L4"] = active["p_cf"] < CF_ALPHA
    active["L7"] = active["time_stab"] <= TIME_STAB_LINE

    active["hard_pass_fdr"] = active["L1"] & active["L2"] & active["L3_fdr"] & active["L4"]
    active["hard_pass_bonf"] = active["L1"] & active["L2"] & active["L3_bonf6"] & active["L4"]

    def grade_fdr(r):
        if not r["hard_pass_fdr"]:
            return "fail"
        return "A" if r["L7"] else "A-"
    def grade_bonf(r):
        if not r["hard_pass_bonf"]:
            return "fail"
        return "A" if r["L7"] else "A-"

    active["grade_fdr"] = active.apply(grade_fdr, axis=1)
    active["grade_bonf"] = active.apply(grade_bonf, axis=1)

    print(f"\nBH FDR 阈值 p ≤ {bh_thr:.5f}")
    print(f"Bonferroni family=6 阈值 p < {BONF_ALPHA:.5f}")

    print("\n" + "=" * 100)
    print("6 类合并版 · 全部结果（分方向 × period）")
    print("=" * 100)
    print(f"{'class·period':>28s} {'dir':>5s} {'n':>4s} {'nday':>4s} "
          f"{'mean':>7s} {'CI 95%':>18s} {'p_boot':>8s} "
          f"{'品保':>5s} {'IR':>6s} {'时稳':>5s} "
          f"{'L2':>3s} {'L3F':>4s} {'L3B':>4s} {'L4':>3s} {'L7':>3s} "
          f"{'FDR':>5s} {'Bonf6':>6s}")
    print("-" * 145)
    for _, r in active.sort_values(["direction", "class", "period"]).iterrows():
        key = f"{r['class']}·{r['period']}"
        ci = f"[{r['ci_lo']:>+6.1f},{r['ci_hi']:>+6.1f}]"
        sr_str = f"{r['symbol_retain']:.0%}" if not np.isnan(r['symbol_retain']) else "-"
        ir_str = f"{r['ir']:+.2f}" if not np.isnan(r['ir']) else "-"
        ts_str = f"{r['time_stab']:.2f}" if not np.isnan(r['time_stab']) else "-"
        m_fdr = "🟢" if r["grade_fdr"] == "A" else "🟡" if r["grade_fdr"] == "A-" else "🔴"
        m_bonf = "🟢" if r["grade_bonf"] == "A" else "🟡" if r["grade_bonf"] == "A-" else "🔴"
        print(f"{key:>28s} {r['direction']:>5s} {int(r['n']):>4d} {int(r['n_days']):>4d} "
              f"{r['mean_bps']:>+7.1f} {ci:>18s} {r['p_boot']:>8.5f} "
              f"{sr_str:>5s} {ir_str:>6s} {ts_str:>5s} "
              f"{'+' if r['L2'] else '-':>3s} {'+' if r['L3_fdr'] else '-':>4s} "
              f"{'+' if r['L3_bonf6'] else '-':>4s} {'+' if r['L4'] else '-':>3s} "
              f"{'+' if r['L7'] else '-':>3s} "
              f"{m_fdr}{r['grade_fdr']:>3s} {m_bonf}{r['grade_bonf']:>4s}")

    print("\n" + "=" * 100)
    print("汇总 · 通过数量对比")
    print("=" * 100)
    print("\n【6 类合并 · FDR α=0.05】")
    print(active.groupby("grade_fdr").size())
    print("\n【6 类合并 · Bonferroni family=6 · α=0.0083】")
    print(active.groupby("grade_bonf").size())

    print(f"\n输出：{out_path}")


if __name__ == "__main__":
    main()
