"""检查 m2609 x_hat 序列，看看变化频率"""

from pathlib import Path
import pandas as pd
import numpy as np

REPO = Path("/Users/gaolei/Documents/src/quant")
CSV_DIR = REPO / "project_data" / "market_data" / "csv"

W = 80


def main():
    df = pd.read_csv(CSV_DIR / "DCE.m2609.tqsdk.1h.csv", parse_dates=["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    df["log_ret"] = np.log(df["close"]).diff()
    df = df.dropna(subset=["log_ret"]).reset_index(drop=True)

    x_list = []
    for i in range(W - 1, len(df)):
        seg = df.iloc[i - W + 1:i + 1]
        mu = seg["log_ret"].mean()
        sd = seg["log_ret"].std(ddof=1)
        if sd <= 1e-6:
            continue
        x_hat = abs(mu) / sd
        x_list.append({
            "datetime": df.loc[i, "datetime"],
            "x_hat": x_hat,
            "close": df.loc[i, "close"],
        })
    df_x = pd.DataFrame(x_list)
    print(f"滚动 x_hat (W={W}): {len(df_x)} 个点 from {df_x['datetime'].min()} to {df_x['datetime'].max()}")
    print()

    # 统计超过 0.1 强度的次数
    cnt_high = (df_x["x_hat"] >= 0.1).sum()
    cnt_total = len(df_x)
    print(f"统计: 总计 {cnt_total} 个滚动窗口, x_hat >= 0.1 的有 {cnt_high} 个 ({cnt_high / cnt_total * 100:.1f}%)")
    print()

    # 按月份分组统计
    df_x["month"] = df_x["datetime"].dt.to_period("M")
    print("按月分布:")
    for month, group in df_x.groupby("month"):
        cnt_month = len(group)
        cnt_month_high = (group["x_hat"] >= 0.1).sum()
        print(f"  {month}: 总计 {cnt_month} 个，>=0.1 {cnt_month_high} 个 ({cnt_month_high / cnt_month * 100:.1f}%)，平均x={group['x_hat'].mean():.4f}")


if __name__ == "__main__":
    main()
