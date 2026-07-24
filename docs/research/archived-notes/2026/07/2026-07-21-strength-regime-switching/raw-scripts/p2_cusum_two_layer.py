"""路线 E：双层 CUSUM 断点检测 — 低层检测 + 高层共识
对比路线 A（多分辨率并行 + 共识）
"""

from pathlib import Path
import pandas as pd
import numpy as np

REPO = Path("/Users/gaolei/Documents/src/quant")
CSV_DIR = REPO / "project_data" / "market_data" / "csv"
OUT_DIR = REPO / "project_data" / "research" / "strength_regime_switching"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SYMBOL = "DCE.c2609"
# 双层参数
LOWER_W = 20          # 低层窗口：检测短期变化
LOWER_H = 3.0         # 低层阈值更松
UPPER_W = 80          # 高层窗口：整合确认
UPPER_H = 3.0         # 高层阈值放宽到 3σ，对比 4σ
MIN_INTERVAL = 50    # 两个断点最小间隔


def cusum_detect(x: np.ndarray, h_mult: float) -> list[int]:
    """CUSUM 检测返回断点索引（在 x 序列上）"""
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


def two_layer_cusum(df: pd.DataFrame, lower_w: int, upper_w: int) -> list[dict]:
    """双层 CUSUM 检测
    1. 低层滚动 x_hat 得到粗检出
    2. 高层滚动 x_hat 对粗检出做二次确认
    3. 最小间隔过滤
    """
    log_rets = np.log(df["close"]).diff().dropna().to_numpy()
    n = len(log_rets)

    # 第一步：低层检测 - 在 lower_w 上检测
    x_lower_list = []
    lower_indices = []
    stride = max(1, lower_w // 4)
    for i in range(lower_w - 1, n, stride):
        seg = log_rets[i - lower_w + 1:i + 1]
        mu = np.mean(seg)
        sd = np.std(seg, ddof=1)
        if sd <= 1e-6:
            continue
        x_hat = abs(mu) / sd
        x_lower_list.append(x_hat)
        # original index in df (log_rets index -> df index)
        lower_indices.append(i + 1)  # +1 because log_rets is offset by 1

    x_lower = np.array(x_lower_list)
    bp_lower = cusum_detect(x_lower, LOWER_H)
    print(f"第一层 (W={lower_w}, h={LOWER_H}σ): detected {len(bp_lower)} 粗检出")

    # 第二步：高层确认 - 对每个粗检出，在 upper_w 窗口确认
    confirmed = []
    last_center = -9999

    for bp_idx in bp_lower:
        center_original_lower = lower_indices[bp_idx]  # df 上的索引
        # 取 centered 窗口跑 upper_w
        start = center_original_lower - upper_w + 1
        if start < 0:
            continue
        if center_original_lower - last_center < MIN_INTERVAL:
            continue  # 太近，跳过

        seg = log_rets[start:center_original_lower + 1]
        mu = np.mean(seg)
        sd = np.std(seg, ddof=1)
        if sd <= 1e-6:
            continue
        x_upper = abs(mu) / sd

        # 计算前后变化 - 我们检测均值漂移
        # 获取漂移前后的均值
        # 漂移点在 center，所以 before = [center-upper_w+1 ... center], after = [center ... center+upper_w-1]
        if center_original_lower + upper_w >= n + 1:
            continue  # 不够长度

        seg_before = log_rets[center_original_lower - upper_w + 1:center_original_lower + 1]
        seg_after = log_rets[center_original_lower : center_original_lower + upper_w]
        mu_before = abs(np.mean(seg_before)) / np.std(seg_before, ddof=1) if np.std(seg_before, ddof=1) > 1e-6 else np.nan
        mu_after = abs(np.mean(seg_after)) / np.std(seg_after, ddof=1) if np.std(seg_after, ddof=1) > 1e-6 else np.nan
        delta_x = mu_after - mu_before

        # 如果变化超过阈值，确认
        if abs(delta_x) >= (UPPER_H * np.std(x_lower)):
            confirmed.append({
                "center_df_idx": center_original_lower,
                "x_before": round(mu_before, 4),
                "x_after": round(mu_after, 4),
                "delta_x": round(delta_x, 4),
            })
            last_center = center_original_lower

    print(f"第二层 (W={upper_w}, h={UPPER_H}σ): confirmed {len(confirmed)} 断点")
    return confirmed


def main():
    df = pd.read_csv(CSV_DIR / f"{SYMBOL}.tqsdk.1h.csv", parse_dates=["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    print(f"Loaded {SYMBOL}: {len(df)} 1h bars from {df['datetime'].min()} to {df['datetime'].max()}")

    confirmed = two_layer_cusum(df, LOWER_W, UPPER_W)

    # 整理输出
    result_rows = []
    for item in confirmed:
        idx = item["center_df_idx"]
        dt = df.loc[idx, "datetime"]
        # 价格变化
        start_idx = max(0, idx - 20)
        end_idx = min(len(df), idx + 20 + 1)
        first_close = df.loc[start_idx, "close"]
        bp_close = df.loc[idx, "close"]
        last_close = df.loc[end_idx - 1, "close"]
        pct_before = (bp_close - first_close) / first_close * 100
        pct_after = (last_close - bp_close) / bp_close * 100

        result_rows.append({
            "breakpoint_datetime": dt,
            "center_df_idx": idx,
            "x_before_80": item["x_before"],
            "x_after_80": item["x_after"],
            "delta_x": item["delta_x"],
            "pct_before_20h": round(pct_before, 2),
            "pct_after_20h": round(pct_after, 2),
        })

    df_result = pd.DataFrame(result_rows)
    out_path = OUT_DIR / "p2_breakpoints_corn_c2609_two_layer.csv"
    df_result.to_csv(out_path, index=False)
    print(f"\nSaved to {out_path}")

    # 打印
    print("\n--- 确认断点汇总 ---")
    for _, row in df_result.iterrows():
        dt = row["breakpoint_datetime"]
        print(f"{dt}: x={row['x_before_80']:.4f}→{row['x_after_80']:.4f} Δ={row['delta_x']:.4f}  price: {row['pct_before_20h']:+.2f}%/{row['pct_after_20h']:+.2f}%")


if __name__ == "__main__":
    main()
