"""
文件级元信息：
- 创建背景：主题 structural-shaping-alpha 阶段 1 猜想 §8.2。gatekeeper 报告的
  win_rate 需要一个"距离档几何自然基准"作对照，否则无法判断组合胜率是"高于
  自然回归"还是"被自然回归拖累"。
- 用途：读现成 gatekeeper CSV 拿事件坐标 (symbol, entry_idx, side, entry_atr)，
  对每个 combo 使用其 (stop_atr, take_atr, max_bars) 三元组做**纯 barrier**
  几何模拟——无 trailing / 无 EOD / 无成本——统计到达率 win_rate_geom。
  然后跟同 SCALE 下的 combo 实测 win_rate 逐一对比。
- 注意事项：
  1. 无成本、无 trailing、无 EOD 强平——纯几何。用来测"当前 5m 数据下，
     给定距离档 (K_S, K_T, T_bars) 的自然到达率"。
  2. 用与 gatekeeper 同一份事件（读同一 seed 生成的 CSV），保证配对；
  3. 一次性诊断脚本，跑完写 workbench §8.2。
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from data.output_paths import market_csv_dir, project_data_root


# 与主 runner 一致的 combo 参数（S=1 基线）
COMBO_PARAMS: dict[str, tuple[float, float | None, int]] = {
    # key -> (stop_atr, take_atr, max_bars)  ; max_bars=99999 视为 EOD sentinel
    "A": (1.5, 3.0, 99999),
    "B": (0.5, 1.0, 40),
    "C": (2.5, 7.5, 160),
    "D": (1.0, None, 80),  # 无止盈 → take_atr=None，几何模式改为 close 判胜负
    "D2": (1.0, 3.0, 80),
    "E": (1.5, 2.0, 80),
    "F": (1.5, 3.0, 80),
}


SYMBOL_FILES: list[tuple[str, str]] = [
    ("rb2601", "SHFE.rb2601.tqsdk.5m.csv"),
    ("rb2605", "SHFE.rb2605.tqsdk.5m.csv"),
    ("i2601", "DCE.i2601.tqsdk.5m.csv"),
    ("i2509", "DCE.i2509.tqsdk.5m.csv"),
    ("cu2601", "SHFE.cu2601.tqsdk.5m.csv"),
    ("cu2509", "SHFE.cu2509.tqsdk.5m.csv"),
    ("al2601", "SHFE.al2601.tqsdk.5m.csv"),
    ("al2509", "SHFE.al2509.tqsdk.5m.csv"),
    ("sc2512", "INE.sc2512.tqsdk.5m.csv"),
    ("sc2509", "INE.sc2509.tqsdk.5m.csv"),
    ("TA601", "CZCE.TA601.tqsdk.5m.csv"),
    ("TA509", "CZCE.TA509.tqsdk.5m.csv"),
    ("m2601", "DCE.m2601.tqsdk.5m.csv"),
    ("m2605", "DCE.m2605.tqsdk.5m.csv"),
    ("p2601", "DCE.p2601.tqsdk.5m.csv"),
    ("p2605", "DCE.p2605.tqsdk.5m.csv"),
    ("SR601", "CZCE.SR601.tqsdk.5m.csv"),
    ("SR605", "CZCE.SR605.tqsdk.5m.csv"),
    ("CF601", "CZCE.CF601.tqsdk.5m.csv"),
    ("CF509", "CZCE.CF509.tqsdk.5m.csv"),
]


ATR_PERIOD = 14
SAMPLING_STRIDE = 20
DIR_RANDOM_SEED = 20260706


def load_bars(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    high = df["high"].to_numpy()
    low = df["low"].to_numpy()
    close = df["close"].to_numpy()
    prev_close = np.concatenate([[close[0]], close[:-1]])
    tr = np.maximum.reduce([high - low, np.abs(high - prev_close), np.abs(low - prev_close)])
    atr = pd.Series(tr).rolling(ATR_PERIOD, min_periods=ATR_PERIOD).mean().to_numpy()
    df["atr"] = atr
    return df


@dataclass(frozen=True)
class Event:
    symbol: str
    entry_idx: int
    side: int
    entry_price: float
    entry_atr: float


def make_events_same_as_runner() -> dict[str, list[Event]]:
    """复现主 runner 的事件生成（同 seed 顺序遍历 symbol）。"""
    import random

    rng = random.Random(DIR_RANDOM_SEED)
    csv_dir = market_csv_dir()
    result: dict[str, list[Event]] = {}
    for symbol, csv_file in SYMBOL_FILES:
        path = csv_dir / csv_file
        if not path.exists():
            continue
        df = load_bars(path)
        events: list[Event] = []
        n = len(df)
        first = ATR_PERIOD
        for i in range(first, n - 1, SAMPLING_STRIDE):
            entry_idx = i + 1
            if entry_idx >= n:
                break
            entry_atr = df["atr"].iat[i]
            if not math.isfinite(entry_atr) or entry_atr <= 0:
                continue
            entry_price = df["open"].iat[entry_idx]
            if not math.isfinite(entry_price):
                continue
            side = 1 if rng.random() < 0.5 else -1
            events.append(Event(symbol, entry_idx, side, float(entry_price), float(entry_atr)))
        result[symbol] = events
    return result


def simulate_barrier(
    event: Event,
    df: pd.DataFrame,
    stop_atr: float,
    take_atr: float | None,
    max_bars: int,
    scale: float,
) -> tuple[str, float]:
    """纯 barrier 几何模拟。返回 (outcome, gross_atr)。

    outcome ∈ {"take", "stop", "time_close_win", "time_close_loss", "data_end"}
    gross_atr：ATR-normalized 净收益（不扣成本，不做 trailing/EOD）
    """
    scaled_stop = stop_atr * scale
    scaled_take = take_atr * scale if take_atr is not None else None
    scaled_max_bars = max_bars if max_bars >= 99999 else int(round(max_bars * scale))
    # sentinel 99999 直接用 A 的 EOD 语义近似为一个大数
    if scaled_max_bars >= 99999:
        scaled_max_bars = 240  # 一个日盘约 48 根 5m bar，A EOD 用 5 倍缓冲，几何近似用 240

    side = event.side
    entry = event.entry_price
    atr = event.entry_atr
    stop_price = entry - side * scaled_stop * atr
    take_price = entry + side * scaled_take * atr if scaled_take is not None else None

    n = len(df)
    for step in range(1, scaled_max_bars + 1):
        j = event.entry_idx + step
        if j >= n:
            j = n - 1
            close_j = df["close"].iat[j]
            gross = side * (close_j - entry) / atr
            return ("data_end", float(gross))
        high_j = df["high"].iat[j]
        low_j = df["low"].iat[j]
        stop_hit = (low_j <= stop_price) if side == 1 else (high_j >= stop_price)
        take_hit = False
        if take_price is not None:
            take_hit = (high_j >= take_price) if side == 1 else (low_j <= take_price)
        if stop_hit:
            gross = side * (stop_price - entry) / atr
            return ("stop", float(gross))
        if take_hit:
            gross = side * (take_price - entry) / atr
            return ("take", float(gross))

    j = min(event.entry_idx + scaled_max_bars, n - 1)
    close_j = df["close"].iat[j]
    gross = side * (close_j - entry) / atr
    outcome = "time_close_win" if gross > 0 else "time_close_loss"
    return (outcome, float(gross))


def main() -> None:
    args = _parse_args()
    scale = args.scale
    csv_dir = market_csv_dir()
    events_by_symbol = make_events_same_as_runner()
    # 缓存 df
    dfs: dict[str, pd.DataFrame] = {}
    for symbol, csv_file in SYMBOL_FILES:
        path = csv_dir / csv_file
        if path.exists():
            dfs[symbol] = load_bars(path)

    summary: dict[str, dict[str, object]] = {}
    for combo_key, (stop_atr, take_atr, max_bars) in COMBO_PARAMS.items():
        outcomes: list[tuple[str, float]] = []
        for symbol, events in events_by_symbol.items():
            df = dfs.get(symbol)
            if df is None:
                continue
            for ev in events:
                outcomes.append(simulate_barrier(ev, df, stop_atr, take_atr, max_bars, scale))
        n = len(outcomes)
        take_n = sum(1 for o, _ in outcomes if o == "take")
        stop_n = sum(1 for o, _ in outcomes if o == "stop")
        tw = sum(1 for o, _ in outcomes if o == "time_close_win")
        tl = sum(1 for o, _ in outcomes if o == "time_close_loss")
        de = sum(1 for o, _ in outcomes if o == "data_end")
        wins = sum(1 for _, g in outcomes if g > 0)
        mean_gross = float(np.mean([g for _, g in outcomes])) if outcomes else 0.0
        summary[combo_key] = {
            "stop_atr_raw": stop_atr,
            "take_atr_raw": take_atr,
            "max_bars_raw": max_bars,
            "scale": scale,
            "n": n,
            "win_rate_geom": wins / n if n else 0.0,
            "mean_gross_atr": mean_gross,  # 无成本
            "take_hit_rate": take_n / n if n else 0.0,
            "stop_hit_rate": stop_n / n if n else 0.0,
            "time_close_win_rate": tw / n if n else 0.0,
            "time_close_loss_rate": tl / n if n else 0.0,
            "data_end_rate": de / n if n else 0.0,
        }

    out_dir = project_data_root() / "research" / "structural_shaping_gatekeeper"
    out_dir.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"barrier_geometry_baseline_scale{scale:g}_{ts}.json"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nSCALE={scale}")
    print(f"{'combo':<5} {'n':>5} {'win_geom':>10} {'take_hit':>10} {'stop_hit':>10} {'mean_gross':>12}")
    for k, s in summary.items():
        print(f"{k:<5} {s['n']:>5d} {s['win_rate_geom']:>10.4f} {s['take_hit_rate']:>10.4f} {s['stop_hit_rate']:>10.4f} {s['mean_gross_atr']:>12.4f}")
    print(f"\nJSON: {json_path}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pure barrier geometry baseline (distance-only, no trailing/EOD/cost)")
    parser.add_argument("--scale", type=float, default=1.0)
    return parser.parse_args()


if __name__ == "__main__":
    main()
