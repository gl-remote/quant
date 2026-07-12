#!/usr/bin/env python3
"""
文件级元信息：
- 创建背景：子实验 A ATR 版本发现 POC 距离-到达率函数在 ATR 单位下跨板块重合，
  推断 VA reacceptance 事件平均落在"过近区" (0.5-1.0 ATR)，导致结构 edge 相对
  高 baseline 占比不高。本脚本直接验证该推断。
- 用途：扫描阶段 1 的 reacceptance 事件（前日 VA/POC，close 从 VA 外侧穿回内侧），
  记录每个事件的 ATR 距离档，输出:
  1) 事件在各 ATR 距离档的分布（占比）
  2) 各距离档下的 reach_rate（N=20/40）与子实验 A 的 baseline 对比
  3) 板块 × 距离档矩阵
- 注意事项：
  - 事件定义与阶段 1 一致（bar close 从 VA 外穿回内）
  - 使用相同 ATR 计算（20-bar rolling TR SMA）
  - baseline 从 stage1_5_A_distance_reach_atr.json 读取
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
DEFAULT_OUTPUT_DIR = Path("project_data/analysis/rolling_reacceptance_stage1_5")
BASELINE_JSON = DEFAULT_OUTPUT_DIR / "stage1_5_A_distance_reach_atr.json"

DISTANCE_BUCKETS: list[tuple[float, float, str]] = [
    (0.0, 0.2, "0-0.2"),
    (0.2, 0.5, "0.2-0.5"),
    (0.5, 1.0, "0.5-1.0"),
    (1.0, 1.5, "1.0-1.5"),
    (1.5, 2.5, "1.5-2.5"),
    (2.5, 4.0, "2.5-4.0"),
    (4.0, 1e9, "4.0+"),
]
OBSERVE_BARS: tuple[int, ...] = (5, 10, 20, 40, 80)
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


@dataclass
class BucketStat:
    n_events: int = 0
    reached: dict[int, int] = field(default_factory=dict)
    distances: list[float] = field(default_factory=list)  # ATR 单位

    def add(self, dist_atr: float, reached_flags: dict[int, bool]) -> None:
        self.n_events += 1
        self.distances.append(dist_atr)
        for n, flag in reached_flags.items():
            self.reached[n] = self.reached.get(n, 0) + (1 if flag else 0)

    def rate(self, n: int) -> float:
        if self.n_events == 0:
            return 0.0
        return self.reached.get(n, 0) / self.n_events


@dataclass
class ContractResult:
    contract: str
    symbol: str
    sector: str
    avg_atr: float
    n_events_total: int
    buckets: dict[str, BucketStat]

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": self.contract, "symbol": self.symbol, "sector": self.sector,
            "avg_atr": self.avg_atr, "n_events_total": self.n_events_total,
            "buckets": {
                name: {
                    "n_events": s.n_events,
                    "reach_rate": {n: s.rate(n) for n in OBSERVE_BARS},
                    "avg_distance_atr": float(np.mean(s.distances)) if s.distances else 0.0,
                }
                for name, s in self.buckets.items()
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
    date_to_prev_profile: dict[date, tuple[float, float, float]] = {}
    for i in range(1, len(dates_sorted)):
        date_to_prev_profile[dates_sorted[i]] = daily_profile[dates_sorted[i - 1]]

    buckets: dict[str, BucketStat] = {name: BucketStat() for _, _, name in DISTANCE_BUCKETS}

    max_idx = len(bars) - max(OBSERVE_BARS) - 1
    highs = bars["high"].to_numpy()
    lows = bars["low"].to_numpy()
    closes = bars["close"].to_numpy()
    dates_arr = bars["date"].to_numpy()

    n_total = 0
    atr_samples: list[float] = []

    # 扫描 reacceptance 事件
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
            entry = curr_close
            # Reaccept_L
            if prev_close < val - tick and curr_close >= val:
                direction = +1
            elif prev_close > vah + tick and curr_close <= vah:
                direction = -1
            if direction == 0:
                continue

            distance_atr = abs(entry - poc) / atr_t
            bucket = bucket_of(distance_atr)
            if bucket is None:
                continue

            reached_flags: dict[int, bool] = {}
            for n in OBSERVE_BARS:
                end = min(orig_idx + n, len(bars) - 1)
                if orig_idx + 1 > end:
                    reached_flags[n] = False
                    continue
                fw_highs = highs[orig_idx + 1: end + 1]
                fw_lows = lows[orig_idx + 1: end + 1]
                if direction == +1:
                    reached_flags[n] = bool((fw_highs >= poc).any())
                else:
                    reached_flags[n] = bool((fw_lows <= poc).any())
            buckets[bucket].add(distance_atr, reached_flags)
            n_total += 1
            atr_samples.append(atr_t)

    return ContractResult(
        contract=contract, symbol=symbol, sector=sector,
        avg_atr=float(np.mean(atr_samples)) if atr_samples else 0.0,
        n_events_total=n_total, buckets=buckets,
    )


def aggregate_by_sector(results: list[ContractResult]) -> dict[str, dict[str, BucketStat]]:
    agg: dict[str, dict[str, BucketStat]] = {}
    for r in results:
        sector_agg = agg.setdefault(r.sector, {name: BucketStat() for _, _, name in DISTANCE_BUCKETS})
        for name, stat in r.buckets.items():
            target = sector_agg[name]
            target.n_events += stat.n_events
            for n, cnt in stat.reached.items():
                target.reached[n] = target.reached.get(n, 0) + cnt
            target.distances.extend(stat.distances)
    return agg


def load_baseline() -> dict[str, dict[str, dict[str, Any]]]:
    """从子实验 A 的 ATR 版本 JSON 加载 baseline reach_rate（按板块聚合）。"""
    if not BASELINE_JSON.exists():
        return {}
    raw = json.loads(BASELINE_JSON.read_text(encoding="utf-8"))
    sector_agg: dict[str, dict[str, dict[str, Any]]] = {}
    for r in raw:
        sector = r["sector"]
        s = sector_agg.setdefault(sector, {name: {"n_samples": 0, "reach_rate_sum": {n: 0.0 for n in OBSERVE_BARS}} for _, _, name in DISTANCE_BUCKETS})
        for name, bucket in r["buckets"].items():
            n = bucket["n_samples"]
            s[name]["n_samples"] += n
            for k, v in bucket["reach_rate"].items():
                if int(k) in OBSERVE_BARS:
                    s[name]["reach_rate_sum"][int(k)] += v * n
    # 归一化为加权 rate
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for sector, buckets in sector_agg.items():
        result[sector] = {}
        for name, info in buckets.items():
            n = info["n_samples"]
            result[sector][name] = {
                "n_samples": n,
                "reach_rate": {k: (v / n if n > 0 else 0.0) for k, v in info["reach_rate_sum"].items()},
            }
    return result


def render_markdown(results: list[ContractResult]) -> str:
    lines: list[str] = []
    lines.append(f"# Stage 1.5-A2 · Reacceptance 事件的 ATR 距离档分布 (run {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n")

    sector_agg = aggregate_by_sector(results)
    baseline = load_baseline()

    # 1. 事件分布：板块 × 距离档
    lines.append("## 1. Reacceptance 事件在 ATR 距离档的分布（占比）\n")
    header = "| sector | 总事件数 | " + " | ".join(name for _, _, name in DISTANCE_BUCKETS) + " |"
    sep = "|---|---|" + "|".join("---" for _ in DISTANCE_BUCKETS) + "|"
    lines.append(header)
    lines.append(sep)
    for sector in sorted(sector_agg.keys()):
        total = sum(sector_agg[sector][name].n_events for _, _, name in DISTANCE_BUCKETS)
        cells = [str(total)]
        for _, _, name in DISTANCE_BUCKETS:
            n = sector_agg[sector][name].n_events
            pct = n / total * 100 if total > 0 else 0
            cells.append(f"{pct:.1f}% ({n})")
        lines.append(f"| {sector} | " + " | ".join(cells) + " |")
    lines.append("")

    # 2. 各距离档 reach_rate vs baseline
    lines.append("## 2. Reacceptance 事件各距离档 · N=20 到达率 vs baseline\n")
    lines.append("| sector | 距离档 | 事件数 | reach_rate | baseline | Δ (事件 - baseline) |")
    lines.append("|---|---|---|---|---|---|")
    for sector in sorted(sector_agg.keys()):
        for _, _, name in DISTANCE_BUCKETS:
            stat = sector_agg[sector][name]
            if stat.n_events < 20:
                continue
            event_rate = stat.rate(20)
            base_rate = baseline.get(sector, {}).get(name, {}).get("reach_rate", {}).get(20, 0.0)
            delta = event_rate - base_rate
            lines.append(
                f"| {sector} | {name} | {stat.n_events} | {event_rate:.3f} | {base_rate:.3f} | {delta:+.3f} |"
            )
    lines.append("")

    # 3. 平均 ATR 距离
    lines.append("## 3. 板块 · reacceptance 事件平均 ATR 距离\n")
    lines.append("| sector | 总事件 | 平均距离(ATR) | 中位距离(ATR) |")
    lines.append("|---|---|---|---|")
    for sector in sorted(sector_agg.keys()):
        all_dists: list[float] = []
        for _, _, name in DISTANCE_BUCKETS:
            all_dists.extend(sector_agg[sector][name].distances)
        if all_dists:
            lines.append(
                f"| {sector} | {len(all_dists)} | {np.mean(all_dists):.3f} | {np.median(all_dists):.3f} |"
            )
    lines.append("")

    # 4. 多 N 到达率对比（板块甜蜜区档 1.5-2.5）
    lines.append("## 4. Reacceptance 事件 in 距离档 1.5-2.5 ATR（甜蜜区）· 多 N 到达率\n")
    header = "| sector | 事件数 | " + " | ".join(f"N={n}" for n in OBSERVE_BARS) + " | baseline N=20 | Δ N=20 |"
    sep = "|---|---|" + "|".join("---" for _ in OBSERVE_BARS) + "|---|---|"
    lines.append(header)
    lines.append(sep)
    for sector in sorted(sector_agg.keys()):
        stat = sector_agg[sector]["1.5-2.5"]
        if stat.n_events < 20:
            continue
        rates = " | ".join(f"{stat.rate(n):.3f}" for n in OBSERVE_BARS)
        base_20 = baseline.get(sector, {}).get("1.5-2.5", {}).get("reach_rate", {}).get(20, 0.0)
        delta = stat.rate(20) - base_20
        lines.append(f"| {sector} | {stat.n_events} | {rates} | {base_20:.3f} | {delta:+.3f} |")
    lines.append("")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Reacceptance events distribution across ATR distance buckets.")
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
        print(f"  n_events={r.n_events_total}, avg_atr={r.avg_atr:.4f}")
        results.append(r)

    if not results:
        print("no results")
        return

    md = render_markdown(results)
    md_path = output_dir / "stage1_5_A2_reacceptance_distance_dist.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"wrote {md_path}")

    json_path = output_dir / "stage1_5_A2_reacceptance_distance_dist.json"
    json_path.write_text(
        json.dumps([r.to_dict() for r in results], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"wrote {json_path}")


if __name__ == "__main__":
    main()
