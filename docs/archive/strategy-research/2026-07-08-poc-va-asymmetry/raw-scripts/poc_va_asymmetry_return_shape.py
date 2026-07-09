"""
文件级元信息：
- 创建背景：阶段 1 已确认 A3_skew × W1 × ret_8h 有方向信号。但 mean 无法
  区分"均匀小赚"与"偶尔大赚"两种分布形态。本脚本刻画 UP/DN 组的收益
  分布形态：分位数 / 偏度 / 峰度 / 累积贡献 / 命中率与平均盈亏。
- 用途：读 long_events.csv → W1 × A3_skew · dedup_8h · k=1.5×σ 阈值下
  UP 组（skew ≥ +1.5σ）与 DN 组（skew ≤ -1.5σ）分别输出：
    (1) 完整分位数 + mean + std + skewness + kurtosis
    (2) hit% × avg_win + (1-hit%) × avg_loss 分解
    (3) top N% 样本累积贡献（80/20 quantify）
    (4) 极端样本清单（top/bottom 5 事件）
  并做 UP/DN vs baseline 的分布形态对比
- 注意事项：临时脚本；ret_8h 单位 bps。
"""

from __future__ import annotations

import math
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
HORIZON = "ret_8h"
K_SIGMA = 1.5  # 主线阈值
DEDUP_GAP_HOURS = 8.0


def dedup_gap(events: pd.DataFrame, min_gap_h: float) -> pd.DataFrame:
    ev = events.sort_values("event_time").reset_index(drop=True)
    kept = []
    last = None
    for i, row in ev.iterrows():
        if last is None or (row["event_time"] - last).total_seconds() / 3600 >= min_gap_h:
            kept.append(i)
            last = row["event_time"]
    return ev.loc[kept]


def describe_group(name: str, ret_bps: np.ndarray) -> dict:
    """详细刻画一组收益分布形态。"""
    if len(ret_bps) == 0:
        return {"name": name}
    print(f"\n{'='*80}\n=== {name} · n={len(ret_bps)} ===\n{'='*80}")

    # 基本统计
    print(f"\n【基本统计】")
    print(f"  mean:     {ret_bps.mean():>+8.2f} bps")
    print(f"  median:   {np.median(ret_bps):>+8.2f} bps")
    print(f"  std:      {ret_bps.std():>8.2f} bps")
    print(f"  min/max:  {ret_bps.min():>+8.2f} / {ret_bps.max():>+8.2f} bps")
    print(f"  skewness: {stats.skew(ret_bps):>+8.3f} (>0 右尾长 · <0 左尾长)")
    print(f"  kurtosis: {stats.kurtosis(ret_bps):>+8.3f} (>0 尖峰厚尾 · <0 扁平)")

    # 分位数
    print(f"\n【分位数】")
    for q in [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95]:
        v = np.quantile(ret_bps, q)
        print(f"  p{int(q*100):02d}: {v:>+8.2f} bps")

    # 命中率 × 平均盈亏分解
    win_mask = ret_bps > 0
    n_win = int(win_mask.sum())
    n_loss = int((~win_mask).sum())
    hit = n_win / len(ret_bps) if len(ret_bps) else 0
    avg_win = ret_bps[win_mask].mean() if n_win else float("nan")
    avg_loss = ret_bps[~win_mask].mean() if n_loss else float("nan")
    payoff_ratio = abs(avg_win / avg_loss) if avg_loss != 0 and not math.isnan(avg_loss) else float("nan")
    print(f"\n【命中率 × 平均盈亏分解】")
    print(f"  hit rate:       {hit:>7.1%}  ({n_win}/{len(ret_bps)})")
    print(f"  avg winner:     {avg_win:>+8.2f} bps  ({n_win} 笔)")
    print(f"  avg loser:      {avg_loss:>+8.2f} bps  ({n_loss} 笔)")
    print(f"  payoff ratio:   {payoff_ratio:>7.2f}  (avg_win / |avg_loss|)")
    print(f"  验证 mean:      hit × avg_win + (1-hit) × avg_loss = "
          f"{hit * avg_win + (1-hit) * avg_loss:+.2f} bps")

    # top N% 累积贡献（80/20 法则）
    print(f"\n【top N% 样本累积贡献（按 |ret| 排序）】")
    abs_ret = np.abs(ret_bps)
    sorted_by_abs = np.argsort(abs_ret)[::-1]  # 从大到小
    total_abs = abs_ret.sum()
    if total_abs > 0:
        for pct in [5, 10, 20, 50]:
            k = max(1, int(len(ret_bps) * pct / 100))
            top_contribution = abs_ret[sorted_by_abs[:k]].sum() / total_abs
            top_signed_ret = ret_bps[sorted_by_abs[:k]].sum()
            print(f"  top {pct:>2d}% (n={k:>3d}) 贡献 |ret| 总和的 {top_contribution:>6.1%} "
                  f"| 有向和 = {top_signed_ret:>+9.1f} bps")

    # 分离正负样本贡献
    pos_sum = ret_bps[ret_bps > 0].sum()
    neg_sum = ret_bps[ret_bps < 0].sum()
    print(f"\n【正/负样本贡献总和】")
    print(f"  正样本收益总和: {pos_sum:>+9.1f} bps ({n_win} 笔)")
    print(f"  负样本亏损总和: {neg_sum:>+9.1f} bps ({n_loss} 笔)")
    print(f"  净和:           {pos_sum + neg_sum:>+9.1f} bps")

    # 极端事件
    print(f"\n【top/bottom 5 极端事件】")
    top5 = np.sort(ret_bps)[-5:][::-1]
    bot5 = np.sort(ret_bps)[:5]
    print(f"  top 5 (最赚):    {['%+.1f' % v for v in top5]}")
    print(f"  bottom 5 (最亏): {['%+.1f' % v for v in bot5]}")

    # 分布形态判断
    print(f"\n【分布形态判断】")
    if stats.skew(ret_bps) > 0.5:
        print(f"  ✓ 显著正偏 (skew={stats.skew(ret_bps):+.2f}) → '偶尔大赚型'（右尾长）")
    elif stats.skew(ret_bps) < -0.5:
        print(f"  ✓ 显著负偏 (skew={stats.skew(ret_bps):+.2f}) → '偶尔大亏型'（左尾长）")
    else:
        print(f"  · 分布对称 (skew={stats.skew(ret_bps):+.2f}) → 均匀型")

    if abs(stats.kurtosis(ret_bps)) > 1.0:
        if stats.kurtosis(ret_bps) > 0:
            print(f"  ✓ 尖峰厚尾 (kurt={stats.kurtosis(ret_bps):+.2f}) → 大部分时候小波动，偶尔极端事件")
        else:
            print(f"  · 分布扁平 (kurt={stats.kurtosis(ret_bps):+.2f}) → 收益均匀铺开")
    else:
        print(f"  · 峰度接近正态 (kurt={stats.kurtosis(ret_bps):+.2f})")

    return {"name": name}


def main() -> None:
    df = pd.read_csv(LONG_PATH)
    df["event_time"] = pd.to_datetime(df["event_time"])
    sub = df[df["window"] == WINDOW].copy()

    # 提取 UP / DN 组 · k=1.5×σ · dedup_8h
    up_by_c: list[pd.DataFrame] = []
    dn_by_c: list[pd.DataFrame] = []
    for c, g in sub.groupby("contract"):
        std_c = g[METRIC].std()
        up_thr = +K_SIGMA * std_c
        dn_thr = -K_SIGMA * std_c
        up = g[g[METRIC] >= up_thr]
        dn = g[g[METRIC] <= dn_thr]
        up_by_c.append(dedup_gap(up, DEDUP_GAP_HOURS))
        dn_by_c.append(dedup_gap(dn, DEDUP_GAP_HOURS))

    up_df = pd.concat(up_by_c, ignore_index=True)
    dn_df = pd.concat(dn_by_c, ignore_index=True)

    up_ret = up_df[HORIZON].dropna().to_numpy() * 1e4  # bps
    dn_ret = dn_df[HORIZON].dropna().to_numpy() * 1e4
    baseline_ret = sub[HORIZON].dropna().to_numpy() * 1e4

    describe_group(f"UP 组 (skew ≥ +{K_SIGMA}×σ, k={K_SIGMA})", up_ret)
    describe_group(f"DN 组 (skew ≤ -{K_SIGMA}×σ, k={K_SIGMA})", dn_ret)
    describe_group("全 events baseline (无阈值)", baseline_ret)

    # 对比总结
    print(f"\n{'='*80}\n=== UP vs DN vs baseline 对比总结 ===\n{'='*80}")
    print(f"{'':16s} {'n':>5s} {'mean':>8s} {'median':>8s} {'std':>8s} "
          f"{'skew':>7s} {'kurt':>7s} {'hit%':>6s} {'win/|loss|':>10s}")

    def summary_row(name: str, arr: np.ndarray) -> None:
        win_mask = arr > 0
        avg_win = arr[win_mask].mean() if win_mask.any() else float("nan")
        avg_loss = arr[~win_mask].mean() if (~win_mask).any() else float("nan")
        pr = abs(avg_win / avg_loss) if avg_loss and not math.isnan(avg_loss) else float("nan")
        print(f"{name:16s} {len(arr):>5d} {arr.mean():>+8.2f} {np.median(arr):>+8.2f} "
              f"{arr.std():>8.2f} {stats.skew(arr):>+7.3f} {stats.kurtosis(arr):>+7.3f} "
              f"{win_mask.mean():>6.1%} {pr:>10.2f}")

    summary_row("UP", up_ret)
    summary_row("DN", dn_ret)
    summary_row("baseline", baseline_ret)

    # 保存
    result_rows = [
        {"group": "UP", "n": len(up_ret), "mean_bps": up_ret.mean(),
         "median_bps": np.median(up_ret), "std_bps": up_ret.std(),
         "skewness": stats.skew(up_ret), "kurtosis": stats.kurtosis(up_ret),
         "hit_pos": (up_ret > 0).mean(),
         "avg_win_bps": up_ret[up_ret > 0].mean() if (up_ret > 0).any() else float("nan"),
         "avg_loss_bps": up_ret[up_ret <= 0].mean() if (up_ret <= 0).any() else float("nan")},
        {"group": "DN", "n": len(dn_ret), "mean_bps": dn_ret.mean(),
         "median_bps": np.median(dn_ret), "std_bps": dn_ret.std(),
         "skewness": stats.skew(dn_ret), "kurtosis": stats.kurtosis(dn_ret),
         "hit_pos": (dn_ret > 0).mean(),
         "avg_win_bps": dn_ret[dn_ret > 0].mean() if (dn_ret > 0).any() else float("nan"),
         "avg_loss_bps": dn_ret[dn_ret <= 0].mean() if (dn_ret <= 0).any() else float("nan")},
        {"group": "baseline", "n": len(baseline_ret), "mean_bps": baseline_ret.mean(),
         "median_bps": np.median(baseline_ret), "std_bps": baseline_ret.std(),
         "skewness": stats.skew(baseline_ret), "kurtosis": stats.kurtosis(baseline_ret),
         "hit_pos": (baseline_ret > 0).mean(),
         "avg_win_bps": baseline_ret[baseline_ret > 0].mean(),
         "avg_loss_bps": baseline_ret[baseline_ret <= 0].mean()},
    ]
    result = pd.DataFrame(result_rows)
    out_path = LOG_DIR / "return_distribution_shape.csv"
    result.to_csv(out_path, index=False)
    print(f"\nOutput: {out_path}")


if __name__ == "__main__":
    main()
