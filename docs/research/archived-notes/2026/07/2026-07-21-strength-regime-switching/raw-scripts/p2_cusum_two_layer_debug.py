"""调试双层 CUSUM 看看漂移分布"""

from pathlib import Path
import pandas as pd
import numpy as np

REPO = Path("/Users/gaolei/Documents/src/quant")
CSV_DIR = REPO / "project_data" / "market_data" / "csv"

SYMBOL = "DCE.c2609"
LOWER_W = 20
LOWER_H = 3.0
UPPER_W = 80
UPPER_H = 3.0
MIN_INTERVAL = 50


def cusum_detect(x: np.ndarray, h_mult: float) -> list[int]:
    n = len(x)
    if n < 10:
        return []

    mu0 = float(np.mean(x))
    sigma = float(np.std(x, ddof=1))
    if sigma <= 1e-6:
        return []

    k = 0.5 * sigma
    h = h_mult * sigma

    c_plus = 0.0
    c_minus = 0.0
    breakpoints = []

    for i in range(n):
        xi = x[i]
        c_plus = max(0.0, xi - (mu0 + k) + c_plus)
        c_minus = max(0.0, (mu0 - k) - xi + c_minus)

        if c_plus > h or c_minus > h:
            breakpoints.append(i)
            c_plus = 0.0
            c_minus = 0.0

    return breakpoints


def main():
    df = pd.read_csv(CSV_DIR / f"{SYMBOL}.tqsdk.1h.csv", parse_dates=["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    log_rets = np.log(df["close"]).diff().dropna().to_numpy()
    n = len(log_rets)

    # 第一层
    x_lower_list = []
    lower_indices = []
    stride = max(1, LOWER_W // 4)
    for i in range(LOWER_W - 1, n, stride):
        seg = log_rets[i - LOWER_W + 1:i + 1]
        mu = np.mean(seg)
        sd = np.std(seg, ddof=1)
        if sd <= 1e-6:
            continue
        x_hat = abs(mu) / sd
        x_lower_list.append(x_hat)
        lower_indices.append(i + 1)

    x_lower = np.array(x_lower_list)
    bp_lower = cusum_detect(x_lower, LOWER_H)
    print(f"第一层: n={len(x_lower)}, mean={np.mean(x_lower):.4f}, std={np.std(x_lower):.4f}")
    print(f"检出粗断点: {len(bp_lower)} 个")
    print(f"阈值: >={UPPER_H} * {np.std(x_lower):.4f} = {UPPER_H * np.std(x_lower):.4f}")

    confirmed = []
    last_center = -9999

    print("\n所有粗断点候选:")
    for bp_idx in bp_lower:
        center_original = lower_indices[bp_idx]
        if center_original - last_center < MIN_INTERVAL:
            print(f"  {df.loc[center_original, 'datetime']}: skipped (too close)")
            continue

        start = center_original - UPPER_W + 1
        if start < 0:
            print(f"  {df.loc[center_original, 'datetime']}: skipped (no enough data before)")
            continue
        if center_original + UPPER_W >= n + 1:
            print(f"  {df.loc[center_original, 'datetime']}: skipped (no enough data after)")
            continue

        seg_before = log_rets[center_original - UPPER_W + 1:center_original + 1]
        seg_after = log_rets[center_original : center_original + UPPER_W]
        mu_before = abs(np.mean(seg_before)) / np.std(seg_before, ddof=1) if np.std(seg_before, ddof=1) > 1e-6 else np.nan
        mu_after = abs(np.mean(seg_after)) / np.std(seg_after, ddof=1) if np.std(seg_after, ddof=1) > 1e-6 else np.nan
        delta_x = mu_after - mu_before

        print(f"  {df.loc[center_original, 'datetime']}: x_before={mu_before:.4f} x_after={mu_after:.4f} delta={delta_x:.4f} threshold={UPPER_H * np.std(x_lower):.4f}")

        if abs(delta_x) >= (UPPER_H * np.std(x_lower)):
            confirmed.append({
                "center_df_idx": center_original,
                "x_before": round(mu_before, 4),
                "x_after": round(mu_after, 4),
                "delta_x": round(delta_x, 4),
            })
            last_center = center_original
            print(f"    → CONFIRMED")
        else:
            print(f"    → REJECTED (delta < threshold)")

    print(f"\n最终确认: {len(confirmed)} 个断点")


if __name__ == "__main__":
    main()
