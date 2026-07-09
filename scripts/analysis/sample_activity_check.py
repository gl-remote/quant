#!/usr/bin/env python3
"""轻量样本活跃度分析：从 CSV 直接输出成交活跃标签。"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from statistics import median


@dataclass(frozen=True)
class RawBar:
    date: str
    volume: float


@dataclass(frozen=True)
class ActivityMetrics:
    symbol: str
    interval: str
    raw_rows: int
    daily_rows: int
    start: str
    end: str
    total_volume: float
    median_daily_volume: float
    median_bar_volume: float
    zero_volume_bar_ratio: float
    low_volume_bar_ratio: float
    active_day_ratio: float
    label: str


def _read_bars(path: Path) -> tuple[list[RawBar], str, str]:
    bars: list[RawBar] = []
    start = ""
    end = ""
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dt = row.get("datetime", "")
            try:
                volume = float(row.get("volume") or 0)
            except ValueError:
                volume = 0.0
            if not start:
                start = dt
            end = dt
            bars.append(RawBar(date=dt[:10], volume=volume))
    return bars, start, end


def _daily_volumes(bars: list[RawBar]) -> list[float]:
    daily: dict[str, float] = {}
    for bar in bars:
        daily[bar.date] = daily.get(bar.date, 0.0) + bar.volume
    return list(daily.values())


def _infer_symbol_interval(path: Path) -> tuple[str, str]:
    parts = path.name.split(".")
    if len(parts) >= 5:
        return f"{parts[0]}.{parts[1]}", parts[3]
    return path.stem, ""


def analyze(path: Path, low_volume_threshold: float, active_day_threshold: float) -> ActivityMetrics:
    bars, start, end = _read_bars(path)
    if not bars:
        raise ValueError(f"CSV 无可用 K 线: {path}")

    symbol, interval = _infer_symbol_interval(path)
    volumes = [bar.volume for bar in bars]
    daily_volumes = _daily_volumes(bars)
    total_volume = sum(volumes)
    median_daily_volume = median(daily_volumes) if daily_volumes else 0.0
    median_bar_volume = median(volumes) if volumes else 0.0
    zero_volume_bar_ratio = sum(1 for volume in volumes if volume <= 0) / len(volumes)
    low_volume_bar_ratio = sum(1 for volume in volumes if volume <= low_volume_threshold) / len(volumes)
    active_day_ratio = sum(1 for volume in daily_volumes if volume >= active_day_threshold) / len(daily_volumes)

    if zero_volume_bar_ratio >= 0.20 or active_day_ratio < 0.50:
        label = "suspicious"
    elif median_daily_volume < active_day_threshold or low_volume_bar_ratio >= 0.35:
        label = "thin"
    else:
        label = "active"

    return ActivityMetrics(
        symbol=symbol,
        interval=interval,
        raw_rows=len(bars),
        daily_rows=len(daily_volumes),
        start=start,
        end=end,
        total_volume=total_volume,
        median_daily_volume=median_daily_volume,
        median_bar_volume=median_bar_volume,
        zero_volume_bar_ratio=zero_volume_bar_ratio,
        low_volume_bar_ratio=low_volume_bar_ratio,
        active_day_ratio=active_day_ratio,
        label=label,
    )


def _format_number(value: float) -> str:
    return f"{value:.0f}"


def _format(metrics: ActivityMetrics) -> str:
    return "\n".join(
        [
            f"symbol: {metrics.symbol}",
            f"interval: {metrics.interval}",
            f"range: {metrics.start} ~ {metrics.end}",
            f"raw_rows: {metrics.raw_rows}",
            f"daily_rows: {metrics.daily_rows}",
            f"label: {metrics.label}",
            f"total_volume: {_format_number(metrics.total_volume)}",
            f"median_daily_volume: {_format_number(metrics.median_daily_volume)}",
            f"median_bar_volume: {_format_number(metrics.median_bar_volume)}",
            f"zero_volume_bar_ratio: {metrics.zero_volume_bar_ratio:.3f}",
            f"low_volume_bar_ratio: {metrics.low_volume_bar_ratio:.3f}",
            f"active_day_ratio: {metrics.active_day_ratio:.3f}",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="从行情 CSV 判断样本成交活跃度")
    parser.add_argument("csv", type=Path, nargs="+", help="行情 CSV 路径")
    parser.add_argument("--low-volume-threshold", type=float, default=0, help="低成交量 bar 阈值，默认只统计 0 成交")
    parser.add_argument("--active-day-threshold", type=float, default=10_000, help="活跃交易日成交量阈值")
    parser.add_argument("--markdown", action="store_true", help="输出 markdown 表格")
    args = parser.parse_args()

    results = [analyze(path, args.low_volume_threshold, args.active_day_threshold) for path in args.csv]
    if args.markdown:
        print(
            "| symbol | interval | raw_rows | daily_rows | range | active_label | total_volume | "
            "median_daily_volume | median_bar_volume | zero_volume_bar_ratio | low_volume_bar_ratio | active_day_ratio |"
        )
        print("| --- | --- | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |")
        for item in results:
            print(
                f"| {item.symbol} | {item.interval} | {item.raw_rows} | {item.daily_rows} | "
                f"{item.start} ~ {item.end} | {item.label} | {_format_number(item.total_volume)} | "
                f"{_format_number(item.median_daily_volume)} | {_format_number(item.median_bar_volume)} | "
                f"{item.zero_volume_bar_ratio:.3f} | {item.low_volume_bar_ratio:.3f} | {item.active_day_ratio:.3f} |"
            )
        return

    for index, item in enumerate(results):
        if index:
            print()
        print(_format(item))


if __name__ == "__main__":
    main()
