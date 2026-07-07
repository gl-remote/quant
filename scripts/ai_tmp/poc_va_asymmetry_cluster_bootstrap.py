"""
文件级元信息：
- 创建背景：poc-va-asymmetry 主线 W1 × A3_skew × ret_8h 已识别方向信号
  （pooled DN mean +14~+32 bps）。需要在 dedup_8h 事件集上做 cluster
  bootstrap（按 contract 聚类）验证 pooled 显著性，避免"事件非独立性"
  导致的高估显著性。
- 用途：
  (1) 对 k ∈ {0.5, 1.0, 1.5, 2.0} 四档 σ 阈值 · dedup_8h · DN 组
  (2) 按 contract 聚类重抽样 5000 次 · 计算 pooled mean_ret_8h 的
      95% CI 与双侧 p 值（H0: mean=0）
  (3) 输出对照表：n / mean / CI / p / 是否显著
- 注意事项：临时脚本；用 W1 × A3_skew，未来窗口 8h（沿用 long_events.csv）
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage1"
)
LONG_PATH = LOG_DIR / "long_events.csv"

WINDOW = "W1"
METRIC = "A3_skew"
HORIZON = "ret_8h"
K_LEVELS = [0.5, 1.0, 1.5, 2.0]
DEDUP_GAP_HOURS = 8.0
BOOTSTRAP_N = 5000
RNG_SEED = 20260707


def dedup_gap(events: pd.DataFrame, min_gap_h: float) -> pd.DataFrame:
    ev = events.sort_values("event_time").reset_index(drop=True)
    kept = []
    last = None
    for i, row in ev.iterrows():
        if last is None or (row["event_time"] - last).total_seconds() / 3600 >= min_gap_h:
            kept.append(i)
            last = row["event_time"]
    return ev.loc[kept]


def cluster_bootstrap_mean(
    events_by_contract: dict[str, np.ndarray],
    n_boot: int = BOOTSTRAP_N,
    rng: np.random.Generator | None = None,
) -> tuple[float, float, float, float]:
    """按 contract 聚类重抽样，返回 (obs_mean_bps, ci_lo, ci_hi, p_two)。

    - 每次抽样：从合约列表中有放回抽 N 个合约（N = 合约总数）
    - 把这些合约的所有事件 pool 起来算 mean
    - 5000 次 → 得到 mean 分布，取 2.5%/97.5% 分位
    """
    if rng is None:
        rng = np.random.default_rng(RNG_SEED)
    contracts = sorted(events_by_contract.keys())
    n_clusters = len(contracts)
    if n_clusters < 2:
        return float("nan"), float("nan"), float("nan"), float("nan")

    # 观测 mean
    all_events = np.concatenate([events_by_contract[c] for c in contracts])
    obs_mean = float(all_events.mean()) * 1e4

    # bootstrap
    boot = np.empty(n_boot, dtype=np.float64)
    idx = rng.integers(0, n_clusters, size=(n_boot, n_clusters))
    for i in range(n_boot):
        picked = [contracts[j] for j in idx[i]]
        pooled = np.concatenate([events_by_contract[c] for c in picked])
        boot[i] = pooled.mean() * 1e4
    ci_lo, ci_hi = np.percentile(boot, [2.5, 97.5])
    p_gt = float(np.mean(boot > 0))
    p_lt = float(np.mean(boot < 0))
    p_two = 2.0 * min(p_gt, p_lt)
    return obs_mean, float(ci_lo), float(ci_hi), p_two


def main() -> None:
    df = pd.read_csv(LONG_PATH)
    df["event_time"] = pd.to_datetime(df["event_time"])
    sub = df[df["window"] == WINDOW].copy()
    contracts = sorted(sub["contract"].unique())

    print(f"=== cluster bootstrap (按 contract 聚类 × 5000 次) · W1 × A3_skew · dedup_8h ===\n")
    print(f"{'k':>5s} {'thresh':>8s}  {'n_events':>9s} {'n_contracts':>12s}  "
          f"{'obs_mean bps':>13s} {'ci_lo':>8s} {'ci_hi':>8s} {'p_two':>8s} {'sig?':>6s}")
    print("-" * 90)

    rows: list[dict] = []

    # 全 events baseline · 无阈值
    all_baseline_by_c = {
        c: sub[sub["contract"] == c][HORIZON].dropna().to_numpy()
        for c in contracts
    }
    b_mean, b_lo, b_hi, b_p = cluster_bootstrap_mean(all_baseline_by_c)
    n_baseline = sum(len(v) for v in all_baseline_by_c.values())
    print(f"{'baseline':>5s} {'-':>8s}  {n_baseline:>9d} {len(contracts):>12d}  "
          f"{b_mean:>+13.3f} {b_lo:>+8.3f} {b_hi:>+8.3f} {b_p:>8.4f} "
          f"{'✗' if b_p > 0.05 else '✓':>6s}")

    for k in K_LEVELS:
        events_by_c: dict[str, np.ndarray] = {}
        for c in contracts:
            g = sub[sub["contract"] == c].copy()
            std_c = g[METRIC].std()
            thr = -k * std_c
            dn = g[g[METRIC] <= thr]
            dn = dedup_gap(dn, DEDUP_GAP_HOURS)
            arr = dn[HORIZON].dropna().to_numpy()
            if len(arr) > 0:
                events_by_c[c] = arr

        mean, ci_lo, ci_hi, p_two = cluster_bootstrap_mean(events_by_c)
        n_events = sum(len(v) for v in events_by_c.values())
        n_used = len(events_by_c)
        # 用 pool 均值算大致阈值范围（每合约 σ 不同，只作参考）
        pooled_std = sub[METRIC].std()
        thresh_ref = -k * pooled_std
        sig = "✓" if (p_two < 0.05 and (ci_lo > 0 or ci_hi < 0)) else "✗"
        print(f"{k:>5.1f} {thresh_ref:>+8.3f}  {n_events:>9d} {n_used:>12d}  "
              f"{mean:>+13.3f} {ci_lo:>+8.3f} {ci_hi:>+8.3f} {p_two:>8.4f} {sig:>6s}")
        rows.append({
            "k_sigma": k,
            "thresh_ref_pooled": thresh_ref,
            "n_events": n_events,
            "n_contracts": n_used,
            "obs_mean_bps": mean,
            "ci_lo_bps": ci_lo,
            "ci_hi_bps": ci_hi,
            "p_two": p_two,
            "significant_ci_excludes_0": (ci_lo > 0 or ci_hi < 0),
        })

    result = pd.DataFrame(rows)
    out_path = LOG_DIR / "cluster_bootstrap_significance.csv"
    result.to_csv(out_path, index=False)
    print(f"\n判据：p_two < 0.05 AND CI 排除 0 → 信号统计显著（cluster 聚类下）")
    print(f"Output: {out_path}")


if __name__ == "__main__":
    main()
