"""
文件级元信息：
- 创建背景：洞察 G 只验证了 DN 侧（底厚→做多）的条件 alpha。UP 侧
  （顶厚→做空）只做过全环境 pooled，未验证条件性。本脚本对称于
  conditional_alpha.py，做 UP 侧的两种维度诊断。
- 用途：读 long_events.csv → W1 × A3_skew × k=1.5σ × dedup_8h × UP 侧
    方式 A · 跨合约：(baseline_mean, UP_mean) 相关性
    方式 B · 段内 15 天：(seg_baseline_mean, seg_UP_mean) 相关性
  同时输出 UP 组在 Q1 跌段的收益分布形态（是否负偏 + 厚尾 = 做空有右尾）
- 注意事项：为符合"做空视角"，报告 UP_mean 时用原始 log_ret；做空收益
  = -log_ret；单位 bps
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage1"
)
LONG_PATH = LOG_DIR / "long_events.csv"

WINDOW = "W1"
METRIC = "A3_skew"
K_SIGMA = 1.5
DEDUP_GAP_HOURS = 8.0
SEGMENT_SIZE_DAYS = 15


def dedup_gap(events: pd.DataFrame, min_gap_h: float) -> pd.DataFrame:
    ev = events.sort_values("event_time").reset_index(drop=True)
    kept = []
    last = None
    for i, row in ev.iterrows():
        if last is None or (row["event_time"] - last).total_seconds() / 3600 >= min_gap_h:
            kept.append(i)
            last = row["event_time"]
    return ev.loc[kept]


def method_a(long_df: pd.DataFrame) -> pd.DataFrame:
    """按合约分组 · UP 侧。"""
    print("\n" + "=" * 90)
    print("方式 A · 按合约分组 · UP 侧（顶厚 → 做空）")
    print("=" * 90)

    rows = []
    for c, g in long_df[long_df["window"] == WINDOW].groupby("contract"):
        g = g.copy()
        g["event_time"] = pd.to_datetime(g["event_time"])
        skew = g[METRIC].dropna()
        std_c = skew.std()
        baseline_ret = g["ret_8h"].dropna() * 1e4
        up_thr = +K_SIGMA * std_c
        up = g[g[METRIC] >= up_thr]
        up_dedup = dedup_gap(up, DEDUP_GAP_HOURS)
        r_up = up_dedup["ret_8h"].dropna() * 1e4  # UP 组的裸对数收益 bps
        if len(r_up) < 3:
            continue
        # 做空视角：short_pnl = -r_up
        rows.append({
            "contract": c,
            "n_baseline": len(baseline_ret),
            "baseline_mean_bps": baseline_ret.mean(),
            "n_up_dedup": len(r_up),
            "up_mean_bps": r_up.mean(),
            "up_median_bps": r_up.median(),
            "up_hit_neg": (r_up < 0).mean(),  # 做空视角：负收益 = 做空赚
            "short_gross_bps": -r_up.mean(),
        })

    df = pd.DataFrame(rows).sort_values("baseline_mean_bps")
    print(f"\n{'contract':16s} {'n_base':>6s} {'baseline':>10s} {'n_up':>5s} "
          f"{'up_mean':>9s} {'up_median':>10s} {'up_hit_neg':>10s} {'short_gross':>12s}")
    for _, r in df.iterrows():
        print(f"{r['contract']:16s} {r['n_baseline']:>6d} {r['baseline_mean_bps']:>+10.2f} "
              f"{r['n_up_dedup']:>5d} {r['up_mean_bps']:>+9.2f} "
              f"{r['up_median_bps']:>+10.2f} {r['up_hit_neg']:>10.1%} {r['short_gross_bps']:>+12.2f}")

    x = df["baseline_mean_bps"].to_numpy()
    y = df["up_mean_bps"].to_numpy()
    pear = stats.pearsonr(x, y)
    spear = stats.spearmanr(x, y)
    print(f"\n(baseline_mean, up_mean) 相关系数:")
    print(f"  Pearson  r={pear.statistic:+.3f}  p={pear.pvalue:.4f}")
    print(f"  Spearman r={spear.statistic:+.3f}  p={spear.pvalue:.4f}")
    print(f"  假设方向: 若 UP 侧对称有效，应该看到负相关（baseline 越跌 → UP mean 越负 → 做空越赚）")

    slope, intercept, r_val, p_val, se = stats.linregress(x, y)
    print(f"\n线性回归: up_mean = {slope:+.3f} × baseline_mean + {intercept:+.2f}")
    print(f"  R² = {r_val**2:.3f}  p_slope = {p_val:.4f}")

    return df


def method_b(long_df: pd.DataFrame) -> pd.DataFrame:
    """段内分组 · UP 侧"""
    print("\n\n" + "=" * 90)
    print(f"方式 B · 每合约切成 {SEGMENT_SIZE_DAYS} 天一段 · UP 侧")
    print("=" * 90)

    rows = []
    for c, g in long_df[long_df["window"] == WINDOW].groupby("contract"):
        g = g.copy()
        g["event_time"] = pd.to_datetime(g["event_time"])
        g["date"] = g["event_time"].dt.date
        std_c = g[METRIC].std()
        up_thr = +K_SIGMA * std_c

        all_dates = sorted(g["date"].unique())
        n_segments = max(1, len(all_dates) // SEGMENT_SIZE_DAYS)
        segments = np.array_split(all_dates, n_segments)

        for seg_idx, seg_dates in enumerate(segments):
            seg_set = set(seg_dates)
            seg_events = g[g["date"].isin(seg_set)].copy()
            if len(seg_events) < 5:
                continue

            seg_baseline_ret = seg_events["ret_8h"].dropna() * 1e4
            seg_up = seg_events[seg_events[METRIC] >= up_thr]
            seg_up_dedup = dedup_gap(seg_up, DEDUP_GAP_HOURS)
            seg_up_ret = seg_up_dedup["ret_8h"].dropna() * 1e4

            rows.append({
                "contract": c,
                "seg_idx": seg_idx,
                "seg_start": min(seg_dates),
                "seg_end": max(seg_dates),
                "n_days": len(seg_dates),
                "seg_baseline_mean_bps": seg_baseline_ret.mean(),
                "n_up_dedup": len(seg_up_ret),
                "seg_up_mean_bps": seg_up_ret.mean() if len(seg_up_ret) else np.nan,
                "seg_short_gross_bps": -seg_up_ret.mean() if len(seg_up_ret) else np.nan,
            })

    df = pd.DataFrame(rows)
    df_valid = df.dropna(subset=["seg_up_mean_bps"])
    df_valid = df_valid[df_valid["n_up_dedup"] >= 2]

    print(f"\n总段数: {len(df)}, 有效段（n_up>=2）: {len(df_valid)}")
    print(f"\n{'contract':16s} {'seg':>3s} {'start':>10s} → {'end':>10s} "
          f"{'base_mean':>10s} {'n_up':>5s} {'up_mean':>9s} {'short':>9s}")
    for _, r in df_valid.iterrows():
        print(f"{r['contract']:16s} {r['seg_idx']:>3d} {str(r['seg_start']):>10s} → "
              f"{str(r['seg_end']):>10s} {r['seg_baseline_mean_bps']:>+10.2f} "
              f"{r['n_up_dedup']:>5d} {r['seg_up_mean_bps']:>+9.2f} "
              f"{r['seg_short_gross_bps']:>+9.2f}")

    x = df_valid["seg_baseline_mean_bps"].to_numpy()
    y = df_valid["seg_up_mean_bps"].to_numpy()
    pear = stats.pearsonr(x, y)
    spear = stats.spearmanr(x, y)
    print(f"\n(seg_baseline_mean, seg_up_mean) 相关系数:")
    print(f"  Pearson  r={pear.statistic:+.3f}  p={pear.pvalue:.4f}")
    print(f"  Spearman r={spear.statistic:+.3f}  p={spear.pvalue:.4f}")

    df_valid = df_valid.sort_values("seg_baseline_mean_bps").reset_index(drop=True)
    df_valid["bucket"] = pd.qcut(df_valid["seg_baseline_mean_bps"], 3,
                                  labels=["Q1", "Q2", "Q3"])
    print(f"\n按段的 baseline_mean 分 3 档:")
    print(f"{'bucket':10s} {'n_seg':>5s} {'base_mean':>12s} {'up_mean(w)':>12s} "
          f"{'short_gross(w)':>16s} {'n_up_total':>12s}")
    for b in ["Q1", "Q2", "Q3"]:
        sub = df_valid[df_valid["bucket"] == b]
        if len(sub) == 0:
            continue
        w_up = np.average(sub["seg_up_mean_bps"], weights=sub["n_up_dedup"])
        w_short = -w_up
        n_up = int(sub["n_up_dedup"].sum())
        print(f"{b:10s} {len(sub):>5d} {sub['seg_baseline_mean_bps'].mean():>+12.2f} "
              f"{w_up:>+12.2f} {w_short:>+16.2f} {n_up:>12d}")

    return df_valid


def shape_in_q1(long_df: pd.DataFrame, df_seg: pd.DataFrame) -> None:
    """UP 组在跌段 Q1 的收益分布形态。"""
    print("\n\n" + "=" * 90)
    print("Q1 跌段中的 UP 事件收益分布形态（做空是否也是右尾长厚尾）")
    print("=" * 90)

    # 找到 Q1 段的所有 (contract, seg_start~seg_end)
    q1_segs = df_seg[df_seg["bucket"] == "Q1"][["contract", "seg_start", "seg_end"]]
    if len(q1_segs) == 0:
        print("Q1 无段。")
        return

    # 挑出这些段里的 UP 事件
    long_df = long_df.copy()
    long_df["event_time"] = pd.to_datetime(long_df["event_time"])
    long_df["date"] = long_df["event_time"].dt.date

    collected = []
    for _, seg in q1_segs.iterrows():
        c = seg["contract"]
        d0, d1 = seg["seg_start"], seg["seg_end"]
        sub = long_df[(long_df["contract"] == c) & (long_df["window"] == WINDOW) &
                      (long_df["date"] >= d0) & (long_df["date"] <= d1)]
        std_c = long_df[(long_df["contract"] == c) & (long_df["window"] == WINDOW)][METRIC].std()
        up_thr = +K_SIGMA * std_c
        up = sub[sub[METRIC] >= up_thr]
        up_dedup = dedup_gap(up, DEDUP_GAP_HOURS)
        collected.append(up_dedup)

    all_up_q1 = pd.concat(collected, ignore_index=True) if collected else pd.DataFrame()
    if len(all_up_q1) == 0:
        print("Q1 段中无 UP 事件。")
        return

    r_up = all_up_q1["ret_8h"].dropna().to_numpy() * 1e4
    r_short = -r_up  # 做空收益

    print(f"\nn = {len(r_up)}")
    print(f"\n【UP 组裸对数收益】")
    print(f"  mean:     {r_up.mean():>+8.2f} bps  (若 < 0 → 做空 gross 期望正)")
    print(f"  median:   {np.median(r_up):>+8.2f} bps")
    print(f"  std:      {r_up.std():>8.2f} bps")
    print(f"  skewness: {stats.skew(r_up):>+8.3f}  (< 0 左尾长 → 做空右尾长)")
    print(f"  kurtosis: {stats.kurtosis(r_up):>+8.3f}")

    print(f"\n【做空 pnl = -UP ret】")
    print(f"  mean short: {r_short.mean():>+8.2f} bps")
    print(f"  median:     {np.median(r_short):>+8.2f} bps")
    print(f"  hit (short win, ret<0): {(r_up < 0).mean():>7.1%}")
    win_mask = r_short > 0
    if win_mask.any():
        print(f"  avg short winner: {r_short[win_mask].mean():>+8.2f} bps")
    if (~win_mask).any():
        print(f"  avg short loser:  {r_short[~win_mask].mean():>+8.2f} bps")

    # 分位数
    print(f"\n【UP 组 log_ret 分位数】")
    for q in [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95]:
        print(f"  p{int(q*100):02d}: {np.quantile(r_up, q):>+8.2f}")

    # top / bottom 5
    r_sorted = np.sort(r_up)
    print(f"\n  bottom 5 (做空最赚): {['%+.1f' % v for v in r_sorted[:5]]}")
    print(f"  top 5    (做空最亏): {['%+.1f' % v for v in r_sorted[-5:][::-1]]}")


def main() -> None:
    long_df = pd.read_csv(LONG_PATH)

    df_a = method_a(long_df)
    df_a.to_csv(LOG_DIR / "conditional_alpha_up_by_contract.csv", index=False)

    df_b = method_b(long_df)
    df_b.to_csv(LOG_DIR / "conditional_alpha_up_by_segment.csv", index=False)

    shape_in_q1(long_df, df_b)

    print(f"\n\nOutputs:")
    print(f"  {LOG_DIR / 'conditional_alpha_up_by_contract.csv'}")
    print(f"  {LOG_DIR / 'conditional_alpha_up_by_segment.csv'}")


if __name__ == "__main__":
    main()
