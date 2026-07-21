"""检测强度变化超过 1.5σ 就报告一次切换，对比原方法（只断点后切换）"""

from pathlib import Path
import pandas as pd
import numpy as np

REPO = Path("/Users/gaolei/Documents/src/quant")
CSV_DIR = REPO / "project_data" / "market_data" / "csv"
OUT_DIR = REPO / "project_data" / "research" / "strength_regime_switching"

W = 80
THRESHOLD = 1.5  # sigma 倍数


def main():
    # 读取数据
    df = pd.read_csv(CSV_DIR / "DCE.m2609.tqsdk.1h.csv", parse_dates=["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    df["log_ret"] = np.log(df["close"]).diff()
    df = df.dropna(subset=["log_ret"]).reset_index(drop=True)

    # 滚动计算 x_hat
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

    # 计算全局均值标准差
    x_series = df_x["x_hat"].to_numpy()
    mu_global = float(np.mean(x_series))
    sigma_global = float(np.std(x_series))

    # 检测切换
    regimes = []
    current_regime = "MID"  # 开始默认中间
    start_idx = 0

    for i in range(len(df_x)):
        x = df_x.iloc[i]["x_hat"]
        if abs(x - mu_global) >= THRESHOLD * sigma_global:
            # 记录切换
            end_idx = i
            regimes.append({
                "start_datetime": df_x.iloc[start_idx]["datetime"],
                "end_datetime": df_x.iloc[end_idx]["datetime"],
                "regime": current_regime,
                "mean_x": float(df_x[start_idx:end_idx+1]["x_hat"].mean()),
            })
            # 切换 regime
            current_regime = "HIGH" if x >= mu_global else "LOW"
            start_idx = i + 1

    # 最后一段
    if start_idx < len(df_x):
        regimes.append({
            "start_datetime": df_x.iloc[start_idx]["datetime"],
            "end_datetime": df_x.iloc[len(df_x)-1]["datetime"],
            "regime": current_regime,
            "mean_x": float(df_x[start_idx:len(df_x)]["x_hat"].mean()),
        })

    df_result = pd.DataFrame(regimes)
    print(f"DCE.m2609 强度切换检测 (阈值={THRESHOLD}σ):")
    print(f"  总计检出 {len(df_result)} 次 regime 切换")
    print()
    for idx, row in df_result.iterrows():
        print(f"  {row['start_datetime']:%Y-%m-%d %H:%M} → {row['end_datetime']:%Y-%m-%d %H:%M} → {row['regime']}, 平均x={row['mean_x']:.4f}")

    # 保存
    out_path = OUT_DIR / f"p2_breakpoints_corn_c2609_{int(THRESHOLD*10)}sigma.csv"
    df_result.to_csv(out_path, index=False)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
