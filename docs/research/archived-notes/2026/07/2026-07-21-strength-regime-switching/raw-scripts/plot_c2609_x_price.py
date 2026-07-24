"""输出 c2609 滚动强度 vs 价格，直观展示断点含义"""

from pathlib import Path
import pandas as pd
import numpy as np

REPO = Path("/Users/gaolei/Documents/src/quant")
CSV_DIR = REPO / "project_data" / "market_data" / "csv"

SYMBOL = "DCE.c2609"
WINDOW = 80  # x_hat 窗口


def main():
    df = pd.read_csv(CSV_DIR / f"{SYMBOL}.tqsdk.1h.csv", parse_dates=["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    df["log_ret"] = np.log(df["close"]).diff()
    df = df.dropna(subset=["log_ret"]).reset_index(drop=True)

    # 计算滚动 x_hat (W=80) 每步都算（不 stride，密集输出）
    print(f"日期时间{'':>10} 价格{'':>8} x_hat(W=80)")
    print("-" * 50)

    # 从 2026-02-01 开始输出到现在
    start_date = pd.Timestamp("2026-02-01")

    for i in range(WINDOW - 1, len(df), 20):  # 每 20h 输出一个
        dt = df.loc[i, "datetime"]
        if pd.to_datetime(dt) < start_date:
            continue

        seg = df.iloc[i - WINDOW + 1:i + 1]
        mu = seg["log_ret"].mean()
        sd = seg["log_ret"].std(ddof=1)
        x_hat = abs(mu) / sd if sd > 1e-6 else np.nan
        price = df.loc[i, "close"]

        print(f"{dt:%Y-%m-%d %H:%M}  {price:>8.2f}  {x_hat:.4f}")


if __name__ == "__main__":
    main()
