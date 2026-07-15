"""玉米 1h 实盘漂移强度探针

对 c2601 / c2603 / c2605 三份 1h 数据，按 K_S=2.75 / K_T=3.0 / MAX_BARS=80
的推荐塑形容器逐 bar 模拟入场（DirRandom 分方向），实测每笔持仓期间的
ν/σ（每 √h 归一化）、E[τ]、P_win、E_gross_ATR。

参照本主题 KF-9 阈值：|ν/σ| < 0.10 视为 martingale 附近；≥ 0.10 视为显著漂移。
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd


REPO = Path("/Users/gaolei/Documents/src/quant")
CSV_DIR = REPO / "project_data" / "market_data" / "csv"
SYMBOLS = ["DCE.c2601", "DCE.c2603", "DCE.c2605"]

ATR_PERIOD = 14
K_S = 2.75            # 止损 ATR
K_T = 3.00            # 止盈 ATR (RR ≈ 1.09)
MAX_BARS = 80         # 1h 上 ≈ 12.3h
STRIDE = 4            # 每 4 bar 尝试一次入场（减重叠）
SIGMA_PER_BAR_1H = 1.0  # 主题标定：1h 上 σ ≈ 1 ATR/√h


def load_bars(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    df["atr"] = tr.rolling(ATR_PERIOD, min_periods=ATR_PERIOD).mean()
    return df.dropna(subset=["atr"]).reset_index(drop=True)


def simulate_trade(
    bars: pd.DataFrame, entry_idx: int, direction: int, atr: float
) -> dict:
    """从 entry_idx 出发，多头 direction=+1，空头 -1。返回该笔归因。"""
    entry_price = bars["close"].iat[entry_idx]
    stop = entry_price - direction * K_S * atr
    take = entry_price + direction * K_T * atr

    exit_idx = None
    exit_reason = "time_exit"
    exit_price = None
    max_lookahead = min(MAX_BARS, len(bars) - entry_idx - 1)
    for step in range(1, max_lookahead + 1):
        j = entry_idx + step
        hi, lo = bars["high"].iat[j], bars["low"].iat[j]
        if direction > 0:
            if lo <= stop:
                exit_idx, exit_reason, exit_price = j, "stop", stop
                break
            if hi >= take:
                exit_idx, exit_reason, exit_price = j, "take", take
                break
        else:
            if hi >= stop:
                exit_idx, exit_reason, exit_price = j, "stop", stop
                break
            if lo <= take:
                exit_idx, exit_reason, exit_price = j, "take", take
                break

    if exit_idx is None:
        exit_idx = entry_idx + max_lookahead
        exit_price = bars["close"].iat[exit_idx]

    n_bars = exit_idx - entry_idx
    # 每 bar 对数收益（direction 归位为多头视角）
    prices = bars["close"].iloc[entry_idx : exit_idx + 1].to_numpy()
    log_ret = np.diff(np.log(prices)) * direction  # 长度 = n_bars
    mu_bar = float(np.mean(log_ret)) if n_bars > 0 else 0.0
    sd_bar = float(np.std(log_ret, ddof=1)) if n_bars > 1 else float("nan")
    # 换算为每 √h 归一化的 ν/σ（1h 一根 bar，σ_bar 就是 √h 归一化的 σ）
    if sd_bar and not math.isnan(sd_bar) and sd_bar > 0:
        nu_over_sigma = mu_bar / sd_bar
    else:
        nu_over_sigma = float("nan")

    gross_atr = direction * (exit_price - entry_price) / atr
    return {
        "n_bars": n_bars,
        "reason": exit_reason,
        "gross_atr": gross_atr,
        "mu_bar": mu_bar,
        "sd_bar": sd_bar,
        "nu_over_sigma": nu_over_sigma,
    }


def analyse_symbol(sym: str) -> pd.DataFrame:
    path = CSV_DIR / f"{sym}.tqsdk.1h.csv"
    bars = load_bars(path)
    print(f"[{sym}] bars={len(bars)}  range=[{bars['datetime'].iat[0]} .. "
          f"{bars['datetime'].iat[-1]}]")

    rng = np.random.default_rng(20260715)
    rows = []
    for i in range(ATR_PERIOD, len(bars) - MAX_BARS, STRIDE):
        atr = bars["atr"].iat[i]
        if atr <= 0 or math.isnan(atr):
            continue
        direction = int(rng.choice([+1, -1]))
        r = simulate_trade(bars, i, direction, atr)
        r["symbol"] = sym
        r["entry_time"] = bars["datetime"].iat[i]
        r["direction"] = direction
        rows.append(r)
    return pd.DataFrame(rows)


def summarize(df: pd.DataFrame, label: str) -> None:
    n = len(df)
    if n == 0:
        print(f"{label}: 无有效样本")
        return
    reasons = df["reason"].value_counts(normalize=True) * 100
    stop = reasons.get("stop", 0.0)
    take = reasons.get("take", 0.0)
    tex = reasons.get("time_exit", 0.0)
    p_win = take / 100.0
    mean_bars = df["n_bars"].mean()
    mean_gross = df["gross_atr"].mean()
    valid = df["nu_over_sigma"].dropna()
    p50 = valid.quantile(0.50) if len(valid) else float("nan")
    p25 = valid.quantile(0.25) if len(valid) else float("nan")
    p75 = valid.quantile(0.75) if len(valid) else float("nan")
    p10 = valid.quantile(0.10) if len(valid) else float("nan")
    p90 = valid.quantile(0.90) if len(valid) else float("nan")

    # 分档统计（KF-9 阈值）
    strong_pos = (valid >= 0.10).mean() * 100
    weak_pos = ((valid >= 0.03) & (valid < 0.10)).mean() * 100
    flat = ((valid > -0.03) & (valid < 0.03)).mean() * 100
    weak_neg = ((valid <= -0.03) & (valid > -0.10)).mean() * 100
    strong_neg = (valid <= -0.10).mean() * 100

    print(f"\n===== {label} (n={n}) =====")
    print(f"  出场比例:  take={take:.1f}%  stop={stop:.1f}%  time_exit={tex:.1f}%")
    print(f"  P_win = {p_win:.3f}")
    print(f"  E[τ] = {mean_bars:.1f} bars ({mean_bars:.1f}h)")
    print(f"  E_gross = {mean_gross:+.3f} ATR/笔")
    print(f"  ν/σ 分位:  p10={p10:+.3f}  p25={p25:+.3f}  "
          f"p50={p50:+.3f}  p75={p75:+.3f}  p90={p90:+.3f}")
    print(f"  行情强度分档 (KF-9 阈值 0.10):")
    print(f"    强正 (≥+0.10): {strong_pos:5.1f}%")
    print(f"    弱正 (+0.03..+0.10): {weak_pos:5.1f}%")
    print(f"    平坦 (|ν/σ|<0.03): {flat:5.1f}%")
    print(f"    弱负 (−0.10..−0.03): {weak_neg:5.1f}%")
    print(f"    强负 (≤−0.10): {strong_neg:5.1f}%")


def main() -> None:
    print(
        f"配置: K_S={K_S} ATR  K_T={K_T} ATR  RR={K_T/K_S:.2f}  "
        f"MAX_BARS={MAX_BARS}  STRIDE={STRIDE}  σ_per_bar={SIGMA_PER_BAR_1H}"
    )
    all_rows = []
    for sym in SYMBOLS:
        df_sym = analyse_symbol(sym)
        summarize(df_sym, sym)
        all_rows.append(df_sym)
    total = pd.concat(all_rows, ignore_index=True)
    summarize(total, "全玉米 (3 合约合并)")

    # 输出到 project_data
    out_dir = REPO / "project_data" / "research" / "first_passage_boundary"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / "corn_1h_realized_strength.csv"
    total.to_csv(out_csv, index=False)
    print(f"\n明细已写入: {out_csv}")


if __name__ == "__main__":
    main()
