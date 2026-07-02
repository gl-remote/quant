#!/usr/bin/env python3
"""轻量样本趋势强度分析：从 CSV 直接输出趋势标签。"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median


@dataclass(frozen=True)
class Bar:
    close: float
    high: float
    low: float


@dataclass(frozen=True)
class RawBar:
    date: str
    close: float
    high: float
    low: float


@dataclass(frozen=True)
class TrendMetrics:
    symbol: str
    interval: str
    raw_rows: int
    daily_rows: int
    start: str
    end: str
    net_change_pct: float
    close_location: float
    efficiency_ratio: float
    atr_pct: float
    trend_atr: float
    directional_consistency: float
    strong_window_ratio: float
    label: str


def _read_raw_bars(path: Path) -> tuple[list[RawBar], str, str]:
    bars: list[RawBar] = []
    start = ""
    end = ""
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                close = float(row["close"])
                high = float(row["high"])
                low = float(row["low"])
            except (KeyError, TypeError, ValueError):
                continue
            dt = row.get("datetime", "")
            if not start:
                start = dt
            end = dt
            bars.append(RawBar(date=dt[:10], close=close, high=high, low=low))
    return bars, start, end


def _to_daily_bars(raw_bars: list[RawBar]) -> list[Bar]:
    daily: list[Bar] = []
    current_date = ""
    high = 0.0
    low = 0.0
    close = 0.0

    for bar in raw_bars:
        if bar.date != current_date:
            if current_date:
                daily.append(Bar(close=close, high=high, low=low))
            current_date = bar.date
            high = bar.high
            low = bar.low
        else:
            high = max(high, bar.high)
            low = min(low, bar.low)
        close = bar.close

    if current_date:
        daily.append(Bar(close=close, high=high, low=low))
    return daily


def _true_ranges(bars: list[Bar]) -> list[float]:
    if not bars:
        return []
    ranges = [bars[0].high - bars[0].low]
    for prev, bar in zip(bars, bars[1:], strict=False):
        ranges.append(max(bar.high - bar.low, abs(bar.high - prev.close), abs(bar.low - prev.close)))
    return ranges


def _directional_consistency(closes: list[float]) -> float:
    ups = 0
    downs = 0
    for left, right in zip(closes, closes[1:], strict=False):
        if right > left:
            ups += 1
        elif right < left:
            downs += 1
    total = ups + downs
    if total == 0:
        return 0.0
    return max(ups, downs) / total


def _efficiency_ratio(closes: list[float]) -> float:
    if len(closes) < 2:
        return 0.0
    net = abs(closes[-1] - closes[0])
    path = sum(abs(right - left) for left, right in zip(closes, closes[1:], strict=False))
    if path == 0:
        return 0.0
    return net / path


def _window_strong_ratio(closes: list[float], window: int) -> float:
    if len(closes) <= window:
        return 0.0
    values: list[float] = []
    step = max(1, window // 2)
    for start in range(0, len(closes) - window + 1, step):
        chunk = closes[start : start + window]
        values.append(_efficiency_ratio(chunk))
    if not values:
        return 0.0
    return sum(1 for value in values if value >= 0.65) / len(values)


def _infer_symbol_interval(path: Path) -> tuple[str, str]:
    parts = path.name.split(".")
    if len(parts) >= 5:
        return f"{parts[0]}.{parts[1]}", parts[3]
    return path.stem, ""


def analyze(path: Path, window: int) -> TrendMetrics:
    raw_bars, start, end = _read_raw_bars(path)
    daily_bars = _to_daily_bars(raw_bars)
    if len(daily_bars) < 2:
        raise ValueError(f"CSV 可用交易日不足: {path}")

    symbol, interval = _infer_symbol_interval(path)
    closes = [bar.close for bar in daily_bars]
    true_ranges = _true_ranges(daily_bars)
    first = closes[0]
    last = closes[-1]
    sample_high = max(bar.high for bar in daily_bars)
    sample_low = min(bar.low for bar in daily_bars)
    price_range = sample_high - sample_low
    atr = mean(true_ranges) if true_ranges else 0.0
    net_change = last - first

    net_change_pct = net_change / first * 100 if first else 0.0
    close_location = (last - sample_low) / price_range if price_range else 0.5
    efficiency = _efficiency_ratio(closes)
    mid_price = median(closes)
    atr_pct = atr / mid_price * 100 if mid_price else 0.0
    trend_atr = abs(net_change) / atr if atr else 0.0
    consistency = _directional_consistency(closes)
    strong_window_ratio = _window_strong_ratio(closes, window)

    strong_votes = 0
    if abs(net_change_pct) >= 8:
        strong_votes += 1
    if trend_atr >= 3:
        strong_votes += 1
    if close_location >= 0.75 or close_location <= 0.25:
        strong_votes += 1
    if efficiency >= 0.25:
        strong_votes += 1
    if consistency >= 0.58 or strong_window_ratio >= 0.35:
        strong_votes += 1

    if strong_votes >= 3:
        label = "strong_trend"
    elif strong_votes == 2:
        label = "trend_bias"
    else:
        label = "non_strong_trend"

    return TrendMetrics(
        symbol=symbol,
        interval=interval,
        raw_rows=len(raw_bars),
        daily_rows=len(daily_bars),
        start=start,
        end=end,
        net_change_pct=net_change_pct,
        close_location=close_location,
        efficiency_ratio=efficiency,
        atr_pct=atr_pct,
        trend_atr=trend_atr,
        directional_consistency=consistency,
        strong_window_ratio=strong_window_ratio,
        label=label,
    )


def _format(metrics: TrendMetrics) -> str:
    direction = "up" if metrics.net_change_pct > 0 else "down" if metrics.net_change_pct < 0 else "flat"
    return "\n".join(
        [
            f"symbol: {metrics.symbol}",
            f"interval: {metrics.interval}",
            f"range: {metrics.start} ~ {metrics.end}",
            f"raw_rows: {metrics.raw_rows}",
            f"daily_rows: {metrics.daily_rows}",
            f"label: {metrics.label}",
            f"direction: {direction}",
            f"net_change_pct: {metrics.net_change_pct:.2f}%",
            f"close_location: {metrics.close_location:.3f}",
            f"efficiency_ratio: {metrics.efficiency_ratio:.3f}",
            f"trend_atr: {metrics.trend_atr:.2f}",
            f"atr_pct: {metrics.atr_pct:.3f}%",
            f"directional_consistency: {metrics.directional_consistency:.3f}",
            f"strong_window_ratio: {metrics.strong_window_ratio:.3f}",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="从行情 CSV 判断整个样本是否偏强趋势")
    parser.add_argument("csv", type=Path, nargs="+", help="行情 CSV 路径")
    parser.add_argument("--window", type=int, default=10, help="局部趋势窗口长度，单位为交易日，默认 10")
    parser.add_argument("--markdown", action="store_true", help="输出 markdown 表格")
    args = parser.parse_args()

    results = [analyze(path, args.window) for path in args.csv]
    if args.markdown:
        print(
            "| symbol | interval | raw_rows | daily_rows | range | label | net_change_pct | close_location | "
            "efficiency_ratio | trend_atr | directional_consistency | strong_window_ratio |"
        )
        print("| --- | --- | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |")
        for item in results:
            print(
                f"| {item.symbol} | {item.interval} | {item.raw_rows} | {item.daily_rows} | "
                f"{item.start} ~ {item.end} | {item.label} | {item.net_change_pct:.2f}% | "
                f"{item.close_location:.3f} | {item.efficiency_ratio:.3f} | {item.trend_atr:.2f} | "
                f"{item.directional_consistency:.3f} | {item.strong_window_ratio:.3f} |"
            )
        return

    for index, item in enumerate(results):
        if index:
            print()
        print(_format(item))


if __name__ == "__main__":
    main()
