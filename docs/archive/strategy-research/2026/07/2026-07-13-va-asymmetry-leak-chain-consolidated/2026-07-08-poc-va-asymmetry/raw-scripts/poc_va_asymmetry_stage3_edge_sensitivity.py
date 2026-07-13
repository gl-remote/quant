"""
诊断边缘触发敏感性 · 量化"离散 rank"的实际不稳定性

问题 D：由于 rank 精度只有 10 档 · 边缘 event（rank 恰好接近阈值）
若下一个新 event 推入 · 可能把该 event 从触发集中挤出

诊断方式：
1. 统计 5 主线触发事件中 · 有多少是"边缘 rank"（距阈值 <0.03）
2. 模拟"扰动"：把 A3_skew ± 5% 后重新算 rank · 看多少 event 触发状态改变
3. 若边缘敏感事件 <20% · 影响可接受
4. 若边缘敏感事件 >50% · 需要缓冲区
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/gaolei/Documents/src/quant/scripts/ai_tmp")
from poc_va_asymmetry_stage2_grid_search import prepare_dataset  # noqa: E402
from poc_va_asymmetry_stage3_task3_regime_transition import flag_regime_transition  # noqa: E402

LOG_DIR = Path("/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage3")


def diagnose_edge_sensitivity(df, name, mask, ret_col, skew_thr, direction):
    """
    对每个触发 event · 计算它距离阈值的 rank 距离
    · 判断是否属于边缘敏感区
    """
    sub = df[mask].dropna(subset=[ret_col, "signed_skew_rank_roll"]).copy()

    if direction == "long":
        # 距离阈值 = 阈值 - rank · 越接近 0 越边缘
        sub["dist_to_thr"] = skew_thr - sub["signed_skew_rank_roll"]
    else:
        sub["dist_to_thr"] = sub["signed_skew_rank_roll"] - skew_thr

    # 边缘定义：距离 <= 0.03（一档 rank 变化 = 0.1 · 半档 = 0.05 · 更严格是 0.03）
    total = len(sub)
    if total == 0:
        return None

    def pct(mask):
        return 100 * mask.sum() / total

    edge_005 = sub["dist_to_thr"] <= 0.005   # 极紧边缘
    edge_003 = sub["dist_to_thr"] <= 0.03    # 边缘
    edge_005_10 = sub["dist_to_thr"] <= 0.10  # 半档内

    # 边缘 event 的 mean 是否与非边缘不同（分辨"边缘 event 是有价值还是纯噪声"）
    non_edge = sub[sub["dist_to_thr"] > 0.03]
    edge = sub[sub["dist_to_thr"] <= 0.03]

    return {
        "combo": name,
        "n_total": total,
        "n_edge_extreme": int(edge_005.sum()),
        "pct_edge_extreme": pct(edge_005),
        "n_edge": int(edge_003.sum()),
        "pct_edge": pct(edge_003),
        "n_half_bucket": int(edge_005_10.sum()),
        "pct_half_bucket": pct(edge_005_10),
        "mean_all": sub[ret_col].mean(),
        "mean_edge": edge[ret_col].mean() if len(edge) > 0 else np.nan,
        "mean_non_edge": non_edge[ret_col].mean() if len(non_edge) > 0 else np.nan,
        "hit_edge": (edge[ret_col] > 0).mean() if len(edge) > 0 else np.nan,
        "hit_non_edge": (non_edge[ret_col] > 0).mean() if len(non_edge) > 0 else np.nan,
    }


def perturbation_test(df, name, mask, mask_relaxed, ret_col, direction):
    """
    对"如果 rank 变一档"做敏感性测试：
    - 原触发集：紧阈值
    - 放宽一档触发集：宽阈值
    - 差异集：会被"下一个新 event 挤入 / 挤出"的边缘事件
    """
    strict_events = df[mask & df[ret_col].notna()]
    relaxed_events = df[mask_relaxed & df[ret_col].notna()]

    # 差异集 = 宽阈值有但紧阈值没有的 events
    strict_idx = set(strict_events.index)
    relaxed_idx = set(relaxed_events.index)
    boundary_idx = relaxed_idx - strict_idx

    boundary = df.loc[list(boundary_idx)]

    return {
        "combo": name,
        "n_strict": len(strict_events),
        "n_relaxed": len(relaxed_events),
        "n_boundary": len(boundary),
        "pct_boundary_of_strict": 100 * len(boundary) / max(1, len(strict_events)),
        "strict_mean": strict_events[ret_col].mean(),
        "relaxed_mean": relaxed_events[ret_col].mean(),
        "boundary_mean": boundary[ret_col].mean() if len(boundary) > 0 else np.nan,
        "boundary_hit": (boundary[ret_col] > 0).mean() if len(boundary) > 0 else np.nan,
    }


def main():
    print("=" * 110)
    print("问题 D · 边缘触发敏感性诊断")
    print("=" * 110)
    print("\n目的：量化'离散 rank'导致的边缘不稳定性 · 判断是否需要缓冲区\n")

    df = prepare_dataset()
    df = flag_regime_transition(df)

    signals = [
        # (name, direction, skew_thr, atr_op, atr_thr, trend_op, trend_thr, relaxed_skew_thr, ret_col)
        ("多头首选", "long", 0.10, "<=", 0.70, ">=", 0.75, 0.20, "ret_8h_bps"),
        ("多头宽松", "long", 0.30, "<=", 0.70, ">=", 0.75, 0.40, "ret_8h_bps"),
        ("空头首选", "short", 0.80, ">", 0.80, "<=", 0.20, 0.70, "short_pnl_4h_bps"),
        ("空头宽松", "short", 0.70, ">", 0.50, "<=", 0.20, 0.60, "short_pnl_4h_bps"),
        ("空头收敛", "short", 0.70, ">", 0.67, "<=", 0.20, 0.60, "short_pnl_4h_bps"),
    ]

    # 修正：空头首选实际是 skew>=0.70 atr>0.80
    signals = [
        ("多头首选", "long", 0.10, 0.70, 0.75, 0.20, "ret_8h_bps"),
        ("多头宽松", "long", 0.30, 0.70, 0.75, 0.40, "ret_8h_bps"),
        ("空头首选", "short", 0.70, 0.80, 0.20, 0.60, "short_pnl_4h_bps"),
        ("空头宽松", "short", 0.70, 0.50, 0.20, 0.60, "short_pnl_4h_bps"),
        ("空头收敛", "short", 0.70, 0.67, 0.20, 0.60, "short_pnl_4h_bps"),
    ]

    # ==============================================
    # 1. 边缘 event 占比诊断
    # ==============================================
    print("=" * 110)
    print("1. 边缘 event 占比 · 距阈值 <=0.03 = 边缘 · <=0.10 = 半档内")
    print("=" * 110)

    edge_results = []
    for name, direction, sk, at, tr, sk_relax, ret_col in signals:
        if direction == "long":
            mask = ((df["signed_skew_rank_roll"] <= sk) &
                    (df["atr_rank_roll"] <= at) &
                    (df["trend_rank_roll"] >= tr))
        else:
            mask = ((df["signed_skew_rank_roll"] >= sk) &
                    (df["atr_rank_roll"] > at) &
                    (df["trend_rank_roll"] <= tr))
        r = diagnose_edge_sensitivity(df, name, mask, ret_col, sk, direction)
        if r:
            edge_results.append(r)

    print(f"\n{'组合':10s} {'总n':>5s} {'极缘':>5s} {'%':>6s} "
          f"{'边缘':>5s} {'%':>6s} {'半档内':>7s} {'%':>6s} "
          f"{'全 mean':>8s} {'边缘 mean':>10s} {'非边缘 mean':>12s}")
    print("-" * 110)
    for r in edge_results:
        print(f"{r['combo']:10s} {r['n_total']:>5d} "
              f"{r['n_edge_extreme']:>5d} {r['pct_edge_extreme']:>5.1f}% "
              f"{r['n_edge']:>5d} {r['pct_edge']:>5.1f}% "
              f"{r['n_half_bucket']:>7d} {r['pct_half_bucket']:>5.1f}% "
              f"{r['mean_all']:>+8.1f} {r['mean_edge']:>+10.1f} {r['mean_non_edge']:>+12.1f}")

    # ==============================================
    # 2. 扰动测试 · rank 松一档时哪些 event 会加入
    # ==============================================
    print("\n" + "=" * 110)
    print("2. 阈值放宽一档的差异集分析 · 边缘 event 的 mean/hit 是否与紧集相似")
    print("=" * 110)
    print("紧阈值 vs 松阈值 · 差异集 = 松阈值有但紧阈值没有的边缘 event\n")

    perturb_results = []
    for name, direction, sk, at, tr, sk_relax, ret_col in signals:
        if direction == "long":
            mask_strict = ((df["signed_skew_rank_roll"] <= sk) &
                           (df["atr_rank_roll"] <= at) &
                           (df["trend_rank_roll"] >= tr))
            mask_relaxed = ((df["signed_skew_rank_roll"] <= sk_relax) &
                            (df["atr_rank_roll"] <= at) &
                            (df["trend_rank_roll"] >= tr))
        else:
            mask_strict = ((df["signed_skew_rank_roll"] >= sk) &
                           (df["atr_rank_roll"] > at) &
                           (df["trend_rank_roll"] <= tr))
            mask_relaxed = ((df["signed_skew_rank_roll"] >= sk_relax) &
                            (df["atr_rank_roll"] > at) &
                            (df["trend_rank_roll"] <= tr))

        r = perturbation_test(df, name, mask_strict, mask_relaxed, ret_col, direction)
        perturb_results.append(r)

    print(f"{'组合':10s} {'紧n':>5s} {'松n':>5s} {'边界n':>6s} "
          f"{'边界%':>6s} {'紧 mean':>10s} {'松 mean':>10s} {'边界 mean':>12s} {'边界 hit':>10s}")
    print("-" * 110)
    for r in perturb_results:
        print(f"{r['combo']:10s} {r['n_strict']:>5d} {r['n_relaxed']:>5d} "
              f"{r['n_boundary']:>6d} {r['pct_boundary_of_strict']:>5.1f}% "
              f"{r['strict_mean']:>+10.1f} {r['relaxed_mean']:>+10.1f} "
              f"{r['boundary_mean']:>+12.1f} {r['boundary_hit']:>9.1%}")

    # ==============================================
    # 3. 综合判读
    # ==============================================
    print("\n" + "=" * 110)
    print("综合判读")
    print("=" * 110)

    for r in edge_results:
        combo = r["combo"]
        # 找到对应扰动结果
        pt = next((p for p in perturb_results if p["combo"] == combo), None)
        print(f"\n【{combo}】")
        print(f"  边缘占比：{r['pct_edge']:.1f}%（紧边缘 <0.03）· {r['pct_half_bucket']:.1f}%（半档内 <0.10）")
        print(f"  边缘 event mean = {r['mean_edge']:+.1f} vs 非边缘 = {r['mean_non_edge']:+.1f}")

        if r["mean_edge"] < 0 and r["mean_non_edge"] > 0:
            print(f"  ⚠️  边缘 event mean 反向 · 建议放宽阈值可能挤入负事件")
        elif abs(r["mean_edge"] - r["mean_non_edge"]) / max(abs(r["mean_all"]), 1) < 0.3:
            print(f"  ✅ 边缘与非边缘 mean 相近 · 边缘不是危险区")
        else:
            print(f"  ⚠️  边缘 event 表现差异较大 · 值得关注")

        if pt and pt["n_boundary"] > 0:
            print(f"  扰动测试：放宽一档会加入 {pt['n_boundary']} 个 event · "
                  f"这些的 mean = {pt['boundary_mean']:+.1f} · hit = {pt['boundary_hit']:.1%}")
            if pt["boundary_mean"] < 0:
                print(f"  ⚠️  放宽后加入的 event 是负 mean · 紧阈值是正确的")
            elif pt["boundary_mean"] > pt["strict_mean"] * 0.7:
                print(f"  ✅ 放宽后加入的 event 也是正 mean · 边缘是安全区")


if __name__ == "__main__":
    main()
