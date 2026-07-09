#!/usr/bin/env python3
"""
文件级元信息：
- 创建背景：Stage 4b 在 5m 周期证伪 reacceptance 触发器特殊性。用户提出：
  切换到 15m 周期是否会改变核心结论？
- 用途：完全复用 Stage 4b 逻辑，唯一变化：把 5m 数据聚合为 15m 后运行。
  参数适配：ATR_WINDOW 从 20 (5m 100min) → 20 (15m 300min，即 5h)，
  OBSERVE_N 从 80 (5m 400min) → 27 (15m 400min ≈ 相同时间窗口)。
- 输出：15m 周期下的完整 Stage 4b 报告，与 5m 结果对比。
- 注意事项：
  - 数据聚合：5m → 15m 用 open first / high max / low min / close last / volume sum
  - 参数选择原则：保持"时间尺度一致"，让 5m 与 15m 结论可比
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
DEFAULT_OUTPUT_DIR = Path("project_data/analysis/rolling_reacceptance_stage4b_15m")

MIN_DISTANCE_ATR = 4.0
# 时间尺度对齐：5m OBSERVE=80 → 400min；15m 对应 ~27 bar
OBSERVE_N = 27
STOP_ATR = 1.5
COST_ATR = 0.05
# 5m ATR_WINDOW=20 → 100min；改用 20 (15m) → 300min（一般日内趋势时长）
ATR_WINDOW = 20
VA_RATIO = 0.7
NO_TRIGGER_STRIDE = 7  # 5m stride=20 → 100min；15m stride=7 → 105min
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
    "reacceptance", "no_trigger", "long_body_reject",
    "volume_spike", "random_time", "breakout_reversal",
]


def parse_contract(filename: str) -> tuple[str, str] | None:
    m = re.match(r"^([A-Z]+)\.([a-zA-Z]+)(\d+)\.tqsdk\.5m\.csv$", filename)
    if not m:
        return None
    exchange, symbol, month = m.groups()
    return f"{exchange}.{symbol}{month}", symbol


def load_and_resample_15m(csv_path: Path) -> pd.DataFrame:
    """加载 5m 数据并聚合为 15m。"""
    df = pd.read_csv(csv_path)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.set_index("datetime")
    # 3 根 5m 聚合成 15m
    agg = pd.DataFrame({
        "open": df["open"].resample("15min").first(),
        "high": df["high"].resample("15min").max(),
        "low": df["low"].resample("15min").min(),
        "close": df["close"].resample("15min").last(),
        "volume": df["volume"].resample("15min").sum(),
    })
    agg = agg.dropna(subset=["open", "high", "low", "close"])
    agg = agg[agg["volume"] > 0]
    agg = agg.reset_index()
    agg["date"] = agg["datetime"].dt.date
    return agg[["datetime", "date", "open", "high", "low", "close", "volume"]].reset_index(drop=True)


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


def simulate_s1(entry_price, target_price, stop_atr, cost_atr, highs, lows, closes, atr_t, side):
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


def detect_triggers(bars, atr, daily, tick, seed):
    n = len(bars)
    highs = bars["high"].to_numpy()
    lows = bars["low"].to_numpy()
    closes = bars["close"].to_numpy()
    opens = bars["open"].to_numpy()
    volumes = bars["volume"].to_numpy()
    dates = bars["date"].to_numpy()

    dates_sorted = sorted(daily.keys())
    day_to_prev = {}
    for i in range(1, len(dates_sorted)):
        day_to_prev[dates_sorted[i]] = dates_sorted[i - 1]

    is_far = np.zeros(n, dtype=bool)
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

    result = {t: [] for t in TRIGGERS}

    for i in range(1, n - OBSERVE_N - 1):
        if not is_far[i]:
            continue
        d = dates[i]
        prev_d = day_to_prev.get(d.item() if hasattr(d, "item") else d)
        if prev_d is None or prev_d not in daily:
            continue
        _, val, vah, _ = daily[prev_d]
        if dates[i - 1] != d:
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

    for i in range(ATR_WINDOW, n - OBSERVE_N - 1, NO_TRIGGER_STRIDE):
        if is_far[i]:
            result["no_trigger"].append(i)

    for i in range(1, n - OBSERVE_N - 1):
        if not is_far[i]:
            continue
        rng = highs[i] - lows[i]
        if rng <= 0:
            continue
        body = abs(closes[i] - opens[i])
        if body < 0.5 * rng:
            continue
        if closes[i] > opens[i]:
            lower_wick = opens[i] - lows[i]
            if lower_wick >= 0.3 * rng:
                result["long_body_reject"].append(i)
        else:
            upper_wick = highs[i] - opens[i]
            if upper_wick >= 0.3 * rng:
                result["long_body_reject"].append(i)

    for i in range(VOLUME_LOOKBACK, n - OBSERVE_N - 1):
        if not is_far[i]:
            continue
        past_vol = volumes[i - VOLUME_LOOKBACK: i]
        if past_vol.size < VOLUME_LOOKBACK:
            continue
        threshold = np.quantile(past_vol, 0.9)
        if volumes[i] >= threshold:
            result["volume_spike"].append(i)

    n_reacc = len(result["reacceptance"])
    all_far_indices = np.where(is_far)[0]
    if n_reacc > 0 and len(all_far_indices) >= n_reacc:
        rng_ = np.random.default_rng(seed)
        sampled = rng_.choice(all_far_indices, size=n_reacc, replace=False)
        result["random_time"] = sorted(sampled.tolist())

    for i in range(BREAKOUT_LOOKBACK + 1, n - OBSERVE_N - 1):
        if not is_far[i]:
            continue
        past_high = highs[i - BREAKOUT_LOOKBACK: i].max()
        past_low = lows[i - BREAKOUT_LOOKBACK: i].min()
        if highs[i] > past_high and closes[i] < past_high:
            result["breakout_reversal"].append(i)
        elif lows[i] < past_low and closes[i] > past_low:
            result["breakout_reversal"].append(i)

    return result


def analyze_contract(csv_path, seed=42):
    parsed = parse_contract(csv_path.name)
    if parsed is None:
        return []
    contract, symbol = parsed
    if symbol not in SECTOR_MAP:
        return []
    sector = SECTOR_MAP[symbol]
    tick = TICK_SIZE.get(symbol, 1.0)
    bars = load_and_resample_15m(csv_path)
    if len(bars) < 200:  # 15m 数据量约为 5m 的 1/3
        return []

    atr = compute_atr(bars, ATR_WINDOW)
    daily = {}
    for day, day_df in bars.groupby("date", sort=True):
        r = daily_poc_va(day_df, tick=tick, ratio=VA_RATIO)
        if r is not None:
            daily[day] = r

    dates_sorted = sorted(daily.keys())
    day_to_prev = {}
    for i in range(1, len(dates_sorted)):
        day_to_prev[dates_sorted[i]] = dates_sorted[i - 1]

    trigger_indices = detect_triggers(bars, atr, daily, tick, seed=seed)

    highs = bars["high"].to_numpy()
    lows = bars["low"].to_numpy()
    closes = bars["close"].to_numpy()
    opens = bars["open"].to_numpy()
    dates = bars["date"].to_numpy()

    trades = []
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
            diff = entry_price - prev_close
            if abs(diff) < tick / 2:
                continue
            side = -1 if diff > 0 else +1
            end = entry_idx + OBSERVE_N
            pnl = simulate_s1(
                entry_price, prev_close, STOP_ATR, COST_ATR,
                highs[entry_idx: end], lows[entry_idx: end], closes[entry_idx: end],
                atr_t, side,
            )
            trades.append({
                "contract": contract, "symbol": symbol, "sector": sector,
                "trigger": trig_name, "pnl_atr": pnl, "date": str(d),
            })
    return trades


def bootstrap_ci(x, n_boot=N_BOOTSTRAP):
    rng = np.random.default_rng(42)
    n = len(x)
    means = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        means[i] = x[idx].mean()
    return float(x.mean()), float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def cluster_bootstrap_1sample(x, cluster, n_boot=N_BOOTSTRAP):
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


def cluster_bootstrap_diff(x, y, cluster_x, cluster_y, n_boot=N_BOOTSTRAP):
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


def render_markdown(df):
    lines = []
    lines.append(f"# Stage 4b (15m) · Reacceptance 触发器特殊性检验 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n")
    lines.append(f"周期：15 分钟（从 5m 聚合）\n")
    lines.append(f"MIN_DISTANCE_ATR = {MIN_DISTANCE_ATR}, OBSERVE_N = {OBSERVE_N} bars ≈ {OBSERVE_N*15}min\n")
    lines.append(f"STOP_ATR = {STOP_ATR}, COST_ATR = {COST_ATR}, ATR_WINDOW = {ATR_WINDOW}\n")
    lines.append(f"目标锚：PrevClose，bootstrap n={N_BOOTSTRAP}\n")
    lines.append(f"总交易数: {len(df)}\n")

    df_ex = df[df["sector"] != "metals"].copy()

    lines.append("## 1. 触发器样本数分布\n")
    pivot = df.pivot_table(index="trigger", columns="sector", values="pnl_atr", aggfunc="count", fill_value=0)
    lines.append(pivot.to_markdown() + "\n")

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

    lines.append("## 3. 单触发器 vs 0（每板块）\n")
    lines.append("| sector | trigger | n | mean | cluster CI | cluster p |")
    lines.append("|---|---|---|---|---|---|")
    for sec in sorted(df["sector"].unique()):
        if sec == "metals":
            continue
        for trig in TRIGGERS:
            sub = df[(df["sector"] == sec) & (df["trigger"] == trig)]
            if len(sub) < 20:
                continue
            x = sub["pnl_atr"].to_numpy()
            obs, c_lo, c_hi, p = cluster_bootstrap_1sample(x, sub["contract"].to_numpy())
            lines.append(f"| {sec} | {trig} | {len(sub)} | {obs:+.3f} | [{c_lo:+.3f}, {c_hi:+.3f}] | {p:.4f} |")
    lines.append("")

    lines.append("## 4. 每触发器 vs no_trigger baseline（H1: trigger > no_trigger）\n")
    lines.append("| sector | trigger | n_trig | n_base | mean_diff | cluster CI | p |")
    lines.append("|---|---|---|---|---|---|---|")
    for sec in sorted(df["sector"].unique()):
        if sec == "metals":
            continue
        base = df[(df["sector"] == sec) & (df["trigger"] == "no_trigger")]
        if len(base) < 20:
            continue
        y = base["pnl_atr"].to_numpy()
        cy = base["contract"].to_numpy()
        for trig in TRIGGERS:
            if trig == "no_trigger":
                continue
            sub = df[(df["sector"] == sec) & (df["trigger"] == trig)]
            if len(sub) < 20:
                continue
            x = sub["pnl_atr"].to_numpy()
            cx = sub["contract"].to_numpy()
            obs, ci_lo, ci_hi, p = cluster_bootstrap_diff(x, y, cx, cy)
            lines.append(f"| {sec} | {trig} | {len(sub)} | {len(base)} | {obs:+.3f} | [{ci_lo:+.3f}, {ci_hi:+.3f}] | {p:.4f} |")
    lines.append("")

    lines.append("## 5. ALL_ex_metals 聚合\n")
    lines.append("| trigger | n | mean | cluster CI | p_vs_0 | diff vs no_trigger | diff CI | diff p |")
    lines.append("|---|---|---|---|---|---|---|---|")
    base = df_ex[df_ex["trigger"] == "no_trigger"]
    y_base = base["pnl_atr"].to_numpy() if len(base) >= 20 else None
    c_base = base["contract"].to_numpy() if y_base is not None else None
    for trig in TRIGGERS:
        sub = df_ex[df_ex["trigger"] == trig]
        if len(sub) < 20:
            continue
        x = sub["pnl_atr"].to_numpy()
        cx = sub["contract"].to_numpy()
        obs1, c_lo, c_hi, p1 = cluster_bootstrap_1sample(x, cx)
        diff_str = diff_ci_str = diff_p_str = "-"
        if trig != "no_trigger" and y_base is not None:
            do, dl, dh, dp = cluster_bootstrap_diff(x, y_base, cx, c_base)
            diff_str = f"{do:+.3f}"; diff_ci_str = f"[{dl:+.3f}, {dh:+.3f}]"; diff_p_str = f"{dp:.4f}"
        lines.append(f"| {trig} | {len(sub)} | {obs1:+.3f} | [{c_lo:+.3f}, {c_hi:+.3f}] | {p1:.4f} | {diff_str} | {diff_ci_str} | {diff_p_str} |")
    lines.append("")

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv-root", default=str(CSV_ROOT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    csv_root = Path(args.csv_root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_csvs = sorted(csv_root.glob("*.tqsdk.5m.csv"))
    all_trades = []
    for csv_path in all_csvs:
        parsed = parse_contract(csv_path.name)
        if parsed is None:
            continue
        contract, symbol = parsed
        if symbol not in SECTOR_MAP:
            continue
        print(f"[analyze 15m] {contract} ...", flush=True)
        t = analyze_contract(csv_path)
        print(f"  trades={len(t)}")
        all_trades.extend(t)

    if not all_trades:
        print("no trades")
        return

    df = pd.DataFrame(all_trades)
    csv_out = output_dir / "stage4b_15m_trades.csv"
    df.to_csv(csv_out, index=False)
    print(f"wrote {csv_out}")

    md = render_markdown(df)
    md_path = output_dir / "stage4b_15m_trigger_significance.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"wrote {md_path}")


if __name__ == "__main__":
    main()
