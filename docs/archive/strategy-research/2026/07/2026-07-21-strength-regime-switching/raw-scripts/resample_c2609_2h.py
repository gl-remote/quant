"""将 c2609 1h 数据重采样为 2h，然后运行 CUSUM 检测"""

from pathlib import Path
import pandas as pd
import numpy as np

REPO = Path("/Users/gaolei/Documents/src/quant")
CSV_DIR = REPO / "project_data" / "market_data" / "csv"
OUT_DIR = REPO / "project_data" / "research" / "strength_regime_switching"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# CUSUM 参数
CUSUM_H_MULTIPLIER = 4.0
CONSENSUS_TOLERANCE_H = 10  # 因为是 2h，容差减半
MIN_RESOLUTIONS_FOR_CONSENSUS = 2
DETECTION_WS = [10, 20, 40, 80]  # 对应原始 20h, 40h, 80h, 160h → 缩放一半


def resample_2h(df_1h: pd.DataFrame) -> pd.DataFrame:
    """将 1h K线重采样为 2h"""
    df_1h = df_1h.copy()
    df_1h["datetime"] = pd.to_datetime(df_1h["datetime"])
    df_1h = df_1h.set_index("datetime")

    # 重采样规则
    agg_dict = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
        "open_oi": "first",
        "close_oi": "last",
    }
    # 只保留有数据的
    df_2h = df_1h.resample("2h").agg(agg_dict).dropna(subset=["open"]).reset_index()
    return df_2h


def compute_x_hat_at_resolution(df: pd.DataFrame, W: int) -> pd.DataFrame:
    """计算给定分辨率 W(单位:bars)下的滚动 x̂_W(t)"""
    log_rets = np.log(df["close"]).diff().dropna().to_numpy()
    n = len(log_rets)
    stride = max(1, W // 4)

    x_hat_list = []
    indices = []

    for i in range(W - 1, n, stride):
        seg = log_rets[i - W + 1:i + 1]
        mu = np.mean(seg)
        sd = np.std(seg, ddof=1)
        if sd <= 1e-10:
            continue
        x_hat = abs(mu) / sd
        x_hat_list.append(x_hat)
        # 原始 df 中 log_ret 少一行，所以索引要调整
        original_i = i + 1
        indices.append(original_i)

    df_out = df.iloc[indices].copy()
    df_out["x_hat"] = x_hat_list
    df_out["window_W"] = W
    return df_out


def cusum_detect(x: np.ndarray, h_mult: float = 4.0) -> list[int]:
    """CUSUM 检测"""
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


def merge_breakpoints(breakpoints_by_w: dict[int, list[tuple[int, int]]],
                     tolerance_h: int, min_count: int) -> list[dict]:
    """合并断点，每个分辨率只计一票"""
    all_candidates = []
    for w, bps in breakpoints_by_w.items():
        for idx, t_h in bps:
            all_candidates.append((t_h, w))

    if not all_candidates:
        return []

    all_candidates.sort(key=lambda x: x[0])

    clusters = []
    current_cluster = [all_candidates[0]]
    for cand in all_candidates[1:]:
        t_curr, _ = cand
        t_first, _ = current_cluster[0]
        if t_curr - t_first <= tolerance_h:
            current_cluster.append(cand)
        else:
            clusters.append(current_cluster)
            current_cluster = [cand]
    clusters.append(current_cluster)

    confirmed = []
    for cluster in clusters:
        unique_ws = sorted(set(w for _, w in cluster))
        n_votes = len(unique_ws)
        if n_votes >= min_count:
            times = [t for t, _ in cluster]
            center_h = int(np.median(times))
            confirmed.append({
                "center_h": center_h,
                "n_votes": n_votes,
                "ws": unique_ws,
                "min_time_h": min(t for t, _ in cluster),
                "max_time_h": max(t for t, _ in cluster),
            })

    return confirmed


def main():
    # 读取 1h 数据
    df_1h = pd.read_csv(CSV_DIR / "DCE.c2609.tqsdk.1h.csv", parse_dates=["datetime"])
    df_1h = df_1h.sort_values("datetime").reset_index(drop=True)
    print(f"Original 1h data: {len(df_1h)} bars from {df_1h['datetime'].min()} to {df_1h['datetime'].max()}")

    # 重采样 2h
    df_2h = resample_2h(df_1h)
    df_2h["log_ret"] = np.log(df_2h["close"]).diff()
    df_2h = df_2h.dropna(subset=["log_ret"]).reset_index(drop=True)
    print(f"Resampled 2h data: {len(df_2h)} bars from {df_2h['datetime'].min()} to {df_2h['datetime'].max()}")

    # 多分辨率检测
    breakpoints_by_w = {}
    xhat_by_w = {}
    overall_start_idx = df_2h.index[0]

    for W in DETECTION_WS:
        df_xw = compute_x_hat_at_resolution(df_2h, W)
        x = df_xw["x_hat"].to_numpy()
        xhat_by_w[W] = df_xw
        bp_indices = cusum_detect(x, CUSUM_H_MULTIPLIER)
        # 转换为原始 2h 轴位置
        bp_time_2h = []
        for idx in bp_indices:
            original_idx = df_xw.index[idx]
            time_h_2h = original_idx - overall_start_idx
            bp_time_2h.append((idx, int(time_h_2h)))
        breakpoints_by_w[W] = bp_time_2h
        print(f"  W={W} (2h bars): detected {len(bp_indices)} breakpoints")

    confirmed = merge_breakpoints(breakpoints_by_w, CONSENSUS_TOLERANCE_H, MIN_RESOLUTIONS_FOR_CONSENSUS)
    print(f"\nConfirmed breakpoints after consensus: {len(confirmed)}")

    result_rows = []
    for i, conf in enumerate(confirmed):
        center_original_idx = overall_start_idx + conf["center_h"]
        dt = df_2h.loc[center_original_idx, "datetime"]

        # 计算前后强度（用 W=40 对应 80h 原始）
        x_before = np.nan
        x_after = np.nan
        delta_x = np.nan
        if 40 in xhat_by_w:
            df_40 = xhat_by_w[40]
            mask = df_40["datetime"] <= dt
            if mask.sum() > 0:
                closest_idx = mask[mask].index[-1]
                x_before = df_40.iloc[max(0, closest_idx - 2):closest_idx + 1]["x_hat"].mean()
                x_after = df_40.iloc[closest_idx:closest_idx + 3]["x_hat"].mean()
                delta_x = x_after - x_before

        # 价格变化
        center_abs_2h = int(center_original_idx)
        start_idx = max(0, center_abs_2h - 10)  # -20h 原始 = -10 2h
        end_idx = min(len(df_2h), center_abs_2h + 10 + 1)  # +20h 原始 = +10 2h
        first_close = df_2h.iloc[start_idx]["close"]
        bp_close = df_2h.loc[center_abs_2h, "close"]
        last_close = df_2h.iloc[end_idx - 1]["close"]
        pct_before = (bp_close - first_close) / first_close * 100
        pct_after = (last_close - bp_close) / bp_close * 100

        row = {
            "group": "corn_c2609_2h",
            "breakpoint_datetime": dt,
            "center_2h_abs": int(center_original_idx),
            "center_2h_rel": conf["center_h"],
            "n_votes": conf["n_votes"],
            "resolutions": ",".join(map(str, conf["ws"])),
            "x_before_40": round(x_before, 4) if not np.isnan(x_before) else np.nan,
            "x_after_40": round(x_after, 4) if not np.isnan(x_after) else np.nan,
            "delta_x": round(delta_x, 4) if not np.isnan(delta_x) else np.nan,
            "pct_before_20h": round(pct_before, 2),
            "pct_after_20h": round(pct_after, 2),
        }
        result_rows.append(row)

        print(f"  [{i+1}] {dt} → x: {x_before:.4f} → {x_after:.4f} (Δ={delta_x:.4f}) n_votes={conf['n_votes']}")
        print(f"      price: -20h→0h {pct_before:+.2f}%  0h→+20h {pct_after:+.2f}%")

    df_result = pd.DataFrame(result_rows)
    out_path = OUT_DIR / "p2_breakpoints_corn_c2609_2h.csv"
    df_result.to_csv(out_path, index=False)
    print(f"\nSaved to {out_path}")

    # 汇总 3月26日之后
    after_date = pd.Timestamp("2026-03-26")
    df_after = df_2h[df_2h["datetime"] >= after_date].reset_index(drop=True)
    print(f"\n--- 2026-03-26 之后 ({len(df_after)} 2h bars ≈ {len(df_after)/12:.1f} 交易日) ---")
    if len(df_after) >= 40:
        mu_total = df_after["log_ret"].mean()
        sd_total = df_after["log_ret"].std(ddof=1)
        x_total = abs(mu_total) / sd_total
        price_start = df_after.iloc[0]["close"]
        price_end = df_after.iloc[-1]["close"]
        pct_change = (price_end - price_start) / price_start * 100
        print(f"  average x (W=80h) = {x_total:.4f}")
        print(f"  price change: {pct_change:+.2f}%")


if __name__ == "__main__":
    main()
