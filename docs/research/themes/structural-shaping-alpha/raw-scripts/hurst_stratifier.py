"""Hurst 指数跨周期估计 · Hurst exponent estimator (H2 verification).

文件级元信息：
- 创建背景：§2.11.7 H2 假设 ν/σ 随周期单调放大是因为"真实漂移 ∝ τ、噪声 ∝ √τ，
  信噪比 ∝ √τ"，且额外的趋势凝聚（Hurst H > 0.5）加成。本脚本用 R/S 分析
  估计 20 合约 × 3 周期的 Hurst 指数，验证：
  (a) H > 0.5 是否广泛出现（若是，√τ 之外的 trend persistence 存在）
  (b) H 是否随周期系统性上升（是否与 ν/σ 单调放大方向一致）
- 用途：一次性研究脚本。读 5m/15m/1h 三份周期 K 线数据，对每合约每周期跑
  R/S 分析：把序列切成 log-scale 窗口，估计 log(R/S) vs log(n) 的斜率作为 H。
- 注意事项：本主题不 fetch 1m 数据，直接用已有 5m 及以上；Hurst 估计有
  N/2 长度依赖，需要序列长度 ≥ 512 才稳定，本主题 480 行 1h 数据接近下限。

用法：
    uv run python docs/research/themes/structural-shaping-alpha/raw-scripts/hurst_stratifier.py
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from data.output_paths import market_csv_dir, project_data_root

# ────────────────────── 常量 ──────────────────────
SYMBOLS: list[tuple[str, str, str]] = [
    ("black", "rb2601", "SHFE.rb2601"),
    ("black", "rb2605", "SHFE.rb2605"),
    ("black", "i2601", "DCE.i2601"),
    ("black", "i2509", "DCE.i2509"),
    ("metals", "cu2601", "SHFE.cu2601"),
    ("metals", "cu2509", "SHFE.cu2509"),
    ("metals", "al2601", "SHFE.al2601"),
    ("metals", "al2509", "SHFE.al2509"),
    ("energy_chem", "sc2512", "INE.sc2512"),
    ("energy_chem", "sc2509", "INE.sc2509"),
    ("energy_chem", "TA601", "CZCE.TA601"),
    ("energy_chem", "TA509", "CZCE.TA509"),
    ("agri_dce", "m2601", "DCE.m2601"),
    ("agri_dce", "m2605", "DCE.m2605"),
    ("agri_dce", "p2601", "DCE.p2601"),
    ("agri_dce", "p2605", "DCE.p2605"),
    ("agri_czce", "SR601", "CZCE.SR601"),
    ("agri_czce", "SR605", "CZCE.SR605"),
    ("agri_czce", "CF601", "CZCE.CF601"),
    ("agri_czce", "CF509", "CZCE.CF509"),
]
INTERVALS = ["5m", "15m", "1h"]


def hurst_rs(series: np.ndarray, min_window: int = 16, max_window: int | None = None) -> tuple[float, int]:
    """R/S 分析估计 Hurst 指数。返回 (H, num_windows_used)。"""
    n = len(series)
    if max_window is None:
        max_window = n // 4
    windows = []
    w = min_window
    while w <= max_window:
        windows.append(w)
        w = int(w * 1.5)
    if not windows:
        return float("nan"), 0

    rs_values = []
    for w in windows:
        n_chunks = n // w
        if n_chunks < 2:
            continue
        chunk_rs = []
        for i in range(n_chunks):
            x = series[i * w : (i + 1) * w]
            mean = x.mean()
            y = np.cumsum(x - mean)
            r = y.max() - y.min()
            s = x.std(ddof=1)
            if s > 0:
                chunk_rs.append(r / s)
        if chunk_rs:
            rs_values.append((w, float(np.mean(chunk_rs))))

    if len(rs_values) < 3:
        return float("nan"), len(rs_values)

    log_w = np.log([x[0] for x in rs_values])
    log_rs = np.log([x[1] for x in rs_values])
    slope, _ = np.polyfit(log_w, log_rs, 1)
    return float(slope), len(rs_values)


def stratify(csv_dir: Path) -> dict:
    results: list[dict] = []
    for sector, symbol, prefix in SYMBOLS:
        for interval in INTERVALS:
            path = csv_dir / f"{prefix}.tqsdk.{interval}.csv"
            if not path.exists():
                continue
            df = pd.read_csv(path)
            if "close" not in df.columns:
                continue
            log_returns = np.diff(np.log(df["close"].values))
            if len(log_returns) < 100:
                continue
            h, n_windows = hurst_rs(log_returns)
            results.append(
                {
                    "sector": sector,
                    "symbol": symbol,
                    "interval": interval,
                    "n_bars": len(log_returns),
                    "hurst": h,
                    "n_windows": n_windows,
                    "interpretation": (
                        "trend-persistent" if h > 0.55 else "mean-reverting" if h < 0.45 else "random-walk"
                    ),
                }
            )
    return {
        "config": {"intervals": INTERVALS, "symbols": [s[1] for s in SYMBOLS]},
        "results": results,
    }


def render_console(summary: dict) -> None:
    print(f"\n{'=' * 100}")
    print("Hurst 指数跨周期估计 · H2 假设验证")
    print(f"{'=' * 100}")

    # 按 interval 汇总
    print()
    for interval in INTERVALS:
        subset = [r for r in summary["results"] if r["interval"] == interval]
        if not subset:
            continue
        hs = np.array([r["hurst"] for r in subset if not math.isnan(r["hurst"])])
        n_trend = sum(1 for r in subset if not math.isnan(r["hurst"]) and r["hurst"] > 0.55)
        n_revert = sum(1 for r in subset if not math.isnan(r["hurst"]) and r["hurst"] < 0.45)
        n_rw = sum(1 for r in subset if not math.isnan(r["hurst"]) and 0.45 <= r["hurst"] <= 0.55)
        print(
            f"[{interval}] n={len(subset)}, mean H = {hs.mean():.4f}, median H = {np.median(hs):.4f}, std = {hs.std():.4f}"
        )
        print(f"       H > 0.55 (trend persistent): {n_trend}/{len(subset)}")
        print(f"       H in [0.45, 0.55] (random walk): {n_rw}/{len(subset)}")
        print(f"       H < 0.45 (mean reverting): {n_revert}/{len(subset)}")

    # 逐合约表
    print()
    print(f"{'=' * 60}")
    print("逐合约 × 周期 明细")
    print(f"{'=' * 60}")
    print(f"  {'symbol':>10} {'sector':>13} {'5m':>8} {'15m':>8} {'1h':>8}")
    by_sym: dict[str, dict[str, float]] = {}
    sector_map: dict[str, str] = {}
    for r in summary["results"]:
        by_sym.setdefault(r["symbol"], {})[r["interval"]] = r["hurst"]
        sector_map[r["symbol"]] = r["sector"]
    for sym in sorted(by_sym.keys()):
        h5 = by_sym[sym].get("5m", float("nan"))
        h15 = by_sym[sym].get("15m", float("nan"))
        h1h = by_sym[sym].get("1h", float("nan"))
        print(f"  {sym:>10} {sector_map[sym]:>13} {h5:>8.4f} {h15:>8.4f} {h1h:>8.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Hurst 指数跨周期估计")
    args = parser.parse_args()  # noqa: F841

    csv_dir = market_csv_dir()
    out_dir = project_data_root() / "research" / "first_passage_boundary"
    summary = stratify(csv_dir)
    render_console(summary)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"hurst_stratified_{timestamp}.json"
    csv_path = out_dir / f"hurst_stratified_{timestamp}.csv"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["sector", "symbol", "interval", "n_bars", "hurst", "n_windows", "interpretation"])
        for r in summary["results"]:
            writer.writerow(
                [
                    r["sector"],
                    r["symbol"],
                    r["interval"],
                    r["n_bars"],
                    f"{r['hurst']:.6f}" if not math.isnan(r["hurst"]) else "",
                    r["n_windows"],
                    r["interpretation"],
                ]
            )

    print(f"\nJSON: {json_path}")
    print(f"CSV:  {csv_path}")


if __name__ == "__main__":
    main()
