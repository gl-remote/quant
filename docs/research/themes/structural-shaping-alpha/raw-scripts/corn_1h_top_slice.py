"""玉米 1h · 只做前 10% 机会的强度画像

在 |ν|/σ 分布上，取前 10% (p90+) / 前 20% (p80+) / 前 30% (p70+) 三档，
输出该档内的均值、极值，以及 P_win/RR 门槛达成条件下的等价配置。
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd


REPO = Path("/Users/gaolei/Documents/src/quant")
CSV_DIR = REPO / "project_data" / "market_data" / "csv"
SYMBOLS = ["DCE.c2601", "DCE.c2603", "DCE.c2605"]

WINDOWS = [20, 80]
EMA_SPAN = 20
STRIDE = 4
QUANTILES = [0.90, 0.80, 0.70, 0.50]  # 分档门槛


def fpt_pwin(lam: float, K_S: float, K_T: float) -> float:
    if abs(lam) < 1e-9:
        return K_S / (K_S + K_T)
    a = math.exp(lam * K_T)
    b = math.exp(-lam * K_S)
    return (a * (1 - b)) / (a - b)


def implied_pwin_from_nu(nu_over_sigma: float, K_S: float, K_T: float) -> float:
    """给定 ν/σ 反推 P_win（1h 上 σ_bar=1，λ = 2·ν_bar/σ_bar² = 2·(ν/σ)/σ）。
    简化：以 σ=1 单位（相当于 K_S、K_T 已按 σ 而非 ATR 归一），λ ≈ 2·(ν/σ)。
    """
    lam = 2 * nu_over_sigma
    return fpt_pwin(lam, K_S, K_T)


def load_1h(sym: str) -> pd.DataFrame:
    df = pd.read_csv(CSV_DIR / f"{sym}.tqsdk.1h.csv", parse_dates=["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    df["log_ret"] = np.log(df["close"]).diff()
    df["ema20"] = df["close"].ewm(span=EMA_SPAN, adjust=False).mean()
    return df.dropna(subset=["log_ret"]).reset_index(drop=True)


def scan(df: pd.DataFrame, W: int, sym: str) -> pd.DataFrame:
    rows = []
    for i in range(0, len(df) - W, STRIDE):
        seg = df["log_ret"].iloc[i : i + W].to_numpy()
        if len(seg) < 5:
            continue
        mu_bar = float(np.mean(seg))
        sd_bar = float(np.std(seg, ddof=1))
        if sd_bar <= 0:
            continue
        # 直接读取该段 close 变化率，等于绝对累计涨跌
        p0 = df["close"].iat[i]
        p1 = df["close"].iat[i + W - 1]
        pct_move = (p1 / p0 - 1) * 100
        rows.append(
            {
                "symbol": sym,
                "start": df["datetime"].iat[i],
                "end": df["datetime"].iat[i + W - 1],
                "nu_dir": mu_bar / sd_bar,
                "nu_abs": abs(mu_bar) / sd_bar,
                "pct_move": pct_move,
                "abs_pct_move": abs(pct_move),
            }
        )
    return pd.DataFrame(rows)


def summarize_top(df: pd.DataFrame, W: int, label: str) -> None:
    print(f"\n===== {label}  W={W}h  n={len(df)} =====")
    print(
        f"整体 |ν|/σ: mean={df['nu_abs'].mean():+.3f}  "
        f"p50={df['nu_abs'].quantile(0.5):+.3f}  "
        f"p90={df['nu_abs'].quantile(0.9):+.3f}  "
        f"max={df['nu_abs'].max():+.3f}"
    )
    # K_S=2.75 / K_T=3.00 参照配置下的 P_win 等价映射
    K_S, K_T = 2.75, 3.00
    print(f"\n分档统计（K_S={K_S} / K_T={K_T}, RR={K_T/K_S:.2f}）:")
    print(
        f"{'档位':<12} {'样本数':>6} {'mean|ν|/σ':>10} {'p_win等价':>10} "
        f"{'mean|涨跌%|':>12} {'max|ν|/σ':>10}"
    )
    for q in QUANTILES:
        thr = df["nu_abs"].quantile(q)
        top = df[df["nu_abs"] >= thr]
        mean_nu = top["nu_abs"].mean()
        mean_move = top["abs_pct_move"].mean()
        max_nu = top["nu_abs"].max()
        p_win_eq = implied_pwin_from_nu(mean_nu, K_S, K_T)
        pct_label = f"前 {int((1-q)*100)}%"
        print(
            f"{pct_label:<12} {len(top):>6} {mean_nu:>10.3f} "
            f"{p_win_eq*100:>9.1f}% {mean_move:>11.2f}% {max_nu:>10.3f}"
        )


def show_top10_examples(df: pd.DataFrame, W: int, label: str) -> None:
    top = df.nlargest(10, "nu_abs").sort_values("start")
    print(f"\n----- {label}  W={W}h  前 10% 中最强的 10 段（按时间排序）-----")
    print(f"{'symbol':<12} {'start':<20} {'nu_abs':>7} {'move%':>8}")
    for _, r in top.iterrows():
        print(
            f"{r['symbol']:<12} {str(r['start']):<20} "
            f"{r['nu_abs']:>+7.3f} {r['pct_move']:>+7.2f}%"
        )


def main() -> None:
    all_frames = {W: [] for W in WINDOWS}
    for sym in SYMBOLS:
        df = load_1h(sym)
        for W in WINDOWS:
            all_frames[W].append(scan(df, W, sym))

    for W in WINDOWS:
        merged = pd.concat(all_frames[W], ignore_index=True)
        summarize_top(merged, W, "全玉米合并")
        show_top10_examples(merged, W, "全玉米合并")

        out_dir = REPO / "project_data" / "research" / "first_passage_boundary"
        merged.to_csv(out_dir / f"corn_1h_top_slice_W{W}.csv", index=False)


if __name__ == "__main__":
    main()
