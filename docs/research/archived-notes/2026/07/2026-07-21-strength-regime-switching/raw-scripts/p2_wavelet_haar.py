"""小波多分辨率分析 — Haar 小波分解，检出强度 regime 变化
对比 CUSUM 结果
"""

from pathlib import Path
import pandas as pd
import numpy as np
import pywt

REPO = Path("/Users/gaolei/Documents/src/quant")
CSV_DIR = REPO / "project_data" / "market_data" / "csv"
OUT_DIR = REPO / "project_data" / "research" / "strength_regime_switching"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SYMBOL = "DCE.c2609"
WINDOW = 80  # 滚动计算小波系数


def wavelet_breakpoint_detect(x: np.ndarray, level: int = 3) -> np.ndarray:
    """Haar 小波分解，返回各尺度细节系数
    细节系数绝对值越大，说明该位置越可能是断点
    """
    coeffs = pywt.wavedec(x, "haar", level=level)
    # coeffs[0] = approximation, coeffs[1:] = details
    details = coeffs[1:]
    # 上采样细节系数到原长度，计算绝对值和
    abs_coeff = np.zeros_like(x)
    for l, d in enumerate(details):
        # 每个细节系数对应 2^(level-l) 个原始点
        scale = 2 ** (level - l)
        for i, di in enumerate(d):
            start = i * scale
            end = (i+1) * scale
            abs_coeff[start:end] += abs(di) / scale  # 平均
    return abs_coeff


def main():
    df = pd.read_csv(CSV_DIR / f"{SYMBOL}.tqsdk.1h.csv", parse_dates=["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    df["log_ret"] = np.log(df["close"]).diff()
    df = df.dropna(subset=["log_ret"]).reset_index(drop=True)

    # 计算滚动 x_hat (W=80)
    xhat_list = []
    for i in range(WINDOW - 1, len(df), 20):
        seg = df.iloc[i - WINDOW + 1:i + 1]
        mu = seg["log_ret"].mean()
        sd = seg["log_ret"].std(ddof=1)
        if sd <= 1e-6:
            xhat = np.nan
        else:
            xhat = abs(mu) / sd
        xhat_list.append({
            "datetime": df.loc[i, "datetime"],
            "x_hat": xhat,
            "df_idx": i,
        })
    df_xhat = pd.DataFrame(xhat_list)
    df_xhat = df_xhat.dropna().reset_index(drop=True)
    print(f"滚动 x_hat: {len(df_xhat)} points from {df_xhat['datetime'].min()} to {df_xhat['datetime'].max()}")

    # 小波分解 x_hat 序列
    x_series = df_xhat["x_hat"].to_numpy().copy()
    print(f"小波分解: n={len(x_series)}, level=3")
    breakpoint_score = wavelet_breakpoint_detect(x_series, level=3)

    df_xhat["breakpoint_score"] = breakpoint_score
    # 找出高分位置
    threshold = np.mean(breakpoint_score) + 2 * np.std(breakpoint_score)
    candidates = df_xhat[breakpoint_score > threshold].sort_values("breakpoint_score", ascending=False)
    print(f"\n阈值 = mean + 2*std = {threshold:.4f}, 检出 {len(candidates)} 候选断点")

    # 按分数排序输出 top 5
    print("\nTop 10 候选断点:")
    print(f"{'日期时间':<20} {'x_hat':>8} {'score':>8}")
    print("-" * 40)
    for _, row in candidates.head(10).iterrows():
        print(f"{row['datetime']:%Y-%m-%d %H:%M} {row['x_hat']:>8.4f} {row['breakpoint_score']:>8.4f}")

    # 对比 CUSUM 检出日期
    print("\n--- 和多分辨率 CUSUM 对比 ---")
    cusum_df = pd.read_csv(OUT_DIR / "p2_breakpoints_corn_c2609.csv", parse_dates=["breakpoint_datetime"])
    print(f"CUSUM 检出 {len(cusum_df)} 个断点:")
    for _, row in cusum_df.iterrows():
        print(f"  {row['breakpoint_datetime']:%Y-%m-%d %H:%M}")

    # 保存小波结果
    out_path = OUT_DIR / "p2_breakpoints_corn_c2609_wavelet.csv"
    df_xhat.to_csv(out_path, index=False)
    print(f"\nSaved detailed result to {out_path}")

    # 统计和CUSUM重叠
    cusum_dates = set(pd.to_datetime(cusum_df["breakpoint_datetime"]).dt.strftime("%Y-%m-%d"))
    wavelet_dates = set(pd.to_datetime(candidates["datetime"]).dt.strftime("%Y-%m-%d"))
    overlap = cusum_dates & wavelet_dates
    print(f"\n日期重叠: {len(overlap)} / {len(cusum_dates)} 个 CUSUM 断点在小波候选中")


if __name__ == "__main__":
    main()
