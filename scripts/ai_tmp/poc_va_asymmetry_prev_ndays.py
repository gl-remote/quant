"""
文件级元信息：
- 创建背景：验证候选 A"自然日边界重要"——如果前 N 天 profile 都优于任意
  rolling，就是自然日边界起作用；如果 N=1 最强、N=2/3 变差，说明只有
  昨天的定价信号最有效（近因效应）。
- 用途：
  (1) 对 top3 + bottom3 六个合约，构建 D1/D2/D3/D5 四档"前 N 天"profile
  (2) 用 k=1.0σ 和 k=1.5σ 阈值 + dedup_8h · DN 侧
  (3) pooled + 分品种展示 n / mean_ret_8h / hit
- 注意事项：临时脚本；ret_8h 从 long_events.csv 借用（避免重算）。
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

CSV_DIR = Path("/Users/gaolei/Documents/src/quant/project_data/market_data/csv")
LOG_DIR = Path(
    "/Users/gaolei/Documents/src/quant/project_data/logs/poc_va_asymmetry_stage1"
)
LONG_PATH = LOG_DIR / "long_events.csv"

TOP_SYMBOLS = ["INE.sc2512", "SHFE.al2601", "CZCE.TA601"]
BOTTOM_SYMBOLS = ["CZCE.SR601", "DCE.p2601", "SHFE.rb2601"]

TICK_SIZE: dict[str, float] = {
    "sc": 0.1, "al": 5.0, "TA": 2.0,
    "SR": 1.0, "p": 2.0, "rb": 1.0,
}

N_DAYS_LIST = [1, 2, 3, 5]  # 前 N 天
K_SIGMA_LEVELS = [1.0, 1.5]
DEDUP_GAP_HOURS = 8.0


def parse_prefix(symbol: str) -> str:
    _, contract = symbol.split(".")
    return "".join(c for c in contract if c.isalpha())


def load_5m(symbol: str) -> pd.DataFrame:
    df = pd.read_csv(CSV_DIR / f"{symbol}.tqsdk.5m.csv")
    df["datetime"] = pd.to_datetime(df["datetime"])
    df["date"] = df["datetime"].dt.date
    return df.sort_values("datetime").reset_index(drop=True)


def compute_skew_from_bars(bars: pd.DataFrame, tick: float) -> float:
    if len(bars) == 0:
        return float("nan")
    buckets = (np.round(bars["close"].to_numpy() / tick) * tick).astype(float)
    volumes = bars["volume"].to_numpy(dtype=float)
    df = (
        pd.DataFrame({"price": buckets, "volume": volumes})
        .groupby("price", as_index=False)["volume"]
        .sum()
    )
    if df.empty or df["volume"].sum() <= 0:
        return float("nan")
    prices = df["price"].to_numpy()
    vols = df["volume"].to_numpy()
    mean = float(np.average(prices, weights=vols))
    var = float(np.average((prices - mean) ** 2, weights=vols))
    if var <= 0:
        return 0.0
    std = math.sqrt(var)
    return float(np.average(((prices - mean) / std) ** 3, weights=vols))


def dedup_gap(events: pd.DataFrame, min_gap_h: float) -> pd.DataFrame:
    ev = events.sort_values("event_time").reset_index(drop=True)
    kept = []
    last = None
    for i, row in ev.iterrows():
        if last is None or (row["event_time"] - last).total_seconds() / 3600 >= min_gap_h:
            kept.append(i)
            last = row["event_time"]
    return ev.loc[kept]


def summarize(events: pd.DataFrame) -> tuple[int, float, float]:
    if events.empty:
        return 0, float("nan"), float("nan")
    r = events["ret_8h"].dropna() * 1e4
    if len(r) == 0:
        return 0, float("nan"), float("nan")
    return int(len(r)), float(r.mean()), float((r > 0).mean())


def build_prev_ndays_events(bars: pd.DataFrame, tick: float, n_days: int) -> pd.DataFrame:
    """对每小时 event 计算"前 N 个交易日"profile 的 A3_skew。"""
    dates = sorted(bars["date"].unique())
    rows = []
    for _, row in bars[bars["datetime"].dt.minute == 0].iterrows():
        d = row["date"]
        if d not in dates:
            continue
        idx = dates.index(d)
        if idx < n_days:
            continue
        prev_dates = dates[idx - n_days: idx]
        window = bars[bars["date"].isin(prev_dates)]
        skew = compute_skew_from_bars(window, tick)
        rows.append({"event_time": row["datetime"], "A3_skew_new": skew})
    return pd.DataFrame(rows)


def main() -> None:
    long_df = pd.read_csv(LONG_PATH)
    long_df["event_time"] = pd.to_datetime(long_df["event_time"])
    ret_map = long_df[long_df["window"] == "W1"][
        ["contract", "event_time", "ret_8h"]
    ]

    print("=== 前 N 天 profile 对比 · top 3 (sc/al/TA) · bottom 3 (SR/p/rb) ===\n")

    for label, syms in [("TOP", TOP_SYMBOLS), ("BOTTOM", BOTTOM_SYMBOLS)]:
        print(f"\n{'='*100}\n{label} 3\n{'='*100}")
        for n_days in N_DAYS_LIST:
            frames = []
            for sym in syms:
                prefix = parse_prefix(sym)
                tick = TICK_SIZE[prefix]
                bars = load_5m(sym)
                new_skew = build_prev_ndays_events(bars, tick, n_days)
                sym_ret = ret_map[ret_map["contract"] == sym].copy()
                merged = sym_ret.merge(new_skew, on="event_time", how="inner")
                merged["contract"] = sym
                frames.append(merged[["contract", "event_time", "A3_skew_new", "ret_8h"]])
            merged_all = pd.concat(frames, ignore_index=True)

            pooled_line = f"前 {n_days} 天 profile "
            for k_sig in K_SIGMA_LEVELS:
                pool_events = []
                for c, g in merged_all.groupby("contract"):
                    std_c = g["A3_skew_new"].std()
                    thr = -k_sig * std_c
                    dn = g[g["A3_skew_new"] <= thr]
                    dn = dedup_gap(dn, DEDUP_GAP_HOURS)
                    pool_events.append(dn)
                pooled = pd.concat(pool_events, ignore_index=True) if pool_events else pd.DataFrame()
                n, m, h = summarize(pooled)
                pooled_line += f" | k={k_sig}: n={n:>3d} mean={m:>+7.2f} bps hit={h:>5.1%}"
            print(pooled_line)

            # 分品种
            for c, g in merged_all.groupby("contract"):
                std_c = g["A3_skew_new"].std()
                per_line = f"    {c:16s}"
                for k_sig in K_SIGMA_LEVELS:
                    thr = -k_sig * std_c
                    dn = g[g["A3_skew_new"] <= thr]
                    dn = dedup_gap(dn, DEDUP_GAP_HOURS)
                    n, m, h = summarize(dn)
                    per_line += f"   k={k_sig}: n={n:>3d} mean={m:>+7.2f} hit={h:>5.1%}"
                print(per_line)
            print()


if __name__ == "__main__":
    main()
