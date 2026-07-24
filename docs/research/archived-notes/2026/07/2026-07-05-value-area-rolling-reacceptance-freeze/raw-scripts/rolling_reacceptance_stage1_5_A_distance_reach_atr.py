#!/usr/bin/env python3
"""
文件级元信息：
- 创建背景：子实验 A（ticks 版本）发现板块间距离-到达率函数差异，但 tick 是绝对
  单位，跨品种不可比，且未考虑波动率。用户提出用 ATR 修正距离以消除品种波动率
  异质性影响。
- 用途：与 rolling_reacceptance_stage1_5_A_distance_reach.py 逻辑一致，但把距离
  分桶单位从 ticks 改为 ATR（distance = |close - poc| / atr_20bar）。用于验证
  ticks 版本的板块画像是否稳健。
- 注意事项：
  - ATR 用 20-bar rolling True Range 均值，每根 bar 独立。
  - ATR < min_atr (0 或极小值) 时跳过。
  - ATR 分桶：0-0.2, 0.2-0.5, 0.5-1.0, 1.0-1.5, 1.5-2.5, 2.5-4.0, 4.0+，覆盖
    从"次级噪声"到"多倍日内波动"的完整光谱。
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

# ATR 距离桶（ATR 单位）
DISTANCE_BUCKETS: list[tuple[float, float, str]] = [
    (0.0, 0.2, "0-0.2"),
    (0.2, 0.5, "0.2-0.5"),
    (0.5, 1.0, "0.5-1.0"),
    (1.0, 1.5, "1.0-1.5"),
    (1.5, 2.5, "1.5-2.5"),
    (2.5, 4.0, "2.5-4.0"),
    (4.0, 1e9, "4.0+"),
]
OBSERVE_BARS: tuple[int, ...] = (5, 10, 20, 40, 80, 160)
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
    """经典 ATR = SMA(TR, window)，返回长度 = len(bars) 的数组，前 window-1 项为 NaN。"""
    high = bars["high"].to_numpy()
    low = bars["low"].to_numpy()
    close = bars["close"].to_numpy()
    prev_close = np.concatenate([[close[0]], close[:-1]])
    tr = np.maximum.reduce([
        high - low,
        np.abs(high - prev_close),
        np.abs(low - prev_close),
    ])
    # SMA
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
    val = unique[lo] * tick
    vah = unique[hi] * tick
    return poc_price, val, vah


def bucket_of(distance_atr: float) -> str | None:
    for lo, hi, name in DISTANCE_BUCKETS:
        if lo <= distance_atr < hi:
            return name
    return None


@dataclass
class BucketStat:
    n_samples: int = 0
    reached: dict[int, int] = field(default_factory=dict)

    def add_bar(self, reached_flags: dict[int, bool]) -> None:
        self.n_samples += 1
        for n, flag in reached_flags.items():
            self.reached[n] = self.reached.get(n, 0) + (1 if flag else 0)

    def rate(self, n: int) -> float:
        if self.n_samples == 0:
            return 0.0
        return self.reached.get(n, 0) / self.n_samples


@dataclass
class ContractResult:
    contract: str
    symbol: str
    sector: str
    tick: float
    avg_atr: float
    n_bars: int
    buckets: dict[str, BucketStat]

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": self.contract,
            "symbol": self.symbol,
            "sector": self.sector,
            "tick": self.tick,
            "avg_atr": self.avg_atr,
            "n_bars": self.n_bars,
            "buckets": {
                name: {
                    "n_samples": s.n_samples,
                    "reach_rate": {n: s.rate(n) for n in OBSERVE_BARS},
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

    atr_samples: list[float] = []

    for idx in range(ATR_WINDOW, max_idx):
        d = bars.loc[idx, "date"]
        if d not in date_to_prev_profile:
            continue
        atr_t = atr[idx]
        if not np.isfinite(atr_t) or atr_t <= 0:
            continue
        poc, _val, _vah = date_to_prev_profile[d]
        close = float(closes[idx])
        diff = close - poc
        if abs(diff) < tick / 2:
            continue
        side = -1 if diff > 0 else +1
        distance_atr = abs(diff) / atr_t
        bucket = bucket_of(distance_atr)
        if bucket is None:
            continue
        atr_samples.append(atr_t)

        reached_flags: dict[int, bool] = {}
        for n in OBSERVE_BARS:
            end = min(idx + n, len(bars) - 1)
            if idx + 1 > end:
                reached_flags[n] = False
                continue
            fw_highs = highs[idx + 1: end + 1]
            fw_lows = lows[idx + 1: end + 1]
            if side == +1:
                reached_flags[n] = bool((fw_highs >= poc).any())
            else:
                reached_flags[n] = bool((fw_lows <= poc).any())
        buckets[bucket].add_bar(reached_flags)

    return ContractResult(
        contract=contract, symbol=symbol, sector=sector, tick=tick,
        avg_atr=float(np.mean(atr_samples)) if atr_samples else 0.0,
        n_bars=len(bars), buckets=buckets,
    )


def aggregate_by_sector(results: list[ContractResult]) -> dict[str, dict[str, BucketStat]]:
    agg: dict[str, dict[str, BucketStat]] = {}
    for r in results:
        sector_agg = agg.setdefault(r.sector, {name: BucketStat() for _, _, name in DISTANCE_BUCKETS})
        for name, stat in r.buckets.items():
            target = sector_agg[name]
            target.n_samples += stat.n_samples
            for n, cnt in stat.reached.items():
                target.reached[n] = target.reached.get(n, 0) + cnt
    return agg


def render_markdown(results: list[ContractResult]) -> str:
    lines: list[str] = []
    lines.append(f"# Stage 1.5-A · 距离-到达率函数 (ATR 修正版本) (run {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n")
    lines.append(
        f"OBSERVE_BARS = {OBSERVE_BARS}, VA_RATIO = {VA_RATIO}, ATR_WINDOW = {ATR_WINDOW}\n"
        f"DISTANCE_BUCKETS(ATR units) = {[name for _, _, name in DISTANCE_BUCKETS]}\n"
    )

    lines.append("## 1. 板块聚合：距离(ATR)-到达率-时间表\n")
    sector_agg = aggregate_by_sector(results)
    for sector in sorted(sector_agg.keys()):
        lines.append(f"### {sector}\n")
        header = "| distance (ATR) | n_samples | " + " | ".join(f"N={n}" for n in OBSERVE_BARS) + " |"
        sep = "|---|---|" + "|".join("---" for _ in OBSERVE_BARS) + "|"
        lines.append(header)
        lines.append(sep)
        for _, _, name in DISTANCE_BUCKETS:
            stat = sector_agg[sector][name]
            if stat.n_samples == 0:
                continue
            rates = " | ".join(f"{stat.rate(n):.3f}" for n in OBSERVE_BARS)
            lines.append(f"| {name} | {stat.n_samples} | {rates} |")
        lines.append("")

    lines.append("## 2. 板块 × 距离(ATR) · N=20 到达率对比\n")
    header = "| sector | " + " | ".join(name for _, _, name in DISTANCE_BUCKETS) + " |"
    sep = "|---|" + "|".join("---" for _ in DISTANCE_BUCKETS) + "|"
    lines.append(header)
    lines.append(sep)
    for sector in sorted(sector_agg.keys()):
        cells = []
        for _, _, name in DISTANCE_BUCKETS:
            stat = sector_agg[sector][name]
            if stat.n_samples < 50:
                cells.append("-")
            else:
                cells.append(f"{stat.rate(20):.3f}")
        lines.append(f"| {sector} | " + " | ".join(cells) + " |")
    lines.append("")

    lines.append("## 3. 各合约平均 ATR（用于诊断，检查 ATR 单位是否稳定）\n")
    lines.append("| contract | sector | tick | avg_atr | avg_atr_ticks |")
    lines.append("|---|---|---|---|---|")
    for r in sorted(results, key=lambda x: (x.sector, x.contract)):
        lines.append(f"| {r.contract} | {r.sector} | {r.tick} | {r.avg_atr:.4f} | {r.avg_atr / r.tick:.1f} |")
    lines.append("")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 1.5-A ATR version: POC distance-reach function in ATR units.")
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
        total = sum(s.n_samples for s in r.buckets.values())
        print(f"  total bars analyzed: {total}, avg_atr={r.avg_atr:.4f}")
        results.append(r)

    if not results:
        print("no results")
        return

    md = render_markdown(results)
    md_path = output_dir / "stage1_5_A_distance_reach_atr.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"wrote {md_path}")

    json_path = output_dir / "stage1_5_A_distance_reach_atr.json"
    json_path.write_text(
        json.dumps([r.to_dict() for r in results], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"wrote {json_path}")


if __name__ == "__main__":
    main()
