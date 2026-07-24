"""计算 c2609 断点前后强度变化"""

from pathlib import Path
import pandas as pd
import numpy as np

REPO = Path("/Users/gaolei/Documents/src/quant")
CSV_DIR = REPO / "project_data" / "market_data" / "csv"
OUT_DIR = REPO / "project_data" / "research" / "strength_regime_switching"

SYMBOL = "DCE.c2609"
W_XHAT = 80
STRIDE = 20


def main():
    df = pd.read_csv(CSV_DIR / f"{SYMBOL}.tqsdk.1h.csv", parse_dates=["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    df["log_ret"] = np.log(df["close"]).diff()
    df = df.dropna(subset=["log_ret"]).reset_index(drop=True)

    # 计算 x_hat 序列 W=80
    log_rets = df["log_ret"].to_numpy()
    n = len(log_rets)

    x_hat_list = []
    indices = []
    for i in range(W_XHAT - 1, n, STRIDE):
        seg = log_rets[i - W_XHAT + 1:i + 1]
        mu = np.mean(seg)
        sd = np.std(seg, ddof=1)
        if sd <= 1e-10:
            continue
        x_hat = abs(mu) / sd
        x_hat_list.append(x_hat)
        indices.append(i)

    df_x = df.iloc[indices].copy()
    df_x["x_hat"] = x_hat_list
    print(f"x_hat W=80 stride=20: {len(df_x)} points from {df_x['datetime'].min()} to {df_x['datetime'].max()}")

    # 读取断点
    bp_df = pd.read_csv(OUT_DIR / "p2_breakpoints_corn_c2609.csv")

    result_rows = []
    for _, row in bp_df.iterrows():
        dt = pd.to_datetime(row["breakpoint_datetime"])
        # 找到最近的 x_hat
        mask = df_x["datetime"] <= dt
        if mask.sum() > 0:
            closest_idx = mask[mask].index[-1]
            # 计算前后平均 x
            x_before = df_x.iloc[max(0, closest_idx - 2):closest_idx + 1]["x_hat"].mean()
            x_after = df_x.iloc[closest_idx:closest_idx + 3]["x_hat"].mean()
            delta_x = x_after - x_before

            # 价格变化
            center_abs_idx = int(row["center_h_abs"])
            start_idx = max(0, center_abs_idx - 20)
            end_idx = min(len(df), center_abs_idx + 20 + 1)
            first_close = df.iloc[start_idx]["close"]
            bp_close = df.loc[center_abs_idx, "close"]
            last_close = df.iloc[end_idx - 1]["close"]
            pct_before = (bp_close - first_close) / first_close * 100
            pct_after = (last_close - bp_close) / bp_close * 100

            result_rows.append({
                **row.to_dict(),
                "x_before_80": round(x_before, 4),
                "x_after_80": round(x_after, 4),
                "delta_x": round(delta_x, 4),
                "pct_before_20h": round(pct_before, 2),
                "pct_after_20h": round(pct_after, 2),
            })

            print(f"\n{dt}:")
            print(f"  x: {x_before:.4f} → {x_after:.4f}  Δ={delta_x:.4f}")
            print(f"  price: -20h→0h {pct_before:+.2f}%  0h→+20h {pct_after:+.2f}%")
            print(f"  resolutions: {row['resolutions']}  n_votes={row['n_votes']}")

    df_result = pd.DataFrame(result_rows)
    out_path = OUT_DIR / "p2_breakpoints_corn_c2609_updated.csv"
    df_result.to_csv(out_path, index=False)
    print(f"\nUpdated saved to {out_path}")


if __name__ == "__main__":
    main()
