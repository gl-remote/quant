"""快速计算跨周期 ATR 缩放比 R = ATR_long / (ATR_short * sqrt(n)).

n 是 bar 数换算: 5m→15m = 3, 5m→1h = 12, 15m→1h = 4.
i.i.d. 基线下 R = 1; mean-reverting R < 1 (子扩散); trending R > 1 (超扩散).
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

REPO = Path("/Users/gaolei/Documents/src/quant")
CSV_DIR = REPO / "project_data" / "market_data" / "csv"

EXCHANGE = {"c": "DCE", "m": "DCE", "rb": "SHFE"}
SYMBOL_CONTRACTS = {
    "c": ["c2601", "c2603", "c2605"],
    "m": ["m2601", "m2603", "m2605"],
    "rb": ["rb2601", "rb2605"],
}
PERIODS = ["5m", "15m", "1h"]
# 周期换算到分钟
PERIOD_MIN = {"5m": 5, "15m": 15, "1h": 60}


def csv_path(contract: str, period: str) -> Path:
    prefix = "rb" if contract.startswith("rb") else contract[0]
    return CSV_DIR / f"{EXCHANGE[prefix]}.{contract}.tqsdk.{period}.csv"


def per_bar_atr(df: pd.DataFrame) -> float:
    """per-bar ATR = mean(true range). 用 close-to-close 近似也可以, 这里用真实 TR."""
    h = df["high"].astype(float).to_numpy()
    l = df["low"].astype(float).to_numpy()
    c = df["close"].astype(float).to_numpy()
    prev_c = np.roll(c, 1)
    prev_c[0] = c[0]
    tr = np.maximum.reduce([h - l, np.abs(h - prev_c), np.abs(l - prev_c)])
    return float(np.mean(tr[1:]))  # 去掉第一根 (prev_c = c[0] 不准)


def main():
    rows = []
    for sym, contracts in SYMBOL_CONTRACTS.items():
        for contract in contracts:
            atr = {}
            for period in PERIODS:
                df = pd.read_csv(csv_path(contract, period))
                atr[period] = per_bar_atr(df)
            # 两两对比
            for (p_lo, p_hi) in [("5m", "15m"), ("5m", "1h"), ("15m", "1h")]:
                n = PERIOD_MIN[p_hi] // PERIOD_MIN[p_lo]
                sqrt_n = np.sqrt(n)
                R = atr[p_hi] / (atr[p_lo] * sqrt_n)
                rows.append({
                    "symbol": sym, "contract": contract,
                    "lo": p_lo, "hi": p_hi, "n": n, "sqrt_n": round(sqrt_n, 3),
                    "ATR_lo": round(atr[p_lo], 2), "ATR_hi": round(atr[p_hi], 2),
                    "R": round(R, 3),
                })

    df = pd.DataFrame(rows)
    print("=== 合约级 R 值 (i.i.d. 基线 R=1; <1 子扩散, >1 超扩散) ===")
    print(df.to_string(index=False))
    print()
    print("=== 品种平均 R ===")
    print(df.groupby(["symbol", "lo", "hi"]).agg(R_mean=("R", "mean"), R_std=("R", "std")).round(3).to_string())


if __name__ == "__main__":
    main()
