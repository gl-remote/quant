#!/usr/bin/env python3
"""
文件级元信息：
- 创建背景：Stage 4 直接对比 rolling POC vs fixed POC vs PrevClose 三锚点的期望净值，
  判决 rolling POC 假设是否成立。
- 用途：在同一批 reacceptance 事件上，同时以 5 个锚点为目标模拟 S1 baseline 交易，
  按板块 × 距离档聚合期望净值，输出三态判决用矩阵。
- 注意事项：
  - reacceptance 事件用 fixed VA 触发（保持与 Stage 1/1.5 一致）
  - 只保留距 fixed POC ≥ 2.5 ATR 的事件（A4 生效边界）
  - rolling POC window: 60 / 120 / 240 bar
  - S1 baseline: stop=1.5 ATR, target=anchor, timeout=80 bar, cost=0.05 ATR
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

CSV_ROOT = Path("project_data/market_data/csv")
DEFAULT_OUTPUT_DIR = Path("project_data/analysis/rolling_reacceptance_stage4")

DISTANCE_BUCKETS: list[tuple[float, float, str]] = [
    (2.5, 4.0, "2.5-4.0"),
    (4.0, 1e9, "4.0+"),
]
OBSERVE_N = 80  # timeout
STOP_ATR = 1.5  # 固定止损
COST_ATR = 0.05  # 单边成本
ATR_WINDOW = 20
VA_RATIO = 0.7

ROLLING_WINDOWS = [60, 120, 240]

TICK_SIZE: dict[str, float] = {
    "rb": 1.0, "i": 0.5, "hc": 1.0, "FG": 1.0,
    "cu": 10.0, "al": 5.0, "ag": 1.0, "au": 0.02,
    "sc": 0.1, "TA": 2.0, "MA": 1.0, "OI": 1.0,
    "m": 1.0, "p": 2.0, "y": 2.0, "c": 1.0, "cs": 1.0,
    "SR": 1.0, "CF": 5.0, "RM": 1.0,
}

SECTOR_MAP: dict[str, str] = {
    "rb": "black", "i": "black", "hc": "black", "FG": "black",
    "cu": "metals", "al": "metals", "ag": "metals", "au": "metals",
    "sc": "energy_chem", "TA": "energy_chem", "MA": "energy_chem", "OI": "energy_chem",
    "m": "agri_dce", "p": "agri_dce", "y": "agri_dce", "c": "agri_dce", "cs": "agri_dce",
    "SR": "agri_czce", "CF": "agri_czce", "RM": "agri_czce",
}


def parse_contract(filename: str) -> tuple[str, str] | None:
    m = re.match(r"^([A-Z]+)\.([a-zA-Z]+)(\d+)\.tqsdk\.5m\.csv$", filename)
    if not m:
        return None
    exchange, symbol, month = m.groups()
    return f"{exchange}.{symbol}{month}", symbol


def load_bars(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df["date"] = df["datetime"].dt.date
    df = df[["datetime", "date", "open", "high", "low", "close", "volume"]].copy()
    df = df.reset_index(drop=True)
    return df


def compute_atr(bars: pd.DataFrame, window: int) -> np.ndarray:
    high = bars["high"].to_numpy()
    low = bars["low"].to_numpy()
    close = bars["close"].to_numpy()
    prev_close = np.concatenate([[close[0]], close[:-1]])
    tr = np.maximum.reduce([high - low, np.abs(high - prev_close), np.abs(low - prev_close)])
    atr = np.full_like(tr, fill_value=np.nan, dtype=float)
    cs = np.cumsum(tr)
    atr[window - 1:] = (cs[window - 1:] - np.concatenate([[0], cs[:-window]])) / window
    return atr


def daily_poc_va(day_bars: pd.DataFrame, tick: float, ratio: float) -> tuple[float, float, float, float] | None:
    """返回 (poc, val, vah, prev_close)。"""
    if day_bars.empty:
        return None
    prices = day_bars["close"].to_numpy()
    volumes = day_bars["volume"].to_numpy(dtype=float)
    if volumes.sum() <= 0:
        return None
    bucket = np.round(prices / tick).astype(int)
    unique, inverse = np.unique(bucket, return_inverse=True)
    bucket_vol = np.zeros_like(unique, dtype=float)
    np.add.at(bucket_vol, inverse, volumes)
    total = bucket_vol.sum()
    if total <= 0:
        return None
    poc_idx = int(bucket_vol.argmax())
    poc_price = unique[poc_idx] * tick

    target = ratio * total
    acc = bucket_vol[poc_idx]
    lo, hi = poc_idx, poc_idx
    while acc < target and (lo > 0 or hi < len(unique) - 1):
        left_vol = bucket_vol[lo - 1] if lo > 0 else -1.0
        right_vol = bucket_vol[hi + 1] if hi < len(unique) - 1 else -1.0
        if left_vol >= right_vol and lo > 0:
            lo -= 1
            acc += bucket_vol[lo]
        elif hi < len(unique) - 1:
            hi += 1
            acc += bucket_vol[hi]
        else:
            break
    val = unique[lo] * tick
    vah = unique[hi] * tick
    prev_close = float(day_bars["close"].iloc[-1])
    return (poc_price, val, vah, prev_close)


def rolling_poc(bars: pd.DataFrame, end_idx: int, window: int, tick: float) -> float | None:
    """计算截至 end_idx（不含）的前 window 根 bar 的 volume profile 众数。"""
    start_idx = end_idx - window
    if start_idx < 0:
        return None
    sub = bars.iloc[start_idx:end_idx]
    prices = sub["close"].to_numpy()
    volumes = sub["volume"].to_numpy(dtype=float)
    if volumes.sum() <= 0:
        return None
    bucket = np.round(prices / tick).astype(int)
    unique, inverse = np.unique(bucket, return_inverse=True)
    bucket_vol = np.zeros_like(unique, dtype=float)
    np.add.at(bucket_vol, inverse, volumes)
    if bucket_vol.sum() <= 0:
        return None
    return float(unique[int(bucket_vol.argmax())] * tick)


def simulate_s1(
    entry_price: float,
    target_price: float,
    stop_atr: float,
    cost_atr: float,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr_t: float,
    side: int,  # +1 long / -1 short
) -> float:
    """S1 baseline 交易模拟，返回单笔期望净值（ATR 单位）。"""
    stop_price = entry_price - side * stop_atr * atr_t
    for i in range(len(highs)):
        # 检查止损
        if side == +1:
            if lows[i] <= stop_price:
                return -stop_atr - cost_atr
            if highs[i] >= target_price:
                return (target_price - entry_price) / atr_t - cost_atr
        else:
            if highs[i] >= stop_price:
                return -stop_atr - cost_atr
            if lows[i] <= target_price:
                return (entry_price - target_price) / atr_t - cost_atr
    # timeout
    final_close = closes[-1] if len(closes) > 0 else entry_price
    pnl = (final_close - entry_price) * side / atr_t
    return pnl - cost_atr


def bucket_of(distance_atr: float) -> str | None:
    for lo, hi, name in DISTANCE_BUCKETS:
        if lo <= distance_atr < hi:
            return name
    return None


@dataclass
class Trade:
    contract: str
    symbol: str
    sector: str
    bucket: str
    anchor_name: str
    pnl_atr: float


def analyze_contract(csv_path: Path) -> list[Trade]:
    parsed = parse_contract(csv_path.name)
    if parsed is None:
        return []
    contract, symbol = parsed
    if symbol not in SECTOR_MAP:
        return []
    sector = SECTOR_MAP[symbol]
    tick = TICK_SIZE.get(symbol, 1.0)
    bars = load_bars(csv_path)
    if len(bars) < 500:
        return []

    atr = compute_atr(bars, ATR_WINDOW)

    # 每日 fixed POC / VA / PrevClose
    daily: dict[date, tuple[float, float, float, float]] = {}
    for day, day_df in bars.groupby("date", sort=True):
        r = daily_poc_va(day_df, tick=tick, ratio=VA_RATIO)
        if r is not None:
            daily[day] = r

    dates_sorted = sorted(daily.keys())
    max_idx = len(bars) - OBSERVE_N - 1

    highs = bars["high"].to_numpy()
    lows = bars["low"].to_numpy()
    closes = bars["close"].to_numpy()
    opens = bars["open"].to_numpy()

    trades: list[Trade] = []

    for i in range(1, len(dates_sorted)):
        today = dates_sorted[i]
        yesterday = dates_sorted[i - 1]
        fixed_poc, val, vah, prev_close = daily[yesterday]

        today_mask = bars["date"] == today
        today_bars = bars[today_mask]
        if len(today_bars) < 2:
            continue

        today_indices = today_bars.index.to_numpy()
        for k in range(1, len(today_indices)):
            orig_idx = int(today_indices[k])
            if orig_idx < max(ATR_WINDOW, max(ROLLING_WINDOWS)) or orig_idx >= max_idx:
                continue
            prev_close_bar = float(closes[orig_idx - 1])
            curr_close = float(closes[orig_idx])
            atr_t = atr[orig_idx]
            if not np.isfinite(atr_t) or atr_t <= 0:
                continue

            # reacceptance 事件判定（fixed VA）
            is_reacceptance = False
            if prev_close_bar < val - tick and curr_close >= val:
                is_reacceptance = True
            elif prev_close_bar > vah + tick and curr_close <= vah:
                is_reacceptance = True
            if not is_reacceptance:
                continue

            # 距 fixed POC 距离 ≥ 2.5 ATR 才纳入
            dist_fixed = abs(curr_close - fixed_poc) / atr_t
            if dist_fixed < 2.5:
                continue

            # 入场价：下一 bar open
            entry_idx = orig_idx + 1
            if entry_idx + OBSERVE_N >= len(bars):
                continue
            entry_price = float(opens[entry_idx])

            # 收集所有锚点
            anchors: dict[str, float] = {
                "fixed_POC": fixed_poc,
                "PrevClose": prev_close,
            }
            for w in ROLLING_WINDOWS:
                rp = rolling_poc(bars, entry_idx, w, tick)
                if rp is not None:
                    anchors[f"rolling_POC_{w}"] = rp

            # 对每个锚点评估：距离档 + S1 模拟
            end = entry_idx + OBSERVE_N
            fw_highs = highs[entry_idx: end]
            fw_lows = lows[entry_idx: end]
            fw_closes = closes[entry_idx: end]

            for anchor_name, anchor_price in anchors.items():
                diff = entry_price - anchor_price
                if abs(diff) < tick / 2:
                    continue
                side = -1 if diff > 0 else +1
                distance_atr = abs(diff) / atr_t
                bucket = bucket_of(distance_atr)
                if bucket is None:
                    continue
                pnl = simulate_s1(
                    entry_price=entry_price,
                    target_price=anchor_price,
                    stop_atr=STOP_ATR,
                    cost_atr=COST_ATR,
                    highs=fw_highs,
                    lows=fw_lows,
                    closes=fw_closes,
                    atr_t=atr_t,
                    side=side,
                )
                trades.append(Trade(
                    contract=contract, symbol=symbol, sector=sector,
                    bucket=bucket, anchor_name=anchor_name, pnl_atr=pnl,
                ))

    return trades


def render_markdown(trades: list[Trade]) -> str:
    df = pd.DataFrame([{
        "contract": t.contract, "symbol": t.symbol, "sector": t.sector,
        "bucket": t.bucket, "anchor": t.anchor_name, "pnl_atr": t.pnl_atr,
    } for t in trades])
    lines: list[str] = []
    lines.append(f"# Stage 4 · Rolling POC vs Fixed POC vs PrevClose 期望净值对比 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n")
    lines.append(f"OBSERVE_N = {OBSERVE_N}, STOP_ATR = {STOP_ATR}, COST_ATR = {COST_ATR}\n")
    lines.append(f"Rolling windows: {ROLLING_WINDOWS}\n")
    lines.append(f"总交易数: {len(df)}\n")

    anchor_order = ["rolling_POC_60", "rolling_POC_120", "rolling_POC_240", "fixed_POC", "PrevClose"]

    # 板块 × 距离档 × 锚点
    lines.append("## 1. 板块 × 距离档 × 锚点 期望净值（ATR/笔）\n")
    for sector in sorted(df["sector"].unique()):
        sec_df = df[df["sector"] == sector]
        lines.append(f"### {sector}\n")
        header = "| bucket | " + " | ".join(anchor_order) + " |"
        sep = "|---|" + "|".join("---" for _ in anchor_order) + "|"
        lines.append(header)
        lines.append(sep)
        for _, _, bname in DISTANCE_BUCKETS:
            bdf = sec_df[sec_df["bucket"] == bname]
            cells = []
            for a in anchor_order:
                sub = bdf[bdf["anchor"] == a]
                if len(sub) < 20:
                    cells.append("-")
                else:
                    mean = sub["pnl_atr"].mean()
                    n = len(sub)
                    cells.append(f"{mean:+.3f}(n={n})")
            lines.append(f"| {bname} | " + " | ".join(cells) + " |")
        lines.append("")

    # 跨板块聚合
    lines.append("## 2. 跨板块聚合（不含 metals）· 期望净值\n")
    df_ex = df[df["sector"] != "metals"]
    header = "| bucket | " + " | ".join(anchor_order) + " |"
    sep = "|---|" + "|".join("---" for _ in anchor_order) + "|"
    lines.append(header)
    lines.append(sep)
    for _, _, bname in DISTANCE_BUCKETS:
        bdf = df_ex[df_ex["bucket"] == bname]
        cells = []
        for a in anchor_order:
            sub = bdf[bdf["anchor"] == a]
            if len(sub) < 30:
                cells.append("-")
            else:
                mean = sub["pnl_atr"].mean()
                cells.append(f"{mean:+.3f}(n={len(sub)})")
        lines.append(f"| {bname} | " + " | ".join(cells) + " |")
    lines.append("")

    # 差值矩阵
    lines.append("## 3. 关键差值（rolling - baseline）· 期望净值\n")
    lines.append("| bucket | sector | rolling_60 - fixed | rolling_120 - fixed | rolling_240 - fixed | best_rolling - PrevClose |")
    lines.append("|---|---|---|---|---|---|")
    for sector in sorted(df["sector"].unique()):
        if sector == "metals":
            continue
        sec_df = df[df["sector"] == sector]
        for _, _, bname in DISTANCE_BUCKETS:
            bdf = sec_df[sec_df["bucket"] == bname]
            means = {}
            for a in anchor_order:
                sub = bdf[bdf["anchor"] == a]
                if len(sub) >= 20:
                    means[a] = sub["pnl_atr"].mean()
            if "fixed_POC" not in means or "PrevClose" not in means:
                continue
            cells = [bname, sector]
            for w in ROLLING_WINDOWS:
                key = f"rolling_POC_{w}"
                if key in means:
                    cells.append(f"{means[key] - means['fixed_POC']:+.3f}")
                else:
                    cells.append("-")
            rolling_means = [means[f"rolling_POC_{w}"] for w in ROLLING_WINDOWS if f"rolling_POC_{w}" in means]
            if rolling_means:
                best = max(rolling_means)
                cells.append(f"{best - means['PrevClose']:+.3f}")
            else:
                cells.append("-")
            lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv-root", default=str(CSV_ROOT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--contracts", nargs="*", default=None)
    args = parser.parse_args()

    csv_root = Path(args.csv_root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_csvs = sorted(csv_root.glob("*.tqsdk.5m.csv"))
    all_trades: list[Trade] = []
    for csv_path in all_csvs:
        parsed = parse_contract(csv_path.name)
        if parsed is None:
            continue
        contract, symbol = parsed
        if args.contracts and contract not in args.contracts:
            continue
        if symbol not in SECTOR_MAP:
            continue
        print(f"[analyze] {contract} ...", flush=True)
        t = analyze_contract(csv_path)
        print(f"  trades={len(t)}")
        all_trades.extend(t)

    if not all_trades:
        print("no trades")
        return

    md = render_markdown(all_trades)
    md_path = output_dir / "stage4_multi_anchor_expected_value.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"wrote {md_path}")

    df = pd.DataFrame([{
        "contract": t.contract, "symbol": t.symbol, "sector": t.sector,
        "bucket": t.bucket, "anchor": t.anchor_name, "pnl_atr": t.pnl_atr,
    } for t in all_trades])
    csv_path = output_dir / "stage4_trades.csv"
    df.to_csv(csv_path, index=False)
    print(f"wrote {csv_path}")


if __name__ == "__main__":
    main()
