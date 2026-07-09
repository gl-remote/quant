"""
文件级元信息：
- 创建背景：需要判断 A3_skew 到底是"独立方向 alpha"还是"趋势搭便车"。
  三个假设：
    H1 · A3_skew 有增量 alpha：DN 事件 > 同段非 DN 事件
    H2 · 只是趋势筛选器：DN 事件集中在涨段
    H3 · 趋势本身就赚：DN mean ≈ 段内 baseline
  用同段内配对对比一次性回答。
- 用途：读 extended_long_events.csv（19 合约）
    Step 1 · 每合约切 15 天段
    Step 2 · 每段算：baseline 事件 mean / DN 事件 mean / 非 DN 事件 mean
    Step 3 · 三层判据：
      (a) DN mean vs 非 DN mean（同段配对差）
      (b) DN 事件在 Q1/Q2/Q3 的分布密度是否偏斜
      (c) 段内 shuffle 检验：把段内 skew 顺序打乱，看随机"DN 事件"的 mean
- 注意事项：这是本主题阶段 1 收尾的关键实验；ret_8h 单位 bps
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage1"
)
EVENTS_PATH = LOG_DIR / "extended_long_events.csv"

K_SIGMA = 1.5
DEDUP_GAP_HOURS = 8.0
SEGMENT_SIZE_DAYS = 15
RNG_SEED = 20260707
N_SHUFFLE = 1000


def dedup_gap(events: pd.DataFrame, min_gap_h: float) -> pd.DataFrame:
    ev = events.sort_values("event_time").reset_index(drop=True)
    kept = []
    last = None
    for i, row in ev.iterrows():
        if last is None or (row["event_time"] - last).total_seconds() / 3600 >= min_gap_h:
            kept.append(i)
            last = row["event_time"]
    return ev.loc[kept]


def paired_test(df: pd.DataFrame) -> pd.DataFrame:
    """
    对每合约 · 每段（15 天）计算：
    - baseline_mean（段内所有 events 的 mean）
    - dn_mean（段内 DN 事件 mean）
    - non_dn_mean（段内非 DN 事件 mean）
    - dn_diff = dn_mean - non_dn_mean（增量 alpha）
    """
    df = df.copy()
    df["event_time"] = pd.to_datetime(df["event_time"])
    df["date"] = df["event_time"].dt.date

    rows = []
    for c, g in df.groupby("contract"):
        skew = g["A3_skew"].dropna()
        std_c = skew.std()
        thr_dn = -K_SIGMA * std_c
        thr_up = +K_SIGMA * std_c

        # 按 15 天分段
        all_dates = sorted(g["date"].unique())
        n_seg = max(1, len(all_dates) // SEGMENT_SIZE_DAYS)
        segments = np.array_split(all_dates, n_seg)

        for seg_idx, seg_dates in enumerate(segments):
            seg_set = set(seg_dates)
            seg = g[g["date"].isin(seg_set)].copy()
            if len(seg) < 20:
                continue

            # 段内 baseline
            base_ret = seg["ret_8h"] * 1e4
            base_mean = base_ret.mean()

            # DN 事件（dedup_8h）
            dn = seg[seg["A3_skew"] <= thr_dn]
            dn_dedup = dedup_gap(dn, DEDUP_GAP_HOURS)
            dn_ret = dn_dedup["ret_8h"] * 1e4
            dn_mean = dn_ret.mean() if len(dn_ret) else np.nan

            # 非 DN 事件（skew > thr_dn 的全部事件）
            non_dn = seg[seg["A3_skew"] > thr_dn]
            non_dn_ret = non_dn["ret_8h"] * 1e4
            non_dn_mean = non_dn_ret.mean() if len(non_dn_ret) else np.nan

            # UP 事件（dedup_8h）
            up = seg[seg["A3_skew"] >= thr_up]
            up_dedup = dedup_gap(up, DEDUP_GAP_HOURS)
            up_ret = up_dedup["ret_8h"] * 1e4
            up_mean = up_ret.mean() if len(up_ret) else np.nan

            # 中段事件（|skew| < 1σ）
            mid = seg[(seg["A3_skew"] > -1.0 * std_c) & (seg["A3_skew"] < 1.0 * std_c)]
            mid_ret = mid["ret_8h"] * 1e4
            mid_mean = mid_ret.mean() if len(mid_ret) else np.nan

            rows.append({
                "contract": c,
                "seg_idx": seg_idx,
                "n_seg_events": len(seg),
                "base_mean": base_mean,
                "n_dn": len(dn_ret),
                "dn_mean": dn_mean,
                "n_non_dn": len(non_dn_ret),
                "non_dn_mean": non_dn_mean,
                "dn_diff": dn_mean - non_dn_mean if len(dn_ret) else np.nan,
                "n_up": len(up_ret),
                "up_mean": up_mean,
                "up_diff": up_mean - non_dn_mean if len(up_ret) else np.nan,
                "n_mid": len(mid_ret),
                "mid_mean": mid_mean,
            })

    return pd.DataFrame(rows)


def shuffle_test(df: pd.DataFrame, seed: int = RNG_SEED) -> None:
    """
    段内 shuffle 检验：把每段内的 skew 与 ret 独立配对打乱，重算 DN mean。
    看 1000 次随机后的 mean 分布，vs 真实 DN mean 的位置。
    如果真实 DN mean 排在随机分布的极端，说明信号真；否则 = 巧合。
    """
    print("\n\n" + "=" * 90)
    print("Shuffle 检验 · 段内随机化 · N=1000")
    print("=" * 90)
    rng = np.random.default_rng(seed)
    df = df.copy()
    df["event_time"] = pd.to_datetime(df["event_time"])
    df["date"] = df["event_time"].dt.date

    real_dn_means = []
    random_dn_means = np.zeros(N_SHUFFLE)

    # pool 每段的 (skew, ret) 对
    seg_pool = []
    for c, g in df.groupby("contract"):
        skew = g["A3_skew"].dropna()
        std_c = skew.std()
        thr_dn = -K_SIGMA * std_c
        all_dates = sorted(g["date"].unique())
        n_seg = max(1, len(all_dates) // SEGMENT_SIZE_DAYS)
        segments = np.array_split(all_dates, n_seg)
        for seg_dates in segments:
            seg = g[g["date"].isin(set(seg_dates))].copy()
            if len(seg) < 20:
                continue
            seg_pool.append({
                "skew": seg["A3_skew"].to_numpy(),
                "ret": seg["ret_8h"].to_numpy() * 1e4,
                "thr_dn": thr_dn,
            })

    # 真实 DN pooled mean
    real_all_dn = []
    for s in seg_pool:
        dn_mask = s["skew"] <= s["thr_dn"]
        real_all_dn.extend(s["ret"][dn_mask].tolist())
    real_dn_mean = float(np.mean(real_all_dn)) if real_all_dn else float("nan")
    real_n = len(real_all_dn)

    # Shuffle：每段内把 skew shuffled 后重新配对
    for i in range(N_SHUFFLE):
        rand_dn = []
        for s in seg_pool:
            perm_skew = rng.permutation(s["skew"])
            dn_mask = perm_skew <= s["thr_dn"]
            rand_dn.extend(s["ret"][dn_mask].tolist())
        random_dn_means[i] = float(np.mean(rand_dn)) if rand_dn else float("nan")

    print(f"\n真实 DN pooled mean (raw · 未 dedup):    {real_dn_mean:+.2f} bps  (n={real_n})")
    print(f"Shuffle DN mean 分布:")
    print(f"  mean:  {random_dn_means.mean():+.2f} bps  (应 ≈ 段内 baseline)")
    print(f"  std:   {random_dn_means.std():.2f} bps")
    print(f"  95% CI: [{np.quantile(random_dn_means, 0.025):+.2f}, "
          f"{np.quantile(random_dn_means, 0.975):+.2f}]")

    # 真实值在随机分布中的排位
    percentile = (random_dn_means < real_dn_mean).mean()
    print(f"\n真实 DN mean 在 shuffle 分布中的百分位: {percentile:.4f}")
    if percentile > 0.975 or percentile < 0.025:
        print(f"  ✅ 真实值在极端尾部（p_two ≈ {2*min(percentile, 1-percentile):.4f}）→ 信号真")
    else:
        print(f"  ❌ 真实值在中央 95% CI 内 → A3_skew 无独立增量")


def main() -> None:
    df = pd.read_csv(EVENTS_PATH)
    print(f"事件表: {len(df)} rows · {df['contract'].nunique()} contracts")

    result = paired_test(df)
    result.to_csv(LOG_DIR / "event_vs_nonevent.csv", index=False)

    # 汇总统计
    print("\n" + "=" * 90)
    print("同段内配对对比 · 每段的 DN 事件 vs 非 DN 事件")
    print("=" * 90)

    valid = result.dropna(subset=["dn_diff"])
    valid = valid[valid["n_dn"] >= 2]

    print(f"\n有效段数（DN 事件≥2）: {len(valid)}")
    print(f"\n{'':15s} {'mean':>10s} {'std':>10s} {'median':>10s}")
    print(f"{'base_mean':15s} {valid['base_mean'].mean():>+10.2f} "
          f"{valid['base_mean'].std():>10.2f} {valid['base_mean'].median():>+10.2f}")
    print(f"{'dn_mean':15s} {valid['dn_mean'].mean():>+10.2f} "
          f"{valid['dn_mean'].std():>10.2f} {valid['dn_mean'].median():>+10.2f}")
    print(f"{'non_dn_mean':15s} {valid['non_dn_mean'].mean():>+10.2f} "
          f"{valid['non_dn_mean'].std():>10.2f} {valid['non_dn_mean'].median():>+10.2f}")
    print(f"{'dn_diff':15s} {valid['dn_diff'].mean():>+10.2f} "
          f"{valid['dn_diff'].std():>10.2f} {valid['dn_diff'].median():>+10.2f}")
    print(f"{'mid_mean':15s} {valid['mid_mean'].mean():>+10.2f} "
          f"{valid['mid_mean'].std():>10.2f} {valid['mid_mean'].median():>+10.2f}")

    # 段内配对 t 检验：dn_diff 是否显著 != 0
    t_stat, p_val = stats.ttest_1samp(valid["dn_diff"].dropna(), 0)
    print(f"\n【配对 t 检验：dn_diff = 0 的假设】")
    print(f"  n_seg = {len(valid)}")
    print(f"  mean dn_diff = {valid['dn_diff'].mean():+.2f} bps")
    print(f"  95% CI = [{valid['dn_diff'].mean() - 1.96*valid['dn_diff'].std()/np.sqrt(len(valid)):+.2f}, "
          f"{valid['dn_diff'].mean() + 1.96*valid['dn_diff'].std()/np.sqrt(len(valid)):+.2f}]")
    print(f"  t = {t_stat:.3f}, p = {p_val:.4f}")
    if p_val < 0.05 and valid["dn_diff"].mean() > 0:
        print(f"  ✅ H1 成立 · A3_skew 有独立增量 alpha")
    elif p_val < 0.05 and valid["dn_diff"].mean() < 0:
        print(f"  ⚠️ 反向 · A3_skew 反筛（负 alpha）")
    else:
        print(f"  ❌ H2/H3 · A3_skew 无独立增量 alpha")

    # 分档看：涨段 vs 平段 vs 跌段的 dn_diff
    print(f"\n【按段 baseline 分 3 档 · dn_diff 是否随环境变化】")
    valid = valid.sort_values("base_mean").reset_index(drop=True)
    valid["bucket"] = pd.qcut(valid["base_mean"], 3, labels=["Q1_跌", "Q2_平", "Q3_涨"])
    print(f"{'bucket':10s} {'n_seg':>5s} {'base_avg':>10s} {'dn_mean':>10s} "
          f"{'non_dn':>10s} {'dn_diff':>10s} {'up_diff':>10s}")
    for b in ["Q1_跌", "Q2_平", "Q3_涨"]:
        sub = valid[valid["bucket"] == b]
        if len(sub) == 0:
            continue
        w_dn = np.average(sub["dn_mean"].dropna(),
                          weights=sub.loc[sub["dn_mean"].notna(), "n_dn"])
        w_non = np.average(sub["non_dn_mean"], weights=sub["n_non_dn"])
        w_diff = w_dn - w_non
        # up diff
        up_sub = sub.dropna(subset=["up_diff"])
        if len(up_sub) > 0:
            w_up_diff = np.average(up_sub["up_diff"],
                                    weights=up_sub["n_up"])
        else:
            w_up_diff = float("nan")
        print(f"{b:10s} {len(sub):>5d} {sub['base_mean'].mean():>+10.2f} "
              f"{w_dn:>+10.2f} {w_non:>+10.2f} {w_diff:>+10.2f} {w_up_diff:>+10.2f}")

    # Shuffle 检验
    shuffle_test(df)

    print(f"\n\nOutput: {LOG_DIR / 'event_vs_nonevent.csv'}")


if __name__ == "__main__":
    main()
