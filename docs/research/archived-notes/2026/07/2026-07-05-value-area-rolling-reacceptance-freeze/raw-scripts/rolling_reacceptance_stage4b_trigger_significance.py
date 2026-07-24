#!/usr/bin/env python3
"""
文件级元信息：
- 创建背景：Stage 4 已证伪 rolling POC 独立价值。用户提出：reacceptance 是否
  真的有特殊性？还是只是"4+ ATR 距离档 + 任意 bar"的伪装？
- 用途：在 4+ ATR 距离档下对比 6 种入场触发器的期望净值：
  1) reacceptance：现有定义（VA 外穿回内）
  2) no_trigger：距离档下每 20 bar 采样（作为"无触发器 baseline"）
  3) long_body_reject：4+ ATR 距离 + 长实体 + 反向长影线
  4) volume_spike：4+ ATR 距离 + 成交量突破前 20 bar 90 分位
  5) random_time：4+ ATR 距离下按 reacceptance 相同 rate 随机采样
  6) breakout_reversal：4+ ATR 距离 + close 突破前 5 bar high/low 又反向
- 输出：
  - 板块 × 触发器的期望净值矩阵（目标锚定为 PrevClose 简化对比）
  - 单锚点 vs 0 显著性
  - 关键配对差值 (每触发器 vs no_trigger baseline) 检验
  - Cluster bootstrap
- 注意事项：
  - 目标锚统一用 PrevClose（Stage 4 显著性检验显示 PrevClose 与 rolling/fixed 无
    显著差异，用 PrevClose 简化 + 稳定）
  - 距离档基于 fixed_POC（保持与 Stage 1/1.5/4 一致的距离定义，仅作为过滤门限）
  - 结构统一 S1 baseline: stop=1.5 ATR, timeout=80 bar, cost=0.05 ATR
"""

from __future__ import annotations

import argparse
import re
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

CSV_ROOT = Path("project_data/market_data/csv")
DEFAULT_OUTPUT_DIR = Path("project_data/analysis/rolling_reacceptance_stage4b")

MIN_DISTANCE_ATR = 4.0  # 距离档过滤下限
OBSERVE_N = 80
STOP_ATR = 1.5
COST_ATR = 0.05
ATR_WINDOW = 20
VA_RATIO = 0.7
NO_TRIGGER_STRIDE = 20  # no_trigger 每 20 bar 采一次
VOLUME_LOOKBACK = 20
BREAKOUT_LOOKBACK = 5
N_BOOTSTRAP = 5000

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

TRIGGERS = [
    "reacceptance",
    "no_trigger",
    "long_body_reject",
    "volume_spike",
    "random_time",
    "breakout_reversal",
]


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


def daily_poc_va(day_bars: pd.DataFrame, tick: float, ratio: float) -> tuple[float, float, float, float] | None:
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
    prev_close = float(day_bars["close"].iloc[-1])
    return (poc_price, val, vah, prev_close)


def simulate_s1(
    entry_price: float,
    target_price: float,
    stop_atr: float,
    cost_atr: float,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr_t: float,
    side: int,
) -> float:
    stop_price = entry_price - side * stop_atr * atr_t
    for i in range(len(highs)):
        if side == +1:
            if lows[i] <= stop_price:
                return -stop_atr - cost_atr
            if highs[i] >= target_price:
                return (target_price - entry_price) / atr_t - cost_atr
        else:
            if highs[i] >= stop_price:
                return -stop_atr - cost_atr
            if lows[i] <= target_price:
                return (entry_price - target_price) / atr_t - cost_atr
    final_close = closes[-1] if len(closes) > 0 else entry_price
    pnl = (final_close - entry_price) * side / atr_t
    return pnl - cost_atr


def detect_triggers(
    bars: pd.DataFrame,
    atr: np.ndarray,
    daily: dict[date, tuple[float, float, float, float]],
    tick: float,
    seed: int,
) -> dict[str, list[int]]:
    """检测各触发器发生的 bar index。返回 {trigger_name: [bar_indices]}"""
    n = len(bars)
    highs = bars["high"].to_numpy()
    lows = bars["low"].to_numpy()
    closes = bars["close"].to_numpy()
    opens = bars["open"].to_numpy()
    volumes = bars["volume"].to_numpy()
    dates = bars["date"].to_numpy()

    dates_sorted = sorted(daily.keys())
    day_to_prev: dict[date, date] = {}
    for i in range(1, len(dates_sorted)):
        day_to_prev[dates_sorted[i]] = dates_sorted[i - 1]

    # 预计算：每个 bar 是否在 4+ ATR 距离档（相对前日 POC）
    is_far: np.ndarray = np.zeros(n, dtype=bool)
    for i in range(ATR_WINDOW, n - OBSERVE_N - 1):
        d = dates[i]
        prev_d = day_to_prev.get(d.item() if hasattr(d, "item") else d)
        if prev_d is None or prev_d not in daily:
            continue
        atr_t = atr[i]
        if not np.isfinite(atr_t) or atr_t <= 0:
            continue
        fixed_poc = daily[prev_d][0]
        dist = abs(closes[i] - fixed_poc) / atr_t
        if dist >= MIN_DISTANCE_ATR:
            is_far[i] = True

    result: dict[str, list[int]] = {t: [] for t in TRIGGERS}

    # 1. reacceptance: bar close 从 VA 外穿回内
    for i in range(1, n - OBSERVE_N - 1):
        if not is_far[i]:
            continue
        d = dates[i]
        prev_d = day_to_prev.get(d.item() if hasattr(d, "item") else d)
        if prev_d is None or prev_d not in daily:
            continue
        _, val, vah, _ = daily[prev_d]
        # 同一日内前后 bar
        if i == 0 or dates[i - 1] != d:
            continue
        prev_close = closes[i - 1]
        curr_close = closes[i]
        is_reacc = False
        if prev_close < val - tick and curr_close >= val:
            is_reacc = True
        elif prev_close > vah + tick and curr_close <= vah:
            is_reacc = True
        if is_reacc:
            result["reacceptance"].append(i)

    # 2. no_trigger: 每 NO_TRIGGER_STRIDE bar 采样
    for i in range(ATR_WINDOW, n - OBSERVE_N - 1, NO_TRIGGER_STRIDE):
        if is_far[i]:
            result["no_trigger"].append(i)

    # 3. long_body_reject: 长实体（body >= 0.8 * range）+ 反向长影线
    for i in range(1, n - OBSERVE_N - 1):
        if not is_far[i]:
            continue
        rng = highs[i] - lows[i]
        if rng <= 0:
            continue
        body = abs(closes[i] - opens[i])
        if body < 0.5 * rng:
            continue
        # 反向长影线：如果是阳线，上影线要短，下影线要长 —— 表示价格下探后被拒
        # 简化：影线长度 >= 0.3 * range
        if closes[i] > opens[i]:  # 阳线
            lower_wick = opens[i] - lows[i]
            if lower_wick >= 0.3 * rng:
                result["long_body_reject"].append(i)
        else:  # 阴线
            upper_wick = highs[i] - opens[i]
            if upper_wick >= 0.3 * rng:
                result["long_body_reject"].append(i)

    # 4. volume_spike: 成交量突破前 VOLUME_LOOKBACK bar 90 分位
    for i in range(VOLUME_LOOKBACK, n - OBSERVE_N - 1):
        if not is_far[i]:
            continue
        past_vol = volumes[i - VOLUME_LOOKBACK: i]
        if past_vol.size < VOLUME_LOOKBACK:
            continue
        threshold = np.quantile(past_vol, 0.9)
        if volumes[i] >= threshold:
            result["volume_spike"].append(i)

    # 5. random_time: 按 reacceptance 相同数量在 is_far bar 中随机采样
    n_reacc = len(result["reacceptance"])
    all_far_indices = np.where(is_far)[0]
    if n_reacc > 0 and len(all_far_indices) >= n_reacc:
        rng = np.random.default_rng(seed)
        sampled = rng.choice(all_far_indices, size=n_reacc, replace=False)
        result["random_time"] = sorted(sampled.tolist())

    # 6. breakout_reversal: close 突破前 BREAKOUT_LOOKBACK bar 极值后反向
    for i in range(BREAKOUT_LOOKBACK + 1, n - OBSERVE_N - 1):
        if not is_far[i]:
            continue
        past_high = highs[i - BREAKOUT_LOOKBACK: i].max()
        past_low = lows[i - BREAKOUT_LOOKBACK: i].min()
        # 突破上又反向：本 bar high 突破 past_high 但 close < 上一 bar high 附近
        if highs[i] > past_high and closes[i] < past_high:
            result["breakout_reversal"].append(i)
        elif lows[i] < past_low and closes[i] > past_low:
            result["breakout_reversal"].append(i)

    return result


def analyze_contract(csv_path: Path, seed: int = 42) -> list[dict]:
    parsed = parse_contract(csv_path.name)
    if parsed is None:
        return []
    contract, symbol = parsed
    if symbol not in SECTOR_MAP:
        return []
    sector = SECTOR_MAP[symbol]
    tick = TICK_SIZE.get(symbol, 1.0)
    bars = load_bars(csv_path)
    if len(bars) < 500:
        return []

    atr = compute_atr(bars, ATR_WINDOW)

    daily: dict[date, tuple[float, float, float, float]] = {}
    for day, day_df in bars.groupby("date", sort=True):
        r = daily_poc_va(day_df, tick=tick, ratio=VA_RATIO)
        if r is not None:
            daily[day] = r

    dates_sorted = sorted(daily.keys())
    day_to_prev: dict[date, date] = {}
    for i in range(1, len(dates_sorted)):
        day_to_prev[dates_sorted[i]] = dates_sorted[i - 1]

    trigger_indices = detect_triggers(bars, atr, daily, tick, seed=seed)

    highs = bars["high"].to_numpy()
    lows = bars["low"].to_numpy()
    closes = bars["close"].to_numpy()
    opens = bars["open"].to_numpy()
    dates = bars["date"].to_numpy()

    trades: list[dict] = []

    for trig_name, indices in trigger_indices.items():
        for i in indices:
            d = dates[i]
            prev_d = day_to_prev.get(d.item() if hasattr(d, "item") else d)
            if prev_d is None:
                continue
            _, _, _, prev_close = daily[prev_d]
            atr_t = atr[i]
            if not np.isfinite(atr_t) or atr_t <= 0:
                continue

            entry_idx = i + 1
            if entry_idx + OBSERVE_N >= len(bars):
                continue
            entry_price = float(opens[entry_idx])

            # target: PrevClose (统一)
            diff = entry_price - prev_close
            if abs(diff) < tick / 2:
                continue
            side = -1 if diff > 0 else +1

            end = entry_idx + OBSERVE_N
            fw_highs = highs[entry_idx: end]
            fw_lows = lows[entry_idx: end]
            fw_closes = closes[entry_idx: end]

            pnl = simulate_s1(
                entry_price=entry_price,
                target_price=prev_close,
                stop_atr=STOP_ATR,
                cost_atr=COST_ATR,
                highs=fw_highs,
                lows=fw_lows,
                closes=fw_closes,
                atr_t=atr_t,
                side=side,
            )
            trades.append({
                "contract": contract, "symbol": symbol, "sector": sector,
                "trigger": trig_name, "pnl_atr": pnl, "bar_idx": int(i),
                "date": str(d),
            })

    return trades


def bootstrap_ci(x: np.ndarray, n_boot: int = N_BOOTSTRAP) -> tuple[float, float, float]:
    rng = np.random.default_rng(42)
    n = len(x)
    means = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        means[i] = x[idx].mean()
    return float(x.mean()), float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def cluster_bootstrap_1sample(x: np.ndarray, cluster: np.ndarray, n_boot: int = N_BOOTSTRAP) -> tuple[float, float, float, float]:
    clusters, inverse = np.unique(cluster, return_inverse=True)
    idx_map = {j: np.where(inverse == j)[0] for j in range(len(clusters))}
    n_c = len(clusters)
    rng = np.random.default_rng(42)
    means = np.empty(n_boot)
    for i in range(n_boot):
        s = rng.integers(0, n_c, size=n_c)
        pick = np.concatenate([idx_map[j] for j in s])
        means[i] = x[pick].mean()
    obs = float(x.mean())
    return obs, float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975)), float((means <= 0).mean())


def cluster_bootstrap_diff(
    x: np.ndarray, y: np.ndarray, cluster_x: np.ndarray, cluster_y: np.ndarray, n_boot: int = N_BOOTSTRAP,
) -> tuple[float, float, float, float]:
    """非配对两组差值的 cluster bootstrap。分别对两组按 cluster 重采样，取均值差。"""
    cxu, invx = np.unique(cluster_x, return_inverse=True)
    cyu, invy = np.unique(cluster_y, return_inverse=True)
    idx_x = {j: np.where(invx == j)[0] for j in range(len(cxu))}
    idx_y = {j: np.where(invy == j)[0] for j in range(len(cyu))}
    nx, ny = len(cxu), len(cyu)
    rng = np.random.default_rng(42)
    diffs = np.empty(n_boot)
    for i in range(n_boot):
        sx = rng.integers(0, nx, size=nx)
        sy = rng.integers(0, ny, size=ny)
        px = np.concatenate([idx_x[j] for j in sx])
        py = np.concatenate([idx_y[j] for j in sy])
        diffs[i] = x[px].mean() - y[py].mean()
    obs = float(x.mean() - y.mean())
    return obs, float(np.quantile(diffs, 0.025)), float(np.quantile(diffs, 0.975)), float((diffs <= 0).mean())


def render_markdown(df: pd.DataFrame) -> str:
    lines: list[str] = []
    lines.append(f"# Stage 4b · Reacceptance 触发器特殊性检验 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n")
    lines.append(f"MIN_DISTANCE_ATR = {MIN_DISTANCE_ATR}, OBSERVE_N = {OBSERVE_N}, STOP_ATR = {STOP_ATR}, COST_ATR = {COST_ATR}\n")
    lines.append(f"目标锚：PrevClose（统一），bootstrap n={N_BOOTSTRAP}\n")
    lines.append(f"总交易数: {len(df)}\n")

    df_ex = df[df["sector"] != "metals"].copy()

    # 1. 每触发器每板块的样本数
    lines.append("## 1. 触发器样本数分布\n")
    pivot = df.pivot_table(index="trigger", columns="sector", values="pnl_atr", aggfunc="count", fill_value=0)
    lines.append(pivot.to_markdown() + "\n")

    # 2. 每触发器每板块期望净值
    lines.append("## 2. 板块 × 触发器 期望净值（ATR/笔）\n")
    lines.append("| trigger | " + " | ".join(sorted(df["sector"].unique())) + " |")
    lines.append("|---|" + "|".join("---" for _ in df["sector"].unique()) + "|")
    for trig in TRIGGERS:
        cells = [trig]
        for sec in sorted(df["sector"].unique()):
            sub = df[(df["sector"] == sec) & (df["trigger"] == trig)]
            if len(sub) < 20:
                cells.append("-")
            else:
                cells.append(f"{sub['pnl_atr'].mean():+.3f}(n={len(sub)})")
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    # 3. 单触发器 vs 0（每板块） - 显著性
    lines.append("## 3. 单触发器期望净值 vs 0（每板块）\n")
    lines.append("| sector | trigger | n | mean | 95% CI | cluster CI | p_one_sided |")
    lines.append("|---|---|---|---|---|---|---|")
    for sec in sorted(df["sector"].unique()):
        if sec == "metals":
            continue
        for trig in TRIGGERS:
            sub = df[(df["sector"] == sec) & (df["trigger"] == trig)]
            if len(sub) < 20:
                continue
            x = sub["pnl_atr"].to_numpy()
            m, ci_lo, ci_hi = bootstrap_ci(x)
            cluster = sub["contract"].to_numpy()
            obs, c_lo, c_hi, p = cluster_bootstrap_1sample(x, cluster)
            t_stat, p_two = stats.ttest_1samp(x, 0.0)
            p_one = p_two / 2 if t_stat > 0 else 1 - p_two / 2
            lines.append(
                f"| {sec} | {trig} | {len(sub)} | {m:+.3f} | "
                f"[{ci_lo:+.3f}, {ci_hi:+.3f}] | [{c_lo:+.3f}, {c_hi:+.3f}] | "
                f"{p_one:.4f} (cluster p={p:.4f}) |"
            )
    lines.append("")

    # 4. 每触发器 vs no_trigger baseline（非配对，因为事件不同）
    lines.append("## 4. 每触发器 vs no_trigger baseline（非配对 cluster bootstrap 差值）\n")
    lines.append("H1: trigger > no_trigger.\n")
    lines.append("| sector | trigger | n_trig | n_base | mean_diff | cluster 95% CI | p_one_sided |")
    lines.append("|---|---|---|---|---|---|---|")
    for sec in sorted(df["sector"].unique()):
        if sec == "metals":
            continue
        base_df = df[(df["sector"] == sec) & (df["trigger"] == "no_trigger")]
        if len(base_df) < 20:
            continue
        y = base_df["pnl_atr"].to_numpy()
        cy = base_df["contract"].to_numpy()
        for trig in TRIGGERS:
            if trig == "no_trigger":
                continue
            sub = df[(df["sector"] == sec) & (df["trigger"] == trig)]
            if len(sub) < 20:
                continue
            x = sub["pnl_atr"].to_numpy()
            cx = sub["contract"].to_numpy()
            obs, ci_lo, ci_hi, p = cluster_bootstrap_diff(x, y, cx, cy)
            lines.append(
                f"| {sec} | {trig} | {len(sub)} | {len(base_df)} | {obs:+.3f} | "
                f"[{ci_lo:+.3f}, {ci_hi:+.3f}] | {p:.4f} |"
            )
    lines.append("")

    # 5. ALL_ex_metals 层聚合
    lines.append("## 5. ALL_ex_metals 聚合 · 触发器对比\n")
    lines.append("| trigger | n | mean | 95% CI | cluster CI | p_vs_0 | diff vs no_trigger | diff CI | diff p |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    base = df_ex[df_ex["trigger"] == "no_trigger"]
    y_base = base["pnl_atr"].to_numpy() if len(base) >= 20 else None
    c_base = base["contract"].to_numpy() if y_base is not None else None
    for trig in TRIGGERS:
        sub = df_ex[df_ex["trigger"] == trig]
        if len(sub) < 20:
            continue
        x = sub["pnl_atr"].to_numpy()
        cx = sub["contract"].to_numpy()
        m, ci_lo, ci_hi = bootstrap_ci(x)
        obs1, c_lo, c_hi, p1 = cluster_bootstrap_1sample(x, cx)
        diff_str = "-"
        diff_ci_str = "-"
        diff_p_str = "-"
        if trig != "no_trigger" and y_base is not None:
            diff_obs, dci_lo, dci_hi, dp = cluster_bootstrap_diff(x, y_base, cx, c_base)
            diff_str = f"{diff_obs:+.3f}"
            diff_ci_str = f"[{dci_lo:+.3f}, {dci_hi:+.3f}]"
            diff_p_str = f"{dp:.4f}"
        lines.append(
            f"| {trig} | {len(sub)} | {m:+.3f} | "
            f"[{ci_lo:+.3f}, {ci_hi:+.3f}] | [{c_lo:+.3f}, {c_hi:+.3f}] | "
            f"{p1:.4f} | {diff_str} | {diff_ci_str} | {diff_p_str} |"
        )
    lines.append("")

    # 6. 判决摘要
    lines.append("## 6. 判决要点\n")
    lines.append("- **reacceptance 特殊 ↔ 假设成立**：reacceptance vs no_trigger 差值 > 0 且 cluster CI 排除 0")
    lines.append("- **reacceptance 不特殊 ↔ 主题真实资产是距离档**：所有触发器 vs no_trigger 差值 CI 都跨 0")
    lines.append("- **触发器排名**：单锚点 vs 0 显著 + diff vs baseline 显著的触发器可考虑")
    lines.append("")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv-root", default=str(CSV_ROOT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--contracts", nargs="*", default=None)
    args = parser.parse_args()

    csv_root = Path(args.csv_root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_csvs = sorted(csv_root.glob("*.tqsdk.5m.csv"))
    all_trades: list[dict] = []
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
        t = analyze_contract(csv_path)
        print(f"  trades={len(t)}")
        all_trades.extend(t)

    if not all_trades:
        print("no trades")
        return

    df = pd.DataFrame(all_trades)
    csv_out = output_dir / "stage4b_trades.csv"
    df.to_csv(csv_out, index=False)
    print(f"wrote {csv_out}")

    md = render_markdown(df)
    md_path = output_dir / "stage4b_trigger_significance.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"wrote {md_path}")


if __name__ == "__main__":
    main()
