"""
文件级元信息：
- 创建背景：用户提出 rolling K=60/120 5m bar 是否比 W1（前一天）更好；
  先在信号最强 3 合约 (sc/al/TA) 和最差 3 合约 (SR/p/rb) 上测。
- 用途：
  (1) 对 6 个合约 · 每小时 event 用 rolling K=60 与 K=120 重新构建 volume
      profile 并计算 A3_skew
  (2) 与原 W1 结果并排展示
  (3) 对每档窗口，用 k=1.0×σ 与 k=1.5×σ 阈值 + dedup_8h 展示 DN 侧
      pooled 与分品种 mean_ret_8h · hit · n
  → 判断 rolling 窗口是否稳定改善（或恶化）
- 注意事项：临时脚本；profile 计算复用原逻辑（close-based bucketing +
  70% VA + volume 加权三阶矩 skew）；ret_8h 从 long_events.csv 直接取
  （避免重算）。
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
ALL_SYMBOLS = TOP_SYMBOLS + BOTTOM_SYMBOLS

# 各合约的 tick_size
TICK_SIZE: dict[str, float] = {
    "sc": 0.1, "al": 5.0, "TA": 2.0,
    "SR": 1.0, "p": 2.0, "rb": 1.0,
}

K_ROLLING = [60, 120]  # 5m bar 数：60 → 5h, 120 → 10h
K_SIGMA_LEVELS = [1.0, 1.5]
DEDUP_GAP_HOURS = 8.0
VALUE_AREA_RATIO = 0.70


def parse_prefix(symbol: str) -> str:
    _, contract = symbol.split(".")
    return "".join(c for c in contract if c.isalpha())


def load_5m(symbol: str) -> pd.DataFrame:
    df = pd.read_csv(CSV_DIR / f"{symbol}.tqsdk.5m.csv")
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    return df


def compute_skew_from_bars(bars: pd.DataFrame, tick: float) -> float:
    """volume 加权三阶矩标准化偏度（复用原口径）。"""
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


def build_rolling_events(bars: pd.DataFrame, tick: float, k: int) -> pd.DataFrame:
    """对每小时 event 计算 rolling K 根 5m bar profile 的 A3_skew。"""
    bars = bars.copy()
    bars["is_hour"] = bars["datetime"].dt.minute == 0
    dt_to_idx = {dt: i for i, dt in enumerate(bars["datetime"])}
    rows = []
    for _, row in bars[bars["is_hour"]].iterrows():
        idx = dt_to_idx[row["datetime"]]
        lo = idx - k
        if lo < 0:
            continue
        window_bars = bars.iloc[lo:idx]
        skew = compute_skew_from_bars(window_bars, tick)
        rows.append({"event_time": row["datetime"], "A3_skew_new": skew})
    return pd.DataFrame(rows)


def evaluate(events: pd.DataFrame, tag: str) -> dict:
    """events 需含 event_time, A3_skew_new, ret_8h, contract 列。
    返回按每合约 std 归一后的 DN mean / hit / n 的 pooled 结果。
    """
    out = {"tag": tag}
    for k_sig in K_SIGMA_LEVELS:
        pooled_events = []
        for c, g in events.groupby("contract"):
            std_c = g["A3_skew_new"].std()
            thr = -k_sig * std_c
            dn = g[g["A3_skew_new"] <= thr]
            dn = dedup_gap(dn, DEDUP_GAP_HOURS)
            pooled_events.append(dn)
        pooled = pd.concat(pooled_events, ignore_index=True) if pooled_events else pd.DataFrame()
        n, m, h = summarize(pooled)
        out[f"k={k_sig}_n"] = n
        out[f"k={k_sig}_mean_bps"] = m
        out[f"k={k_sig}_hit"] = h
    return out


def main() -> None:
    # 载入原 long_events.csv 拿 ret_8h（W1 结果 + 每 hourly event 的 close_t/ret_8h）
    long_df = pd.read_csv(LONG_PATH)
    long_df["event_time"] = pd.to_datetime(long_df["event_time"])
    # 只用 W1 记录里的 event 时间对齐（每个 event × window 会有 3 行，取 W1 即可）
    ret_map = long_df[long_df["window"] == "W1"][
        ["contract", "event_time", "ret_8h", "A3_skew"]
    ].rename(columns={"A3_skew": "A3_skew_W1"})

    print("=== 分组：top 3 (sc / al / TA)  ·  bottom 3 (SR / p / rb) ===\n")

    all_results: list[dict] = []

    for label, syms in [("TOP", TOP_SYMBOLS), ("BOTTOM", BOTTOM_SYMBOLS)]:
        print(f"\n{'='*100}\n{label} 3\n{'='*100}")
        for k_win in [None] + K_ROLLING:  # None = W1 对照
            frames = []
            for sym in syms:
                prefix = parse_prefix(sym)
                tick = TICK_SIZE[prefix]
                sym_ret = ret_map[ret_map["contract"] == sym].copy()
                if k_win is None:
                    # W1 直接用原 A3_skew
                    sym_ret = sym_ret.rename(columns={"A3_skew_W1": "A3_skew_new"})
                    frames.append(sym_ret[["contract", "event_time", "A3_skew_new", "ret_8h"]])
                else:
                    bars = load_5m(sym)
                    new_skew = build_rolling_events(bars, tick, k_win)
                    merged = sym_ret.merge(new_skew, on="event_time", how="inner")
                    merged["contract"] = sym
                    frames.append(merged[["contract", "event_time", "A3_skew_new", "ret_8h"]])
            merged_all = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
            tag = "W1 (yesterday)" if k_win is None else f"rolling K={k_win} ({k_win*5/60:.1f}h)"
            r = evaluate(merged_all, tag)
            r["group"] = label
            all_results.append(r)
            print(f"{tag:24s}  "
                  f"k=1.0: n={r['k=1.0_n']:>3d}  mean={r['k=1.0_mean_bps']:>+7.2f} bps  hit={r['k=1.0_hit']:>5.1%}  "
                  f"|  k=1.5: n={r['k=1.5_n']:>3d}  mean={r['k=1.5_mean_bps']:>+7.2f} bps  hit={r['k=1.5_hit']:>5.1%}")

            # 分品种展开（简）
            for c, g in merged_all.groupby("contract"):
                std_c = g["A3_skew_new"].std()
                for k_sig in K_SIGMA_LEVELS:
                    thr = -k_sig * std_c
                    dn = g[g["A3_skew_new"] <= thr]
                    dn = dedup_gap(dn, DEDUP_GAP_HOURS)
                    n, m, h = summarize(dn)
                    print(f"    {c:16s} k={k_sig}: n={n:>3d}  mean={m:>+7.2f}  hit={h:>5.1%}")
                print()

    result_df = pd.DataFrame(all_results)
    result_df.to_csv(LOG_DIR / "rolling_window_compare.csv", index=False)
    print(f"\nOutput: {LOG_DIR / 'rolling_window_compare.csv'}")


if __name__ == "__main__":
    main()
