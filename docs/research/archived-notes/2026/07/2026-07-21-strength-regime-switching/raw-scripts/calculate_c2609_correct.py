"""重新计算 c2609 断点前后强度变化 - 正确索引版本"""

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

    # 读取断点
    bp_df = pd.read_csv(OUT_DIR / "p2_breakpoints_corn_c2609.csv")

    # 预计算所有滚动 x_hat
    print(f"Original 1h data: {len(df)} bars from {df['datetime'].min()} to {df['datetime'].max()}")

    result_rows = []

    for _, row in bp_df.iterrows():
        center_abs_idx = int(row["center_h_abs"])
        dt = pd.to_datetime(row["breakpoint_datetime"])

        # 计算断点前后窗口的 x_hat（W=80）
        # x_hat at t is based on [t-W+1 ... t], so before breakpoint is centered before it
        # 我们计算断点前一个窗口 和 断点后一个窗口
        if center_abs_idx - W_XHAT + 1 >= 0 and center_abs_idx < len(df):
            window_before = df.iloc[center_abs_idx - W_XHAT + 1 : center_abs_idx + 1]
            mu_before = np.mean(window_before["log_ret"])
            sd_before = np.std(window_before["log_ret"], ddof=1)
            x_before = abs(mu_before) / sd_before if sd_before > 1e-6 else np.nan
        else:
            x_before = np.nan

        if center_abs_idx + 1 - W_XHAT + 1 >= 0 and center_abs_idx + 1 < len(df):
            window_after = df.iloc[center_abs_idx + 1 - W_XHAT + 1 : center_abs_idx + 1 + 1]
            mu_after = np.mean(window_after["log_ret"])
            sd_after = np.std(window_after["log_ret"], ddof=1)
            x_after = abs(mu_after) / sd_after if sd_after > 1e-6 else np.nan
        else:
            x_after = np.nan

        delta_x = x_after - x_before if not np.isnan(x_before) and not np.isnan(x_after) else np.nan

        # 价格变化 -20h → 0h, 0h → +20h
        start_idx = max(0, center_abs_idx - 20)
        end_idx = min(len(df), center_abs_idx + 20 + 1)
        first_close = df.iloc[start_idx]["close"]
        bp_close = df.loc[center_abs_idx, "close"]
        last_close = df.iloc[end_idx - 1]["close"]
        pct_before = (bp_close - first_close) / first_close * 100
        pct_after = (last_close - bp_close) / bp_close * 100

        result_rows.append({
            **row.to_dict(),
            "x_before_80": round(x_before, 4) if not np.isnan(x_before) else np.nan,
            "x_after_80": round(x_after, 4) if not np.isnan(x_after) else np.nan,
            "delta_x": round(delta_x, 4) if not np.isnan(delta_x) else np.nan,
            "pct_before_20h": round(pct_before, 2),
            "pct_after_20h": round(pct_after, 2),
        })

        print(f"\n{dt}:")
        print(f"  x (W=80): {x_before:.4f} → {x_after:.4f}  Δ={delta_x:.4f}")
        print(f"  price: -20h→0h {pct_before:+.2f}%  0h→+20h {pct_after:+.2f}%")
        print(f"  resolutions: {row['resolutions']}  n_votes={row['n_votes']}")

    df_result = pd.DataFrame(result_rows)
    out_path = OUT_DIR / "p2_breakpoints_corn_c2609_final.csv"
    df_result.to_csv(out_path, index=False)
    print(f"\nFinal result saved to {out_path}")


if __name__ == "__main__":
    main()
