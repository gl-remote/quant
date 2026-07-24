#!/usr/bin/env python3
"""
文件级元信息：
- 创建背景：A3 用最简交易结构（单一 POC 目标 + 固定 stop）判定盈利，但用户提出
  更复杂止盈止损结构可能改变盈利地图（stage1_5-poc-attraction.md §5.5.7）。
- 用途：对同一批 reacceptance 事件，运行 6 种不同交易结构，输出 距离档 × 结构
  的期望净值矩阵，量化"结构敏感性"，识别每个距离档的最优结构。
- 注意事项：
  - 6 种结构：S1 基线（固定 stop + POC 目标）/ S2 部分止盈 / S3 breakeven
    trailing / S4 中位目标 / S5 分级 stop / S6 时间衰减部分退出
  - 全部用 1.5 ATR 作为默认 stop（A3 显示这是最好的固定 stop）
  - 成本仍 0.1 ATR/笔双边
  - 距离档合并为 4 档（避免子桶样本过小）：0-1 / 1-2 / 2-4 / 4+ ATR
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

CSV_ROOT = Path("project_data/market_data/csv")
DEFAULT_OUTPUT_DIR = Path("project_data/analysis/rolling_reacceptance_stage1_5")

DISTANCE_BUCKETS: list[tuple[float, float, str]] = [
    (0.0, 1.0, "0-1"),
    (1.0, 2.0, "1-2"),
    (2.0, 4.0, "2-4"),
    (4.0, 1e9, "4+"),
]

TIME_LIMIT = 80
COST_ATR_ROUND_TRIP = 0.1
VA_RATIO = 0.7
ATR_WINDOW = 20

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


def compute_daily_va_poc(day_bars: pd.DataFrame, tick: float, ratio: float) -> tuple[float, float, float] | None:
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
    return poc_price, unique[lo] * tick, unique[hi] * tick


def bucket_of(distance_atr: float) -> str | None:
    for lo, hi, name in DISTANCE_BUCKETS:
        if lo <= distance_atr < hi:
            return name
    return None


# ==================== 交易结构定义 ====================
# 统一签名：接收入场上下文，返回 pnl_in_atr


def _iterate(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
    entry_idx: int, time_limit: int,
) -> range:
    end = min(entry_idx + time_limit, len(highs) - 1)
    return range(entry_idx + 1, end + 1)


def structure_S1_baseline(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
    entry_idx: int, entry_price: float, poc: float, val: float, vah: float,
    direction: int, atr_t: float, distance_atr: float,
) -> float:
    """S1: 固定 stop=1.5 ATR + 目标 POC + 80 bar timeout。"""
    stop = 1.5
    stop_price = entry_price - direction * stop * atr_t
    for i in _iterate(highs, lows, closes, entry_idx, TIME_LIMIT):
        if direction == +1:
            if lows[i] <= stop_price:
                return -stop
            if highs[i] >= poc:
                return (poc - entry_price) / atr_t
        else:
            if highs[i] >= stop_price:
                return -stop
            if lows[i] <= poc:
                return (entry_price - poc) / atr_t
    end = min(entry_idx + TIME_LIMIT, len(closes) - 1)
    return (closes[end] - entry_price) * direction / atr_t


def structure_S2_partial_50(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
    entry_idx: int, entry_price: float, poc: float, val: float, vah: float,
    direction: int, atr_t: float, distance_atr: float,
) -> float:
    """S2: 到入场点与 POC 距离一半时平 50%，剩下追 POC，stop=1.5 ATR。"""
    stop = 1.5
    stop_price = entry_price - direction * stop * atr_t
    half_target = entry_price + direction * (poc - entry_price) * 0.5
    partial_taken = False
    partial_pnl = 0.0
    for i in _iterate(highs, lows, closes, entry_idx, TIME_LIMIT):
        if direction == +1:
            if lows[i] <= stop_price:
                # 剩余仓位以当前 stop_price 结算
                remaining_pnl = (stop_price - entry_price) / atr_t
                if partial_taken:
                    return partial_pnl + 0.5 * remaining_pnl
                return remaining_pnl
            if not partial_taken and highs[i] >= half_target:
                partial_taken = True
                partial_pnl = 0.5 * (half_target - entry_price) / atr_t
                # 剩下 50% stop 上移到 breakeven
                stop_price = entry_price
            if highs[i] >= poc:
                if partial_taken:
                    return partial_pnl + 0.5 * (poc - entry_price) / atr_t
                return (poc - entry_price) / atr_t
        else:
            if highs[i] >= stop_price:
                remaining_pnl = (entry_price - stop_price) / atr_t
                if partial_taken:
                    return partial_pnl + 0.5 * remaining_pnl
                return remaining_pnl
            if not partial_taken and lows[i] <= half_target:
                partial_taken = True
                partial_pnl = 0.5 * (entry_price - half_target) / atr_t
                stop_price = entry_price
            if lows[i] <= poc:
                if partial_taken:
                    return partial_pnl + 0.5 * (entry_price - poc) / atr_t
                return (entry_price - poc) / atr_t
    end = min(entry_idx + TIME_LIMIT, len(closes) - 1)
    tail_pnl = (closes[end] - entry_price) * direction / atr_t
    if partial_taken:
        return partial_pnl + 0.5 * tail_pnl
    return tail_pnl


def structure_S3_breakeven_trailing(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
    entry_idx: int, entry_price: float, poc: float, val: float, vah: float,
    direction: int, atr_t: float, distance_atr: float,
) -> float:
    """S3: 初始 stop=1.5 ATR，价格走 1 ATR 后 stop 上移到 breakeven，目标 POC。"""
    stop = 1.5
    stop_price = entry_price - direction * stop * atr_t
    trigger = entry_price + direction * 1.0 * atr_t
    for i in _iterate(highs, lows, closes, entry_idx, TIME_LIMIT):
        if direction == +1:
            if lows[i] <= stop_price:
                return (stop_price - entry_price) / atr_t
            if highs[i] >= trigger:
                stop_price = max(stop_price, entry_price)
            if highs[i] >= poc:
                return (poc - entry_price) / atr_t
        else:
            if highs[i] >= stop_price:
                return (entry_price - stop_price) / atr_t
            if lows[i] <= trigger:
                stop_price = min(stop_price, entry_price)
            if lows[i] <= poc:
                return (entry_price - poc) / atr_t
    end = min(entry_idx + TIME_LIMIT, len(closes) - 1)
    return (closes[end] - entry_price) * direction / atr_t


def structure_S4_midpoint_target(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
    entry_idx: int, entry_price: float, poc: float, val: float, vah: float,
    direction: int, atr_t: float, distance_atr: float,
) -> float:
    """S4: 目标改为 entry-POC 中点，stop=1.5 ATR。"""
    stop = 1.5
    stop_price = entry_price - direction * stop * atr_t
    mid_target = entry_price + direction * (poc - entry_price) * 0.5
    for i in _iterate(highs, lows, closes, entry_idx, TIME_LIMIT):
        if direction == +1:
            if lows[i] <= stop_price:
                return -stop
            if highs[i] >= mid_target:
                return (mid_target - entry_price) / atr_t
        else:
            if highs[i] >= stop_price:
                return -stop
            if lows[i] <= mid_target:
                return (entry_price - mid_target) / atr_t
    end = min(entry_idx + TIME_LIMIT, len(closes) - 1)
    return (closes[end] - entry_price) * direction / atr_t


def structure_S5_tiered_stop(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
    entry_idx: int, entry_price: float, poc: float, val: float, vah: float,
    direction: int, atr_t: float, distance_atr: float,
) -> float:
    """S5: 分级 stop：近档 0.5 ATR / 中档 1.0 ATR / 远档 2.0 ATR，目标 POC。"""
    if distance_atr < 1.0:
        stop = 0.5
    elif distance_atr < 2.0:
        stop = 1.0
    elif distance_atr < 4.0:
        stop = 1.5
    else:
        stop = 2.0
    stop_price = entry_price - direction * stop * atr_t
    for i in _iterate(highs, lows, closes, entry_idx, TIME_LIMIT):
        if direction == +1:
            if lows[i] <= stop_price:
                return -stop
            if highs[i] >= poc:
                return (poc - entry_price) / atr_t
        else:
            if highs[i] >= stop_price:
                return -stop
            if lows[i] <= poc:
                return (entry_price - poc) / atr_t
    end = min(entry_idx + TIME_LIMIT, len(closes) - 1)
    return (closes[end] - entry_price) * direction / atr_t


def structure_S6_time_decay(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
    entry_idx: int, entry_price: float, poc: float, val: float, vah: float,
    direction: int, atr_t: float, distance_atr: float,
) -> float:
    """S6: 到 40 bar 时检查，若 pnl > 0.3 ATR 全平；stop=1.5 ATR + 80 bar timeout 兜底。"""
    stop = 1.5
    stop_price = entry_price - direction * stop * atr_t
    checkpoint = entry_idx + 40
    end = min(entry_idx + TIME_LIMIT, len(closes) - 1)
    for i in range(entry_idx + 1, end + 1):
        if direction == +1:
            if lows[i] <= stop_price:
                return -stop
            if highs[i] >= poc:
                return (poc - entry_price) / atr_t
        else:
            if highs[i] >= stop_price:
                return -stop
            if lows[i] <= poc:
                return (entry_price - poc) / atr_t
        if i == checkpoint:
            interim_pnl = (closes[i] - entry_price) * direction / atr_t
            if interim_pnl > 0.3:
                return interim_pnl
    return (closes[end] - entry_price) * direction / atr_t


STRUCTURES: dict[str, tuple[str, Callable[..., float]]] = {
    "S1_baseline": ("固定 stop=1.5 + POC + timeout", structure_S1_baseline),
    "S2_partial_50": ("半路平 50% + BE + POC", structure_S2_partial_50),
    "S3_breakeven": ("初始 stop=1.5 + 走 1 ATR 后 BE + POC", structure_S3_breakeven_trailing),
    "S4_midpoint": ("目标 = 中点 + stop=1.5", structure_S4_midpoint_target),
    "S5_tiered_stop": ("stop 随距离档 (0.5/1.0/1.5/2.0)", structure_S5_tiered_stop),
    "S6_time_decay": ("40 bar 检查 + 早退", structure_S6_time_decay),
}


@dataclass
class BucketAgg:
    n: int = 0
    pnl_sum: float = 0.0
    pnl_sq_sum: float = 0.0
    n_pos: int = 0

    def add(self, pnl: float) -> None:
        self.n += 1
        self.pnl_sum += pnl
        self.pnl_sq_sum += pnl * pnl
        if pnl > 0:
            self.n_pos += 1

    def summary(self, cost: float) -> dict[str, float]:
        if self.n == 0:
            return {"n": 0, "win_rate": 0.0, "avg_pnl": 0.0, "avg_pnl_net": 0.0, "std_pnl": 0.0}
        avg = self.pnl_sum / self.n
        var = max(self.pnl_sq_sum / self.n - avg * avg, 0.0)
        return {
            "n": self.n,
            "win_rate": self.n_pos / self.n,
            "avg_pnl": avg,
            "avg_pnl_net": avg - cost,
            "std_pnl": var ** 0.5,
        }


@dataclass
class ContractResult:
    contract: str
    symbol: str
    sector: str
    # 键：(structure_name, distance_bucket) → BucketAgg
    stats: dict[tuple[str, str], BucketAgg]

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": self.contract, "symbol": self.symbol, "sector": self.sector,
            "stats": {
                f"{s}_{b}": agg.summary(COST_ATR_ROUND_TRIP)
                for (s, b), agg in self.stats.items()
            },
        }


def analyze_contract(csv_path: Path) -> ContractResult | None:
    parsed = parse_contract(csv_path.name)
    if parsed is None:
        return None
    contract, symbol = parsed
    if symbol not in SECTOR_MAP:
        return None
    sector = SECTOR_MAP[symbol]
    tick = TICK_SIZE.get(symbol, 1.0)
    bars = load_bars(csv_path)
    if len(bars) < 500:
        return None

    atr = compute_atr(bars, ATR_WINDOW)

    daily_profile: dict[date, tuple[float, float, float]] = {}
    for day, day_df in bars.groupby("date", sort=True):
        r = compute_daily_va_poc(day_df, tick=tick, ratio=VA_RATIO)
        if r is not None:
            daily_profile[day] = r

    dates_sorted = sorted(daily_profile.keys())
    max_idx = len(bars) - TIME_LIMIT - 1

    highs = bars["high"].to_numpy()
    lows = bars["low"].to_numpy()
    closes = bars["close"].to_numpy()

    stats: dict[tuple[str, str], BucketAgg] = {}

    for i in range(1, len(dates_sorted)):
        today = dates_sorted[i]
        yesterday = dates_sorted[i - 1]
        poc, val, vah = daily_profile[yesterday]
        today_mask = bars["date"] == today
        today_bars = bars[today_mask].reset_index()
        if len(today_bars) < 2:
            continue
        for j in range(1, len(today_bars)):
            prev_close = float(today_bars.loc[j - 1, "close"])
            curr_close = float(today_bars.loc[j, "close"])
            orig_idx = int(today_bars.loc[j, "index"])
            if orig_idx < ATR_WINDOW or orig_idx >= max_idx:
                continue
            atr_t = atr[orig_idx]
            if not np.isfinite(atr_t) or atr_t <= 0:
                continue

            direction: int = 0
            if prev_close < val - tick and curr_close >= val:
                direction = +1
            elif prev_close > vah + tick and curr_close <= vah:
                direction = -1
            if direction == 0:
                continue

            distance_atr = abs(curr_close - poc) / atr_t
            bucket = bucket_of(distance_atr)
            if bucket is None:
                continue

            for struct_name, (_desc, fn) in STRUCTURES.items():
                pnl = fn(highs, lows, closes, orig_idx, curr_close, poc, val, vah,
                        direction, atr_t, distance_atr)
                stats.setdefault((struct_name, bucket), BucketAgg()).add(pnl)

    return ContractResult(contract=contract, symbol=symbol, sector=sector, stats=stats)


def aggregate_by_sector(
    results: list[ContractResult],
) -> dict[str, dict[tuple[str, str], BucketAgg]]:
    agg: dict[str, dict[tuple[str, str], BucketAgg]] = {}
    for r in results:
        sector_agg = agg.setdefault(r.sector, {})
        for key, ba in r.stats.items():
            tgt = sector_agg.setdefault(key, BucketAgg())
            tgt.n += ba.n
            tgt.pnl_sum += ba.pnl_sum
            tgt.pnl_sq_sum += ba.pnl_sq_sum
            tgt.n_pos += ba.n_pos
    return agg


def render_markdown(results: list[ContractResult]) -> str:
    lines: list[str] = []
    lines.append(f"# Stage 1.5-A4 · 多结构敏感性 (run {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n")
    lines.append(f"DISTANCE_BUCKETS(ATR) = {[name for _, _, name in DISTANCE_BUCKETS]}, "
                 f"TIME_LIMIT = {TIME_LIMIT}, COST = {COST_ATR_ROUND_TRIP} ATR/双边\n")
    lines.append("### 结构说明\n")
    for name, (desc, _) in STRUCTURES.items():
        lines.append(f"- **{name}**: {desc}")
    lines.append("")

    sec_agg = aggregate_by_sector(results)

    # 每板块一个矩阵表：行 = 距离档，列 = 结构，值 = avg_pnl_net
    for sector in sorted(sec_agg.keys()):
        lines.append(f"## {sector} · 期望净值 (ATR/笔) 矩阵\n")
        header = "| 距离档 | 事件数 | " + " | ".join(STRUCTURES.keys()) + " |"
        sep = "|---|---|" + "|".join("---" for _ in STRUCTURES) + "|"
        lines.append(header)
        lines.append(sep)
        for _, _, bname in DISTANCE_BUCKETS:
            # 事件数在任意结构下都相同（同一批事件），取 S1
            key_s1 = ("S1_baseline", bname)
            if key_s1 not in sec_agg[sector]:
                continue
            n = sec_agg[sector][key_s1].n
            if n < 20:
                continue
            cells = [f"{n}"]
            for struct_name in STRUCTURES.keys():
                key = (struct_name, bname)
                if key not in sec_agg[sector]:
                    cells.append("-")
                    continue
                s = sec_agg[sector][key].summary(COST_ATR_ROUND_TRIP)
                cells.append(f"{s['avg_pnl_net']:+.3f}")
            lines.append(f"| {bname} | " + " | ".join(cells) + " |")
        lines.append("")

        # 每格胜率（备查）
        lines.append(f"### {sector} · 胜率 (%)\n")
        header = "| 距离档 | " + " | ".join(STRUCTURES.keys()) + " |"
        sep = "|---|" + "|".join("---" for _ in STRUCTURES) + "|"
        lines.append(header)
        lines.append(sep)
        for _, _, bname in DISTANCE_BUCKETS:
            key_s1 = ("S1_baseline", bname)
            if key_s1 not in sec_agg[sector] or sec_agg[sector][key_s1].n < 20:
                continue
            cells = []
            for struct_name in STRUCTURES.keys():
                key = (struct_name, bname)
                if key not in sec_agg[sector]:
                    cells.append("-")
                    continue
                s = sec_agg[sector][key].summary(COST_ATR_ROUND_TRIP)
                cells.append(f"{s['win_rate']:.1%}")
            lines.append(f"| {bname} | " + " | ".join(cells) + " |")
        lines.append("")

    # 每距离档最优结构（跨板块）
    lines.append("## 每距离档 · 最优结构（跨板块）\n")
    lines.append("| 板块 | 距离档 | 最优结构 | 最优期望净值 | 最差期望净值 | 敏感性 (max-min) |")
    lines.append("|---|---|---|---|---|---|")
    for sector in sorted(sec_agg.keys()):
        for _, _, bname in DISTANCE_BUCKETS:
            key_s1 = ("S1_baseline", bname)
            if key_s1 not in sec_agg[sector] or sec_agg[sector][key_s1].n < 20:
                continue
            values: list[tuple[str, float]] = []
            for struct_name in STRUCTURES.keys():
                key = (struct_name, bname)
                if key not in sec_agg[sector]:
                    continue
                s = sec_agg[sector][key].summary(COST_ATR_ROUND_TRIP)
                values.append((struct_name, s["avg_pnl_net"]))
            if not values:
                continue
            best = max(values, key=lambda x: x[1])
            worst = min(values, key=lambda x: x[1])
            sensitivity = best[1] - worst[1]
            lines.append(
                f"| {sector} | {bname} | {best[0]} | {best[1]:+.3f} | {worst[1]:+.3f} | {sensitivity:.3f} |"
            )
    lines.append("")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 1.5-A4: multi-structure sensitivity.")
    parser.add_argument("--csv-root", default=str(CSV_ROOT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--contracts", nargs="*", default=None)
    args = parser.parse_args()

    csv_root = Path(args.csv_root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_csvs = sorted(csv_root.glob("*.tqsdk.5m.csv"))
    results: list[ContractResult] = []
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
        r = analyze_contract(csv_path)
        if r is None:
            print("  skipped")
            continue
        n_events = sum(a.n for a in r.stats.values()) // len(STRUCTURES)
        print(f"  events={n_events}")
        results.append(r)

    if not results:
        print("no results")
        return

    md = render_markdown(results)
    md_path = output_dir / "stage1_5_A4_multi_structure.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"wrote {md_path}")

    json_path = output_dir / "stage1_5_A4_multi_structure.json"
    json_path.write_text(
        json.dumps([r.to_dict() for r in results], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"wrote {json_path}")


if __name__ == "__main__":
    main()
