#!/usr/bin/env python3
"""
文件级元信息：
- 创建背景：value-area-rolling-reacceptance 主题阶段 1 gatekeeper 实验，
  验证价格从 VA 外侧穿回内侧后是否有向 POC 的方向 edge，并识别生效品种子集。
- 用途：加载 5m CSV，用前一交易日 fixed-window VA/POC 扫描 reacceptance 事件，
  统计事件后 N ∈ {5,10,20,40} bar 的方向指标，并与 same-direction / random-direction
  随机基准对照。输出逐品种 markdown + JSON。
- 注意事项：
  - 只做 fixed-window（前日）扫描，不涉及 rolling；rolling 对照留到阶段 4。
  - 事件时点用 bar close，不看 intra-bar；观察窗口从 t+1 起算。
  - 结果只作 gatekeeper 定性判断，不作策略回测。
"""

from __future__ import annotations

import argparse
import json
import random
import re
import statistics
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

CSV_ROOT = Path("project_data/market_data/csv")
DEFAULT_OUTPUT_DIR = Path("project_data/analysis/rolling_reacceptance_stage1")

OBSERVE_BARS: tuple[int, ...] = (5, 10, 20, 40)
VA_RATIO = 0.7
BUCKET_TICKS = 1  # volume profile 桶宽（1 tick）
RANDOM_SEEDS: tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)

# 各品种 tick size（元 / 手最小价格变动），用于 volume profile 分桶。
# 缺失的品种默认 1.0，不会导致算法错误，只是分桶粒度略粗。
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


@dataclass(frozen=True)
class Event:
    symbol: str
    contract: str
    sector: str
    ts: pd.Timestamp
    idx: int  # 事件所在 bar 在整段序列中的位置
    entry: float
    poc: float
    val: float
    vah: float
    direction: int  # +1: 从下方穿回，往上朝 POC；-1: 从上方穿回，往下朝 POC


@dataclass
class MetricSet:
    n_events: int = 0
    reach_rate: dict[int, float] = field(default_factory=dict)
    directional_bias: dict[int, float] = field(default_factory=dict)  # tick 归一化
    win_rate: dict[int, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_events": self.n_events,
            "reach_rate": self.reach_rate,
            "directional_bias": self.directional_bias,
            "win_rate": self.win_rate,
        }


@dataclass
class SymbolReport:
    contract: str
    symbol: str
    sector: str
    tick: float
    n_bars: int
    n_events: int
    avg_entry_distance_ticks: float
    structure: MetricSet
    same_dir: MetricSet
    random_dir: MetricSet
    distance_matched: MetricSet

    def verdict(self) -> str:
        """基于 reach_rate 差值给出粗判：>0.03 显著优，(0, 0.03] 弱优，<= 0 无优势。"""
        if self.n_events < 30:
            return "insufficient"
        deltas = [
            self.structure.reach_rate[n] - self.same_dir.reach_rate[n] for n in OBSERVE_BARS
        ]
        pos = sum(1 for d in deltas if d > 0)
        if pos >= 3 and max(deltas) >= 0.03:
            return "signal"
        if pos >= 3:
            return "weak"
        return "no_signal"

    def verdict_vs_distance(self) -> str:
        """相对 distance-matched baseline 的判定：结构 edge 是否超越 POC 天然吸引力。"""
        if self.n_events < 30 or self.distance_matched.n_events < 20:
            return "insufficient"
        deltas = [
            self.structure.reach_rate[n] - self.distance_matched.reach_rate[n] for n in OBSERVE_BARS
        ]
        pos = sum(1 for d in deltas if d > 0)
        if pos >= 3 and max(deltas) >= 0.03:
            return "beyond_poc"
        if pos >= 3:
            return "marginal"
        return "no_edge_beyond_poc"

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": self.contract,
            "symbol": self.symbol,
            "sector": self.sector,
            "tick": self.tick,
            "n_bars": self.n_bars,
            "n_events": self.n_events,
            "avg_entry_distance_ticks": self.avg_entry_distance_ticks,
            "structure": self.structure.to_dict(),
            "same_direction": self.same_dir.to_dict(),
            "random_direction": self.random_dir.to_dict(),
            "distance_matched": self.distance_matched.to_dict(),
            "verdict": self.verdict(),
            "verdict_vs_distance": self.verdict_vs_distance(),
        }


def parse_contract(filename: str) -> tuple[str, str] | None:
    """从 CSV 文件名解析 (contract_full, product_symbol)。"""
    m = re.match(r"^([A-Z]+)\.([a-zA-Z]+)(\d+)\.tqsdk\.5m\.csv$", filename)
    if not m:
        return None
    exchange, symbol, _month = m.groups()
    return f"{exchange}.{symbol}{_month}", symbol


def load_bars(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df["date"] = df["datetime"].dt.date
    df = df[["datetime", "date", "open", "high", "low", "close", "volume"]].copy()
    df = df.reset_index(drop=True)
    return df


def compute_daily_va_poc(day_bars: pd.DataFrame, tick: float, ratio: float) -> tuple[float, float, float] | None:
    """给定单日 5m bar，用 close-based volume profile 计算 POC / VAL / VAH。返回 (poc, val, vah)。"""
    if day_bars.empty:
        return None
    prices = day_bars["close"].to_numpy()
    volumes = day_bars["volume"].to_numpy(dtype=float)
    if volumes.sum() <= 0:
        return None
    # 分桶：按 tick 粒度
    bucket = np.round(prices / tick).astype(int)
    unique, inverse = np.unique(bucket, return_inverse=True)
    bucket_vol = np.zeros_like(unique, dtype=float)
    np.add.at(bucket_vol, inverse, volumes)
    total = bucket_vol.sum()
    if total <= 0:
        return None
    # POC = 成交量最大的桶
    poc_idx = int(bucket_vol.argmax())
    poc_price = unique[poc_idx] * tick

    # 贪心扩张 VA 到 ratio
    target = ratio * total
    included = np.zeros_like(bucket_vol, dtype=bool)
    included[poc_idx] = True
    acc = bucket_vol[poc_idx]
    lo, hi = poc_idx, poc_idx
    while acc < target and (lo > 0 or hi < len(unique) - 1):
        left_vol = bucket_vol[lo - 1] if lo > 0 else -1.0
        right_vol = bucket_vol[hi + 1] if hi < len(unique) - 1 else -1.0
        if left_vol >= right_vol and lo > 0:
            lo -= 1
            included[lo] = True
            acc += bucket_vol[lo]
        elif hi < len(unique) - 1:
            hi += 1
            included[hi] = True
            acc += bucket_vol[hi]
        else:
            break
    val = unique[lo] * tick
    vah = unique[hi] * tick
    return poc_price, val, vah


def scan_events(bars: pd.DataFrame, symbol: str, contract: str, sector: str, tick: float) -> tuple[list[Event], dict[date, tuple[float, float, float]]]:
    """扫描所有 (前日 VA/POC 已知) 的 reacceptance 事件。同时返回每日 profile 索引供 baseline 复用。"""
    events: list[Event] = []
    # 按 date 分组，先算每日 profile
    daily_profile: dict[date, tuple[float, float, float]] = {}
    for day, day_df in bars.groupby("date", sort=True):
        result = compute_daily_va_poc(day_df, tick=tick, ratio=VA_RATIO)
        if result is not None:
            daily_profile[day] = result

    dates_sorted = sorted(daily_profile.keys())
    # 每一天的 anchor 用前一日 profile
    for i in range(1, len(dates_sorted)):
        today = dates_sorted[i]
        yesterday = dates_sorted[i - 1]
        poc, val, vah = daily_profile[yesterday]
        today_mask = bars["date"] == today
        today_bars = bars[today_mask].reset_index()  # 保留 index 列（原始 bars index）
        if len(today_bars) < 2:
            continue
        for j in range(1, len(today_bars)):
            prev_close = today_bars.loc[j - 1, "close"]
            curr_close = today_bars.loc[j, "close"]
            orig_idx = int(today_bars.loc[j, "index"])
            ts = today_bars.loc[j, "datetime"]
            # 下方穿回（Reaccept_L）：前 close < VAL - 1tick, 当前 close >= VAL
            if prev_close < val - tick and curr_close >= val:
                events.append(Event(
                    symbol=symbol, contract=contract, sector=sector,
                    ts=ts, idx=orig_idx, entry=curr_close,
                    poc=poc, val=val, vah=vah, direction=+1,
                ))
            # 上方穿回（Reaccept_U）：前 close > VAH + 1tick, 当前 close <= VAH
            elif prev_close > vah + tick and curr_close <= vah:
                events.append(Event(
                    symbol=symbol, contract=contract, sector=sector,
                    ts=ts, idx=orig_idx, entry=curr_close,
                    poc=poc, val=val, vah=vah, direction=-1,
                ))
    return events, daily_profile


def build_distance_index(
    bars: pd.DataFrame,
    daily_profile: dict[date, tuple[float, float, float]],
    tick: float,
) -> dict[tuple[int, int], list[tuple[int, tuple[float, float, float]]]]:
    """
    对每根 bar (idx > 0)，用其"前一交易日 profile"作为 anchor，计算：
    - side = +1（close < POC，向上朝 POC）或 -1（close > POC，向下朝 POC）
    - distance_bucket = round(|close - POC| / tick)

    返回：{(side, distance_bucket): [(bar_idx, (poc, val, vah)), ...]}
    """
    index: dict[tuple[int, int], list[tuple[int, tuple[float, float, float]]]] = {}
    dates_sorted = sorted(daily_profile.keys())
    date_to_prev_profile: dict[date, tuple[float, float, float]] = {}
    for i in range(1, len(dates_sorted)):
        date_to_prev_profile[dates_sorted[i]] = daily_profile[dates_sorted[i - 1]]

    # 排除末端 40 bar 与开头 100 bar，保证有观察窗口
    max_idx = len(bars) - max(OBSERVE_BARS) - 1
    for orig_idx in range(100, max_idx):
        d = bars.loc[orig_idx, "date"]
        if d not in date_to_prev_profile:
            continue
        poc, val, vah = date_to_prev_profile[d]
        close = float(bars.loc[orig_idx, "close"])
        diff = close - poc
        if abs(diff) < tick / 2:
            continue  # 在 POC 上，无方向
        side = -1 if diff > 0 else +1
        bucket = int(round(abs(diff) / tick))
        index.setdefault((side, bucket), []).append((orig_idx, (poc, val, vah)))
    return index


def measure_forward(
    bars: pd.DataFrame,
    entry_idx: int,
    entry_price: float,
    poc: float,
    val: float,
    vah: float,
    direction: int,
    tick: float,
    n_bars: int,
) -> tuple[bool, float, bool]:
    """
    返回 (reached_poc, directional_bias_ticks, win)。
    reached_poc：N bar 内 close 是否至少一次触及 POC（方向侧）。
    directional_bias_ticks：t+1..t+N 平均 close 相对 entry 的位移（往 POC 为正），单位 tick。
    win：N bar 内先触 POC（+方向）算胜，先穿越对侧 VA 边界（-方向）算负。
    """
    end = min(entry_idx + n_bars, len(bars) - 1)
    if entry_idx + 1 > end:
        return False, 0.0, False
    forward = bars.iloc[entry_idx + 1: end + 1]
    closes = forward["close"].to_numpy()
    highs = forward["high"].to_numpy()
    lows = forward["low"].to_numpy()

    reached = False
    if direction == +1:
        # 往上：任一 bar high 触及 POC
        reached = bool((highs >= poc).any())
        # 对侧边界：VAL 下方（这里用 val - tick 作为止损参考）
        stop_line = val - tick
        # win：先触 POC 前 low 不穿破 stop_line
        for i in range(len(forward)):
            if highs[i] >= poc:
                win = True
                break
            if lows[i] < stop_line:
                win = False
                break
        else:
            win = False
    else:
        reached = bool((lows <= poc).any())
        stop_line = vah + tick
        for i in range(len(forward)):
            if lows[i] <= poc:
                win = True
                break
            if highs[i] > stop_line:
                win = False
                break
        else:
            win = False

    mean_close = float(closes.mean())
    directional_bias_ticks = (mean_close - entry_price) / tick * direction
    return reached, directional_bias_ticks, win


def evaluate_events(bars: pd.DataFrame, events: Sequence[Event], tick: float) -> MetricSet:
    m = MetricSet(n_events=len(events))
    if not events:
        for n in OBSERVE_BARS:
            m.reach_rate[n] = 0.0
            m.directional_bias[n] = 0.0
            m.win_rate[n] = 0.0
        return m
    for n in OBSERVE_BARS:
        reach: list[int] = []
        biases: list[float] = []
        wins: list[int] = []
        for ev in events:
            reached, bias, win = measure_forward(
                bars, ev.idx, ev.entry, ev.poc, ev.val, ev.vah, ev.direction, tick, n,
            )
            reach.append(1 if reached else 0)
            biases.append(bias)
            wins.append(1 if win else 0)
        m.reach_rate[n] = float(np.mean(reach))
        m.directional_bias[n] = float(np.mean(biases))
        m.win_rate[n] = float(np.mean(wins))
    return m


def build_random_events(
    events: Sequence[Event],
    bars: pd.DataFrame,
    mode: str,
    seed: int,
    symbol: str,
    contract: str,
    sector: str,
) -> list[Event]:
    """
    mode = 'same'   → 保留结构事件方向分布，仅随机化时间点
    mode = 'random' → 时间点 + 方向都随机
    """
    if not events:
        return []
    rng = random.Random(seed)
    n_total = len(bars)
    # 排除末端 40 bar，保证观察窗口有足够 bar
    max_idx = n_total - max(OBSERVE_BARS) - 1
    if max_idx <= 100:
        return []
    result: list[Event] = []
    for ev in events:
        new_idx = rng.randint(100, max_idx)  # 避开开头 100 bar，保证 anchor 已就绪
        entry = float(bars.loc[new_idx, "close"])
        ts = bars.loc[new_idx, "datetime"]
        if mode == "same":
            direction = ev.direction
        else:
            direction = rng.choice([+1, -1])
        result.append(Event(
            symbol=symbol, contract=contract, sector=sector,
            ts=ts, idx=new_idx, entry=entry,
            poc=ev.poc, val=ev.val, vah=ev.vah, direction=direction,
        ))
    return result


def build_distance_matched_events(
    events: Sequence[Event],
    bars: pd.DataFrame,
    dist_index: dict[tuple[int, int], list[tuple[int, tuple[float, float, float]]]],
    tick: float,
    tolerance_ticks: int,
    seed: int,
    symbol: str,
    contract: str,
    sector: str,
) -> list[Event]:
    """
    对每个结构事件，从"同方向 + 距 POC 距离 ± tolerance ticks 内"的候选 bar 中
    随机抽一个作为 baseline。这样排除了"结构入场时点天然离 POC 更近"的干扰。
    """
    if not events:
        return []
    rng = random.Random(seed)
    result: list[Event] = []
    for ev in events:
        target_bucket = int(round(abs(ev.entry - ev.poc) / tick))
        candidates: list[tuple[int, tuple[float, float, float]]] = []
        for delta in range(-tolerance_ticks, tolerance_ticks + 1):
            key = (ev.direction, target_bucket + delta)
            if key in dist_index:
                candidates.extend(dist_index[key])
        # 排除结构事件自身（避免采到同一 bar）
        candidates = [c for c in candidates if c[0] != ev.idx]
        if not candidates:
            continue
        picked = rng.choice(candidates)
        new_idx, (poc, val, vah) = picked
        entry = float(bars.loc[new_idx, "close"])
        ts = bars.loc[new_idx, "datetime"]
        result.append(Event(
            symbol=symbol, contract=contract, sector=sector,
            ts=ts, idx=new_idx, entry=entry,
            poc=poc, val=val, vah=vah, direction=ev.direction,
        ))
    return result


def average_metric_sets(sets: list[MetricSet]) -> MetricSet:
    if not sets:
        return MetricSet()
    m = MetricSet(n_events=int(np.mean([s.n_events for s in sets])))
    for n in OBSERVE_BARS:
        m.reach_rate[n] = float(np.mean([s.reach_rate[n] for s in sets]))
        m.directional_bias[n] = float(np.mean([s.directional_bias[n] for s in sets]))
        m.win_rate[n] = float(np.mean([s.win_rate[n] for s in sets]))
    return m


def analyze_contract(csv_path: Path) -> SymbolReport | None:
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
    events, daily_profile = scan_events(bars, symbol, contract, sector, tick)
    structure = evaluate_events(bars, events, tick)

    avg_entry_distance = 0.0
    if events:
        avg_entry_distance = float(np.mean([abs(ev.entry - ev.poc) / tick for ev in events]))

    # distance-matched baseline 用距离桶索引
    dist_index = build_distance_index(bars, daily_profile, tick)
    # 容差：黑色 tick=1 时 3 ticks；ticks 越大容差越小，控制在"约 0.5% 相对价格"
    # 简化：直接取 3 ticks，配合各品种的 tick size 本身就有相对含义
    tolerance_ticks = 3

    same_sets = []
    random_sets = []
    dist_sets: list[MetricSet] = []
    for seed in RANDOM_SEEDS:
        same_ev = build_random_events(events, bars, "same", seed, symbol, contract, sector)
        rand_ev = build_random_events(events, bars, "random", seed, symbol, contract, sector)
        dist_ev = build_distance_matched_events(
            events, bars, dist_index, tick, tolerance_ticks, seed, symbol, contract, sector,
        )
        same_sets.append(evaluate_events(bars, same_ev, tick))
        random_sets.append(evaluate_events(bars, rand_ev, tick))
        dist_sets.append(evaluate_events(bars, dist_ev, tick))

    return SymbolReport(
        contract=contract, symbol=symbol, sector=sector, tick=tick,
        n_bars=len(bars), n_events=len(events),
        avg_entry_distance_ticks=avg_entry_distance,
        structure=structure,
        same_dir=average_metric_sets(same_sets),
        random_dir=average_metric_sets(random_sets),
        distance_matched=average_metric_sets(dist_sets),
    )


def render_markdown(reports: list[SymbolReport]) -> str:
    lines: list[str] = []
    lines.append(f"# Stage 1 · 方向信息 · 结果 (run {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n")
    lines.append(f"OBSERVE_BARS = {OBSERVE_BARS}, VA_RATIO = {VA_RATIO}, RANDOM_SEEDS = {len(RANDOM_SEEDS)}\n")

    # 逐合约表：reach_rate(20)
    lines.append("## 逐合约（N=20 reach_rate）\n")
    lines.append("| contract | sector | n_events | avg_dist | struct | same | random | dist_match | Δstr-same | Δstr-dist | verdict | vs_dist |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in sorted(reports, key=lambda x: (x.sector, x.contract)):
        d_same = r.structure.reach_rate[20] - r.same_dir.reach_rate[20]
        d_dist = r.structure.reach_rate[20] - r.distance_matched.reach_rate[20]
        lines.append(
            f"| {r.contract} | {r.sector} | {r.n_events} | "
            f"{r.avg_entry_distance_ticks:.1f} | "
            f"{r.structure.reach_rate[20]:.3f} | {r.same_dir.reach_rate[20]:.3f} | "
            f"{r.random_dir.reach_rate[20]:.3f} | {r.distance_matched.reach_rate[20]:.3f} | "
            f"{d_same:+.3f} | {d_dist:+.3f} | {r.verdict()} | {r.verdict_vs_distance()} |"
        )
    lines.append("")

    # 板块聚合
    lines.append("## 板块聚合（事件加权平均 reach_rate @ N=20）\n")
    lines.append("| sector | contracts | total_events | struct | same | random | dist_match | Δstr-same | Δstr-dist |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    by_sector: dict[str, list[SymbolReport]] = {}
    for r in reports:
        by_sector.setdefault(r.sector, []).append(r)
    for sector, rs in sorted(by_sector.items()):
        total_ev = sum(r.n_events for r in rs)
        if total_ev == 0:
            continue
        def weighted(field_getter: Any) -> float:
            return sum(field_getter(r) * r.n_events for r in rs) / total_ev
        s = weighted(lambda r: r.structure.reach_rate[20])
        sm = weighted(lambda r: r.same_dir.reach_rate[20])
        rd = weighted(lambda r: r.random_dir.reach_rate[20])
        dm = weighted(lambda r: r.distance_matched.reach_rate[20])
        lines.append(
            f"| {sector} | {len(rs)} | {total_ev} | "
            f"{s:.3f} | {sm:.3f} | {rd:.3f} | {dm:.3f} | "
            f"{s - sm:+.3f} | {s - dm:+.3f} |"
        )
    lines.append("")

    # 多 N 的 reach_rate 变化（每合约一行，两种 baseline）
    lines.append("## 多 N reach_rate 差值（Δ 相对 same_direction）\n")
    header = "| contract | " + " | ".join(f"Δ N={n}" for n in OBSERVE_BARS) + " |"
    sep = "|---|" + "|".join("---" for _ in OBSERVE_BARS) + "|"
    lines.append(header)
    lines.append(sep)
    for r in sorted(reports, key=lambda x: (x.sector, x.contract)):
        deltas = [r.structure.reach_rate[n] - r.same_dir.reach_rate[n] for n in OBSERVE_BARS]
        row = f"| {r.contract} | " + " | ".join(f"{d:+.3f}" for d in deltas) + " |"
        lines.append(row)
    lines.append("")

    lines.append("## 多 N reach_rate 差值（Δ 相对 distance_matched，隔离 POC 天然吸引力）\n")
    lines.append(header)
    lines.append(sep)
    for r in sorted(reports, key=lambda x: (x.sector, x.contract)):
        deltas = [r.structure.reach_rate[n] - r.distance_matched.reach_rate[n] for n in OBSERVE_BARS]
        row = f"| {r.contract} | " + " | ".join(f"{d:+.3f}" for d in deltas) + " |"
        lines.append(row)
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 1 direction-info analysis for value-area-rolling-reacceptance.")
    parser.add_argument("--csv-root", default=str(CSV_ROOT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--symbols", nargs="*", default=None,
                        help="可选，限定产品代码列表（如 m p rb），不传则全跑。")
    parser.add_argument("--contracts", nargs="*", default=None,
                        help="可选，限定合约（如 DCE.m2601），不传则全跑。")
    args = parser.parse_args()

    csv_root = Path(args.csv_root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_csvs = sorted(csv_root.glob("*.tqsdk.5m.csv"))
    reports: list[SymbolReport] = []
    for csv_path in all_csvs:
        parsed = parse_contract(csv_path.name)
        if parsed is None:
            continue
        contract, symbol = parsed
        if args.symbols and symbol not in args.symbols:
            continue
        if args.contracts and contract not in args.contracts:
            continue
        if symbol not in SECTOR_MAP:
            continue
        print(f"[analyze] {contract} ...", flush=True)
        r = analyze_contract(csv_path)
        if r is None:
            print(f"  skipped (no data or too short)")
            continue
        print(f"  n_events={r.n_events}, verdict={r.verdict()}")
        reports.append(r)

    if not reports:
        print("no reports generated")
        return

    md = render_markdown(reports)
    md_path = output_dir / "stage1_direction_report.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"wrote {md_path}")

    json_path = output_dir / "stage1_direction_report.json"
    json_path.write_text(
        json.dumps([r.to_dict() for r in reports], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"wrote {json_path}")


if __name__ == "__main__":
    main()
