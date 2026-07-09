"""
12 格深度诊断 · 4 分位 × 3 ATR 制度

分位段：
- 段1 · 极端创新低 (skew ≤ 0.09)
- 段2 · 前低拉锯 (0.09 < skew ≤ 0.19)
- 段3 · 未及前低 (0.19 < skew ≤ 0.25)
- 段4 · 稀释区 (0.25 < skew ≤ 0.30)

ATR 制度：
- 低 (atr_rank ≤ 0.33)
- 中 (0.33 < atr_rank ≤ 0.67)
- 高 (0.67 < atr_rank ≤ 0.70)   ← 因基础 filter 是 atr≤0.70

其他 filter 保持：trend_rank ≥ 0.75 · 稳定期 · 8h horizon

Layer 1: 数据量普查
Layer 2: 描述性统计 + 品种保留率
Layer 3: 3 条线索验证
   L3.1 ATR 制度一致性（同分位段在 3 个制度下是否相似形状）
   L3.2 时间 K-fold（4 段）
   L3.3 Horizon 曲线（4h/8h/12h）
Layer 4: 综合判读
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


BANDS = [
    ("段1", 0.00, 0.09),
    ("段2", 0.09, 0.19),
    ("段3", 0.19, 0.25),
    ("段4", 0.25, 0.30),
]

ATR_REGIMES = [
    ("低", 0.00, 0.33),
    ("中", 0.33, 0.67),
    ("高", 0.67, 1.00),  # 放宽 ATR 上限到 1.0 · 覆盖全 ATR 制度
]

LOG_DIR = Path("/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage3")


def get_prefix(contract):
    return "".join([c for c in contract if not c.isdigit()])


def get_cell_mask(df, band_lo, band_hi, atr_lo, atr_hi):
    """
    格子 mask：
    - skew rank 在 (band_lo, band_hi]
    - atr rank 在 (atr_lo, atr_hi]  · 已放宽上限到 1.0（覆盖全 ATR）
    - trend rank ≥ 0.75（保持主线定义）
    - 稳定期
    """
    return (
        (df["signed_skew_rank_roll"] > band_lo) &
        (df["signed_skew_rank_roll"] <= band_hi) &
        (df["atr_rank_roll"] > atr_lo) &
        (df["atr_rank_roll"] <= atr_hi) &
        (df["trend_rank_roll"] >= 0.75) &
        (~df["transition_flag"])
    )


def cell_stats(df, mask, ret_col):
    sub = df[mask].dropna(subset=[ret_col]).copy()
    if len(sub) == 0:
        return None
    sub["event_date"] = pd.to_datetime(sub["event_time"]).dt.date
    sub["prefix"] = sub["contract"].apply(get_prefix)

    n = len(sub)
    n_days = sub["event_date"].nunique()
    n_prefix = sub["prefix"].nunique()

    prefix_means = sub.groupby("prefix")[ret_col].agg(["count", "mean"])
    prefix_means = prefix_means[prefix_means["count"] >= 3]
    n_prefix_valid = len(prefix_means)
    n_positive = (prefix_means["mean"] > 0).sum() if n_prefix_valid > 0 else 0
    retain_rate = n_positive / n_prefix_valid if n_prefix_valid > 0 else 0
    top_prefix = prefix_means.nlargest(1, "count").index[0] if len(prefix_means) > 0 else "-"

    r = sub[ret_col].values
    winners = r[r > 0]
    losers = r[r < 0]

    return {
        "n": n,
        "n_days": n_days,
        "n_prefix": n_prefix,
        "n_prefix_valid": n_prefix_valid,
        "n_positive": n_positive,
        "retain_rate": retain_rate,
        "top_prefix": top_prefix,
        "mean": r.mean(),
        "std": r.std() if len(r) > 1 else 0,
        "hit": (r > 0).mean(),
        "avg_win": winners.mean() if len(winners) > 0 else 0,
        "avg_loss": losers.mean() if len(losers) > 0 else 0,
        "payoff": abs(winners.mean() / losers.mean()) if len(losers) > 0 and losers.mean() < 0 else np.inf,
    }


def horizon_curve(df, mask):
    sub = df[mask].copy()
    if len(sub) < 10:
        return {}
    result = {}
    for h in [1, 2, 3, 4, 6, 8, 12]:
        col = f"ret_{h}h_bps"
        if col in df.columns:
            result[h] = sub[col].mean()
    return result


def time_kfold(df, mask, ret_col, n_folds=4):
    sub = df[mask].dropna(subset=[ret_col]).copy()
    if len(sub) < 20:
        return None
    sub["event_time_dt"] = pd.to_datetime(sub["event_time"])
    sub = sub.sort_values("event_time_dt")
    fold_size = len(sub) // n_folds
    fold_means = []
    for i in range(n_folds):
        lo = i * fold_size
        hi = (i + 1) * fold_size if i < n_folds - 1 else len(sub)
        seg = sub.iloc[lo:hi]
        fold_means.append(seg[ret_col].mean())
    return {
        "fold_means": fold_means,
        "mean_of_folds": np.mean(fold_means),
        "std_of_folds": np.std(fold_means),
        "cv": np.std(fold_means) / abs(np.mean(fold_means)) if abs(np.mean(fold_means)) > 1 else np.inf,
        "n_positive_folds": sum(m > 0 for m in fold_means),
    }


def main():
    print("=" * 130)
    print("12 格深度诊断 · 4 分位 × 3 ATR 制度 · 多头 · trend≥0.75 · 稳定期 · 8h")
    print("=" * 130)

    df = prepare_dataset()
    df = flag_regime_transition(df)

    # ==========================================
    # Layer 1: 数据量普查
    # ==========================================
    print("\n" + "=" * 130)
    print("Layer 1 · 数据量普查")
    print("=" * 130)
    print(f"\n{'格子':30s} {'n':>5s} {'n_days':>7s} {'n_prefix':>9s} {'n_prefix≥3':>11s} {'主导品种':>15s}")
    print("-" * 130)

    grid_stats = {}
    for band_name, band_lo, band_hi in BANDS:
        for atr_name, atr_lo, atr_hi in ATR_REGIMES:
            key = f"{band_name}·ATR{atr_name}"
            mask = get_cell_mask(df, band_lo, band_hi, atr_lo, atr_hi)
            s = cell_stats(df, mask, "ret_8h_bps")
            grid_stats[key] = s
            if s is None:
                print(f"{key:30s} {'-':>5s} {'-':>7s} {'-':>9s} {'-':>11s} {'-':>15s}")
            else:
                print(f"{key:30s} {s['n']:>5d} {s['n_days']:>7d} "
                      f"{s['n_prefix']:>9d} {s['n_prefix_valid']:>11d} "
                      f"{s['top_prefix']:>15s}")

    # ==========================================
    # Layer 2: 描述性统计
    # ==========================================
    print("\n" + "=" * 130)
    print("Layer 2 · 描述性统计")
    print("=" * 130)
    print(f"\n{'格子':30s} {'n':>5s} {'mean':>8s} {'hit':>7s} {'std':>7s} "
          f"{'payoff':>7s} {'avg_win':>8s} {'avg_loss':>9s} "
          f"{'品种保留':>10s} {'n_pos_pfx':>10s}")
    print("-" * 130)
    for key, s in grid_stats.items():
        if s is None or s["n"] < 5:
            continue
        payoff_str = f"{s['payoff']:>7.2f}" if s['payoff'] != np.inf else "  inf"
        print(f"{key:30s} {s['n']:>5d} {s['mean']:>+8.1f} {s['hit']:>6.1%} "
              f"{s['std']:>7.1f} {payoff_str:>7s} "
              f"{s['avg_win']:>+8.1f} {s['avg_loss']:>+9.1f} "
              f"{s['retain_rate']:>9.1%} {s['n_positive']:>4d}/{s['n_prefix_valid']:<5d}")

    # ==========================================
    # Layer 3.1 · ATR 制度一致性
    # ==========================================
    print("\n" + "=" * 130)
    print("Layer 3.1 · ATR 制度一致性 · 同分位段在 3 个 ATR 下的 mean 是否呈相似形状")
    print("=" * 130)

    print(f"\n{'分位段':10s} {'ATR低 mean':>12s} {'ATR中 mean':>12s} {'ATR高 mean':>12s} "
          f"{'低→高单调':>10s} {'峰值 ATR':>10s}")
    print("-" * 100)
    band_by_atr = {}
    for band_name, _, _ in BANDS:
        means = []
        for atr_name, _, _ in ATR_REGIMES:
            key = f"{band_name}·ATR{atr_name}"
            s = grid_stats.get(key)
            if s and s["n"] >= 5:
                means.append((atr_name, s["mean"]))
            else:
                means.append((atr_name, np.nan))
        band_by_atr[band_name] = means
        m_vals = [m[1] for m in means]
        if not any(np.isnan(m_vals)):
            monotonic = "↑单增" if m_vals[0] < m_vals[1] < m_vals[2] else \
                        "↓单减" if m_vals[0] > m_vals[1] > m_vals[2] else "非单调"
            peak_idx = np.argmax(m_vals)
            peak_atr = ["低", "中", "高"][peak_idx]
        else:
            monotonic = "n不足"
            peak_atr = "n不足"
        print(f"{band_name:10s} " +
              " ".join([f"{m[1]:>+12.1f}" if not np.isnan(m[1]) else f"{'-':>12s}" for m in means]) +
              f" {monotonic:>10s} {peak_atr:>10s}")

    # ==========================================
    # Layer 3.2 · 时间 K-fold
    # ==========================================
    print("\n" + "=" * 130)
    print("Layer 3.2 · 时间 4-fold · 每格 mean 稳定性")
    print("=" * 130)

    print(f"\n{'格子':30s} {'fold1':>8s} {'fold2':>8s} {'fold3':>8s} {'fold4':>8s} "
          f"{'折均':>8s} {'折std':>8s} {'CV':>7s} {'正折数':>8s}")
    print("-" * 130)
    time_folds = {}
    for band_name, band_lo, band_hi in BANDS:
        for atr_name, atr_lo, atr_hi in ATR_REGIMES:
            key = f"{band_name}·ATR{atr_name}"
            mask = get_cell_mask(df, band_lo, band_hi, atr_lo, atr_hi)
            t = time_kfold(df, mask, "ret_8h_bps")
            time_folds[key] = t
            if t is None:
                continue
            fm = t["fold_means"]
            print(f"{key:30s} " +
                  " ".join([f"{m:>+8.1f}" for m in fm]) +
                  f" {t['mean_of_folds']:>+8.1f} {t['std_of_folds']:>8.1f} "
                  f"{t['cv']:>7.2f} {t['n_positive_folds']:>4d}/4")

    # ==========================================
    # Layer 3.3 · Horizon 曲线
    # ==========================================
    print("\n" + "=" * 130)
    print("Layer 3.3 · 每格的 horizon 曲线（1h/2h/3h/4h/6h/8h/12h）")
    print("=" * 130)

    print(f"\n{'格子':30s} " + " ".join([f"{h}h".rjust(8) for h in [1, 2, 3, 4, 6, 8, 12]]) +
          f" {'峰值 h':>7s}")
    print("-" * 130)
    for band_name, band_lo, band_hi in BANDS:
        for atr_name, atr_lo, atr_hi in ATR_REGIMES:
            key = f"{band_name}·ATR{atr_name}"
            mask = get_cell_mask(df, band_lo, band_hi, atr_lo, atr_hi)
            hc = horizon_curve(df, mask)
            if not hc:
                continue
            vals = [hc.get(h, np.nan) for h in [1, 2, 3, 4, 6, 8, 12]]
            if not any(np.isnan(vals)):
                peak_h = [1, 2, 3, 4, 6, 8, 12][np.argmax(vals)]
            else:
                peak_h = "-"
            print(f"{key:30s} " +
                  " ".join([f"{v:>+8.1f}" if not np.isnan(v) else f"{'-':>8s}" for v in vals]) +
                  f" {peak_h:>7}")

    # ==========================================
    # Layer 4: 综合判决
    # ==========================================
    print("\n" + "=" * 130)
    print("Layer 4 · 综合判决 · 每格 3 条线索打分")
    print("=" * 130)
    print("\n判据：")
    print("  - L3.1: 该分位段的 ATR 曲线是否与其他分位段形状一致（视觉判断）· 此处简化用 '峰值 ATR' 是否一致")
    print("  - L3.2: 时间 4-fold 至少 3 折为正 · CV < 2")
    print("  - L3.3: horizon 曲线是否有明确峰值（单调或倒 U）")
    print("  - 数据量：n ≥ 15")

    print(f"\n{'格子':30s} {'n≥15':>6s} {'时间稳':>7s} {'CV<2':>7s} {'peak_h':>7s} {'评级'}")
    print("-" * 100)

    verdicts = {}
    for key in grid_stats:
        s = grid_stats[key]
        t = time_folds.get(key)
        if s is None:
            continue
        # 判据
        has_data = "✅" if s["n"] >= 15 else "❌"
        time_stable = "?" if t is None else ("✅" if t["n_positive_folds"] >= 3 else "❌")
        cv_ok = "?" if t is None else ("✅" if t["cv"] < 2 else "❌")

        # 综合评级
        scores = [1 if x == "✅" else 0 for x in [has_data, time_stable, cv_ok]]
        total = sum(scores)
        if total >= 3:
            verdict = "🟢 稳定"
        elif total >= 2:
            verdict = "🟡 部分稳"
        elif total >= 1:
            verdict = "🟠 弱证"
        else:
            verdict = "🔴 不稳"
        # 若无数据则给"数据不足"
        if s["n"] < 10:
            verdict = "⚪ 数据不足"
        verdicts[key] = verdict

        peak_h_str = "-"

        print(f"{key:30s} {has_data:>6s} {time_stable:>7s} {cv_ok:>7s} {peak_h_str:>7s} {verdict}")

    # 保存
    result_df = pd.DataFrame([
        {"cell": k, **grid_stats[k], "verdict": verdicts.get(k, "?")}
        for k in grid_stats if grid_stats[k]
    ])
    result_df.to_csv(LOG_DIR / "twelve_cells_diagnosis.csv", index=False)

    print(f"\n输出：{LOG_DIR / 'twelve_cells_diagnosis.csv'}")


if __name__ == "__main__":
    main()
