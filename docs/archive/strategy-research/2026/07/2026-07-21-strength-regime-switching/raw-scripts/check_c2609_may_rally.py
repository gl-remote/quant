"""检查 c2609 2026-04-20 之后的强度回升是否被漏检"""

from pathlib import Path
import pandas as pd
import numpy as np

REPO = Path("/Users/gaolei/Documents/src/quant")
CSV_DIR = REPO / "project_data" / "market_data" / "csv"

SYMBOL = "DCE.c2609"
W = 80
CUSUM_H_MULTIPLIER = 4.0


def main():
    df = pd.read_csv(CSV_DIR / f"{SYMBOL}.tqsdk.1h.csv", parse_dates=["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    df["log_ret"] = np.log(df["close"]).diff()
    df = df.dropna(subset=["log_ret"]).reset_index(drop=True)

    # 计算全序列 x_hat
    stride = 20
    x_list = []
    idx_list = []
    for i in range(W - 1, len(df), stride):
        seg = df.iloc[i - W + 1:i + 1]
        mu = seg["log_ret"].mean()
        sd = seg["log_ret"].std(ddof=1)
        if sd <= 1e-6:
            continue
        x_hat = abs(mu) / sd
        x_list.append(x_hat)
        idx_list.append(i)

    x = np.array(x_list)
    mu0 = float(np.mean(x))
    sigma = float(np.std(x, ddof=1))
    print(f"全序列 x_hat: n={len(x)}, mean={mu0:.4f}, sigma={sigma:.4f}")
    print(f"CUSUM threshold h = {CUSUM_H_MULTIPLIER * sigma:.4f}\n")

    # CUSUM 检测
    k = 0.5 * sigma
    h = CUSUM_H_MULTIPLIER * sigma
    c_plus = 0.0
    c_minus = 0.0
    breakpoints = []

    for i in range(len(x)):
        xi = x[i]
        c_plus = max(0.0, xi - (mu0 + k) + c_plus)
        c_minus = max(0.0, (mu0 - k) - xi + c_minus)
        if c_plus > h or c_minus > h:
            # 检出断点，记录原始索引
            original_idx = idx_list[i]
            dt = df.loc[original_idx, "datetime"]
            breakpoints.append((i, original_idx, dt, "plus" if c_plus > h else "minus"))
            c_plus = 0.0
            c_minus = 0.0

    print(f"检出断点 (on x_hat sequence W=80 stride=20): {len(breakpoints)}")
    for i, original_idx, dt, direction in breakpoints:
        print(f"  {dt} direction={direction}  x_hat={x[i]:.4f}")

    # 特别检查 4月下旬到 5月
    print(f"\n--- 4月下旬~5月强度变化 ---")
    start_dt = pd.Timestamp("2026-04-01")
    end_dt = pd.Timestamp("2026-06-01")
    mask = (df["datetime"] >= start_dt) & (df["datetime"] <= end_dt)
    period_df = df[mask]
    mu_period = period_df["log_ret"].mean()
    sd_period = period_df["log_ret"].std(ddof=1)
    x_period = abs(mu_period) / sd_period
    price_start = period_df.iloc[0]["close"]
    price_end = period_df["log_ret"].iloc[-1]
    print(f"{start_dt.date()} ~ {end_dt.date()}:")
    print(f"  x_hat = {x_period:.4f}  price change = {(period_df.iloc[-1]['close'] - price_start)/price_start*100:.2f}%")

    # 找到 x 序列中这个区间有几个点
    print(f"\nx_hat 序列在该区间:")
    for (i, original_idx, dt, direction) in breakpoints:
        if start_dt <= pd.to_datetime(dt) <= end_dt:
            print(f"  检出断点: {dt} direction={direction}")

    # 看看为什么没检出 0.018 → 0.178 的漂移
    before_start = pd.Timestamp("2026-03-26")
    before_end = pd.Timestamp("2026-04-20")
    after_start = pd.Timestamp("2026-04-20")
    after_end = pd.Timestamp("2026-05-20")
    x_before = df[(df["datetime"] >= before_start) & (df["datetime"] <= before_end)]["log_ret"].agg({"mean": np.mean, "std": np.std})
    x_after = df[(df["datetime"] >= after_start) & (df["datetime"] <= after_end)]["log_ret"].agg({"mean": np.mean, "std": np.std})
    xb = abs(x_before["mean"]) / x_before["std"]
    xa = abs(x_after["mean"]) / x_after["std"]
    print(f"\n分段对比:")
    print(f"  2026-03-26 ~ 2026-04-20: x={xb:.4f}")
    print(f"  2026-04-20 ~ 2026-05-20: x={xa:.4f}")
    print(f"  漂移 = {xa - xb:.4f}")
    print(f"  CUSUM 阈值 h = {h:.4f}")


if __name__ == "__main__":
    main()
