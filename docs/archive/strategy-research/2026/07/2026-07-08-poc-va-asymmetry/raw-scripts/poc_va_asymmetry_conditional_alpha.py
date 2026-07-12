"""
文件级元信息：
- 创建背景：反向合约诊断显示 DN mean 与合约样本期整体趋势相关。需要用
  两种方式量化"条件 alpha"假设：
    方式 A · 按合约分组：10 合约 (baseline_mean, DN_mean) 点对相关性
    方式 B · 时段内分组：每合约切成滑动/固定段，每段算段内趋势 vs 段内 DN mean
  两种方式一起验证"信号强度随大行情方向变化"这个假设
- 用途：读 long_events.csv → W1 × A3_skew × k=1.5σ × dedup_8h
- 注意事项：ret_8h 单位 bps
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
SEGMENT_SIZE_DAYS = 15  # 方式 B 每段大小


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
    """按合约分组：(baseline_mean, DN_mean) 相关性。"""
    print("\n" + "=" * 90)
    print("方式 A · 按合约分组")
    print("=" * 90)

    rows = []
    for c, g in long_df[long_df["window"] == WINDOW].groupby("contract"):
        g = g.copy()
        g["event_time"] = pd.to_datetime(g["event_time"])
        skew = g[METRIC].dropna()
        std_c = skew.std()
        baseline_ret = g["ret_8h"].dropna() * 1e4
        dn_thr = -K_SIGMA * std_c
        dn = g[g[METRIC] <= dn_thr]
        dn_dedup = dedup_gap(dn, DEDUP_GAP_HOURS)
        r_dn = dn_dedup["ret_8h"].dropna() * 1e4
        if len(r_dn) < 3:
            continue
        rows.append({
            "contract": c,
            "n_baseline": len(baseline_ret),
            "baseline_mean_bps": baseline_ret.mean(),
            "n_dn_dedup": len(r_dn),
            "dn_mean_bps": r_dn.mean(),
            "dn_median_bps": r_dn.median(),
            "dn_hit": (r_dn > 0).mean(),
        })

    df = pd.DataFrame(rows).sort_values("baseline_mean_bps")
    print(f"\n{'contract':16s} {'n_base':>6s} {'baseline':>10s} {'n_dn':>5s} "
          f"{'dn_mean':>9s} {'dn_median':>10s} {'dn_hit':>7s}")
    for _, r in df.iterrows():
        print(f"{r['contract']:16s} {r['n_baseline']:>6d} {r['baseline_mean_bps']:>+10.2f} "
              f"{r['n_dn_dedup']:>5d} {r['dn_mean_bps']:>+9.2f} "
              f"{r['dn_median_bps']:>+10.2f} {r['dn_hit']:>7.1%}")

    # 相关系数
    x = df["baseline_mean_bps"].to_numpy()
    y = df["dn_mean_bps"].to_numpy()
    pear = stats.pearsonr(x, y)
    spear = stats.spearmanr(x, y)
    print(f"\n(baseline_mean, dn_mean) 相关系数:")
    print(f"  Pearson  r={pear.statistic:+.3f}  p={pear.pvalue:.4f}")
    print(f"  Spearman r={spear.statistic:+.3f}  p={spear.pvalue:.4f}")

    y2 = df["dn_median_bps"].to_numpy()
    pear2 = stats.pearsonr(x, y2)
    spear2 = stats.spearmanr(x, y2)
    print(f"\n(baseline_mean, dn_median) 相关系数:")
    print(f"  Pearson  r={pear2.statistic:+.3f}  p={pear2.pvalue:.4f}")
    print(f"  Spearman r={spear2.statistic:+.3f}  p={spear2.pvalue:.4f}")

    # 线性回归
    slope, intercept, r_val, p_val, se = stats.linregress(x, y)
    print(f"\n线性回归: dn_mean = {slope:+.3f} × baseline_mean + {intercept:+.2f}")
    print(f"  R² = {r_val**2:.3f}  p_slope = {p_val:.4f}")
    print(f"  斜率含义: 大行情每 +10 bps, DN mean 变化 {slope*10:+.2f} bps")

    return df


def method_b(long_df: pd.DataFrame) -> pd.DataFrame:
    """时段内分组：每合约切成 SEGMENT_SIZE_DAYS 天一段"""
    print("\n\n" + "=" * 90)
    print(f"方式 B · 每合约切成 {SEGMENT_SIZE_DAYS} 天一段")
    print("=" * 90)

    rows = []
    for c, g in long_df[long_df["window"] == WINDOW].groupby("contract"):
        g = g.copy()
        g["event_time"] = pd.to_datetime(g["event_time"])
        g["date"] = g["event_time"].dt.date
        std_c = g[METRIC].std()
        dn_thr = -K_SIGMA * std_c

        # 按日期分段
        all_dates = sorted(g["date"].unique())
        n_segments = max(1, len(all_dates) // SEGMENT_SIZE_DAYS)
        segments = np.array_split(all_dates, n_segments)

        for seg_idx, seg_dates in enumerate(segments):
            seg_set = set(seg_dates)
            seg_events = g[g["date"].isin(seg_set)].copy()
            if len(seg_events) < 5:
                continue

            seg_baseline_ret = seg_events["ret_8h"].dropna() * 1e4
            seg_dn = seg_events[seg_events[METRIC] <= dn_thr]
            seg_dn_dedup = dedup_gap(seg_dn, DEDUP_GAP_HOURS)
            seg_dn_ret = seg_dn_dedup["ret_8h"].dropna() * 1e4

            rows.append({
                "contract": c,
                "seg_idx": seg_idx,
                "seg_start": min(seg_dates),
                "seg_end": max(seg_dates),
                "n_days": len(seg_dates),
                "seg_baseline_mean_bps": seg_baseline_ret.mean(),
                "n_dn_dedup": len(seg_dn_ret),
                "seg_dn_mean_bps": seg_dn_ret.mean() if len(seg_dn_ret) else np.nan,
            })

    df = pd.DataFrame(rows)
    df_valid = df.dropna(subset=["seg_dn_mean_bps"])
    df_valid = df_valid[df_valid["n_dn_dedup"] >= 2]  # 至少 2 个 DN 事件的段

    print(f"\n总段数: {len(df)}, 有效段（n_dn>=2）: {len(df_valid)}")
    print(f"\n{'contract':16s} {'seg':>3s} {'start':>10s} → {'end':>10s} "
          f"{'base_mean':>10s} {'n_dn':>5s} {'dn_mean':>9s}")
    for _, r in df_valid.iterrows():
        print(f"{r['contract']:16s} {r['seg_idx']:>3d} {str(r['seg_start']):>10s} → "
              f"{str(r['seg_end']):>10s} {r['seg_baseline_mean_bps']:>+10.2f} "
              f"{r['n_dn_dedup']:>5d} {r['seg_dn_mean_bps']:>+9.2f}")

    x = df_valid["seg_baseline_mean_bps"].to_numpy()
    y = df_valid["seg_dn_mean_bps"].to_numpy()
    pear = stats.pearsonr(x, y)
    spear = stats.spearmanr(x, y)
    print(f"\n(seg_baseline_mean, seg_dn_mean) 相关系数:")
    print(f"  Pearson  r={pear.statistic:+.3f}  p={pear.pvalue:.4f}")
    print(f"  Spearman r={spear.statistic:+.3f}  p={spear.pvalue:.4f}")

    # 分箱看趋势
    df_valid = df_valid.sort_values("seg_baseline_mean_bps").reset_index(drop=True)
    n_bins = 3
    df_valid["bucket"] = pd.qcut(df_valid["seg_baseline_mean_bps"], n_bins,
                                  labels=[f"Q{i+1}" for i in range(n_bins)])
    print(f"\n按段的 baseline_mean 分 3 档（趋势方向）:")
    print(f"{'bucket':10s} {'n_seg':>5s} {'base_mean_avg':>15s} {'dn_mean_avg':>15s} "
          f"{'dn_mean_std':>15s}")
    for b in ["Q1", "Q2", "Q3"]:
        sub = df_valid[df_valid["bucket"] == b]
        if len(sub) == 0:
            continue
        # 按 n_dn 加权 dn_mean 更准
        w_dn = np.average(sub["seg_dn_mean_bps"], weights=sub["n_dn_dedup"])
        print(f"{b:10s} {len(sub):>5d} {sub['seg_baseline_mean_bps'].mean():>+15.2f} "
              f"{w_dn:>+15.2f} {sub['seg_dn_mean_bps'].std():>15.2f}")

    return df_valid


def main() -> None:
    long_df = pd.read_csv(LONG_PATH)

    df_a = method_a(long_df)
    df_a.to_csv(LOG_DIR / "conditional_alpha_by_contract.csv", index=False)

    df_b = method_b(long_df)
    df_b.to_csv(LOG_DIR / "conditional_alpha_by_segment.csv", index=False)

    print(f"\n\nOutputs:")
    print(f"  {LOG_DIR / 'conditional_alpha_by_contract.csv'}")
    print(f"  {LOG_DIR / 'conditional_alpha_by_segment.csv'}")


if __name__ == "__main__":
    main()
