"""
文件级元信息：
- 创建背景：§5.4 v2 用 per-contract 全样本分位（q=16%）作阈值，包含未来
  函数。用户要求用两种"无未来函数"方案重验：
    (A) 固定阈值 |A3_skew| ≥ 0.45 · 无参数依赖
    (B) rolling K=200 event 的 16% 分位 · 每 t 只用过去 200 事件
- 用途：读 long_events.csv → 对每个合约按 A/B 两种规则各自筛出 DN 事件
  → 应用 dedup_8h → pooled + 分品种展示 DN mean_ret_8h · hit · n
  → 与原 in-sample q=16% dedup_8h 对比，判断信号是否被未来函数放大
- 注意事项：
  - 方案 A 阈值 0.45 是根据 §asymmetry_distribution.csv 里 W1 × A3_skew
    的 std ≈ 0.45 与 16% 分位实测 ~-0.42~-0.47 选定的近似值
  - 方案 B warm-up：前 200 事件因为没有足够历史，直接跳过（不算 DN/UP）
  - 都只对 DN 侧展开（UP 侧对称，节省输出）
"""

from __future__ import annotations

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

# 方案 A · 固定阈值
FIXED_LO = -0.45  # DN
FIXED_HI = +0.45  # UP

# 方案 B · rolling 分位
ROLLING_K = 200
ROLLING_Q = 0.16
WARMUP_MIN = 200

DEDUP_GAP_HOURS = 8.0


def dedup_gap(events: pd.DataFrame, min_gap_h: float) -> pd.DataFrame:
    events_sorted = events.sort_values("event_time").reset_index(drop=True)
    kept = []
    last = None
    for i, row in events_sorted.iterrows():
        if last is None or (row["event_time"] - last).total_seconds() / 3600 >= min_gap_h:
            kept.append(i)
            last = row["event_time"]
    return events_sorted.loc[kept]


def summarize(events: pd.DataFrame) -> tuple[int, float, float]:
    if events.empty:
        return 0, float("nan"), float("nan")
    r = events[HORIZON].dropna() * 1e4
    if len(r) == 0:
        return 0, float("nan"), float("nan")
    return int(len(r)), float(r.mean()), float((r > 0).mean())


def plan_a_dn(events_sym: pd.DataFrame) -> pd.DataFrame:
    return events_sym[events_sym[METRIC] <= FIXED_LO].copy()


def plan_b_dn(events_sym: pd.DataFrame) -> pd.DataFrame:
    ev = events_sym.sort_values("event_time").reset_index(drop=True)
    skew = ev[METRIC].to_numpy()
    keep_mask = np.zeros(len(ev), dtype=bool)
    for i in range(WARMUP_MIN, len(ev)):
        window = skew[max(0, i - ROLLING_K):i]  # 过去 K 事件（不含 t）
        if len(window) < WARMUP_MIN:
            continue
        lo = np.quantile(window, ROLLING_Q)
        if skew[i] <= lo:
            keep_mask[i] = True
    return ev[keep_mask].copy()


def plan_in_sample_dn(events_sym: pd.DataFrame) -> pd.DataFrame:
    """原 in-sample q=16% · 用整段样本分位（有未来函数），作为对照。"""
    lo = events_sym[METRIC].quantile(0.16)
    return events_sym[events_sym[METRIC] <= lo].copy()


def main() -> None:
    df = pd.read_csv(LONG_PATH)
    df["event_time"] = pd.to_datetime(df["event_time"])
    df["date"] = df["event_time"].dt.date
    sub = df[df["window"] == WINDOW].copy()

    contracts = sorted(sub["contract"].unique())

    # 分品种展开
    print("=== 分品种 · DN dedup_8h · 三方案对比（mean_ret_8h in bps）===\n")
    print(f"{'contract':16s}  {'in_sample q=16% (未来函数)':>26s}   {'plan A (|skew|≥0.45)':>22s}   {'plan B (rolling K=200 q=16%)':>28s}")
    print(f"{'':16s}  {'n':>4s} {'mean':>6s} {'hit':>5s}    {'n':>4s} {'mean':>6s} {'hit':>5s}    {'n':>4s} {'mean':>6s} {'hit':>5s}")
    print("-" * 105)

    rows: list[dict] = []
    for c in contracts:
        events_sym = sub[sub["contract"] == c].copy()

        dn_is = dedup_gap(plan_in_sample_dn(events_sym), DEDUP_GAP_HOURS)
        dn_a = dedup_gap(plan_a_dn(events_sym), DEDUP_GAP_HOURS)
        dn_b = dedup_gap(plan_b_dn(events_sym), DEDUP_GAP_HOURS)

        n_is, m_is, h_is = summarize(dn_is)
        n_a, m_a, h_a = summarize(dn_a)
        n_b, m_b, h_b = summarize(dn_b)

        print(f"{c:16s}  "
              f"{n_is:>4d} {m_is:>+6.1f} {h_is:>5.1%}    "
              f"{n_a:>4d} {m_a:>+6.1f} {h_a:>5.1%}    "
              f"{n_b:>4d} {m_b:>+6.1f} {h_b:>5.1%}")

        rows.append(
            {
                "contract": c,
                "in_sample_n": n_is, "in_sample_mean": m_is, "in_sample_hit": h_is,
                "plan_a_n": n_a, "plan_a_mean": m_a, "plan_a_hit": h_a,
                "plan_b_n": n_b, "plan_b_mean": m_b, "plan_b_hit": h_b,
            }
        )

    result = pd.DataFrame(rows)
    out_path = LOG_DIR / "no_lookahead_comparison.csv"
    result.to_csv(out_path, index=False)

    # Pooled
    print("\n=== Pooled（跨合约 pool） · DN dedup_8h ===")
    for name, fn in [
        ("in_sample q=16% (未来函数)", plan_in_sample_dn),
        ("plan A · fixed |skew|≥0.45", plan_a_dn),
        ("plan B · rolling K=200 q=16%", plan_b_dn),
    ]:
        all_ev = pd.concat(
            [dedup_gap(fn(sub[sub["contract"] == c]), DEDUP_GAP_HOURS) for c in contracts],
            ignore_index=True,
        )
        n, m, h = summarize(all_ev)
        print(f"  {name:38s}  n={n:>4d}  mean={m:>+6.2f} bps  hit={h:>5.1%}")

    # baseline
    all_baseline = sub[HORIZON].dropna() * 1e4
    print(f"  {'全 events baseline':38s}  n={len(all_baseline):>4d}  "
          f"mean={all_baseline.mean():>+6.2f} bps  hit={(all_baseline>0).mean():>5.1%}")

    print(f"\nOutput: {out_path}")


if __name__ == "__main__":
    main()
