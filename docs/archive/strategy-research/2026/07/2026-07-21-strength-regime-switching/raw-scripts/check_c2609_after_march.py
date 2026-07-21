"""检查 c2609 2026-03-26 之后的走势"""

from pathlib import Path
import pandas as pd
import numpy as np

REPO = Path("/Users/gaolei/Documents/src/quant")
CSV_DIR = REPO / "project_data" / "market_data" / "csv"

SYMBOL = "DCE.c2609"
WINDOW = 80


def main():
    df = pd.read_csv(CSV_DIR / f"{SYMBOL}.tqsdk.1h.csv", parse_dates=["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    df["log_ret"] = np.log(df["close"]).diff()
    df = df.dropna(subset=["log_ret"]).reset_index(drop=True)

    # 找到 2026-03-26 之后
    after_date = pd.Timestamp("2026-03-26")
    df_after = df[df["datetime"] >= after_date].reset_index(drop=True)
    print(f"数据范围: {df['datetime'].min()} → {df['datetime'].max()}")
    print(f"2026-03-26 之后有 {len(df_after)} 根 1h K线\n")

    # 滚动计算 x_hat 每 20h
    print("滚动 x_hat (W=80) 从 2026-03-26 到现在:")
    print(f"{'日期时间':<20} {'价格':>8} {'x_hat':>8}")
    print("-" * 40)

    stride = 20
    x_records = []
    for i in range(WINDOW - 1, len(df), stride):
        seg = df.iloc[i - WINDOW + 1:i + 1]
        mu = seg["log_ret"].mean()
        sd = seg["log_ret"].std(ddof=1)
        if sd <= 1e-6:
            continue
        x_hat = abs(mu) / sd
        dt = seg["datetime"].iloc[-1]
        price = seg["close"].iloc[-1]
        x_records.append((dt, price, x_hat))
        if dt > after_date:
            print(f"{dt:%Y-%m-%d %H:%M} {price:>8.2f} {x_hat:>8.4f}")

    # 计算整个后一段的平均强度
    if len(df_after) >= WINDOW:
        mu_total = df_after["log_ret"].mean()
        sd_total = df_after["log_ret"].std(ddof=1)
        x_total = abs(mu_total) / sd_total
        price_start = df_after.iloc[0]["close"]
        price_end = df_after.iloc[-1]["close"]
        pct_change = (price_end - price_start) / price_start * 100
        print(f"\n--- 汇总 ---")
        print(f"2026-03-26 → {df_after['datetime'].max()}:")
        print(f"  平均强度 x = {x_total:.4f}")
        print(f"  价格变化: {pct_change:+.2f}%")
        print(f"  总时长: {len(df_after)} 小时 ≈ {len(df_after)/24:.1f} 天")


if __name__ == "__main__":
    main()
