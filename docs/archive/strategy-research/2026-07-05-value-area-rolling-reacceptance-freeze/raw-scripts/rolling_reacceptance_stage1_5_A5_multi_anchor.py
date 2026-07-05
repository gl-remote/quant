#!/usr/bin/env python3
"""
文件级元信息：
- 创建背景：A/A2/A3/A4 全部假设 POC 是特殊的引力点，但从未验证 POC 与其他显著价格点
  相比的独特性。用户提出证伪实验：如果任意锚点都有类似的距离-到达率函数，那"POC 引力"
  只是均值回归的普遍现象，策略假设失败。
- 用途：对每根 bar 同时计算多种锚点（POC / VAH / VAL / Runner-up POC / PrevClose /
  PrevMid / PriceMedian）的距离与到达率，按 ATR 距离档聚合，判断 POC 曲线是否显著
  优于其他锚点。
- 注意事项：
  - 所有锚点用同一批 bar，跨锚点可比
  - 距离档同 A2/A3：0-0.5, 0.5-1.0, 1.0-1.5, 1.5-2.5, 2.5-4.0, 4.0+ ATR
  - N=20 作为主观察窗口（沿用之前设定）
  - 若 POC 与其他锚点曲线重合 → 结果落地为"POC 假设证伪"，主题需重新定位
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

DISTANCE_BUCKETS: list[tuple[float, float, str]] = [
    (0.0, 0.5, "0-0.5"),
    (0.5, 1.0, "0.5-1.0"),
    (1.0, 1.5, "1.0-1.5"),
    (1.5, 2.5, "1.5-2.5"),
    (2.5, 4.0, "2.5-4.0"),
    (4.0, 1e9, "4.0+"),
]
OBSERVE_N = 20
VA_RATIO = 0.7
ATR_WINDOW = 20

ANCHOR_NAMES: list[str] = [
    "POC",
    "VAH",
    "VAL",
    "RunnerUpPOC",
    "PrevClose",
    "PrevMid",
    "PriceMedian",
]

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


@dataclass
class DailyAnchors:
    poc: float
    val: float
    vah: float
    runner_up_poc: float
    prev_close: float
    prev_mid: float
    price_median: float


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


def compute_daily_anchors(day_bars: pd.DataFrame, tick: float, ratio: float) -> DailyAnchors | None:
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

    # POC = 最大 volume 桶
    poc_idx = int(bucket_vol.argmax())
    poc_price = unique[poc_idx] * tick

    # Runner-up POC = 第二大 volume 桶（要求与 POC 距离 >= 3 ticks，避免相邻粘连）
    order = np.argsort(bucket_vol)[::-1]
    runner_up_price = poc_price
    for cand_idx in order[1:]:
        cand_price = unique[cand_idx] * tick
        if abs(cand_price - poc_price) >= 3 * tick:
            runner_up_price = cand_price
            break

    # VA 贪心扩张
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

    # 时间锚点
    prev_close = float(day_bars["close"].iloc[-1])
    prev_high = float(day_bars["high"].max())
    prev_low = float(day_bars["low"].min())
    prev_mid = (prev_high + prev_low) / 2

    # 价格中位数（不加权 volume）
    price_median = float(np.median(prices))

    return DailyAnchors(
        poc=poc_price, val=val, vah=vah,
        runner_up_poc=runner_up_price,
        prev_close=prev_close, prev_mid=prev_mid, price_median=price_median,
    )


def bucket_of(distance_atr: float) -> str | None:
    for lo, hi, name in DISTANCE_BUCKETS:
        if lo <= distance_atr < hi:
            return name
    return None


@dataclass
class BucketStat:
    n: int = 0
    reached: int = 0

    def rate(self) -> float:
        return self.reached / self.n if self.n > 0 else 0.0


@dataclass
class ContractResult:
    contract: str
    symbol: str
    sector: str
    # {anchor_name: {bucket_name: BucketStat}}
    stats: dict[str, dict[str, BucketStat]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": self.contract, "symbol": self.symbol, "sector": self.sector,
            "stats": {
                anchor: {b: {"n": s.n, "reach_rate": s.rate()} for b, s in bs.items()}
                for anchor, bs in self.stats.items()
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

    daily: dict[date, DailyAnchors] = {}
    for day, day_df in bars.groupby("date", sort=True):
        r = compute_daily_anchors(day_df, tick=tick, ratio=VA_RATIO)
        if r is not None:
            daily[day] = r

    dates_sorted = sorted(daily.keys())
    date_to_prev: dict[date, DailyAnchors] = {}
    for i in range(1, len(dates_sorted)):
        date_to_prev[dates_sorted[i]] = daily[dates_sorted[i - 1]]

    highs = bars["high"].to_numpy()
    lows = bars["low"].to_numpy()
    closes = bars["close"].to_numpy()
    dates_arr = bars["date"].to_numpy()

    max_idx = len(bars) - OBSERVE_N - 1

    stats: dict[str, dict[str, BucketStat]] = {
        anchor: {b: BucketStat() for _, _, b in DISTANCE_BUCKETS} for anchor in ANCHOR_NAMES
    }

    for idx in range(ATR_WINDOW, max_idx):
        d = bars.loc[idx, "date"]
        if d not in date_to_prev:
            continue
        atr_t = atr[idx]
        if not np.isfinite(atr_t) or atr_t <= 0:
            continue
        anchors = date_to_prev[d]
        anchor_values = {
            "POC": anchors.poc,
            "VAH": anchors.vah,
            "VAL": anchors.val,
            "RunnerUpPOC": anchors.runner_up_poc,
            "PrevClose": anchors.prev_close,
            "PrevMid": anchors.prev_mid,
            "PriceMedian": anchors.price_median,
        }

        close = float(closes[idx])
        # 未来 N bar 的 high/low
        end = min(idx + OBSERVE_N, len(bars) - 1)
        fw_highs = highs[idx + 1: end + 1]
        fw_lows = lows[idx + 1: end + 1]
        if fw_highs.size == 0:
            continue

        for anchor_name, anchor_price in anchor_values.items():
            diff = close - anchor_price
            if abs(diff) < tick / 2:
                continue
            side = -1 if diff > 0 else +1
            distance_atr = abs(diff) / atr_t
            bucket = bucket_of(distance_atr)
            if bucket is None:
                continue

            if side == +1:
                reached = bool((fw_highs >= anchor_price).any())
            else:
                reached = bool((fw_lows <= anchor_price).any())

            stat = stats[anchor_name][bucket]
            stat.n += 1
            if reached:
                stat.reached += 1

    return ContractResult(contract=contract, symbol=symbol, sector=sector, stats=stats)


def aggregate_by_sector(
    results: list[ContractResult],
) -> dict[str, dict[str, dict[str, BucketStat]]]:
    """sector -> anchor -> bucket -> stat"""
    agg: dict[str, dict[str, dict[str, BucketStat]]] = {}
    for r in results:
        sec = agg.setdefault(r.sector, {
            anchor: {b: BucketStat() for _, _, b in DISTANCE_BUCKETS} for anchor in ANCHOR_NAMES
        })
        for anchor, buckets in r.stats.items():
            for bname, s in buckets.items():
                target = sec[anchor][bname]
                target.n += s.n
                target.reached += s.reached
    return agg


def render_markdown(results: list[ContractResult]) -> str:
    lines: list[str] = []
    lines.append(f"# Stage 1.5-A5 · 多锚点引力对比 (run {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n")
    lines.append(f"OBSERVE_N = {OBSERVE_N}, ATR_WINDOW = {ATR_WINDOW}\n")
    lines.append("### 锚点说明\n")
    anchor_docs = {
        "POC": "前日 volume 分布众数（最高峰）",
        "VAH": "前日 VA 上边界",
        "VAL": "前日 VA 下边界",
        "RunnerUpPOC": "前日 volume 第 2 大桶（次峰，距 POC ≥3 ticks）",
        "PrevClose": "前日收盘价（时间锚，非分布）",
        "PrevMid": "前日 (H+L)/2（对称时间锚）",
        "PriceMedian": "前日 5m close 序列中位数（非 volume 加权分布）",
    }
    for name, desc in anchor_docs.items():
        lines.append(f"- **{name}**: {desc}")
    lines.append("")

    sec_agg = aggregate_by_sector(results)

    # 每板块：锚点 × 距离档 · reach_rate 矩阵
    for sector in sorted(sec_agg.keys()):
        lines.append(f"## {sector} · N={OBSERVE_N} reach_rate 矩阵\n")
        header = "| anchor | " + " | ".join(name for _, _, name in DISTANCE_BUCKETS) + " |"
        sep = "|---|" + "|".join("---" for _ in DISTANCE_BUCKETS) + "|"
        lines.append(header)
        lines.append(sep)
        for anchor in ANCHOR_NAMES:
            cells = []
            for _, _, bname in DISTANCE_BUCKETS:
                s = sec_agg[sector][anchor][bname]
                if s.n < 50:
                    cells.append("-")
                else:
                    cells.append(f"{s.rate():.3f}")
            lines.append(f"| {anchor} | " + " | ".join(cells) + " |")
        lines.append("")

        # POC 相对其他锚点的差值
        lines.append(f"### {sector} · POC - 其他锚点 reach_rate 差值\n")
        header = "| anchor | " + " | ".join(name for _, _, name in DISTANCE_BUCKETS) + " |"
        lines.append(header)
        lines.append(sep)
        for anchor in ANCHOR_NAMES:
            if anchor == "POC":
                continue
            cells = []
            for _, _, bname in DISTANCE_BUCKETS:
                s_poc = sec_agg[sector]["POC"][bname]
                s_other = sec_agg[sector][anchor][bname]
                if s_poc.n < 50 or s_other.n < 50:
                    cells.append("-")
                else:
                    delta = s_poc.rate() - s_other.rate()
                    cells.append(f"{delta:+.3f}")
            lines.append(f"| POC - {anchor} | " + " | ".join(cells) + " |")
        lines.append("")

    # 跨板块聚合：所有 sector 合并（可选）
    lines.append("## 跨板块聚合：锚点 × 距离档 · reach_rate\n")
    header = "| anchor | " + " | ".join(name for _, _, name in DISTANCE_BUCKETS) + " |"
    lines.append(header)
    lines.append(sep)
    total_agg: dict[str, dict[str, BucketStat]] = {
        anchor: {b: BucketStat() for _, _, b in DISTANCE_BUCKETS} for anchor in ANCHOR_NAMES
    }
    for sector, anchors in sec_agg.items():
        for anchor, buckets in anchors.items():
            for bname, s in buckets.items():
                t = total_agg[anchor][bname]
                t.n += s.n
                t.reached += s.reached
    for anchor in ANCHOR_NAMES:
        cells = []
        for _, _, bname in DISTANCE_BUCKETS:
            s = total_agg[anchor][bname]
            if s.n < 100:
                cells.append("-")
            else:
                cells.append(f"{s.rate():.3f}")
        lines.append(f"| {anchor} | " + " | ".join(cells) + " |")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 1.5-A5: multi-anchor gravitation comparison.")
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
        total = sum(s.n for anchors in r.stats.values() for s in anchors.values()) // len(ANCHOR_NAMES)
        print(f"  avg bars per anchor: {total}")
        results.append(r)

    if not results:
        print("no results")
        return

    md = render_markdown(results)
    md_path = output_dir / "stage1_5_A5_multi_anchor.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"wrote {md_path}")

    json_path = output_dir / "stage1_5_A5_multi_anchor.json"
    json_path.write_text(
        json.dumps([r.to_dict() for r in results], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"wrote {json_path}")


if __name__ == "__main__":
    main()
