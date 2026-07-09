#!/usr/bin/env python3
"""
文件级元信息：
- 创建背景：A2 发现 reacceptance edge 在远距离最强，但需要评估在真实交易语义下
  (止损 + 时间限制) 的期望净收益，而不只是 reach_rate。
- 用途：对每个 reacceptance 事件模拟三种交易路径（止损 / 止盈到 POC / 时间平仓），
  按板块 × ATR 距离档聚合胜率、平均盈亏、期望值，与 distance-matched baseline 对比。
- 注意事项：
  - 止损假设 s_atr ∈ {0.5, 1.0, 1.5} ATR，从 entry 反方向计
  - 时间窗口 N=80 bar
  - 用 bar 内 high/low 判定止损 / 止盈先触
  - 成本估算：单边佣金 + 滑点 ≈ 0.05 ATR / 笔（保守），双边 0.1 ATR
"""

from __future__ import annotations

import argparse
import json
import random
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
STOP_LOSS_ATRS: tuple[float, ...] = (0.5, 1.0, 1.5)
TIME_LIMIT = 80  # bars
COST_ATR_ROUND_TRIP = 0.1  # 双边成本
VA_RATIO = 0.7
ATR_WINDOW = 20
BASELINE_SEEDS = (1, 2, 3, 4, 5)

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


def simulate_trade(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    entry_idx: int,
    entry_price: float,
    poc: float,
    direction: int,
    atr_t: float,
    stop_atr: float,
    time_limit: int,
) -> tuple[str, float]:
    """
    模拟交易路径。返回 (outcome, pnl_in_atr)。
    outcome ∈ {"win", "loss", "timeout"}
    pnl_in_atr：以 ATR 为单位的浮盈浮亏（正 = 盈）
    """
    stop_price = entry_price - direction * stop_atr * atr_t  # direction=+1 时 stop 在下方
    end = min(entry_idx + time_limit, len(highs) - 1)
    for i in range(entry_idx + 1, end + 1):
        h = highs[i]
        low = lows[i]
        if direction == +1:
            # 先检查止损（保守：同 bar 内先触止损）
            if low <= stop_price:
                return "loss", -stop_atr
            if h >= poc:
                return "win", (poc - entry_price) / atr_t
        else:
            if h >= stop_price:
                return "loss", -stop_atr
            if low <= poc:
                return "win", (entry_price - poc) / atr_t
    # 时间平仓：按 end 的 close
    final_close = closes[end]
    pnl_price = (final_close - entry_price) * direction
    return "timeout", pnl_price / atr_t


@dataclass
class BucketAgg:
    n: int = 0
    n_win: int = 0
    n_loss: int = 0
    n_timeout: int = 0
    pnl_sum: float = 0.0
    pnl_sq_sum: float = 0.0
    distances: list[float] = field(default_factory=list)

    def add(self, outcome: str, pnl: float, dist: float) -> None:
        self.n += 1
        self.pnl_sum += pnl
        self.pnl_sq_sum += pnl * pnl
        self.distances.append(dist)
        if outcome == "win":
            self.n_win += 1
        elif outcome == "loss":
            self.n_loss += 1
        else:
            self.n_timeout += 1

    def summary(self, cost: float) -> dict[str, float]:
        if self.n == 0:
            return {"n": 0, "win_rate": 0.0, "loss_rate": 0.0, "timeout_rate": 0.0,
                    "avg_pnl": 0.0, "avg_pnl_net": 0.0, "std_pnl": 0.0, "avg_dist": 0.0}
        avg_pnl = self.pnl_sum / self.n
        var = max(self.pnl_sq_sum / self.n - avg_pnl * avg_pnl, 0.0)
        return {
            "n": self.n,
            "win_rate": self.n_win / self.n,
            "loss_rate": self.n_loss / self.n,
            "timeout_rate": self.n_timeout / self.n,
            "avg_pnl": avg_pnl,
            "avg_pnl_net": avg_pnl - cost,
            "std_pnl": var ** 0.5,
            "avg_dist": float(np.mean(self.distances)) if self.distances else 0.0,
        }


@dataclass
class ContractResult:
    contract: str
    symbol: str
    sector: str
    # 键：(stop_atr, distance_bucket) → BucketAgg
    reacceptance: dict[tuple[float, str], BucketAgg]
    baseline: dict[tuple[float, str], BucketAgg]

    def to_dict(self) -> dict[str, Any]:
        def dump(d: dict[tuple[float, str], BucketAgg]) -> dict[str, dict[str, float]]:
            out: dict[str, dict[str, float]] = {}
            for (s, b), agg in d.items():
                out[f"stop{s}_{b}"] = agg.summary(COST_ATR_ROUND_TRIP)
            return out
        return {
            "contract": self.contract, "symbol": self.symbol, "sector": self.sector,
            "reacceptance": dump(self.reacceptance),
            "baseline": dump(self.baseline),
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

    max_idx = len(bars) - TIME_LIMIT - 1
    highs = bars["high"].to_numpy()
    lows = bars["low"].to_numpy()
    closes = bars["close"].to_numpy()

    reacc: dict[tuple[float, str], BucketAgg] = {}
    baseline: dict[tuple[float, str], BucketAgg] = {}

    # Step 1: 扫描 reacceptance 事件并模拟交易
    reacceptance_events: list[tuple[int, float, float, int, float, str]] = []
    # (idx, entry, poc, direction, atr_t, bucket)

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
            reacceptance_events.append((orig_idx, curr_close, poc, direction, atr_t, bucket))
            for stop_atr in STOP_LOSS_ATRS:
                outcome, pnl = simulate_trade(
                    highs, lows, closes, orig_idx, curr_close, poc, direction, atr_t,
                    stop_atr, TIME_LIMIT,
                )
                key = (stop_atr, bucket)
                reacc.setdefault(key, BucketAgg()).add(outcome, pnl, distance_atr)

    # Step 2: baseline - 对每个 reacceptance 事件，找同方向、距 POC 距离相近的 bar 作为对照
    # 构建距离索引：{(side, distance_atr_bin): [(idx, poc, atr)]}
    # bin = 0.1 ATR 粒度
    dist_index: dict[tuple[int, int], list[tuple[int, float, float]]] = {}
    for idx in range(ATR_WINDOW, max_idx):
        d = bars.loc[idx, "date"]
        if d not in date_to_prev_profile:
            continue
        atr_t = atr[idx]
        if not np.isfinite(atr_t) or atr_t <= 0:
            continue
        poc_i, _val, _vah = date_to_prev_profile[d]
        close = float(closes[idx])
        diff = close - poc_i
        if abs(diff) < tick / 2:
            continue
        side = -1 if diff > 0 else +1
        dist_atr = abs(diff) / atr_t
        # 距离 bin：0.1 ATR 粒度
        bin_key = int(dist_atr * 10)
        dist_index.setdefault((side, bin_key), []).append((idx, poc_i, atr_t))

    # 对每个 reacceptance 事件采样 baseline
    for seed in BASELINE_SEEDS:
        rng = random.Random(seed)
        for orig_idx, entry, poc, direction, atr_t, bucket in reacceptance_events:
            dist_atr = abs(entry - poc) / atr_t
            bin_key = int(dist_atr * 10)
            # 容差 ±1 bin (0.1 ATR)
            candidates: list[tuple[int, float, float]] = []
            for delta in (-1, 0, 1):
                key = (direction, bin_key + delta)
                if key in dist_index:
                    candidates.extend(dist_index[key])
            candidates = [c for c in candidates if c[0] != orig_idx]
            if not candidates:
                continue
            new_idx, new_poc, new_atr = rng.choice(candidates)
            new_entry = float(closes[new_idx])
            for stop_atr in STOP_LOSS_ATRS:
                outcome, pnl = simulate_trade(
                    highs, lows, closes, new_idx, new_entry, new_poc, direction, new_atr,
                    stop_atr, TIME_LIMIT,
                )
                key = (stop_atr, bucket)
                baseline.setdefault(key, BucketAgg()).add(outcome, pnl, dist_atr)

    return ContractResult(
        contract=contract, symbol=symbol, sector=sector,
        reacceptance=reacc, baseline=baseline,
    )


def aggregate_by_sector(
    results: list[ContractResult],
    field_name: str,
) -> dict[str, dict[tuple[float, str], BucketAgg]]:
    agg: dict[str, dict[tuple[float, str], BucketAgg]] = {}
    for r in results:
        sector_agg = agg.setdefault(r.sector, {})
        source = getattr(r, field_name)
        for key, ba in source.items():
            target = sector_agg.setdefault(key, BucketAgg())
            target.n += ba.n
            target.n_win += ba.n_win
            target.n_loss += ba.n_loss
            target.n_timeout += ba.n_timeout
            target.pnl_sum += ba.pnl_sum
            target.pnl_sq_sum += ba.pnl_sq_sum
            target.distances.extend(ba.distances)
    return agg


def render_markdown(results: list[ContractResult]) -> str:
    lines: list[str] = []
    lines.append(f"# Stage 1.5-A3 · 期望值 / R:R 计算 (run {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n")
    lines.append(f"STOP_LOSS_ATRS = {STOP_LOSS_ATRS}, TIME_LIMIT = {TIME_LIMIT} bars, "
                 f"COST (round-trip, ATR) = {COST_ATR_ROUND_TRIP}\n")
    lines.append("模拟规则：进场后先判定止损（stop_atr × ATR 反向）与止盈（POC），"
                 "如果 TIME_LIMIT bar 内都没触发按 close 时间平仓。同 bar 内止损优先（保守）。\n")

    reacc_agg = aggregate_by_sector(results, "reacceptance")
    base_agg = aggregate_by_sector(results, "baseline")

    for stop_atr in STOP_LOSS_ATRS:
        lines.append(f"## Stop = {stop_atr} ATR\n")
        lines.append(f"### Reacceptance 事件（每距离档）\n")
        lines.append("| sector | 距离档 | n | win% | loss% | timeout% | avg_pnl (ATR) | avg_pnl_net (ATR) |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for sector in sorted(reacc_agg.keys()):
            for _, _, name in DISTANCE_BUCKETS:
                key = (stop_atr, name)
                if key not in reacc_agg[sector]:
                    continue
                s = reacc_agg[sector][key].summary(COST_ATR_ROUND_TRIP)
                if s["n"] < 20:
                    continue
                lines.append(
                    f"| {sector} | {name} | {int(s['n'])} | "
                    f"{s['win_rate']:.1%} | {s['loss_rate']:.1%} | {s['timeout_rate']:.1%} | "
                    f"{s['avg_pnl']:+.3f} | {s['avg_pnl_net']:+.3f} |"
                )
        lines.append("")

        lines.append(f"### Distance-matched Baseline（每距离档）\n")
        lines.append("| sector | 距离档 | n | win% | loss% | timeout% | avg_pnl (ATR) | avg_pnl_net (ATR) |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for sector in sorted(base_agg.keys()):
            for _, _, name in DISTANCE_BUCKETS:
                key = (stop_atr, name)
                if key not in base_agg[sector]:
                    continue
                s = base_agg[sector][key].summary(COST_ATR_ROUND_TRIP)
                if s["n"] < 50:
                    continue
                lines.append(
                    f"| {sector} | {name} | {int(s['n'])} | "
                    f"{s['win_rate']:.1%} | {s['loss_rate']:.1%} | {s['timeout_rate']:.1%} | "
                    f"{s['avg_pnl']:+.3f} | {s['avg_pnl_net']:+.3f} |"
                )
        lines.append("")

        lines.append(f"### Δ Reacceptance - Baseline · Stop {stop_atr} ATR\n")
        lines.append("| sector | 距离档 | reacc pnl_net | baseline pnl_net | Δ | reacc win% | baseline win% | Δ win% |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for sector in sorted(reacc_agg.keys()):
            for _, _, name in DISTANCE_BUCKETS:
                key = (stop_atr, name)
                if key not in reacc_agg[sector]:
                    continue
                r_s = reacc_agg[sector][key].summary(COST_ATR_ROUND_TRIP)
                if key not in base_agg.get(sector, {}):
                    continue
                b_s = base_agg[sector][key].summary(COST_ATR_ROUND_TRIP)
                if r_s["n"] < 20 or b_s["n"] < 50:
                    continue
                delta_pnl = r_s["avg_pnl_net"] - b_s["avg_pnl_net"]
                delta_win = r_s["win_rate"] - b_s["win_rate"]
                lines.append(
                    f"| {sector} | {name} | {r_s['avg_pnl_net']:+.3f} | {b_s['avg_pnl_net']:+.3f} | "
                    f"{delta_pnl:+.3f} | {r_s['win_rate']:.1%} | {b_s['win_rate']:.1%} | {delta_win:+.1%} |"
                )
        lines.append("")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 1.5-A3: expected value / R:R by ATR distance bucket.")
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
        n_re = sum(agg.n for agg in r.reacceptance.values())
        n_bs = sum(agg.n for agg in r.baseline.values())
        print(f"  reacceptance trials={n_re}, baseline trials={n_bs}")
        results.append(r)

    if not results:
        print("no results")
        return

    md = render_markdown(results)
    md_path = output_dir / "stage1_5_A3_expected_value.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"wrote {md_path}")

    json_path = output_dir / "stage1_5_A3_expected_value.json"
    json_path.write_text(
        json.dumps([r.to_dict() for r in results], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"wrote {json_path}")


if __name__ == "__main__":
    main()
