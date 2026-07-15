"""玉米 1h · 强度择时 + DirRandom 方向下的塑形参数网格扫描

固定假设：
- 能事前识别 |ν|/σ 前 10% 强信号段
- 方向随机（DirRandom）
- 玉米 1h（c2601/c2603/c2605）

扫描维度：
- K_S ∈ {1.0, 1.5, 2.0, 2.75, 4.0, 5.0}  (含跳空安全下限外/内)
- RR ∈ {0.5, 0.8, 1.0, 1.5, 2.0}         (对应 K_T = K_S × RR)
- MAX_BARS ∈ {20, 40, 80, 120}
- 强度窗口 W ∈ {20}                       (先固定，减少爆炸)
- 成本 c_side ∈ {0.0, 0.077, 0.154}      (零/现价/双倍)

每格取 P_win / E_gross / E_net / Sharpe/trade / 年化 ATR / 年化@r=1%。
输出最优 Top-K。
"""

from __future__ import annotations

import math
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd


REPO = Path("/Users/gaolei/Documents/src/quant")
CSV_DIR = REPO / "project_data" / "market_data" / "csv"
SYMBOLS = ["DCE.c2601", "DCE.c2603", "DCE.c2605"]

ATR_PERIOD = 14
STRIDE = 4
EMA_SPAN = 20
WINDOW_HOURS = 20
TOP_Q = 0.90    # 前 10%
N_MC = 100      # 每入场点方向 MC

K_S_GRID = [1.0, 1.5, 2.0, 2.75, 4.0, 5.0]
RR_GRID = [0.5, 0.8, 1.0, 1.5, 2.0]
MB_GRID = [20, 40, 80, 120]
COST_GRID = [0.0, 0.077, 0.154]


def load_bars(sym: str) -> pd.DataFrame:
    df = pd.read_csv(CSV_DIR / f"{sym}.tqsdk.1h.csv", parse_dates=["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    hi, lo, cl = df["high"], df["low"], df["close"]
    prev = cl.shift(1)
    tr = pd.concat([hi - lo, (hi - prev).abs(), (lo - prev).abs()], axis=1).max(1)
    df["atr"] = tr.rolling(ATR_PERIOD, min_periods=ATR_PERIOD).mean()
    df["log_ret"] = np.log(cl).diff()
    return df.dropna(subset=["atr", "log_ret"]).reset_index(drop=True)


def measure_strength(df: pd.DataFrame, W: int, look_forward: int) -> pd.DataFrame:
    rows = []
    for i in range(0, len(df) - W - look_forward, STRIDE):
        seg = df["log_ret"].iloc[i : i + W].to_numpy()
        if len(seg) < 5:
            continue
        sd = float(np.std(seg, ddof=1))
        if sd <= 0:
            continue
        mu = float(np.mean(seg))
        atr = df["atr"].iat[i]
        if atr <= 0 or math.isnan(atr):
            continue
        rows.append({"i": i, "nu_abs": abs(mu) / sd, "atr": atr})
    return pd.DataFrame(rows)


def simulate(
    bars: pd.DataFrame,
    entry_idx: int,
    direction: int,
    atr: float,
    K_S: float,
    K_T: float,
    max_bars: int,
) -> float:
    entry = bars["close"].iat[entry_idx]
    stop = entry - direction * K_S * atr
    take = entry + direction * K_T * atr
    max_look = min(max_bars, len(bars) - entry_idx - 1)
    exit_price = None
    for step in range(1, max_look + 1):
        j = entry_idx + step
        hi, lo = bars["high"].iat[j], bars["low"].iat[j]
        if direction > 0:
            if lo <= stop:
                exit_price = stop
                break
            if hi >= take:
                exit_price = take
                break
        else:
            if hi >= stop:
                exit_price = stop
                break
            if lo <= take:
                exit_price = take
                break
    if exit_price is None:
        exit_price = bars["close"].iat[entry_idx + max_look]
    return direction * (exit_price - entry) / atr


def run_config(
    bars_map: dict, K_S: float, RR: float, max_bars: int
) -> tuple[float, float, float, int]:
    """跨 3 合约合并跑一个 (K_S, RR, MB) 配置。返回 P_win, E_gross, std, n_trades。"""
    K_T = K_S * RR
    trades = []
    for sym, bars in bars_map.items():
        strength = measure_strength(bars, WINDOW_HOURS, max_bars)
        thr = strength["nu_abs"].quantile(TOP_Q)
        top = strength[strength["nu_abs"] >= thr]
        rng = np.random.default_rng(20260715)
        for _, row in top.iterrows():
            for _ in range(N_MC):
                d = int(rng.choice([+1, -1]))
                g = simulate(
                    bars, int(row["i"]), d, row["atr"], K_S, K_T, max_bars
                )
                trades.append(g)
    arr = np.array(trades)
    if len(arr) == 0:
        return 0.0, 0.0, 0.0, 0
    return (
        float(np.mean(arr > 0)),
        float(np.mean(arr)),
        float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
        len(arr),
    )


def main() -> None:
    bars_map = {sym: load_bars(sym) for sym in SYMBOLS}
    total_hours = sum(len(b) for b in bars_map.values())
    year_hours = 250 * 6.5

    results = []
    total = len(K_S_GRID) * len(RR_GRID) * len(MB_GRID)
    idx = 0
    for K_S, RR, MB in product(K_S_GRID, RR_GRID, MB_GRID):
        idx += 1
        p_win, e_gross, std, n_tr = run_config(bars_map, K_S, RR, MB)
        n_entries_year = (n_tr / N_MC) * year_hours / total_hours
        for c in COST_GRID:
            e_net = e_gross - 2 * c
            sharpe_trade = e_net / std if std > 0 else float("nan")
            ann_atr = e_net * n_entries_year
            ann_std = std * math.sqrt(n_entries_year)
            sharpe_year = ann_atr / ann_std if ann_std > 0 else float("nan")
            ann_pct_r1 = (e_net / K_S) * n_entries_year  # r=1%/笔
            results.append(
                {
                    "K_S": K_S,
                    "RR": RR,
                    "K_T": K_S * RR,
                    "MB": MB,
                    "c_side": c,
                    "P_win": p_win,
                    "E_gross": e_gross,
                    "E_net": e_net,
                    "std": std,
                    "Sharpe_trade": sharpe_trade,
                    "n_year": n_entries_year,
                    "ann_ATR": ann_atr,
                    "Sharpe_year": sharpe_year,
                    "ann_pct_r1": ann_pct_r1,
                }
            )
        if idx % 20 == 0:
            print(
                f"[{idx}/{total}] K_S={K_S} RR={RR} MB={MB}  "
                f"P_win={p_win:.3f}  E_gross={e_gross:+.3f}  n_tr={n_tr}"
            )

    df = pd.DataFrame(results)

    print("\n\n===== Top-15 (按现价成本 c=0.077, Sharpe/年 排序) =====")
    sub = df[df["c_side"] == 0.077].sort_values(
        "Sharpe_year", ascending=False
    ).head(15)
    print(
        sub[
            [
                "K_S",
                "RR",
                "K_T",
                "MB",
                "P_win",
                "E_gross",
                "E_net",
                "Sharpe_trade",
                "n_year",
                "ann_ATR",
                "Sharpe_year",
                "ann_pct_r1",
            ]
        ].to_string(index=False, float_format=lambda x: f"{x:+.3f}")
    )

    print("\n\n===== Top-10 现价成本按 ann_pct_r1 排序 =====")
    sub2 = df[df["c_side"] == 0.077].sort_values(
        "ann_pct_r1", ascending=False
    ).head(10)
    print(
        sub2[["K_S", "RR", "MB", "P_win", "E_net", "n_year",
              "Sharpe_year", "ann_pct_r1"]]
        .to_string(index=False, float_format=lambda x: f"{x:+.3f}")
    )

    print("\n\n===== 零成本极限 (c=0.0) Top-10 =====")
    sub3 = df[df["c_side"] == 0.0].sort_values(
        "Sharpe_year", ascending=False
    ).head(10)
    print(
        sub3[["K_S", "RR", "MB", "P_win", "E_gross", "E_net",
              "Sharpe_year", "ann_pct_r1"]]
        .to_string(index=False, float_format=lambda x: f"{x:+.3f}")
    )

    print("\n\n===== 双倍成本 (c=0.154) 最佳 =====")
    sub4 = df[df["c_side"] == 0.154].sort_values(
        "Sharpe_year", ascending=False
    ).head(5)
    print(
        sub4[["K_S", "RR", "MB", "P_win", "E_net", "Sharpe_year",
              "ann_pct_r1"]]
        .to_string(index=False, float_format=lambda x: f"{x:+.3f}")
    )

    out = REPO / "project_data" / "research" / "first_passage_boundary"
    df.to_csv(out / "corn_1h_dirrand_grid.csv", index=False)
    print(f"\n完整网格已写入 {out}/corn_1h_dirrand_grid.csv")


if __name__ == "__main__":
    main()
