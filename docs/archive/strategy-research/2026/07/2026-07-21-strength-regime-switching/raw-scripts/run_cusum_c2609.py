"""对 DCE.c2609 运行完整 CUSUM 断点检测"""

from pathlib import Path
import pandas as pd
import numpy as np

REPO = Path("/Users/gaolei/Documents/src/quant")
CSV_DIR = REPO / "project_data" / "market_data" / "csv"
OUT_DIR = REPO / "project_data" / "research" / "strength_regime_switching"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# CUSUM 参数
CUSUM_H_MULTIPLIER = 4.0
CONSENSUS_TOLERANCE_H = 20
MIN_RESOLUTIONS_FOR_CONSENSUS = 2
DETECTION_WS = [20, 40, 80, 160]


def load_1h(sym: str) -> pd.DataFrame:
    df = pd.read_csv(CSV_DIR / f"{sym}.tqsdk.1h.csv", parse_dates=["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    df["log_ret"] = np.log(df["close"]).diff()
    df = df.dropna(subset=["log_ret"]).reset_index(drop=True)
    return df


def compute_x_hat_at_resolution(df: pd.DataFrame, W: int) -> pd.DataFrame:
    """计算给定分辨率 W 下的滚动 x̂_W(t)"""
    log_rets = df["log_ret"].to_numpy()
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
        indices.append(i)

    df_out = df.iloc[indices].copy()
    df_out["x_hat"] = x_hat_list
    df_out["window_W"] = W
    return df_out


def cusum_detect(x: np.ndarray, h_mult: float = 4.0) -> list[int]:
    """CUSUM 检测均值漂移，返回断点索引"""
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


def analyze_c2609():
    print(f"Running multi-resolution CUSUM on DCE.c2609 ...")
    df = load_1h("DCE.c2609")
    print(f"Loaded {len(df)} 1h bars from {df['datetime'].min()} to {df['datetime'].max()}")

    breakpoints_by_w = {}
    xhat_by_w = {}
    overall_start_idx = df.index[0]

    for W in DETECTION_WS:
        df_xw = compute_x_hat_at_resolution(df, W)
        x = df_xw["x_hat"].to_numpy()
        xhat_by_w[W] = df_xw
        bp_indices = cusum_detect(x, CUSUM_H_MULTIPLIER)
        # 转换为原始时间轴位置
        bp_time_h = []
        for idx in bp_indices:
            original_idx = df_xw.index[idx]
            time_h = original_idx - overall_start_idx
            bp_time_h.append((idx, int(time_h)))
        breakpoints_by_w[W] = bp_time_h
        print(f"  W={W}: detected {len(bp_indices)} breakpoints")

    confirmed = merge_breakpoints(breakpoints_by_w, CONSENSUS_TOLERANCE_H, MIN_RESOLUTIONS_FOR_CONSENSUS)
    print(f"\nConfirmed breakpoints after consensus: {len(confirmed)}")

    result_rows = []
    for i, conf in enumerate(confirmed):
        center_original_idx = overall_start_idx + conf["center_h"]
        dt = df.loc[center_original_idx, "datetime"]
        # 检查前后强度变化
        # 找到对应的 x_hat 在最粗分辨率（80）上的值
        x_before = np.nan
        x_after = np.nan
        if 80 in xhat_by_w:
            df_80 = xhat_by_w[80]
            # 找到断点附近的 x_hat - 在原始数据上找最近 datetime
            mask = df_80["datetime"] <= dt
            if mask.sum() > 0:
                closest_idx = mask[mask].index[-1]
                # 前后平均
                x_before = df_80.iloc[max(0, closest_idx - 3):closest_idx + 1]["x_hat"].mean()
                x_after = df_80.iloc[closest_idx:closest_idx + 4]["x_hat"].mean()
        else:
            # 用 40 分辨率
            if 40 in xhat_by_w:
                df_40 = xhat_by_w[40]
                mask = df_40["datetime"] <= dt
                if mask.sum() > 0:
                    closest_idx = mask[mask].index[-1]
                    x_before = df_40.iloc[max(0, closest_idx - 2):closest_idx + 1]["x_hat"].mean()
                    x_after = df_40.iloc[closest_idx:closest_idx + 3]["x_hat"].mean()

        row = {
            "group": "corn_c2609",
            "breakpoint_datetime": dt,
            "center_h_abs": int(center_original_idx),
            "center_h_rel": conf["center_h"],
            "n_votes": conf["n_votes"],
            "resolutions": ",".join(map(str, conf["ws"])),
            "x_before_80": round(x_before, 4) if not np.isnan(x_before) else np.nan,
            "x_after_80": round(x_after, 4) if not np.isnan(x_after) else np.nan,
            "delta_x": round(x_after - x_before, 4) if not np.isnan(x_before) and not np.isnan(x_after) else np.nan,
            "min_h_rel": conf["min_time_h"],
            "max_h_rel": conf["max_time_h"],
        }
        result_rows.append(row)

        print(f"  [{i+1}] {dt} → x: {x_before:.4f} → {x_after:.4f} (Δ={x_after - x_before:.4f}) n_votes={conf['n_votes']}")

    df_result = pd.DataFrame(result_rows)
    out_path = OUT_DIR / "p2_breakpoints_corn_c2609.csv"
    df_result.to_csv(out_path, index=False)
    print(f"\nSaved to {out_path}")

    # 打印价格变化
    print("\n--- Price changes around breakpoints ---")
    for _, row in df_result.iterrows():
        dt = pd.to_datetime(row["breakpoint_datetime"])
        center_idx = int(row["center_h_abs"])
        start_idx = max(0, center_idx - 20)
        end_idx = min(len(df), center_idx + 20 + 1)
        window = df.iloc[start_idx:end_idx]
        first_close = window.iloc[0]["close"]
        bp_close = df.loc[center_idx, "close"]
        last_close = window.iloc[-1]["close"]
        pct_before = (bp_close - first_close) / first_close * 100
        pct_after = (last_close - bp_close) / bp_close * 100
        print(f"\n{row['breakpoint_datetime']}:")
        print(f"  -20h→0h: {pct_before:+.2f}%,  0h→+20h: {pct_after:+.2f}%")
        if not np.isnan(row["delta_x"]):
            print(f"  x_hat change: {row['delta_x']:+.4f}")


if __name__ == "__main__":
    analyze_c2609()
