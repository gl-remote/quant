"""
文件级元信息：
- 创建背景：cu 排查发现严重事件重叠 → q=8% 的 DN 事件在多数合约上只
  来自极少数几天，同一段行情被反复计入。用户建议扫描不同阈值档位
  （8% / 16% / 32% / 50%），看真实（去重后）信号是否仍成立。
- 用途：读 long_events.csv → 对每个 q 档位，展开每合约的
    (a) 原始 DN/UP 事件数 + mean_ret_8h
    (b) 每日最多 1 次去重版 mean
    (c) 相邻 ≥8h 无重叠版 mean
    (d) 全样本 baseline mean（no-signal 对照）
  → 输出对照表，判断是"真信号"还是"重叠伪影"
- 注意事项：临时诊断脚本。ret_8h 单位 bps。
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
Q_LEVELS = [0.08, 0.16, 0.32, 0.50]  # 每侧分位；50% 对应"所有 skew<0" 与 "所有 skew>0"
HORIZON = "ret_8h"


def dedup_daily(events: pd.DataFrame) -> pd.DataFrame:
    """每天最多保留一个（按 event_time 排序取第一个）。"""
    return events.sort_values("event_time").drop_duplicates(subset="date", keep="first")


def dedup_gap(events: pd.DataFrame, min_gap_h: float = 8.0) -> pd.DataFrame:
    """相邻事件间隔至少 min_gap_h 小时。"""
    events_sorted = events.sort_values("event_time").reset_index(drop=True)
    kept_idx: list[int] = []
    last_time = None
    for i, row in events_sorted.iterrows():
        if last_time is None or (row["event_time"] - last_time).total_seconds() / 3600 >= min_gap_h:
            kept_idx.append(i)
            last_time = row["event_time"]
    return events_sorted.loc[kept_idx]


def summarize(events: pd.DataFrame) -> tuple[int, float, float, float]:
    """返回 (n, mean_bps, median_bps, hit_pos)。"""
    if events.empty:
        return 0, float("nan"), float("nan"), float("nan")
    r = events[HORIZON].dropna() * 1e4
    if len(r) == 0:
        return 0, float("nan"), float("nan"), float("nan")
    return int(len(r)), float(r.mean()), float(r.median()), float((r > 0).mean())


def main() -> None:
    df = pd.read_csv(LONG_PATH)
    df["event_time"] = pd.to_datetime(df["event_time"])
    df["date"] = df["event_time"].dt.date

    sub = df[df["window"] == WINDOW].copy()

    contracts = sorted(sub["contract"].unique())
    rows: list[dict] = []
    print(f"=== W1 × A3_skew × ret_8h · 阈值扫描 × 三种去重口径 ===\n")

    # baseline: 每合约全样本 mean_ret_8h（no-signal）
    baseline: dict[str, float] = {}
    for c in contracts:
        r = sub[sub["contract"] == c][HORIZON].dropna() * 1e4
        baseline[c] = float(r.mean()) if len(r) else float("nan")

    print(f"{'contract':16s} {'baseline_mean':>13s}  ", end="")
    for q in Q_LEVELS:
        print(f"| q={int(q*100):02d}% raw:n/mean_dn_bps  |  dedup_day  |  dedup_8h  ",
              end="")
    print()
    print("-" * (17 + 15 + len(Q_LEVELS) * 66))

    for c in contracts:
        g = sub[sub["contract"] == c].copy()
        row_out = f"{c:16s} {baseline[c]:>13.2f}  "
        for q in Q_LEVELS:
            lo = g[METRIC].quantile(q)
            dn_raw = g[g[METRIC] <= lo]
            n_raw, mean_raw, _, _ = summarize(dn_raw)
            dn_day = dedup_daily(dn_raw)
            n_day, mean_day, _, _ = summarize(dn_day)
            dn_8h = dedup_gap(dn_raw, 8.0)
            n_8h, mean_8h, _, _ = summarize(dn_8h)
            row_out += (
                f"| {n_raw:3d}:{mean_raw:>+7.1f}  |  {n_day:3d}:{mean_day:>+7.1f}  "
                f"|  {n_8h:3d}:{mean_8h:>+7.1f}  "
            )
            rows.append(
                {
                    "contract": c,
                    "q": q,
                    "n_raw": n_raw,
                    "mean_raw_bps": mean_raw,
                    "n_dedup_day": n_day,
                    "mean_dedup_day_bps": mean_day,
                    "n_dedup_8h": n_8h,
                    "mean_dedup_8h_bps": mean_8h,
                    "baseline_mean_bps": baseline[c],
                }
            )
        print(row_out)

    result = pd.DataFrame(rows)
    out_path = LOG_DIR / "threshold_dedup_scan.csv"
    result.to_csv(out_path, index=False)

    # pooled 视角（跨合约 pool 所有事件）
    print(f"\n=== Pooled（跨合约 pool 事件）· DN 组 mean_ret_8h(bps) ===\n")
    print(f"{'口径':16s}", end="")
    for q in Q_LEVELS:
        print(f"  q={int(q*100):02d}%: n / mean / hit_pos", end="")
    print()

    def pooled_summary(dedup_fn) -> dict:
        out = {}
        for q in Q_LEVELS:
            all_events: list[pd.DataFrame] = []
            for c in contracts:
                g = sub[sub["contract"] == c].copy()
                lo = g[METRIC].quantile(q)
                dn = g[g[METRIC] <= lo]
                if dedup_fn is not None:
                    dn = dedup_fn(dn)
                all_events.append(dn)
            merged = pd.concat(all_events, ignore_index=True) if all_events else pd.DataFrame()
            n, mean, _, hit = summarize(merged)
            out[q] = (n, mean, hit)
        return out

    for name, fn in [("raw", None), ("dedup_day", dedup_daily), ("dedup_8h", lambda d: dedup_gap(d, 8.0))]:
        pooled = pooled_summary(fn)
        line = f"{name:16s}"
        for q in Q_LEVELS:
            n, m, h = pooled[q]
            line += f"  {n:5d} / {m:>+7.1f} / {h:.2%}"
        print(line)

    # 全样本 baseline pooled
    all_baseline_ret = sub[HORIZON].dropna() * 1e4
    print(f"\n全 events pooled baseline: n={len(all_baseline_ret)}  "
          f"mean={all_baseline_ret.mean():+.2f} bps  hit_pos={(all_baseline_ret>0).mean():.2%}")

    print(f"\n【判据】DN mean_dedup_8h 若显著高于 baseline_mean，才是真信号；")
    print(f"        若二者接近，说明是全样本单边趋势型伪信号。")
    print(f"\nOutput: {out_path}")


if __name__ == "__main__":
    main()
